from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class ScheduledJobParser:
    """Парсер регламентных заданий."""

    def parse(self, xml_path: Path) -> dict[str, Any] | None:
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        for child in root:
            if XMLUtils.strip_ns(child.tag) == "ScheduledJob":
                properties = XMLUtils.get_child(child, "Properties")
                if properties is None:
                    return None

                return {
                    "type": "ScheduledJob",
                    "name": XMLUtils.get_text(properties, "Name"),
                    "uuid": child.get("uuid", ""),
                    "synonym": XMLUtils.get_synonym(properties),
                    "method_name": XMLUtils.get_text(properties, "MethodName"),
                    "description": XMLUtils.get_text(properties, "Description"),
                    "use": XMLUtils.get_bool(properties, "Use"),
                    "predefined": XMLUtils.get_bool(properties, "Predefined"),
                    "restart_count": XMLUtils.get_int(properties, "RestartCountOnFailure"),
                    "restart_interval": XMLUtils.get_int(properties, "RestartIntervalOnFailure"),
                }
        return None


# ============================================================================
# ГЛАВНЫЙ ЭКСТРАКТОР — оркестратор
# ============================================================================

# Маппинг: директория → (тип объекта, парсер)
# None = используем UniversalObjectParser
TYPE_MAPPING = {
    "Catalogs": ("Catalog", None),
    "Documents": ("Document", None),
    "InformationRegisters": ("InformationRegister", None),
    "AccumulationRegisters": ("AccumulationRegister", None),
    "DataProcessors": ("DataProcessor", None),
    "Reports": ("Report", None),
    "Enums": ("Enum", None),
    "Constants": ("Constant", None),
    "ChartsOfCharacteristicTypes": ("ChartOfCharacteristicTypes", None),
    "ChartsOfAccounts": ("ChartOfAccounts", None),
    "BusinessProcesses": ("BusinessProcess", None),
    "Tasks": ("Task", None),
    "ExchangePlans": ("ExchangePlan", None),
    "FilterCriteria": ("FilterCriterion", None),
    "CommonModules": ("CommonModule", None),
    "CommonForms": ("CommonForm", None),
    "CommonCommands": ("CommonCommand", None),
    "CommonTemplates": ("CommonTemplate", None),
    "CommonPictures": ("CommonPicture", None),
    "CommonAttributes": ("CommonAttribute", None),
    "CommandGroups": ("CommandGroup", None),
    "DefinedTypes": ("DefinedType", None),
    "DocumentJournals": ("DocumentJournal", None),
    "DocumentNumerators": ("DocumentNumerator", None),
    "Sequences": ("Sequence", None),
    "SettingsStorages": ("SettingsStorage", None),
    "FunctionalOptions": ("FunctionalOption", None),
    "FunctionalOptionsParameters": ("FunctionalOptionParameter", None),
    "SessionParameters": ("SessionParameter", None),
    "WebServices": ("WebService", None),
    "HTTPServices": ("HTTPService", None),
    "XDTOPackages": ("XDTOPackage", None),
    "WSReferences": ("WSReference", None),
    "Styles": ("Style", None),
    "StyleItems": ("StyleItem", None),
    "Languages": ("Language", None),
    # Специальные парсеры:
    "Subsystems": ("Subsystem", "subsystem"),
    "EventSubscriptions": ("EventSubscription", "event_subscription"),
    "ScheduledJobs": ("ScheduledJob", "scheduled_job"),
    # Roles обрабатываются отдельно в секции 4 (с правами доступа)
}


