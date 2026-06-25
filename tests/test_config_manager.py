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
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from setup_src.services.path_manager import PathManager
from setup_src.services.config_manager import ConfigManager
from setup_src.models.config_registry import ConfigurationRegistry
from setup_src.models.configuration import Configuration


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
    with patch("setup_src.services.config_manager.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        report = cm.build("ut11")

    assert report["name"] == "ut11"
    assert report["index"] is True
    assert report["api"] is True
    # Должно быть 2 вызова: build_metadata_index + build_api_reference
    assert mock_run.call_count == 2


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
