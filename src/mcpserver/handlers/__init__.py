"""
src/mcp/handlers/__init__.py — реестр MCP handlers.

P2.2: handlers вынесены из mcp_server.py по группам.
Каждый handler: async (project, arguments) -> list[types.TextContent]

R1 (2026-07-09): Добавлены HIGH_LEVEL_HANDLERS (plan, gather, generate,
validate, explain, run_cli) — 6 high-level tools, видимых LLM вместо 12.
"""

from __future__ import annotations
from typing import Any

from .analyzers import ANALYZER_HANDLERS
from .config_search import CONFIG_SEARCH_HANDLERS
from .dsl_cfe import DSL_CFE_HANDLERS
from .generate import GENERATE_HANDLERS
from .high_level import HIGH_LEVEL_HANDLERS
from .inspect_data import INSPECT_DATA_HANDLERS
from .misc import MISC_HANDLERS
from .quality import QUALITY_HANDLERS
from .query import QUERY_HANDLERS
from .structure import STRUCTURE_HANDLERS

# Объединённый реестр всех handlers
ALL_HANDLERS: dict[str, Any] = {}
ALL_HANDLERS.update(CONFIG_SEARCH_HANDLERS)
ALL_HANDLERS.update(DSL_CFE_HANDLERS)
ALL_HANDLERS.update(ANALYZER_HANDLERS)
ALL_HANDLERS.update(MISC_HANDLERS)
ALL_HANDLERS.update(INSPECT_DATA_HANDLERS)
ALL_HANDLERS.update(STRUCTURE_HANDLERS)
ALL_HANDLERS.update(GENERATE_HANDLERS)
ALL_HANDLERS.update(QUALITY_HANDLERS)
ALL_HANDLERS.update(QUERY_HANDLERS)
ALL_HANDLERS.update(HIGH_LEVEL_HANDLERS)

__all__ = ["ALL_HANDLERS", "HIGH_LEVEL_HANDLERS"]
