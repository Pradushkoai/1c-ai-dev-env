"""
src/adapters/protocols.py — Protocol-контракты для adapter слоя.

Адаптеры изолируют внешние зависимости (BSL LS Java, tree-sitter, v8unpack).
Каждый адаптер реализует Protocol, что позволяет core работать без знания
о конкретной реализации.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class BslLsAdapter(Protocol):
    """Контракт: адаптер BSL Language Server (Java).

    Реализации: BslAnalyzer (обёртка над BSL LS через subprocess).
    """

    def analyze(self, file_path: Path | str) -> Any:
        """Запустить BSL LS анализ файла.

        Args:
            file_path: Путь к .bsl файлу

        Returns:
            Результат анализа (диагностики).
        """
        ...


class V8UnpackAdapter(Protocol):
    """Контракт: адаптер v8unpack для распаковки .cf/.cfe файлов.

    Реализации: CFExtractor (через v8unpack или собственный парсер).
    """

    def extract(self, container_path: Path, output_dir: Path) -> bool:
        """Распаковать контейнер 1С (.cf/.cfe) в директорию.

        Args:
            container_path: Путь к .cf/.cfe файлу
            output_dir: Куда распаковывать

        Returns:
            True если успешно, False иначе.
        """
        ...


class TreeSitterAdapter(Protocol):
    """Контракт: адаптер tree-sitter-bsl для AST парсинга.

    Реализации: BslTreeSitterParser.
    """

    def parse(self, code: str) -> list[Any]:
        """Распарсить BSL код в AST.

        Args:
            code: BSL исходный код

        Returns:
            Список символов (процедур/функций).
        """
        ...
