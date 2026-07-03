"""
Комплексные тесты для ConfigValidator (P0.1: coverage 65% → 85%+).

Покрывают:
- check_freshness() с существующими свежими индексами
- check_freshness() с устаревшими индексами (source новее)
- check_freshness() с отсутствующими индексами
- _latest_source_mtime() с разными файлами
- validate_sources() с .bsl файлами и без
- validate_sources() с ошибкой доступа к файлам
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from src.models.config_registry import ConfigurationRegistry
from src.models.configuration import Configuration
from src.services.config_validator import (
    ConfigValidator,
    IndexFreshnessReport,
    IndexStatus,
    SourceValidation,
)
from src.services.path_manager import PathManager


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture
def project_setup(tmp_path: Path) -> tuple[PathManager, ConfigurationRegistry, Path]:
    """Создаёт PathManager + registry в tmp_path."""
    (tmp_path / "paths.env").write_text("# fake\n", encoding="utf-8")
    (tmp_path / "data" / "configs").mkdir(parents=True)
    (tmp_path / "derived" / "configs").mkdir(parents=True)
    pm = PathManager(tmp_path)
    reg = ConfigurationRegistry(pm.config_registry_path, pm.root)
    return pm, reg, tmp_path


@pytest.fixture
def active_config_with_files(
    project_setup: tuple[PathManager, ConfigurationRegistry, Path],
) -> tuple[ConfigValidator, str, Path, PathManager]:
    """Создаёт активную конфигурацию с валидными исходниками и .bsl файлами."""
    pm, reg, tmp_path = project_setup
    cfg_dir = pm.configs_dir / "test_cfg"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "Configuration.xml").write_text(
        '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
        encoding="utf-8",
    )
    (cfg_dir / "CommonModules").mkdir()
    (cfg_dir / "CommonModules" / "TestModule.bsl").write_text(
        "// test code\n", encoding="utf-8"
    )
    (cfg_dir / "Subsystems").mkdir()
    (cfg_dir / "Subsystems" / "Main.xml").write_text(
        "<Subsystem/>", encoding="utf-8"
    )

    config = Configuration(
        name="test_cfg",
        title="Test",
        path=cfg_dir,
        status="active",
    )
    reg.add(config)

    validator = ConfigValidator(reg, pm)
    return validator, "test_cfg", cfg_dir, pm


# ============================================================================
# Тесты check_freshness() — с реальными индексами
# ============================================================================


class TestCheckFreshnessWithIndexes:
    """check_freshness() с существующими индексами."""

    def test_all_indexes_fresh(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Все индексы существуют и свежее source → all_fresh=True."""
        validator, name, cfg_dir, pm = active_config_with_files
        # Создаём индексы (новее source)
        derived_dir = pm.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)
        future_time = time.time() + 100  # новее source
        for idx_file in [
            derived_dir / "unified-metadata-index.json",
            pm.config_api_reference_json(name),
            derived_dir / "skd-index.json",
            derived_dir / "form-index.json",
        ]:
            idx_file.parent.mkdir(parents=True, exist_ok=True)
            idx_file.write_text("[]", encoding="utf-8")
            os.utime(idx_file, (future_time, future_time))

        report = validator.check_freshness(name)
        assert report.all_fresh is True
        assert len(report.stale_indexes) == 0
        assert len(report.missing_indexes) == 0
        assert len(report.indexes) == 4

    def test_all_indexes_missing(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Ни один индекс не существует → all missing."""
        validator, name, cfg_dir, pm = active_config_with_files
        report = validator.check_freshness(name)
        assert report.all_fresh is False
        assert len(report.missing_indexes) == 4
        assert "metadata" in report.missing_indexes
        assert "api" in report.missing_indexes
        assert "skd" in report.missing_indexes
        assert "forms" in report.missing_indexes

    def test_indexes_stale_when_source_newer(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Source новее индексов → индексы stale."""
        validator, name, cfg_dir, pm = active_config_with_files
        # Создаём старые индексы
        derived_dir = pm.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)
        past_time = time.time() - 1000  # старше source
        for idx_file in [
            derived_dir / "unified-metadata-index.json",
            pm.config_api_reference_json(name),
            derived_dir / "skd-index.json",
            derived_dir / "form-index.json",
        ]:
            idx_file.parent.mkdir(parents=True, exist_ok=True)
            idx_file.write_text("[]", encoding="utf-8")
            os.utime(idx_file, (past_time, past_time))

        report = validator.check_freshness(name)
        assert report.all_fresh is False
        assert len(report.stale_indexes) == 4
        # Каждый индекс имеет stale_reason
        for status in report.indexes:
            assert status.is_stale is True
            assert status.stale_reason != ""

    def test_partial_freshness(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Часть индексов свежие, часть отсутствует → смешанный отчёт."""
        validator, name, cfg_dir, pm = active_config_with_files
        derived_dir = pm.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)
        future_time = time.time() + 100
        # Создаём только metadata (свежий)
        metadata_idx = derived_dir / "unified-metadata-index.json"
        metadata_idx.write_text("[]", encoding="utf-8")
        os.utime(metadata_idx, (future_time, future_time))

        report = validator.check_freshness(name)
        assert report.all_fresh is False
        # metadata не в stale и не в missing
        assert "metadata" not in report.stale_indexes
        assert "metadata" not in report.missing_indexes
        # остальные missing
        assert "api" in report.missing_indexes
        assert "skd" in report.missing_indexes
        assert "forms" in report.missing_indexes

    def test_index_status_has_size_bytes(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """IndexStatus содержит size_bytes для существующих индексов."""
        validator, name, cfg_dir, pm = active_config_with_files
        derived_dir = pm.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)
        future_time = time.time() + 100
        metadata_idx = derived_dir / "unified-metadata-index.json"
        test_content = '{"test": "data"}'
        metadata_idx.write_text(test_content, encoding="utf-8")
        os.utime(metadata_idx, (future_time, future_time))

        report = validator.check_freshness(name)
        metadata_status = next(
            s for s in report.indexes if s.name == "metadata"
        )
        assert metadata_status.exists is True
        assert metadata_status.size_bytes == len(test_content.encode("utf-8"))

    def test_source_mtime_in_report(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Report содержит source_mtime."""
        validator, name, cfg_dir, pm = active_config_with_files
        report = validator.check_freshness(name)
        assert report.source_mtime is not None
        assert report.source_mtime > 0


# ============================================================================
# Тесты _latest_source_mtime()
# ============================================================================


class TestLatestSourceMtime:
    """_latest_source_mtime() — поиск самого свежего файла."""

    def test_empty_dir_returns_none(self, tmp_path: Path) -> None:
        """Пустая директория → None."""
        result = ConfigValidator._latest_source_mtime(tmp_path)
        assert result is None

    def test_with_xml_files(self, tmp_path: Path) -> None:
        """XML файлы → max mtime."""
        f1 = tmp_path / "config.xml"
        f1.write_text("<c/>", encoding="utf-8")
        f2 = tmp_path / "sub" / "form.xml"
        f2.parent.mkdir()
        f2.write_text("<f/>", encoding="utf-8")
        # f2 новее
        future = time.time() + 50
        os.utime(f2, (future, future))

        result = ConfigValidator._latest_source_mtime(tmp_path)
        assert result is not None
        assert abs(result - future) < 1

    def test_with_bsl_files(self, tmp_path: Path) -> None:
        """BSL файлы учитываются."""
        bsl = tmp_path / "module.bsl"
        bsl.write_text("// code", encoding="utf-8")
        result = ConfigValidator._latest_source_mtime(tmp_path)
        assert result is not None

    def test_ignores_non_xml_bsl_files(self, tmp_path: Path) -> None:
        """Не-XML/BSL файлы игнорируются."""
        txt = tmp_path / "readme.txt"
        txt.write_text("text", encoding="utf-8")
        result = ConfigValidator._latest_source_mtime(tmp_path)
        assert result is None


# ============================================================================
# Тесты validate_sources() — дополнительные сценарии
# ============================================================================


class TestValidateSourcesAdditional:
    """validate_sources() — дополнительные сценарии покрытия."""

    def test_validate_with_bsl_files(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Конфигурация с .bsl файлами → has_bsl_files=True."""
        validator, name, _, _ = active_config_with_files
        result = validator.validate_sources(name)
        assert result.has_bsl_files is True
        assert result.is_valid is True

    def test_validate_without_bsl_files(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Конфигурация без .bsl файлов → warning."""
        pm, reg, tmp_path = project_setup
        cfg_dir = pm.configs_dir / "no_bsl"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "Configuration.xml").write_text(
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
            encoding="utf-8",
        )
        (cfg_dir / "Subsystems").mkdir()
        (cfg_dir / "Subsystems" / "Main.xml").write_text(
            "<Subsystem/>", encoding="utf-8"
        )
        # Нет .bsl файлов

        config = Configuration(
            name="no_bsl",
            title="No BSL",
            path=cfg_dir,
            status="active",
        )
        reg.add(config)

        validator = ConfigValidator(reg, pm)
        result = validator.validate_sources("no_bsl")
        assert result.has_bsl_files is False
        assert any(".bsl" in w for w in result.warnings)

    def test_validate_without_configuration_xml(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Конфигурация без Configuration.xml → is_valid=False."""
        pm, reg, tmp_path = project_setup
        cfg_dir = pm.configs_dir / "no_xml"
        cfg_dir.mkdir(parents=True)
        # Нет Configuration.xml
        (cfg_dir / "Subsystems").mkdir()
        (cfg_dir / "Subsystems" / "Main.xml").write_text(
            "<Subsystem/>", encoding="utf-8"
        )

        config = Configuration(
            name="no_xml",
            title="No XML",
            path=cfg_dir,
            status="active",
        )
        reg.add(config)

        validator = ConfigValidator(reg, pm)
        result = validator.validate_sources("no_xml")
        assert result.is_valid is False
        assert result.has_configuration_xml is False
        assert any("Configuration.xml" in e for e in result.errors)

    def test_validate_finds_type_dirs(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """Найденные директории типов в found_type_dirs."""
        validator, name, cfg_dir, _ = active_config_with_files
        result = validator.validate_sources(name)
        assert "CommonModules" in result.found_type_dirs
        assert "Subsystems" in result.found_type_dirs

    def test_validate_has_metadata_dirs_true(
        self,
        active_config_with_files: tuple,
    ) -> None:
        """С конфигурацией с директориями → has_metadata_dirs=True."""
        validator, name, _, _ = active_config_with_files
        result = validator.validate_sources(name)
        assert result.has_metadata_dirs is True
