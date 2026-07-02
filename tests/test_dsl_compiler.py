"""
Тесты для DslCompiler — JSON DSL → XML компиляторы для 1С.

3 компилятора:
1. MetaCompiler — метаданные 1С (23 типа объектов)
2. FormCompiler — управляемые формы (Form.xml)
3. SkdCompiler — схемы компоновки данных (СКД)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.services.dsl_compiler import (
    DslCompiler,
    MetaCompiler,
    FormCompiler,
    SkdCompiler,
    CompileResult,
    TYPE_MAP,
    RU_TYPE_SYNONYMS,
    _camel_to_words,
    _normalize_type,
    _normalize_object_type,
    _parse_attribute,
)


# ─────────────────────────────────────────────
# Утилиты tests
# ─────────────────────────────────────────────


def _parse_xml(path: Path) -> ET.Element:
    """Прочитать XML и вернуть root."""
    tree = ET.parse(path)
    return tree.getroot()


def _find_tag(root: ET.Element, tag: str) -> ET.Element | None:
    """Найти тег без namespace."""
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local == tag:
            return elem
    return None


def _find_all_tags(root: ET.Element, tag: str) -> list[ET.Element]:
    """Найти все теги без namespace."""
    result = []
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local == tag:
            result.append(elem)
    return result


# ─────────────────────────────────────────────
# Утилиты — тесты
# ─────────────────────────────────────────────


class TestCamelToWords:
    """Тесты автогенерации синонимов из CamelCase."""

    def test_russian_camelcase(self):
        assert _camel_to_words("АвансовыйОтчет") == "Авансовый отчет"

    def test_russian_with_numbers(self):
        assert _camel_to_words("НДС20") == "НДС20"

    def test_english_camelcase(self):
        assert _camel_to_words("IncomingDocument") == "Incoming document"


class TestNormalizeType:
    """Тесты нормализации типов данных."""

    def test_russian_string(self):
        assert _normalize_type("Строка") == "String"

    def test_russian_number(self):
        assert _normalize_type("Число") == "Number"

    def test_russian_catalog_ref(self):
        assert _normalize_type("СправочникСсылка.Товары") == "CatalogRef.Товары"

    def test_english_passthrough(self):
        assert _normalize_type("String(100)") == "String(100)"

    def test_empty_returns_string(self):
        assert _normalize_type("") == "String"


class TestNormalizeObjectType:
    """Тесты нормализации типов объектов."""

    def test_english_passthrough(self):
        assert _normalize_object_type("Catalog") == "Catalog"

    def test_russian_synonym(self):
        assert _normalize_object_type("Справочник") == "Catalog"

    def test_russian_with_yo(self):
        assert _normalize_object_type("Отчёт") == "Report"
        assert _normalize_object_type("Отчет") == "Report"


class TestParseAttribute:
    """Тесты разбора определения реквизита."""

    def test_string_form_simple(self):
        attr = _parse_attribute("Имя")
        assert attr["name"] == "Имя"
        assert attr["type"] == "String"

    def test_string_form_with_type(self):
        attr = _parse_attribute("Цена: Number(15,2)")
        assert attr["name"] == "Цена"
        assert "Number" in attr["type"]

    def test_string_form_with_flags(self):
        attr = _parse_attribute("Контрагент: CatalogRef.Контрагенты | req, index")
        assert attr["name"] == "Контрагент"
        assert attr["fillChecking"] == "ShowError"
        assert attr["indexing"] == "Index"

    def test_dict_form(self):
        attr = _parse_attribute(
            {
                "name": "Сумма",
                "type": "Number(15,2)",
                "synonym": "Сумма документа",
            }
        )
        assert attr["name"] == "Сумма"
        assert attr["synonym"] == "Сумма документа"

    def test_russian_type_in_shorthand(self):
        attr = _parse_attribute("Количество: Число(10,3)")
        assert attr["name"] == "Количество"
        assert "Number" in attr["type"]


# ─────────────────────────────────────────────
# MetaCompiler tests
# ─────────────────────────────────────────────


class TestMetaCompiler:
    """Тесты компилятора метаданных."""

    def test_compile_catalog_basic(self, tmp_path):
        """Базовая компиляция справочника."""
        compiler = MetaCompiler()
        result = compiler.compile(
            {
                "type": "Catalog",
                "name": "Товары",
                "synonym": "Номенклатура",
            },
            tmp_path,
        )

        assert result.object_type == "Catalog"
        assert result.object_name == "Товары"
        assert result.xml_path is not None
        assert result.xml_path.exists()
        # Должен быть создан ObjectModule.bsl
        assert len(result.module_paths) >= 1

    def test_compile_creates_xml_with_correct_root(self, tmp_path):
        """XML имеет корневой элемент Catalog."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Catalog", "name": "Товары"}, tmp_path)

        root = _parse_xml(result.xml_path)
        local_tag = root.tag.split("}")[-1]
        assert local_tag == "Catalog"

    def test_compile_synonym_in_xml(self, tmp_path):
        """Синоним записан в XML."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Catalog", "name": "Товары", "synonym": "Номенклатура"}, tmp_path)

        root = _parse_xml(result.xml_path)
        # Ищем Synonym → item → content
        contents = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "content":
                contents.append(elem.text)
        assert "Номенклатура" in contents

    def test_compile_auto_synonym_from_camelcase(self, tmp_path):
        """Синоним автогенерируется из CamelCase если не указан."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Catalog", "name": "АвансовыйОтчет"}, tmp_path)

        root = _parse_xml(result.xml_path)
        contents = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "content":
                contents.append(elem.text)
        assert "Авансовый отчет" in contents

    def test_compile_attributes(self, tmp_path):
        """Реквизиты добавлены в ChildObjects."""
        compiler = MetaCompiler()
        result = compiler.compile(
            {
                "type": "Catalog",
                "name": "Товары",
                "attributes": [
                    "Артикул: String(50)",
                    "Цена: Number(15,2) | req",
                ],
            },
            tmp_path,
        )

        root = _parse_xml(result.xml_path)
        attrs = _find_all_tags(root, "Attribute")
        assert len(attrs) == 2

    def test_compile_tabular_sections(self, tmp_path):
        """Табличные части добавлены."""
        compiler = MetaCompiler()
        result = compiler.compile(
            {
                "type": "Catalog",
                "name": "Товары",
                "tabularSections": {
                    "Характеристики": [
                        "Имя: String(100)",
                        "Значение: String(200)",
                    ],
                },
            },
            tmp_path,
        )

        root = _parse_xml(result.xml_path)
        ts = _find_all_tags(root, "TabularSection")
        assert len(ts) == 1

    def test_compile_enum_values(self, tmp_path):
        """Значения перечисления добавлены."""
        compiler = MetaCompiler()
        result = compiler.compile(
            {
                "type": "Enum",
                "name": "ВидыОплат",
                "values": ["Приход", "Расход"],
            },
            tmp_path,
        )

        root = _parse_xml(result.xml_path)
        values = _find_all_tags(root, "EnumValue")
        assert len(values) == 2

    def test_compile_document(self, tmp_path):
        """Компиляция документа."""
        compiler = MetaCompiler()
        result = compiler.compile(
            {
                "type": "Document",
                "name": "ПоступлениеТоваров",
                "attributes": ["Контрагент: CatalogRef.Контрагенты | req"],
            },
            tmp_path,
        )

        assert result.object_type == "Document"
        root = _parse_xml(result.xml_path)
        local_tag = root.tag.split("}")[-1]
        assert local_tag == "Document"

    def test_compile_constant(self, tmp_path):
        """Компиляция константы."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Constant", "name": "ОсновнаяВалюта", "valueType": "String"}, tmp_path)

        assert result.object_type == "Constant"
        assert result.xml_path.exists()

    def test_compile_russian_type_synonym(self, tmp_path):
        """Русский синоним типа объекта."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Справочник", "name": "Товары"}, tmp_path)

        assert result.object_type == "Catalog"

    def test_compile_unsupported_type_raises(self, tmp_path):
        """Неподдерживаемый тип → ValueError."""
        compiler = MetaCompiler()
        with pytest.raises(ValueError):
            compiler.compile({"type": "UnknownType", "name": "X"}, tmp_path)

    def test_compile_missing_name_raises(self, tmp_path):
        """Отсутствует name → ValueError."""
        compiler = MetaCompiler()
        with pytest.raises(ValueError):
            compiler.compile({"type": "Catalog"}, tmp_path)

    def test_compile_from_json_string(self, tmp_path):
        """Компиляция из JSON-строки."""
        compiler = MetaCompiler()
        json_str = json.dumps({"type": "Catalog", "name": "Товары"})
        result = compiler.compile(json_str, tmp_path)

        assert result.object_name == "Товары"
        assert result.xml_path.exists()

    def test_compile_from_json_file(self, tmp_path):
        """Компиляция из JSON-файла."""
        compiler = MetaCompiler()
        json_file = tmp_path / "def.json"
        json_file.write_text(json.dumps({"type": "Catalog", "name": "Товары"}), encoding="utf-8")
        result = compiler.compile(json_file, tmp_path)

        assert result.object_name == "Товары"
        assert result.xml_path.exists()

    def test_compile_registers_in_config(self, tmp_path):
        """Объект регистрируется в Configuration.xml если он существует."""
        # Создаём минимальный Configuration.xml
        config_xml = tmp_path / "Configuration.xml"
        config_xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses">\n'
            "  <md:ChildObjects/>\n"
            "</md:Configuration>\n",
            encoding="utf-8",
        )

        compiler = MetaCompiler()
        result = compiler.compile({"type": "Catalog", "name": "Товары"}, tmp_path)

        assert result.registered_in_config is True

        # Проверяем что в Configuration.xml появился тег <Catalog>Товары</Catalog>
        root = _parse_xml(config_xml)
        found = False
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "Catalog" and elem.text == "Товары":
                found = True
                break
        assert found

    def test_compile_creates_object_module(self, tmp_path):
        """Для Catalog создаётся ObjectModule.bsl."""
        compiler = MetaCompiler()
        result = compiler.compile({"type": "Catalog", "name": "Товары"}, tmp_path)

        # Путь: Catalogs/Товары/Ext/ObjectModule.bsl
        module_path = tmp_path / "Catalogs" / "Товары" / "Ext" / "ObjectModule.bsl"
        assert module_path.exists()
        assert module_path in result.module_paths

    def test_compile_object_module_has_regions(self, tmp_path):
        """ObjectModule.bsl содержит стандартные области 1С."""
        compiler = MetaCompiler()
        compiler.compile({"type": "Catalog", "name": "Товары"}, tmp_path)

        module_path = tmp_path / "Catalogs" / "Товары" / "Ext" / "ObjectModule.bsl"
        content = module_path.read_text(encoding="utf-8")
        assert "#Область ПрограммныйИнтерфейс" in content
        assert "#Область СлужебныйПрограммныйИнтерфейс" in content
        assert "#Область СлужебныеПроцедурыИФункции" in content


# ─────────────────────────────────────────────
# FormCompiler tests
# ─────────────────────────────────────────────


class TestFormCompiler:
    """Тесты компилятора форм."""

    def test_compile_form_basic(self, tmp_path):
        """Базовая компиляция формы."""
        compiler = FormCompiler()
        result = compiler.compile({"name": "ФормаЭлемента", "synonym": "Форма элемента"}, tmp_path / "Form.xml")

        assert result.object_type == "Form"
        assert result.xml_path.exists()

    def test_compile_form_has_items(self, tmp_path):
        """Форма содержит элементы."""
        compiler = FormCompiler()
        result = compiler.compile(
            {
                "name": "ФормаЭлемента",
                "items": [
                    {"type": "InputField", "name": "Артикул", "dataPath": "Объект.Артикул"},
                    {"type": "Button", "name": "Сохранить"},
                ],
            },
            tmp_path / "Form.xml",
        )

        root = _parse_xml(result.xml_path)
        # Должны быть InputField и Button
        input_fields = _find_all_tags(root, "InputField")
        buttons = _find_all_tags(root, "Button")
        assert len(input_fields) >= 1
        assert len(buttons) >= 1

    def test_compile_form_with_nested_items(self, tmp_path):
        """Форма с вложенными элементами (группа с детьми)."""
        compiler = FormCompiler()
        result = compiler.compile(
            {
                "name": "ФормаЭлемента",
                "items": [
                    {
                        "type": "Group",
                        "name": "ГруппаШапка",
                        "children": [
                            {"type": "InputField", "name": "Наименование"},
                        ],
                    },
                ],
            },
            tmp_path / "Form.xml",
        )

        root = _parse_xml(result.xml_path)
        groups = _find_all_tags(root, "Group")
        assert len(groups) >= 1


# ─────────────────────────────────────────────
# SkdCompiler tests
# ─────────────────────────────────────────────


class TestSkdCompiler:
    """Тесты компилятора СКД."""

    def test_compile_skd_basic(self, tmp_path):
        """Базовая компиляция СКД."""
        compiler = SkdCompiler()
        result = compiler.compile(
            {
                "name": "ОсновнаяСхема",
                "dataSets": [
                    {
                        "name": "Продажи",
                        "type": "query",
                        "query": "ВЫБРАТЬ * ИЗ Документ.Продажа",
                        "fields": [
                            {"path": "Сумма", "title": "Сумма"},
                        ],
                    },
                ],
            },
            tmp_path / "Template.xml",
        )

        assert result.object_type == "DataCompositionSchema"
        assert result.xml_path.exists()

    def test_compile_skd_has_data_sources(self, tmp_path):
        """СКД имеет источники данных (auto если не указаны)."""
        compiler = SkdCompiler()
        result = compiler.compile(
            {"dataSets": [{"name": "Данные", "type": "query", "query": "ВЫБРАТЬ 1"}]}, tmp_path / "Template.xml"
        )

        root = _parse_xml(result.xml_path)
        data_sources = _find_all_tags(root, "dataSource")
        assert len(data_sources) >= 1

    def test_compile_skd_calculated_fields(self, tmp_path):
        """Вычисляемые поля добавлены."""
        compiler = SkdCompiler()
        result = compiler.compile(
            {
                "dataSets": [{"name": "Данные", "type": "query", "query": "ВЫБРАТЬ 1"}],
                "calculatedFields": [
                    {"path": "СуммаНДС", "expression": "Сумма * 0.2"},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        calc_fields = _find_all_tags(root, "calculatedField")
        assert len(calc_fields) >= 1

    def test_compile_skd_total_fields(self, tmp_path):
        """Итоговые поля (ресурсы) добавлены."""
        compiler = SkdCompiler()
        result = compiler.compile(
            {
                "dataSets": [{"name": "Данные", "type": "query", "query": "ВЫБРАТЬ 1"}],
                "totalFields": [
                    {"path": "Сумма", "expression": "СУММА(Сумма)", "group": "Контрагент"},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        total_fields = _find_all_tags(root, "totalField")
        assert len(total_fields) >= 1

    def test_compile_skd_parameters(self, tmp_path):
        """Параметры СКД добавлены."""
        compiler = SkdCompiler()
        result = compiler.compile(
            {
                "dataSets": [{"name": "Данные", "type": "query", "query": "ВЫБРАТЬ 1"}],
                "parameters": [
                    {"name": "ДатаНачала", "type": "Date", "title": "Дата начала"},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        params = _find_all_tags(root, "parameter")
        assert len(params) >= 1


# ─────────────────────────────────────────────
# DslCompiler facade tests
# ─────────────────────────────────────────────


class TestDslCompilerFacade:
    """Тесты фасада DslCompiler."""

    def test_facade_has_all_compilers(self):
        """Фасад имеет все 3 компилятора."""
        compiler = DslCompiler()
        assert hasattr(compiler, "meta")
        assert hasattr(compiler, "form")
        assert hasattr(compiler, "skd")

    def test_facade_compile_meta(self, tmp_path):
        """Фасад компилирует meta."""
        compiler = DslCompiler()
        result = compiler.compile_meta({"type": "Catalog", "name": "Товары"}, tmp_path)
        assert result.object_type == "Catalog"

    def test_facade_compile_form(self, tmp_path):
        """Фасад компилирует form."""
        compiler = DslCompiler()
        result = compiler.compile_form({"name": "Форма"}, tmp_path / "Form.xml")
        assert result.object_type == "Form"

    def test_facade_compile_skd(self, tmp_path):
        """Фасад компилирует skd."""
        compiler = DslCompiler()
        result = compiler.compile_skd(
            {"dataSets": [{"name": "Д", "type": "query", "query": "ВЫБРАТЬ 1"}]}, tmp_path / "Template.xml"
        )
        assert result.object_type == "DataCompositionSchema"


# ─────────────────────────────────────────────
# TYPE_MAP tests
# ─────────────────────────────────────────────


class TestTypeMap:
    """Тесты маппинга типов."""

    def test_has_23_types(self):
        """TYPE_MAP содержит 23 типа объектов."""
        assert len(TYPE_MAP) == 23

    def test_has_key_types(self):
        """Ключевые типы присутствуют."""
        required = [
            "Catalog",
            "Document",
            "Enum",
            "Constant",
            "InformationRegister",
            "AccumulationRegister",
            "CommonModule",
            "Report",
            "DataProcessor",
        ]
        for t in required:
            assert t in TYPE_MAP

    def test_ru_synonyms_count(self):
        """Русские синонимы покрывают все типы."""
        assert len(RU_TYPE_SYNONYMS) >= 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ─────────────────────────────────────────────
# MxlCompiler tests
# ─────────────────────────────────────────────


class TestMxlCompiler:
    """Тесты компилятора MXL (табличные документы)."""

    def test_compile_mxl_basic(self, tmp_path):
        """Базовая компиляция MXL-макета."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 5,
                "defaultWidth": 20,
                "areas": [
                    {"name": "Заголовок", "rows": [{"cells": [{"col": 1, "span": 5, "text": "Печатная форма"}]}]},
                ],
            },
            tmp_path / "Template.xml",
        )

        assert result.object_type == "SpreadsheetDocument"
        assert result.xml_path.exists()

    def test_compile_mxl_has_columns(self, tmp_path):
        """MXL содержит колонки."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile({"columns": 3, "defaultWidth": 15}, tmp_path / "Template.xml")

        root = _parse_xml(result.xml_path)
        cols = _find_all_tags(root, "column")
        assert len(cols) == 3

    def test_compile_mxl_column_widths_dict(self, tmp_path):
        """columnWidths dict правильно парсится."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 5,
                "defaultWidth": 10,
                "columnWidths": {"1": 20, "2-4": 30, "5": 15},
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        cols = _find_all_tags(root, "column")
        widths = []
        for col in cols:
            w = _find_tag(col, "width")
            if w is not None:
                widths.append(int(w.text))
        assert widths == [20, 30, 30, 30, 15]

    def test_compile_mxl_fonts(self, tmp_path):
        """Шрифты добавляются в XML."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 3,
                "fonts": {
                    "default": {"face": "Arial", "size": 10},
                    "bold": {"face": "Arial", "size": 10, "bold": True},
                },
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        fonts = _find_all_tags(root, "font")
        assert len(fonts) == 2

    def test_compile_mxl_styles(self, tmp_path):
        """Стили добавляются."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 3,
                "styles": {
                    "header": {"font": "bold", "align": "center"},
                    "bordered": {"border": "all"},
                },
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        styles = _find_all_tags(root, "style")
        assert len(styles) == 2

    def test_compile_mxl_areas(self, tmp_path):
        """Области добавляются."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 3,
                "areas": [
                    {"name": "Заголовок", "rows": []},
                    {"name": "Шапка", "rows": []},
                    {"name": "Строка", "rows": []},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        areas = _find_all_tags(root, "area")
        assert len(areas) == 3

    def test_compile_mxl_cell_with_text(self, tmp_path):
        """Ячейка с text."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 3,
                "areas": [
                    {"name": "Шапка", "rows": [{"cells": [{"col": 1, "text": "№"}]}]},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        texts = _find_all_tags(root, "text")
        text_values = [t.text for t in texts]
        assert "№" in text_values

    def test_compile_mxl_cell_with_param(self, tmp_path):
        """Ячейка с param (параметр печатной формы)."""
        from src.services.dsl_compiler import MxlCompiler

        compiler = MxlCompiler()
        result = compiler.compile(
            {
                "columns": 3,
                "areas": [
                    {"name": "Строка", "rows": [{"cells": [{"col": 1, "param": "НомерСтроки"}]}]},
                ],
            },
            tmp_path / "Template.xml",
        )

        root = _parse_xml(result.xml_path)
        params = _find_all_tags(root, "parameter")
        assert len(params) == 1
        assert params[0].get("name") == "НомерСтроки"


# ─────────────────────────────────────────────
# RoleCompiler tests
# ─────────────────────────────────────────────


class TestRoleCompiler:
    """Тесты компилятора ролей 1С."""

    def test_compile_role_basic(self, tmp_path):
        """Базовая компиляция роли."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile({"name": "МенеджерПродаж", "synonym": "Менеджер продаж"}, tmp_path / "Roles")

        assert result.object_type == "Role"
        assert result.object_name == "МенеджерПродаж"
        # Метаданные роли
        assert (tmp_path / "Roles" / "МенеджерПродаж.xml").exists()
        # Rights.xml
        assert (tmp_path / "Roles" / "МенеджерПродаж" / "Ext" / "Rights.xml").exists()

    def test_compile_role_metadata_has_name(self, tmp_path):
        """Метаданные роли содержат Name."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile({"name": "Менеджер", "synonym": "Менеджер"}, tmp_path / "Roles")

        meta_path = tmp_path / "Roles" / "Менеджер.xml"
        root = _parse_xml(meta_path)
        local_tag = root.tag.split("}")[-1]
        assert local_tag == "Role"

        names = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "Name":
                names.append(elem.text)
        assert "Менеджер" in names

    def test_compile_role_synonym(self, tmp_path):
        """Синоним записан в метаданных."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        compiler.compile({"name": "R1", "synonym": "Моя роль"}, tmp_path / "Roles")

        meta_path = tmp_path / "Roles" / "R1.xml"
        root = _parse_xml(meta_path)
        contents = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "content":
                contents.append(elem.text)
        assert "Моя роль" in contents

    def test_compile_role_objects_with_preset_view(self, tmp_path):
        """Объекты с пресетом view."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile(
            {
                "name": "Viewer",
                "objects": [{"name": "Catalog.Товары", "preset": "view"}],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "Viewer" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        # Новый формат: <object> (lowercase)
        objects = _find_all_tags(root, "object")
        assert len(objects) == 1
        # Ищем права: <right><name>Read</name><value>true</value></right>
        rights_found = []
        for child in objects[0]:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "right":
                for sub in child:
                    st = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if st == "name" and sub.text:
                        rights_found.append(sub.text)
        assert "Read" in rights_found
        assert "View" in rights_found

    def test_compile_role_objects_with_explicit_rights(self, tmp_path):
        """Объекты с явными правами."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile(
            {
                "name": "Editor",
                "objects": [{"name": "Catalog.Товары", "rights": ["Read", "Insert", "Update"]}],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "Editor" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        objects = _find_all_tags(root, "object")
        rights_found = []
        for child in objects[0]:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "right":
                for sub in child:
                    st = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if st == "name" and sub.text:
                        rights_found.append(sub.text)
        assert "Read" in rights_found
        assert "Insert" in rights_found
        assert "Update" in rights_found

    def test_compile_role_russian_rights(self, tmp_path):
        """Русские синонимы прав работают."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        compiler.compile(
            {
                "name": "R",
                "objects": [{"name": "Catalog.Товары", "rights": ["Чтение", "Просмотр"]}],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "R" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        objects = _find_all_tags(root, "object")
        rights_found = []
        for child in objects[0]:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "right":
                for sub in child:
                    st = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                    if st == "name" and sub.text:
                        rights_found.append(sub.text)
        assert "Read" in rights_found
        assert "View" in rights_found

    def test_compile_role_russian_object_type(self, tmp_path):
        """Русский тип объекта работает."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        compiler.compile(
            {
                "name": "R",
                "objects": [{"name": "Справочник.Товары", "preset": "view"}],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "R" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        objects = _find_all_tags(root, "object")
        # Имя объекта в child <name> должно быть нормализовано: Catalog.Товары
        name_elem = None
        for child in objects[0]:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "name":
                name_elem = child
                break
        assert name_elem is not None
        assert name_elem.text == "Catalog.Товары"

    def test_compile_role_shorthand_string(self, tmp_path):
        """Строковый shorthand 'Тип.Имя: @пресет'."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile(
            {
                "name": "R",
                "objects": ["Catalog.Товары: @view"],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "R" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        objects = _find_all_tags(root, "object")
        assert len(objects) == 1

    def test_compile_role_rls_templates(self, tmp_path):
        """Шаблоны RLS добавляются."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        result = compiler.compile(
            {
                "name": "R",
                "templates": [{"name": "ДляОбъекта(Модификатор)", "condition": "Таблица.Организация = &Организация"}],
            },
            tmp_path / "Roles",
        )

        rights_path = tmp_path / "Roles" / "R" / "Ext" / "Rights.xml"
        root = _parse_xml(rights_path)
        # Новый формат: <template> (lowercase)
        templates = _find_all_tags(root, "template")
        assert len(templates) == 1

    def test_compile_role_missing_name_raises(self, tmp_path):
        """Отсутствует name → ValueError."""
        from src.services.dsl_compiler import RoleCompiler

        compiler = RoleCompiler()
        with pytest.raises(ValueError):
            compiler.compile({"synonym": "X"}, tmp_path / "Roles")


# ─────────────────────────────────────────────
# DslCompiler facade (расширенный) tests
# ─────────────────────────────────────────────


class TestDslCompilerFacadeExtended:
    """Тесты расширенного фасада DslCompiler (5 компиляторов)."""

    def test_facade_has_5_compilers(self):
        """Фасад имеет все 5 компиляторов."""
        from src.services.dsl_compiler import DslCompiler

        compiler = DslCompiler()
        assert hasattr(compiler, "meta")
        assert hasattr(compiler, "form")
        assert hasattr(compiler, "skd")
        assert hasattr(compiler, "mxl")
        assert hasattr(compiler, "role")

    def test_facade_compile_mxl(self, tmp_path):
        """Фасад компилирует mxl."""
        from src.services.dsl_compiler import DslCompiler

        compiler = DslCompiler()
        result = compiler.compile_mxl({"columns": 3, "defaultWidth": 15}, tmp_path / "Template.xml")
        assert result.object_type == "SpreadsheetDocument"

    def test_facade_compile_role(self, tmp_path):
        """Фасад компилирует role."""
        from src.services.dsl_compiler import DslCompiler

        compiler = DslCompiler()
        result = compiler.compile_role({"name": "R1"}, tmp_path / "Roles")
        assert result.object_type == "Role"
