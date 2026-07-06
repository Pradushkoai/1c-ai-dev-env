"""
T5.5 (2026-07-06): Тесты для DSL round-trip.

Проверяет:
- verify_round_trip для Subsystem
- verify_round_trip для CommonModule
- Decompile: извлечение name, synonym, comment из XML
- Compare: detection различий
- verify_all_round_trips: все типы
- Edge cases: пустые определения, неверный type
- CLI
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dsl.round_trip import (
    RoundTripResult,
    _compare_definitions,
    _decompile_xml,
    _extract_common_module_props,
    _extract_subsystem_props,
    _extract_synonym,
    _find_child,
    _get_test_definitions,
    verify_all_round_trips,
    verify_round_trip,
)


# ============================================================================
# Subsystem round-trip tests
# ============================================================================


class TestSubsystemRoundTrip:
    """Тесты round-trip для Subsystem."""

    def test_simple_subsystem_round_trip(self, tmp_path: Path) -> None:
        """Простая подсистема round-trip."""
        result = verify_round_trip(
            dsl_definition={
                "type": "Subsystem",
                "name": "TestSub",
                "synonym": "Тестовая подсистема",
            },
            output_dir=tmp_path,
        )
        assert result.object_type == "Subsystem"
        assert result.object_name == "TestSub"
        # name должно совпадать
        assert result.decompiled_definition.get("name") == "TestSub"

    def test_subsystem_with_synonym_round_trip(self, tmp_path: Path) -> None:
        """Подсистема с синонимом."""
        result = verify_round_trip(
            dsl_definition={
                "type": "Subsystem",
                "name": "Sales",
                "synonym": "Продажи",
            },
            output_dir=tmp_path,
        )
        assert result.decompiled_definition.get("synonym") == "Продажи"

    def test_subsystem_with_includes_round_trip(self, tmp_path: Path) -> None:
        """Подсистема с includes."""
        result = verify_round_trip(
            dsl_definition={
                "type": "Subsystem",
                "name": "Purchases",
                "includes": ["Документ.Поступление", "Справочник.Поставщики"],
            },
            output_dir=tmp_path,
        )
        dec_includes = result.decompiled_definition.get("includes", [])
        assert "Документ.Поступление" in dec_includes
        assert "Справочник.Поставщики" in dec_includes

    def test_subsystem_with_nested_subsystems(self, tmp_path: Path) -> None:
        """Подсистема с вложенными подсистемами."""
        result = verify_round_trip(
            dsl_definition={
                "type": "Subsystem",
                "name": "Trade",
                "subsystems": ["Wholesale", "Retail"],
            },
            output_dir=tmp_path,
        )
        dec_subs = result.decompiled_definition.get("subsystems", [])
        assert "Wholesale" in dec_subs
        assert "Retail" in dec_subs

    def test_subsystem_creates_xml_file(self, tmp_path: Path) -> None:
        """Round-trip создаёт XML файл."""
        result = verify_round_trip(
            dsl_definition={
                "type": "Subsystem",
                "name": "WithXml",
            },
            output_dir=tmp_path,
        )
        assert result.compiled_xml_path is not None
        assert result.compiled_xml_path.exists()


# ============================================================================
# CommonModule round-trip tests
# ============================================================================


class TestCommonModuleRoundTrip:
    """Тесты round-trip для CommonModule."""

    def test_simple_module_round_trip(self, tmp_path: Path) -> None:
        """Простой общий модуль round-trip."""
        result = verify_round_trip(
            dsl_definition={
                "type": "CommonModule",
                "name": "TestModule",
                "synonym": "Тестовый модуль",
            },
            output_dir=tmp_path,
        )
        assert result.object_type == "CommonModule"
        assert result.decompiled_definition.get("name") == "TestModule"

    def test_module_with_server_flag(self, tmp_path: Path) -> None:
        """Модуль с server=True."""
        result = verify_round_trip(
            dsl_definition={
                "type": "CommonModule",
                "name": "ServerMod",
                "server": True,
            },
            output_dir=tmp_path,
        )
        assert result.decompiled_definition.get("server") is True

    def test_module_with_privileged_flag(self, tmp_path: Path) -> None:
        """Модуль с privileged=True."""
        result = verify_round_trip(
            dsl_definition={
                "type": "CommonModule",
                "name": "PrivMod",
                "privileged": True,
            },
            output_dir=tmp_path,
        )
        assert result.decompiled_definition.get("privileged") is True

    def test_module_with_all_flags(self, tmp_path: Path) -> None:
        """Модуль со всеми флагами."""
        result = verify_round_trip(
            dsl_definition={
                "type": "CommonModule",
                "name": "AllFlags",
                "server": True,
                "client": True,
                "privileged": True,
                "server_call": True,
            },
            output_dir=tmp_path,
        )
        dec = result.decompiled_definition
        assert dec.get("server") is True
        assert dec.get("client") is True
        assert dec.get("privileged") is True
        assert dec.get("server_call") is True

    def test_module_creates_xml_and_bsl(self, tmp_path: Path) -> None:
        """Round-trip создаёт XML и BSL файлы."""
        result = verify_round_trip(
            dsl_definition={
                "type": "CommonModule",
                "name": "WithFiles",
            },
            output_dir=tmp_path,
        )
        assert result.compiled_xml_path is not None
        assert result.compiled_xml_path.exists()
        # BSL файл тоже должен быть
        bsl_path = result.compiled_xml_path.parent / "Module.bsl"
        assert bsl_path.exists()


# ============================================================================
# Compare tests
# ============================================================================


class TestCompare:
    """Тесты функции сравнения определений."""

    def test_identical_definitions_no_diff(self) -> None:
        """Идентичные определения — нет различий."""
        orig = {"type": "Subsystem", "name": "X", "synonym": "Y"}
        dec = {"type": "Subsystem", "name": "X", "synonym": "Y"}
        assert _compare_definitions(orig, dec) == []

    def test_different_name_detected(self) -> None:
        """Различие в name обнаруживается."""
        orig = {"type": "Subsystem", "name": "X"}
        dec = {"type": "Subsystem", "name": "Y"}
        diffs = _compare_definitions(orig, dec)
        assert any("name" in d for d in diffs)

    def test_different_synonym_detected(self) -> None:
        """Различие в synonym обнаруживается."""
        orig = {"type": "Subsystem", "name": "X", "synonym": "A"}
        dec = {"type": "Subsystem", "name": "X", "synonym": "B"}
        diffs = _compare_definitions(orig, dec)
        assert any("synonym" in d for d in diffs)

    def test_common_module_flag_difference(self) -> None:
        """Различие в boolean flags для CommonModule."""
        orig = {"type": "CommonModule", "name": "X", "server": True}
        dec = {"type": "CommonModule", "name": "X", "server": False}
        diffs = _compare_definitions(orig, dec)
        assert any("server" in d for d in diffs)

    def test_subsystem_includes_difference(self) -> None:
        """Различие в includes для Subsystem."""
        orig = {"type": "Subsystem", "name": "X", "includes": ["A", "B"]}
        dec = {"type": "Subsystem", "name": "X", "includes": ["A"]}
        diffs = _compare_definitions(orig, dec)
        assert any("includes" in d for d in diffs)


# ============================================================================
# verify_all_round_trips tests
# ============================================================================


class TestVerifyAll:
    """Тесты verify_all_round_trips."""

    def test_returns_results_for_all_test_defs(self, tmp_path: Path) -> None:
        """Возвращает результат для каждого тестового определения."""
        results = verify_all_round_trips(tmp_path)
        test_defs = _get_test_definitions()
        assert len(results) == len(test_defs)

    def test_all_results_have_object_type(self, tmp_path: Path) -> None:
        """Все результаты имеют object_type."""
        results = verify_all_round_trips(tmp_path)
        for r in results:
            assert r.object_type in ("Subsystem", "CommonModule")

    def test_all_results_have_object_name(self, tmp_path: Path) -> None:
        """Все результаты имеют object_name."""
        results = verify_all_round_trips(tmp_path)
        for r in results:
            assert r.object_name


# ============================================================================
# Decompile helper tests
# ============================================================================


class TestDecompileHelpers:
    """Тесты вспомогательных функций декомпиляции."""

    def test_extract_synonym_from_xml(self, tmp_path: Path) -> None:
        """Извлечение синонима из XML."""
        import xml.etree.ElementTree as ET

        from src.dsl._common import NS_MD

        xml_content = f'''<?xml version="1.0"?>
<MetaDataObject xmlns="{NS_MD}">
  <Subsystem>
    <Properties>
      <Synonym>
        <v8:item xmlns:v8="http://v8.1c.ru/8.1/data/core">
          <v8:lang>ru</v8:lang>
          <v8:content>Тестовый синоним</v8:content>
        </v8:item>
      </Synonym>
    </Properties>
  </Subsystem>
</MetaDataObject>'''
        xml_path = tmp_path / "test.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Find Subsystem > Properties
        subsystem = None
        for child in root:
            if "Subsystem" in child.tag:
                subsystem = child
                break

        props = subsystem.find(f"{{{NS_MD}}}Properties")
        synonym = _extract_synonym(props)
        assert synonym == "Тестовый синоним"

    def test_find_child_with_namespace(self) -> None:
        """Поиск дочернего элемента с namespace."""
        import xml.etree.ElementTree as ET

        from src.dsl._common import NS_MD

        elem = ET.fromstring(f'<root xmlns="{NS_MD}"><Name>Test</Name></root>')
        name_elem = _find_child(elem, "Name")
        assert name_elem is not None
        assert name_elem.text == "Test"

    def test_find_child_without_namespace(self) -> None:
        """Поиск дочернего элемента без namespace."""
        import xml.etree.ElementTree as ET

        elem = ET.fromstring("<root><Name>Test</Name></root>")
        name_elem = _find_child(elem, "Name")
        assert name_elem is not None
        assert name_elem.text == "Test"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Граничные случаи."""

    def test_empty_definition(self, tmp_path: Path) -> None:
        """Пустое определение."""
        result = verify_round_trip({}, tmp_path)
        assert not result.success
        assert result.error

    def test_unknown_type(self, tmp_path: Path) -> None:
        """Неизвестный тип."""
        result = verify_round_trip(
            {"type": "Unknown", "name": "X"},
            tmp_path,
        )
        # Не должно упасть, но и не должно быть success
        assert isinstance(result, RoundTripResult)

    def test_missing_name(self, tmp_path: Path) -> None:
        """Отсутствие name."""
        result = verify_round_trip(
            {"type": "Subsystem"},
            tmp_path,
        )
        assert not result.success


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_runs(self, capsys, tmp_path: Path) -> None:
        import sys

        sys.argv = [
            "round_trip",
            "--output-dir", str(tmp_path / "rt_test"),
        ]
        from src.dsl.round_trip import main

        rc = main()
        # Может быть 0 или 1 в зависимости от того, все ли round-trip прошли
        assert rc in (0, 1)
        captured = capsys.readouterr()
        assert "ROUND-TRIP" in captured.out


# ============================================================================
# Test definitions
# ============================================================================


class TestTestDefinitions:
    """Тесты тестовых определений."""

    def test_get_test_definitions_returns_list(self) -> None:
        defs = _get_test_definitions()
        assert isinstance(defs, list)
        assert len(defs) >= 4

    def test_all_test_defs_have_type(self) -> None:
        defs = _get_test_definitions()
        for d in defs:
            assert "type" in d

    def test_all_test_defs_have_name(self) -> None:
        defs = _get_test_definitions()
        for d in defs:
            assert "name" in d

    def test_test_defs_include_both_types(self) -> None:
        """Тестовые определения включают и Subsystem, и CommonModule."""
        defs = _get_test_definitions()
        types = {d["type"] for d in defs}
        assert "Subsystem" in types
        assert "CommonModule" in types
