"""Тесты для Configuration model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "setup_src"))

from models.configuration import Configuration


def test_configuration_basic():
    c = Configuration(name="test", title="Test Config")
    assert c.name == "test"
    assert c.title == "Test Config"
    assert c.version == "unknown"
    assert c.status == "active"
    assert not c.is_archived()
    assert c.is_active() == False  # нет path


def test_configuration_from_dict():
    data = {"name": "УТ 11", "version": "11.3.4.197", "status": "active"}
    c = Configuration.from_dict("ut11", data, Path("/tmp"))
    assert c.name == "ut11"
    assert c.version == "11.3.4.197"
    assert c.title == "УТ 11"


def test_configuration_to_dict():
    c = Configuration(name="test", title="Test", version="1.0")
    d = c.to_dict()
    assert d["name"] == "Test"
    assert d["version"] == "1.0"


if __name__ == "__main__":
    test_configuration_basic()
    test_configuration_from_dict()
    test_configuration_to_dict()
    print("✅ Все тесты прошли")
