from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class ConfigParser:
    """Парсер Configuration.xml и ConfigDumpInfo.xml."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse_configuration(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит Configuration.xml — главный файл конфигурации."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        config_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == "Configuration":
                config_elem = child
                break

        if config_elem is None:
            return None

        properties = XMLUtils.get_child(config_elem, "Properties")
        child_objects = XMLUtils.get_child(config_elem, "ChildObjects")

        result = {
            "type": "Configuration",
            "uuid": config_elem.get("uuid", ""),
            "properties": {},
            "child_objects": {
                "subsystems": [],
                "common_modules": [],
                "common_forms": [],
                "common_commands": [],
                "common_templates": [],
                "common_pictures": [],
                "common_attributes": [],
                "catalogs": [],
                "documents": [],
                "information_registers": [],
                "accumulation_registers": [],
                "data_processors": [],
                "reports": [],
                "enums": [],
                "roles": [],
                "event_subscriptions": [],
                "scheduled_jobs": [],
                "defined_types": [],
                "functional_options": [],
                "exchange_plans": [],
                "web_services": [],
                "http_services": [],
                "xdto_packages": [],
                "session_parameters": [],
                "command_groups": [],
                "document_journals": [],
                "filter_criteria": [],
                "languages": [],
                "other": [],
            },
        }

        # Properties
        if properties is not None:
            for child in properties:
                tag = XMLUtils.strip_ns(child.tag)
                if tag == "Synonym":
                    result["properties"]["Synonym"] = XMLUtils.get_synonym(properties)
                elif child.text and child.text.strip():
                    result["properties"][tag] = child.text.strip()

        # ChildObjects — список всех объектов конфигурации
        if child_objects is not None:
            for child in child_objects:
                tag = XMLUtils.strip_ns(child.tag)
                name = child.text or ""
                uuid = child.get("uuid", "")

                entry = {"name": name, "uuid": uuid, "type": tag}

                # Маппинг тегов к спискам
                tag_lower = tag.lower()
                if tag == "Subsystem":
                    result["child_objects"]["subsystems"].append(entry)
                elif tag == "CommonModule":
                    result["child_objects"]["common_modules"].append(entry)
                elif tag == "CommonForm":
                    result["child_objects"]["common_forms"].append(entry)
                elif tag == "CommonCommand":
                    result["child_objects"]["common_commands"].append(entry)
                elif tag == "CommonTemplate":
                    result["child_objects"]["common_templates"].append(entry)
                elif tag == "CommonPicture":
                    result["child_objects"]["common_pictures"].append(entry)
                elif tag == "CommonAttribute":
                    result["child_objects"]["common_attributes"].append(entry)
                elif tag == "Catalog":
                    result["child_objects"]["catalogs"].append(entry)
                elif tag == "Document":
                    result["child_objects"]["documents"].append(entry)
                elif tag == "InformationRegister":
                    result["child_objects"]["information_registers"].append(entry)
                elif tag == "AccumulationRegister":
                    result["child_objects"]["accumulation_registers"].append(entry)
                elif tag == "DataProcessor":
                    result["child_objects"]["data_processors"].append(entry)
                elif tag == "Report":
                    result["child_objects"]["reports"].append(entry)
                elif tag == "Enum":
                    result["child_objects"]["enums"].append(entry)
                elif tag == "Role":
                    result["child_objects"]["roles"].append(entry)
                elif tag == "EventSubscription":
                    result["child_objects"]["event_subscriptions"].append(entry)
                elif tag == "ScheduledJob":
                    result["child_objects"]["scheduled_jobs"].append(entry)
                elif tag == "DefinedType":
                    result["child_objects"]["defined_types"].append(entry)
                elif tag == "FunctionalOption":
                    result["child_objects"]["functional_options"].append(entry)
                elif tag == "ExchangePlan":
                    result["child_objects"]["exchange_plans"].append(entry)
                elif tag == "WebService":
                    result["child_objects"]["web_services"].append(entry)
                elif tag == "HTTPService":
                    result["child_objects"]["http_services"].append(entry)
                elif tag == "XDTOPackage":
                    result["child_objects"]["xdto_packages"].append(entry)
                elif tag == "SessionParameter":
                    result["child_objects"]["session_parameters"].append(entry)
                elif tag == "CommandGroup":
                    result["child_objects"]["command_groups"].append(entry)
                elif tag == "DocumentJournal":
                    result["child_objects"]["document_journals"].append(entry)
                elif tag == "FilterCriterion":
                    result["child_objects"]["filter_criteria"].append(entry)
                elif tag == "Language":
                    result["child_objects"]["languages"].append(entry)
                else:
                    result["child_objects"]["other"].append(entry)

        return result

    def parse_config_dump_info(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит ConfigDumpInfo.xml — дамп версий объектов."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        versions = []
        config_versions = XMLUtils.get_child(root, "ConfigVersions")
        if config_versions is not None:
            for meta in config_versions:
                if XMLUtils.strip_ns(meta.tag) == "Metadata":
                    name = meta.get("name", "")
                    obj_id = meta.get("id", "")
                    config_version = meta.get("configVersion", "")
                    versions.append(
                        {
                            "name": name,
                            "id": obj_id,
                            "config_version": config_version,
                        }
                    )

        return {
            "type": "ConfigDumpInfo",
            "total_objects": len(versions),
            "versions": versions,
        }


# ============================================================================
# ПАРСЕР ROLES (права доступа)
# ============================================================================


