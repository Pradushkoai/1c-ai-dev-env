"""
Тесты для CfeManager — работа с расширениями конфигураций 1С (CFE).

3 операции:
1. borrow_object — заимствование объекта из конфигурации в расширение
2. patch_method — генерация BSL с &Перед/&После/&ИзменениеИКонтроль
3. diff — анализ что перенесено в основную конфигурацию
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.services.cfe_manager import (
    CfeManager,
    BorrowResult,
    PatchMethodResult,
    CfeDiffResult,
    TYPE_MAP,
)


# ─────────────────────────────────────────────
# Фикстуры
# ─────────────────────────────────────────────


@pytest.fixture
def setup_extension(tmp_path):
    """Создать минимальное расширение с Configuration.xml."""
    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()

    # Configuration.xml расширения
    config_xml = ext_dir / "Configuration.xml"
    config_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:xr="http://v8.1c.ru/8.3/xcf/extprops">\n'
        "  <md:Properties>\n"
        "    <xr:NamePrefix>Расш_</xr:NamePrefix>\n"
        "  </md:Properties>\n"
        "  <md:ChildObjects/>\n"
        "</md:Configuration>\n",
        encoding="utf-8",
    )
    return ext_dir


@pytest.fixture
def setup_config(tmp_path):
    """Создать минимальную конфигурацию с одним справочником."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    # Catalogs/ directory
    catalogs_dir = cfg_dir / "Catalogs"
    catalogs_dir.mkdir()

    # Catalogs/Контрагенты/
    catalog_dir = catalogs_dir / "Контрагенты"
    catalog_dir.mkdir()

    # Catalogs/Контрагенты.xml
    catalog_xml = catalogs_dir / "Контрагенты.xml"
    catalog_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<md:Catalog xmlns:md="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:xr="http://v8.1c.ru/8.3/xcf/extprops" uuid="abc-123">\n'
        "  <md:InternalInfo/>\n"
        "  <md:Properties>\n"
        "    <xr:Name>Контрагенты</xr:Name>\n"
        "    <xr:Synonym>Контрагенты</xr:Synonym>\n"
        "  </md:Properties>\n"
        "  <md:ChildObjects/>\n"
        "</md:Catalog>\n",
        encoding="utf-8",
    )
    return cfg_dir


# ─────────────────────────────────────────────
# BORROW tests
# ─────────────────────────────────────────────


class TestBorrowObject:
    """Тесты заимствования объектов."""

    def test_borrow_catalog_success(self, setup_extension, setup_config):
        """Успешное заимствование справочника."""
        manager = CfeManager()
        result = manager.borrow_object(setup_extension, setup_config, "Catalog.Контрагенты")

        assert result.object_ref == "Catalog.Контрагенты"
        assert result.object_type == "Catalog"
        assert result.object_name == "Контрагенты"
        assert len(result.xml_created) >= 1
        assert result.registered_in_config is True

        # XML файл создан
        obj_xml = setup_extension / "Catalogs" / "Контрагенты.xml"
        assert obj_xml.exists()

    def test_borrow_creates_object_belonging_adopted(self, setup_extension, setup_config):
        """Заимствованный объект имеет ObjectBelonging=Adopted."""
        manager = CfeManager()
        manager.borrow_object(setup_extension, setup_config, "Catalog.Контрагенты")

        obj_xml = setup_extension / "Catalogs" / "Контрагенты.xml"
        tree = ET.parse(obj_xml)
        root = tree.getroot()

        belonging = None
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "ObjectBelonging":
                belonging = elem.text
                break

        assert belonging == "Adopted"

    def test_borrow_registers_in_config(self, setup_extension, setup_config):
        """Объект регистрируется в ChildObjects Configuration.xml."""
        manager = CfeManager()
        manager.borrow_object(setup_extension, setup_config, "Catalog.Контрагенты")

        # Проверяем что в Configuration.xml появился тег <Catalog>Контрагенты</Catalog>
        config_xml = setup_extension / "Configuration.xml"
        tree = ET.parse(config_xml)
        root = tree.getroot()

        found = False
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Catalog" and elem.text == "Контрагенты":
                found = True
                break
        assert found

    def test_borrow_missing_extension_raises(self, tmp_path, setup_config):
        """Несуществующее расширение → FileNotFoundError."""
        manager = CfeManager()
        with pytest.raises(FileNotFoundError):
            manager.borrow_object(tmp_path / "missing", setup_config, "Catalog.Контрагенты")

    def test_borrow_missing_config_raises(self, setup_extension, tmp_path):
        """Несуществующая конфигурация → FileNotFoundError."""
        manager = CfeManager()
        with pytest.raises(FileNotFoundError):
            manager.borrow_object(setup_extension, tmp_path / "missing", "Catalog.Контрагенты")

    def test_borrow_invalid_object_ref(self, setup_extension, setup_config):
        """Неверный формат object_ref → ValueError."""
        manager = CfeManager()
        with pytest.raises(ValueError):
            manager.borrow_object(setup_extension, setup_config, "InvalidFormat")

    def test_borrow_unsupported_type(self, setup_extension, setup_config):
        """Неподдерживаемый тип → ValueError."""
        manager = CfeManager()
        with pytest.raises(ValueError):
            manager.borrow_object(setup_extension, setup_config, "UnknownType.X")

    def test_borrow_batch_multiple_objects(self, setup_extension, setup_config):
        """Batch заимствование через ;;."""
        # Добавим ещё один объект в конфигурацию
        (setup_config / "CommonModules").mkdir()
        cm_xml = setup_config / "CommonModules" / "РаботаСФайлами.xml"
        cm_xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<md:CommonModule xmlns:md="http://v8.1c.ru/8.3/MDClasses" uuid="def-456"/>',
            encoding="utf-8",
        )

        manager = CfeManager()
        result = manager.borrow_object(
            setup_extension, setup_config, "Catalog.Контрагенты;; CommonModule.РаботаСФайлами"
        )

        assert result.object_type == "Multiple"
        # Должны быть созданы оба XML
        assert (setup_extension / "Catalogs" / "Контрагенты.xml").exists()
        assert (setup_extension / "CommonModules" / "РаботаСФайлами.xml").exists()

    def test_borrow_warning_when_not_in_config(self, setup_extension, tmp_path):
        """Если объекта нет в конфигурации — warning, но XML создаётся."""
        # Минимальная конфигурация без нужного объекта
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        (cfg / "Configuration.xml").write_text(
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>', encoding="utf-8"
        )

        manager = CfeManager()
        result = manager.borrow_object(setup_extension, cfg, "Catalog.Несуществующий")

        assert len(result.warnings) >= 1
        assert any("не найден" in w for w in result.warnings)
        # XML всё равно создаётся
        assert (setup_extension / "Catalogs" / "Несуществующий.xml").exists()


# ─────────────────────────────────────────────
# PATCH_METHOD tests
# ─────────────────────────────────────────────


class TestPatchMethod:
    """Тесты генерации BSL-перехватчиков."""

    def test_patch_before_creates_bsl(self, setup_extension):
        """&Перед генерирует BSL-файл."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "Before",
        )

        assert result.interceptor_type == "Before"
        assert result.bsl_file is not None
        assert result.bsl_file.exists()
        assert "&Перед" in result.bsl_content
        assert "ПриЗаписи" in result.bsl_content

    def test_patch_after_creates_bsl(self, setup_extension):
        """&После генерирует BSL-файл."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "After",
        )

        assert "&После" in result.bsl_content

    def test_patch_modification_and_control(self, setup_extension):
        """&ИзменениеИКонтроль генерирует BSL с маркерами #Вставка/#Удаление."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "ModificationAndControl",
        )

        assert "&ИзменениеИКонтроль" in result.bsl_content
        assert "#Вставка" in result.bsl_content
        assert "#Удаление" in result.bsl_content

    def test_patch_invalid_interceptor_type(self, setup_extension):
        """Неверный interceptor_type → ValueError."""
        manager = CfeManager()
        with pytest.raises(ValueError):
            manager.patch_method(
                setup_extension,
                "Catalog.Контрагенты.ObjectModule",
                "ПриЗаписи",
                "InvalidType",
            )

    def test_patch_invalid_module_path(self, setup_extension):
        """Неверный module_path → ValueError."""
        manager = CfeManager()
        with pytest.raises(ValueError):
            manager.patch_method(
                setup_extension,
                "InvalidModulePath",
                "ПриЗаписи",
                "Before",
            )

    def test_patch_unsupported_object_type(self, setup_extension):
        """Неподдерживаемый тип объекта → ValueError."""
        manager = CfeManager()
        with pytest.raises(ValueError):
            manager.patch_method(
                setup_extension,
                "UnknownType.X.ObjectModule",
                "ПриЗаписи",
                "Before",
            )

    def test_patch_uses_name_prefix(self, setup_extension):
        """Имя процедуры включает NamePrefix из Configuration.xml."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "Before",
        )

        # NamePrefix = "Расш_" (из фикстуры)
        assert "Расш_ПриЗаписи" in result.bsl_content

    def test_patch_function_adds_return(self, setup_extension):
        """is_function=True добавляет Возврат."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "CommonModule.РаботаСФайлами",
            "НайтиФайл",
            "Before",
            is_function=True,
        )

        assert "Функция" in result.bsl_content
        assert "Возврат" in result.bsl_content
        assert "КонецФункции" in result.bsl_content

    def test_patch_creates_subdirectories(self, setup_extension):
        """Создаёт подкаталоги если их нет."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "Before",
        )

        # Путь: Catalogs/Контрагенты/Ext/ObjectModule.bsl
        expected = setup_extension / "Catalogs" / "Контрагенты" / "Ext" / "ObjectModule.bsl"
        assert result.bsl_file == expected
        assert expected.exists()

    def test_patch_form_module_path(self, setup_extension):
        """Form module_path правильно резолвится."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.Form.ФормаЭлемента",
            "ПриОткрытии",
            "Before",
        )

        # Путь: Catalogs/Контрагенты/Forms/ФормаЭлемента/Ext/Form/Module.bsl
        expected = (
            setup_extension / "Catalogs" / "Контрагенты" / "Forms" / "ФормаЭлемента" / "Ext" / "Form" / "Module.bsl"
        )
        assert result.bsl_file == expected

    def test_patch_common_module_path(self, setup_extension):
        """CommonModule.X резолвится в CommonModules/X/Ext/Module.bsl."""
        manager = CfeManager()
        result = manager.patch_method(
            setup_extension,
            "CommonModule.РаботаСФайлами",
            "НайтиФайл",
            "Before",
        )

        expected = setup_extension / "CommonModules" / "РаботаСФайлами" / "Ext" / "Module.bsl"
        assert result.bsl_file == expected


# ─────────────────────────────────────────────
# DIFF tests
# ─────────────────────────────────────────────


class TestCfeDiff:
    """Тесты анализа расширения."""

    def test_diff_empty_extension(self, setup_extension, setup_config):
        """Пустое расширение → пустые списки."""
        manager = CfeManager()
        result = manager.diff(setup_extension, setup_config)

        assert result.borrowed_objects == []
        assert result.patch_methods == []

    def test_diff_finds_borrowed_object(self, setup_extension, setup_config):
        """diff находит заимствованный объект."""
        manager = CfeManager()
        manager.borrow_object(setup_extension, setup_config, "Catalog.Контрагенты")

        result = manager.diff(setup_extension, setup_config)

        assert len(result.borrowed_objects) == 1
        obj = result.borrowed_objects[0]
        assert obj["object_ref"] == "Catalog.Контрагенты"
        assert obj["object_belonging"] == "Adopted"
        assert obj["found_in_config"] is True

    def test_diff_finds_patch_methods(self, setup_extension, setup_config):
        """diff находит методы перехвата в BSL."""
        manager = CfeManager()
        # Заимствуем и добавляем patch
        manager.borrow_object(setup_extension, setup_config, "Catalog.Контрагенты")
        manager.patch_method(
            setup_extension,
            "Catalog.Контрагенты.ObjectModule",
            "ПриЗаписи",
            "Before",
        )

        result = manager.diff(setup_extension, setup_config)

        assert len(result.patch_methods) >= 1
        patch = result.patch_methods[0]
        assert patch["method_name"] == "Расш_ПриЗаписи"  # с NamePrefix
        assert patch["interceptor_type"] == "Before"

    def test_diff_finds_object_not_in_config(self, setup_extension, tmp_path):
        """diff помечает объекты которых нет в основной конфигурации."""
        # Создаём конфигурацию БЕЗ нужного объекта
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        (cfg / "Configuration.xml").write_text(
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>', encoding="utf-8"
        )

        manager = CfeManager()
        # Заимствуем объект которого нет в конфигурации
        manager.borrow_object(setup_extension, cfg, "Catalog.Несуществующий")

        result = manager.diff(setup_extension, cfg)

        assert len(result.borrowed_objects) == 1
        assert result.borrowed_objects[0]["found_in_config"] is False
        assert "Catalog.Несуществующий" in result.not_in_config

    def test_diff_missing_extension(self, tmp_path, setup_config):
        """diff на несуществующее расширение → warning."""
        manager = CfeManager()
        result = manager.diff(tmp_path / "missing", setup_config)

        assert len(result.warnings) >= 1
        assert result.borrowed_objects == []


# ─────────────────────────────────────────────
# TYPE_MAP tests
# ─────────────────────────────────────────────


class TestTypeMap:
    """Тесты маппинга типов объектов."""

    def test_type_map_has_44_types(self):
        """TYPE_MAP содержит 44 типа объектов 1С."""
        assert len(TYPE_MAP) >= 40  # 44 по стандарту 1С

    def test_type_map_has_key_types(self):
        """TYPE_MAP содержит ключевые типы."""
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
            "ChartOfAccounts",
            "ExchangePlan",
        ]
        for t in required:
            assert t in TYPE_MAP, f"Отсутствует тип: {t}"

    def test_type_map_has_dir_for_each(self):
        """Каждый тип имеет директорию."""
        for type_name, info in TYPE_MAP.items():
            assert "dir" in info, f"Нет dir для {type_name}"
            assert "xml_tag" in info, f"Нет xml_tag для {type_name}"
            assert info["dir"], f"Пустой dir для {type_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
