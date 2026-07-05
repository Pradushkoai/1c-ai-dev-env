"""
T5.4 (2026-07-06): Тесты для Subsystem и CommonModule компиляторов.

Проверяет:
- SubsystemCompiler: генерация Subsystem.xml + Content.xml
- CommonModuleCompiler: генерация CommonModule.xml + Module.bsl
- Properties: server, client, privileged flags
- Валидация: неверный type, отсутствие name
- XML валидность
- Регистрация в Configuration.xml
- Edge cases: пустая подсистема, подсистема с includes
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.dsl.subsystem_common import (
    CommonModuleCompiler,
    CommonModuleProperties,
    SubsystemCompiler,
)


# ============================================================================
# SubsystemCompiler tests
# ============================================================================


class TestSubsystemCompiler:
    """Тесты SubsystemCompiler."""

    def test_compile_creates_subsystem_xml(self, tmp_path: Path) -> None:
        """Создаёт Subsystem.xml."""
        compiler = SubsystemCompiler()
        result = compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Продажи",
                "synonym": "Продажи",
            },
            output_dir=tmp_path,
        )
        assert result.object_type == "Subsystem"
        assert result.object_name == "Продажи"
        assert (tmp_path / "Subsystems" / "Продажи" / "Subsystem.xml").exists()

    def test_compile_with_subsystems(self, tmp_path: Path) -> None:
        """Подсистема с вложенными подсистемами."""
        compiler = SubsystemCompiler()
        result = compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Торговля",
                "synonym": "Торговля",
                "subsystems": ["Опт", "Розница"],
            },
            output_dir=tmp_path,
        )
        xml_path = tmp_path / "Subsystems" / "Торговля" / "Subsystem.xml"
        content = xml_path.read_text(encoding="utf-8")
        assert "Subsystem.Опт" in content
        assert "Subsystem.Розница" in content

    def test_compile_with_includes(self, tmp_path: Path) -> None:
        """Подсистема с включёнными объектами."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Закупки",
                "includes": [
                    "Документ.Поступление",
                    "Справочник.Поставщики",
                ],
            },
            output_dir=tmp_path,
        )
        xml_path = tmp_path / "Subsystems" / "Закупки" / "Subsystem.xml"
        content = xml_path.read_text(encoding="utf-8")
        assert "Документ.Поступление" in content
        assert "Справочник.Поставщики" in content

    def test_compile_creates_content_xml_when_has_includes(
        self, tmp_path: Path
    ) -> None:
        """Content.xml создаётся при наличии includes."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Склад",
                "includes": ["Документ.Перемещение"],
            },
            output_dir=tmp_path,
        )
        content_path = (
            tmp_path / "Subsystems" / "Склад" / "Content.xml"
        )
        assert content_path.exists()

    def test_compile_no_content_xml_when_empty(self, tmp_path: Path) -> None:
        """Без includes/subsystems Content.xml не создаётся."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Пустая",
                "synonym": "Пустая",
            },
            output_dir=tmp_path,
        )
        content_path = (
            tmp_path / "Subsystems" / "Пустая" / "Content.xml"
        )
        assert not content_path.exists()

    def test_compile_with_synonym(self, tmp_path: Path) -> None:
        """Синоним попадает в XML."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Sales",
                "synonym": "Продажи",
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "Subsystems" / "Sales" / "Subsystem.xml").read_text(encoding="utf-8")
        assert "Продажи" in xml
        assert "<v8:content>Продажи</v8:content>" in xml

    def test_compile_with_visible_flag(self, tmp_path: Path) -> None:
        """Флаг visible попадает в XML."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "Hidden",
                "visible": False,
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "Subsystems" / "Hidden" / "Subsystem.xml").read_text(encoding="utf-8")
        assert "<IncludeInCommandInterface>false</IncludeInCommandInterface>" in xml

    def test_invalid_type_raises(self, tmp_path: Path) -> None:
        """Неверный type → ValueError."""
        compiler = SubsystemCompiler()
        with pytest.raises(ValueError, match="Subsystem"):
            compiler.compile(
                definition={"type": "Catalog", "name": "X"},
                output_dir=tmp_path,
            )

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        """Отсутствие name → ValueError."""
        compiler = SubsystemCompiler()
        with pytest.raises(ValueError, match="name"):
            compiler.compile(
                definition={"type": "Subsystem"},
                output_dir=tmp_path,
            )

    def test_compile_from_json_string(self, tmp_path: Path) -> None:
        """Компиляция из JSON-строки."""
        compiler = SubsystemCompiler()
        json_str = json.dumps({
            "type": "Subsystem",
            "name": "FromString",
        })
        compiler.compile(definition=json_str, output_dir=tmp_path)
        assert (tmp_path / "Subsystems" / "FromString").exists()

    def test_compile_from_file(self, tmp_path: Path) -> None:
        """Компиляция из JSON-файла."""
        compiler = SubsystemCompiler()
        json_path = tmp_path / "subsystem.json"
        json_path.write_text(
            json.dumps({"type": "Subsystem", "name": "FromFile"}),
            encoding="utf-8",
        )
        compiler.compile(definition=json_path, output_dir=tmp_path)
        assert (tmp_path / "Subsystems" / "FromFile").exists()

    def test_xml_is_valid(self, tmp_path: Path) -> None:
        """Subsystem.xml — валидный XML."""
        compiler = SubsystemCompiler()
        compiler.compile(
            definition={"type": "Subsystem", "name": "ValidXML"},
            output_dir=tmp_path,
        )
        xml_path = tmp_path / "Subsystems" / "ValidXML" / "Subsystem.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Root tag — MetaDataObject, Subsystem — вложенный элемент
        assert "MetaDataObject" in root.tag or root.tag.endswith("}MetaDataObject")
        # Ищем Subsystem вложенный
        for child in root:
            if "Subsystem" in child.tag:
                return
        pytest.fail("Subsystem element not found in XML")


# ============================================================================
# CommonModuleCompiler tests
# ============================================================================


class TestCommonModuleCompiler:
    """Тесты CommonModuleCompiler."""

    def test_compile_creates_module_xml(self, tmp_path: Path) -> None:
        """Создаёт CommonModule.xml."""
        compiler = CommonModuleCompiler()
        result = compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "ОбщегоНазначения",
                "synonym": "Общего назначения",
            },
            output_dir=tmp_path,
        )
        assert result.object_type == "CommonModule"
        assert result.object_name == "ОбщегоНазначения"
        assert (tmp_path / "CommonModules" / "ОбщегоНазначения" / "CommonModule.xml").exists()

    def test_compile_creates_module_bsl(self, tmp_path: Path) -> None:
        """Создаёт Module.bsl с заглушкой."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "Модуль1",
            },
            output_dir=tmp_path,
        )
        bsl_path = tmp_path / "CommonModules" / "Модуль1" / "Module.bsl"
        assert bsl_path.exists()
        bsl_content = bsl_path.read_text(encoding="utf-8")
        assert "Функция" in bsl_content or "Процедура" in bsl_content

    def test_compile_with_server_flag(self, tmp_path: Path) -> None:
        """Флаг server=True попадает в XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "ServerModule",
                "server": True,
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "CommonModules" / "ServerModule" / "CommonModule.xml").read_text(encoding="utf-8")
        assert "<Server>true</Server>" in xml

    def test_compile_with_client_flag(self, tmp_path: Path) -> None:
        """Флаг client=True попадает в XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "ClientModule",
                "client": True,
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "CommonModules" / "ClientModule" / "CommonModule.xml").read_text(encoding="utf-8")
        assert "<Client>true</Client>" in xml

    def test_compile_with_privileged_flag(self, tmp_path: Path) -> None:
        """Флаг privileged=True попадает в XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "PrivModule",
                "privileged": True,
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "CommonModules" / "PrivModule" / "CommonModule.xml").read_text(encoding="utf-8")
        assert "<Privileged>true</Privileged>" in xml

    def test_compile_with_server_call(self, tmp_path: Path) -> None:
        """Флаг server_call=True попадает в XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "ServerCallModule",
                "server_call": True,
                "server": True,
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "CommonModules" / "ServerCallModule" / "CommonModule.xml").read_text(encoding="utf-8")
        assert "<ServerCall>true</ServerCall>" in xml

    def test_compile_with_synonym(self, tmp_path: Path) -> None:
        """Синоним попадает в XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "MyModule",
                "synonym": "Мой модуль",
            },
            output_dir=tmp_path,
        )
        xml = (tmp_path / "CommonModules" / "MyModule" / "CommonModule.xml").read_text(encoding="utf-8")
        assert "Мой модуль" in xml

    def test_compile_bsl_has_version_function(self, tmp_path: Path) -> None:
        """BSL содержит функцию ПолучитьВерсиюМодуля."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={"type": "CommonModule", "name": "Versioned"},
            output_dir=tmp_path,
        )
        bsl = (tmp_path / "CommonModules" / "Versioned" / "Module.bsl").read_text(encoding="utf-8")
        assert "ПолучитьВерсиюМодуля" in bsl
        assert "Экспорт" in bsl

    def test_invalid_type_raises(self, tmp_path: Path) -> None:
        """Неверный type → ValueError."""
        compiler = CommonModuleCompiler()
        with pytest.raises(ValueError, match="CommonModule"):
            compiler.compile(
                definition={"type": "Document", "name": "X"},
                output_dir=tmp_path,
            )

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        """Отсутствие name → ValueError."""
        compiler = CommonModuleCompiler()
        with pytest.raises(ValueError, match="name"):
            compiler.compile(
                definition={"type": "CommonModule"},
                output_dir=tmp_path,
            )

    def test_xml_is_valid(self, tmp_path: Path) -> None:
        """CommonModule.xml — валидный XML."""
        compiler = CommonModuleCompiler()
        compiler.compile(
            definition={
                "type": "CommonModule",
                "name": "ValidModule",
                "server": True,
                "client": False,
            },
            output_dir=tmp_path,
        )
        xml_path = tmp_path / "CommonModules" / "ValidModule" / "CommonModule.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        assert "MetaDataObject" in root.tag or root.tag.endswith("}MetaDataObject")
        for child in root:
            if "CommonModule" in child.tag:
                return
        pytest.fail("CommonModule element not found in XML")

    def test_compile_from_json_string(self, tmp_path: Path) -> None:
        """Компиляция из JSON-строки."""
        compiler = CommonModuleCompiler()
        json_str = json.dumps({
            "type": "CommonModule",
            "name": "FromString",
        })
        compiler.compile(definition=json_str, output_dir=tmp_path)
        assert (tmp_path / "CommonModules" / "FromString").exists()


# ============================================================================
# CommonModuleProperties dataclass tests
# ============================================================================


class TestCommonModuleProperties:
    """Тесты CommonModuleProperties dataclass."""

    def test_defaults(self) -> None:
        props = CommonModuleProperties(name="X")
        assert props.name == "X"
        assert props.server is False
        assert props.client is False
        assert props.privileged is False
        assert props.server_call is False
        assert props.global_ is False

    def test_with_all_flags(self) -> None:
        props = CommonModuleProperties(
            name="X",
            server=True,
            client=True,
            privileged=True,
            server_call=True,
        )
        assert props.server
        assert props.client
        assert props.privileged
        assert props.server_call


# ============================================================================
# Integration: complex subsystem
# ============================================================================


class TestIntegrationComplexSubsystem:
    """Интеграционный тест: сложная подсистема с вложениями."""

    def test_complex_subsystem(self, tmp_path: Path) -> None:
        """Подсистема со всеми свойствами."""
        compiler = SubsystemCompiler()
        result = compiler.compile(
            definition={
                "type": "Subsystem",
                "name": "УправлениеЗакупками",
                "synonym": "Управление закупками",
                "comment": "Подсистема управления закупками",
                "subsystems": ["ПланированиеЗакупок", "ПоступлениеТоваров"],
                "includes": [
                    "Документ.ЗаказПоставщику",
                    "Документ.ПоступлениеТоваров",
                    "Справочник.Поставщики",
                    "Справочник.Номенклатура",
                ],
                "visible": True,
                "include_help_in_contents": True,
            },
            output_dir=tmp_path,
        )

        # Проверки
        subsystem_dir = tmp_path / "Subsystems" / "УправлениеЗакупками"
        assert (subsystem_dir / "Subsystem.xml").exists()
        assert (subsystem_dir / "Content.xml").exists()

        # Subsystem.xml содержит все элементы
        xml = (subsystem_dir / "Subsystem.xml").read_text(encoding="utf-8")
        assert "Управление закупками" in xml
        assert "Subsystem.ПланированиеЗакупок" in xml
        assert "Subsystem.ПоступлениеТоваров" in xml
        assert "Документ.ЗаказПоставщику" in xml
        assert "Документ.ПоступлениеТоваров" in xml
        assert "Справочник.Поставщики" in xml
        assert "Справочник.Номенклатура" in xml
        assert "<IncludeHelpInContents>true</IncludeHelpInContents>" in xml

        # Content.xml валиден
        content = (subsystem_dir / "Content.xml").read_text(encoding="utf-8")
        ET.fromstring(content)   # не должно падать
