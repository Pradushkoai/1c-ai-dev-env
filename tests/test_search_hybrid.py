"""
Тесты для гибридного поиска (P1.1: search_hybrid.py).

Проверяют:
1. Гибридный поиск с векторным недоступным → fallback на BM25
2. Гибридный поиск с векторным доступным (моки) → комбинированные scores
3. Нормализация scores
4. search_hybrid_auto — авто-выбор алгоритма
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.search_hybrid import search_hybrid, search_hybrid_auto, _normalize_scores


# ============================================================================
# Helpers
# ============================================================================


def _create_bm25_index(tmp_path: Path, methods: list[dict] | None = None) -> Path:
    """Создать тестовый BM25 индекс v2."""
    if methods is None:
        methods = [
            {
                "name_ru": "НайтиПоКоду",
                "name_en": "FindByCode",
                "syntax": "НайтиПоКоду(Код)",
                "description": "Находит элемент справочника по коду",
                "context": "Справочники",
            },
            {
                "name_ru": "СоздатьДокумент",
                "name_en": "CreateDocument",
                "syntax": "СоздатьДокумент()",
                "description": "Создаёт новый документ",
                "context": "Документы",
            },
        ]

    index_data = {
        "version": 2,
        "algorithm": "bm25",
        "methods": methods,
        "idf": {},
        "inverted_index": {},
        "doc_lengths": {0: 10, 1: 8},
        "avg_doc_length": 9.0,
        "total_methods": len(methods),
        "trigrams_index": {},
        "method_trigrams": {},
        "stem_map": {},
    }

    index_path = tmp_path / "fast-search-index.json"
    index_path.write_text(json.dumps(index_data, ensure_ascii=False), encoding="utf-8")
    return index_path


# ============================================================================
# Тесты _normalize_scores
# ============================================================================


class TestNormalizeScores:
    """Проверка нормализации scores."""

    def test_normalize_empty_list(self) -> None:
        """Пустой список → пустой список."""
        result = _normalize_scores([])
        assert result == []

    def test_normalize_single_element(self) -> None:
        """Один элемент → возвращается как есть (no range)."""
        result = _normalize_scores([{"score": 5.0, "name": "test"}])
        assert len(result) == 1
        assert result[0]["score"] == 5.0  # не нормализуется (min==max)

    def test_normalize_multiple_elements(self) -> None:
        """Несколько элементов → scores в [0, 1]."""
        results = [
            {"score": 10.0, "name": "a"},
            {"score": 5.0, "name": "b"},
            {"score": 0.0, "name": "c"},
        ]
        normalized = _normalize_scores(results)
        scores = [r["score"] for r in normalized]
        assert max(scores) == 1.0  # max → 1.0
        assert min(scores) == 0.0  # min → 0.0
        # Средний элемент нормализован
        assert 0.0 < normalized[1]["score"] < 1.0

    def test_normalize_preserves_other_fields(self) -> None:
        """Нормализация сохраняет другие поля."""
        results = [{"score": 10.0, "name": "a", "description": "test"}]
        normalized = _normalize_scores(results)
        assert normalized[0]["name"] == "a"
        assert normalized[0]["description"] == "test"


# ============================================================================
# Тесты search_hybrid — fallback на BM25
# ============================================================================


class TestSearchHybridFallback:
    """Гибридный поиск с недоступным векторным → fallback на BM25."""

    def test_hybrid_fallback_to_bm25_only(self, tmp_path: Path) -> None:
        """Если vector недоступен → вернуть BM25 результаты с source='bm25'."""
        index_path = _create_bm25_index(tmp_path)

        with patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = False

            results = search_hybrid(index_path, "найти", limit=5, alpha=0.5)

        assert isinstance(results, list)
        for r in results:
            assert r.get("source") == "bm25"

    def test_hybrid_alpha_validation(self, tmp_path: Path) -> None:
        """alpha вне [0, 1] → ValueError."""
        index_path = _create_bm25_index(tmp_path)
        with pytest.raises(ValueError, match="alpha"):
            search_hybrid(index_path, "test", limit=5, alpha=1.5)
        with pytest.raises(ValueError, match="alpha"):
            search_hybrid(index_path, "test", limit=5, alpha=-0.1)


# ============================================================================
# Тесты search_hybrid — гибридный режим с моками
# ============================================================================


class TestSearchHybridCombined:
    """Гибридный поиск с векторным доступным (моки)."""

    def test_hybrid_combines_bm25_and_vector(self, tmp_path: Path) -> None:
        """Гибридный поиск комбинирует BM25 и vector scores."""
        index_path = _create_bm25_index(tmp_path)

        # Мокаем VectorSearch
        mock_vs = MagicMock()
        mock_vs.is_available.return_value = True
        mock_vs.search.return_value = [
            {
                "score": 0.9,
                "name_ru": "НайтиПоКоду",
                "name_en": "FindByCode",
                "syntax": "НайтиПоКоду(Код)",
                "description": "Находит элемент по коду",
                "context": "Справочники",
            }
        ]

        results = search_hybrid(index_path, "найти", limit=5, alpha=0.5, vector_search=mock_vs)

        assert len(results) > 0
        # Результаты отсортированы по убыванию score
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_hybrid_results_have_combined_fields(self, tmp_path: Path) -> None:
        """Результаты содержат bm25_score, vector_score, source."""
        index_path = _create_bm25_index(tmp_path)

        mock_vs = MagicMock()
        mock_vs.is_available.return_value = True
        mock_vs.search.return_value = [
            {
                "score": 0.9,
                "name_ru": "НайтиПоКоду",
                "name_en": "FindByCode",
                "syntax": "НайтиПоКоду(Код)",
                "description": "Находит элемент по коду",
                "context": "Справочники",
            }
        ]

        results = search_hybrid(index_path, "найти", limit=5, alpha=0.5, vector_search=mock_vs)

        for r in results:
            assert "bm25_score" in r
            assert "vector_score" in r
            assert "source" in r
            assert r["source"] in ("hybrid", "bm25", "vector")

    def test_hybrid_alpha_1_means_bm25_only(self, tmp_path: Path) -> None:
        """alpha=1.0 → только BM25 (vector_score не влияет)."""
        index_path = _create_bm25_index(tmp_path)

        mock_vs = MagicMock()
        mock_vs.is_available.return_value = True
        mock_vs.search.return_value = [
            {
                "score": 0.9,
                "name_ru": "VectorOnly",
                "name_en": "VectorOnly",
                "syntax": "",
                "description": "Vector only result",
                "context": "",
            }
        ]

        results = search_hybrid(index_path, "найти", limit=5, alpha=1.0, vector_search=mock_vs)
        # alpha=1.0 → combined score = bm25_score, vector не влияет
        for r in results:
            # Если метод есть в BM25, его combined score = bm25_score (нормализованный)
            assert r["score"] == r["bm25_score"] * 1.0 + r["vector_score"] * 0.0


# ============================================================================
# Тесты search_hybrid_auto
# ============================================================================


class TestSearchHybridAuto:
    """Авто-выбор алгоритма."""

    def test_auto_uses_hybrid_when_available(self, tmp_path: Path) -> None:
        """search_hybrid_auto использует hybrid если vector доступен."""
        index_path = _create_bm25_index(tmp_path)

        with patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = True
            mock_instance.search.return_value = []

            results = search_hybrid_auto(index_path, "найти", limit=5)

        assert isinstance(results, list)

    def test_auto_fallback_to_bm25_when_unavailable(self, tmp_path: Path) -> None:
        """search_hybrid_auto fallback на BM25 если vector недоступен."""
        index_path = _create_bm25_index(tmp_path)

        with patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = False

            results = search_hybrid_auto(index_path, "найти", limit=5)

        assert isinstance(results, list)
        # Все результаты имеют source='bm25' (fallback)
        for r in results:
            assert r.get("source") == "bm25"

    def test_auto_handles_missing_index(self, tmp_path: Path) -> None:
        """search_hybrid_auto с несуществующим индексом → пустой список."""
        index_path = tmp_path / "nonexistent.json"

        with patch("src.services.search_hybrid.VectorSearch") as MockVS:
            mock_instance = MockVS.return_value
            mock_instance.is_available.return_value = False

            results = search_hybrid_auto(index_path, "найти", limit=5)

        assert results == []
