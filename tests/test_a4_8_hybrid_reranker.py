"""
A4.8 (2026-07-06): Тесты для hybrid reranker.

Покрывает:
- 5 алгоритмов: WEIGHTED_FUSION, RRF, MMR, COMBSUM, COMBMNZ
- RerankingConfig dataclass
- RerankedResult dataclass
- Helpers: _normalize_scores, _jaccard_similarity
- Edge cases: empty lists, single result, all in both lists
- Integration с search_hybrid_reranked (mocked)
- CLI demo
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from src.services.hybrid_reranker import (
    RerankingAlgorithm,
    RerankingConfig,
    RerankedResult,
    _jaccard_similarity,
    _normalize_scores,
    main,
    rerank,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def bm25_results() -> list[dict]:
    """BM25 результаты (sorted by score desc)."""
    return [
        {"name_en": "Find", "name_ru": "Найти", "description": "Найти элемент", "score": 5.0},
        {"name_en": "FindByCode", "name_ru": "НайтиПоКоду", "description": "По коду", "score": 4.0},
        {"name_en": "FindByName", "name_ru": "НайтиПоНаименованию", "description": "По имени", "score": 3.0},
    ]


@pytest.fixture
def vector_results() -> list[dict]:
    """Vector результаты (sorted by score desc)."""
    return [
        {"name_en": "FindByCode", "name_ru": "НайтиПоКоду", "description": "По коду", "score": 0.9},
        {"name_en": "Search", "name_ru": "Поиск", "description": "Поиск элементов", "score": 0.8},
        {"name_en": "Find", "name_ru": "Найти", "description": "Найти элемент", "score": 0.7},
    ]


# ============================================================================
# RerankingAlgorithm enum tests
# ============================================================================


class TestRerankingAlgorithm:
    def test_all_algorithms_defined(self) -> None:
        assert RerankingAlgorithm.WEIGHTED_FUSION == "weighted_fusion"
        assert RerankingAlgorithm.RRF == "rrf"
        assert RerankingAlgorithm.MMR == "mmr"
        assert RerankingAlgorithm.COMBSUM == "combsum"
        assert RerankingAlgorithm.COMBMNZ == "combmnz"

    def test_enum_has_5_algorithms(self) -> None:
        assert len(list(RerankingAlgorithm)) == 5

    def test_enum_is_str(self) -> None:
        """Алгоритм — str enum (для JSON serialization)."""
        assert isinstance(RerankingAlgorithm.RRF.value, str)


# ============================================================================
# RerankingConfig dataclass tests
# ============================================================================


class TestRerankingConfig:
    def test_defaults(self) -> None:
        config = RerankingConfig()
        assert config.algorithm == RerankingAlgorithm.RRF
        assert config.limit == 10
        assert config.alpha == 0.5
        assert config.rrf_k == 60
        assert config.mmr_lambda == 0.7
        assert config.doc_id_field == "name_en"

    def test_custom_values(self) -> None:
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.MMR,
            limit=5,
            mmr_lambda=0.3,
        )
        assert config.algorithm == RerankingAlgorithm.MMR
        assert config.limit == 5
        assert config.mmr_lambda == 0.3


# ============================================================================
# RerankedResult dataclass tests
# ============================================================================


class TestRerankedResult:
    def test_creation(self) -> None:
        r = RerankedResult(
            doc={"name_en": "Test"},
            score=0.5,
        )
        assert r.doc == {"name_en": "Test"}
        assert r.score == 0.5
        assert r.bm25_score == 0.0
        assert r.vector_score == 0.0
        assert r.source == "hybrid"
        assert r.appears_in == []


# ============================================================================
# Weighted Fusion tests
# ============================================================================


class TestWeightedFusion:
    def test_basic_weighted_fusion(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.WEIGHTED_FUSION,
            alpha=0.5,
            limit=10,
        )
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0
        assert all(isinstance(r, RerankedResult) for r in results)

    def test_alpha_zero_means_vector_only(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """alpha=0 → только vector score."""
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.WEIGHTED_FUSION,
            alpha=0.0,
        )
        results = rerank(bm25_results, vector_results, config)
        # Для документов только в BM25 (FindByName) — score должен быть 0
        for r in results:
            if r.doc["name_en"] == "FindByName":
                assert r.score == 0.0

    def test_alpha_one_means_bm25_only(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """alpha=1 → только BM25 score."""
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.WEIGHTED_FUSION,
            alpha=1.0,
        )
        results = rerank(bm25_results, vector_results, config)
        # Для документов только в vector (Search) — score должен быть 0
        for r in results:
            if r.doc["name_en"] == "Search":
                assert r.score == 0.0

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            rerank(
                [{"name_en": "x", "score": 1.0}],
                [{"name_en": "x", "score": 1.0}],
                RerankingConfig(algorithm=RerankingAlgorithm.WEIGHTED_FUSION, alpha=1.5),
            )

    def test_hybrid_source_for_both_lists(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """Документ в обоих списках → source='hybrid'."""
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.WEIGHTED_FUSION,
            alpha=0.5,
        )
        results = rerank(bm25_results, vector_results, config)
        # Find и FindByCode в обоих списках
        find_result = next(r for r in results if r.doc["name_en"] == "Find")
        assert find_result.source == "hybrid"
        assert "bm25" in find_result.appears_in
        assert "vector" in find_result.appears_in


# ============================================================================
# RRF tests
# ============================================================================


class TestRRF:
    def test_basic_rrf(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0

    def test_rrf_doc_in_both_lists_gets_higher_score(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """Документ в обоих списках должен иметь более высокий score."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, limit=10)
        results = rerank(bm25_results, vector_results, config)

        # FindByCode в обоих списках (rank 1 в vector, rank 2 в bm25)
        find_by_code = next(r for r in results if r.doc["name_en"] == "FindByCode")
        find_by_name = next(r for r in results if r.doc["name_en"] == "FindByName")

        # FindByCode в обоих списках → score должен быть выше
        assert find_by_code.score > find_by_name.score

    def test_rrf_formula(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """Проверка формулы RRF: score = 1/(k+rank_bm25) + 1/(k+rank_vector)."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, rrf_k=60, limit=10)
        results = rerank(bm25_results, vector_results, config)

        # Find: BM25 rank 1, vector rank 3
        find = next(r for r in results if r.doc["name_en"] == "Find")
        expected = 1.0 / (60 + 1) + 1.0 / (60 + 3)
        assert abs(find.score - expected) < 1e-9

    def test_rrf_invalid_k_raises(self) -> None:
        with pytest.raises(ValueError, match="rrf_k"):
            rerank(
                [{"name_en": "x", "score": 1.0}],
                [{"name_en": "x", "score": 1.0}],
                RerankingConfig(algorithm=RerankingAlgorithm.RRF, rrf_k=0),
            )

    def test_rrf_no_normalization_needed(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """RRF не требует нормализации scores — работает с разными шкалами."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF)
        results = rerank(bm25_results, vector_results, config)
        # Все scores должны быть > 0 для документов в списках
        assert all(r.score > 0 for r in results)


# ============================================================================
# MMR tests
# ============================================================================


class TestMMR:
    def test_basic_mmr(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(algorithm=RerankingAlgorithm.MMR, limit=3)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0

    def test_mmr_promotes_diversity(self) -> None:
        """MMR с low lambda → более diverse результаты."""
        # Создаём документы с большой overlap (similar)
        bm25 = [
            {"name_en": "Find1", "description": "find element code", "score": 5.0},
            {"name_en": "Find2", "description": "find element code", "score": 4.0},
            {"name_en": "Search1", "description": "search query text", "score": 3.0},
        ]
        vector = [
            {"name_en": "Find1", "description": "find element code", "score": 0.9},
            {"name_en": "Find2", "description": "find element code", "score": 0.8},
            {"name_en": "Search1", "description": "search query text", "score": 0.7},
        ]

        # High lambda (0.9) → больше relevance, меньше diversity
        config_high = RerankingConfig(
            algorithm=RerankingAlgorithm.MMR, mmr_lambda=0.9, limit=3
        )
        results_high = rerank(bm25, vector, config_high)

        # Low lambda (0.1) → больше diversity
        config_low = RerankingConfig(
            algorithm=RerankingAlgorithm.MMR, mmr_lambda=0.1, limit=3
        )
        results_low = rerank(bm25, vector, config_low)

        # Порядки могут отличаться
        high_ids = [r.doc["name_en"] for r in results_high]
        low_ids = [r.doc["name_en"] for r in results_low]
        # Оба должны содержать все 3 документа
        assert set(high_ids) == {"Find1", "Find2", "Search1"}
        assert set(low_ids) == {"Find1", "Find2", "Search1"}

    def test_mmr_invalid_lambda_raises(self) -> None:
        with pytest.raises(ValueError, match="mmr_lambda"):
            rerank(
                [{"name_en": "x", "score": 1.0}],
                [{"name_en": "x", "score": 1.0}],
                RerankingConfig(algorithm=RerankingAlgorithm.MMR, mmr_lambda=1.5),
            )

    def test_mmr_first_doc_is_most_relevant(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """Первый документ в MMR — самый релевантный (нет diversity penalty)."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.MMR, limit=3)
        results = rerank(bm25_results, vector_results, config)
        # FindByCode имеет высший RRF score (rank 1 в vector, rank 2 в bm25)
        assert results[0].doc["name_en"] == "FindByCode"


# ============================================================================
# CombSUM tests
# ============================================================================


class TestCombSUM:
    def test_basic_combsum(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(algorithm=RerankingAlgorithm.COMBSUM)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0

    def test_combsum_sums_normalized_scores(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """CombSUM = sum of normalized scores."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.COMBSUM, limit=10)
        results = rerank(bm25_results, vector_results, config)

        # Документ в обоих списках должен иметь score = bm25_norm + vector_norm
        find = next(r for r in results if r.doc["name_en"] == "Find")
        # BM25: Find is rank 1, score 5.0 → max → normalized = 1.0
        # Vector: Find is rank 3, score 0.7 → normalized = (0.7-0.7)/(0.9-0.7) = 0.0
        # CombSUM = 1.0 + 0.0 = 1.0
        assert abs(find.score - 1.0) < 1e-9


# ============================================================================
# CombMNZ tests
# ============================================================================


class TestCombMNZ:
    def test_basic_combmnz(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(algorithm=RerankingAlgorithm.COMBMNZ)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0

    def test_combmnz_doubles_score_for_both_lists(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """CombMNZ = CombSUM × count_of_lists. Документ в обоих списках → ×2."""
        config_sum = RerankingConfig(algorithm=RerankingAlgorithm.COMBSUM, limit=10)
        config_mnz = RerankingConfig(algorithm=RerankingAlgorithm.COMBMNZ, limit=10)

        results_sum = rerank(bm25_results, vector_results, config_sum)
        results_mnz = rerank(bm25_results, vector_results, config_mnz)

        # Для Find (в обоих списках): mnz = sum × 2
        sum_find = next(r for r in results_sum if r.doc["name_en"] == "Find")
        mnz_find = next(r for r in results_mnz if r.doc["name_en"] == "Find")
        assert abs(mnz_find.score - sum_find.score * 2) < 1e-9


# ============================================================================
# Helpers tests
# ============================================================================


class TestNormalizeScores:
    def test_normalize_basic(self) -> None:
        results = [{"score": 5.0}, {"score": 3.0}, {"score": 1.0}]
        normalized = _normalize_scores(results)
        scores = [r["score"] for r in normalized]
        assert scores[0] == 1.0   # max
        assert scores[2] == 0.0   # min
        assert scores[1] == 0.5   # midpoint

    def test_normalize_empty(self) -> None:
        assert _normalize_scores([]) == []

    def test_normalize_all_equal(self) -> None:
        """Если все scores одинаковые — возвращаем как есть."""
        results = [{"score": 5.0}, {"score": 5.0}]
        normalized = _normalize_scores(results)
        # No division by zero
        assert len(normalized) == 2

    def test_normalize_preserves_other_fields(self) -> None:
        results = [{"score": 5.0, "name": "x"}, {"score": 1.0, "name": "y"}]
        normalized = _normalize_scores(results)
        assert normalized[0]["name"] == "x"
        assert normalized[1]["name"] == "y"


class TestJaccardSimilarity:
    def test_identical_docs(self) -> None:
        doc = {"name_ru": "Найти", "description": "поиск элемента"}
        assert _jaccard_similarity(doc, doc) == 1.0

    def test_completely_different(self) -> None:
        doc1 = {"name_ru": "AAA", "description": "xxx"}
        doc2 = {"name_ru": "BBB", "description": "yyy"}
        assert _jaccard_similarity(doc1, doc2) == 0.0

    def test_partial_overlap(self) -> None:
        doc1 = {"name_ru": "find", "description": "element code"}
        doc2 = {"name_ru": "search", "description": "element query"}
        # words1: {find, element, code}
        # words2: {search, element, query}
        # intersection: {element} = 1
        # union: {find, element, code, search, query} = 5
        # Jaccard = 1/5 = 0.2
        assert abs(_jaccard_similarity(doc1, doc2) - 0.2) < 1e-9

    def test_empty_docs(self) -> None:
        assert _jaccard_similarity({}, {}) == 0.0

    def test_case_insensitive(self) -> None:
        doc1 = {"name_ru": "Find", "description": ""}
        doc2 = {"name_ru": "FIND", "description": ""}
        assert _jaccard_similarity(doc1, doc2) == 1.0


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_bm25(self, vector_results: list[dict]) -> None:
        """Пустой BM25 — все результаты из vector."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF)
        results = rerank([], vector_results, config)
        assert len(results) == 3
        assert all(r.source == "vector" for r in results)

    def test_empty_vector(self, bm25_results: list[dict]) -> None:
        """Пустой vector — все результаты из BM25."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF)
        results = rerank(bm25_results, [], config)
        assert len(results) == 3
        assert all(r.source == "bm25" for r in results)

    def test_both_empty(self) -> None:
        config = RerankingConfig()
        assert rerank([], [], config) == []

    def test_single_result_in_each(self) -> None:
        bm25 = [{"name_en": "X", "score": 1.0}]
        vector = [{"name_en": "Y", "score": 0.5}]
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, limit=10)
        results = rerank(bm25, vector, config)
        assert len(results) == 2

    def test_limit_truncates_results(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, limit=2)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) <= 2

    def test_doc_without_id_skipped(
        self, bm25_results: list[dict], vector_results: list[dict]
    ) -> None:
        """Документ без doc_id_field skipped."""
        bm25_with_missing = [{"description": "no name", "score": 1.0}] + bm25_results
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, limit=10)
        results = rerank(bm25_with_missing, vector_results, config)
        # Документ без name_en skipped
        assert all(r.doc.get("name_en") for r in results)


# ============================================================================
# Custom doc_id_field tests
# ============================================================================


class TestCustomDocIdField:
    def test_custom_field_used_for_dedup(self) -> None:
        """Custom doc_id_field используется для дедупликации."""
        bm25 = [
            {"id": "1", "name_en": "X", "score": 5.0},
            {"id": "2", "name_en": "Y", "score": 4.0},
        ]
        vector = [
            {"id": "1", "name_en": "X", "score": 0.9},
            {"id": "3", "name_en": "Z", "score": 0.8},
        ]
        config = RerankingConfig(
            algorithm=RerankingAlgorithm.RRF,
            doc_id_field="id",
            limit=10,
        )
        results = rerank(bm25, vector, config)
        # Документ с id=1 в обоих списках → source='hybrid'
        doc1 = next(r for r in results if r.doc["id"] == "1")
        assert doc1.source == "hybrid"
        assert len(doc1.appears_in) == 2


# ============================================================================
# Integration с search_hybrid_reranked (mocked)
# ============================================================================


class TestSearchHybridReranked:
    """Тесты search_hybrid_reranked с mocked BM25 + vector."""

    def test_search_hybrid_reranked_returns_results(
        self, tmp_path, bm25_results, vector_results
    ) -> None:
        from src.services.search_hybrid import search_hybrid_reranked

        # Create dummy BM25 index
        import json
        index_path = tmp_path / "index.json"
        index_path.write_text(
            json.dumps({"methods": bm25_results, "version": 3}),
            encoding="utf-8",
        )

        # Mock search_bm25 to return bm25_results
        # Mock VectorSearch.search to return vector_results
        with patch("src.services.search_hybrid.search_bm25", return_value=bm25_results), \
             patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = True
            mock_instance.search.return_value = vector_results

            results = search_hybrid_reranked(
                index_path, "test query", limit=5,
                algorithm=RerankingAlgorithm.RRF,
            )

            assert len(results) > 0
            assert all("score" in r for r in results)
            assert all("source" in r for r in results)

    def test_search_hybrid_reranked_fallback_to_bm25(self, tmp_path, bm25_results) -> None:
        """Если vector недоступен — fallback на BM25."""
        from src.services.search_hybrid import search_hybrid_reranked

        import json
        index_path = tmp_path / "index.json"
        index_path.write_text(
            json.dumps({"methods": bm25_results, "version": 3}),
            encoding="utf-8",
        )

        with patch("src.services.search_hybrid.search_bm25", return_value=bm25_results), \
             patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = False

            results = search_hybrid_reranked(index_path, "test", limit=5)

            assert len(results) > 0
            assert all(r.get("source") == "bm25" for r in results)


# ============================================================================
# Algorithm comparison tests
# ============================================================================


class TestAlgorithmComparison:
    """Сравнение алгоритмов — все должны возвращать валидные результаты."""

    @pytest.mark.parametrize("algo", list(RerankingAlgorithm))
    def test_all_algorithms_produce_results(
        self,
        algo: RerankingAlgorithm,
        bm25_results: list[dict],
        vector_results: list[dict],
    ) -> None:
        config = RerankingConfig(algorithm=algo, limit=10)
        results = rerank(bm25_results, vector_results, config)
        assert len(results) > 0
        # Все scores должны быть конечными числами
        assert all(isinstance(r.score, (int, float)) for r in results)
        assert all(math.isfinite(r.score) for r in results if isinstance(r.score, float))

    def test_results_sorted_by_score_desc(
        self,
        bm25_results: list[dict],
        vector_results: list[dict],
    ) -> None:
        """Результаты отсортированы по убыванию score."""
        config = RerankingConfig(algorithm=RerankingAlgorithm.RRF, limit=10)
        results = rerank(bm25_results, vector_results, config)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_runs_successfully(self, capsys) -> None:
        import sys
        sys.argv = ["hybrid_reranker"]
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "Algorithm" in captured.out
        assert "Score" in captured.out

    def test_cli_with_algorithm(self, capsys) -> None:
        import sys
        sys.argv = ["hybrid_reranker", "--algorithm", "rrf"]
        rc = main()
        assert rc == 0

    def test_cli_with_mmr(self, capsys) -> None:
        import sys
        sys.argv = ["hybrid_reranker", "--algorithm", "mmr", "--mmr-lambda", "0.3"]
        rc = main()
        assert rc == 0
