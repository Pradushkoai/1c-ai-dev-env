"""
Тесты для build_config_index_generic.py.
Проверяем парсинг Configuration.xml, ConfigDumpInfo.xml, генерацию индекса.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    """Загрузить build_config_index_generic как модуль."""
    script = Path(__file__).parent.parent / "scripts" / "build_config_index_generic.py"
    spec = importlib.util.spec_from_file_location("build_config_index_generic", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def idx():
    """Фикстура — загруженный модуль build_config_index_generic."""
    return _load_module()


# === Хелперы ===

def test_strip_ns(idx):
    """strip_ns убирает namespace из тега."""
    assert idx.strip_ns("{http://namespace}Tag") == "Tag"
    assert idx.strip_ns("PlainTag") == "PlainTag"


def test_get_child_and_text(idx):
    """get_child и get_text находят дочерние элементы."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring("<Root><Name>Тест</Name><Other>Значение</Other></Root>")
    child = idx.get_child(root, "Name")
    assert child is not None
    assert child.text == "Тест"
    assert idx.get_text(root, "Name") == "Тест"
    assert idx.get_text(root, "Missing", "default") == "default"


def test_get_synonym_text(idx):
    """get_synonym_text извлекает синоним из <item><content>."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring("""
    <Root>
        <Synonym>
            <item>
                <content>Мой справочник</content>
            </item>
        </Synonym>
    </Root>
    """)
    assert idx.get_synonym_text(root) == "Мой справочник"


# === parse_configuration_xml ===

def test_parse_configuration_xml_valid(idx, tmp_path):
    """parse_configuration_xml извлекает свойства и подсистемы."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <Configuration>
    <Properties>
      <Name>УправлениеТорговлей</Name>
      <Version>11.3.4</Version>
      <Vendor>1C</Vendor>
      <ScriptVariant>Russian</ScriptVariant>
      <Synonym>
        <item><content>Управление торговлей</content></item>
      </Synonym>
    </Properties>
    <ChildObjects>
      <Subsystem>Стандартные подсистемы</Subsystem>
      <Subsystem>Продажи</Subsystem>
    </ChildObjects>
  </Configuration>
</ConfigDumpInfo>
"""
    xml_path = tmp_path / "Configuration.xml"
    xml_path.write_text(xml_content, encoding="utf-8")

    props, subsystems = idx.parse_configuration_xml(str(xml_path))

    assert props["Name"] == "УправлениеТорговлей"
    assert props["Version"] == "11.3.4"
    assert props["Vendor"] == "1C"
    assert props["ScriptVariant"] == "Russian"
    assert props["Synonym"] == "Управление торговлей"
    assert len(subsystems) == 2
    assert "Продажи" in subsystems


def test_parse_configuration_xml_missing_file(idx, tmp_path):
    """parse_configuration_xml для несуществующего файла возвращает ({}, [])."""
    props, subsystems = idx.parse_configuration_xml(str(tmp_path / "nope.xml"))
    assert props == {}
    assert subsystems == []


def test_parse_configuration_xml_no_configuration_element(idx, tmp_path):
    """parse_configuration_xml без <Configuration> возвращает ({}, [])."""
    xml_path = tmp_path / "empty.xml"
    xml_path.write_text("<?xml version='1.0'?><ConfigDumpInfo/>", encoding="utf-8")
    props, subsystems = idx.parse_configuration_xml(str(xml_path))
    assert props == {}
    assert subsystems == []


# === parse_dumpinfo ===

def _write_dumpinfo(tmp_path: Path, objects_xml: str) -> Path:
    """Создать ConfigDumpInfo.xml с указанными Metadata элементами."""
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  {objects_xml}
</ConfigDumpInfo>
"""
    p = tmp_path / "ConfigDumpInfo.xml"
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_dumpinfo_catalog(idx, tmp_path):
    """parse_dumpinfo находит Catalog с UUID."""
    xml = '<Metadata name="Catalog.Товары" id="abc-123"/>'
    path = _write_dumpinfo(tmp_path, xml)

    objects = idx.parse_dumpinfo(str(path))

    assert "Catalog" in objects
    assert "Товары" in objects["Catalog"]
    obj = objects["Catalog"]["Товары"]
    assert obj["name"] == "Товары"
    assert obj["uuid"] == "abc-123"


def test_parse_dumpinfo_document_with_form(idx, tmp_path):
    """parse_dumpinfo извлекает формы документа."""
    xml = """
    <Metadata name="Document.Заказ" id="doc-1"/>
    <Metadata name="Document.Заказ.Form.ФормаДокумента" id="form-1"/>
    """
    path = _write_dumpinfo(tmp_path, xml)

    objects = idx.parse_dumpinfo(str(path))

    doc = objects["Document"]["Заказ"]
    assert doc["uuid"] == "doc-1"
    assert "ФормаДокумента" in doc["forms"]


def test_parse_dumpinfo_with_template_and_command(idx, tmp_path):
    """parse_dumpinfo извлекает шаблоны и команды."""
    xml = """
    <Metadata name="Catalog.Клиенты" id="cat-1"/>
    <Metadata name="Catalog.Клиенты.Template.Печать" id="tpl-1"/>
    <Metadata name="Catalog.Клиенты.Command.Открыть" id="cmd-1"/>
    """
    path = _write_dumpinfo(tmp_path, xml)

    objects = idx.parse_dumpinfo(str(path))
    cat = objects["Catalog"]["Клиенты"]
    assert "Печать" in cat["templates"]
    assert "Открыть" in cat["commands"]


def test_parse_dumpinfo_with_modules(idx, tmp_path):
    """parse_dumpinfo извлекает модули объектов."""
    xml = """
    <Metadata name="Catalog.Склады" id="c-1"/>
    <Metadata name="Catalog.Склады.ObjectModule" id="m-1"/>
    <Metadata name="Catalog.Склады.ManagerModule" id="m-2"/>
    """
    path = _write_dumpinfo(tmp_path, xml)

    objects = idx.parse_dumpinfo(str(path))
    cat = objects["Catalog"]["Склады"]
    assert "ObjectModule" in cat["modules"]
    assert "ManagerModule" in cat["modules"]


def test_parse_dumpinfo_with_fields(idx, tmp_path):
    """parse_dumpinfo извлекает реквизиты и измерения."""
    xml = """
    <Metadata name="InformationRegister.Цены" id="r-1"/>
    <Metadata name="InformationRegister.Цены.Dimension.Номенклатура" id="d-1"/>
    <Metadata name="InformationRegister.Цены.Resource.Цена" id="res-1"/>
    """
    path = _write_dumpinfo(tmp_path, xml)

    objects = idx.parse_dumpinfo(str(path))
    reg = objects["InformationRegister"]["Цены"]
    field_names = [f["name"] for f in reg["fields"]]
    assert "Номенклатура" in field_names
    assert "Цена" in field_names
    # Проверим типы
    dim = next(f for f in reg["fields"] if f["name"] == "Номенклатура")
    assert dim["type"] == "Dimension"
    res = next(f for f in reg["fields"] if f["name"] == "Цена")
    assert res["type"] == "Resource"


def test_parse_dumpinfo_missing_file(idx, tmp_path):
    """parse_dumpinfo для несуществующего файла возвращает пустой dict."""
    objects = idx.parse_dumpinfo(str(tmp_path / "nope.xml"))
    assert len(objects) == 0


def test_parse_dumpinfo_unknown_type_skipped(idx, tmp_path):
    """parse_dumpinfo пропускает неизвестные типы."""
    xml = '<Metadata name="UnknownType.SomeName" id="x-1"/>'
    path = _write_dumpinfo(tmp_path, xml)
    objects = idx.parse_dumpinfo(str(path))
    assert "UnknownType" not in objects


# === build_index ===

def test_build_index_generates_markdown(idx, tmp_path):
    """build_index создаёт Markdown файл с метаданными."""
    # Минимальная конфигурация
    (tmp_path / "Configuration.xml").write_text("""<?xml version="1.0"?>
<ConfigDumpInfo>
  <Configuration>
    <Properties>
      <Name>Тестовая</Name>
      <Version>1.0</Version>
      <Vendor>Test</Vendor>
    </Properties>
  </Configuration>
</ConfigDumpInfo>
""", encoding="utf-8")

    (tmp_path / "ConfigDumpInfo.xml").write_text("""<?xml version="1.0"?>
<ConfigDumpInfo>
  <Metadata name="Catalog.Товары" id="c-1"/>
  <Metadata name="Document.Заказ" id="d-1"/>
</ConfigDumpInfo>
""", encoding="utf-8")

    output = tmp_path / "index.md"
    idx.build_index(str(tmp_path), str(output), "Тестовая конфигурация")

    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "Тестовая конфигурация" in content
    assert "Товары" in content
    assert "Заказ" in content
    assert "Catalog" in content or "Справочник" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
