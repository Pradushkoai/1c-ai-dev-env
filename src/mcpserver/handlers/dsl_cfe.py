"""
dsl_cfe.py — handlers для DSL компиляторов, CFE, СКД и графа зависимостей.

P2.2: вынесено из mcp_server.py (группа 2).
Handlers: dsl_compile_*, cfe_*, skd_trace, build_dependency_graph, dependency_query
"""

from __future__ import annotations

# Заглушка — handlers будут перенесены поэтапно
DSL_CFE_HANDLERS: dict = {}
