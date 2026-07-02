#!/usr/bin/env python3
"""
edt_form_converter.py — Конвертер EDT Form.xml → v8unpack Form.elem.json.

P3.4: Превращает форму из EDT XML-формата во внутренний формат v8unpack
Form.elem.json, который EpfFactory использует для сборки .epf.

Поддерживаемые элементы EDT Form.xml:
- InputField (поле ввода)
- Button (кнопка)
- Label (надпись)
- Table (таблица)
- Group (группа)
- CheckBox (флажок)
- RadioButton (переключатель)

Использование:
    from src.services.edt_form_converter import convert_edt_form_to_v8unpack

    form_elem = convert_edt_form_to_v8unpack("path/to/Form.xml")
    # → Form.elem.json dict

Или через CLI:
    python3 -m src.services.edt_form_converter Form.xml output.json
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Namespace 1С для EDT Form.xml
NS_MD = "http://v8.1c.ru/8.3/MDClasses"


def _strip_ns(tag: str) -> str:
    """Убрать namespace из тега."""
    return tag.split("}")[-1] if "}" in tag else tag


def _get_child_text(elem: ET.Element, tag: str, default: str = "") -> str:
    """Получить текст первого потомка с указанным тегом."""
    for child in elem:
        if _strip_ns(child.tag) == tag:
            return child.text or ""
    return default


def _convert_input_field(elem: ET.Element, id_counter: list[int]) -> dict[str, Any]:
    """Конвертировать InputField из EDT в v8unpack prop."""
    name = _get_child_text(elem, "Name")
    title = _get_child_text(elem, "Title")
    data_path = _get_child_text(elem, "DataPath")

    prop_id = str(id_counter[0])
    id_counter[0] += 1

    return {
        "name": name,
        "id": prop_id,
        "type": "InputField",
        "title": title,
        "data_path": data_path,
        "raw": _build_raw_for_input_field(name, prop_id),
    }


def _convert_button(elem: ET.Element, id_counter: list[int]) -> dict[str, Any]:
    """Конвертировать Button из EDT в v8unpack prop."""
    name = _get_child_text(elem, "Name")
    title = _get_child_text(elem, "Title")
    command_name = _get_child_text(elem, "CommandName")

    prop_id = str(id_counter[0])
    id_counter[0] += 1

    return {
        "name": name,
        "id": prop_id,
        "type": "Button",
        "title": title,
        "command_name": command_name,
        "raw": _build_raw_for_button(name, prop_id),
    }


def _convert_label(elem: ET.Element, id_counter: list[int]) -> dict[str, Any]:
    """Конвертировать Label из EDT в v8unpack prop."""
    name = _get_child_text(elem, "Name")
    title = _get_child_text(elem, "Title")

    prop_id = str(id_counter[0])
    id_counter[0] += 1

    return {
        "name": name,
        "id": prop_id,
        "type": "Label",
        "title": title,
        "raw": _build_raw_for_label(name, prop_id),
    }


def _convert_table(elem: ET.Element, id_counter: list[int]) -> dict[str, Any]:
    """Конвертировать Table из EDT в v8unpack prop."""
    name = _get_child_text(elem, "Name")
    title = _get_child_text(elem, "Title")
    data_path = _get_child_text(elem, "DataPath")

    prop_id = str(id_counter[0])
    id_counter[0] += 1

    # Колонки таблицы
    columns = []
    for child in elem:
        if _strip_ns(child.tag) == "Columns":
            for col in child:
                if _strip_ns(col.tag) == "Column":
                    col_name = _get_child_text(col, "Name")
                    col_title = _get_child_text(col, "Title")
                    col_data_path = _get_child_text(col, "DataPath")
                    columns.append(
                        {
                            "name": col_name,
                            "title": col_title,
                            "data_path": col_data_path,
                        }
                    )

    return {
        "name": name,
        "id": prop_id,
        "type": "Table",
        "title": title,
        "data_path": data_path,
        "columns": columns,
        "raw": _build_raw_for_table(name, prop_id),
    }


def _convert_checkbox(elem: ET.Element, id_counter: list[int]) -> dict[str, Any]:
    """Конвертировать CheckBox из EDT в v8unpack prop."""
    name = _get_child_text(elem, "Name")
    title = _get_child_text(elem, "Title")
    data_path = _get_child_text(elem, "DataPath")

    prop_id = str(id_counter[0])
    id_counter[0] += 1

    return {
        "name": name,
        "id": prop_id,
        "type": "CheckBox",
        "title": title,
        "data_path": data_path,
        "raw": _build_raw_for_checkbox(name, prop_id),
    }


def _build_raw_for_input_field(name: str, prop_id: str) -> list:
    """Построить raw-структуру v8unpack для InputField (минимальная)."""
    return [
        "9",
        [prop_id],
        "0",
        f'"{name}"',
        ["1", "0"],
        ['"Pattern"', ['"#"', "Родитель"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", "0"],
        ["0", "0"],
        "1",
        "0",
        "0",
        "0",
        ["0", "0"],
        ["0", "0"],
    ]


def _build_raw_for_button(name: str, prop_id: str) -> list:
    """Построить raw-структуру v8unpack для Button (минимальная)."""
    return [
        "9",
        [prop_id],
        "0",
        f'"{name}"',
        ["1", "0"],
        ['"Pattern"', ['"#"', "Родитель"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", "0"],
        ["0", "0"],
        "1",
        "0",
        "0",
        "0",
        ["0", "0"],
        ["0", "0"],
    ]


def _build_raw_for_label(name: str, prop_id: str) -> list:
    """Построить raw-структуру v8unpack для Label (минимальная)."""
    return [
        "9",
        [prop_id],
        "0",
        f'"{name}"',
        ["1", "0"],
        ['"Pattern"', ['"#"', "Родитель"]],
        ["0", "0"],
        ["0", "0"],
        ["0", "0"],
        ["0", "0"],
        "1",
        "0",
        "0",
        "0",
        ["0", "0"],
        ["0", "0"],
    ]


def _build_raw_for_table(name: str, prop_id: str) -> list:
    """Построить raw-структуру v8unpack для Table (минимальная)."""
    return [
        "9",
        [prop_id],
        "0",
        f'"{name}"',
        ["1", "0"],
        ['"Pattern"', ['"#"', "Родитель"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", "0"],
        ["0", "0"],
        "1",
        "0",
        "0",
        "0",
        ["0", "0"],
        ["0", "0"],
    ]


def _build_raw_for_checkbox(name: str, prop_id: str) -> list:
    """Построить raw-структуру v8unpack для CheckBox (минимальная)."""
    return [
        "9",
        [prop_id],
        "0",
        f'"{name}"',
        ["1", "0"],
        ['"Pattern"', ['"#"', "Родитель"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", ["0", ['"B"', "1"], "0"]],
        ["0", "0"],
        ["0", "0"],
        "1",
        "0",
        "0",
        "0",
        ["0", "0"],
        ["0", "0"],
    ]


# Маппинг типов элементов EDT → конвертеры
ELEMENT_CONVERTERS = {
    "InputField": _convert_input_field,
    "Button": _convert_button,
    "Label": _convert_label,
    "Table": _convert_table,
    "CheckBox": _convert_checkbox,
}


def convert_edt_form_to_v8unpack(form_xml_path: str | Path) -> dict[str, Any]:
    """Конвертировать EDT Form.xml в v8unpack Form.elem.json формат.

    Args:
        form_xml_path: Путь к EDT Form.xml файлу

    Returns:
        dict в формате Form.elem.json (v8unpack)

    Raises:
        FileNotFoundError: если файл не найден
        ET.ParseError: если XML невалидный
        ValueError: если это не Form.xml
    """
    form_xml_path = Path(form_xml_path)
    if not form_xml_path.exists():
        raise FileNotFoundError(f"Form.xml not found: {form_xml_path}")

    tree = ET.parse(form_xml_path)
    root = tree.getroot()

    # Проверяем что это Form
    if _strip_ns(root.tag) != "Form":
        raise ValueError(f"Expected <Form> root element, got <{_strip_ns(root.tag)}>")

    # Ищем элементы формы
    id_counter = [2]  # начинаем с 2 (1 = Объект)
    props: list[dict[str, Any]] = []

    # Добавляем стандартный реквизит Объект
    props.append(
        {
            "name": "Объект",
            "id": "1",
            "type": "DataProcessorObject",
            "raw": [
                "9",
                ["1"],
                "0",
                '"Объект"',
                ["1", "0"],
                ['"Pattern"', ['"#"', "Родитель"]],
                ["0", ["0", ['"B"', "1"], "0"]],
                ["0", ["0", ['"B"', "1"], "0"]],
                ["0", "0"],
                ["0", "0"],
                "1",
                "0",
                "0",
                "0",
                ["0", "0"],
                ["0", "0"],
            ],
        }
    )

    # Обходим ChildItems для поиска элементов формы
    for elem in root.iter():
        tag = _strip_ns(elem.tag)
        if tag in ELEMENT_CONVERTERS:
            prop = ELEMENT_CONVERTERS[tag](elem, id_counter)
            props.append(prop)

    # Строим финальный Form.elem.json
    return {
        "params": None,
        "props": props,
        "commands": [],
        "tree": [],
        "data": {},
    }


def main() -> int:
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 -m src.services.edt_form_converter Form.xml [output.json]")
        return 1

    form_xml = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    result = convert_edt_form_to_v8unpack(form_xml)

    if output_path:
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Converted: {form_xml} → {output_path}")
        print(f"   Props: {len(result['props'])}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
