"""
src/core/search/ — Поиск: BM25 + FTS5 + vector.

Phase 2 of refactoring: core layer for search functionality.

Backward compat: реэкспортирует из src.services для нового пути импорта.
"""

from __future__ import annotations

# Re-export поиска из src.services
from src.services.search_bm25 import (
    BM25_B,
    BM25_K1,
    build_index_bm25,
    make_trigrams,
    search_bm25,
    stem,
    tokenize_identifier,
    tokenize_lower,
    tokenize_stemmed,
    trigram_similarity,
)
from src.services.search_code import search_code
from src.services.search_hybrid import search_hybrid, search_hybrid_auto, search_hybrid_reranked

# Опциональные импорты (могут требовать heavy deps)
try:
    from src.services.search_vector import VectorSearch
except ImportError:
    pass

__all__ = [
    "BM25_B",
    "BM25_K1",
    "build_index_bm25",
    "make_trigrams",
    "search_bm25",
    "search_code",
    "search_hybrid",
    "search_hybrid_auto",
    "search_hybrid_reranked",
    "stem",
    "tokenize_identifier",
    "tokenize_lower",
    "tokenize_stemmed",
    "trigram_similarity",
]
