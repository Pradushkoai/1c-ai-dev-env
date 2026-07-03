"""
src.mcpserver.tools — определения MCP tools.

P2.2: вынесено из mcp_server.py для декомпозиции (SRP).
Содержит:
- tool_definitions.py: определения 45 types.Tool (для list_tools handler)
- get_all_descriptions(): статические описания (для CLI)
"""

from __future__ import annotations

from .tool_definitions import get_all_descriptions, get_all_tool_definitions

__all__ = ["get_all_descriptions", "get_all_tool_definitions"]
