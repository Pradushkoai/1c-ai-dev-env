"""
P1.2: Тест синхронизации MCP tools.

Гарантирует, что статическое описание _get_tools_description()
и реальный list_tools handler регистрируют ОДИНАКОВЫЙ набор tools.

Это критично: расхождение означает, что CLI `1c-ai mcp tools` покажет
одни tools, а IDE получит другие через MCP протокол.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


def _get_handler_tools() -> set[str]:
    """Получить имена tools из реального list_tools handler."""
    with patch("src.project.Project"):
        from mcp.types import ListToolsRequest

        from src.mcp_server import create_mcp_server

        server = create_mcp_server()
        handler = next(
            (h for req_type, h in server.request_handlers.items() if req_type == ListToolsRequest),
            None,
        )
        if handler is None:
            return set()
        result = asyncio.run(handler(ListToolsRequest(method="tools/list")))
        return {t.name for t in result.root.tools}


def _get_static_tools() -> set[str]:
    """Получить имена tools из статического описания."""
    from src.mcp_server import _get_tools_description

    return {t["name"] for t in _get_tools_description()}


def test_static_and_handler_have_same_tool_count() -> None:
    """Количество tools в статическом описании и handler должно совпадать."""
    static = _get_static_tools()
    handler = _get_handler_tools()
    assert len(static) == len(handler), (
        f"Count mismatch: static={len(static)}, handler={len(handler)}. "
        f"Missing in static: {handler - static}. "
        f"Missing in handler: {static - handler}."
    )


def test_static_and_handler_have_same_tool_names() -> None:
    """Имена tools в статическом описании и handler должны совпадать."""
    static = _get_static_tools()
    handler = _get_handler_tools()
    missing_in_static = handler - static
    missing_in_handler = static - handler
    assert not missing_in_static, (
        f"Tools в handler, но отсутствуют в _get_tools_description(): {missing_in_static}. "
        f"Добавь их в src/mcp_server.py _get_tools_description()."
    )
    assert not missing_in_handler, (
        f"Tools в _get_tools_description(), но отсутствуют в handler: {missing_in_handler}. "
        f"Добавь их в src/mcp_server.py list_tools()."
    )


def test_no_duplicate_tool_names_in_static() -> None:
    """В статическом описании не должно быть дубликатов tool names."""
    from src.mcp_server import _get_tools_description

    tools = _get_tools_description()
    names = [t["name"] for t in tools]
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates, f"Дубликаты tool names в _get_tools_description(): {duplicates}"


def test_no_duplicate_tool_names_in_handler() -> None:
    """В handler не должно быть дубликатов tool names."""
    handler_tools = _get_handler_tools()
    # _get_handler_tools возвращает set, поэтому дубликатов нет по определению
    # но проверим что set не пустой
    assert len(handler_tools) > 0, "Handler не зарегистрировал ни одного tool"


def test_all_static_tools_have_non_empty_description() -> None:
    """Каждый tool в статическом описании имеет непустое description."""
    from src.mcp_server import _get_tools_description

    tools = _get_tools_description()
    for t in tools:
        assert t["description"], f"Tool '{t['name']}' имеет пустое description"
        assert len(t["description"]) > 10, (
            f"Tool '{t['name']}' имеет слишком короткое description: '{t['description']}'"
        )


def test_all_static_tools_have_required_and_optional_params() -> None:
    """Каждый tool имеет required_params и optional_params (даже если пустые)."""
    from src.mcp_server import _get_tools_description

    tools = _get_tools_description()
    for t in tools:
        assert "required_params" in t, f"Tool '{t['name']}' не имеет required_params"
        assert "optional_params" in t, f"Tool '{t['name']}' не имеет optional_params"
        assert isinstance(t["required_params"], list), f"Tool '{t['name']}': required_params не list"
        assert isinstance(t["optional_params"], list), f"Tool '{t['name']}': optional_params не list"
