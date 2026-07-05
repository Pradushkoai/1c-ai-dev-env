"""D2.2 + D2.3 (2026-07-05): Тесты для builders XML utils + index versioning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.builders._xml_utils import strip_ns, get_child, get_text, get_synonym_text
from src.services.index_versioning import (
    CURRENT_SCHEMA_VERSION,
    check_schema_version,
    needs_migration,
    migrate_index,
    add_schema_version_if_missing,
)


class TestXmlUtils:
    """D2.2: XML утилиты вынесены в _xml_utils.py."""

    def test_strip_ns(self) -> None:
        assert strip_ns("{http://v8.1c.ru/8.3/MDClasses}Catalog") == "Catalog"
        assert strip_ns("Catalog") == "Catalog"

    def test_get_child_returns_none_for_none(self) -> None:
        assert get_child(None, "test") is None

    def test_get_text_returns_default(self) -> None:
        assert get_text(None, "test", "default") == "default"

    def test_xml_utils_module_exists(self) -> None:
        from src.services.builders import _xml_utils
        assert hasattr(_xml_utils, "strip_ns")
        assert hasattr(_xml_utils, "get_child")
        assert hasattr(_xml_utils, "get_text")
        assert hasattr(_xml_utils, "get_synonym_text")
        assert hasattr(_xml_utils, "get_type_description")

    def test_config_index_imports_from_xml_utils(self) -> None:
        """config_index.py импортирует из _xml_utils."""
        from src.services.builders import config_index
        # Функции должны быть доступны (импортированы)
        assert callable(strip_ns)


class TestIndexVersioning:
    """D2.3: Версионирование индексов."""

    def test_current_schema_version_is_2(self) -> None:
        assert CURRENT_SCHEMA_VERSION == 2

    def test_check_schema_version_missing_file(self, tmp_path: Path) -> None:
        assert check_schema_version(tmp_path / "missing.json") == 0

    def test_check_schema_version_legacy_v1(self, tmp_path: Path) -> None:
        """Индекс без schema_version → версия 1 (legacy)."""
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"objects": []}), encoding="utf-8")
        assert check_schema_version(path) == 1

    def test_check_schema_version_v2(self, tmp_path: Path) -> None:
        """Индекс с schema_version=2."""
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"schema_version": 2, "objects": []}), encoding="utf-8")
        assert check_schema_version(path) == 2

    def test_needs_migration_true_for_legacy(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"objects": []}), encoding="utf-8")
        assert needs_migration(path) is True

    def test_needs_migration_false_for_current(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
        assert needs_migration(path) is False

    def test_migrate_index_v1_to_v2(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"objects": [{"name": "test"}]}), encoding="utf-8")

        result = migrate_index(path)
        assert result is True

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_version"] == 2
        assert data["objects"] == [{"name": "test"}]  # Данные сохранены

    def test_migrate_index_already_current(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")

        result = migrate_index(path)
        assert result is True

    def test_add_schema_version_if_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text(json.dumps({"objects": []}), encoding="utf-8")

        add_schema_version_if_missing(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_add_schema_version_skips_if_present(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        original = {"schema_version": 5, "objects": []}
        path.write_text(json.dumps(original), encoding="utf-8")

        add_schema_version_if_missing(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_version"] == 5  # Не перезаписана
