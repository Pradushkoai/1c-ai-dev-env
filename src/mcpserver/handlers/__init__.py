"""
src/mcp/handlers/__init__.py — реестр MCP handlers.

P2.2: handlers вынесены из mcp_server.py по группам.
Каждый handler: async (project, arguments) -> list[types.TextContent]
"""

from __future__ import annotations

from .analyzers import ANALYZER_HANDLERS
from .config_search import CONFIG_SEARCH_HANDLERS
from .dsl_cfe import DSL_CFE_HANDLERS
from .generate import GENERATE_HANDLERS
from .inspect_data import INSPECT_DATA_HANDLERS
from .misc import MISC_HANDLERS
from .quality import QUALITY_HANDLERS
from .structure import STRUCTURE_HANDLERS

# Объединённый реестр всех handlers
ALL_HANDLERS: dict = {}
ALL_HANDLERS.update(CONFIG_SEARCH_HANDLERS)
ALL_HANDLERS.update(DSL_CFE_HANDLERS)
ALL_HANDLERS.update(ANALYZER_HANDLERS)
ALL_HANDLERS.update(MISC_HANDLERS)
ALL_HANDLERS.update(INSPECT_DATA_HANDLERS)
ALL_HANDLERS.update(STRUCTURE_HANDLERS)
ALL_HANDLERS.update(GENERATE_HANDLERS)
ALL_HANDLERS.update(QUALITY_HANDLERS)

__all__ = ["ALL_HANDLERS"]
