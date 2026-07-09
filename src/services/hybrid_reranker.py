"""
A4.8 (2026-07-06): Hybrid reranking — продвинутые алгоритмы комбинирования.

Существующий search_hybrid.py использует только weighted fusion:
    score = α * bm25_score + (1-α) * vector_score

Этот модуль добавляет продвинутые алгоритмы reranking:

1. **Reciprocal Rank Fusion (RRF)** — самый популярный алгоритм в IR:
   score = sum(1 / (k + rank_i)) для каждого списка
   Преимущества: не требует нормализации scores, устойчив к разным метрикам,
   работает даже если scores в разных шкалах.

2. **Maximal Marginal Relevance (MMR)** — diversity-aware reranking:
   На каждой итерации выбираем документ, который:
   - максимально релевантен запросу (relevance)
   - минимально похож на уже выбранные (diversity)
   score = α * relevance(doc, query) - (1-α) * max(similarity(doc, selected))
   Предотвращает дублирование похожих результатов.

3. **Weighted Fusion** (существующий) — оставлен для совместимости.

4. **CombSUM** — комбинирует нормализованные scores:
   score = sum(normalized_score_i)

5. **CombMNZ** — CombSUM + bonus за появление в нескольких списках:
   score = CombSUM * count_of_lists_where_doc_appears

Использование:
    from src.services.hybrid_reranker import rerank, RerankingAlgorithm

    # RRF (recommended default)
    results = rerank(
        bm25_results= bm25_list,
        vector_results=vector_list,
        algorithm=RerankingAlgorithm.RRF,
        limit=10,
    )

    # MMR for diversity
    results = rerank(
        bm25_results=bm25_list,
        vector_results=vector_list,
        algorithm=RerankingAlgorithm.MMR,
        limit=10,
        mmr_lambda=0.7,   # 0.7 = more relevance, 0.3 = more diversity
    )

Алгоритмы НЕ требуют реальных embeddings для similarity — используют
совпадение слов в name_ru/description (Jaccard similarity).
Для MMR с embeddings — см. параметр similarity_func.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Types
# ============================================================================

# Функция для вычисления similarity между двумя документами [0, 1]
SimilarityFunc = Callable[[dict[str, Any], dict[str, Any]], float]


class RerankingAlgorithm(str, Enum):
    """Алгоритмы reranking."""

    WEIGHTED_FUSION = "weighted_fusion"   # alpha * bm25 + (1-alpha) * vector
    RRF = "rrf"                           # Reciprocal Rank Fusion
    MMR = "mmr"                           # Maximal Marginal Relevance
    COMBSUM = "combsum"                   # sum of normalized scores
    COMBMNZ = "combmnz"                   # combsum * count_of_lists


@dataclass
class RerankingConfig:
    """Конфигурация reranking."""

    algorithm: RerankingAlgorithm = RerankingAlgorithm.RRF
    limit: int = 10

    # Для WEIGHTED_FUSION
    alpha: float = 0.5          # вес BM25 (0.5 = баланс)

    # Для RRF
    rrf_k: int = 60             # стандартное значение из оригинальной статьи

    # Для MMR
    mmr_lambda: float = 0.7     # 0.7 = more relevance, 0.3 = more diversity

    # Ключ для идентификации документа (уникальный ID)
    doc_id_field: str = "name_en"

    # Функция similarity для MMR (по умолчанию — Jaccard на словах)
    similarity_func: SimilarityFunc | None = None


@dataclass
class RerankedResult:
    """Результат reranking."""

    doc: dict[str, Any]
    score: float
    bm25_score: float = 0.0
    vector_score: float = 0.0
    bm25_rank: int = 0          # 0 = not in BM25 list
    vector_rank: int = 0        # 0 = not in vector list
    source: str = "hybrid"      # bm25 / vector / hybrid
    appears_in: list[str] = field(default_factory=list)   # ["bm25", "vector"]


# ============================================================================
# Public API
# ============================================================================


def rerank(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig | None = None,
) -> list[RerankedResult]:
    """Rerank комбинацию BM25 + vector результатов.

    Args:
        bm25_results: Результаты BM25 (с полем 'score').
        vector_results: Результаты vector search (с полем 'score').
        config: Конфигурация reranking. Если None — использует RRF defaults.

    Returns:
        Список RerankedResult, отсортированный по убыванию score.
    """
    if config is None:
        config = RerankingConfig()

    if config.algorithm == RerankingAlgorithm.WEIGHTED_FUSION:
        results = _weighted_fusion(bm25_results, vector_results, config)
    elif config.algorithm == RerankingAlgorithm.RRF:
        results = _reciprocal_rank_fusion(bm25_results, vector_results, config)
    elif config.algorithm == RerankingAlgorithm.MMR:
        results = _maximal_marginal_relevance(bm25_results, vector_results, config)
    elif config.algorithm == RerankingAlgorithm.COMBSUM:
        results = _combsum(bm25_results, vector_results, config)
    elif config.algorithm == RerankingAlgorithm.COMBMNZ:
        results = _combmnz(bm25_results, vector_results, config)
    else:
        raise ValueError(f"Unknown reranking algorithm: {config.algorithm}")

    # Ограничиваем количество результатов
    return results[: config.limit]


# ============================================================================
# Algorithm 1: Weighted Fusion (существующий подход, формализован)
# ============================================================================


def _weighted_fusion(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig,
) -> list[RerankedResult]:
    """Взвешенное объединение: score = alpha * bm25 + (1-alpha) * vector.

    Scores нормализуются min-max в [0, 1] перед объединением.
    """
    alpha = config.alpha
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")

    # Нормализуем scores
    bm25_norm = _normalize_scores(bm25_results)
    vector_norm = _normalize_scores(vector_results)

    # Объединяем по doc_id
    combined: dict[str, RerankedResult] = {}

    for rank, r in enumerate(bm25_norm, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        combined[doc_id] = RerankedResult(
            doc=r,
            score=alpha * r.get("score", 0.0),
            bm25_score=r.get("score", 0.0),
            vector_score=0.0,
            bm25_rank=rank,
            source="bm25",
            appears_in=["bm25"],
        )

    for rank, r in enumerate(vector_norm, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        if doc_id in combined:
            existing = combined[doc_id]
            existing.vector_score = r.get("score", 0.0)
            existing.vector_rank = rank
            existing.score += (1.0 - alpha) * r.get("score", 0.0)
            existing.appears_in.append("vector")
            existing.source = "hybrid"
        else:
            combined[doc_id] = RerankedResult(
                doc=r,
                score=(1.0 - alpha) * r.get("score", 0.0),
                bm25_score=0.0,
                vector_score=r.get("score", 0.0),
                vector_rank=rank,
                source="vector",
                appears_in=["vector"],
            )

    results = list(combined.values())
    results.sort(key=lambda x: -x.score)
    return results


# ============================================================================
# Algorithm 2: Reciprocal Rank Fusion (RRF)
# ============================================================================


def _reciprocal_rank_fusion(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig,
) -> list[RerankedResult]:
    """RRF: score = sum(1 / (k + rank_i)) для каждого списка.

    Преимущества:
    - Не требует нормализации scores
    - Устойчив к разным метрикам (BM25 vs cosine similarity)
    - Стандартный алгоритм в IR (используется в Elasticsearch, Bing)

    Reference: Cormack, Clarke, Buettcher (2009) "Reciprocal Rank Fusion
    outperforms Condorcet and individual Rank Learning Methods".
    """
    k = config.rrf_k
    if k <= 0:
        raise ValueError(f"rrf_k must be > 0, got {k}")

    combined: dict[str, RerankedResult] = {}

    # BM25 contributes 1 / (k + rank)
    for rank, r in enumerate(bm25_results, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        contribution = 1.0 / (k + rank)
        combined[doc_id] = RerankedResult(
            doc=r,
            score=contribution,
            bm25_score=r.get("score", 0.0),
            vector_score=0.0,
            bm25_rank=rank,
            source="bm25",
            appears_in=["bm25"],
        )

    # Vector contributes 1 / (k + rank)
    for rank, r in enumerate(vector_results, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        contribution = 1.0 / (k + rank)
        if doc_id in combined:
            existing = combined[doc_id]
            existing.vector_score = r.get("score", 0.0)
            existing.vector_rank = rank
            existing.score += contribution
            existing.appears_in.append("vector")
            existing.source = "hybrid"
        else:
            combined[doc_id] = RerankedResult(
                doc=r,
                score=contribution,
                bm25_score=0.0,
                vector_score=r.get("score", 0.0),
                vector_rank=rank,
                source="vector",
                appears_in=["vector"],
            )

    results = list(combined.values())
    results.sort(key=lambda x: -x.score)
    return results


# ============================================================================
# Algorithm 3: Maximal Marginal Relevance (MMR)
# ============================================================================


def _maximal_marginal_relevance(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig,
) -> list[RerankedResult]:
    """MMR: diversity-aware reranking.

    На каждой итерации выбираем документ с максимальным:
        score = lambda * relevance(doc) - (1-lambda) * max(similarity(doc, selected))

    Где relevance — это RRF score (комбинированный).
    similarity — Jaccard на словах name+description (или custom similarity_func).

    Reference: Carbonell, Goldstein (1998) "The Use of MMR, Diversity-Based
    Reranking for Reordering Documents and Producing Summaries".
    """
    lambda_val = config.mmr_lambda
    if not 0.0 <= lambda_val <= 1.0:
        raise ValueError(f"mmr_lambda must be in [0, 1], got {lambda_val}")

    similarity_func = config.similarity_func or _jaccard_similarity

    # Сначала вычисляем relevance через RRF
    rrf_results = _reciprocal_rank_fusion(bm25_results, vector_results, config)

    if not rrf_results:
        return []

    selected: list[RerankedResult] = []
    remaining = list(rrf_results)

    # Первый документ — самый релевантный (нет diversity penalty)
    selected.append(remaining.pop(0))

    # Итеративно выбираем следующие
    while remaining and len(selected) < config.limit * 2:  # buffer
        best_idx = 0
        best_score = -math.inf

        for i, candidate in enumerate(remaining):
            # Relevance component (RRF score, normalized)
            relevance = candidate.score

            # Diversity component: max similarity to already selected
            max_sim = 0.0
            for sel in selected:
                sim = similarity_func(candidate.doc, sel.doc)
                if sim > max_sim:
                    max_sim = sim

            mmr_score = lambda_val * relevance - (1.0 - lambda_val) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        # Создаем новый результат с MMR score
        chosen = remaining.pop(best_idx)
        chosen.score = best_score   # overwrite with MMR score
        selected.append(chosen)

    return selected


# ============================================================================
# Algorithm 4: CombSUM
# ============================================================================


def _combsum(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig,
) -> list[RerankedResult]:
    """CombSUM: score = sum of normalized scores from each list.

    Reference: Fox, Shaw (1994) "Combination of Multiple Searches".
    """
    bm25_norm = _normalize_scores(bm25_results)
    vector_norm = _normalize_scores(vector_results)

    combined: dict[str, RerankedResult] = {}

    for rank, r in enumerate(bm25_norm, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        combined[doc_id] = RerankedResult(
            doc=r,
            score=r.get("score", 0.0),
            bm25_score=r.get("score", 0.0),
            vector_score=0.0,
            bm25_rank=rank,
            source="bm25",
            appears_in=["bm25"],
        )

    for rank, r in enumerate(vector_norm, 1):
        doc_id = r.get(config.doc_id_field, "")
        if not doc_id:
            continue
        if doc_id in combined:
            existing = combined[doc_id]
            existing.vector_score = r.get("score", 0.0)
            existing.score += r.get("score", 0.0)
            existing.vector_rank = rank
            existing.appears_in.append("vector")
            existing.source = "hybrid"
        else:
            combined[doc_id] = RerankedResult(
                doc=r,
                score=r.get("score", 0.0),
                bm25_score=0.0,
                vector_score=r.get("score", 0.0),
                vector_rank=rank,
                source="vector",
                appears_in=["vector"],
            )

    results = list(combined.values())
    results.sort(key=lambda x: -x.score)
    return results


# ============================================================================
# Algorithm 5: CombMNZ
# ============================================================================


def _combmnz(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    config: RerankingConfig,
) -> list[RerankedResult]:
    """CombMNZ: score = CombSUM * count_of_lists_where_doc_appears.

    Документы, появляющиеся в обоих списках, получают bonus (×2).
    Reference: Fox, Shaw (1994).
    """
    # Сначала CombSUM
    combsum_results = _combsum(bm25_results, vector_results, config)

    # Умножаем на количество списков, где документ появился
    for r in combsum_results:
        r.score *= len(r.appears_in)

    combsum_results.sort(key=lambda x: -x.score)
    return combsum_results


# ============================================================================
# Helpers
# ============================================================================


def _normalize_scores(
    results: list[dict[str, Any]],
    score_key: str = "score",
) -> list[dict[str, Any]]:
    """Min-max normalization scores в [0, 1]."""
    if not results:
        return results

    scores = [r.get(score_key, 0.0) for r in results]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0

    if max_score == min_score:
        return results   # avoid division by zero

    normalized = []
    for r in results:
        r_copy = dict(r)
        original = r.get(score_key, 0.0)
        r_copy[score_key] = (original - min_score) / (max_score - min_score)
        normalized.append(r_copy)

    return normalized


def _jaccard_similarity(doc1: dict[str, Any], doc2: dict[str, Any]) -> float:
    """Jaccard similarity между двумя документами [0, 1].

    Использует words из name_ru + name_en + description.
    """
    # Извлекаем слова из обоих документов
    text1 = " ".join([
        str(doc1.get("name_ru", "")),
        str(doc1.get("name_en", "")),
        str(doc1.get("description", "")),
    ]).lower()
    text2 = " ".join([
        str(doc2.get("name_ru", "")),
        str(doc2.get("name_en", "")),
        str(doc2.get("description", "")),
    ]).lower()

    words1 = set(text1.split())
    words2 = set(text2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для hybrid reranker (демо)."""
    import argparse

    parser = argparse.ArgumentParser(description="Hybrid reranker demo")
    parser.add_argument(
        "--algorithm",
        choices=[a.value for a in RerankingAlgorithm],
        default=RerankingAlgorithm.RRF.value,
    )
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--mmr-lambda", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    # Demo data
    bm25_results = [
        {"name_en": "Find", "name_ru": "Найти", "description": "Найти элемент", "score": 5.0},
        {"name_en": "FindByCode", "name_ru": "НайтиПоКоду", "description": "По коду", "score": 4.0},
        {"name_en": "FindByName", "name_ru": "НайтиПоНаименованию", "description": "По имени", "score": 3.0},
    ]
    vector_results = [
        {"name_en": "FindByCode", "name_ru": "НайтиПоКоду", "description": "По коду", "score": 0.9},
        {"name_en": "Search", "name_ru": "Поиск", "description": "Поиск элементов", "score": 0.8},
        {"name_en": "Find", "name_ru": "Найти", "description": "Найти элемент", "score": 0.7},
    ]

    config = RerankingConfig(
        algorithm=RerankingAlgorithm(args.algorithm),
        alpha=args.alpha,
        mmr_lambda=args.mmr_lambda,
        limit=args.limit,
    )

    results = rerank(bm25_results, vector_results, config)

    print(f"\nAlgorithm: {args.algorithm}")
    print(f"{'Rank':<5} {'Score':<10} {'Source':<10} {'Doc ID':<20} {'Appears In'}")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        print(f"{i:<5} {r.score:<10.4f} {r.source:<10} "
              f"{r.doc.get('name_en', ''):<20} {','.join(r.appears_in)}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
