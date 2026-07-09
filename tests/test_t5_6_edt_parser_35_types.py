"""
T5.6 (2026-07-06): Тесты для EDT parser — все 35 типов.

Проверяет:
- EDT_TYPE_MAP содержит 35 типов
- EDT_DIRS содержит 35 типов
- _parse_type_specific_fields обрабатывает все 35 типов
- Каждый type-specific parser извлекает правильные поля
- Интеграционные тесты с синтетическими .mdo файлами
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.services.edt_parser import EDT_DIRS, EDT_TYPE_MAP, EdtParser


# ============================================================================
# Constants tests
# ============================================================================


class TestEDTConstants:
    """Тесты констант EDT."""

    def test_edt_type_map_has_35_types(self) -> None:
        """EDT_TYPE_MAP содержит ровно 35 типов."""
        assert len(EDT_TYPE_MAP) == 35, f"Expected 35, got {len(EDT_TYPE_MAP)}"

    def test_edt_dirs_has_35_types(self) -> None:
        """EDT_DIRS содержит ровно 35 типов."""
        assert len(EDT_DIRS) == 35, f"Expected 35, got {len(EDT_DIRS)}"

    def test_edt_type_map_and_dirs_same_keys(self) -> None:
        """EDT_TYPE_MAP и EDT_DIRS имеют одинаковые ключи."""
        assert set(EDT_TYPE_MAP.keys()) == set(EDT_DIRS.keys())

    def test_all_35_types_listed(self) -> None:
        """Все 35 ожидаемых типов присутствуют."""
        expected_types = {
            "Catalog", "Document", "Enum", "InformationRegister",
            "AccumulationRegister", "AccountingRegister", "CalculationRegister",
            "Constant", "CommonModule", "CommonForm", "CommonCommand",
            "CommonTemplate", "CommonPicture", "CommonAttribute",
            "Report", "DataProcessor",
            "ChartOfAccounts", "ChartOfCharacteristicTypes", "ChartOfCalculationTypes",
            "BusinessProcess", "Task", "ExchangePlan",
            "DocumentJournal", "DocumentNumerator", "Sequence",
            "DefinedType", "EventSubscription", "ScheduledJob",
            "FilterCriterion", "CommandGroup",
            "FunctionalOption", "FunctionalOptionParameter",
            "SessionParameter", "SettingsStorage", "Style",
        }
        assert expected_types == set(EDT_TYPE_MAP.keys())


# ============================================================================
# Type-specific parser tests
# ============================================================================


class TestTypeSpecificParsers:
    """Тесты type-specific парсеров."""

    NS_EDT = "http://g5.1c.ru/v8/dt/metadata/mdclasses"

    def _make_mdo_content(self, obj_type: str, extra_fields: str = "") -> str:
        """Создать синтетический .mdo контент с EDT namespace."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<mdObject class="{obj_type}" xmlns="{self.NS_EDT}">
  <name>Тест{obj_type}</name>
  <synonym>Тестовый {obj_type}</synonym>
  <comment>Для теста</comment>
  {extra_fields}
</mdObject>"""

    def _parse_obj(self, obj_type: str, extra_fields: str = "") -> dict:
        """Парсить объект заданного типа."""
        parser = EdtParser()
        content = self._make_mdo_content(obj_type, extra_fields)
        # Используем _parse_mdo_file напрямую через временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mdo", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            mdo_path = Path(f.name)
        try:
            return parser._parse_mdo_file(mdo_path, obj_type)
        finally:
            mdo_path.unlink(missing_ok=True)

    def test_catalog_parsed(self) -> None:
        obj = self._parse_obj("Catalog", '<hierarchical>true</hierarchical>')
        assert obj is not None
        assert obj["type"] == "Catalog"
        assert obj["hierarchical"] is True

    def test_document_parsed(self) -> None:
        obj = self._parse_obj("Document", '<numberType>String</numberType>')
        assert obj is not None
        assert obj["number_type"] == "String"

    def test_information_register_parsed(self) -> None:
        obj = self._parse_obj("InformationRegister", '<periodicity>Nonperiodical</periodicity>')
        assert obj is not None
        assert obj["periodicity"] == "Nonperiodical"

    def test_accumulation_register_parsed(self) -> None:
        obj = self._parse_obj("AccumulationRegister", '<periodicity>Nonperiodical</periodicity>')
        assert obj is not None
        assert obj["periodicity"] == "Nonperiodical"

    def test_accounting_register_parsed(self) -> None:
        obj = self._parse_obj("AccountingRegister", '<periodicity>Nonperiodical</periodicity>')
        assert obj is not None
        assert obj["periodicity"] == "Nonperiodical"

    def test_calculation_register_parsed(self) -> None:
        obj = self._parse_obj("CalculationRegister", '<periodicity>Nonperiodical</periodicity>')
        assert obj is not None
        assert obj["periodicity"] == "Nonperiodical"

    def test_enum_parsed(self) -> None:
        obj = self._parse_obj("Enum")
        assert obj is not None
        assert "enum_values" in obj

    def test_constant_parsed(self) -> None:
        obj = self._parse_obj("Constant", '<type>String</type>')
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_common_module_parsed(self) -> None:
        obj = self._parse_obj(
            "CommonModule",
            "<server>true</server><client>false</client><privileged>true</privileged>"
        )
        assert obj is not None
        assert obj["server"] is True
        assert obj["client"] is False
        assert obj["privileged"] is True

    def test_common_form_parsed(self) -> None:
        obj = self._parse_obj("CommonForm", '<formType>Managed</formType>')
        assert obj is not None
        assert obj["form_type"] == "Managed"

    def test_common_command_parsed(self) -> None:
        obj = self._parse_obj(
            "CommonCommand",
            "<commandKind>Auto</commandKind><group>PanelActions</group>"
        )
        assert obj is not None
        assert obj["command_kind"] == "Auto"

    def test_common_template_parsed(self) -> None:
        obj = self._parse_obj("CommonTemplate", '<templateType>SpreadsheetDocument</templateType>')
        assert obj is not None
        assert obj["template_type"] == "SpreadsheetDocument"

    def test_common_picture_parsed(self) -> None:
        obj = self._parse_obj("CommonPicture", '<pictureSize>32</pictureSize>')
        assert obj is not None
        assert obj["picture_size"] == "32"

    def test_common_attribute_parsed(self) -> None:
        obj = self._parse_obj("CommonAttribute", '<type>String</type><autoUse>Use</autoUse>')
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_report_parsed(self) -> None:
        obj = self._parse_obj("Report")
        assert obj is not None
        assert "attributes" in obj

    def test_data_processor_parsed(self) -> None:
        obj = self._parse_obj("DataProcessor")
        assert obj is not None
        assert "attributes" in obj

    def test_chart_of_accounts_parsed(self) -> None:
        obj = self._parse_obj("ChartOfAccounts", '<hierarchical>true</hierarchical>')
        assert obj is not None
        assert obj["hierarchical"] is True

    def test_chart_of_characteristic_types_parsed(self) -> None:
        obj = self._parse_obj("ChartOfCharacteristicTypes")
        assert obj is not None

    def test_chart_of_calculation_types_parsed(self) -> None:
        obj = self._parse_obj("ChartOfCalculationTypes")
        assert obj is not None

    def test_business_process_parsed(self) -> None:
        obj = self._parse_obj("BusinessProcess", '<numberType>String</numberType>')
        assert obj is not None
        assert obj["number_type"] == "String"

    def test_task_parsed(self) -> None:
        obj = self._parse_obj("Task", '<numberType>String</numberType>')
        assert obj is not None
        assert obj["number_type"] == "String"

    def test_exchange_plan_parsed(self) -> None:
        obj = self._parse_obj("ExchangePlan", '<distributed>true</distributed>')
        assert obj is not None
        assert obj["distributed"] is True

    def test_document_journal_parsed(self) -> None:
        obj = self._parse_obj("DocumentJournal")
        assert obj is not None

    def test_document_numerator_parsed(self) -> None:
        obj = self._parse_obj("DocumentNumerator", '<numberType>String</numberType>')
        assert obj is not None
        assert obj["number_type"] == "String"

    def test_sequence_parsed(self) -> None:
        obj = self._parse_obj("Sequence", '<documentType>Document.Продажа</documentType>')
        assert obj is not None
        assert obj["document_type"] == "Document.Продажа"

    def test_defined_type_parsed(self) -> None:
        obj = self._parse_obj("DefinedType", '<type>String</type>')
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_event_subscription_parsed(self) -> None:
        obj = self._parse_obj(
            "EventSubscription",
            "<event>OnWrite</event><handler>Module.Handler</handler>"
        )
        assert obj is not None
        assert obj["event"] == "OnWrite"

    def test_scheduled_job_parsed(self) -> None:
        obj = self._parse_obj(
            "ScheduledJob",
            "<methodName>Module.Run</methodName><schedule>Daily</schedule>"
        )
        assert obj is not None
        assert obj["method_name"] == "Module.Run"

    def test_filter_criterion_parsed(self) -> None:
        obj = self._parse_obj("FilterCriterion", '<type>String</type>')
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_command_group_parsed(self) -> None:
        obj = self._parse_obj("CommandGroup", '<groupKind>ActionsPanel</groupKind>')
        assert obj is not None
        assert obj["group_kind"] == "ActionsPanel"

    def test_functional_option_parsed(self) -> None:
        obj = self._parse_obj(
            "FunctionalOption",
            "<type>Boolean</type><location>Constant.UseFeature</location>"
        )
        assert obj is not None
        assert obj["value_type"] == "Boolean"

    def test_functional_option_parameter_parsed(self) -> None:
        obj = self._parse_obj(
            "FunctionalOptionParameter",
            "<type>String</type><use>Use</use>"
        )
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_session_parameter_parsed(self) -> None:
        obj = self._parse_obj("SessionParameter", '<type>String</type>')
        assert obj is not None
        assert obj["value_type"] == "String"

    def test_settings_storage_parsed(self) -> None:
        obj = self._parse_obj("SettingsStorage", '<form>Form.Settings</form>')
        assert obj is not None
        assert obj["form"] == "Form.Settings"

    def test_style_parsed(self) -> None:
        obj = self._parse_obj("Style")
        assert obj is not None
        assert "style_items" in obj


# ============================================================================
# Parametrized: all 35 types
# ============================================================================


class TestAllTypesParametrized:
    """Параметризованные тесты для всех 35 типов."""

    @pytest.mark.parametrize("obj_type", sorted(EDT_TYPE_MAP.keys()))
    def test_all_types_return_dict(self, obj_type: str) -> None:
        """Все 35 типов возвращают dict (не None)."""
        parser = EdtParser()
        ns = "http://g5.1c.ru/v8/dt/metadata/mdclasses"
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdObject class="{obj_type}" xmlns="{ns}">
  <name>Test{obj_type}</name>
  <synonym>Test {obj_type}</synonym>
</mdObject>"""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mdo", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            mdo_path = Path(f.name)
        try:
            obj = parser._parse_mdo_file(mdo_path, obj_type)
            assert obj is not None
            assert obj["type"] == EDT_TYPE_MAP[obj_type]
            assert obj["name"] == f"Test{obj_type}"
        finally:
            mdo_path.unlink(missing_ok=True)

    @pytest.mark.parametrize("obj_type", sorted(EDT_DIRS.keys()))
    def test_all_types_have_dirs(self, obj_type: str) -> None:
        """Все 35 типов имеют директорию в EDT_DIRS."""
        assert obj_type in EDT_DIRS
        assert EDT_DIRS[obj_type]  # не пустая строка


# ============================================================================
# Integration: full project parse
# ============================================================================


class TestIntegrationFullProject:
    """Интеграционный тест: полный EDT проект."""

    def test_parse_project_with_multiple_types(self, tmp_path: Path) -> None:
        """Парсинг проекта с несколькими типами объектов."""
        ns = "http://g5.1c.ru/v8/dt/metadata/mdclasses"
        # Создаём структуру EDT проекта
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Configuration.mdo
        config_mdo = src_dir / "Configuration.mdo"
        config_mdo.write_text(
            f'<?xml version="1.0"?>\n<mdObject class="Configuration" xmlns="{ns}">'
            '<name>ТестоваяКонфигурация</name></mdObject>',
            encoding="utf-8",
        )

        # Catalogs
        cat_dir = src_dir / "Catalogs"
        cat_dir.mkdir()
        (cat_dir / "Товары.mdo").write_text(
            f'<?xml version="1.0"?>\n<mdObject class="Catalog" xmlns="{ns}">'
            '<name>Товары</name><synonym>Товары</synonym>'
            '<hierarchical>true</hierarchical></mdObject>',
            encoding="utf-8",
        )

        # Documents
        doc_dir = src_dir / "Documents"
        doc_dir.mkdir()
        (doc_dir / "Продажа.mdo").write_text(
            f'<?xml version="1.0"?>\n<mdObject class="Document" xmlns="{ns}">'
            '<name>Продажа</name><synonym>Продажа</synonym>'
            '<numberType>String</numberType></mdObject>',
            encoding="utf-8",
        )

        # CommonModules
        cm_dir = src_dir / "CommonModules"
        cm_dir.mkdir()
        (cm_dir / "ОбщегоНазначения.mdo").write_text(
            f'<?xml version="1.0"?>\n<mdObject class="CommonModule" xmlns="{ns}">'
            '<name>ОбщегоНазначения</name><synonym>Общего назначения</synonym>'
            '<server>true</server></mdObject>',
            encoding="utf-8",
        )

        # Парсим
        parser = EdtParser()
        objects = parser.parse(tmp_path)

        # Должны найти 3 объекта (Configuration.mdo не считается)
        assert len(objects) == 3

        # Проверяем типы
        types = {obj["type"] for obj in objects}
        assert "Catalog" in types
        assert "Document" in types
        assert "CommonModule" in types

        # Проверяем конкретные поля
        cat = next(o for o in objects if o["type"] == "Catalog")
        assert cat["name"] == "Товары"
        assert cat["hierarchical"] is True

        doc = next(o for o in objects if o["type"] == "Document")
        assert doc["number_type"] == "String"

        cm = next(o for o in objects if o["type"] == "CommonModule")
        assert cm["server"] is True

    def test_get_stats(self, tmp_path: Path) -> None:
        """get_stats возвращает корректную статистику."""
        ns = "http://g5.1c.ru/v8/dt/metadata/mdclasses"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Configuration.mdo").write_text(
            f'<?xml version="1.0"?><mdObject class="Configuration" xmlns="{ns}">'
            '<name>TestConfig</name></mdObject>',
            encoding="utf-8",
        )
        # Создаём 2 каталога
        cat_dir = src_dir / "Catalogs"
        cat_dir.mkdir()
        for name in ["Кат1", "Кат2"]:
            (cat_dir / f"{name}.mdo").write_text(
                f'<?xml version="1.0"?><mdObject class="Catalog" xmlns="{ns}">'
                f'<name>{name}</name></mdObject>',
                encoding="utf-8",
            )

        parser = EdtParser()
        parser.parse(tmp_path)
        stats = parser.get_stats()

        assert stats["total_objects"] == 2
        assert stats["by_type"]["Catalog"] == 2
        assert stats["source"] == "edt"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Граничные случаи."""

    def test_unknown_type_no_crash(self, tmp_path: Path) -> None:
        """Неизвестный тип не вызывает crash."""
        parser = EdtParser()
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mdo", delete=False, encoding="utf-8"
        ) as f:
            f.write('<?xml version="1.0"?><mdObject class="Unknown">'
                    '<name>X</name></mdObject>')
            mdo_path = Path(f.name)
        try:
            obj = parser._parse_mdo_file(mdo_path, "Unknown")
            # Не должно упасть, возвращает базовый объект
            assert obj is not None
            assert obj["name"] == "X"
        finally:
            mdo_path.unlink(missing_ok=True)

    def test_empty_project(self, tmp_path: Path) -> None:
        """Пустой проект возвращает пустой список."""
        parser = EdtParser()
        objects = parser.parse(tmp_path)
        assert objects == []

    def test_malformed_xml_skipped(self, tmp_path: Path) -> None:
        """Повреждённый XML пропускается."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "Configuration.mdo").write_text(
            '<?xml version="1.0"?><mdObject><name>Test</name></mdObject>',
            encoding="utf-8",
        )
        cat_dir = src_dir / "Catalogs"
        cat_dir.mkdir()
        (cat_dir / "Bad.mdo").write_text("not xml", encoding="utf-8")
        (cat_dir / "Good.mdo").write_text(
            '<?xml version="1.0"?><mdObject class="Catalog">'
            '<name>Good</name></mdObject>',
            encoding="utf-8",
        )

        parser = EdtParser()
        objects = parser.parse(tmp_path)
        # Bad пропущен, Good распарсен
        assert len(objects) == 1
        assert objects[0]["name"] == "Good"
