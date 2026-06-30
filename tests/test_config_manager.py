"""
Тесты для ConfigManager.
subprocess мокируется (чтобы не запускать внешние скрипты).
ZIP создаётся реальный (для проверки логики распаковки).
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.config_registry import ConfigurationRegistry
from src.models.configuration import Configuration
from src.services.config_manager import ConfigManager
from src.services.path_manager import PathManager


@pytest.fixture
def setup(tmp_path):
    """Фикстура: PathManager + пустой реестр + ConfigManager."""
    # Минимальная структура
    for d in ["data/configs", "data/archives", "derived/configs", "runtime"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    pm = PathManager(project_root=tmp_path)
    registry_path = tmp_path / "runtime" / "config-registry.json"
    registry_path.write_text('{"version": "2.0", "configs": {}}', encoding='utf-8')

    reg = ConfigurationRegistry(registry_path, tmp_path)
    cm = ConfigManager(reg, pm)
    return pm, reg, cm, tmp_path


def _make_zip(zip_path: Path, files: dict[str, str]) -> None:
    """Создать ZIP с указанными файлами (filename → content)."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def _config_xml(version: str = "11.3.4", vendor: str = "1C") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <Configuration>
    <Properties>
      <Version>{version}</Version>
      <Vendor>{vendor}</Vendor>
    </Properties>
  </Configuration>
</ConfigDumpInfo>"""


def test_add_from_zip_success(setup):
    """add_from_zip распаковывает и регистрирует конфигурацию."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml("11.3.4", "1C"),
        "Catalogs/Товары/Товары.xml": "<root/>",
    })

    config = cm.add_from_zip("ut11", zip_path, "УТ 11")

    assert config.name == "ut11"
    assert config.title == "УТ 11"
    assert config.version == "11.3.4"
    assert config.vendor == "1C"
    assert config.status == "active"
    assert config.path.exists()
    assert "ut11" in reg
    assert (config.path / "Configuration.xml").exists()


def test_add_from_zip_duplicate(setup):
    """Дубликат имени вызывает ValueError."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {"Configuration.xml": _config_xml()})

    cm.add_from_zip("ut11", zip_path, "УТ 11")
    with pytest.raises(ValueError, match="уже существует"):
        cm.add_from_zip("ut11", zip_path, "УТ 11")


def test_add_from_zip_not_found(setup):
    """Несуществующий ZIP вызывает FileNotFoundError."""
    pm, reg, cm, tmp = setup
    with pytest.raises(FileNotFoundError):
        cm.add_from_zip("missing", tmp / "nope.zip", "Missing")


def test_add_from_zip_bad_zip(setup):
    """Повреждённый ZIP → ValueError с понятным сообщением."""
    pm, reg, cm, tmp = setup
    bad_zip = tmp / "bad.zip"
    bad_zip.write_bytes(b"NOT A ZIP FILE")

    with pytest.raises(ValueError, match="ZIP повреждён"):
        cm.add_from_zip("bad", bad_zip, "Bad")

    # Директория должна быть очищена
    assert not (pm.config_path("bad")).exists()
    assert "bad" not in reg


def test_count_objects(setup):
    """_count_objects правильно считает поддиректории."""
    pm, reg, cm, tmp = setup
    config_dir = tmp / "cfg"
    config_dir.mkdir()
    (config_dir / "Catalogs").mkdir()
    (config_dir / "Catalogs" / "Товары").mkdir()
    (config_dir / "Catalogs" / "Клиенты").mkdir()
    (config_dir / "Documents").mkdir()
    (config_dir / "Documents" / "Заказ").mkdir()
    (config_dir / "Subsystems").mkdir()  # пустая

    count = cm._count_objects(config_dir)
    assert count == 3  # 2 Catalogs + 1 Document


def test_build_with_mocked_subprocess(setup):
    """build() вызывает внешние скрипты через subprocess (замокано)."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml("11.3.4", "1C"),
        "CommonModules/Модуль/Модуль.bsl": "Процедура Тест() Экспорт\nКонецПроцедуры",
    })

    cm.add_from_zip("ut11", zip_path, "УТ 11")

    # Мокаем subprocess.run — чтобы не запускать реальные скрипты
    # force=True чтобы не сработал skip_if_fresh (индексов нет → всё missing, но
    # check_freshness вернёт all_fresh=False, поэтому build всё равно запустится)
    with patch("src.services.config_manager.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        report = cm.build("ut11", force=True)

    assert report["name"] == "ut11"
    assert report.get("index", report.get("metadata")) is True
    assert report["api"] is True
    # Новый build() вызывает 4 парсера через subprocess (metadata, skd, forms) + _build_api_reference
    # Минимум 3 subprocess вызова (metadata_extractor, skd_parser, form_analyzer)
    assert mock_run.call_count >= 3


def test_build_non_active(setup):
    """build() для неактивной конфигурации → ValueError."""
    pm, reg, cm, tmp = setup
    reg.add(Configuration(name="archived", title="Archived", status="archived"))
    with pytest.raises(ValueError, match="не активна"):
        cm.build("archived")


def test_archive_and_activate(setup):
    """archive() → activate() цикл."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml("11.3.4", "1C"),
    })

    config = cm.add_from_zip("ut11", zip_path, "УТ 11")
    original_path = config.path

    # Архивируем
    cm.archive("ut11")
    cfg = reg.get("ut11")
    assert cfg.status == "archived"
    assert cfg.archive.exists()
    assert not original_path.exists()

    # Активируем
    cm.activate("ut11")
    cfg = reg.get("ut11")
    assert cfg.status == "active"
    assert cfg.path.exists()
    assert (cfg.path / "Configuration.xml").exists()


# ============================
# Тесты validate_sources()
# ============================

def test_validate_sources_valid(setup):
    """Валидные исходники: Configuration.xml + Catalogs/."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
        "CommonModules/Модуль/Модуль.bsl": "Процедура Тест() Экспорт\nКонецПроцедуры",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    result = cm.validate_sources("ut11")

    assert result.is_valid is True
    assert result.has_configuration_xml is True
    assert result.has_metadata_dirs is True
    assert result.has_bsl_files is True
    assert "Catalogs" in result.found_type_dirs
    assert "CommonModules" in result.found_type_dirs
    assert result.errors == []


def test_validate_sources_missing_configuration_xml(setup):
    """Нет Configuration.xml → невалидно."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Catalogs/Товары/Товары.xml": "<root/>",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    result = cm.validate_sources("ut11")

    assert result.is_valid is False
    assert result.has_configuration_xml is False
    assert any("Configuration.xml" in e for e in result.errors)


def test_validate_sources_missing_metadata_dirs(setup):
    """Нет ни одной критической директории → невалидно."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Roles/Role1/Role1.xml": "<root/>",  # Roles не в MIN_REQUIRED_DIRS
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    result = cm.validate_sources("ut11")

    assert result.is_valid is False
    assert result.has_metadata_dirs is False
    assert any("критических" in e for e in result.errors)


def test_validate_sources_no_bsl_warning(setup):
    """Нет .bsl файлов → warning но is_valid=True."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    result = cm.validate_sources("ut11")

    assert result.is_valid is True
    assert result.has_bsl_files is False
    assert len(result.warnings) >= 1
    assert any(".bsl" in w for w in result.warnings)


def test_validate_sources_non_active(setup):
    """Архивная конфигурация → невалидна."""
    pm, reg, cm, tmp = setup
    reg.add(Configuration(name="archived", title="A", status="archived"))
    result = cm.validate_sources("archived")
    assert result.is_valid is False
    assert any("не активна" in e for e in result.errors)


# ============================
# Тесты check_freshness()
# ============================

def test_check_freshness_no_indexes(setup):
    """Нет индексов → все missing, all_fresh=False."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    report = cm.check_freshness("ut11")

    assert report.all_fresh is False
    assert len(report.missing_indexes) == 4
    assert set(report.missing_indexes) == {"metadata", "api", "skd", "forms"}
    assert report.source_mtime is not None


def test_check_freshness_all_present_and_fresh(setup):
    """Все 4 индекса свежие → all_fresh=True."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    # Создаём индексы с mtime > source (в будущем относительно source)
    import time as _time
    derived_dir = pm.config_derived_dir("ut11")
    derived_dir.mkdir(parents=True, exist_ok=True)
    future_time = _time.time() + 100  # на 100 сек новее

    for idx_file in [
        derived_dir / "unified-metadata-index.json",
        derived_dir / "skd-index.json",
        derived_dir / "form-index.json",
        pm.config_api_reference_json("ut11"),
    ]:
        idx_file.write_text('{"test": true}', encoding='utf-8')
        # Устанавливаем mtime в будущее
        import os as _os
        _os.utime(idx_file, (future_time, future_time))

    report = cm.check_freshness("ut11")

    assert report.all_fresh is True
    assert report.missing_indexes == []
    assert report.stale_indexes == []
    for idx in report.indexes:
        assert idx.exists is True
        assert idx.is_stale is False


def test_check_freshness_stale_index(setup):
    """Один индекс устарел (source новее) → stale."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    # Сначала создаём индексы (старые)
    import os as _os
    import time as _time
    derived_dir = pm.config_derived_dir("ut11")
    derived_dir.mkdir(parents=True, exist_ok=True)
    past_time = _time.time() - 1000  # на 1000 сек старше

    idx_file = derived_dir / "unified-metadata-index.json"
    idx_file.write_text('{}', encoding='utf-8')
    _os.utime(idx_file, (past_time, past_time))

    # Touch source чтобы сделать его новее
    src_file = cm._registry.get("ut11").path / "Catalogs" / "Товары" / "Товары.xml"
    _os.utime(src_file, (_time.time(), _time.time()))

    report = cm.check_freshness("ut11")

    assert report.all_fresh is False
    assert "metadata" in report.stale_indexes
    metadata_status = next(i for i in report.indexes if i.name == "metadata")
    assert metadata_status.is_stale is True
    assert "исходники новее" in metadata_status.stale_reason


# ============================
# Тесты build() с валидацией и freshness
# ============================

def test_build_invalid_sources_raises(setup):
    """build() для невалидных исходников → ValueError."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Roles/Role1/Role1.xml": "<root/>",  # нет Configuration.xml, нет критических директорий
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    with pytest.raises(ValueError, match="невалидны"):
        cm.build("ut11")


def test_build_skips_when_all_fresh(setup):
    """build() с skip_if_fresh=True пропускает если все индексы свежие."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
        "CommonModules/Модуль/Модуль.bsl": "Процедура Тест() Экспорт\nКонецПроцедуры",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    # Создаём все 4 индекса свежими (новее source)
    import os as _os
    import time as _time
    derived_dir = pm.config_derived_dir("ut11")
    derived_dir.mkdir(parents=True, exist_ok=True)
    future_time = _time.time() + 100

    for idx_file in [
        derived_dir / "unified-metadata-index.json",
        derived_dir / "skd-index.json",
        derived_dir / "form-index.json",
        pm.config_api_reference_json("ut11"),
    ]:
        idx_file.write_text('{}', encoding='utf-8')
        _os.utime(idx_file, (future_time, future_time))

    # Мокаем subprocess.run — он НЕ должен вызваться если индексы свежие
    with patch("src.services.config_manager.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        report = cm.build("ut11", skip_if_fresh=True)

    assert mock_run.call_count == 0  # Ноль вызовов!
    assert report["skipped"] == ["all"]
    assert report["reason"] == "all indexes fresh"


def test_build_force_rebuilds_even_when_fresh(setup):
    """build(force=True) пересобирает даже если индексы свежие."""
    pm, reg, cm, tmp = setup
    zip_path = tmp / "ut11.zip"
    _make_zip(zip_path, {
        "Configuration.xml": _config_xml(),
        "Catalogs/Товары/Товары.xml": "<root/>",
        "CommonModules/Модуль/Модуль.bsl": "Процедура Тест() Экспорт\nКонецПроцедуры",
    })
    cm.add_from_zip("ut11", zip_path, "УТ 11")

    # Создаём свежие индексы
    import os as _os
    import time as _time
    derived_dir = pm.config_derived_dir("ut11")
    derived_dir.mkdir(parents=True, exist_ok=True)
    future_time = _time.time() + 100

    for idx_file in [
        derived_dir / "unified-metadata-index.json",
        derived_dir / "skd-index.json",
        derived_dir / "form-index.json",
        pm.config_api_reference_json("ut11"),
    ]:
        idx_file.write_text('{}', encoding='utf-8')
        _os.utime(idx_file, (future_time, future_time))

    # Мокаем subprocess.run — он ДОЛЖЕН вызваться при force=True
    with patch("src.services.config_manager.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        report = cm.build("ut11", force=True)

    assert mock_run.call_count >= 3  # metadata + skd + forms (api через _build_api_reference)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
