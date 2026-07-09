"""
src/adapters/ — Адаптеры внешних зависимостей.

Phase 2 of refactoring: adapter layer для изоляции внешних библиотек.

Каждый адаптер оборачивает внешнюю зависимость в единый интерфейс,
что позволяет менять реализацию без правок в core/services.

Backward compat: реэкспортирует из src.services для нового пути.
"""

from __future__ import annotations

# Re-export адаптеров внешних зависимостей
from src.services.bsl_analyzer import BSLAnalyzer as BslLsAdapter
from src.services.bsl_ast import (
    get_ast_node_types,
    has_syntax_errors,
    is_tree_sitter_available,
    parse_bsl,
)
from src.services.bsl_tree_sitter import (
    BslTreeSitterParser,
    extract_symbols,
    extract_symbols_from_file,
    is_available,
)
from src.services.cf.extractor import V8Container as CFExtractor  # noqa: F401 — v8unpack adapter

__all__ = [
    "BslLsAdapter",
    "BslTreeSitterParser",
    "CFExtractor",
    "extract_symbols",
    "extract_symbols_from_file",
    "get_ast_node_types",
    "is_available",
    "is_tree_sitter_available",
    "has_syntax_errors",
    "parse_bsl",
]
