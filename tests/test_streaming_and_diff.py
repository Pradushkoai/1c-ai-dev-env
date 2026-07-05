"""
D2.5 + D2.6 (2026-07-05): Тесты для streaming parser и config diff engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.config_diff import ConfigDiff, DiffChange, DiffResult


class TestStreamingParser:
    """D2.5: streaming-парсинг через lxml.iterparse."""

    def test_is_streaming_available_returns_bool(self) -> None:
        """is_streaming_available возвращает bool."""
        from src.services.metadata.streaming_parser import is_streaming_available
        result = is_streaming_available()
        assert isinstance(result, bool)

    def test_stream_parse_raises_without_lxml(self, tmp_path: Path) -> None:
        """stream_parse_config raises ImportError если lxml не установлен."""
        from src.services.metadata.streaming_parser import stream_parse_config, _check_lxml

        if _check_lxml():
            pytest.skip("lxml установлен — тест пропускается")

        with pytest.raises(ImportError, match="lxml"):
            stream_parse_config(tmp_path, tmp_path / "out.json")

    def test_streaming_parser_module_exists(self) -> None:
        """Модуль streaming_parser существует."""
        from src.services.metadata import streaming_parser
        assert hasattr(streaming_parser, "stream_parse_config")
        assert hasattr(streaming_parser, "is_streaming_available")


class TestConfigDiff:
    """D2.6: Configuration diff engine."""

    def test_diff_detects_added(self, tmp_path: Path) -> None:
        """Diff находит добавленные объекты."""
        old = {"version": "1.0", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"}
        ]}
        new = {"version": "1.1", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"},
            {"type": "Document", "name": "Заказ", "uuid": "bbb"},
        ]}

        old_path = tmp_path / "old.json"
        new_path = tmp_path / "new.json"
        old_path.write_text(json.dumps(old), encoding="utf-8")
        new_path.write_text(json.dumps(new), encoding="utf-8")

        differ = ConfigDiff()
        result = differ.diff(old_path, new_path)

        assert result.added_count == 1
        assert result.removed_count == 0
        assert result.modified_count == 0
        assert result.unchanged_count == 1
        assert len(result.changes) == 1
        assert result.changes[0].change_type == "added"
        assert result.changes[0].object_name == "Заказ"

    def test_diff_detects_removed(self, tmp_path: Path) -> None:
        """Diff находит удалённые объекты."""
        old = {"version": "1.0", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"},
            {"type": "Document", "name": "Заказ", "uuid": "bbb"},
        ]}
        new = {"version": "1.1", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"},
        ]}

        old_path = tmp_path / "old.json"
        new_path = tmp_path / "new.json"
        old_path.write_text(json.dumps(old), encoding="utf-8")
        new_path.write_text(json.dumps(new), encoding="utf-8")

        differ = ConfigDiff()
        result = differ.diff(old_path, new_path)

        assert result.removed_count == 1
        assert result.changes[0].change_type == "removed"
        assert result.changes[0].object_name == "Заказ"

    def test_diff_detects_modified(self, tmp_path: Path) -> None:
        """Diff находит изменённые объекты (UUID изменился)."""
        old = {"version": "1.0", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"},
        ]}
        new = {"version": "1.1", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "bbb"},
        ]}

        old_path = tmp_path / "old.json"
        new_path = tmp_path / "new.json"
        old_path.write_text(json.dumps(old), encoding="utf-8")
        new_path.write_text(json.dumps(new), encoding="utf-8")

        differ = ConfigDiff()
        result = differ.diff(old_path, new_path)

        assert result.modified_count == 1
        assert result.changes[0].change_type == "modified"
        assert result.changes[0].details == "UUID changed"

    def test_diff_summary(self, tmp_path: Path) -> None:
        """DiffResult.summary() работает."""
        result = DiffResult(added_count=2, removed_count=1, modified_count=3, unchanged_count=5)
        summary = result.summary()
        assert "Added: 2" in summary
        assert "Removed: 1" in summary
        assert "Modified: 3" in summary
        assert "Unchanged: 5" in summary

    def test_diff_to_dict(self, tmp_path: Path) -> None:
        """DiffResult.to_dict() работает."""
        result = DiffResult(old_version="1.0", new_version="1.1")
        result.changes.append(DiffChange(
            change_type="added",
            object_type="Catalog",
            object_name="Test",
        ))
        d = result.to_dict()
        assert d["old_version"] == "1.0"
        assert d["new_version"] == "1.1"
        assert len(d["changes"]) == 1
        assert d["changes"][0]["change_type"] == "added"

    def test_diff_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Diff raises FileNotFoundError если файл не существует."""
        differ = ConfigDiff()
        with pytest.raises(FileNotFoundError):
            differ.diff(tmp_path / "missing.json", tmp_path / "also_missing.json")

    def test_diff_change_str(self) -> None:
        """DiffChange.__str__ работает."""
        change = DiffChange(change_type="added", object_type="Catalog", object_name="Test")
        s = str(change)
        assert "+" in s
        assert "Catalog" in s
        assert "Test" in s

    def test_diff_no_changes(self, tmp_path: Path) -> None:
        """Diff с одинаковыми файлами — 0 changes."""
        data = {"version": "1.0", "objects": [
            {"type": "Catalog", "name": "Товары", "uuid": "aaa"},
        ]}
        path = tmp_path / "same.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        differ = ConfigDiff()
        result = differ.diff(path, path)

        assert result.added_count == 0
        assert result.removed_count == 0
        assert result.modified_count == 0
        assert result.unchanged_count == 1
        assert len(result.changes) == 0
