"""
Пакет metadata — парсинг метаданных 1С.

D2.1 (2026-07-05): декомпозиция extractor.py (1101 LOC) на 7 файлов:
  - utils.py — XMLUtils (общие утилиты)
  - universal_parser.py — UniversalObjectParser (35+ типов объектов)
  - config_parser.py — ConfigParser (Configuration.xml)
  - role_parser.py — RoleParser (роли 1С)
  - subsystem_parser.py — SubsystemParser (подсистемы)
  - event_subscription_parser.py — EventSubscriptionParser
  - scheduled_job_parser.py — ScheduledJobParser
  - extractor.py — MetadataExtractor (оркестратор) + extract_and_save()

P1.5 (2026-07-06): добавлены модули для статического валидатора запросов:
  - standard_attributes.py — платформенные стандартные реквизиты (Ссылка, Период, Регистратор, ...)
  - type_resolver.py — ресолвинг типов полей (CatalogRef.X → структура)

Использование:
    from src.services.metadata import MetadataExtractor, extract_and_save
    from src.services.metadata.extractor import MetadataExtractor  # backward compat
    from src.services.metadata.standard_attributes import get_standard_attributes, get_virtual_tables
    from src.services.metadata.type_resolver import resolve_types, parse_type_string
"""

from __future__ import annotations

# D2.1: Re-export для backward compat
from .config_parser import ConfigParser
from .event_subscription_parser import EventSubscriptionParser
from .extractor import MetadataExtractor, extract_and_save
from .role_parser import RoleParser
from .scheduled_job_parser import ScheduledJobParser
# P1.5: стандартные реквизиты и ресолвинг типов
from .standard_attributes import (
    VIRTUAL_TABLES,
    STANDARD_ATTRIBUTES,
    get_standard_attributes,
    get_standard_tabular_sections,
    get_virtual_tables,
    is_virtual_table_name,
)
from .subsystem_parser import SubsystemParser
# P1.5: type resolver
from .type_resolver import (
    ResolvedType,
    parse_type_string,
    resolve_defined_type,
    resolve_field_types_from_metadata,
    resolve_types,
)
from .universal_parser import UniversalObjectParser
from .utils import XMLUtils

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
