"""
Тесты для P2.11: разделение ConfigManager на 3 класса (SRP).

До фикса: ConfigManager был God Object (746 строк) с CRUD + build + validate
всё в одном классе. Это нарушало SRP и усложняло тестирование.

После фикса:
- ConfigManager (CRUD): add_from_zip, archive, activate, remove
- ConfigBuilder: build, build_all
- ConfigValidator: validate_sources, check_freshness

ConfigManager делегирует builder/validator через свойства для backward compat.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.config_registry import ConfigurationRegistry
from src.services.config_builder import ConfigBuilder
from src.services.config_manager import ConfigManager
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


# ============================================================================
# Тесты — ConfigValidator (выделен из ConfigManager)
# ============================================================================


class TestConfigValidatorStandalone:
    """ConfigValidator работает независимо от ConfigManager."""

    def test_validator_can_be_instantiated(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigValidator инстанцируется с registry и paths."""
        pm, reg, _ = project_setup
        validator = ConfigValidator(reg, pm)
        assert validator is not None

    def test_validate_sources_returns_source_validation(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """validate_sources возвращает SourceValidation."""
        pm, reg, _ = project_setup
        validator = ConfigValidator(reg, pm)
        result = validator.validate_sources("nonexistent")
        assert isinstance(result, SourceValidation)
        assert result.is_valid is False

    def test_check_freshness_returns_index_freshness_report(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """check_freshness возвращает IndexFreshnessReport."""
        pm, reg, _ = project_setup
        validator = ConfigValidator(reg, pm)
        result = validator.check_freshness("nonexistent")
        assert isinstance(result, IndexFreshnessReport)
        assert result.config_name == "nonexistent"
        assert result.all_fresh is False

    def test_validate_sources_on_inactive_config(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """validate_sources на неактивной конфигурации → is_valid=False."""
        pm, reg, tmp_path = project_setup
        validator = ConfigValidator(reg, pm)
        result = validator.validate_sources("nonexistent")
        assert result.is_valid is False
        assert any("не активна" in err for err in result.errors)

    def test_check_freshness_on_inactive_config(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """check_freshness на неактивной конфигурации → все индексы missing."""
        pm, reg, _ = project_setup
        validator = ConfigValidator(reg, pm)
        result = validator.check_freshness("nonexistent")
        assert "metadata" in result.missing_indexes
        assert "api" in result.missing_indexes
        assert "skd" in result.missing_indexes
        assert "forms" in result.missing_indexes


class TestConfigValidatorOnActiveConfig:
    """ConfigValidator на активной конфигурации с реальными файлами."""

    def test_validate_sources_with_valid_xml(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
        tmp_path: Path,
    ) -> None:
        """validate_sources на конфигурации с Configuration.xml → is_valid может быть True."""
        pm, reg, _ = project_setup
        # Создаём конфигурацию с Configuration.xml и CommonModules
        cfg_dir = pm.configs_dir / "test_cfg"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "Configuration.xml").write_text(
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
            encoding="utf-8",
        )
        (cfg_dir / "CommonModules").mkdir()
        (cfg_dir / "CommonModules" / "TestModule.bsl").write_text("// test", encoding="utf-8")

        # Регистрируем конфигурацию
        from src.models.configuration import Configuration

        config = Configuration(
            name="test_cfg",
            title="Test",
            path=cfg_dir,
            status="active",
        )
        reg.add(config)

        validator = ConfigValidator(reg, pm)
        result = validator.validate_sources("test_cfg")
        assert result.has_configuration_xml is True
        assert result.has_metadata_dirs is True
        assert result.has_bsl_files is True


# ============================================================================
# Тесты — ConfigBuilder (выделен из ConfigManager)
# ============================================================================


class TestConfigBuilderStandalone:
    """ConfigBuilder работает независимо от ConfigManager."""

    def test_builder_can_be_instantiated(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """ConfigBuilder инстанцируется с registry и paths."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        assert builder is not None

    def test_build_raises_on_inactive_config(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """build на неактивной конфигурации → ValueError."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        with pytest.raises(ValueError, match="не активна"):
            builder.build("nonexistent")

    def test_build_all_returns_list(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """build_all возвращает список (пустой если нет активных конфигов)."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        results = builder.build_all()
        assert isinstance(results, list)


# ============================================================================
# Тесты — ConfigManager делегирует
# ============================================================================


class TestConfigManagerDelegation:
    """ConfigManager должен иметь builder и validator свойства."""

    def test_config_manager_has_builder_property(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigManager.builder возвращает ConfigBuilder."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        builder = cm.builder
        assert isinstance(builder, ConfigBuilder)

    def test_config_manager_has_validator_property(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigManager.validator возвращает ConfigValidator."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        validator = cm.validator
        assert isinstance(validator, ConfigValidator)

    def test_builder_and_validator_are_lazy(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """builder и validator создаются при первом обращении (lazy init)."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        # До обращения они None
        assert cm._builder is None
        assert cm._validator is None
        # После обращения — инстанцианы
        _ = cm.builder
        _ = cm.validator
        assert cm._builder is not None
        assert cm._validator is not None

    def test_builder_cached(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """Повторное обращение к builder возвращает тот же объект."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        b1 = cm.builder
        b2 = cm.builder
        assert b1 is b2

    def test_validator_cached(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """Повторное обращение к validator возвращает тот же объект."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        v1 = cm.validator
        v2 = cm.validator
        assert v1 is v2


# ============================================================================
# Тесты — backward compat (существующие методы ConfigManager работают)
# ============================================================================


class TestConfigManagerBackwardCompat:
    """Все существующие методы ConfigManager должны работать как раньше."""

    def test_all_existing_methods_present(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """ConfigManager сохраняет все public методы."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        # CRUD методы
        assert hasattr(cm, "add_from_zip")
        assert hasattr(cm, "add_from_cf")
        assert hasattr(cm, "register_existing")
        assert hasattr(cm, "archive")
        assert hasattr(cm, "activate")
        assert hasattr(cm, "remove")
        # Build методы (делегируют в builder)
        assert hasattr(cm, "build")
        assert hasattr(cm, "build_all")
        # Validate методы (делегируют в validator)
        assert hasattr(cm, "validate_sources")
        assert hasattr(cm, "check_freshness")

    def test_validate_sources_via_config_manager(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigManager.validate_sources возвращает SourceValidation."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        result = cm.validate_sources("nonexistent")
        assert isinstance(result, SourceValidation)
        assert result.is_valid is False

    def test_check_freshness_via_config_manager(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigManager.check_freshness возвращает IndexFreshnessReport."""
        pm, reg, _ = project_setup
        cm = ConfigManager(reg, pm)
        result = cm.check_freshness("nonexistent")
        assert isinstance(result, IndexFreshnessReport)


# ============================================================================
# Тесты — SRP: каждый класс имеет одну ответственность
# ============================================================================


class TestSRP:
    """Каждый класс должен иметь только одну ответственность."""

    def test_config_validator_only_validates(
        self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]
    ) -> None:
        """ConfigValidator не должен иметь CRUD методов."""
        pm, reg, _ = project_setup
        validator = ConfigValidator(reg, pm)
        # CRUD методы НЕ должны быть на validator
        assert not hasattr(validator, "add_from_zip")
        assert not hasattr(validator, "add_from_cf")
        assert not hasattr(validator, "archive")
        assert not hasattr(validator, "activate")
        assert not hasattr(validator, "remove")
        # Build методы НЕ должны быть на validator
        assert not hasattr(validator, "build")
        assert not hasattr(validator, "build_all")

    def test_config_builder_only_builds(self, project_setup: tuple[PathManager, ConfigurationRegistry, Path]) -> None:
        """ConfigBuilder не должен иметь CRUD или validate методов."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        # CRUD методы НЕ должны быть на builder
        assert not hasattr(builder, "add_from_zip")
        assert not hasattr(builder, "add_from_cf")
        assert not hasattr(builder, "archive")
        assert not hasattr(builder, "activate")
        assert not hasattr(builder, "remove")
        # Но у него есть валидатор для pre-flight проверок
        assert hasattr(builder, "_validator")
        assert isinstance(builder._validator, ConfigValidator)
