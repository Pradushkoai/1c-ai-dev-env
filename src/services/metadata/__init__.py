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

Использование:
    from src.services.metadata import MetadataExtractor, extract_and_save
    from src.services.metadata.extractor import MetadataExtractor  # backward compat
"""

from __future__ import annotations

# D2.1: Re-export для backward compat
from .config_parser import ConfigParser
from .event_subscription_parser import EventSubscriptionParser
from .extractor import MetadataExtractor, extract_and_save
from .role_parser import RoleParser
from .scheduled_job_parser import ScheduledJobParser
from .subsystem_parser import SubsystemParser
from .universal_parser import UniversalObjectParser
from .utils import XMLUtils

__all__ = [
    "ConfigParser",
    "EventSubscriptionParser",
    "MetadataExtractor",
    "RoleParser",
    "ScheduledJobParser",
    "SubsystemParser",
    "UniversalObjectParser",
    "XMLUtils",
    "extract_and_save",
]
