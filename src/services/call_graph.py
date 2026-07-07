"""
call_graph.py — Граф вызовов методов конфигурации 1С (re-export module).

Phase 3.4 of refactoring: разделён на 3 модуля для SRP:
- call_graph_model.py    — CallEdge, CallGraph (модель + алгоритмы)
- call_graph_parser.py   — парсеры BSL (tree-sitter + regex)
- call_graph_builder.py  — build_call_graph (оркестратор)

Этот файл — тонкая обёртка для backward compat. Все публичные символы
реэкспортируются, существующий импорт `from src.services.call_graph import
build_call_graph, get_callers, get_callees` продолжает работать.

Пример:
    from src.services.call_graph import build_call_graph, get_callers, get_callees
    graph = build_call_graph("obhod", paths)           # построить граф
    callers = get_callers(graph, "ОбменДокументы", "ВыполнитьПолныйОбмен")
    callees = get_callees(graph, "ОбменДокументы", "ВыполнитьПолныйОбмен")
"""

from __future__ import annotations

# Re-export из новых модулей для backward compat
from .call_graph_builder import build_call_graph
from .call_graph_model import CallEdge, CallGraph
from .call_graph_parser import (
    BSL_KEYWORDS,
    CROSS_MODULE_CALL_PATTERN,
    LOCAL_CALL_PATTERN,
    STANDARD_OBJECTS,
    _find_current_procedure,
    _get_module_name_from_path,
    _parse_bsl_file_with_regex,
    _parse_bsl_file_with_tree_sitter,
    _strip_comments,
    _TREE_SITTER_AVAILABLE,
)


# ============================================================================
# Backward compat функции-обёртки
# ============================================================================


def get_callers(graph: CallGraph, module: str, method: str) -> list[dict]:
    """Кто вызывает данный метод? (backward compat wrapper)."""
    return graph.get_callers(module, method)


def get_callees(graph: CallGraph, module: str, method: str) -> list[dict]:
    """Кого вызывает данный метод? (backward compat wrapper)."""
    return graph.get_callees(module, method)


def find_cycles(graph: CallGraph) -> list[list[str]]:
    """Найти циклы в графе (backward compat wrapper)."""
    return graph.find_cycles()


def find_dead_code(graph: CallGraph, export_methods: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Найти мёртвый код (backward compat wrapper)."""
    return graph.find_dead_code(export_methods)


__all__ = [
    "BSL_KEYWORDS",
    "CROSS_MODULE_CALL_PATTERN",
    "CallEdge",
    "CallGraph",
    "LOCAL_CALL_PATTERN",
    "STANDARD_OBJECTS",
    "_TREE_SITTER_AVAILABLE",
    "_find_current_procedure",
    "_get_module_name_from_path",
    "_parse_bsl_file_with_regex",
    "_parse_bsl_file_with_tree_sitter",
    "_strip_comments",
    "build_call_graph",
    "find_cycles",
    "find_dead_code",
    "get_callees",
    "get_callers",
]
