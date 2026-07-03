"""
Комплексные тесты для ConfigBuilder (P0.1: coverage 26% → 80%+).

Покрывают:
- build() с force=True (bypass freshness)
- build() с skip_if_fresh и all_fresh (skip all)
- build() с частичной свежестью индексов
- build() с ошибками парсеров (metadata/api/skd/forms)
- build() без CommonModules dir (api skipped)
- _run_script() успех и失败
- _build_api_reference() успех и失败
- _count_objects() статический метод
- build_all() с активными конфигами
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.config_registry import ConfigurationRegistry
from src.models.configuration import Configuration
from src.services.config_builder import ConfigBuilder
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
    (tmp_path / "scripts").mkdir(parents=True)
    pm = PathManager(tmp_path)
    reg = ConfigurationRegistry(pm.config_registry_path, pm.root)
    return pm, reg, tmp_path


@pytest.fixture
def active_config(
    project_setup: tuple[PathManager, ConfigurationRegistry, Path],
) -> tuple[ConfigBuilder, str, Path]:
    """Создаёт активную конфигурацию с валидными исходниками."""
    pm, reg, tmp_path = project_setup
    cfg_dir = pm.configs_dir / "test_cfg"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "Configuration.xml").write_text(
        '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
        encoding="utf-8",
    )
    (cfg_dir / "CommonModules").mkdir()
    (cfg_dir / "CommonModules" / "TestModule.bsl").write_text("// test", encoding="utf-8")

    config = Configuration(
        name="test_cfg",
        title="Test",
        path=cfg_dir,
        status="active",
    )
    reg.add(config)

    builder = ConfigBuilder(reg, pm)
    return builder, "test_cfg", cfg_dir


def _make_freshness_report(
    config_name: str,
    all_fresh: bool = False,
    stale_indexes: list[str] | None = None,
) -> IndexFreshnessReport:
    """Создать IndexFreshnessReport с заданным состоянием."""
    stale = stale_indexes or []
    indexes = []
    for idx_name in ["metadata", "api", "skd", "forms"]:
        is_stale = idx_name in stale and not all_fresh
        indexes.append(
            IndexStatus(
                name=idx_name,
                path=None,
                exists=all_fresh or not is_stale,
                mtime=2000.0 if (all_fresh or not is_stale) else None,
                is_stale=is_stale,
                stale_reason="source newer" if is_stale else "",
            )
        )
    return IndexFreshnessReport(
        config_name=config_name,
        source_mtime=1000.0,
        all_fresh=all_fresh,
        indexes=indexes,
        stale_indexes=[i.name for i in indexes if i.is_stale],
    )


# ============================================================================
# Тесты build() — основной метод
# ============================================================================


class TestBuildForce:
    """build() с force=True — пересборка всех индексов."""

    def test_build_force_skips_freshness_check(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """force=True → не проверяет freshness, строит все индексы."""
        builder, name, _ = active_config
        with (
            patch.object(builder, "_run_script") as mock_run,
            patch.object(builder, "_build_api_reference") as mock_api,
            patch.object(builder, "_count_objects", return_value=5),
        ):
            result = builder.build(name, force=True)
            assert result["name"] == name
            assert mock_run.call_count == 3  # metadata, skd, forms
            mock_api.assert_called_once()

    def test_build_force_all_indexes_attempted(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """force=True → все 4 индекса пытаются построиться."""
        builder, name, _ = active_config
        with (
            patch.object(builder, "_run_script") as mock_run,
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            builder.build(name, force=True)
            # 3 скрипта (metadata, skd, forms) + 1 api reference
            assert mock_run.call_count == 3

    def test_build_force_does_not_return_skipped_all(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """force=True → report не содержит 'skipped: [all]'."""
        builder, name, _ = active_config
        with (
            patch.object(builder, "_run_script"),
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build(name, force=True)
            assert result.get("skipped") != ["all"]


class TestBuildSkipIfFresh:
    """build() с skip_if_fresh=True — пропуск свежих индексов."""

    def test_build_all_fresh_returns_skipped_all(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Все индексы свежие → report с skipped=['all']."""
        builder, name, _ = active_config
        fresh_report = _make_freshness_report(name, all_fresh=True)
        with (
            patch.object(builder._validator, "check_freshness", return_value=fresh_report),
            patch.object(builder._validator, "validate_sources") as mock_validate,
        ):
            mock_validate.return_value = SourceValidation(
                is_valid=True,
                has_configuration_xml=True,
                has_metadata_dirs=True,
                has_bsl_files=True,
            )
            result = builder.build(name, force=False, skip_if_fresh=True)
            assert result["skipped"] == ["all"]
            assert result["metadata"] is True
            assert result["api"] is True
            assert result["skd"] is True
            assert result["forms"] is True

    def test_build_partial_freshness_only_stale_rebuilt(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Только metadata устарел → пересобирается только metadata."""
        builder, name, _ = active_config
        fresh_report = _make_freshness_report(name, all_fresh=False, stale_indexes=["metadata"])
        with (
            patch.object(builder._validator, "check_freshness", return_value=fresh_report),
            patch.object(builder._validator, "validate_sources") as mock_validate,
            patch.object(builder, "_run_script") as mock_run,
            patch.object(builder, "_build_api_reference") as mock_api,
            patch.object(builder, "_count_objects", return_value=0),
        ):
            mock_validate.return_value = SourceValidation(
                is_valid=True,
                has_configuration_xml=True,
                has_metadata_dirs=True,
                has_bsl_files=True,
            )
            result = builder.build(name, force=False, skip_if_fresh=True)
            # Только metadata пересобирается
            assert result["metadata"] is True
            assert result["skd"] is True  # fresh, skipped
            assert result["forms"] is True  # fresh, skipped
            assert "metadata" not in result.get("skipped", [])
            assert "skd" in result.get("skipped", [])
            assert "forms" in result.get("skipped", [])
            # _run_script вызывается только для metadata (1 раз)
            assert mock_run.call_count == 1
            # api не вызывается (fresh)
            mock_api.assert_not_called()


class TestBuildParserErrors:
    """build() с ошибками парсеров — graceful degradation."""

    def test_build_metadata_parser_failure(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Ошибка metadata_extractor → report['metadata']=False, остальные строятся."""
        builder, name, _ = active_config
        with (
            patch.object(builder, "_run_script", side_effect=[RuntimeError("metadata failed"), None, None]),
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build(name, force=True)
            assert result["metadata"] is False
            assert result["skd"] is True
            assert result["forms"] is True

    def test_build_skd_parser_failure(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Ошибка skd_parser → report['skd']=False."""
        builder, name, _ = active_config
        with (
            patch.object(
                builder,
                "_run_script",
                side_effect=[None, RuntimeError("skd failed"), None],
            ),
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build(name, force=True)
            assert result["metadata"] is True
            assert result["skd"] is False
            assert result["forms"] is True

    def test_build_forms_parser_failure(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Ошибка form_analyzer → report['forms']=False."""
        builder, name, _ = active_config
        with (
            patch.object(
                builder,
                "_run_script",
                side_effect=[None, None, RuntimeError("forms failed")],
            ),
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build(name, force=True)
            assert result["forms"] is False
            assert result["metadata"] is True
            assert result["skd"] is True

    def test_build_api_failure(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
    ) -> None:
        """Ошибка build_api_reference → report['api']=False."""
        builder, name, _ = active_config
        with (
            patch.object(builder, "_run_script"),
            patch.object(
                builder,
                "_build_api_reference",
                side_effect=RuntimeError("api failed"),
            ),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build(name, force=True)
            assert result["api"] is False
            assert result["metadata"] is True


class TestBuildNoCommonModules:
    """build() без CommonModules dir → api skipped."""

    def test_build_without_common_modules_skips_api(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Конфигурация без CommonModules → api=False, skipped_reasons заполнен."""
        pm, reg, tmp_path = project_setup
        cfg_dir = pm.configs_dir / "no_cm"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "Configuration.xml").write_text(
            '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
            encoding="utf-8",
        )
        # НЕ создаём CommonModules dir, но создаём Subsystems (критическая директория для валидатора)
        (cfg_dir / "Subsystems").mkdir()
        (cfg_dir / "Subsystems" / "Main.xml").write_text("<Subsystem/>", encoding="utf-8")
        config = Configuration(
            name="no_cm",
            title="No CM",
            path=cfg_dir,
            status="active",
        )
        reg.add(config)

        builder = ConfigBuilder(reg, pm)
        with (
            patch.object(builder, "_run_script"),
            patch.object(builder, "_build_api_reference") as mock_api,
            patch.object(builder, "_count_objects", return_value=0),
        ):
            result = builder.build("no_cm", force=True)
            assert result["api"] is False
            mock_api.assert_not_called()
            assert "api" in result.get("skipped_reasons", {})


# ============================================================================
# Тесты _run_script()
# ============================================================================


class TestRunScript:
    """_run_script() — запуск Python скриптов."""

    def test_run_script_success(self, tmp_path: Path) -> None:
        """Успешный запуск скрипта → не raise."""
        # Создаём тестовый скрипт
        script = tmp_path / "test_script.py"
        script.write_text("print('ok')", encoding="utf-8")
        # Нужен ConfigBuilder instance для _run_script
        pm = PathManager(tmp_path)
        (tmp_path / "paths.env").write_text("# fake\n", encoding="utf-8")
        reg = ConfigurationRegistry(pm.config_registry_path, pm.root)
        builder = ConfigBuilder(reg, pm)
        # Не должно raise
        builder._run_script(script, ["arg1"])

    def test_run_script_failure_raises_runtime_error(self, tmp_path: Path) -> None:
        """Скрипт с ненулевым exit code → RuntimeError."""
        script = tmp_path / "fail_script.py"
        script.write_text("import sys; sys.exit(1)", encoding="utf-8")
        pm = PathManager(tmp_path)
        (tmp_path / "paths.env").write_text("# fake\n", encoding="utf-8")
        reg = ConfigurationRegistry(pm.config_registry_path, pm.root)
        builder = ConfigBuilder(reg, pm)
        with pytest.raises(RuntimeError, match="fail_script"):
            builder._run_script(script, [])


# ============================================================================
# Тесты _count_objects()
# ============================================================================


class TestCountObjects:
    """_count_objects() — подсчёт объектов метаданных."""

    def test_count_objects_empty_dir(self, tmp_path: Path) -> None:
        """Пустая директория → 0."""
        count = ConfigBuilder._count_objects(tmp_path)
        assert count == 0

    def test_count_objects_with_catalogs(self, tmp_path: Path) -> None:
        """Catalogs с 2 объектами → 2."""
        (tmp_path / "Catalogs" / "Номенклатура").mkdir(parents=True)
        (tmp_path / "Catalogs" / "Контрагенты").mkdir(parents=True)
        count = ConfigBuilder._count_objects(tmp_path)
        assert count == 2

    def test_count_objects_multiple_types(self, tmp_path: Path) -> None:
        """Разные типы объектов → сумма."""
        (tmp_path / "Catalogs" / "Товары").mkdir(parents=True)
        (tmp_path / "Documents" / "Заказ").mkdir(parents=True)
        (tmp_path / "Documents" / "Реализация").mkdir(parents=True)
        (tmp_path / "CommonModules" / "ОбщийМодуль").mkdir(parents=True)
        count = ConfigBuilder._count_objects(tmp_path)
        assert count == 4

    def test_count_objects_ignores_files(self, tmp_path: Path) -> None:
        """Файлы (не директории) не считаются."""
        (tmp_path / "Catalogs" / "Товары").mkdir(parents=True)
        (tmp_path / "Catalogs" / "file.txt").write_text("test", encoding="utf-8")
        count = ConfigBuilder._count_objects(tmp_path)
        assert count == 1

    def test_count_objects_ignores_unknown_dirs(self, tmp_path: Path) -> None:
        """Неизвестные директории (не в списке типов) не считаются."""
        (tmp_path / "Catalogs" / "Товары").mkdir(parents=True)
        (tmp_path / "UnknownType" / "Something").mkdir(parents=True)
        count = ConfigBuilder._count_objects(tmp_path)
        assert count == 1


# ============================================================================
# Тесты build_all()
# ============================================================================


class TestBuildAll:
    """build_all() — построение индексов для всех активных конфигов."""

    def test_build_all_empty_registry(self, project_setup: tuple) -> None:
        """Пустой registry → пустой список."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        results = builder.build_all()
        assert results == []

    def test_build_all_multiple_configs(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Несколько активных конфигов → результат для каждого."""
        pm, reg, tmp_path = project_setup
        for i in range(3):
            cfg_dir = pm.configs_dir / f"cfg_{i}"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "Configuration.xml").write_text(
                '<md:Configuration xmlns:md="http://v8.1c.ru/8.3/MDClasses"/>',
                encoding="utf-8",
            )
            # Создаём CommonModules и Subsystems для прохождения валидации
            (cfg_dir / "CommonModules").mkdir()
            (cfg_dir / "CommonModules" / "Module.bsl").write_text("// test", encoding="utf-8")
            (cfg_dir / "Subsystems").mkdir()
            (cfg_dir / "Subsystems" / "Main.xml").write_text("<Subsystem/>", encoding="utf-8")
            config = Configuration(
                name=f"cfg_{i}",
                title=f"Config {i}",
                path=cfg_dir,
                status="active",
            )
            reg.add(config)

        builder = ConfigBuilder(reg, pm)
        with (
            patch.object(builder, "_run_script"),
            patch.object(builder, "_build_api_reference"),
            patch.object(builder, "_count_objects", return_value=0),
        ):
            results = builder.build_all(force=True)
            assert len(results) == 3
            assert all(r["name"].startswith("cfg_") for r in results)

    def test_build_all_force_propagated(
        self,
        active_config: tuple[ConfigBuilder, str, Path],
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """force параметр передаётся в build()."""
        pm, reg, _ = project_setup
        builder = active_config[0]
        with patch.object(builder, "build") as mock_build:
            mock_build.return_value = {"name": "test", "metadata": True}
            builder.build_all(force=True)
            mock_build.assert_called_once()
            assert mock_build.call_args.kwargs.get("force") is True


# ============================================================================
# Тесты build() — валидация исходников
# ============================================================================


class TestBuildValidation:
    """build() — валидация исходников перед индексацией."""

    def test_build_invalid_sources_raises_value_error(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Невалидные исходники → ValueError."""
        pm, reg, tmp_path = project_setup
        cfg_dir = pm.configs_dir / "invalid_cfg"
        cfg_dir.mkdir(parents=True)
        # Нет Configuration.xml
        config = Configuration(
            name="invalid_cfg",
            title="Invalid",
            path=cfg_dir,
            status="active",
        )
        reg.add(config)

        builder = ConfigBuilder(reg, pm)
        with pytest.raises(ValueError, match="невалидны"):
            builder.build("invalid_cfg", force=True)

    def test_build_inactive_config_raises_value_error(
        self,
        project_setup: tuple[PathManager, ConfigurationRegistry, Path],
    ) -> None:
        """Неактивная конфигурация → ValueError."""
        pm, reg, _ = project_setup
        builder = ConfigBuilder(reg, pm)
        with pytest.raises(ValueError, match="не активна"):
            builder.build("nonexistent", force=True)
