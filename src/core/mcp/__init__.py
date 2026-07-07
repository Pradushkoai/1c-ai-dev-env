"""
src/core/mcp/ — MCP server + handlers + tool definitions.

Phase 2 of refactoring: core layer for MCP protocol.

Backward compat: реэкспортирует из src.mcpserver для нового пути.
"""

from __future__ import annotations

# Re-export MCP server
from src.mcp_server import (
    _get_tools_description,
    create_mcp_server,
    run_mcp_server,
    run_mcp_server_sync,
)
from src.mcpserver.handlers import ALL_HANDLERS
from src.mcpserver.tools.tool_definitions import (
    get_all_descriptions,
    get_all_tool_definitions,
)

__all__ = [
    "ALL_HANDLERS",
    "_get_tools_description",
    "create_mcp_server",
    "get_all_descriptions",
    "get_all_tool_definitions",
    "run_mcp_server",
    "run_mcp_server_sync",
]
