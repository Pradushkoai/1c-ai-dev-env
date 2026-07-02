"""
Тесты для src/services/edt_form_converter.py — EDT Form.xml → v8unpack конвертер.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.edt_form_converter import convert_edt_form_to_v8unpack


def _create_form_xml(elements_xml: str = "") -> str:
    """Создать тестовый Form.xml с указанными элементами."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Properties>
    <Name>Форма</Name>
  </Properties>
  <ChildItems>
{elements_xml}
  </ChildItems>
</Form>"""


@pytest.fixture
def simple_form_xml(tmp_path: Path) -> Path:
    """Form.xml с одним InputField."""
    xml = _create_form_xml(
        """    <InputField>
      <Name>ИмяКлиента</Name>
      <Title>Имя клиента</Title>
      <DataPath>Объект.ИмяКлиента</DataPath>
    </InputField>"""
    )
    path = tmp_path / "Form.xml"
    path.write_text(xml, encoding="utf-8")
    return path


@pytest.fixture
def complex_form_xml(tmp_path: Path) -> Path:
    """Form.xml с несколькими элементами."""
    xml = _create_form_xml(
        """    <InputField>
      <Name>ИмяКлиента</Name>
      <Title>Имя клиента</Title>
      <DataPath>Объект.ИмяКлиента</DataPath>
    </InputField>
    <Button>
      <Name>КнопкаОК</Name>
      <Title>ОК</Title>
      <CommandName>Объект.ОК</CommandName>
    </Button>
    <Label>
      <Name>Подсказка</Name>
      <Title>Введите данные</Title>
    </Label>
    <CheckBox>
      <Name>ФлагАктивности</Name>
      <Title>Активен</Title>
      <DataPath>Объект.Активен</DataPath>
    </CheckBox>"""
    )
    path = tmp_path / "Form.xml"
    path.write_text(xml, encoding="utf-8")
    return path


@pytest.fixture
def table_form_xml(tmp_path: Path) -> Path:
    """Form.xml с таблицей."""
    xml = _create_form_xml(
        """    <Table>
      <Name>ТаблицаТоваров</Name>
      <Title>Товары</Title>
      <DataPath>Объект.Товары</DataPath>
      <Columns>
        <Column>
          <Name>Номенклатура</Name>
          <Title>Номенклатура</Title>
          <DataPath>Объект.Товары.Номенклатура</DataPath>
        </Column>
        <Column>
          <Name>Количество</Name>
          <Title>Количество</Title>
          <DataPath>Объект.Товары.Количество</DataPath>
        </Column>
      </Columns>
    </Table>"""
    )
    path = tmp_path / "Form.xml"
    path.write_text(xml, encoding="utf-8")
    return path


# ─── Базовые тесты ───


class TestConvertBasic:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            convert_edt_form_to_v8unpack("/nonexistent/Form.xml")

    def test_invalid_xml(self, tmp_path: Path):
        path = tmp_path / "Form.xml"
        path.write_text("not valid xml", encoding="utf-8")
        import xml.etree.ElementTree as ET

        with pytest.raises(ET.ParseError):
            convert_edt_form_to_v8unpack(path)

    def test_not_form_element(self, tmp_path: Path):
        path = tmp_path / "Form.xml"
        path.write_text('<?xml version="1.0"?><Catalog xmlns="http://v8.1c.ru/8.3/MDClasses"/>', encoding="utf-8")
        with pytest.raises(ValueError, match="Expected <Form>"):
            convert_edt_form_to_v8unpack(path)

    def test_empty_form(self, tmp_path: Path):
        """Пустая форма — только реквизит Объект."""
        path = tmp_path / "Form.xml"
        path.write_text(_create_form_xml(), encoding="utf-8")
        result = convert_edt_form_to_v8unpack(path)
        assert result["params"] is None
        assert len(result["props"]) == 1  # только Объект
        assert result["props"][0]["name"] == "Объект"
        assert result["commands"] == []
        assert result["tree"] == []


# ─── InputField ───


class TestInputField:
    def test_single_input_field(self, simple_form_xml: Path):
        result = convert_edt_form_to_v8unpack(simple_form_xml)
        # Объект + InputField = 2 props
        assert len(result["props"]) == 2
        field = result["props"][1]
        assert field["name"] == "ИмяКлиента"
        assert field["type"] == "InputField"
        assert field["title"] == "Имя клиента"
        assert field["data_path"] == "Объект.ИмяКлиента"
        assert field["id"] == "2"
        assert "raw" in field

    def test_input_field_has_raw_structure(self, simple_form_xml: Path):
        result = convert_edt_form_to_v8unpack(simple_form_xml)
        field = result["props"][1]
        raw = field["raw"]
        assert isinstance(raw, list)
        assert raw[0] == "9"  # v8unpack magic


# ─── Multiple elements ───


class TestMultipleElements:
    def test_multiple_elements(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        # Объект + InputField + Button + Label + CheckBox = 5 props
        assert len(result["props"]) == 5

        types = [p["type"] for p in result["props"]]
        assert "DataProcessorObject" in types
        assert "InputField" in types
        assert "Button" in types
        assert "Label" in types
        assert "CheckBox" in types

    def test_button_has_command_name(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        button = next(p for p in result["props"] if p["type"] == "Button")
        assert button["name"] == "КнопкаОК"
        assert button["title"] == "ОК"
        assert button["command_name"] == "Объект.ОК"

    def test_label_has_title(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        label = next(p for p in result["props"] if p["type"] == "Label")
        assert label["name"] == "Подсказка"
        assert label["title"] == "Введите данные"

    def test_checkbox_has_data_path(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        checkbox = next(p for p in result["props"] if p["type"] == "CheckBox")
        assert checkbox["name"] == "ФлагАктивности"
        assert checkbox["data_path"] == "Объект.Активен"

    def test_unique_ids(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        ids = [p["id"] for p in result["props"]]
        assert len(ids) == len(set(ids))  # все уникальны


# ─── Table ───


class TestTable:
    def test_table_with_columns(self, table_form_xml: Path):
        result = convert_edt_form_to_v8unpack(table_form_xml)
        # Объект + Table = 2 props
        assert len(result["props"]) == 2
        table = result["props"][1]
        assert table["type"] == "Table"
        assert table["name"] == "ТаблицаТоваров"
        assert table["title"] == "Товары"
        assert table["data_path"] == "Объект.Товары"
        assert len(table["columns"]) == 2
        assert table["columns"][0]["name"] == "Номенклатура"
        assert table["columns"][1]["name"] == "Количество"


# ─── V8unpack format ───


class TestV8UnpackFormat:
    def test_result_is_json_serializable(self, simple_form_xml: Path):
        result = convert_edt_form_to_v8unpack(simple_form_xml)
        # Должен быть сериализуемым в JSON
        json_str = json.dumps(result, ensure_ascii=False)
        assert json.loads(json_str) == result

    def test_has_required_v8unpack_keys(self, simple_form_xml: Path):
        result = convert_edt_form_to_v8unpack(simple_form_xml)
        assert "params" in result
        assert "props" in result
        assert "commands" in result
        assert "tree" in result
        assert "data" in result

    def test_object_prop_always_first(self, complex_form_xml: Path):
        result = convert_edt_form_to_v8unpack(complex_form_xml)
        assert result["props"][0]["name"] == "Объект"
        assert result["props"][0]["id"] == "1"
