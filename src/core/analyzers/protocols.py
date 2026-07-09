"""
src/core/analyzers/protocols.py — Protocol-контракты для analyzer слоя.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class BslAnalyzer(Protocol):
    """Контракт: анализатор BSL кода.

    Реализации: AstAnalyzer, SecurityAuditor, StandardsChecker.
    """

    def analyze(self, file_path: Path | str) -> list[Any]:
        """Проанализировать BSL файл.

        Args:
            file_path: Путь к .bsl файлу

        Returns:
            Список нарушений/проблем.
        """
        ...


class BslParser(Protocol):
    """Контракт: парсер BSL кода.

    Реализации: BslTreeSitterParser (AST), regex-based fallback.
    """

    def parse(self, code: str) -> list[Any]:
        """Распарсить BSL код.

        Args:
            code: BSL исходный код

        Returns:
            Список символов (процедур/функций).
        """
        ...


class QueryValidator(Protocol):
    """Контракт: валидатор запросов 1С.

    Реализации: StaticQueryValidator (offline), LiveQueryValidator (planned).
    """

    def validate(self, query_text: str) -> Any:
        """Валидировать запрос 1С.

        Args:
            query_text: Текст запроса

        Returns:
            ValidationResult с найденными проблемами.
        """
        ...
