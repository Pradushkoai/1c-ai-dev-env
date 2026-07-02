#!/usr/bin/env python3
"""
form_elem_builder.py — Универсальный генератор Form.elem.json (формат v8unpack).

Превращает человекочитаемое DSL-описание формы (Python dict / JSON) во
внутренний формат v8unpack Form.elem.json с правильными raw-структурами 1С.

Это решает проблему универсальности: EpfFactory.create_epf() принимает
form_spec как параметр, и для каждой задачи генерируется правильная форма
со статическими реквизитами (которые видит компилятор 1С).

DSL пример:
    {
      "props": [
        {"name": "Объект", "type": "DataProcessorObject"},
        {
          "name": "ТаблицаСписка",
          "type": "ValueTable",
          "synonym": "Список обходов",
          "columns": [
            {"name": "Дата", "type": "Date"},
            {"name": "Номер", "type": "String", "length": 50},
            {"name": "Ответственный", "type": "String", "length": 150},
            {"name": "Проведен", "type": "Boolean"},
            {"name": "Сумма", "type": "Number", "digits": 10, "fraction": 2}
          ]
        },
        {"name": "ДатаНачала", "type": "Date", "synonym": "Дата начала"},
        {"name": "Организация", "type": "CatalogRef", "catalog": "Организации"}
      ]
    }

Поддерживаемые типы реквизитов:
  - DataProcessorObject  — Объект обработки (обязательный, обычно id=1)
  - ValueTable           — Таблица значений с колонками
  - Date                 — Дата (с квалификаторами DateFractions)
  - String               — Строка (с длиной)
  - Number               — Число (digits/fraction)
  - Boolean              — Булево
  - CatalogRef           — СправочникСсылка.<catalog>
  - DocumentRef          — ДокументСсылка.<document>

Формат raw основан на Form.elem.template.json (из реального EPF).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Идентификатор типа "ТаблицаЗначений" во внутреннем формате 1С
# (взят из Form.elem.template.json, реквизит ПорядокОбхода)
VALUETABLE_TYPE_UUID = "acf6192e-81ca-46ef-93a6-5a6968b78663"

# Базовый raw-шаблон для реквизита (тип 9 = Attribute)
# Заполняется динамически в зависимости от типа данных.
# Структура: [type_id, [id], unused, name, synonym, pattern, save, load, ...]
_BASE_ATTR_RAW = [
    "9",          # type_id: Attribute
    None,         # [id] — заменить
    "0",          # unused
    None,         # name (в кавычках 1С)
    None,         # synonym: ["1", "1", ["\"ru\"", "\"...\""]] или ["1", "0"]
    None,         # pattern: ["\"Pattern\"", [...]]
    ["0", ["0", ["\"B\"", "1"], "0"]],   # save (стандартный)
    ["0", ["0", ["\"B\"", "1"], "0"]],   # load (стандартный)
    ["0", "0"],
    ["0", "0"],
    "0", "0", "0",
    "отдельно",   # code_in_separate_file
    ["0", "0"],
    ["0", "0"],
]


@dataclass
class FormElemColumn:
    """Колонка таблицы значений."""
    name: str
    type: str          # Date, String, Number, Boolean, CatalogRef, DocumentRef
    synonym: str = ""
    length: int = 0    # для String
    digits: int = 0    # для Number
    fraction: int = 0  # для Number
    catalog: str = ""  # для CatalogRef
    document: str = "" # для DocumentRef


@dataclass
class FormElemProp:
    """Реквизит формы."""
    name: str
    type: str          # DataProcessorObject, ValueTable, Date, String, Number, Boolean, CatalogRef, DocumentRef
    synonym: str = ""
    columns: list[FormElemColumn] = None  # для ValueTable
    length: int = 0
    digits: int = 0
    fraction: int = 0
    catalog: str = ""
    document: str = ""


# ─── Конструкторы Pattern (внутренний формат 1С) ─────────────────

def _pattern_date() -> list:
    """Pattern для типа Дата (с квалификатором ДатаВремя)."""
    return ["\"D\""]


def _pattern_string(length: int = 50) -> list:
    """Pattern для типа Строка(length, variable)."""
    return ["\"S\"", str(length), "1"]


def _pattern_number(digits: int = 10, fraction: int = 2) -> list:
    """Pattern для типа Число(digits, fraction, non-negative)."""
    return ["\"N\"", str(digits), str(fraction), "0"]


def _pattern_boolean() -> list:
    """Pattern для типа Булево."""
    return ["\"B\""]


def _pattern_catalog_ref(catalog_name: str) -> list:
    """Pattern для типа СправочникСсылка.<catalog_name>.

    В 1С используется идентификатор типа справочника, но в Form.elem.json
    часто встречается упрощённое представление через '#'.
    """
    return ["\"#\"", "Родитель"]  # упрощённо — будет уточнено через metadata


def _pattern_document_ref(document_name: str) -> list:
    """Pattern для типа ДокументСсылка.<document_name>."""
    return ["\"#\"", "Родитель"]


def _pattern_valuetable() -> list:
    """Pattern для типа ТаблицаЗначений (по UUID)."""
    return ["\"#\"", VALUETABLE_TYPE_UUID]


def _pattern_data_processor_object() -> list:
    """Pattern для типа Объект внешней обработки."""
    return ["\"#\"", "Родитель"]


def _build_pattern(prop: FormElemProp) -> list:
    """Построить Pattern по типу реквизита."""
    if prop.type == "DataProcessorObject":
        return _pattern_data_processor_object()
    if prop.type == "ValueTable":
        return _pattern_valuetable()
    if prop.type == "Date":
        return _pattern_date()
    if prop.type == "String":
        return _pattern_string(prop.length or 50)
    if prop.type == "Number":
        return _pattern_number(prop.digits or 10, prop.fraction or 0)
    if prop.type == "Boolean":
        return _pattern_boolean()
    if prop.type == "CatalogRef":
        return _pattern_catalog_ref(prop.catalog)
    if prop.type == "DocumentRef":
        return _pattern_document_ref(prop.document)
    raise ValueError(f"Неизвестный тип реквизита: {prop.type}")


# ─── Конструкторы raw-структур ────────────────────────────────────

def _make_synonym(synonym: str) -> list:
    """Синоним в формате 1С: ["1", "1", ["\"ru\"", "\"<text>\""]] или ["1", "0"]."""
    if not synonym:
        return ["1", "0"]
    return ["1", "1", ["\"ru\"", f"\"{synonym}\""]]


def _make_attr_raw(prop: FormElemProp, prop_id: int) -> list:
    """Построить raw для реквизита (тип 9 = Attribute)."""
    raw = list(_BASE_ATTR_RAW)
    raw[1] = [str(prop_id)]
    raw[3] = f"\"{prop.name}\""
    raw[4] = _make_synonym(prop.synonym)
    raw[5] = ["\"Pattern\"", _build_pattern(prop)]
    return raw


def _make_column_raw(col: FormElemColumn, col_id: int) -> dict:
    """Построить raw для колонки таблицы значений (тип 5 = Column).

    Структура проще, чем у Attribute: [type_id, id, unused, name, synonym, pattern, ...]
    """
    col_prop = FormElemProp(
        name=col.name,
        type=col.type,
        synonym=col.synonym,
        length=col.length,
        digits=col.digits,
        fraction=col.fraction,
        catalog=col.catalog,
        document=col.document,
    )
    return {
        "name": col.name,
        "id": str(col_id),
        "raw": [
            "5",                  # type_id: Column (вложенный элемент)
            str(col_id),          # ID колонки
            "0",
            f"\"{col.name}\"",
            _make_synonym(col.synonym),
            ["\"Pattern\"", _build_pattern(col_prop)],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", "0"],
            "0"
        ]
    }


def _make_valuetable_prop(prop: FormElemProp, prop_id: int) -> dict:
    """Построить полный реквизит ТаблицыЗначений с колонками."""
    raw = _make_attr_raw(prop, prop_id)
    columns_json = []
    for i, col in enumerate(prop.columns or [], start=1):
        columns_json.append(_make_column_raw(col, i))
    return {
        "name": prop.name,
        "id": str(prop_id),
        "raw": raw,
        "child": columns_json,
    }


def _make_simple_prop(prop: FormElemProp, prop_id: int) -> dict:
    """Построить простой реквизит (Date, String, Number, Boolean, Reference)."""
    return {
        "name": prop.name,
        "id": str(prop_id),
        "raw": _make_attr_raw(prop, prop_id),
    }


# ─── Главная функция ─────────────────────────────────────────────

def build_form_elem(form_spec: dict, base_template_path: str | Path | None = None) -> dict:
    """Построить Form.elem.json (формат v8unpack) из DSL-описания.

    Args:
        form_spec: dict с ключом "props" — список описаний реквизитов.
            Каждый реквизит:
              {"name": "...", "type": "...", "synonym": "...", ...}
        base_template_path: путь к Form.elem.template.json (реальный EPF,
            извлечённый через v8unpack). Если задан — берётся как база,
            и новые реквизиты добавляются в конец props. Это даёт
            валидную для 1С структуру (template уже прошёл проверку 1С).
            Если None — генерируется с нуля (пустая форма).

    Returns:
        dict в формате v8unpack Form.elem.json

    Важно: при base_template_path=None форма может быть невалидной для 1С
    (v8unpack неправильно сериализует пустую форму). Используйте
    base_template_path для реальных EPF.
    """
    if base_template_path is not None:
        # Загружаем template как базу
        import json as _json
        with open(base_template_path, encoding="utf-8") as f:
            base = _json.load(f)

        # Добавляем новые реквизиты в конец props
        props_spec = form_spec.get("props", [])
        existing_names = {p["name"] for p in base.get("props", [])}
        next_id = max([int(p["id"]) for p in base.get("props", []) if p.get("id", "0").isdigit()] + [0]) + 1

        for prop_spec in props_spec:
            prop = _parse_prop_spec(prop_spec)
            if prop.name in existing_names:
                continue  # пропускаем дубликаты (например, Объект)
            if prop.type == "ValueTable":
                base["props"].append(_make_valuetable_prop(prop, next_id))
            else:
                base["props"].append(_make_simple_prop(prop, next_id))
            next_id += 1

        return base

    # Без template — генерируем с нуля (старое поведение)
    props_spec = form_spec.get("props", [])
    if not props_spec:
        # Если не задан — добавляем только Объект (обязательный)
        props_spec = [{"name": "Объект", "type": "DataProcessorObject"}]

    props_json = []
    for i, prop_spec in enumerate(props_spec, start=1):
        prop = _parse_prop_spec(prop_spec)
        if prop.type == "ValueTable":
            props_json.append(_make_valuetable_prop(prop, i))
        else:
            props_json.append(_make_simple_prop(prop, i))

    return {
        "params": None,
        "props": props_json,
        "commands": [],
        "tree": [],
        "data": {}
    }


def _parse_prop_spec(spec: dict) -> FormElemProp:
    """Распарсить описание реквизита из DSL в FormElemProp."""
    name = spec.get("name")
    if not name:
        raise ValueError("Реквизит должен иметь name")

    type_ = spec.get("type", "String")
    columns = None
    if type_ == "ValueTable":
        columns = [
            FormElemColumn(
                name=c.get("name", ""),
                type=c.get("type", "String"),
                synonym=c.get("synonym", ""),
                length=c.get("length", 0),
                digits=c.get("digits", 0),
                fraction=c.get("fraction", 0),
                catalog=c.get("catalog", ""),
                document=c.get("document", ""),
            )
            for c in spec.get("columns", [])
        ]

    return FormElemProp(
        name=name,
        type=type_,
        synonym=spec.get("synonym", ""),
        columns=columns,
        length=spec.get("length", 0),
        digits=spec.get("digits", 0),
        fraction=spec.get("fraction", 0),
        catalog=spec.get("catalog", ""),
        document=spec.get("document", ""),
    )


def build_and_save_form_elem(form_spec: dict, output_path: Path) -> dict:
    """Построить Form.elem.json и сохранить в файл.

    Args:
        form_spec: DSL-описание формы
        output_path: куда сохранить

    Returns:
        Сгенерированный Form.elem.json (dict)
    """
    form_elem = build_form_elem(form_spec)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(form_elem, f, ensure_ascii=False, indent=2)
    return form_elem


# ─── CLI ─────────────────────────────────────────────────────────

def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Универсальный генератор Form.elem.json из DSL",
    )
    parser.add_argument("--spec", required=True, help="Путь к JSON-файлу с DSL описанием формы")
    parser.add_argument("--output", required=True, help="Путь к выходному Form.elem.json")
    args = parser.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        form_spec = json.load(f)

    form_elem = build_and_save_form_elem(form_spec, Path(args.output))

    print(f"✅ Form.elem.json создан: {args.output}")
    print(f"   Размер: {Path(args.output).stat().st_size} байт")
    print(f"   Реквизитов: {len(form_elem['props'])}")
    for p in form_elem['props']:
        cols = len(p.get('child', []))
        type_str = "ValueTable" if cols > 0 else "simple"
        print(f"   - {p['name']} (id={p['id']}, {type_str}, колонок={cols})")


if __name__ == "__main__":
    _cli()
