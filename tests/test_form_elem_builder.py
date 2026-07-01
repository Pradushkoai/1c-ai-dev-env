"""
Тесты для form_elem_builder.py — генератора Form.elem.json из DSL.

Проверяет:
  1. Создание формы с пустым DSL (только Объект)
  2. Создание формы с ТаблицаЗначений и колонками
  3. Различные типы данных (Date, String, Number, Boolean)
  4. Обработка некорректных типов
  5. Генерация и сохранение в файл

Запуск:
  pytest tests/test_form_elem_builder.py -v
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.services.form_elem_builder import (
    build_form_elem,
    build_and_save_form_elem,
    FormElemProp,
    FormElemColumn,
    _pattern_date,
    _pattern_string,
    _pattern_number,
    _pattern_boolean,
    _pattern_valuetable,
    VALUETABLE_TYPE_UUID,
)


def test_empty_form_spec_returns_default_object_prop():
    """Пустой DSL возвращает форму с одним реквизитом Объект."""
    form_elem = build_form_elem({})

    assert form_elem["params"] is None
    assert len(form_elem["props"]) == 1
    assert form_elem["props"][0]["name"] == "Объект"
    assert form_elem["props"][0]["id"] == "1"
    assert form_elem["commands"] == []
    assert form_elem["tree"] == []
    assert form_elem["data"] == {}


def test_form_with_valuetable_and_columns():
    """Форма с ТаблицаЗначений и 3 колонками."""
    form_spec = {
        "props": [
            {"name": "Объект", "type": "DataProcessorObject"},
            {
                "name": "ТаблицаСписка",
                "type": "ValueTable",
                "synonym": "Список обходов",
                "columns": [
                    {"name": "Дата", "type": "Date"},
                    {"name": "Номер", "type": "String", "length": 50},
                    {"name": "Проведен", "type": "Boolean"},
                ]
            }
        ]
    }
    form_elem = build_form_elem(form_spec)

    assert len(form_elem["props"]) == 2
    assert form_elem["props"][0]["name"] == "Объект"
    assert form_elem["props"][1]["name"] == "ТаблицаСписка"
    assert form_elem["props"][1]["id"] == "2"

    # Колонки
    columns = form_elem["props"][1].get("child", [])
    assert len(columns) == 3
    assert columns[0]["name"] == "Дата"
    assert columns[1]["name"] == "Номер"
    assert columns[2]["name"] == "Проведен"


def test_pattern_date():
    """Pattern для типа Дата."""
    assert _pattern_date() == ["\"D\""]


def test_pattern_string_with_length():
    """Pattern для типа Строка с длиной."""
    assert _pattern_string(50) == ["\"S\"", "50", "1"]
    assert _pattern_string(100) == ["\"S\"", "100", "1"]


def test_pattern_number_with_digits_and_fraction():
    """Pattern для типа Число."""
    assert _pattern_number(10, 2) == ["\"N\"", "10", "2", "0"]
    assert _pattern_number(15, 0) == ["\"N\"", "15", "0", "0"]


def test_pattern_boolean():
    """Pattern для типа Булево."""
    assert _pattern_boolean() == ["\"B\""]


def test_pattern_valuetable_uses_correct_uuid():
    """Pattern для ТаблицыЗначений использует правильный UUID."""
    pattern = _pattern_valuetable()
    assert pattern[0] == "\"#\""
    assert pattern[1] == VALUETABLE_TYPE_UUID
    assert pattern[1] == "acf6192e-81ca-46ef-93a6-5a6968b78663"


def test_unknown_type_raises_error():
    """Неизвестный тип реквизита вызывает ValueError."""
    form_spec = {
        "props": [
            {"name": "Test", "type": "UnknownType"}
        ]
    }
    with pytest.raises(ValueError, match="Неизвестный тип реквизита"):
        build_form_elem(form_spec)


def test_prop_without_name_raises_error():
    """Реквизит без name вызывает ValueError."""
    form_spec = {
        "props": [
            {"type": "Date"}
        ]
    }
    with pytest.raises(ValueError, match="должен иметь name"):
        build_form_elem(form_spec)


def test_build_and_save_form_elem_creates_file(tmp_path):
    """build_and_save_form_elem сохраняет файл в правильном формате."""
    form_spec = {
        "props": [
            {"name": "Объект", "type": "DataProcessorObject"},
            {"name": "ДатаНачала", "type": "Date", "synonym": "Дата начала"}
        ]
    }
    output = tmp_path / "Form.elem.json"
    form_elem = build_and_save_form_elem(form_spec, output)

    assert output.exists()
    with open(output, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == form_elem
    assert len(loaded["props"]) == 2


def test_valuetable_prop_has_correct_raw_structure():
    """ТаблицаЗначений имеет raw-структуру с правильным Pattern."""
    form_spec = {
        "props": [
            {"name": "Объект", "type": "DataProcessorObject"},
            {
                "name": "Таблица",
                "type": "ValueTable",
                "columns": [
                    {"name": "Кол1", "type": "String", "length": 10}
                ]
            }
        ]
    }
    form_elem = build_form_elem(form_spec)
    table_prop = form_elem["props"][1]

    # raw[5] — Pattern
    assert table_prop["raw"][5][0] == "\"Pattern\""
    assert table_prop["raw"][5][1][0] == "\"#\""
    assert table_prop["raw"][5][1][1] == VALUETABLE_TYPE_UUID


def test_column_has_correct_pattern():
    """Колонка с типом Date имеет Pattern ['D']."""
    form_spec = {
        "props": [
            {"name": "Объект", "type": "DataProcessorObject"},
            {
                "name": "Таблица",
                "type": "ValueTable",
                "columns": [
                    {"name": "ДатаКолонки", "type": "Date"}
                ]
            }
        ]
    }
    form_elem = build_form_elem(form_spec)
    column = form_elem["props"][1]["child"][0]

    # raw[5] — Pattern
    assert column["raw"][5] == ["\"Pattern\"", ["\"D\""]]


def test_multiple_simple_props():
    """Несколько простых реквизитов разных типов."""
    form_spec = {
        "props": [
            {"name": "Объект", "type": "DataProcessorObject"},
            {"name": "ДатаНачала", "type": "Date", "synonym": "Дата начала"},
            {"name": "Комментарий", "type": "String", "length": 200, "synonym": "Комментарий"},
            {"name": "Сумма", "type": "Number", "digits": 15, "fraction": 2, "synonym": "Сумма"},
            {"name": "Флаг", "type": "Boolean", "synonym": "Флаг"}
        ]
    }
    form_elem = build_form_elem(form_spec)

    assert len(form_elem["props"]) == 5
    assert form_elem["props"][0]["name"] == "Объект"
    assert form_elem["props"][1]["name"] == "ДатаНачала"
    assert form_elem["props"][2]["name"] == "Комментарий"
    assert form_elem["props"][3]["name"] == "Сумма"
    assert form_elem["props"][4]["name"] == "Флаг"

    # ID должны идти по порядку
    for i, prop in enumerate(form_elem["props"], start=1):
        assert prop["id"] == str(i)


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
