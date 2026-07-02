"""
Тесты для check_metadata_standards.py.
Проверяем анализ XML метаданных конфигурации 1С.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_metadata_standards import (
    MetadataViolation,
    _get_synonym,
    _parse_object_xml,
    _strip_ns,
    check_metadata,
)


def _make_config_xml(name="Конфигурация", vendor="", version="", name_prefix="", compat="", script="Russian"):
    """Создаёт тестовый Configuration.xml."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration uuid="test-uuid">
    <Properties>
      <Name>{name}</Name>
      <Synonym/>
      <Comment/>
      <NamePrefix>{name_prefix}</NamePrefix>
      <CompatibilityMode>{compat}</CompatibilityMode>
      <DefaultRunMode>ManagedApplication</DefaultRunMode>
      <ScriptVariant>{script}</ScriptVariant>
      <Vendor>{vendor}</Vendor>
      <Version>{version}</Version>
    </Properties>
  </Configuration>
</MetaDataObject>"""


def _make_catalog_xml(name="Товары", synonym="", check_unique="false", code_length="11", list_form="", obj_form=""):
    """Создаёт тестовый Catalog XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Catalog uuid="test-uuid">
    <Properties>
      <Name>{name}</Name>
      <Synonym>{synonym}</Synonym>
      <Comment/>
      <CodeLength>{code_length}</CodeLength>
      <CheckUnique>{check_unique}</CheckUnique>
      <DefaultListForm>{list_form}</DefaultListForm>
      <DefaultObjectForm>{obj_form}</DefaultObjectForm>
    </Properties>
  </Catalog>
</MetaDataObject>"""


def _make_common_module_xml(
    name="ТестовыйМодуль", synonym="", comment="", server="false", server_call="false", client="false"
):
    """Создаёт тестовый CommonModule XML."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <CommonModule uuid="test-uuid">
    <Properties>
      <Name>{name}</Name>
      <Synonym>{synonym}</Synonym>
      <Comment>{comment}</Comment>
      <Server>{server}</Server>
      <ServerCall>{server_call}</ServerCall>
      <ClientManagedApplication>{client}</ClientManagedApplication>
    </Properties>
  </CommonModule>
</MetaDataObject>"""


@pytest.fixture
def config_dir(tmp_path):
    """Создаёт тестовую структуру конфигурации."""
    # Configuration.xml
    (tmp_path / "Configuration.xml").write_text(
        _make_config_xml(vendor="", version="", name_prefix=""), encoding="utf-8"
    )

    # Catalogs/
    cat_dir = tmp_path / "Catalogs"
    cat_dir.mkdir()
    (cat_dir / "Товары.xml").write_text(
        _make_catalog_xml(name="Товары", check_unique="false", code_length="11"), encoding="utf-8"
    )

    # CommonModules/
    cm_dir = tmp_path / "CommonModules"
    cm_dir.mkdir()
    (cm_dir / "ТестовыйМодуль.xml").write_text(
        _make_common_module_xml(name="ТестовыйМодуль", comment="", server="true", server_call="true"), encoding="utf-8"
    )

    return tmp_path


def test_strip_ns():
    """_strip_ns убирает namespace."""
    assert _strip_ns("{http://test}Tag") == "Tag"
    assert _strip_ns("PlainTag") == "PlainTag"


def test_parse_object_xml(tmp_path):
    """_parse_object_xml правильно парсит Catalog."""
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(_make_catalog_xml(name="МойСправочник"), encoding="utf-8")

    obj_type, obj_name, props = _parse_object_xml(xml_file)
    assert obj_type == "Catalog"
    assert obj_name == "МойСправочник"
    assert props is not None


def test_parse_object_xml_invalid(tmp_path):
    """_parse_object_xml для невалидного XML возвращает пустые значения."""
    xml_file = tmp_path / "bad.xml"
    xml_file.write_text("not xml", encoding="utf-8")
    obj_type, obj_name, props = _parse_object_xml(xml_file)
    assert obj_type == ""
    assert obj_name == ""


def test_check_configuration_empty_vendor(config_dir):
    """Пустой Vendor → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "empty-vendor" for v in violations)


def test_check_configuration_empty_version(config_dir):
    """Пустой Version → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "empty-version" for v in violations)


def test_check_configuration_empty_name_prefix(config_dir):
    """Пустой NamePrefix → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "empty-name-prefix" for v in violations)


def test_check_configuration_filled_ok(tmp_path):
    """Заполненные свойства Configuration → нет warnings."""
    (tmp_path / "Configuration.xml").write_text(
        _make_config_xml(vendor="TestCorp", version="1.0", name_prefix="Пр", compat="Version8_3_24"), encoding="utf-8"
    )
    violations = check_metadata(tmp_path)
    config_violations = [v for v in violations if v.object_type == "Configuration"]
    assert len(config_violations) == 0


def test_check_catalog_no_check_unique(config_dir):
    """CheckUnique=false при наличии кода → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "catalog-no-check-unique" and v.object_name == "Товары" for v in violations)


def test_check_catalog_check_unique_ok(tmp_path):
    """CheckUnique=true → нет warning."""
    cat_dir = tmp_path / "Catalogs"
    cat_dir.mkdir()
    (cat_dir / "Товары.xml").write_text(
        _make_catalog_xml(
            name="Товары",
            check_unique="true",
            list_form="Catalog.Товары.Form.ФормаСписка",
            obj_form="Catalog.Товары.Form.ФормаЭлемента",
        ),
        encoding="utf-8",
    )
    violations = check_metadata(tmp_path)
    assert not any(v.rule_id == "catalog-no-check-unique" for v in violations)


def test_check_catalog_no_list_form(config_dir):
    """Нет DefaultListForm → warning."""
    violations = check_metadata(config_dir)
    # Товары не имеет list_form в фикстуре
    assert any(v.rule_id == "catalog-no-list-form" for v in violations)


def test_check_common_module_no_comment(config_dir):
    """Comment не заполнен → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "module-no-comment" and v.object_name == "ТестовыйМодуль" for v in violations)


def test_check_common_module_servercall_no_suffix(tmp_path):
    """ServerCall без суффикса ВызовСервера → warning."""
    cm_dir = tmp_path / "CommonModules"
    cm_dir.mkdir()
    (cm_dir / "Модуль.xml").write_text(
        _make_common_module_xml(name="Модуль", server="true", server_call="true"), encoding="utf-8"
    )
    violations = check_metadata(tmp_path)
    assert any(v.rule_id == "module-servercall-no-suffix" for v in violations)


def test_check_common_module_servercall_with_suffix_ok(tmp_path):
    """ServerCall с суффиксом ВызовСервера → нет warning."""
    cm_dir = tmp_path / "CommonModules"
    cm_dir.mkdir()
    (cm_dir / "МодульВызовСервера.xml").write_text(
        _make_common_module_xml(name="МодульВызовСервера", server="true", server_call="true", comment="Тест"),
        encoding="utf-8",
    )
    violations = check_metadata(tmp_path)
    assert not any(v.rule_id == "module-servercall-no-suffix" for v in violations)


def test_check_object_empty_synonym(config_dir):
    """Пустой синоним → warning."""
    violations = check_metadata(config_dir)
    assert any(v.rule_id == "empty-synonym" for v in violations)


def test_check_object_name_with_spaces(tmp_path):
    """Имя с пробелами → error."""
    cat_dir = tmp_path / "Catalogs"
    cat_dir.mkdir()
    (cat_dir / "test.xml").write_text(_make_catalog_xml(name="Имя С Пробелами"), encoding="utf-8")
    violations = check_metadata(tmp_path)
    assert any(v.rule_id == "name-with-spaces" and v.severity == "error" for v in violations)


def test_check_object_name_starts_with_digit(tmp_path):
    """Имя начинается с цифры → error."""
    cat_dir = tmp_path / "Catalogs"
    cat_dir.mkdir()
    (cat_dir / "test.xml").write_text(_make_catalog_xml(name="1Товары"), encoding="utf-8")
    violations = check_metadata(tmp_path)
    assert any(v.rule_id == "name-starts-with-digit" for v in violations)


def test_format_violations_empty():
    """Пустой список → сообщение об отсутствии нарушений."""
    from check_metadata_standards import format_violations

    result = format_violations([])
    assert "не найдено" in result.lower()


def test_format_violations_text():
    """Текстовый формат вывода."""
    from check_metadata_standards import format_violations

    violations = [
        MetadataViolation(
            file="test.xml",
            object_type="Catalog",
            object_name="Товары",
            rule_id="test-rule",
            severity="warning",
            message="Test message",
        )
    ]
    result = format_violations(violations)
    assert "Catalog" in result
    assert "Товары" in result
    assert "test-rule" in result


def test_format_violations_json():
    """JSON формат вывода."""
    import json

    from check_metadata_standards import format_violations

    violations = [
        MetadataViolation(
            file="test.xml",
            object_type="Catalog",
            object_name="Товары",
            rule_id="test-rule",
            severity="error",
            message="Test error",
        )
    ]
    result = format_violations(violations, "json")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["rule_id"] == "test-rule"


def test_nonexistent_dir(tmp_path):
    """Несуществующая директория → нет нарушений."""
    violations = check_metadata(tmp_path / "nonexistent")
    assert violations == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
