"""
MCP-сервер для 1C AI Development Environment.

Экспортирует 62 tools для MCP-совместимых клиентов (Cursor, Claude Desktop,
VS Code, JetBrains). Полный список tools — в src/mcpserver/tools/tool_definitions.py.

Запуск: 1c-ai mcp serve
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, cast

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .project import Project
from .services.logger import configure_logging, get_logger

# MCP-сервер пишет логи в stderr (stdout занят под MCP-протокол)
# JSON-формат включается через LOG_FORMAT=json
configure_logging()
log = get_logger("src.mcp_server")


def _get_tools_description() -> list[dict]:
    """
    Статическое описание VISIBLE tools (для CLI без запуска сервера).

    Возвращает только 10 ключевых инструментов (как list_tools handler).
    """
    from .mcpserver.tools.tool_definitions import get_mcp_visible_tools

    tools = get_mcp_visible_tools()
    result: list[dict] = []
    for t in tools:
        schema = t.inputSchema or {}
        properties = schema.get("properties", {})
        required_list = schema.get("required", [])
        required_set = set(required_list)
        required_params = [p for p in required_list if p in properties]
        optional_params = [p for p in properties.keys() if p not in required_set]
        result.append({
            "name": t.name,
            "description": t.description,
            "required_params": required_params,
            "optional_params": optional_params,
        })
    result.sort(key=lambda x: x["name"])
    return result


def create_mcp_server() -> Server:
    """Создать MCP-сервер с tools для 1C AI Development Environment."""
    from .mcpserver.instructions import SYSTEM_INSTRUCTIONS

    server = Server(
        "1c-ai-dev-env",
        instructions=SYSTEM_INSTRUCTIONS,
    )
    project = Project()

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Возвращает список MCP tools, видимых LLM.

        Гибридный подход: LLM видит только 10 ключевых инструментов
        (get_mcp_visible_tools) вместо всех 54. Это предотвращает
        tool interference — когда LLM путается в большом списке.
        Остальные инструменты доступны через CLI.
        """
        from .mcpserver.tools.tool_definitions import get_mcp_visible_tools

        return get_mcp_visible_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """Выполняет tool и возвращает результат."""
        # Структурированный лог каждого вызова — для отладки и аудита
        with contextlib.suppress(Exception):
            log.info(f"mcp_tool_called: {name} args={list(arguments.keys()) if arguments else []}")

        # T1 (2026-07-10): HIGH_LEVEL_HANDLERS проверяются ПЕРВЫМИ —
        # это 6 из 7 visible tools (plan, gather, generate, validate, explain, run_cli).
        # Без этого R1 рефакторинг не работает — LLM получает "Unknown tool".
        from .mcpserver.handlers import HIGH_LEVEL_HANDLERS

        handler = HIGH_LEVEL_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 1 (config/search/metadata)
        from .mcpserver.handlers import CONFIG_SEARCH_HANDLERS

        handler = CONFIG_SEARCH_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 3a (BSL анализаторы)
        from .mcpserver.handlers import ANALYZER_HANDLERS

        handler = ANALYZER_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 2 (dsl/cfe/skd/depgraph)
        from .mcpserver.handlers import DSL_CFE_HANDLERS

        handler = DSL_CFE_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 4 (openspec)
        from .mcpserver.handlers import MISC_HANDLERS

        handler = MISC_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 5 (inspect/data)
        from .mcpserver.handlers import INSPECT_DATA_HANDLERS

        handler = INSPECT_DATA_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для оставшихся handlers (группы 6-8)
        # Структура/Генерация/Качество — проверяются одним проходом,
        # без дублирования (раньше STRUCTURE_HANDLERS искался дважды).
        from .mcpserver.handlers import GENERATE_HANDLERS, QUALITY_HANDLERS, STRUCTURE_HANDLERS

        for handlers_dict in (STRUCTURE_HANDLERS, GENERATE_HANDLERS, QUALITY_HANDLERS):
            handler = handlers_dict.get(name)
            if handler is not None:
                return cast(list[types.TextContent], await handler(project, arguments))

        # P2.2: dict[str, Any]-dispatch для handlers группы 6 (query — Phase D)
        from .mcpserver.handlers import QUERY_HANDLERS

        handler = QUERY_HANDLERS.get(name)
        if handler is not None:
            return cast(list[types.TextContent], await handler(project, arguments))

        # Неизвестный tool
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False),
            )
        ]

    return server


async def run_mcp_server() -> None:
    """Точка входа MCP-сервера."""
    # P1.5: опциональный Prometheus /metrics endpoint
    from .services.metrics import maybe_start_metrics_server

    maybe_start_metrics_server()

    server = create_mcp_server()
    init_options = server.create_initialization_options()
    async with stdio_server() as (read, write):
        await server.run(read, write, init_options)


def run_mcp_server_sync() -> None:
    """Синхронная точка входа (для console_scripts в pyproject.toml)."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    run_mcp_server_sync()
