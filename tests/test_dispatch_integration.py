"""
T14: Integration тест — call_tool через диспетчер mcp_server.py.

Предотвращает повторение BUG-1 (HIGH_LEVEL_HANDLERS не были подключены к
диспетчеру, 6/7 visible tools не работали).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server import create_mcp_server


def _parse(result):
    """Parse MCP tool result — handles different response structures."""
    # MCP CallToolResult has .root.content list
    if hasattr(result, "root"):
        if hasattr(result.root, "content"):
            content = result.root.content[0]
        else:
            content = result.root[0]
    elif hasattr(result, "content"):
        content = result.content[0]
    elif isinstance(result, list):
        content = result[0]
    else:
        content = result
    text = content.text if hasattr(content, "text") else str(content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


class TestCallToolDispatch:
    """T14: Integration тесты — call_tool через диспетчер.

    Эти тесты вызывают tools через MCP Server call_tool handler,
    а не напрямую. Это ловит баги в диспетчере (как BUG-1).
    """

    @pytest.fixture
    def mcp_server(self):
        """MCP server с mocked Project."""
        with patch("src.mcp_server.Project"):
            return create_mcp_server()

    @pytest.fixture
    def call_handler(self, mcp_server):
        """Get call_tool handler from server."""
        from mcp.types import CallToolRequest
        handler = next(
            h for req_type, h in mcp_server.request_handlers.items()
            if req_type == CallToolRequest
        )
        return handler

    @pytest.mark.asyncio
    async def test_plan_dispatched(self, call_handler):
        """T14: plan() доступен через диспетчер (не Unknown tool)."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "plan", "arguments": {"query": "создай справочник"}},
                )
            )
        data = _parse(result)
        # Не должно быть error "Unknown tool"
        assert "error" not in data or "Unknown tool" not in data.get("error", "")
        assert "plan_id" in data or "intent" in data

    @pytest.mark.asyncio
    async def test_gather_dispatched(self, call_handler):
        """T14: gather() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            # gather без plan — должен вернуть error о plan, не Unknown tool
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "gather", "arguments": {}},
                )
            )
        data = _parse(result)
        assert "Unknown tool" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_generate_dispatched(self, call_handler):
        """T14: generate() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "generate", "arguments": {"task": "test"}},
                )
            )
        data = _parse(result)
        assert "Unknown tool" not in data.get("error", "")
        assert "artifact_id" in data or "error" in data

    @pytest.mark.asyncio
    async def test_validate_dispatched(self, call_handler):
        """T14: validate() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "validate", "arguments": {}},
                )
            )
        data = _parse(result)
        assert "Unknown tool" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_explain_dispatched(self, call_handler):
        """T14: explain() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "explain", "arguments": {}},
                )
            )
        data = _parse(result)
        assert "Unknown tool" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_run_cli_dispatched(self, call_handler):
        """T14: run_cli() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "run_cli", "arguments": {"command": "list_configs"}},
                )
            )
        data = _parse(result)
        # Не должно быть Unknown tool — значит dispatch работает
        assert "Unknown tool" not in data.get("error", data.get("raw", ""))

    @pytest.mark.asyncio
    async def test_data_status_dispatched(self, call_handler):
        """T14: data_status() доступен через диспетчер."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            with patch("src.services.data_package.DataPackage"):
                result = await call_handler(
                    CallToolRequest(
                        method="tools/call",
                        params={"name": "data_status", "arguments": {}},
                    )
                )
        data = _parse(result)
        assert "Unknown tool" not in data.get("error", "")

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, call_handler):
        """T14: неизвестный tool возвращает Unknown tool error."""
        from mcp.types import CallToolRequest

        with patch("src.project.Project"):
            result = await call_handler(
                CallToolRequest(
                    method="tools/call",
                    params={"name": "nonexistent_tool", "arguments": {}},
                )
            )
        data = _parse(result)
        assert "Unknown tool" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_all_visible_tools_dispatched(self, call_handler):
        """T14: ВСЕ 7 visible tools доступны через диспетчер.

        Это regression тест для BUG-1 — после R1 рефакторинга
        HIGH_LEVEL_HANDLERS не были подключены к диспетчеру.
        """
        from mcp.types import CallToolRequest
        from src.mcpserver.tools.tool_definitions import MCP_VISIBLE_TOOLS

        for tool_name in MCP_VISIBLE_TOOLS:
            with patch("src.project.Project"):
                result = await call_handler(
                    CallToolRequest(
                        method="tools/call",
                        params={"name": tool_name, "arguments": {}},
                    )
                )
            data = _parse(result)
            error = data.get("error", "")
            assert "Unknown tool" not in error, f"Tool '{tool_name}' returned Unknown tool error: {error}"
