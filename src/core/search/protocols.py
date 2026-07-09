"""
src/core/search/protocols.py — Protocol-контракты для search слоя.
"""

from __future__ import annotations

from typing import Any, Protocol


class Searcher(Protocol):
    """Контракт: поисковик.

    Реализации: BM25Searcher, HybridSearcher, VectorSearch.
    """

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Найти документы по запросу.

        Args:
            query: Поисковый запрос
            limit: Максимум результатов

        Returns:
            Список документов с score и метаданными.
        """
        ...


class Tokenizer(Protocol):
    """Контракт: токенизатор для поискового индекса."""

    def tokenize(self, text: str) -> list[str]:
        """Разбить текст на токены.

        Args:
            text: Входной текст

        Returns:
            Список токенов.
        """
        ...
