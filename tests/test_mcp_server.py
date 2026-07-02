"""
Тесты для MCP-сервера (Фаза 1):
- _get_tools_description() — статическое описание tools
- create_mcp_server() — создание сервера
- call_tool handler — вызов каждого tool
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server import _get_tools_description, create_mcp_server

# ============ _get_tools_description ============


def test_get_tools_description_returns_29_tools():
    """Должно быть 29 tools (v5.2 — все анализаторы + epf_factory)."""
    tools = _get_tools_description()
    assert len(tools) == 29


def test_get_tools_description_names():
    """Имена tools соответствуют спецификации."""
    tools = _get_tools_description()
    expected = {
        "list_configs",
        "search_1c_methods",
        "search_code",
        "call_graph",
        "get_form_elements",
        "get_api_reference",
        "analyze_bsl",
        "check_standards",
        "solve_context",
        "solve_check",
        "data_status",
        "get_object_structure",
        "get_skd_schema",
        "get_form_structure",
        "generate_processing",
        "generate_report",
        "build_epf",
        "validate_generated",
        "get_knowledge",
        "audit_security",
        "get_code_metrics",
        "check_transactions",
        "analyze_architecture",
        "analyze_queries",
        "check_form_quality",
        "check_skd_quality",
        "diff_configs",
        "epf_factory_create",
        "epf_factory_templates",
    }
    actual = {t["name"] for t in tools}
    assert actual == expected


def test_get_tools_description_has_required_fields():
    """Каждый tool имеет name, description, required_params, optional_params."""
    tools = _get_tools_description()
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "required_params" in t
        assert "optional_params" in t
        assert isinstance(t["required_params"], list)
        assert isinstance(t["optional_params"], list)


def test_get_tools_description_search_has_query_required():
    """search_1c_methods требует query."""
    tools = {t["name"]: t for t in _get_tools_description()}
    assert "query" in tools["search_1c_methods"]["required_params"]
    assert "limit" in tools["search_1c_methods"]["optional_params"]


def test_get_tools_description_get_api_reference_requires_config():
    """get_api_reference требует config_name."""
    tools = {t["name"]: t for t in _get_tools_description()}
    assert "config_name" in tools["get_api_reference"]["required_params"]
    assert "module" in tools["get_api_reference"]["optional_params"]


# ============ create_mcp_server ============


def test_create_mcp_server_returns_server():
    """create_mcp_server возвращает Server."""
    with patch("src.project.Project"):
        server = create_mcp_server()
    assert server is not None
    assert server.name == "1c-ai-dev-env"


def test_create_mcp_server_registers_handlers():
    """Server регистрирует handlers для list_tools и call_tool."""
    with patch("src.project.Project"):
        server = create_mcp_server()
    # Проверяем что есть зарегистрированные handlers
    # MCP SDK хранит их в server.request_handlers
    assert hasattr(server, "request_handlers")
    assert len(server.request_handlers) > 0


# ============ call_tool handler (через Project mock) ============


@pytest.fixture
def mcp_server_with_mock_project():
    """MCP-сервер с замоканным Project."""
    with patch("src.mcp_server.Project") as project_cls:
        project = MagicMock()
        project_cls.return_value = project

        # list_configs_info возвращает список конфигураций
        project.list_configs_info.return_value = [
            {
                "name": "ut11",
                "version": "11.3.4.197",
                "status": "active",
                "objects_count": 5000,
                "api_methods_count": 1242,
                "has_api": True,
            }
        ]

        # get_config_info возвращает инфо
        project.get_config_info.return_value = {
            "name": "ut11",
            "version": "11.3.4.197",
            "status": "active",
            "objects_count": 5000,
            "modules": [{"name": "ОбщегоНазначения", "methods_count": 10}],
        }

        # get_api_methods возвращает методы
        project.get_api_methods.return_value = [
            {
                "module": "ОбщегоНазначения",
                "name": "СообщитьОбОшибке",
                "type": "Процедура",
                "params": [],
                "description": "Test",
                "returns": "",
                "signature": "СообщитьОбОшибке()",
            }
        ]

        # search_methods
        project.search_methods.return_value = [{"score": 0.9, "name_ru": "Найти", "name_en": "Find"}]

        # bsl_analyzer
        result_mock = MagicMock()
        result_mock.total = 5
        result_mock.by_code = {"BSL_DIAG": 5}
        result_mock.diagnostics = [{"code": "BSL_DIAG", "severity": "warning", "line": 10, "message": "test"}]
        project.bsl_analyzer.analyze.return_value = result_mock

        # paths mock для solve_check
        project.paths.bsl_ls_binary.exists.return_value = True
        project.paths.scripts_dir = Path("/nonexistent")
        project.paths.root = Path("/nonexistent")

        server = create_mcp_server()
        return server, project


def test_call_list_configs(mcp_server_with_mock_project):
    """call_tool('list_configs', {}) возвращает JSON с конфигурациями."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(CallToolRequest(method="tools/call", params={"name": "list_configs", "arguments": {}}))
    )
    assert result.root.content is not None
    assert len(result.root.content) > 0
    text = result.root.content[0].text
    data = json.loads(text)
    assert isinstance(data, list)
    assert data[0]["name"] == "ut11"


def test_call_search_1c_methods(mcp_server_with_mock_project):
    """call_tool('search_1c_methods', {query: ...}) возвращает результаты поиска."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(method="tools/call", params={"name": "search_1c_methods", "arguments": {"query": "найти"}})
        )
    )
    project.search_methods.assert_called_once_with("найти", 10)
    data = json.loads(result.root.content[0].text)
    assert len(data) == 1
    assert data[0]["name_ru"] == "Найти"


def test_call_get_api_reference_without_module(mcp_server_with_mock_project):
    """get_api_reference без module возвращает инфо о конфигурации."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(
                method="tools/call", params={"name": "get_api_reference", "arguments": {"config_name": "ut11"}}
            )
        )
    )
    project.get_config_info.assert_called_once_with("ut11")
    data = json.loads(result.root.content[0].text)
    assert data["name"] == "ut11"
    assert "modules" in data


def test_call_get_api_reference_with_module(mcp_server_with_mock_project):
    """get_api_reference с module возвращает методы конкретного модуля."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(
                method="tools/call",
                params={
                    "name": "get_api_reference",
                    "arguments": {"config_name": "ut11", "module": "ОбщегоНазначения"},
                },
            )
        )
    )
    project.get_api_methods.assert_called_once_with("ut11", "ОбщегоНазначения")
    data = json.loads(result.root.content[0].text)
    assert len(data) == 1
    assert data[0]["module"] == "ОбщегоНазначения"


def test_call_get_api_reference_unknown_config(mcp_server_with_mock_project):
    """get_api_reference для неизвестной конфигурации возвращает error."""
    server, project = mcp_server_with_mock_project
    project.get_config_info.return_value = None
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(
                method="tools/call", params={"name": "get_api_reference", "arguments": {"config_name": "unknown"}}
            )
        )
    )
    data = json.loads(result.root.content[0].text)
    assert "error" in data


def test_call_solve_context(mcp_server_with_mock_project):
    """solve_context возвращает собранный контекст (через TaskProcessor)."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(
                method="tools/call",
                params={"name": "solve_context", "arguments": {"query": "создать справочник", "config": "ut11"}},
            )
        )
    )
    data = json.loads(result.root.content[0].text)
    assert data["query"] == "создать справочник"
    assert data["config"] == "ut11"
    # Новый формат через TaskContext.to_dict()
    assert "platform_methods" in data
    assert "api_modules" in data
    assert "metadata_objects" in data
    assert "skd_schemas" in data
    assert "forms" in data
    assert "knowledge_articles" in data
    assert "standards_summary" in data
    assert "missing_sources" in data
    # 7 источников → 302 проверки
    assert data["standards_summary"]["total_checks"] == 302


def test_call_analyze_bsl(mcp_server_with_mock_project):
    """analyze_bsl возвращает диагностики BSL LS."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(
            CallToolRequest(
                method="tools/call", params={"name": "analyze_bsl", "arguments": {"file_path": "/tmp/test.bsl"}}
            )
        )
    )
    data = json.loads(result.root.content[0].text)
    assert data["total"] == 5
    assert "BSL_DIAG" in data["by_code"]


def test_call_unknown_tool(mcp_server_with_mock_project):
    """call_tool с неизвестным именем возвращает error."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    result = asyncio.run(
        handler(CallToolRequest(method="tools/call", params={"name": "unknown_tool", "arguments": {}}))
    )
    data = json.loads(result.root.content[0].text)
    assert "error" in data
    assert "unknown_tool" in data["error"].lower()


def test_call_list_tools(mcp_server_with_mock_project):
    """list_tools handler возвращает все зарегистрированные Tool объекты.

    Включает tools из _get_tools_description() (29) + дополнительные tools,
    зарегистрированные динамически через @server.tool (build_dependency_graph,
    dependency_query, openspec_*, dsl_compile_*, cfe_*, skd_trace, inspect).
    """
    server, project = mcp_server_with_mock_project
    from mcp.types import ListToolsRequest

    handler = next((h for req_type, h in server.request_handlers.items() if req_type == ListToolsRequest), None)
    assert handler is not None

    result = asyncio.run(handler(ListToolsRequest(method="tools/list")))
    # 29 (из _get_tools_description) + 16 (динамически зарегистрированные) = 45
    assert len(result.root.tools) == 45
    names = {t.name for t in result.root.tools}
    assert "list_configs" in names
    assert "solve_check" in names
    assert "search_code" in names
    assert "data_status" in names


def test_call_data_status(mcp_server_with_mock_project):
    """data_status возвращает статус данных проекта."""
    server, project = mcp_server_with_mock_project
    from mcp.types import CallToolRequest

    handler = next(h for req_type, h in server.request_handlers.items() if req_type == CallToolRequest)

    # Мокаем DataPackage.status
    with patch("src.services.data_package.DataPackage") as dp_cls:
        dp = MagicMock()
        dp_cls.return_value = dp
        dp.status.return_value = {
            "has_platform_index": True,
            "has_platform_methods": True,
            "configs": [{"name": "ut11", "has_api": True}],
            "autosave_available": False,
            "autosave_info": None,
        }

        result = asyncio.run(
            handler(CallToolRequest(method="tools/call", params={"name": "data_status", "arguments": {}}))
        )
        data = json.loads(result.root.content[0].text)
        assert data["has_platform_index"] is True
        assert data["has_platform_methods"] is True
        assert len(data["configs"]) == 1
        assert data["autosave_available"] is False
