"""
T5.3 (2026-07-06): Тесты для CFE extensions (формы и модули).

Проверяет:
- CfeFormExtension: create_form_extension с разными overrides
- CfeModuleExtension: create_module_extension с разными patches
- CfeExtensionBuilder: build_extension создаёт структуру
- FormOverride и ModulePatch dataclasses
- Edge cases: пустые overrides, неверный base_form
- XML/BSL валидность
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.services.cfe.extensions import (
    CfeExtensionBuilder,
    CfeExtensionInfo,
    CfeFormExtension,
    CfeModuleExtension,
    FormOverride,
    ModulePatch,
)


# ============================================================================
# FormOverride dataclass tests
# ============================================================================


class TestFormOverride:
    def test_creation(self) -> None:
        o = FormOverride(element_name="Кнопка1", action="add")
        assert o.element_name == "Кнопка1"
        assert o.action == "add"
        assert o.new_value == ""
        assert o.handler == ""

    def test_with_all_fields(self) -> None:
        o = FormOverride(
            element_name="Поле1",
            action="modify",
            new_value="Новое значение",
            handler="Обработчик",
        )
        assert o.new_value == "Новое значение"
        assert o.handler == "Обработчик"


# ============================================================================
# ModulePatch dataclass tests
# ============================================================================


class TestModulePatch:
    def test_creation(self) -> None:
        p = ModulePatch(method="МойМетод", action="wrap")
        assert p.method == "МойМетод"
        assert p.action == "wrap"
        assert p.hook == ""
        assert p.new_code == ""

    def test_with_all_fields(self) -> None:
        p = ModulePatch(
            method="Метод1",
            action="replace",
            hook="Хук",
            new_code="Сообщить(1)",
        )
        assert p.hook == "Хук"
        assert p.new_code == "Сообщить(1)"


# ============================================================================
# CfeFormExtension tests
# ============================================================================


class TestCfeFormExtension:
    def test_create_form_extension_returns_xml(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="ПродажаРасш",
        )
        assert isinstance(xml, str)
        assert "<Form" in xml
        assert "</Form>" in xml

    def test_create_form_extension_with_add_override(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш1",
            overrides=[
                FormOverride(
                    element_name="КнопкаПечать",
                    action="add",
                    new_value="Печать",
                    handler="ПечатьДокумента",
                )
            ],
        )
        assert "КнопкаПечать" in xml
        assert "UsualButton" in xml
        assert "ПечатьДокумента" in xml

    def test_create_form_extension_with_hide_override(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Catalog.Товары.Form.ФормаСписка",
            extension_name="Расш2",
            overrides=[
                FormOverride(element_name="КнопкаУдалить", action="hide"),
            ],
        )
        assert "КнопкаУдалить" in xml
        assert "Hide" in xml

    def test_create_form_extension_with_modify_override(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш3",
            overrides=[
                FormOverride(
                    element_name="ПолеНомер",
                    action="modify",
                    new_value="Новый номер",
                )
            ],
        )
        assert "ПолеНомер" in xml
        assert "Modify" in xml
        assert "Новый номер" in xml

    def test_create_form_extension_with_replace_handler(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш4",
            overrides=[
                FormOverride(
                    element_name="ПриОткрытии",
                    action="replace_handler",
                    handler="Расш_ПриОткрытии",
                )
            ],
        )
        assert "ПриОткрытии" in xml
        assert "HandlerReplace" in xml
        assert "Расш_ПриОткрытии" in xml

    def test_invalid_base_form_raises(self) -> None:
        ext = CfeFormExtension()
        with pytest.raises(ValueError, match="base_form"):
            ext.create_form_extension(
                base_form="Invalid.Path",
                extension_name="Расш",
            )

    def test_empty_overrides(self) -> None:
        ext = CfeFormExtension()
        xml = ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш5",
        )
        assert "<Form" in xml
        assert "<Items>" in xml


# ============================================================================
# CfeModuleExtension tests
# ============================================================================


class TestCfeModuleExtension:
    def test_create_module_extension_returns_bsl(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.ОбщегоНазначения",
            extension_name="ОбщегоНазначенияРасш",
        )
        assert isinstance(bsl, str)
        assert "Расширение модуля" in bsl
        assert "ОбщегоНазначения" in bsl

    def test_create_module_extension_with_wrap_patch(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.ОбщегоНазначения",
            extension_name="Расш1",
            patches=[
                ModulePatch(
                    method="МойМетод",
                    action="wrap",
                    hook="ЛогированиеВызова",
                )
            ],
        )
        assert "&Вместо" in bsl
        assert "МойМетод" in bsl
        assert "ПродолжитьВызов" in bsl
        assert "ЛогированиеВызова" in bsl

    def test_create_module_extension_with_before_patch(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш2",
            patches=[
                ModulePatch(method="Метод1", action="before", hook="ПередВызовом"),
            ],
        )
        assert "&Перед" in bsl
        assert "Метод1" in bsl
        assert "ПередВызовом" in bsl

    def test_create_module_extension_with_after_patch(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш3",
            patches=[
                ModulePatch(method="Метод1", action="after", hook="ПослеВызова"),
            ],
        )
        assert "&После" in bsl
        assert "Метод1" in bsl
        assert "ПослеВызова" in bsl

    def test_create_module_extension_with_replace_patch(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш4",
            patches=[
                ModulePatch(
                    method="Метод1",
                    action="replace",
                    new_code="Сообщить(\"Заменено\")",
                )
            ],
        )
        assert "&Вместо" in bsl
        assert "Метод1" in bsl
        assert "Сообщить" in bsl

    def test_create_module_extension_with_new_procedures(self) -> None:
        ext = CfeModuleExtension()
        new_proc = "Процедура МояНоваяПроцедура() Экспорт\nСообщить(\"New\");\nКонецПроцедуры"
        bsl = ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш5",
            new_procedures=[new_proc],
        )
        assert "МояНоваяПроцедура" in bsl
        assert "Экспорт" in bsl

    def test_empty_patches_and_procedures(self) -> None:
        ext = CfeModuleExtension()
        bsl = ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш6",
        )
        assert "Расширение модуля" in bsl
        assert "Модуль1" in bsl


# ============================================================================
# CfeExtensionBuilder tests
# ============================================================================


class TestCfeExtensionBuilder:
    def test_build_extension_creates_config_xml(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="ТестовоеРасширение",
            synonym="Тестовое расширение",
        )
        assert isinstance(info, CfeExtensionInfo)
        assert info.name == "ТестовоеРасширение"
        config_path = tmp_path / "ТестовоеРасширение" / "Configuration.xml"
        assert config_path.exists()
        assert config_path in info.files

    def test_build_extension_with_form_extensions(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        form_ext = CfeFormExtension()
        form_xml = form_ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш",
        )
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="СФормами",
            form_extensions=[("Document.Продажа.Form.ФормаДокумента", form_xml)],
        )
        form_path = tmp_path / "СФормами" / "Forms" / "ФормаДокумента.xml"
        assert form_path.exists()
        assert "Document.Продажа.Form.ФормаДокумента" in info.borrowed_objects

    def test_build_extension_with_module_extensions(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        module_ext = CfeModuleExtension()
        bsl_code = module_ext.create_module_extension(
            base_module="CommonModule.ОбщегоНазначения",
            extension_name="Расш",
        )
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="СМодулями",
            module_extensions=[("CommonModule.ОбщегоНазначения", bsl_code)],
        )
        module_path = tmp_path / "СМодулями" / "Modules" / "ОбщегоНазначения.bsl"
        assert module_path.exists()
        assert "CommonModule.ОбщегоНазначения" in info.borrowed_objects

    def test_build_extension_with_both(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        form_ext = CfeFormExtension()
        form_xml = form_ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="Расш",
        )
        module_ext = CfeModuleExtension()
        bsl_code = module_ext.create_module_extension(
            base_module="CommonModule.Модуль1",
            extension_name="Расш",
        )
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="Комбинированное",
            form_extensions=[("Document.Продажа.Form.ФормаДокумента", form_xml)],
            module_extensions=[("CommonModule.Модуль1", bsl_code)],
        )
        assert len(info.files) == 3  # Configuration.xml + form + module
        assert len(info.borrowed_objects) == 2

    def test_config_xml_is_valid(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="ВалидныйXML",
        )
        config_path = tmp_path / "ВалидныйXML" / "Configuration.xml"
        tree = ET.parse(config_path)
        root = tree.getroot()
        # Configuration element must exist
        found = False
        for child in root:
            if "Configuration" in child.tag:
                found = True
                break
        assert found

    def test_config_xml_has_borrowed_objects(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="СЗаимствованиями",
            form_extensions=[
                ("Document.Продажа.Form.ФормаДокумента", "<Form/>"),
                ("Catalog.Товары.Form.ФормаСписка", "<Form/>"),
            ],
        )
        config_path = tmp_path / "СЗаимствованиями" / "Configuration.xml"
        content = config_path.read_text(encoding="utf-8")
        assert "Document.Продажа.Form.ФормаДокумента" in content
        assert "Catalog.Товары.Form.ФормаСписка" in content
        assert "Adopted" in content  # ObjectBelonging=Adopted

    def test_build_extension_creates_directories(self, tmp_path: Path) -> None:
        builder = CfeExtensionBuilder()
        builder.build_extension(
            output_dir=tmp_path,
            extension_name="СДиректориями",
            form_extensions=[("Document.Продажа.Form.ФормаДокумента", "<Form/>")],
            module_extensions=[("CommonModule.Модуль1", "// code")],
        )
        assert (tmp_path / "СДиректориями").is_dir()
        assert (tmp_path / "СДиректориями" / "Forms").is_dir()
        assert (tmp_path / "СДиректориями" / "Modules").is_dir()


# ============================================================================
# CfeExtensionInfo dataclass tests
# ============================================================================


class TestCfeExtensionInfo:
    def test_defaults(self) -> None:
        info = CfeExtensionInfo(name="Test")
        assert info.name == "Test"
        assert info.synonym == ""
        assert info.uuid  # auto-generated
        assert info.borrowed_objects == []
        assert info.files == []

    def test_uuid_is_unique(self) -> None:
        info1 = CfeExtensionInfo(name="Test1")
        info2 = CfeExtensionInfo(name="Test2")
        assert info1.uuid != info2.uuid


# ============================================================================
# Integration: complete CFE
# ============================================================================


class TestIntegrationCompleteCFE:
    """Интеграционный тест: полное CFE расширение."""

    def test_complete_cfe_with_form_and_module(self, tmp_path: Path) -> None:
        """Полное CFE: form extension + module extension."""
        # Создаём form extension
        form_ext = CfeFormExtension()
        form_xml = form_ext.create_form_extension(
            base_form="Document.Продажа.Form.ФормаДокумента",
            extension_name="ПродажаРасширение",
            overrides=[
                FormOverride(
                    element_name="КнопкаПечать",
                    action="add",
                    new_value="Печать",
                    handler="Расш_Печать",
                ),
                FormOverride(element_name="КнопкаУдалить", action="hide"),
            ],
        )

        # Создаём module extension
        module_ext = CfeModuleExtension()
        bsl_code = module_ext.create_module_extension(
            base_module="CommonModule.ОбщегоНазначения",
            extension_name="ПродажаРасширение",
            patches=[
                ModulePatch(
                    method="СообщитьПользователю",
                    action="wrap",
                    hook="ЛогированиеСообщений",
                )
            ],
            new_procedures=[
                "Процедура Расш_Печать() Экспорт\nСообщить(\"Печать из расширения\");\nКонецПроцедуры"
            ],
        )

        # Собираем CFE
        builder = CfeExtensionBuilder()
        info = builder.build_extension(
            output_dir=tmp_path,
            extension_name="ПродажаРасширение",
            synonym="Расширение для продаж",
            comment="Добавляет печать и логирование",
            form_extensions=[("Document.Продажа.Form.ФормаДокумента", form_xml)],
            module_extensions=[("CommonModule.ОбщегоНазначения", bsl_code)],
        )

        # Проверки
        assert info.name == "ПродажаРасширение"
        assert info.synonym == "Расширение для продаж"
        assert len(info.files) == 3  # Configuration.xml + form + module
        assert len(info.borrowed_objects) == 2

        # Configuration.xml валиден
        config_path = tmp_path / "ПродажаРасширение" / "Configuration.xml"
        ET.parse(config_path)  # не должно падать

        # Form содержит overrides
        form_path = tmp_path / "ПродажаРасширение" / "Forms" / "ФормаДокумента.xml"
        form_content = form_path.read_text(encoding="utf-8")
        assert "КнопкаПечать" in form_content
        assert "КнопкаУдалить" in form_content

        # Module содержит patches и new procedures
        module_path = tmp_path / "ПродажаРасширение" / "Modules" / "ОбщегоНазначения.bsl"
        module_content = module_path.read_text(encoding="utf-8")
        assert "&Вместо" in module_content
        assert "СообщитьПользователю" in module_content
        assert "Расш_Печать" in module_content
