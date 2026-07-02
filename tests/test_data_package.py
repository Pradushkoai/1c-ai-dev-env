"""
Тесты для DataPackage — persistence данных проекта между сессиями.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.data_package import DataPackage, PackageManifest


@pytest.fixture
def mock_paths(tmp_path):
    """Mock PathManager с реальной файловой структурой в tmp_path."""
    paths = MagicMock()
    paths.root = tmp_path
    paths.data_dir = tmp_path / "data"
    paths.configs_dir = tmp_path / "data" / "configs"
    paths.derived_dir = tmp_path / "derived"
    paths.derived_configs_dir = tmp_path / "derived" / "configs"
    paths.derived_platform_dir = tmp_path / "derived" / "platform"
    paths.runtime_dir = tmp_path / "runtime"
    paths.config_registry_path = tmp_path / "runtime" / "config-registry.json"

    def config_derived_dir(name):
        return paths.derived_configs_dir / name

    def config_path(name):
        return paths.configs_dir / name

    def config_api_reference_json(name):
        return config_derived_dir(name) / "api-reference.json"

    # Fast search index и syntax-helper — обычные Path
    paths.fast_search_index = paths.derived_platform_dir / "fast-search-index.json"
    paths.syntax_helper_index_json = paths.derived_platform_dir / "syntax-helper-index.json"

    paths.config_derived_dir = config_derived_dir
    paths.config_path = config_path
    paths.config_api_reference_json = config_api_reference_json

    return paths


@pytest.fixture
def project_with_data(mock_paths):
    """Создать проект с конфигурацией и индексами."""
    # config-registry.json
    mock_paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    registry = {
        "version": "2.0",
        "configs": {
            "ut11": {
                "name": "УТ 11",
                "version": "11.3.4.197",
                "status": "active",
                "objects_count": 5440,
                "path": str(mock_paths.configs_dir / "ut11"),
            }
        },
    }
    with open(mock_paths.config_registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False)

    # derived/configs/ut11/api-reference.json
    ut11_derived = mock_paths.derived_configs_dir / "ut11"
    ut11_derived.mkdir(parents=True, exist_ok=True)
    api_data = [{"name": "ОбщегоНазначения", "methods_count": 5}]
    with open(ut11_derived / "api-reference.json", "w", encoding="utf-8") as f:
        json.dump(api_data, f, ensure_ascii=False)
    (ut11_derived / "index.md").write_text("# УТ 11 индекс")

    # derived/platform/fast-search-index.json
    mock_paths.derived_platform_dir.mkdir(parents=True, exist_ok=True)
    index_data = {"version": 2, "algorithm": "bm25", "methods": [], "total_methods": 0}
    with open(mock_paths.derived_platform_dir / "fast-search-index.json", "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False)

    return mock_paths


# ============ PackageManifest ============


class TestPackageManifest:
    def test_default_values(self):
        m = PackageManifest()
        assert m.version == "1.0"
        assert m.include_raw is False
        assert m.include_derived is True
        assert m.configs == []

    def test_to_dict_and_back(self):
        m = PackageManifest(
            version="1.0",
            created_at="2026-01-01",
            include_raw=True,
            configs=[{"name": "ut11"}],
            files_count=42,
            size_bytes=1024,
        )
        d = m.to_dict()
        m2 = PackageManifest.from_dict(d)
        assert m2.version == m.version
        assert m2.created_at == m.created_at
        assert m2.include_raw == m.include_raw
        assert m2.configs == m.configs
        assert m2.files_count == m.files_count
        assert m2.size_bytes == m.size_bytes


# ============ DataPackage.save ============


class TestDataPackageSave:
    def test_save_creates_zip(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        result = dp.save(output, include_raw=False, include_derived=True)
        assert result == output
        assert output.exists()
        assert zipfile.is_zipfile(output)

    def test_save_includes_manifest(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        dp.save(output, include_derived=True)

        with zipfile.ZipFile(output, "r") as zf:
            assert "data-package/manifest.json" in zf.namelist()
            manifest_data = json.loads(zf.read("data-package/manifest.json"))
            assert manifest_data["version"] == "1.0"
            assert manifest_data["include_derived"] is True
            assert manifest_data["include_raw"] is False

    def test_save_includes_config_registry(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        dp.save(output, include_derived=True)

        with zipfile.ZipFile(output, "r") as zf:
            assert "data-package/runtime/config-registry.json" in zf.namelist()

    def test_save_includes_derived(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        dp.save(output, include_derived=True)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any("derived/configs/ut11/api-reference.json" in n for n in names)
            assert any("derived/platform/fast-search-index.json" in n for n in names)

    def test_save_without_derived_excludes_them(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        # Создадим файл в data/, чтобы было что сохранять
        ut11_data = project_with_data.configs_dir / "ut11"
        ut11_data.mkdir(parents=True, exist_ok=True)
        (ut11_data / "Configuration.xml").write_text("<xml/>")

        # Можно сохранить только raw (без derived)
        dp.save(output, include_raw=True, include_derived=False)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert not any("derived/" in n for n in names)
            assert any("data/" in n for n in names)

    def test_save_raises_on_nothing_selected(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        with pytest.raises(ValueError, match="Хотя бы одно"):
            dp.save(output, include_raw=False, include_derived=False)

    def test_save_includes_config_info_in_manifest(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        dp.save(output, include_derived=True)

        with zipfile.ZipFile(output, "r") as zf:
            manifest = json.loads(zf.read("data-package/manifest.json"))
            assert len(manifest["configs"]) == 1
            assert manifest["configs"][0]["name"] == "ut11"
            assert manifest["configs"][0]["version"] == "11.3.4.197"

    def test_save_with_raw_includes_data_dir(self, project_with_data, tmp_path):
        # Создадим файл в data/
        ut11_data = project_with_data.configs_dir / "ut11"
        ut11_data.mkdir(parents=True, exist_ok=True)
        (ut11_data / "Configuration.xml").write_text("<xml/>")

        dp = DataPackage(project_with_data)
        output = tmp_path / "backup.zip"
        dp.save(output, include_raw=True, include_derived=True)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any("data/configs/ut11/Configuration.xml" in n for n in names)


# ============ DataPackage.load ============


class TestDataPackageLoad:
    def test_load_restores_files(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        backup = tmp_path / "backup.zip"
        dp.save(backup, include_derived=True)

        # Удаляем всё
        import shutil

        shutil.rmtree(project_with_data.derived_dir)
        assert not project_with_data.derived_dir.exists()

        # Восстанавливаем
        stats = dp.load(backup)
        assert stats["files_restored"] > 0
        assert (project_with_data.derived_dir / "configs" / "ut11" / "api-reference.json").exists()
        assert (project_with_data.derived_platform_dir / "fast-search-index.json").exists()

    def test_load_restores_config_registry(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        backup = tmp_path / "backup.zip"
        dp.save(backup, include_derived=True)

        # Удаляем registry
        project_with_data.config_registry_path.unlink()
        assert not project_with_data.config_registry_path.exists()

        # Восстанавливаем
        stats = dp.load(backup)
        assert stats["configs_loaded"] == 1
        assert project_with_data.config_registry_path.exists()

        with open(project_with_data.config_registry_path) as f:
            data = json.load(f)
        assert "ut11" in data["configs"]

    def test_load_missing_file_raises(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        with pytest.raises(FileNotFoundError):
            dp.load(tmp_path / "nonexistent.zip")

    def test_load_returns_stats(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        backup = tmp_path / "backup.zip"
        dp.save(backup, include_derived=True)

        stats = dp.load(backup)
        assert "files_restored" in stats
        assert "configs_loaded" in stats
        assert "derived_restored" in stats
        assert "raw_restored" in stats
        assert stats["manifest"] is not None


# ============ DataPackage.info ============


class TestDataPackageInfo:
    def test_info_returns_manifest(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        backup = tmp_path / "backup.zip"
        dp.save(backup, include_derived=True, description="test backup")

        info = dp.info(backup)
        assert info["manifest"] is not None
        assert info["manifest"]["description"] == "test backup"
        assert info["total_files"] > 0
        assert info["size_mb"] > 0

    def test_info_file_list_sample(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        backup = tmp_path / "backup.zip"
        dp.save(backup, include_derived=True)

        info = dp.info(backup)
        assert len(info["file_list_sample"]) > 0
        assert "data-package/manifest.json" in info["file_list_sample"]

    def test_info_missing_file_raises(self, project_with_data, tmp_path):
        dp = DataPackage(project_with_data)
        with pytest.raises(FileNotFoundError):
            dp.info(tmp_path / "nonexistent.zip")


# ============ Autosave / Autoload ============


class TestAutosaveAutoload:
    def test_default_package_path(self, project_with_data):
        dp = DataPackage(project_with_data)
        path = dp.default_package_path
        assert "download" in str(path)
        assert path.name == "1c-ai-data-package.zip"

    def test_has_autosave_false_initially(self, project_with_data):
        dp = DataPackage(project_with_data)
        assert dp.has_autosave() is False

    def test_autosave_creates_file(self, project_with_data):
        dp = DataPackage(project_with_data)
        result = dp.autosave()
        assert result.exists()
        assert dp.has_autosave() is True

    def test_autoload_returns_none_if_no_autosave(self, project_with_data):
        dp = DataPackage(project_with_data)
        assert dp.autoload() is None

    def test_autoload_restores(self, project_with_data):
        dp = DataPackage(project_with_data)
        dp.autosave(include_derived=True)

        # Удаляем derived
        import shutil

        shutil.rmtree(project_with_data.derived_dir)

        stats = dp.autoload()
        assert stats is not None
        assert stats["files_restored"] > 0
        assert project_with_data.derived_dir.exists()

    def test_autosave_autoload_cycle(self, project_with_data):
        """Полный цикл: autosave → удалить → autoload → проверить."""
        dp = DataPackage(project_with_data)

        # Сохраняем
        dp.autosave(include_derived=True, description="cycle test")
        assert dp.has_autosave()

        # Удаляем всё
        import shutil

        shutil.rmtree(project_with_data.derived_dir)
        shutil.rmtree(project_with_data.runtime_dir)

        # Восстанавливаем
        stats = dp.autoload()
        assert stats["files_restored"] > 0
        assert project_with_data.derived_dir.exists()
        assert project_with_data.config_registry_path.exists()


# ============ Status ============


class TestStatus:
    def test_status_empty_project(self, mock_paths):
        dp = DataPackage(mock_paths)
        status = dp.status()
        assert status["has_platform_index"] is False
        assert status["has_platform_methods"] is False
        assert status["configs"] == []
        assert status["autosave_available"] is False

    def test_status_with_data(self, project_with_data):
        dp = DataPackage(project_with_data)
        status = dp.status()
        assert status["has_platform_index"] is True
        assert len(status["configs"]) == 1
        assert status["configs"][0]["name"] == "ut11"
        assert status["configs"][0]["has_derived"] is True
        assert status["configs"][0]["has_api"] is True

    def test_status_after_autosave(self, project_with_data):
        dp = DataPackage(project_with_data)
        dp.autosave()
        status = dp.status()
        assert status["autosave_available"] is True
        assert status["autosave_info"] is not None
        assert status["autosave_info"]["total_files"] > 0

    def test_status_shows_missing_indices(self, project_with_data):
        # Удалим api-reference.json
        (project_with_data.derived_configs_dir / "ut11" / "api-reference.json").unlink()

        dp = DataPackage(project_with_data)
        status = dp.status()
        assert status["configs"][0]["has_api"] is False
        assert status["configs"][0]["has_derived"] is True  # директория осталась
