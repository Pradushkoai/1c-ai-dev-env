"""Тесты для Configuration model."""
from pathlib import Path

import pytest
from src.models.configuration import Configuration


def test_configuration_basic():
    """Базовое создание конфигурации."""
    c = Configuration(name="test", title="Test Config")
    assert c.name == "test"
    assert c.title == "Test Config"
    assert c.version == "unknown"
    assert c.status == "active"
    assert not c.is_archived()
    assert c.is_active() is False  # нет path


def test_configuration_from_dict():
    """Создание из dict (config-registry.json)."""
    data = {"name": "УТ 11", "version": "11.3.4.197", "status": "active"}
    c = Configuration.from_dict("ut11", data, Path("/tmp"))
    assert c.name == "ut11"
    assert c.version == "11.3.4.197"
    assert c.title == "УТ 11"


def test_configuration_to_dict():
    """Сериализация в dict."""
    c = Configuration(name="test", title="Test", version="1.0")
    d = c.to_dict()
    assert d["name"] == "Test"  # title сериализуется как name
    assert d["version"] == "1.0"
    assert d["status"] == "active"


def test_configuration_is_active(tmp_path):
    """is_active() зависит от path и status."""
    c = Configuration(name="t", title="T", path=tmp_path, status="active")
    assert c.is_active() is True

    c.status = "archived"
    assert c.is_active() is False


def test_configuration_common_modules_dir(tmp_path):
    """common_modules_dir возвращает Path если папка существует."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "CommonModules").mkdir()

    c = Configuration(name="t", title="T", path=cfg_dir)
    assert c.common_modules_dir == cfg_dir / "CommonModules"

    c2 = Configuration(name="t", title="T", path=tmp_path)
    assert c2.common_modules_dir is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
