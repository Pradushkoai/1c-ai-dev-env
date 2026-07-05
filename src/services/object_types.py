"""
object_types.py — Единый источник маппинга типов объектов 1С.

P3.17: до фикса TYPE_MAP дублировался в двух местах:
  - src/dsl/_common.py (24 типа)
  - src/services/cfe_manager.py (41 тип)

Это нарушало DRY — при добавлении нового типа нужно было обновлять оба файла,
легко было забыть (что и произошло с опечаткой 'WebServce' в P0.2).

После фикса: единый TYPE_MAP здесь, оба модуля импортируют его.
"""

from __future__ import annotations
from typing import Any

# Полный маппинг типов объектов 1С → XML-теги и папки.
# Источник: формат конфигурации 1С:Предприятие 8.3 (Configuration.xml).
#
# Каждая запись: {xml_tag, dir}
#   xml_tag — XML-тег объекта в Configuration.xml
#   dir — имя директории в распакованной конфигурации
TYPE_MAP: dict[str, dict] = {
    # ─── Основные объекты метаданных ───
    "Catalog": {"xml_tag": "Catalog", "dir": "Catalogs"},
    "Document": {"xml_tag": "Document", "dir": "Documents"},
    "Enum": {"xml_tag": "Enum", "dir": "Enums"},
    "Constant": {"xml_tag": "Constant", "dir": "Constants"},
    "InformationRegister": {"xml_tag": "InformationRegister", "dir": "InformationRegisters"},
    "AccumulationRegister": {"xml_tag": "AccumulationRegister", "dir": "AccumulationRegisters"},
    "AccountingRegister": {"xml_tag": "AccountingRegister", "dir": "AccountingRegisters"},
    "CalculationRegister": {"xml_tag": "CalculationRegister", "dir": "CalculationRegisters"},
    "ChartOfAccounts": {"xml_tag": "ChartOfAccounts", "dir": "ChartsOfAccounts"},
    "ChartOfCharacteristicTypes": {"xml_tag": "ChartOfCharacteristicTypes", "dir": "ChartsOfCharacteristicTypes"},
    "ChartOfCalculationTypes": {"xml_tag": "ChartOfCalculationTypes", "dir": "ChartsOfCalculationTypes"},
    "BusinessProcess": {"xml_tag": "BusinessProcess", "dir": "BusinessProcesses"},
    "Task": {"xml_tag": "Task", "dir": "Tasks"},
    "ExchangePlan": {"xml_tag": "ExchangePlan", "dir": "ExchangePlans"},
    "DocumentJournal": {"xml_tag": "DocumentJournal", "dir": "DocumentJournals"},
    "Report": {"xml_tag": "Report", "dir": "Reports"},
    "DataProcessor": {"xml_tag": "DataProcessor", "dir": "DataProcessors"},
    # ─── Общие объекты ───
    "CommonModule": {"xml_tag": "CommonModule", "dir": "CommonModules"},
    "CommonForm": {"xml_tag": "CommonForm", "dir": "CommonForms"},
    "CommonCommand": {"xml_tag": "CommonCommand", "dir": "CommonCommands"},
    "CommonTemplate": {"xml_tag": "CommonTemplate", "dir": "CommonTemplates"},
    "CommonPicture": {"xml_tag": "CommonPicture", "dir": "CommonPictures"},
    "CommonAttribute": {"xml_tag": "CommonAttribute", "dir": "CommonAttributes"},
    "CommandGroup": {"xml_tag": "CommandGroup", "dir": "CommandGroups"},
    "DefinedType": {"xml_tag": "DefinedType", "dir": "DefinedTypes"},
    "DocumentNumerator": {"xml_tag": "DocumentNumerator", "dir": "DocumentNumerators"},
    "EventSubscription": {"xml_tag": "EventSubscription", "dir": "EventSubscriptions"},
    "FilterCriterion": {"xml_tag": "FilterCriterion", "dir": "FilterCriteria"},
    "FunctionalOption": {"xml_tag": "FunctionalOption", "dir": "FunctionalOptions"},
    "FunctionalOptionParameter": {"xml_tag": "FunctionalOptionParameter", "dir": "FunctionalOptionsParameters"},
    # ─── Сервисы ───
    "HTTPService": {"xml_tag": "HTTPService", "dir": "HTTPServices"},
    "WebService": {"xml_tag": "WebService", "dir": "WebServices"},
    "WSReference": {"xml_tag": "WSReference", "dir": "WSReferences"},
    # ─── Планирование и сессии ───
    "ScheduledJob": {"xml_tag": "ScheduledJob", "dir": "ScheduledJobs"},
    "Sequence": {"xml_tag": "Sequence", "dir": "Sequences"},
    "SessionParameter": {"xml_tag": "SessionParameter", "dir": "SessionParameters"},
    "SettingsStorage": {"xml_tag": "SettingsStorage", "dir": "SettingsStorages"},
    # ─── Прочие ───
    "Style": {"xml_tag": "Style", "dir": "Styles"},
    "Subsystem": {"xml_tag": "Subsystem", "dir": "Subsystems"},
    "Role": {"xml_tag": "Role", "dir": "Roles"},
    "XDTOPackage": {"xml_tag": "XDTOPackage", "dir": "XDTOPackages"},
}


# Типы, поддерживаемые DSL-компиляторами (подмножество полного TYPE_MAP).
# DSL работает с генерацией метаданных, поэтому поддерживает не все типы
# (например, WSReference и XDTOPackage — это интеграционные типы, их нельзя
# сгенерировать через DSL).
DSL_SUPPORTED_TYPES: frozenset[str] = frozenset(
    {
        "Catalog",
        "Document",
        "Enum",
        "Constant",
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "DocumentJournal",
        "Report",
        "DataProcessor",
        "CommonModule",
        "ScheduledJob",
        "EventSubscription",
        "DefinedType",
        "HTTPService",
        "WebService",
    }
)


def get_type_info(type_name: str) -> dict[str, Any] | None:
    """
    Получить информацию о типе объекта 1С.

    Args:
        type_name: Имя типа (Catalog, Document, WebService, etc.)

    Returns:
        dict[str, Any] с полями {xml_tag, dir} или None если тип неизвестен.

    Examples:
        >>> get_type_info("Catalog")
        {'xml_tag': 'Catalog', 'dir': 'Catalogs'}
        >>> get_type_info("Unknown")
        None
    """
    return TYPE_MAP.get(type_name)


def is_supported_type(type_name: str) -> bool:
    """Проверить, поддерживается ли тип в TYPE_MAP."""
    return type_name in TYPE_MAP


def is_dsl_supported(type_name: str) -> bool:
    """Проверить, поддерживается ли тип в DSL-компиляторах."""
    return type_name in DSL_SUPPORTED_TYPES


# ─── Derived constants (single source of truth) ───
# Все валидные директории метаданных 1С — derived из TYPE_MAP.
# Используется config_manager.py для валидации XML-выгрузок.
REQUIRED_TYPE_DIRS: tuple[str, ...] = tuple(sorted({v["dir"] for v in TYPE_MAP.values()}))

# Минимальный набор директорий, чтобы считать выгрузку валидной 1С-конфигурацией.
# Хотя бы одна из этих директорий должна присутствовать в распакованной выгрузке.
MIN_REQUIRED_DIRS: tuple[str, ...] = ("CommonModules", "Catalogs", "Documents", "Subsystems")
