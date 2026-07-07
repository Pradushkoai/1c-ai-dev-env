"""
src/core/ — Ядро проекта 1c-ai-dev-env.

Phase 2 of refactoring plan: layered architecture with Protocol contracts.

Слои (каждый с чёткими ответственностями):
- metadata/   — парсинг XML метаданных 1С
- search/     — поиск (BM25 + FTS5 + vector)
- analyzers/  — BSL AST, security, standards
- mcp/        — MCP server + handlers + tool definitions

Зависимости идут только внутрь (core не зависит от services/adapters).
Контракты слоёв — через typing.Protocol (см. protocols.py в каждом слое).

Backward compat: все старые пути импорта продолжают работать через re-export.
"""

from __future__ import annotations
