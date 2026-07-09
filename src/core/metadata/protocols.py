"""
src/core/metadata/protocols.py — Protocol-контракты для metadata слоя.

Phase 2 of refactoring: явные interface через typing.Protocol.
Позволяет тестировать слои изолированно и менять реализацию.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class MetadataParser(Protocol):
    """Контракт: парсер метаданных 1С из XML."""

    def parse(self, xml_path: Path) -> dict[str, Any] | None:
        """Распарсить XML файл метаданных.

        Args:
            xml_path: Путь к XML файлу

        Returns:
            dict с метаданными или None при ошибке.
        """
        ...


class MetadataExtractorProtocol(Protocol):
    """Контракт: экстрактор всех метаданных конфигурации."""

    def extract_all(
        self, config_dir: Path | str, progress_callback: Any = None
    ) -> dict[str, Any]:
        """Извлечь все метаданные из директории конфигурации.

        Args:
            config_dir: Путь к распакованной конфигурации
            progress_callback: Опциональный callback для прогресса

        Returns:
            dict со всеми объектами метаданных.
        """
        ...


class TypeResolver(Protocol):
    """Контракт: ресолвер типов полей 1С."""

    def resolve(self, type_strings: list[str]) -> Any:
        """Разрешить список строк типов в структурированный тип.

        Args:
            type_strings: Список типов (например, ['cfg:CatalogRef.Номенклатура'])

        Returns:
            ResolvedType с распознанной структурой.
        """
        ...
