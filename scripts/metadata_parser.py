#!/usr/bin/env python3
"""
metadata_parser.py — Парсер полных метаданных объектов 1С из XML выгрузки Конфигуратора.

Извлекает из XML:
- Реквизиты (Attributes) с типами данных
- Табличные части (TabularSections) с их реквизитами
- Стандартные реквизиты (StandardAttributes)
- Предопределённые значения (Predefined)
- Формы объекта (список имён)
- Команды объекта
- Свойства объекта (CodeLength, DescriptionLength, Hierarchical, и т.д.)

Поддерживаемые типы объектов:
- Catalog (Справочник)
- Document (Документ)
- InformationRegister (Регистр сведений)
- AccumulationRegister (Регистр накопления)
- DataProcessor (Обработка)
- Report (Отчёт)
- Enum (Перечисление)
- ChartOfCharacteristicTypes (План видов характеристик)
- ChartOfAccounts (План счетов)

Создаёт metadata-index.json для каждой конфигурации.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ============================================================================
# УТИЛИТЫ
# ============================================================================


def strip_ns(tag: str) -> str:
    """Убирает namespace из тега."""
    return tag.split("}")[1] if "}" in tag else tag


def get_child(elem, tag: str):
    """Возвращает первого потомка с указанным тегом (без namespace)."""
    if elem is None:
        return None
    for child in elem:
        if strip_ns(child.tag) == tag:
            return child
    return None


def get_children(elem, tag: str):
    """Возвращает всех потомков с указанным тегом."""
    if elem is None:
        return []
    return [child for child in elem if strip_ns(child.tag) == tag]


def get_text(elem, tag: str, default: str = "") -> str:
    """Возвращает текст первого потомка с тегом."""
    child = get_child(elem, tag)
    if child is not None:
        return child.text or ""
    return default


def get_synonym_text(parent, tag: str = "Synonym") -> str:
    """Извлекает синоним из v8:item/v8:content."""
    elem = get_child(parent, tag)
    if elem is None:
        return ""
    for item in elem:
        if strip_ns(item.tag) == "item":
            content = get_text(item, "content")
            if content:
                return content
    return ""


def parse_type(type_elem) -> list[str]:
    """Парсит элемент <Type> и возвращает список типов."""
    if type_elem is None:
        return []
    types = []
    for child in type_elem:
        if strip_ns(child.tag) == "Type":
            text = child.text or ""
            if text:
                types.append(text)
    # Также проверяем TypeLink
    for child in type_elem:
        if strip_ns(child.tag) == "TypeLink":
            text = child.text or ""
            if text:
                types.append(f"TypeLink:{text}")
    return types


# ============================================================================
# ПАРСЕР РЕКВИЗИТОВ
# ============================================================================


def parse_attribute(attr_elem) -> dict:
    """Парсит <Attribute> — реквизит объекта или табличной части."""
    uuid = attr_elem.get("uuid", "")
    name = ""
    properties = get_child(attr_elem, "Properties")
    if properties is not None:
        name = get_text(properties, "Name")

    result = {
        "name": name,
        "uuid": uuid,
        "synonym": get_synonym_text(properties) if properties is not None else "",
        "comment": get_text(properties, "Comment") if properties is not None else "",
        "types": [],
        "password_mode": False,
        "fill_checking": "",
        "use": "",
        "indexing": "",
    }

    if properties is not None:
        type_elem = get_child(properties, "Type")
        result["types"] = parse_type(type_elem)
        result["password_mode"] = get_text(properties, "PasswordMode") == "true"
        result["fill_checking"] = get_text(properties, "FillChecking")
        result["use"] = get_text(properties, "Use")
        result["indexing"] = get_text(properties, "Indexing")

    return result


def parse_tabular_section(ts_elem) -> dict:
    """Парсит <TabularSection> — табличную часть."""
    uuid = ts_elem.get("uuid", "")
    name = ""
    properties = get_child(ts_elem, "Properties")
    if properties is not None:
        name = get_text(properties, "Name")

    result = {
        "name": name,
        "uuid": uuid,
        "synonym": get_synonym_text(properties) if properties is not None else "",
        "comment": get_text(properties, "Comment") if properties is not None else "",
        "attributes": [],
    }

    # Реквизиты табличной части — в ChildObjects
    child_objects = get_child(ts_elem, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            if strip_ns(child.tag) == "Attribute":
                result["attributes"].append(parse_attribute(child))

    return result


def parse_standard_attribute(attr_elem) -> dict:
    """Парсит <xr:StandardAttribute> — стандартный реквизит."""
    name = attr_elem.get("name", "")
    return {
        "name": name,
        "fill_checking": get_text(attr_elem, "FillChecking"),
        "fill_from_filling_value": get_text(attr_elem, "FillFromFillingValue") == "true",
        "create_on_input": get_text(attr_elem, "CreateOnInput"),
        "data_history": get_text(attr_elem, "DataHistory"),
    }


# ============================================================================
# ПАРСЕРЫ ОБЪЕКТОВ
# ============================================================================


def parse_catalog(xml_path: Path) -> dict:
    """Парсит Catalog.xml — справочник."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    catalog = get_child(root, "Catalog")
    if catalog is None:
        return {}

    uuid = catalog.get("uuid", "")
    properties = get_child(catalog, "Properties")

    result = {
        "type": "Catalog",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "hierarchical": get_text(properties, "Hierarchical") == "true",
        "hierarchy_type": get_text(properties, "HierarchyType"),
        "code_length": int(get_text(properties, "CodeLength") or "0"),
        "description_length": int(get_text(properties, "DescriptionLength") or "0"),
        "code_type": get_text(properties, "CodeType"),
        "check_unique": get_text(properties, "CheckUnique") == "true",
        "autonumbering": get_text(properties, "Autonumbering") == "true",
        "default_object_form": get_text(properties, "DefaultObjectForm"),
        "default_list_form": get_text(properties, "DefaultListForm"),
        "default_choice_form": get_text(properties, "DefaultChoiceForm"),
        "standard_attributes": [],
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "commands": [],
    }

    # StandardAttributes
    for sa in get_children(properties, "StandardAttributes"):
        result["standard_attributes"].append(parse_standard_attribute(sa))

    # ChildObjects: Attributes, TabularSections, Forms, Commands
    child_objects = get_child(catalog, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "TabularSection":
                result["tabular_sections"].append(parse_tabular_section(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})
            elif tag == "Command":
                result["commands"].append({"name": child.text or ""})

    return result


def parse_document(xml_path: Path) -> dict:
    """Парсит Document.xml — документ."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    document = get_child(root, "Document")
    if document is None:
        return {}

    uuid = document.get("uuid", "")
    properties = get_child(document, "Properties")

    result = {
        "type": "Document",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "number_length": int(get_text(properties, "NumberLength") or "0"),
        "check_unique": get_text(properties, "CheckUnique") == "true",
        "autonumbering": get_text(properties, "Autonumbering") == "true",
        "default_object_form": get_text(properties, "DefaultObjectForm"),
        "default_list_form": get_text(properties, "DefaultListForm"),
        "standard_attributes": [],
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "commands": [],
    }

    for sa in get_children(properties, "StandardAttributes"):
        result["standard_attributes"].append(parse_standard_attribute(sa))

    child_objects = get_child(document, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "TabularSection":
                result["tabular_sections"].append(parse_tabular_section(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})
            elif tag == "Command":
                result["commands"].append({"name": child.text or ""})

    return result


def parse_information_register(xml_path: Path) -> dict:
    """Парсит InformationRegister.xml — регистр сведений."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    reg = get_child(root, "InformationRegister")
    if reg is None:
        return {}

    uuid = reg.get("uuid", "")
    properties = get_child(reg, "Properties")

    result = {
        "type": "InformationRegister",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "periodicity": get_text(properties, "Periodicity"),
        "write_on_post": get_text(properties, "WriteOnPost"),
        "main_filter_on_period": get_text(properties, "MainFilterOnPeriod") == "true",
        "include_help_in_contents": get_text(properties, "IncludeHelpInContents") == "true",
        "standard_attributes": [],
        "dimensions": [],  # Измерения
        "resources": [],  # Ресурсы
        "attributes": [],  # Реквизиты
        "forms": [],
        "commands": [],
    }

    for sa in get_children(properties, "StandardAttributes"):
        result["standard_attributes"].append(parse_standard_attribute(sa))

    child_objects = get_child(reg, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Dimension":
                attr = parse_attribute(child)
                attr["kind"] = "Dimension"
                result["dimensions"].append(attr)
            elif tag == "Resource":
                attr = parse_attribute(child)
                attr["kind"] = "Resource"
                result["resources"].append(attr)
            elif tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})
            elif tag == "Command":
                result["commands"].append({"name": child.text or ""})

    return result


def parse_accumulation_register(xml_path: Path) -> dict:
    """Парсит AccumulationRegister.xml — регистр накопления."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    reg = get_child(root, "AccumulationRegister")
    if reg is None:
        return {}

    uuid = reg.get("uuid", "")
    properties = get_child(reg, "Properties")

    result = {
        "type": "AccumulationRegister",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "register_type": get_text(properties, "RegisterType"),  # Balance or Turnovers
        "enable_expression_totals": get_text(properties, "EnableExpressionTotals") == "true",
        "standard_attributes": [],
        "dimensions": [],
        "resources": [],
        "attributes": [],
        "forms": [],
        "commands": [],
    }

    for sa in get_children(properties, "StandardAttributes"):
        result["standard_attributes"].append(parse_standard_attribute(sa))

    child_objects = get_child(reg, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Dimension":
                attr = parse_attribute(child)
                attr["kind"] = "Dimension"
                result["dimensions"].append(attr)
            elif tag == "Resource":
                attr = parse_attribute(child)
                attr["kind"] = "Resource"
                result["resources"].append(attr)
            elif tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})

    return result


def parse_data_processor(xml_path: Path) -> dict:
    """Парсит DataProcessor.xml — обработка."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    dp = get_child(root, "DataProcessor")
    if dp is None:
        return {}

    uuid = dp.get("uuid", "")
    properties = get_child(dp, "Properties")

    result = {
        "type": "DataProcessor",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "default_form": get_text(properties, "DefaultForm"),
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "commands": [],
    }

    child_objects = get_child(dp, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "TabularSection":
                result["tabular_sections"].append(parse_tabular_section(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})
            elif tag == "Command":
                result["commands"].append({"name": child.text or ""})

    return result


def parse_report(xml_path: Path) -> dict:
    """Парсит Report.xml — отчёт."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    rep = get_child(root, "Report")
    if rep is None:
        return {}

    uuid = rep.get("uuid", "")
    properties = get_child(rep, "Properties")

    result = {
        "type": "Report",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "default_form": get_text(properties, "DefaultForm"),
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "commands": [],
    }

    child_objects = get_child(rep, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "Attribute":
                result["attributes"].append(parse_attribute(child))
            elif tag == "TabularSection":
                result["tabular_sections"].append(parse_tabular_section(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})
            elif tag == "Command":
                result["commands"].append({"name": child.text or ""})

    return result


def parse_enum(xml_path: Path) -> dict:
    """Парсит Enum.xml — перечисление."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    enum = get_child(root, "Enum")
    if enum is None:
        return {}

    uuid = enum.get("uuid", "")
    properties = get_child(enum, "Properties")

    result = {
        "type": "Enum",
        "name": get_text(properties, "Name"),
        "uuid": uuid,
        "synonym": get_synonym_text(properties),
        "comment": get_text(properties, "Comment"),
        "enum_values": [],
        "forms": [],
    }

    child_objects = get_child(enum, "ChildObjects")
    if child_objects is not None:
        for child in child_objects:
            tag = strip_ns(child.tag)
            if tag == "EnumValue":
                value_name = get_text(child, "Name")
                value_syn = get_synonym_text(child)
                result["enum_values"].append(
                    {
                        "name": value_name,
                        "synonym": value_syn,
                    }
                )
            elif tag == "Form":
                result["forms"].append({"name": child.text or ""})

    return result


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

TYPE_PARSERS = {
    "Catalogs": parse_catalog,
    "Documents": parse_document,
    "InformationRegisters": parse_information_register,
    "AccumulationRegisters": parse_accumulation_register,
    "DataProcessors": parse_data_processor,
    "Reports": parse_report,
    "Enums": parse_enum,
}


def parse_config_metadata(config_dir: Path | str, progress_callback=None) -> dict:
    """Парсит все объекты метаданных конфигурации.

    Args:
        config_dir: Путь к директории конфигурации
        progress_callback: Функция(done, total) для прогресса

    Returns:
        dict: {
            'objects': [{type, name, uuid, ...}, ...],
            'stats': {
                'total': int,
                'by_type': {type_name: count, ...},
                'total_attributes': int,
                'total_tabular_sections': int,
            }
        }
    """
    config_dir = Path(config_dir)
    objects = []
    stats = {
        "total": 0,
        "by_type": {},
        "total_attributes": 0,
        "total_tabular_sections": 0,
        "total_forms": 0,
        "total_commands": 0,
    }

    # Сначала подсчитаем общее количество файлов для прогресса
    total_files = 0
    for type_dir_name in TYPE_PARSERS:
        type_dir = config_dir / type_dir_name
        if type_dir.exists():
            for xml_file in type_dir.glob("*.xml"):
                if xml_file.is_file():
                    total_files += 1

    done = 0
    for type_dir_name, parser in TYPE_PARSERS.items():
        type_dir = config_dir / type_dir_name
        if not type_dir.exists():
            continue

        for xml_file in sorted(type_dir.glob("*.xml")):
            if not xml_file.is_file():
                continue
            done += 1
            if progress_callback and done % 100 == 0:
                progress_callback(done, total_files)

            try:
                obj = parser(xml_file)
                if obj and obj.get("name"):
                    objects.append(obj)
                    type_name = obj["type"]
                    stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
                    stats["total"] += 1
                    stats["total_attributes"] += len(obj.get("attributes", []))
                    stats["total_tabular_sections"] += len(obj.get("tabular_sections", []))
                    stats["total_forms"] += len(obj.get("forms", []))
                    stats["total_commands"] += len(obj.get("commands", []))
            except Exception as e:
                print(f"  ⚠️ Ошибка парсинга {xml_file}: {e}", file=sys.stderr)

    return {"objects": objects, "stats": stats}


def save_metadata_index(config_dir: Path | str, output_path: Path | str) -> dict:
    """Парсит метаданные и сохраняет в metadata-index.json.

    Returns:
        Статистика парсинга
    """
    config_dir = Path(config_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def progress(done, total):
        print(f"  Обработано {done}/{total} объектов...", end="\r", flush=True)

    print(f"Парсинг метаданных из: {config_dir}")
    result = parse_config_metadata(config_dir, progress)

    print(f"\n✅ Распарсено {result['stats']['total']} объектов")
    print(f"   Реквизитов: {result['stats']['total_attributes']}")
    print(f"   Табличных частей: {result['stats']['total_tabular_sections']}")
    print(f"   Форм: {result['stats']['total_forms']}")
    print(f"   Команд: {result['stats']['total_commands']}")
    print("   По типам:")
    for type_name, count in sorted(result["stats"]["by_type"].items()):
        print(f"     {type_name}: {count}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в: {output_path} ({output_path.stat().st_size // 1024} КБ)")

    return result["stats"]


# ============================================================================
# CLI
# ============================================================================


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 metadata_parser.py <config_dir> [output_path]")
        print()
        print("Пример:")
        print("  python3 metadata_parser.py data/configs/ut11 derived/configs/ut11/metadata-index.json")
        sys.exit(1)

    config_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "metadata-index.json"

    save_metadata_index(config_dir, output)


if __name__ == "__main__":
    main()
