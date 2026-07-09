"""
src/core/mcp/protocols.py — Protocol-контракты для MCP слоя.
"""

from __future__ import annotations

from typing import Any, Protocol


class McpTool(Protocol):
    """Контракт: MCP tool для вызова LLM-агентами."""

    name: str
    description: str

    async def call(self, arguments: dict[str, Any]) -> list[Any]:
        """Выполнить tool с указанными аргументами.

        Args:
            arguments: Аргументы tool

        Returns:
            Список TextContent с результатом.
        """
        ...


class McpServer(Protocol):
    """Контракт: MCP-сервер."""

    async def list_tools(self) -> list[Any]:
        """Вернуть список доступных tools."""
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[Any]:
        """Вызвать tool по имени.

        Args:
            name: Имя tool
            arguments: Аргументы

        Returns:
            Результат вызова.
        """
        ...
