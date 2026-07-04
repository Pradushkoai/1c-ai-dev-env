"""
Пакет metadata — парсинг метаданных 1С.

Этап 2.3: metadata_extractor.py перенесён из scripts/ в src/services/metadata/extractor.py.

Поддерживает 35+ типов объектов 1С (Catalog, Document, Enum, etc.) через
универсальный UniversalObjectParser.

Использование:
    from src.services.metadata.extractor import MetadataExtractor, extract_and_save
"""

from __future__ import annotations

from .extractor import MetadataExtractor, extract_and_save

__all__ = ["MetadataExtractor", "extract_and_save"]
