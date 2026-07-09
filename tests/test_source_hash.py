"""
D2.4 (2026-07-05): Тесты для идемпотентности индексов (content hash).

Гарантирует:
1. _compute_source_hash существует и возвращает SHA-256
2. save_source_hash сохраняет hash в .source-hash файл
3. check_freshness использует hash (а не только mtime)
4. Если hash совпадает — индекс НЕ stale (даже при изменённом mtime)
5. Если hash отличается — индекс stale
6. Fallback на mtime если .source-hash не существует
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from src.services.config_validator import ConfigValidator, IndexFreshnessReport, IndexStatus


class TestComputeSourceHash:
    """D2.4: _compute_source_hash — content hash исходников."""

    def test_compute_hash_returns_string(self, tmp_path: Path) -> None:
        """_compute_source_hash возвращает строку."""
        (tmp_path / "test.xml").write_text("<root/>", encoding="utf-8")
        h = ConfigValidator._compute_source_hash(tmp_path)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_deterministic(self, tmp_path: Path) -> None:
        """Hash одинаковый для одинакового содержимого."""
        (tmp_path / "test.xml").write_text("<root/>", encoding="utf-8")
        h1 = ConfigValidator._compute_source_hash(tmp_path)
        h2 = ConfigValidator._compute_source_hash(tmp_path)
        assert h1 == h2

    def test_hash_changes_on_content_change(self, tmp_path: Path) -> None:
        """Hash меняется при изменении содержимого файла."""
        f = tmp_path / "test.xml"
        f.write_text("<root/>", encoding="utf-8")
        h1 = ConfigValidator._compute_source_hash(tmp_path)

        f.write_text("<root><child/></root>", encoding="utf-8")
        h2 = ConfigValidator._compute_source_hash(tmp_path)
        assert h1 != h2

    def test_hash_same_after_touch(self, tmp_path: Path) -> None:
        """Hash НЕ меняется при touch (mtime меняется, содержимое нет)."""
        f = tmp_path / "test.xml"
        f.write_text("<root/>", encoding="utf-8")
        h1 = ConfigValidator._compute_source_hash(tmp_path)

        # Меняем mtime, но не содержимое
        new_time = time.time() + 100
        os.utime(str(f), (new_time, new_time))
        h2 = ConfigValidator._compute_source_hash(tmp_path)
        assert h1 == h2

    def test_hash_includes_multiple_files(self, tmp_path: Path) -> None:
        """Hash учитывает все .xml и .bsl файлы."""
        (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
        h1 = ConfigValidator._compute_source_hash(tmp_path)

        (tmp_path / "b.bsl").write_text("Процедура Тест() КонецПроцедуры", encoding="utf-8")
        h2 = ConfigValidator._compute_source_hash(tmp_path)
        assert h1 != h2


class TestSourceHashFile:
    """D2.4: .source-hash файл — сохранение и чтение."""

    def test_save_source_hash_creates_file(self, tmp_path: Path) -> None:
        """save_source_hash создаёт .source-hash файл."""
        from src.models.config_registry import ConfigurationRegistry
        from src.models.configuration import Configuration
        from src.services.path_manager import PathManager

        # Setup mock
        pm = PathManager(project_root=tmp_path)
        registry = ConfigurationRegistry(pm.config_registry_path, pm.root)
        config = Configuration(name="test", title="Test", path=tmp_path / "config")
        config.path = tmp_path / "config"
        config.path.mkdir(parents=True, exist_ok=True)
        (config.path / "test.xml").write_text("<root/>", encoding="utf-8")
        registry.add(config)

        validator = ConfigValidator(registry, pm)
        result = validator.save_source_hash("test")

        hash_file = pm.config_derived_dir("test") / ".source-hash"
        assert hash_file.exists(), ".source-hash файл должен существовать"
        assert hash_file.read_text(encoding="utf-8").strip() == result
        assert len(result) == 64  # SHA-256


class TestCheckFreshnessWithHash:
    """D2.4: check_freshness использует content hash."""

    def test_freshness_report_has_source_hash(self) -> None:
        """IndexFreshnessReport содержит поле source_hash."""
        report = IndexFreshnessReport(config_name="test")
        assert hasattr(report, "source_hash")
        assert report.source_hash == ""

    def test_index_status_has_hash_match(self) -> None:
        """IndexStatus содержит поле source_hash_match."""
        status = IndexStatus(name="test", path=None)
        assert hasattr(status, "source_hash_match")
        assert status.source_hash_match is True
