"""
P1.5 — Тесты для доработанного парсера метаданных.

Проверяет:
1. Платформенные стандартные реквизиты (Ссылка, Период, Регистратор, ...)
2. Парсинг <Predefined> (предопределённые элементы)
3. Ресолвинг типов (CatalogRef.X → структура)
4. Разделение attributes по kind (Dimension/Resource/Attribute/Standard)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.metadata.standard_attributes import (
    STANDARD_ATTRIBUTES,
    VIRTUAL_TABLES,
    get_standard_attributes,
    get_virtual_tables,
    is_virtual_table_name,
)
from src.services.metadata.type_resolver import (
    ResolvedType,
    parse_type_string,
    resolve_types,
)
from src.services.metadata.universal_parser import UniversalObjectParser


# ============================================================================
# 1. СТАНДАРТНЫЕ РЕКВИЗИТЫ
# ============================================================================


class TestStandardAttributes:
    """Тесты платформенных стандартных реквизитов."""

    def test_catalog_has_reference_and_code(self):
        """Справочник должен иметь Ссылка, Код, Наименование, ПометкаУдаления."""
        attrs = get_standard_attributes("Catalog", {})
        names = [a["name"] for a in attrs]
        assert "Ссылка" in names
        assert "Код" in names
        assert "Наименование" in names
        assert "ПометкаУдаления" in names
        assert "Родитель" in names
        assert "Владелец" in names

    def test_document_has_link_and_number(self):
        """Документ должен иметь Ссылка, Номер, Дата, Проведен."""
        attrs = get_standard_attributes("Document", {})
        names = [a["name"] for a in attrs]
        assert "Ссылка" in names
        assert "Номер" in names
        assert "Дата" in names
        assert "Проведен" in names
        assert "ПометкаУдаления" in names

    def test_accumulation_register_has_period_and_registrator(self):
        """Регистр накопления должен иметь Период, Регистратор, Активность, НомерСтроки."""
        attrs = get_standard_attributes("AccumulationRegister", {})
        names = [a["name"] for a in attrs]
        assert "Период" in names
        assert "Регистратор" in names
        assert "Активность" in names
        assert "НомерСтроки" in names

    def test_accumulation_register_balance_has_movement_type(self):
        """Регистр накопления остатков должен иметь ВидДвижения."""
        attrs_balance = get_standard_attributes("AccumulationRegister", {"RegisterType": "Balance"})
        attrs_turnovers = get_standard_attributes("AccumulationRegister", {"RegisterType": "Turnovers"})
        names_balance = [a["name"] for a in attrs_balance]
        names_turnovers = [a["name"] for a in attrs_turnovers]
        assert "ВидДвижения" in names_balance
        assert "ВидДвижения" not in names_turnovers

    def test_information_register_periodic_has_period(self):
        """Периодический регистр сведений должен иметь Период."""
        attrs_periodic = get_standard_attributes(
            "InformationRegister", {"Periodicity": "MonthlyPeriod"}
        )
        attrs_nonperiodic = get_standard_attributes(
            "InformationRegister", {"Periodicity": "Nonperiodical"}
        )
        names_periodic = [a["name"] for a in attrs_periodic]
        names_nonperiodic = [a["name"] for a in attrs_nonperiodic]
        assert "Период" in names_periodic
        assert "Период" not in names_nonperiodic

    def test_information_register_subordinate_has_registrator(self):
        """Подчинённый регистратору регистр сведений должен иметь Регистратор."""
        attrs_sub = get_standard_attributes(
            "InformationRegister",
            {"Periodicity": "RecorderPeriod", "RecordingType": "SubordinateToRecorder"},
        )
        attrs_indep = get_standard_attributes(
            "InformationRegister",
            {"Periodicity": "MonthlyPeriod", "RecordingType": "Independent"},
        )
        names_sub = [a["name"] for a in attrs_sub]
        names_indep = [a["name"] for a in attrs_indep]
        assert "Регистратор" in names_sub
        assert "Регистратор" not in names_indep

    def test_unknown_type_returns_empty(self):
        """Неизвестный тип должен возвращать пустой список."""
        attrs = get_standard_attributes("NonexistentType", {})
        assert attrs == []


# ============================================================================
# 2. ВИРТУАЛЬНЫЕ ТАБЛИЦЫ
# ============================================================================


class TestVirtualTables:
    """Тесты виртуальных таблиц регистров."""

    def test_accumulation_balance_has_balances(self):
        """Регистр остатков должен иметь Остатки, Обороты, ОстаткиИОбороты."""
        vtables = get_virtual_tables("AccumulationRegister", {"RegisterType": "Balance"})
        assert "Остатки" in vtables
        assert "Обороты" in vtables
        assert "ОстаткиИОбороты" in vtables

    def test_accumulation_turnovers_no_balances(self):
        """Регистр оборотов НЕ должен иметь Остатки."""
        vtables = get_virtual_tables("AccumulationRegister", {"RegisterType": "Turnovers"})
        assert "Остатки" not in vtables
        assert "Обороты" in vtables

    def test_information_register_periodic_has_slice_last(self):
        """Периодический регистр сведений должен иметь СрезПоследних."""
        vtables = get_virtual_tables(
            "InformationRegister", {"Periodicity": "MonthlyPeriod"}
        )
        assert "СрезПоследних" in vtables

    def test_information_register_nonperiodic_no_slice_last(self):
        """Непериодический регистр сведений НЕ должен иметь СрезПоследних."""
        vtables = get_virtual_tables(
            "InformationRegister", {"Periodicity": "Nonperiodical"}
        )
        assert "СрезПоследних" not in vtables

    def test_is_virtual_table_name_russian(self):
        """Распознавание русских имён виртуальных таблиц."""
        assert is_virtual_table_name("Остатки") == "Остатки"
        assert is_virtual_table_name("Обороты") == "Обороты"
        assert is_virtual_table_name("СрезПоследних") == "СрезПоследних"

    def test_is_virtual_table_name_english(self):
        """Распознавание английских алиасов виртуальных таблиц."""
        assert is_virtual_table_name("Balances") == "Остатки"
        assert is_virtual_table_name("Turnovers") == "Обороты"
        assert is_virtual_table_name("SliceLast") == "СрезПоследних"

    def test_is_virtual_table_name_unknown(self):
        """Неизвестное имя возвращает None."""
        assert is_virtual_table_name("НесуществующаяТаблица") is None


# ============================================================================
# 3. РЕСОЛВИНГ ТИПОВ
# ============================================================================


class TestTypeResolver:
    """Тесты ресолвера типов полей 1С."""

    def test_parse_catalog_ref(self):
        """Парсинг cfg:CatalogRef.Номенклатура."""
        rt = parse_type_string("cfg:CatalogRef.Номенклатура")
        assert rt.kind == "ref"
        assert rt.ref_kind == "Catalog"
        assert rt.ref_name == "Номенклатура"
        assert rt.is_ref() is True
        assert rt.is_numeric() is False

    def test_parse_document_ref(self):
        """Парсинг cfg:DocumentRef.ПриходТовара."""
        rt = parse_type_string("cfg:DocumentRef.ПриходТовара")
        assert rt.kind == "ref"
        assert rt.ref_kind == "Document"
        assert rt.ref_name == "ПриходТовара"

    def test_parse_enum_ref(self):
        """Парсинг cfg:EnumRef.СтавкиНДС."""
        rt = parse_type_string("cfg:EnumRef.СтавкиНДС")
        assert rt.kind == "ref"
        assert rt.ref_kind == "Enum"
        assert rt.ref_name == "СтавкиНДС"

    def test_parse_defined_type(self):
        """Парсинг cfg:DefinedType.Товары."""
        rt = parse_type_string("cfg:DefinedType.Товары")
        assert rt.kind == "defined_type"
        assert rt.ref_name == "Товары"

    def test_parse_primitive_string(self):
        """Парсинг xs:string."""
        rt = parse_type_string("xs:string")
        assert rt.kind == "primitive"
        assert rt.primitive == "string"
        assert rt.is_string() is True

    def test_parse_primitive_decimal(self):
        """Парсинг xs:decimal."""
        rt = parse_type_string("xs:decimal")
        assert rt.kind == "primitive"
        assert rt.primitive == "decimal"
        assert rt.is_numeric() is True

    def test_parse_primitive_boolean(self):
        """Парсинг xs:boolean."""
        rt = parse_type_string("xs:boolean")
        assert rt.kind == "primitive"
        assert rt.primitive == "boolean"
        assert rt.is_boolean() is True

    def test_parse_primitive_datetime(self):
        """Парсинг xs:dateTime."""
        rt = parse_type_string("xs:dateTime")
        assert rt.kind == "primitive"
        assert rt.primitive == "dateTime"
        assert rt.is_date() is True

    def test_parse_unknown_type(self):
        """Неизвестный тип возвращает unknown."""
        rt = parse_type_string("что-то-странное")
        assert rt.kind == "unknown"

    def test_resolve_composite_types(self):
        """Составной тип (CatalogRef.X OR xs:string)."""
        rt = resolve_types(["cfg:CatalogRef.Номенклатура", "xs:string", "xs:decimal"])
        assert rt.kind == "composite"
        assert len(rt.variants) == 3
        assert rt.is_composite() is True
        assert rt.is_numeric() is True  # хотя бы один числовой
        assert rt.is_string() is True  # хотя бы один строковый

    def test_resolve_single_type(self):
        """Один тип не делается composite."""
        rt = resolve_types(["xs:decimal"])
        assert rt.kind == "primitive"
        assert rt.primitive == "decimal"

    def test_resolve_empty_types(self):
        """Пустой список типов → unknown."""
        rt = resolve_types([])
        assert rt.kind == "unknown"

    def test_to_dict_serialization(self):
        """Сериализация в dict."""
        rt = parse_type_string("cfg:CatalogRef.Номенклатура")
        d = rt.to_dict()
        assert d["kind"] == "ref"
        assert d["ref_kind"] == "Catalog"
        assert d["ref_name"] == "Номенклатура"
        assert "description" in d


# ============================================================================
# 4. ИНТЕГРАЦИЯ С UNIVERSAL PARSER
# ============================================================================


@pytest.fixture
def demo_config_dir() -> Path:
    """Директория демо-конфигурации."""
    p = Path(__file__).parent / "functional_test_data" / "ДемоКонфигурация"
    if not p.exists():
        pytest.skip(f"Demo config not found: {p}")
    return p


class TestUniversalParserEnhancements:
    """Тесты интеграции доработок в UniversalObjectParser."""

    def test_parser_initializes(self):
        """Парсер инициализируется без ошибок."""
        parser = UniversalObjectParser()
        assert parser is not None

    def test_parse_demo_catalog(self, demo_config_dir):
        """Парсинг демо-справочника Товары — должны быть стандартные реквизиты."""
        catalog_xml = demo_config_dir / "Catalogs" / "Товары" / "Товары.xml"
        if not catalog_xml.exists():
            pytest.skip(f"Demo catalog not found: {catalog_xml}")

        parser = UniversalObjectParser()
        result = parser.parse(catalog_xml)
        assert result is not None
        assert result["type"] == "Catalog"

        # P1.5: проверяем что стандартные реквизиты добавлены
        children = result["child_objects"]
        all_attrs = children.get("attributes", [])
        all_names = {a.get("name") for a in all_attrs}
        assert "Ссылка" in all_names
        assert "Код" in all_names
        assert "Наименование" in all_names
        assert "ПометкаУдаления" in all_names

        # P1.5: проверяем разделение по kind
        std_attrs = children.get("standard_attributes", [])
        std_names = {a.get("name") for a in std_attrs}
        assert "Ссылка" in std_names
        assert "Код" in std_names

    def test_parse_demo_document(self, demo_config_dir):
        """Парсинг демо-документа Продажа."""
        doc_xml = demo_config_dir / "Documents" / "Продажа" / "Продажа.xml"
        if not doc_xml.exists():
            pytest.skip(f"Demo document not found: {doc_xml}")

        parser = UniversalObjectParser()
        result = parser.parse(doc_xml)
        assert result is not None
        assert result["type"] == "Document"

        children = result["child_objects"]
        all_attrs = children.get("attributes", [])
        all_names = {a.get("name") for a in all_attrs}
        assert "Ссылка" in all_names
        assert "Номер" in all_names
        assert "Дата" in all_names
        assert "Проведен" in all_names

    def test_resolved_type_attached_to_attributes(self, demo_config_dir):
        """P1.5: к каждому реквизиту должен быть прикреплён resolved_type."""
        catalog_xml = demo_config_dir / "Catalogs" / "Товары" / "Товары.xml"
        if not catalog_xml.exists():
            pytest.skip(f"Demo catalog not found: {catalog_xml}")

        parser = UniversalObjectParser()
        result = parser.parse(catalog_xml)
        assert result is not None

        children = result["child_objects"]
        attrs_with_types = [a for a in children.get("attributes", []) if "types" in a and a["types"]]
        # Если в демо-конфигурации есть реквизиты с типами — проверяем resolved_type
        for attr in attrs_with_types:
            assert "resolved_type" in attr, f"resolved_type missing for {attr.get('name')}"
            rt_dict = attr["resolved_type"]
            assert "kind" in rt_dict
            assert "description" in rt_dict

    def test_predefined_parsing_does_not_crash(self, demo_config_dir):
        """P1.5: парсинг предопределённых не должен падать, даже если их нет."""
        catalog_xml = demo_config_dir / "Catalogs" / "Товары" / "Товары.xml"
        if not catalog_xml.exists():
            pytest.skip(f"Demo catalog not found: {catalog_xml}")

        parser = UniversalObjectParser()
        result = parser.parse(catalog_xml)
        assert result is not None
        # predefined может быть пустым, но ключ должен быть
        assert "predefined" in result["child_objects"]
        assert isinstance(result["child_objects"]["predefined"], list)

    def test_kind_separation_in_child_objects(self, demo_config_dir):
        """P1.5: child_objects должен содержать dimensions, resources, attributes_only."""
        catalog_xml = demo_config_dir / "Catalogs" / "Товары" / "Товары.xml"
        if not catalog_xml.exists():
            pytest.skip(f"Demo catalog not found: {catalog_xml}")

        parser = UniversalObjectParser()
        result = parser.parse(catalog_xml)
        children = result["child_objects"]
        assert "dimensions" in children
        assert "resources" in children
        assert "attributes_only" in children
        assert "standard_attributes" in children
        assert isinstance(children["dimensions"], list)
        assert isinstance(children["resources"], list)
        assert isinstance(children["attributes_only"], list)
        assert isinstance(children["standard_attributes"], list)
