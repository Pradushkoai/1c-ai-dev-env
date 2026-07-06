"""
edt_parser.py — Парсер EDT (Enterprise Development Tools) формата 1С.

P2.1: MVP парсер EDT XML выгрузки в унифицированный формат metadata-index.

EDT формат отличается от Конфигуратора:
- Структура каталогов: EDT использует src/<Configuration>/ вместо корня
- Имена файлов: Configuration.mdo вместо Configuration.xml
- Namespace: http://g5.1c.ru/v8/dt/metadata/mdclasses вместо v8.1c.ru/8.3/MDClasses
- Дополнительные файлы: .mdo, .en.md (документация), .settings

Этот парсер конвертирует EDT выгрузку в тот же формат, что и
metadata_extractor (unified-metadata-index.json), чтобы все MCP tools
работали с обоими форматами без изменений.

Использование:
    from src.services.edt_parser import EdtParser

    parser = EdtParser()
    objects = parser.parse(edt_project_path)
    # objects — список в формате unified-metadata-index

Статус: MVP — поддерживает Catalog, Document, Enum, InformationRegister.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# EDT namespace
NS_EDT = "http://g5.1c.ru/v8/dt/metadata/mdclasses"

# Маппинг типов объектов EDT → unified format
# D2.8 (2026-07-05): расширено с 9 до 35 типов
EDT_TYPE_MAP: dict[str, str] = {
    "Catalog": "Catalog",
    "Document": "Document",
    "Enum": "Enum",
    "InformationRegister": "InformationRegister",
    "AccumulationRegister": "AccumulationRegister",
    "AccountingRegister": "AccountingRegister",
    "CalculationRegister": "CalculationRegister",
    "Constant": "Constant",
    "CommonModule": "CommonModule",
    "CommonForm": "CommonForm",
    "CommonCommand": "CommonCommand",
    "CommonTemplate": "CommonTemplate",
    "CommonPicture": "CommonPicture",
    "CommonAttribute": "CommonAttribute",
    "Report": "Report",
    "DataProcessor": "DataProcessor",
    "ChartOfAccounts": "ChartOfAccounts",
    "ChartOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes": "ChartOfCalculationTypes",
    "BusinessProcess": "BusinessProcess",
    "Task": "Task",
    "ExchangePlan": "ExchangePlan",
    "DocumentJournal": "DocumentJournal",
    "DocumentNumerator": "DocumentNumerator",
    "Sequence": "Sequence",
    "DefinedType": "DefinedType",
    "EventSubscription": "EventSubscription",
    "ScheduledJob": "ScheduledJob",
    "FilterCriterion": "FilterCriterion",
    "CommandGroup": "CommandGroup",
    "FunctionalOption": "FunctionalOption",
    "FunctionalOptionParameter": "FunctionalOptionParameter",
    "SessionParameter": "SessionParameter",
    "SettingsStorage": "SettingsStorage",
    "Style": "Style",
}

# Папки EDT по типам объектов
# D2.8 (2026-07-05): расширено с 9 до 35 типов
EDT_DIRS: dict[str, str] = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "Enum": "Enums",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "AccountingRegister": "AccountingRegisters",
    "CalculationRegister": "CalculationRegisters",
    "Constant": "Constants",
    "CommonModule": "CommonModules",
    "CommonForm": "CommonForms",
    "CommonCommand": "CommonCommands",
    "CommonTemplate": "CommonTemplates",
    "CommonPicture": "CommonPictures",
    "CommonAttribute": "CommonAttributes",
    "Report": "Reports",
    "DataProcessor": "DataProcessors",
    "ChartOfAccounts": "ChartsOfAccounts",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
    "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks",
    "ExchangePlan": "ExchangePlans",
    "DocumentJournal": "DocumentJournals",
    "DocumentNumerator": "DocumentNumerators",
    "Sequence": "Sequences",
    "DefinedType": "DefinedTypes",
    "EventSubscription": "EventSubscriptions",
    "ScheduledJob": "ScheduledJobs",
    "FilterCriterion": "FilterCriteria",
    "CommandGroup": "CommandGroups",
    "FunctionalOption": "FunctionalOptions",
    "FunctionalOptionParameter": "FunctionalOptionsParameters",
    "SessionParameter": "SessionParameters",
    "SettingsStorage": "SettingsStorages",
    "Style": "Styles",
}


class EdtParser:
    """Парсер EDT (Enterprise Development Tools) формата 1С.

    MVP (P2.1): поддерживает Catalog, Document, Enum, InformationRegister.
    Конвертирует EDT XML в unified-metadata-index формат.
    """

    def __init__(self) -> None:
        self._objects: list[dict[str, Any]] = []
        self._config_name: str = ""

    def parse(self, edt_project_path: Path | str) -> list[dict[str, Any]]:
        """Парсить EDT проект в unified metadata format.

        Args:
            edt_project_path: Путь к корню EDT проекта (содержит src/).

        Returns:
            Список объектов в unified-metadata-index формате.
        """
        project_path = Path(edt_project_path)
        self._objects = []
        self._config_name = self._detect_config_name(project_path)

        # EDT структура: src/<Configuration>/Configuration.mdo
        # и src/<Configuration>/Catalogs/, Documents/, и т.д.
        src_dir = project_path / "src"
        if not src_dir.exists():
            # Fallback: корень проекта может быть напрямую конфигурацией
            src_dir = project_path

        # Ищем поддиректории с типами объектов
        for obj_type, dir_name in EDT_DIRS.items():
            type_dir = src_dir / dir_name
            if type_dir.is_dir():
                for mdo_file in type_dir.glob("*.mdo"):
                    try:
                        obj = self._parse_mdo_file(mdo_file, obj_type)
                        if obj:
                            self._objects.append(obj)
                    except Exception as e:
                        logger.warning("Failed to parse %s: %s", mdo_file, e)

        logger.info("EDT parse complete: %d objects found", len(self._objects))
        return self._objects

    def _detect_config_name(self, project_path: Path) -> str:
        """Определить имя конфигурации из EDT проекта."""
        # Ищем Configuration.mdo
        src_dir = project_path / "src"
        if not src_dir.exists():
            src_dir = project_path

        for config_mdo in src_dir.rglob("Configuration.mdo"):
            try:
                tree = ET.parse(config_mdo)
                root = tree.getroot()
                # Имя конфигурации (пробуем с EDT namespace и без)
                name = self._get_text(root, "name")
                if name:
                    return name
            except ET.ParseError:
                continue

        return project_path.name

    def _parse_mdo_file(self, mdo_path: Path, obj_type: str) -> dict[str, Any] | None:
        """Парсить один .mdo файл EDT.

        Args:
            mdo_path: Путь к .mdo файлу.
            obj_type: Тип объекта (Catalog, Document, и т.д.).

        Returns:
            Объект в unified format, или None если парсинг не удался.
        """
        try:
            tree = ET.parse(mdo_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.warning("XML parse error in %s: %s", mdo_path, e)
            return None

        # Извлекаем имя объекта
        name = self._get_text(root, "name")
        if not name:
            # Fallback: имя из имени файла
            name = mdo_path.stem

        # Создаём объект в unified format
        obj: dict[str, Any] = {
            "type": EDT_TYPE_MAP.get(obj_type, obj_type),
            "name": name,
            "synonym": self._get_text(root, "synonym") or name,
            "comment": self._get_text(root, "comment") or "",
            "source": "edt",
            "mdo_path": str(mdo_path),
        }

        # Парсим специфичные для типа поля
        self._parse_type_specific_fields(obj_type, root, obj)

        return obj

    def _parse_type_specific_fields(
        self, obj_type: str, root: ET.Element, obj: dict[str, Any]
    ) -> None:
        """T5.6: Парсить специфичные для типа поля (35 типов)."""
        if obj_type == "Catalog":
            self._parse_catalog_fields(root, obj)
        elif obj_type == "Document":
            self._parse_document_fields(root, obj)
        elif obj_type in ("InformationRegister", "AccumulationRegister",
                          "AccountingRegister", "CalculationRegister"):
            self._parse_register_fields(root, obj)
        elif obj_type == "Enum":
            self._parse_enum_fields(root, obj)
        elif obj_type == "Constant":
            self._parse_constant_fields(root, obj)
        elif obj_type == "CommonModule":
            self._parse_common_module_fields(root, obj)
        elif obj_type == "CommonForm":
            self._parse_common_form_fields(root, obj)
        elif obj_type == "CommonCommand":
            self._parse_common_command_fields(root, obj)
        elif obj_type == "CommonTemplate":
            self._parse_common_template_fields(root, obj)
        elif obj_type == "CommonPicture":
            self._parse_common_picture_fields(root, obj)
        elif obj_type == "CommonAttribute":
            self._parse_common_attribute_fields(root, obj)
        elif obj_type == "Report":
            self._parse_report_fields(root, obj)
        elif obj_type == "DataProcessor":
            self._parse_data_processor_fields(root, obj)
        elif obj_type in ("ChartOfAccounts", "ChartOfCharacteristicTypes",
                          "ChartOfCalculationTypes"):
            self._parse_chart_fields(root, obj)
        elif obj_type == "BusinessProcess":
            self._parse_business_process_fields(root, obj)
        elif obj_type == "Task":
            self._parse_task_fields(root, obj)
        elif obj_type == "ExchangePlan":
            self._parse_exchange_plan_fields(root, obj)
        elif obj_type == "DocumentJournal":
            self._parse_document_journal_fields(root, obj)
        elif obj_type == "DocumentNumerator":
            self._parse_document_numerator_fields(root, obj)
        elif obj_type == "Sequence":
            self._parse_sequence_fields(root, obj)
        elif obj_type == "DefinedType":
            self._parse_defined_type_fields(root, obj)
        elif obj_type == "EventSubscription":
            self._parse_event_subscription_fields(root, obj)
        elif obj_type == "ScheduledJob":
            self._parse_scheduled_job_fields(root, obj)
        elif obj_type == "FilterCriterion":
            self._parse_filter_criterion_fields(root, obj)
        elif obj_type == "CommandGroup":
            self._parse_command_group_fields(root, obj)
        elif obj_type == "FunctionalOption":
            self._parse_functional_option_fields(root, obj)
        elif obj_type == "FunctionalOptionParameter":
            self._parse_functional_option_parameter_fields(root, obj)
        elif obj_type == "SessionParameter":
            self._parse_session_parameter_fields(root, obj)
        elif obj_type == "SettingsStorage":
            self._parse_settings_storage_fields(root, obj)
        elif obj_type == "Style":
            self._parse_style_fields(root, obj)

    def _parse_catalog_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля справочника."""
        obj["hierarchical"] = self._get_text(root, "hierarchical") == "true"
        obj["owners"] = []  # TODO: парсить владельцев
        # Реквизиты
        obj["attributes"] = self._parse_attributes(root)

    def _parse_document_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля документа."""
        obj["number_type"] = self._get_text(root, "numberType") or "String"
        obj["register_records"] = []  # TODO: парсить регистры
        obj["attributes"] = self._parse_attributes(root)

    def _parse_register_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля регистра сведений."""
        obj["periodicity"] = self._get_text(root, "periodicity") or "Nonperiodical"
        obj["resources"] = self._parse_attributes(root, tag="resources")
        obj["dimensions"] = self._parse_attributes(root, tag="dimensions")

    def _parse_enum_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля перечисления."""
        obj["enum_values"] = self._parse_attributes(root, tag="enumValues")

    def _parse_constant_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля константы."""
        obj["value_type"] = self._get_text(root, "type") or "String"

    def _parse_common_module_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общего модуля."""
        obj["server"] = self._get_text(root, "server") == "true"
        obj["client"] = self._get_text(root, "client") == "true"
        obj["privileged"] = self._get_text(root, "privileged") == "true"
        obj["server_call"] = self._get_text(root, "serverCall") == "true"

    def _parse_common_form_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общей формы."""
        obj["form_type"] = self._get_text(root, "formType") or "Managed"

    def _parse_common_command_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общей команды."""
        obj["command_kind"] = self._get_text(root, "commandKind") or "Auto"
        obj["group"] = self._get_text(root, "group") or ""

    def _parse_common_template_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общего макета."""
        obj["template_type"] = self._get_text(root, "templateType") or "SpreadsheetDocument"

    def _parse_common_picture_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общего рисунка."""
        obj["picture_size"] = self._get_text(root, "pictureSize") or "16"

    def _parse_common_attribute_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля общего реквизита."""
        obj["value_type"] = self._get_text(root, "type") or "String"
        obj["auto_use"] = self._get_text(root, "autoUse") or "Use"

    def _parse_report_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля отчёта."""
        obj["has_data_composition_schema"] = (
            self._get_text(root, "dataCompositionSchema") is not None
        )
        obj["attributes"] = self._parse_attributes(root)

    def _parse_data_processor_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля обработки."""
        obj["attributes"] = self._parse_attributes(root)

    def _parse_chart_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля плана видов (ChartOf*)."""
        obj["hierarchical"] = self._get_text(root, "hierarchical") == "true"
        obj["attributes"] = self._parse_attributes(root)

    def _parse_business_process_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля бизнес-процесса."""
        obj["number_type"] = self._get_text(root, "numberType") or "String"
        obj["attributes"] = self._parse_attributes(root)

    def _parse_task_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля задачи."""
        obj["number_type"] = self._get_text(root, "numberType") or "String"
        obj["attributes"] = self._parse_attributes(root)

    def _parse_exchange_plan_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля плана обмена."""
        obj["distributed"] = self._get_text(root, "distributed") == "true"
        obj["attributes"] = self._parse_attributes(root)

    def _parse_document_journal_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля журнала документов."""
        obj["registered_types"] = self._parse_attributes(root, tag="registeredTypes")

    def _parse_document_numerator_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля нумератора документов."""
        obj["number_type"] = self._get_text(root, "numberType") or "String"

    def _parse_sequence_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля последовательности."""
        obj["document_type"] = self._get_text(root, "documentType") or ""

    def _parse_defined_type_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля определяемого типа."""
        obj["value_type"] = self._get_text(root, "type") or "String"

    def _parse_event_subscription_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля подписки на события."""
        obj["event"] = self._get_text(root, "event") or ""
        obj["handler"] = self._get_text(root, "handler") or ""

    def _parse_scheduled_job_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля регламентного задания."""
        obj["method_name"] = self._get_text(root, "methodName") or ""
        obj["schedule"] = self._get_text(root, "schedule") or ""

    def _parse_filter_criterion_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля критерия отбора."""
        obj["value_type"] = self._get_text(root, "type") or "String"
        obj["content"] = self._parse_attributes(root, tag="content")

    def _parse_command_group_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля группы команд."""
        obj["group_kind"] = self._get_text(root, "groupKind") or "ActionsPanel"

    def _parse_functional_option_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля функциональной опции."""
        obj["value_type"] = self._get_text(root, "type") or "Boolean"
        obj["location"] = self._get_text(root, "location") or ""

    def _parse_functional_option_parameter_fields(
        self, root: ET.Element, obj: dict[str, Any]
    ) -> None:
        """Парсить поля параметра функциональной опции."""
        obj["value_type"] = self._get_text(root, "type") or "String"
        obj["use"] = self._get_text(root, "use") or "Use"

    def _parse_session_parameter_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля параметра сеанса."""
        obj["value_type"] = self._get_text(root, "type") or "String"

    def _parse_settings_storage_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля хранилища настроек."""
        obj["form"] = self._get_text(root, "form") or ""

    def _parse_style_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля стиля."""
        obj["style_items"] = self._parse_attributes(root, tag="styleItems")

    def _parse_attributes(self, root: ET.Element, tag: str = "attributes") -> list[dict[str, str]]:
        """Парсить реквизиты/ресурсы/измерения объекта.

        Args:
            root: XML корень элемента.
            tag: Имя тега для поиска (attributes, resources, dimensions).

        Returns:
            Список атрибутов [{name, type, synonym}].
        """
        attrs: list[dict[str, str]] = []
        # Пробуем с EDT namespace и без
        attr_elems = root.findall(f".//{{{NS_EDT}}}{tag}")
        if not attr_elems:
            attr_elems = root.findall(f".//{tag}")

        for attr_elem in attr_elems:
            name = self._get_text(attr_elem, "name")
            if name:
                attrs.append(
                    {
                        "name": name,
                        "type": self._get_text(attr_elem, "type") or "String",
                        "synonym": self._get_text(attr_elem, "synonym") or name,
                    }
                )
        return attrs

    def _get_text(self, root: ET.Element, tag: str) -> str | None:
        """Получить текст элемента по имени тега (с EDT namespace).

        Args:
            root: XML элемент для поиска.
            tag: Имя тега без namespace.

        Returns:
            Текст элемента, или None если не найден.
        """
        # Пробуем с EDT namespace
        elem = root.find(f".//{{{NS_EDT}}}{tag}")
        if elem is not None and elem.text:
            return elem.text.strip()

        # Fallback: без namespace
        elem = root.find(f".//{tag}")
        if elem is not None and elem.text:
            return elem.text.strip()

        return None

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику парсинга.

        Returns:
            {config_name, total_objects, by_type}
        """
        by_type: dict[str, int] = {}
        for obj in self._objects:
            t = obj.get("type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "config_name": self._config_name,
            "total_objects": len(self._objects),
            "by_type": by_type,
            "source": "edt",
        }
