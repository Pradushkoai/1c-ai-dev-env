"""
search_hybrid.py — Гибридный поиск: BM25 + векторный.

P1.1: комбинирует keyword search (BM25) и semantic search (vector)
для лучшего качества на нетиповых конфигурациях 1С.

Преимущества гибридного поиска:
- BM25 хорош для точного совпадения ключевых слов (имена методов, термины)
- Vector search хорош для семантического смысла (синонимы, перефразировки)
- Комбинация даёт лучшее из обоих миров

Алгоритм:
1. BM25 search → top-N результатов с scores [0..1]
2. Vector search → top-N результатов с scores [0..1]
3. Объединение: для каждого метода score = α * bm25_score + (1-α) * vector_score
4. Сортировка по убыванию combined score
5. Top-limit результатов

Использование:
    from src.services.search_hybrid import search_hybrid

    results = search_hybrid(
        index_path=Path("fast-search-index.json"),
        query="найти элемент по коду",
        limit=10,
        alpha=0.5,  # вес BM25, 0.5 = баланс
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .search_bm25 import search_bm25
from .search_vector import VectorSearch

logger = logging.getLogger(__name__)


def _normalize_scores(results: list[dict], score_key: str = "score") -> list[dict]:
    """Нормализовать scores в [0, 1] (min-max normalization).

    Args:
        results: Список результатов с полем score.
        score_key: Ключ поля score.

    Returns:
        Результаты с нормализованными scores.
    """
    if not results:
        return results

    scores = [r.get(score_key, 0.0) for r in results]
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0

    # Если все scores одинаковые — возвращаем как есть (avoid division by zero)
    if max_score == min_score:
        return results

    normalized = []
    for r in results:
        r_copy = dict(r)
        original = r.get(score_key, 0.0)
        r_copy[score_key] = (original - min_score) / (max_score - min_score)
        normalized.append(r_copy)

    return normalized


def search_hybrid(
    index_path: Path,
    query: str,
    limit: int = 10,
    alpha: float = 0.5,
    vector_search: VectorSearch | None = None,
) -> list[dict]:
    """Гибридный поиск: BM25 + векторный.

    Комбинирует keyword search (BM25) и semantic search (vector).
    Если векторный поиск недоступен — fallback на чистый BM25.

    Args:
        index_path: Путь к BM25 индексу (fast-search-index.json).
        query: Поисковый запрос.
        limit: Максимум результатов.
        alpha: Вес BM25 в гибридной оценке (0.0 — только vector,
            1.0 — только BM25, 0.5 — баланс). Default: 0.5.
        vector_search: Опциональный VectorSearch instance (для переиспользования).
            Если None — создаётся новый.

    Returns:
        Список: [{score, name_ru, name_en, syntax, description, context, source}, ...]
        Отсортирован по убыванию combined score.
        Поле 'source' указывает источник: 'bm25', 'vector', 'hybrid'.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")

    # 1. BM25 search (всегда доступен)
    bm25_results = search_bm25(index_path, query, limit=limit * 2, hybrid=True)
    bm25_results = _normalize_scores(bm25_results)

    # 2. Vector search (опционально)
    vs = vector_search or VectorSearch()
    vector_results: list[dict] = []
    if vs.is_available():
        try:
            vector_results = vs.search(query, limit=limit * 2, score_threshold=0.0)
            vector_results = _normalize_scores(vector_results)
        except Exception as e:
            logger.warning("Vector search failed, fallback to BM25 only: %s", e)
            vector_results = []
    else:
        logger.debug("Vector search unavailable, using BM25 only")

    # 3. Если vector недоступен — вернуть BM25 результаты
    if not vector_results:
        bm25_only: list[dict] = []
        for r in bm25_results[:limit]:
            r_copy = dict(r)
            r_copy["source"] = "bm25"
            bm25_only.append(r_copy)
        return bm25_only

    # 4. Объединение: combined score = alpha * bm25 + (1-alpha) * vector
    # Используем name_en как ключ для объединения (уникальный идентификатор метода)
    combined: dict[str, dict[str, Any]] = {}

    for r in bm25_results:
        key = r.get("name_en", "") or r.get("name_ru", "")
        if key:
            combined[key] = {
                "bm25_score": r.get("score", 0.0),
                "vector_score": 0.0,
                "data": r,
            }

    for r in vector_results:
        key = r.get("name_en", "") or r.get("name_ru", "")
        if not key:
            continue
        if key in combined:
            combined[key]["vector_score"] = r.get("score", 0.0)
            # Обновляем data если vector имеет более полное описание
            if r.get("description") and not combined[key]["data"].get("description"):
                combined[key]["data"]["description"] = r["description"]
        else:
            combined[key] = {
                "bm25_score": 0.0,
                "vector_score": r.get("score", 0.0),
                "data": r,
            }

    # 5. Вычисление combined score
    results: list[dict] = []
    for _key, info in combined.items():
        bm25_s = info["bm25_score"]
        vector_s = info["vector_score"]
        combined_score = alpha * bm25_s + (1.0 - alpha) * vector_s

        result = dict(info["data"])
        result["score"] = combined_score
        result["bm25_score"] = bm25_s
        result["vector_score"] = vector_s

        # Определяем источник
        if bm25_s > 0 and vector_s > 0:
            result["source"] = "hybrid"
        elif bm25_s > 0:
            result["source"] = "bm25"
        else:
            result["source"] = "vector"

        results.append(result)

    # 6. Сортировка по combined score
    results.sort(key=lambda x: -x["score"])

    return results[:limit]


def search_hybrid_auto(
    index_path: Path,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Авто-выбор: гибридный если vector доступен, иначе BM25.

    Удобная обёртка для MCP tools и CLI — автоматически использует
    лучший доступный алгоритм поиска.

    Args:
        index_path: Путь к индексу.
        query: Поисковый запрос.
        limit: Максимум результатов.

    Returns:
        Список результатов (формат как в search_hybrid).
    """
    vs = VectorSearch()
    if vs.is_available():
        return search_hybrid(index_path, query, limit, alpha=0.5, vector_search=vs)
    else:
        # Fallback на чистый BM25
        from .search_bm25 import search_auto

        results = search_auto(index_path, query, limit)
        # Добавляем source='bm25' для консистентности
        for r in results:
            r.setdefault("source", "bm25")
        return results
