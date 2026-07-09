"""
call_graph_builder.py — Оркестратор построения графа вызовов.

Phase 3.4 of refactoring: выделение из call_graph.py.

Содержит:
- build_call_graph(config_name, paths, use_cache) → CallGraph
- Гибридная стратегия: tree-sitter (локальные) + regex (кросс-модульные)
- Кэширование в derived/configs/<name>/call-graph-index.json
- Дедупликация рёбер

Использует:
- call_graph_model.CallGraph, CallEdge — модель графа
- call_graph_parser._parse_bsl_file_with_tree_sitter, _parse_bsl_file_with_regex — парсеры
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .call_graph_model import CallEdge, CallGraph
from .call_graph_parser import (
    _parse_bsl_file_with_regex,
    _parse_bsl_file_with_tree_sitter,
    _TREE_SITTER_AVAILABLE,
    _get_module_name_from_path,
)
from .path_manager import PathManager

logger = logging.getLogger(__name__)


def build_call_graph(
    config_name: str,
    paths: PathManager | None = None,
    use_cache: bool = True,
) -> CallGraph:
    """
    Построить граф вызовов для конфигурации.

    Парсит все .bsl файлы, находит:
    1. Кросс-модульные вызовы: ОбменДокументы.ВыполнитьПолныйОбмен()
    2. Локальные вызовы: ВыполнитьЗапрос() внутри того же модуля

    P1-A-Integration: если установлен tree-sitter-bsl (pip install -e ".[ast]"),
    использует AST для точного извлечения вызовов. Иначе — regex fallback.

    При use_cache=True (по умолчанию) — загружает из cache файла если существует,
    иначе строит и сохраняет. Cache файл: derived/configs/<name>/call-graph-index.json

    Args:
        config_name: Имя конфигурации (ut11, obhod, ...)
        paths: PathManager (если None — создаётся)
        use_cache: Использовать кэш (default: True)

    Returns:
        CallGraph с рёбрами и индексами
    """
    if paths is None:
        paths = PathManager()

    # D-5: Check cache first
    cache_path = paths.config_derived_dir(config_name) / "call-graph-index.json"
    if use_cache:
        cached = CallGraph.load(cache_path)
        if cached is not None:
            logger.info(
                "Call graph loaded from cache: %s (%d edges)", cache_path, len(cached.edges)
            )
            return cached

    config_dir = paths.config_path(config_name)
    if not config_dir.exists():
        raise FileNotFoundError(
            f"Конфигурация '{config_name}' не найдена. "
            f"Выполните: 1c-ai config add --name {config_name} --zip <path.zip> && "
            f"1c-ai config build --name {config_name}"
        )

    graph = CallGraph(config_name=config_name)

    # Загружаем список экспортных методов из api-reference.json
    api_json = paths.config_api_reference_json(config_name)
    export_methods: set[str] = set()  # "ИмяМодуля.ИмяМетода"
    module_names: set[str] = set()
    if api_json.exists():
        try:
            with open(api_json, encoding="utf-8") as f:
                modules = json.load(f)
            for mod in modules:
                mod_name = mod.get("name", "")
                module_names.add(mod_name)
                for method in mod.get("methods", []):
                    export_methods.add(f"{mod_name}.{method.get('name', '')}")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to load api-reference.json for '%s': %s", config_name, e
            )

    # Парсим все .bsl файлы
    bsl_files = list(config_dir.rglob("*.bsl"))

    # P1-A-Integration: выбираем метод парсинга
    use_tree_sitter = _TREE_SITTER_AVAILABLE
    if use_tree_sitter:
        logger.info(
            "Building call graph with tree-sitter-bsl (AST) for local calls + regex for cross-module"
        )
    else:
        logger.info("tree-sitter-bsl не установлен — используем regex для всех вызовов")

    for bsl_path in bsl_files:
        mod_name = _get_module_name_from_path(bsl_path, config_dir)

        # P1-A-Integration: tree-sitter path для локальных вызовов
        if use_tree_sitter:
            try:
                edges = _parse_bsl_file_with_tree_sitter(
                    bsl_path, config_dir, mod_name, module_names, export_methods
                )
                graph.edges.extend(edges)
            except Exception as e:
                logger.debug(
                    "tree-sitter parsing failed for %s: %s, falling back to regex",
                    bsl_path,
                    e,
                )
                edges = _parse_bsl_file_with_regex(
                    bsl_path, config_dir, mod_name, module_names, export_methods
                )
                graph.edges.extend(edges)
                continue

        # Regex path: кросс-модульные вызовы (всегда, даже при tree-sitter)
        edges_regex = _parse_bsl_file_with_regex(
            bsl_path, config_dir, mod_name, module_names, export_methods
        )
        if not use_tree_sitter:
            graph.edges.extend(edges_regex)
        else:
            # Берём из regex только кросс-модульные вызовы (callee_module != mod_name)
            for edge in edges_regex:
                if edge.callee_module != edge.caller_module:
                    graph.edges.append(edge)

    # Дедупликация рёбер (tree-sitter + regex могли дать дубли)
    seen_edges: set[tuple] = set()
    unique_edges: list[CallEdge] = []
    for edge in graph.edges:
        key = (edge.caller_module, edge.caller_method, edge.callee_module, edge.callee_method, edge.line, edge.file)
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(edge)
    if len(unique_edges) != len(graph.edges):
        logger.debug(
            "Deduplicated edges: %d → %d", len(graph.edges), len(unique_edges)
        )
    graph.edges = unique_edges

    graph._reindex()

    # D-5: Save to cache for fast subsequent loads
    if use_cache:
        try:
            graph.save(cache_path)
            logger.info(
                "Call graph saved to cache: %s (%d edges)", cache_path, len(graph.edges)
            )
        except Exception as e:
            logger.warning("Failed to save call graph cache: %s", e)

    return graph
