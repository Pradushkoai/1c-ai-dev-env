"""
src/core/metadata/ — Парсинг XML метаданных 1С.

Phase 2 of refactoring: core layer for metadata parsing.

Backward compat: этот модуль реэкспортирует из src.services.metadata.
Исходный код остаётся в src/services/metadata/ до полной миграции.
"""

from __future__ import annotations

# Re-export из src.services.metadata для нового пути импорта
from src.services.metadata import (
    ConfigParser,
    EventSubscriptionParser,
    MetadataExtractor,
    ResolvedType,
    RoleParser,
    STANDARD_ATTRIBUTES,
    ScheduledJobParser,
    SubsystemParser,
    VIRTUAL_TABLES,
    UniversalObjectParser,
    XMLUtils,
    extract_and_save,
    get_standard_attributes,
    get_standard_tabular_sections,
    get_virtual_tables,
    is_virtual_table_name,
    parse_type_string,
    resolve_defined_type,
    resolve_field_types_from_metadata,
    resolve_types,
)

__all__ = [
    "ConfigParser",
    "EventSubscriptionParser",
    "MetadataExtractor",
    "ResolvedType",
    "RoleParser",
    "STANDARD_ATTRIBUTES",
    "ScheduledJobParser",
    "SubsystemParser",
    "VIRTUAL_TABLES",
    "UniversalObjectParser",
    "XMLUtils",
    "extract_and_save",
    "get_standard_attributes",
    "get_standard_tabular_sections",
    "get_virtual_tables",
    "is_virtual_table_name",
    "parse_type_string",
    "resolve_defined_type",
    "resolve_field_types_from_metadata",
    "resolve_types",
]
