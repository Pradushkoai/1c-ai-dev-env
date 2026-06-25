"""
Тесты для build_api_reference.py.
Тестируем парсинг .bsl файлов (Процедура/Функция Экспорт) и комментарии.
Импорт через importlib с подменой sys.argv, т.к. скрипт использует argparse при импорте.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    """Загрузить build_api_reference как модуль с фейковым argparse."""
    script = Path(__file__).parent.parent / "scripts" / "build_api_reference.py"

    # Подменяем sys.argv, чтобы argparse не падал
    old_argv = sys.argv
    sys.argv = [
        "build_api_reference.py",
        "--config", "test",
        "--config-dir", "/tmp/test",
        "--output-md", "/tmp/test.md",
        "--output-json", "/tmp/test.json",
        "--title", "Test",
    ]
    try:
        spec = importlib.util.spec_from_file_location("build_api_reference", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.argv = old_argv


@pytest.fixture(scope="module")
def api():
    """Фикстура — загруженный модуль build_api_reference."""
    return _load_module()


def test_parse_module_bsl_export_function(api, tmp_path):
    """parse_module_bsl извлекает экспортную функцию с документацией."""
    bsl_content = """// Поиск элемента справочника по коду.
//
// Параметры:
//  Код - Строка - код элемента
//  Справочник - СправочникСсылка - ссылка на справочник
//
// Возвращаемое значение:
//  СправочникСсылка - найденный элемент
Функция НайтиПоКоду(Код, Справочник) Экспорт
    Возврат Неопределено;
КонецФункции
"""
    bsl_path = tmp_path / "module.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")

    methods = api.parse_module_bsl(str(bsl_path))

    assert len(methods) == 1
    m = methods[0]
    assert m["name"] == "НайтиПоКоду"
    assert m["type"] == "Функция"
    assert "Экспорт" in m["signature"]
    assert "Поиск элемента" in m["description"]
    assert "СправочникСсылка" in m["returns"]
    assert len(m["params"]) == 2
    assert m["params"][0]["name"] == "Код"


def test_parse_module_bsl_export_procedure(api, tmp_path):
    """parse_module_bsl извлекает экспортную процедуру."""
    bsl_content = """// Удаление элемента.
Процедура УдалитьЭлемент(Ссылка) Экспорт
КонецПроцедуры
"""
    bsl_path = tmp_path / "mod.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")

    methods = api.parse_module_bsl(str(bsl_path))

    assert len(methods) == 1
    assert methods[0]["name"] == "УдалитьЭлемент"
    assert methods[0]["type"] == "Процедура"


def test_parse_module_bsl_skips_non_export(api, tmp_path):
    """parse_module_bsl НЕ извлекает приватные (без Экспорт) методы."""
    bsl_content = """Процедура ВнутренняяПроцедура()
КонецПроцедуры

Функция ВнутренняяФункция() 
    Возврат 1;
КонецФункции

Функция Публичная() Экспорт
    Возврат 2;
КонецФункции
"""
    bsl_path = tmp_path / "mod.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")

    methods = api.parse_module_bsl(str(bsl_path))
    names = [m["name"] for m in methods]

    assert "Публичная" in names
    assert "ВнутренняяПроцедура" not in names
    assert "ВнутренняяФункция" not in names


def test_parse_module_bsl_multiple_methods(api, tmp_path):
    """parse_module_bsl извлекает несколько экспортных методов."""
    bsl_content = """
// Метод 1.
Функция Метод1() Экспорт
    Возврат 1;
КонецФункции

// Метод 2.
Процедура Метод2(Парам) Экспорт
КонецПроцедуры

// Метод 3.
Функция Метод3(А, Б = 0) Экспорт
    Возврат А + Б;
КонецФункции
"""
    bsl_path = tmp_path / "mod.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")

    methods = api.parse_module_bsl(str(bsl_path))
    names = [m["name"] for m in methods]
    assert len(methods) == 3
    assert "Метод1" in names
    assert "Метод2" in names
    assert "Метод3" in names


def test_parse_comment_block_structure(api):
    """parse_comment_block корректно разбирает секции."""
    comment = """// Краткое описание метода.
//
// Параметры:
//  Код - Строка - код элемента
//  Имя - Строка - имя элемента
//
// Возвращаемое значение:
//  СправочникСсылка - найденный элемент
"""
    # parse_comment_block ожидает сырой текст с //
    result = api.parse_comment_block(comment)

    assert "Краткое описание метода" in result["description"]
    assert len(result["params"]) == 2
    assert result["params"][0]["name"] == "Код"
    assert result["params"][0]["type"] == "Строка"
    assert "СправочникСсылка" in result["returns"]


def test_parse_comment_block_empty(api):
    """parse_comment_block для пустого блока возвращает пустой dict."""
    result = api.parse_comment_block("")
    assert result == {} or "description" in result


def test_parse_module_bsl_empty_file(api, tmp_path):
    """parse_module_bsl для пустого файла возвращает пустой список."""
    bsl_path = tmp_path / "empty.bsl"
    bsl_path.write_text("", encoding="utf-8")
    assert api.parse_module_bsl(str(bsl_path)) == []


def test_parse_module_bsl_nonexistent(api, tmp_path):
    """parse_module_bsl для несуществующего файла возвращает пустой список."""
    assert api.parse_module_bsl(str(tmp_path / "nope.bsl")) == []


def test_parse_module_xml(api, tmp_path):
    """parse_module_xml извлекает свойства общего модуля."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <CommonModule>
    <Properties>
      <Name>МойМодуль</Name>
      <Synonym><item><content>Мой модуль</content></item></Synonym>
      <Comment>Тестовый модуль</Comment>
      <Server>true</Server>
      <ClientManagedApplication>false</ClientManagedApplication>
      <Global>false</Global>
      <ServerCall>true</ServerCall>
    </Properties>
  </CommonModule>
</ConfigDumpInfo>
"""
    xml_path = tmp_path / "module.xml"
    xml_path.write_text(xml_content, encoding="utf-8")

    result = api.parse_module_xml(str(xml_path))

    assert result is not None
    assert result["name"] == "МойМодуль"
    assert result["synonym"] == "Мой модуль"
    assert result["server"] == "true"
    assert result["server_call"] == "true"
    assert result["global"] == "false"


def test_parse_module_xml_invalid(api, tmp_path):
    """parse_module_xml для невалидного XML возвращает None."""
    xml_path = tmp_path / "bad.xml"
    xml_path.write_text("<<<NOT XML>>>", encoding="utf-8")
    assert api.parse_module_xml(str(xml_path)) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
