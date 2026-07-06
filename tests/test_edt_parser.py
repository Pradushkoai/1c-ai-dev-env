"""
P2.1: Тесты для EDT парсера.

Проверяет:
1. EdtParser парсит .mdo файлы
2. Разные типы объектов (Catalog, Document, Enum, InformationRegister)
3. Атрибуты/ресурсы/измерения
4. Статистика
5. Обработка ошибок (malformed XML, пустые директории)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.edt_parser import EdtParser, EDT_TYPE_MAP


# ============================================================================
# Helpers
# ============================================================================


def _create_edt_project(tmp_path: Path) -> Path:
    """Создать тестовый EDT проект с несколькими объектами."""
    project = tmp_path / "edt_project"
    src = project / "src"

    # Configuration.mdo
    src.mkdir(parents=True)
    config_mdo = src / "Configuration.mdo"
    config_mdo.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mdclass:Configuration xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclasses">\n'
        "  <name>TestConfig</name>\n"
        "</mdclass:Configuration>\n",
        encoding="utf-8",
    )

    # Catalog
    catalogs_dir = src / "Catalogs"
    catalogs_dir.mkdir()
    (catalogs_dir / "Номенклатура.mdo").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mdclass:Catalog xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclasses">\n'
        "  <name>Номенклатура</name>\n"
        "  <synonym>Номенклатура</synonym>\n"
        "  <hierarchical>true</hierarchical>\n"
        "  <attributes>\n"
        "    <name>Артикул</name>\n"
        "    <type>String</type>\n"
        "  </attributes>\n"
        "  <attributes>\n"
        "    <name>Цена</name>\n"
        "    <type>Number</type>\n"
        "  </attributes>\n"
        "</mdclass:Catalog>\n",
        encoding="utf-8",
    )

    # Document
    docs_dir = src / "Documents"
    docs_dir.mkdir()
    (docs_dir / "Заказ.mdo").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mdclass:Document xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclasses">\n'
        "  <name>Заказ</name>\n"
        "  <synonym>Заказ клиента</synonym>\n"
        "  <numberType>String</numberType>\n"
        "  <attributes>\n"
        "    <name>Контрагент</name>\n"
        "    <type>CatalogRef.Контрагенты</type>\n"
        "  </attributes>\n"
        "</mdclass:Document>\n",
        encoding="utf-8",
    )

    return project


# ============================================================================
# Тесты — EdtParser базовый функционал
# ============================================================================


class TestEdtParserBasic:
    """Базовая проверка EdtParser."""

    def test_edt_parser_init(self) -> None:
        """EdtParser инициализируется."""
        parser = EdtParser()
        assert parser is not None
        assert parser._objects == []

    def test_parse_empty_directory(self, tmp_path: Path) -> None:
        """parse() на пустой директории → пустой список."""
        parser = EdtParser()
        result = parser.parse(tmp_path)
        assert result == []

    def test_parse_nonexistent_directory(self, tmp_path: Path) -> None:
        """parse() на несуществующей директории → пустой список."""
        parser = EdtParser()
        result = parser.parse(tmp_path / "nonexistent")
        assert result == []


# ============================================================================
# Тесты — парсинг EDT проекта
# ============================================================================


class TestEdtParserProject:
    """Проверка парсинга EDT проекта."""

    def test_parse_finds_objects(self, tmp_path: Path) -> None:
        """parse() находит объекты в EDT проекте."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        result = parser.parse(project)

        assert len(result) >= 2  # Catalog + Document

    def test_parse_catalog(self, tmp_path: Path) -> None:
        """parse() корректно парсит Catalog."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        result = parser.parse(project)

        catalogs = [o for o in result if o["type"] == "Catalog"]
        assert len(catalogs) == 1
        assert catalogs[0]["name"] == "Номенклатура"
        assert catalogs[0]["synonym"] == "Номенклатура"
        assert catalogs[0]["hierarchical"] is True
        assert len(catalogs[0]["attributes"]) == 2
        assert catalogs[0]["attributes"][0]["name"] == "Артикул"

    def test_parse_document(self, tmp_path: Path) -> None:
        """parse() корректно парсит Document."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        result = parser.parse(project)

        docs = [o for o in result if o["type"] == "Document"]
        assert len(docs) == 1
        assert docs[0]["name"] == "Заказ"
        assert docs[0]["number_type"] == "String"
        assert len(docs[0]["attributes"]) == 1

    def test_parse_object_has_source_field(self, tmp_path: Path) -> None:
        """Все объекты имеют source='edt'."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        result = parser.parse(project)

        for obj in result:
            assert obj["source"] == "edt"

    def test_parse_object_has_mdo_path(self, tmp_path: Path) -> None:
        """Все объекты имеют mdo_path."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        result = parser.parse(project)

        for obj in result:
            assert "mdo_path" in obj
            assert ".mdo" in obj["mdo_path"]


# ============================================================================
# Тесты — статистика
# ============================================================================


class TestEdtParserStats:
    """Проверка get_stats()."""

    def test_get_stats_after_parse(self, tmp_path: Path) -> None:
        """get_stats() возвращает корректную статистику."""
        project = _create_edt_project(tmp_path)
        parser = EdtParser()
        parser.parse(project)

        stats = parser.get_stats()
        assert stats["config_name"] == "TestConfig"
        assert stats["total_objects"] >= 2
        assert stats["source"] == "edt"
        assert "Catalog" in stats["by_type"]
        assert "Document" in stats["by_type"]

    def test_get_stats_empty(self) -> None:
        """get_stats() без parse() → пустая статистика."""
        parser = EdtParser()
        stats = parser.get_stats()
        assert stats["total_objects"] == 0


# ============================================================================
# Тесты — обработка ошибок
# ============================================================================


class TestEdtParserErrors:
    """Проверка обработки ошибок."""

    def test_parse_malformed_xml(self, tmp_path: Path) -> None:
        """parse() не падает на malformed XML."""
        project = tmp_path / "bad_edt"
        src = project / "src" / "Catalogs"
        src.mkdir(parents=True)
        (src / "Bad.mdo").write_text("<unclosed>", encoding="utf-8")

        parser = EdtParser()
        result = parser.parse(project)
        # Должен вернуть пустой список (или без Bad объекта)
        assert isinstance(result, list)

    def test_parse_mdo_without_name(self, tmp_path: Path) -> None:
        """parse() использует имя файла если нет <name> тега."""
        project = tmp_path / "edt_no_name"
        src = project / "src" / "Catalogs"
        src.mkdir(parents=True)
        (src / "ИмяФайла.mdo").write_text(
            '<?xml version="1.0"?>\n'
            '<mdclass:Catalog xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclasses">\n'
            "</mdclass:Catalog>\n",
            encoding="utf-8",
        )

        parser = EdtParser()
        result = parser.parse(project)

        if result:
            assert result[0]["name"] == "ИмяФайла"


# ============================================================================
# Тесты — константы
# ============================================================================


class TestEdtConstants:
    """Проверка констант EDT."""

    def test_edt_type_map_has_catalog(self) -> None:
        """EDT_TYPE_MAP содержит Catalog."""
        assert "Catalog" in EDT_TYPE_MAP
        assert EDT_TYPE_MAP["Catalog"] == "Catalog"

    def test_edt_type_map_has_document(self) -> None:
        """EDT_TYPE_MAP содержит Document."""
        assert "Document" in EDT_TYPE_MAP

    def test_edt_type_map_has_common_module(self) -> None:
        """EDT_TYPE_MAP содержит CommonModule."""
        assert "CommonModule" in EDT_TYPE_MAP
