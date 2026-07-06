"""
config_search.py — handlers для конфигураций, поиска и метаданных.

P2.2: вынесено из mcp_server.py (группа 1).
Handlers: list[Any]_configs, search_1c_methods, search_code, call_graph,
          get_form_elements, get_api_reference
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import mcp.types as types

from ._async_helpers import run_sync

if TYPE_CHECKING:
    from ..project import Project


async def handle_list_configs(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Список загруженных конфигураций 1С."""
    configs = project.list_configs_info()
    return [
        types.TextContent(
            type="text",
            text=json.dumps(configs, ensure_ascii=False, indent=2),
        )
    ]


async def handle_search_1c_methods(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """BM25 поиск по методам платформы 1С."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    # P1.10: BM25 search может быть тяжёлым (100K+ методов) — не блокируем event loop.
    results = await run_sync(project.search_methods, query, limit)
    return [
        types.TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2),
        )
    ]


async def handle_search_code(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """BM25 поиск по коду конфигурации."""
    query = arguments.get("query", "")
    config_name = arguments.get("config_name", "")
    limit = arguments.get("limit", 10)

    # D-5: Если config_name не указан, пытаемся найти первую активную конфигурацию
    if not config_name:
        configs = project.config_manager._registry.list_active()
        if configs:
            config_name = configs[0].name
        else:
            return [types.TextContent(type="text", text=json.dumps(
                {"error": "config_name required", "hint": "Укажите config_name или используйте list_configs() для просмотра доступных"},
                ensure_ascii=False
            ))]

    from src.services.search_code import search_code

    results = await run_sync(search_code, config_name, query, limit, project.paths)
    return [
        types.TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2),
        )
    ]


async def handle_call_graph(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Граф вызовов методов конфигурации."""
    config_name = arguments.get("config_name", "")
    action = arguments.get("action", "stats")
    module = arguments.get("module", "")
    method = arguments.get("method", "")

    if not config_name:
        return [types.TextContent(type="text", text=json.dumps(
            {"error": "config_name required", "hint": "Используйте list_configs для просмотра доступных конфигураций"},
            ensure_ascii=False
        ))]

    from src.services.call_graph import build_call_graph

    try:
        graph = await run_sync(build_call_graph, config_name, project.paths)
    except FileNotFoundError as e:
        return [types.TextContent(type="text", text=json.dumps(
            {"error": str(e), "hint": f"Сначала добавьте и проиндексируйте конфигурацию: 1c-ai config add --name {config_name} --zip <path> && 1c-ai config build --name {config_name}"},
            ensure_ascii=False
        ))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps(
            {"error": f"call_graph failed: {e}", "hint": "Проверьте что конфигурация проиндексирована"},
            ensure_ascii=False
        ))]
    result: Any = None
    if action == "stats":
        result = graph.get_stats()
    elif action == "callers":
        result = graph.get_callers(module, method)
    elif action == "callees":
        result = graph.get_callees(module, method)
    elif action == "dead-code":
        api_json = project.paths.config_api_reference_json(config_name)
        export_methods: list[tuple[str, str]] = []
        if api_json.exists():
            with open(api_json, encoding="utf-8") as f:
                modules = json.load(f)
            for m in modules:
                for meth in m.get("methods", []):
                    export_methods.append((m["name"], meth["name"]))
        result = [{"module": mod, "method": meth} for mod, meth in graph.find_dead_code(export_methods)]
    elif action == "cycles":
        result = graph.find_cycles()
    else:
        result = graph.to_dict()
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


async def handle_get_form_elements(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Элементы формы конфигурации."""
    config_name = arguments.get("config_name", "")
    form_name = arguments.get("form_name", "")
    api_json = project.paths.config_api_reference_json(config_name)
    if not api_json.exists():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"API reference not found for '{config_name}'"}, ensure_ascii=False),
            )
        ]
    with open(api_json, encoding="utf-8") as f:
        modules = json.load(f)
    forms = [m for m in modules if m.get("type") == "Форма"]
    if not form_name:
        result = [
            {
                "name": f["name"],
                "methods_count": f.get("methods_count", 0),
                "form_elements_count": f.get("form_elements_count", 0),
                "parent_type": f.get("parent_type", ""),
                "parent_name": f.get("parent_name", ""),
            }
            for f in forms
        ]
    else:
        result = []
        for f in forms:
            if f["name"] == form_name:
                result = f.get("form_elements", [])
                break
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


async def handle_get_api_reference(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """API-справочник конфигурации."""
    config_name = arguments.get("config_name", "")
    module = arguments.get("module", "")

    if not module:
        info = project.get_config_info(config_name)
        if info is None:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Конфигурация '{config_name}' не найдена"}, ensure_ascii=False),
                )
            ]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(info, ensure_ascii=False, indent=2),
            )
        ]
    else:
        methods = project.get_api_methods(config_name, module)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(methods, ensure_ascii=False, indent=2),
            )
        ]


# Реестр handlers группы 1
CONFIG_SEARCH_HANDLERS: dict[str, Any] = {
    "list_configs": handle_list_configs,
    "search_1c_methods": handle_search_1c_methods,
    "search_code": handle_search_code,
    "call_graph": handle_call_graph,
    "get_form_elements": handle_get_form_elements,
    "get_api_reference": handle_get_api_reference,
}
