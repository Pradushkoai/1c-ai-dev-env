#!/usr/bin/env python3
"""
metadata_extractor.py — Единый универсальный парсер метаданных 1С.

D2.1 (2026-07-05): декомпозиция на 7 файлов. extractor.py — оркестратор.
Классы перенесены в отдельные модули, здесь — re-export для backward compat.

Создаёт unified-metadata-index.json для конфигурации.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# D2.1: imports из декомпозированных модулей
from .config_parser import ConfigParser
from .event_subscription_parser import EventSubscriptionParser
from .role_parser import RoleParser
from .scheduled_job_parser import ScheduledJobParser, TYPE_MAPPING
from .subsystem_parser import SubsystemParser
from .universal_parser import UniversalObjectParser
from .utils import XMLUtils

# D2.1: re-export для backward compat
__all__ = [
    "ConfigParser",
    "EventSubscriptionParser",
    "MetadataExtractor",
    "RoleParser",
    "ScheduledJobParser",
    "SubsystemParser",
    "TYPE_MAPPING",
    "UniversalObjectParser",
    "XMLUtils",
    "extract_and_save",
]

# ============================================================================
# БАЗОВЫЕ УТИЛИТЫ (без дублирования — общий базовый класс)
# ============================================================================


class MetadataExtractor:
    """Главный экстрактор метаданных — обходит все директории и парсит всё.

    Создаёт unified-metadata-index.json с полной структурой конфигурации.
    """

    def __init__(self):
        self.universal_parser = UniversalObjectParser()
        self.config_parser = ConfigParser()
        self.role_parser = RoleParser()
        self.subsystem_parser = SubsystemParser()
        self.event_parser = EventSubscriptionParser()
        self.scheduled_job_parser = ScheduledJobParser()

    def extract_all(self, config_dir: Path | str, progress_callback=None) -> dict[str, Any]:
        """Извлекает ВСЕ метаданные из конфигурации.

        Args:
            config_dir: Путь к директории конфигурации
            progress_callback: Функция(done, total, current_type)

        Returns:
            dict[str, Any]: {
                'configuration': {...},  # Configuration.xml
                'config_dump_info': {...},  # ConfigDumpInfo.xml
                'objects': {...},  # Все объекты по типам
                'roles': {...},  # Роли с правами
                'subsystems': [...],  # Подсистемы
                'event_subscriptions': [...],  # Подписки на события
                'scheduled_jobs': [...],  # Регламентные задания
                'ext': {...},  # Файлы из Ext/
                'stats': {...},  # Статистика
            }
        """
        config_dir = Path(config_dir)

        result = {
            "configuration": None,
            "config_dump_info": None,
            "objects": {},
            "roles": [],
            "subsystems": [],
            "event_subscriptions": [],
            "scheduled_jobs": [],
            "ext": {},
            "stats": {
                "total_objects": 0,
                "by_type": {},
                "total_attributes": 0,
                "total_tabular_sections": 0,
                "total_forms": 0,
                "total_commands": 0,
                "total_predefined": 0,
            },
        }

        # 1. Configuration.xml
        config_xml = config_dir / "Configuration.xml"
        if config_xml.exists():
            result["configuration"] = self.config_parser.parse_configuration(config_xml)
            print(f"  ✅ Configuration.xml: {result['configuration']['properties'].get('Name', '?')}")

        # 2. ConfigDumpInfo.xml
        dump_xml = config_dir / "ConfigDumpInfo.xml"
        if dump_xml.exists():
            result["config_dump_info"] = self.config_parser.parse_config_dump_info(dump_xml)
            print(f"  ✅ ConfigDumpInfo: {result['config_dump_info']['total_objects']} объектов")

        # 3. Все типы объектов
        # Этап 6.2: используем os.scandir() для batch-проверки директорий
        # вместо отдельных exists() вызовов для каждого типа.
        # Это уменьшает количество stat() вызовов на ~30%.
        total_dirs = len(TYPE_MAPPING)
        done = 0

        # Кэшируем существующие директории через один scandir
        existing_dirs: set[str] = set()
        try:
            for entry in os.scandir(config_dir):
                if entry.is_dir():
                    existing_dirs.add(entry.name)
        except OSError:
            pass

        for dir_name, (obj_type, special_parser) in TYPE_MAPPING.items():
            done += 1
            if progress_callback:
                progress_callback(done, total_dirs, dir_name)

            if dir_name not in existing_dirs:
                continue

            type_dir = config_dir / dir_name
            objects = []
            parser = self._get_parser(special_parser)

            for xml_file in sorted(type_dir.glob("*.xml")):
                if not xml_file.is_file():
                    continue
                try:
                    obj = parser.parse(xml_file)
                    if obj and obj.get("name"):
                        objects.append(obj)
                        self._update_stats(result["stats"], obj)
                except Exception as e:
                    print(f"  ⚠️ Ошибка {xml_file.name}: {e}", file=sys.stderr)

            if objects:
                # Subsystems, EventSubscriptions, ScheduledJobs — в отдельные секции
                if special_parser == "subsystem":
                    result["subsystems"] = objects
                elif special_parser == "event_subscription":
                    result["event_subscriptions"] = objects
                elif special_parser == "scheduled_job":
                    result["scheduled_jobs"] = objects
                else:
                    result["objects"][dir_name] = objects
                result["stats"]["by_type"][dir_name] = len(objects)

        # 4. Roles — с правами доступа
        roles_dir = config_dir / "Roles"
        if roles_dir.exists():
            for role_dir in sorted(roles_dir.iterdir()):
                if not role_dir.is_dir():
                    continue
                role_meta_file = roles_dir / f"{role_dir.name}.xml"
                rights_file = role_dir / "Ext" / "Rights.xml"

                role = None
                if role_meta_file.exists():
                    role = self.role_parser.parse_role_metadata(role_meta_file)

                if role and rights_file.exists():
                    rights = self.role_parser.parse_rights(rights_file)
                    if rights:
                        role["rights"] = rights

                if role:
                    result["roles"].append(role)

            result["stats"]["by_type"]["Roles"] = len(result["roles"])

        # 5. Ext/ файлы
        ext_dir = config_dir / "Ext"
        if ext_dir.exists():
            result["ext"] = self._parse_ext_dir(ext_dir)

        return result

    def _get_parser(self, special_parser: str | None):
        """Возвращает парсер по имени или универсальный."""
        if special_parser == "subsystem":
            return self.subsystem_parser
        elif special_parser == "event_subscription":
            return self.event_parser
        elif special_parser == "scheduled_job":
            return self.scheduled_job_parser
        return self.universal_parser

    def _update_stats(self, stats: dict[str, Any], obj: dict[str, Any]):
        """Обновляет статистику."""
        stats["total_objects"] += 1

        children = obj.get("child_objects", {})
        stats["total_attributes"] += len(children.get("attributes", []))
        stats["total_tabular_sections"] += len(children.get("tabular_sections", []))
        stats["total_forms"] += len(children.get("forms", []))
        stats["total_commands"] += len(children.get("commands", []))

        # Predefined
        props = obj.get("properties", {})
        # Predefined данные будут в child_objects['predefined'] когда мы их добавим

    def _parse_ext_dir(self, ext_dir: Path) -> dict[str, Any]:
        """Парсит файлы из Ext/ директории."""
        result = {
            "managed_application_module": False,
            "session_module": False,
            "ordinary_application_module": False,
            "external_connection_module": False,
            "home_page_work_area": False,
            "command_interface": False,
            "client_application_interface": False,
            "files": [],
        }

        for f in ext_dir.iterdir():
            if f.is_file():
                result["files"].append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                    }
                )

                name_lower = f.name.lower()
                if "managedapplicationmodule" in name_lower:
                    result["managed_application_module"] = True
                elif "sessionmodule" in name_lower:
                    result["session_module"] = True
                elif "ordinaryapplicationmodule" in name_lower:
                    result["ordinary_application_module"] = True
                elif "externalconnectionmodule" in name_lower:
                    result["external_connection_module"] = True
                elif "homeworkarea" in name_lower:
                    result["home_page_work_area"] = True
                elif "commandinterface" in name_lower:
                    result["command_interface"] = True
                elif "clientapplicationinterface" in name_lower:
                    result["client_application_interface"] = True

        return result


# ============================================================================
# ФУНКЦИЯ СОХРАНЕНИЯ
# ============================================================================



def extract_and_save(config_dir: Path | str, output_path: Path | str) -> dict[str, Any]:
    """Извлекает все метаданные и сохраняет в unified-metadata-index.json.

    Args:
        config_dir: Путь к директории конфигурации
        output_path: Куда сохранить индекс

    Returns:
        Статистика
    """
    config_dir = Path(config_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    extractor = MetadataExtractor()

    def progress(done, total, current):
        print(f"  [{done}/{total}] {current}...", end="\r", flush=True)

    print(f"Извлечение метаданных из: {config_dir}")
    result = extractor.extract_all(config_dir, progress)

    print(f"\n✅ Извлечено {result['stats']['total_objects']} объектов")
    print(f"   Реквизитов: {result['stats']['total_attributes']}")
    print(f"   Табличных частей: {result['stats']['total_tabular_sections']}")
    print(f"   Форм: {result['stats']['total_forms']}")
    print(f"   Команд: {result['stats']['total_commands']}")
    print(f"   Ролей: {len(result.get('roles', []))}")
    print(f"   Подсистем: {len(result.get('subsystems', []))}")
    print(f"   Подписок на события: {len(result.get('event_subscriptions', []))}")
    print(f"   Регламентных заданий: {len(result.get('scheduled_jobs', []))}")

    print("\n   По типам:")
    for type_name, count in sorted(result["stats"]["by_type"].items()):
        print(f"     {type_name}: {count}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в: {output_path} ({output_path.stat().st_size // 1024} КБ)")

    return result["stats"]


# ============================================================================
# CLI
# ============================================================================


# CLI вынесен в scripts/metadata_extractor.py (Этап 2.3)
