"""
Тесты для новых API-методов Project (Фаза 0):
- list_configs_info()
- get_config_info(name)
- get_api_methods(config_name, module_name)
- search_methods(query, limit)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.project import Project


@pytest.fixture
def project_with_configs(tmp_path):
    """Project с двумя конфигурациями и API-справочником для одной из них."""
    # Конфигурации
    cfg1 = MagicMock()
    cfg1.name = "ut11"
    cfg1.version = "11.3.4.197"
    cfg1.status = "active"
    cfg1.objects_count = 5000

    cfg2 = MagicMock()
    cfg2.name = "priemka"
    cfg2.version = "1.0"
    cfg2.status = "active"
    cfg2.objects_count = 50

    # API-справочник для ut11 (с 2 модулями)
    api_data = [
        {
            "name": "ОбщегоНазначения",
            "methods_count": 2,
            "methods": [
                {
                    "name": "СообщитьОбОшибке",
                    "type": "Процедура",
                    "params": [{"name": "Текст"}],
                    "description": "Выводит сообщение об ошибке",
                    "returns": "",
                    "signature": "СообщитьОбОшибке(Текст)",
                },
                {
                    "name": "ВыполнитьЗапрос",
                    "type": "Функция",
                    "params": [{"name": "Запрос"}],
                    "description": "Выполняет запрос",
                    "returns": "Результат",
                    "signature": "ВыполнитьЗапрос(Запрос)",
                },
            ],
        },
        {
            "name": "ДокументыОбщие",
            "methods_count": 1,
            "methods": [
                {
                    "name": "ПровестиДокумент",
                    "type": "Процедура",
                    "params": [],
                    "description": "",
                    "returns": "",
                    "signature": "ПровестиДокумент()",
                },
            ],
        },
    ]

    api_path = tmp_path / "ut11_api.json"
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(api_data, f, ensure_ascii=False)

    # Патчим классы в пространстве имён src.project
    with patch("src.project.PathManager") as pm_cls, patch("src.project.ConfigurationRegistry") as reg_cls:
        pm = MagicMock()
        pm_cls.return_value = pm
        pm.root = tmp_path
        pm.validate.return_value = {"bsl_ls": True, "scripts": True}

        def config_api_reference_json(name):
            if name == "ut11":
                return api_path
            return tmp_path / f"{name}_api.json"  # не существует

        pm.config_api_reference_json.side_effect = config_api_reference_json

        reg = MagicMock()
        reg_cls.return_value = reg
        reg.list_all.return_value = [cfg1, cfg2]
        reg.get.side_effect = lambda name: {"ut11": cfg1, "priemka": cfg2}.get(name)

        project = Project()
        yield project


def test_list_configs_info_returns_list(project_with_configs):
    """list_configs_info возвращает список dict с инфо о каждой конфигурации."""
    result = project_with_configs.list_configs_info()
    assert isinstance(result, list)
    assert len(result) == 2


def test_list_configs_info_has_required_fields(project_with_configs):
    """Каждый элемент содержит все обязательные поля."""
    result = project_with_configs.list_configs_info()
    for item in result:
        assert "name" in item
        assert "version" in item
        assert "status" in item
        assert "objects_count" in item
        assert "api_methods_count" in item
        assert "has_api" in item


def test_list_configs_info_counts_api_methods(project_with_configs):
    """api_methods_count считается правильно: ut11 = 2+1 = 3, priemka = 0."""
    result = {c["name"]: c for c in project_with_configs.list_configs_info()}
    assert result["ut11"]["api_methods_count"] == 3
    assert result["ut11"]["has_api"] is True
    assert result["priemka"]["api_methods_count"] == 0
    assert result["priemka"]["has_api"] is False


def test_get_config_info_returns_dict(project_with_configs):
    """get_config_info возвращает dict с инфо."""
    info = project_with_configs.get_config_info("ut11")
    assert info is not None
    assert info["name"] == "ut11"
    assert info["version"] == "11.3.4.197"
    assert info["objects_count"] == 5000


def test_get_config_info_includes_modules(project_with_configs):
    """get_config_info включает список модулей."""
    info = project_with_configs.get_config_info("ut11")
    assert "modules" in info
    assert len(info["modules"]) == 2
    assert info["modules"][0]["name"] == "ОбщегоНазначения"
    assert info["modules"][0]["methods_count"] == 2


def test_get_config_info_unknown_returns_none(project_with_configs):
    """get_config_info для неизвестной конфигурации возвращает None."""
    assert project_with_configs.get_config_info("unknown") is None


def test_get_api_methods_all_modules(project_with_configs):
    """get_api_methods без module_name возвращает методы всех модулей."""
    methods = project_with_configs.get_api_methods("ut11")
    assert len(methods) == 3
    names = [m["name"] for m in methods]
    assert "СообщитьОбОшибке" in names
    assert "ВыполнитьЗапрос" in names
    assert "ПровестиДокумент" in names


def test_get_api_methods_specific_module(project_with_configs):
    """get_api_methods с module_name возвращает только методы этого модуля."""
    methods = project_with_configs.get_api_methods("ut11", "ОбщегоНазначения")
    assert len(methods) == 2
    assert all(m["module"] == "ОбщегоНазначения" for m in methods)


def test_get_api_methods_unknown_config_returns_empty(project_with_configs):
    """get_api_methods для конфигурации без API возвращает пустой список."""
    assert project_with_configs.get_api_methods("priemka") == []


def test_get_api_methods_method_fields(project_with_configs):
    """Каждый метод содержит все нужные поля."""
    methods = project_with_configs.get_api_methods("ut11", "ОбщегоНазначения")
    for m in methods:
        assert "module" in m
        assert "name" in m
        assert "type" in m
        assert "params" in m
        assert "description" in m
        assert "returns" in m
        assert "signature" in m


def test_search_methods_no_index_returns_empty(project_with_configs):
    """search_methods без индекса возвращает пустой список."""
    project_with_configs.paths.fast_search_index = Path("/nonexistent")
    result = project_with_configs.search_methods("запрос")
    assert result == []


def test_search_methods_with_index(project_with_configs, tmp_path):
    """search_methods делегирует в services.search."""
    fake_results = [{"score": 0.9, "name_ru": "Найти", "name_en": "Find"}]
    # Создаём существующий файл-индекс, чтобы exists() вернул True
    fake_index_path = tmp_path / "index.pkl"
    fake_index_path.touch()
    project_with_configs.paths.fast_search_index = fake_index_path
    with patch("src.services.search.search", return_value=fake_results) as mock_search:
        result = project_with_configs.search_methods("найти", limit=5)
    assert result == fake_results
    mock_search.assert_called_once_with(fake_index_path, "найти", 5)
