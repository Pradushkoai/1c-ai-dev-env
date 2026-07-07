"""
Тесты для src/mcpserver/handlers/config_search.py — конфигурации, поиск, метаданные.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.config_search import (
    handle_call_graph,
    handle_get_api_reference,
    handle_get_form_elements,
    handle_list_configs,
    handle_search_1c_methods,
    handle_search_code,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    return project


# ─── handle_list_configs ───


class TestHandleListConfigs:
    @pytest.mark.asyncio
    async def test_returns_configs(self):
        project = _make_project()
        project.list_configs_info.return_value = [{"name": "ut11", "version": "11.5"}]
        result = await handle_list_configs(project, {})
        data = _parse(result)
        # P1.x: handler возвращает dict с configs + _next_steps
        configs = data["configs"]
        assert len(configs) == 1
        assert configs[0]["name"] == "ut11"
        # _next_steps присутствует для LLM-агентов
        assert "_next_steps" in data
        assert isinstance(data["_next_steps"], list)

    @pytest.mark.asyncio
    async def test_empty_configs(self):
        project = _make_project()
        project.list_configs_info.return_value = []
        result = await handle_list_configs(project, {})
        data = _parse(result)
        # P1.x: даже при пустом списке возвращается dict с configs и _next_steps
        assert data["configs"] == []
        assert "_next_steps" in data


# ─── handle_search_1c_methods ───


class TestHandleSearch1cMethods:
    @pytest.mark.asyncio
    async def test_search_with_query(self):
        project = _make_project()
        project.search_methods.return_value = [{"name": "НайтиПоКоду", "score": 0.95}]
        result = await handle_search_1c_methods(project, {"query": "найти", "limit": 5})
        data = _parse(result)
        # P1.x: handler возвращает dict с results + total + _next_steps
        results = data["results"]
        assert len(results) == 1
        assert results[0]["name"] == "НайтиПоКоду"
        project.search_methods.assert_called_once_with("найти", 5)

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        project = _make_project()
        project.search_methods.return_value = []
        result = await handle_search_1c_methods(project, {"query": ""})
        data = _parse(result)
        # P1.x: пустой запрос возвращает dict с пустым results
        assert data["results"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_default_limit(self):
        project = _make_project()
        project.search_methods.return_value = []
        await handle_search_1c_methods(project, {"query": "test"})
        project.search_methods.assert_called_once_with("test", 10)


# ─── handle_search_code ───


class TestHandleSearchCode:
    @pytest.mark.asyncio
    async def test_search_code_with_config(self):
        project = _make_project()
        with patch("src.services.search_code.search_code") as mock_search:
            mock_search.return_value = [{"name": "СоздатьЗаказ", "score": 0.9}]
            result = await handle_search_code(project, {"query": "заказ", "config_name": "ut11", "limit": 5})
            data = _parse(result)
            # P1.x: handler возвращает dict с results + total + _next_steps
            results = data["results"]
            assert len(results) == 1
            assert results[0]["name"] == "СоздатьЗаказ"
            mock_search.assert_called_once_with("ut11", "заказ", 5, project.paths)

    @pytest.mark.asyncio
    async def test_search_code_empty_results(self):
        project = _make_project()
        with patch("src.services.search_code.search_code") as mock_search:
            mock_search.return_value = []
            result = await handle_search_code(project, {"query": "несуществующее", "config_name": "ut11"})
            data = _parse(result)
            # P1.x: пустой результат возвращает dict с пустым results
            assert data["results"] == []
            assert data["total"] == 0


# ─── handle_call_graph ───


class TestHandleCallGraph:
    @pytest.mark.asyncio
    async def test_stats_action(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.get_stats.return_value = {"total_methods": 100, "total_edges": 500}
            mock_build.return_value = graph
            result = await handle_call_graph(project, {"config_name": "ut11", "action": "stats"})
            data = _parse(result)
            # P1.x: handler возвращает dict с result + _next_steps
            assert data["result"]["total_methods"] == 100
            assert "_next_steps" in data

    @pytest.mark.asyncio
    async def test_cycles_action(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.find_cycles.return_value = [["A", "B", "A"]]
            mock_build.return_value = graph
            result = await handle_call_graph(project, {"config_name": "ut11", "action": "cycles"})
            data = _parse(result)
            assert len(data["result"]) == 1

    @pytest.mark.asyncio
    async def test_callers_action(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.get_callers.return_value = [{"module": "M1", "method": "F1"}]
            mock_build.return_value = graph
            result = await handle_call_graph(
                project,
                {"config_name": "ut11", "action": "callers", "module": "M1", "method": "F2"},
            )
            data = _parse(result)
            assert len(data["result"]) == 1

    @pytest.mark.asyncio
    async def test_callees_action(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.get_callees.return_value = [{"module": "M2", "method": "F3"}]
            mock_build.return_value = graph
            result = await handle_call_graph(
                project,
                {"config_name": "ut11", "action": "callees", "module": "M1", "method": "F1"},
            )
            data = _parse(result)
            assert len(data["result"]) == 1

    @pytest.mark.asyncio
    async def test_dead_code_action(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.find_dead_code.return_value = [("M1", "unused_method")]
            mock_build.return_value = graph
            # Also need to mock api_reference_json
            api_path = MagicMock()
            api_path.exists.return_value = False
            project.paths.config_api_reference_json.return_value = api_path
            result = await handle_call_graph(project, {"config_name": "ut11", "action": "dead-code"})
            data = _parse(result)
            assert len(data["result"]) == 1
            assert data["result"][0]["module"] == "M1"

    @pytest.mark.asyncio
    async def test_unknown_action_returns_dict(self):
        project = _make_project()
        with patch("src.services.call_graph.build_call_graph") as mock_build:
            graph = MagicMock()
            graph.to_dict.return_value = {"nodes": [], "edges": []}
            mock_build.return_value = graph
            result = await handle_call_graph(project, {"config_name": "ut11", "action": "unknown"})
            data = _parse(result)
            # P1.x: handler оборачивает в dict с result + _next_steps
            assert "nodes" in data["result"]
            assert "_next_steps" in data


# ─── handle_get_form_elements ───


class TestHandleGetFormElements:
    @pytest.mark.asyncio
    async def test_api_reference_not_found(self):
        project = _make_project()
        api_path = MagicMock()
        api_path.exists.return_value = False
        project.paths.config_api_reference_json.return_value = api_path
        result = await handle_get_form_elements(project, {"config_name": "ut11"})
        data = _parse(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_all_forms(self):
        project = _make_project()
        api_path = MagicMock()
        api_path.exists.return_value = True
        project.paths.config_api_reference_json.return_value = api_path
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
                [{"name": "Форма1", "type": "Форма", "methods_count": 5, "form_elements_count": 10}]
            )
            result = await handle_get_form_elements(project, {"config_name": "ut11"})
            data = _parse(result)
            assert len(data) == 1
            assert data[0]["name"] == "Форма1"

    @pytest.mark.asyncio
    async def test_specific_form_elements(self):
        project = _make_project()
        api_path = MagicMock()
        api_path.exists.return_value = True
        project.paths.config_api_reference_json.return_value = api_path
        forms_data = [
            {"name": "Форма1", "type": "Форма", "form_elements": [{"name": "Кнопка1"}]},
        ]
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(forms_data)
            result = await handle_get_form_elements(project, {"config_name": "ut11", "form_name": "Форма1"})
            data = _parse(result)
            assert len(data) == 1
            assert data[0]["name"] == "Кнопка1"


# ─── handle_get_api_reference ───


class TestHandleGetApiReference:
    @pytest.mark.asyncio
    async def test_list_modules(self):
        project = _make_project()
        project.get_config_info.return_value = {"name": "ut11", "modules": 100}
        result = await handle_get_api_reference(project, {"config_name": "ut11"})
        data = _parse(result)
        assert data["name"] == "ut11"

    @pytest.mark.asyncio
    async def test_config_not_found(self):
        project = _make_project()
        project.get_config_info.return_value = None
        result = await handle_get_api_reference(project, {"config_name": "nonexistent"})
        data = _parse(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_specific_module_methods(self):
        project = _make_project()
        project.get_api_methods.return_value = [{"name": "Метод1", "type": "Функция"}]
        result = await handle_get_api_reference(project, {"config_name": "ut11", "module": "ОбщийМодуль1"})
        data = _parse(result)
        assert len(data) == 1
        assert data[0]["name"] == "Метод1"
