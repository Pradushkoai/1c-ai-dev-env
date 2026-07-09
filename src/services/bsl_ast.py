"""
D3.2 + 14.2 (2026-07-05): BSL tree-sitter adapter.

P1-A-Integration (Phase 1.3, 2026-07-07): thin wrapper над bsl_tree_sitter.
Раньше здесь была отдельная инициализация tree-sitter — теперь делегирует в
bsl_tree_sitter (единый источник истины).

Если tree-sitter не установлен — fallback на regex (существующие правила).

Deprecated: используйте src.services.bsl_tree_sitter напрямую для новых
кода. Этот модуль сохранён для backward compat (parse_bsl, get_ast_node_types,
has_syntax_errors), будет удалён в v7.0.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# P1-A-Integration: единая точка проверки доступности tree-sitter
from src.services.bsl_tree_sitter import (
    BslTreeSitterParser,
    is_available as _ts_is_available,
)

# Глобальный singleton parser (lazy init)
_BS_PARSER: BslTreeSitterParser | None = None
_BS_TREE_CACHE: dict[int, Any] = {}  # id(code) → tree (для parse_bsl)


def _check_tree_sitter() -> bool:
    """Проверить доступность tree-sitter + tree-sitter-bsl.

    P1-A-Integration: делегирует в bsl_tree_sitter.is_available().
    """
    return _ts_is_available()


def _get_parser() -> BslTreeSitterParser | None:
    """Возвращает singleton parser (создаёт при первом вызове)."""
    global _BS_PARSER
    if not _check_tree_sitter():
        return None
    if _BS_PARSER is None:
        _BS_PARSER = BslTreeSitterParser()
    return _BS_PARSER


def parse_bsl(code: str) -> Any:
    """
    D3.2/14.2: Распарсить BSL код через tree-sitter → AST Tree.

    P1-A-Integration: использует BslTreeSitterParser из bsl_tree_sitter
    для создания parser, но возвращает низкоуровневый tree-sitter Tree
    (для backward compat с ast_analyzer.py и ast_analyzers_extended.py).

    Args:
        code: BSL исходный код.

    Returns:
        tree-sitter Tree объект, или None если tree-sitter не установлен.

    Example:
        tree = parse_bsl("Процедура Тест()\\nКонецПроцедуры")
        if tree:
            root = tree.root_node
            for child in root.children:
                print(child.type)
    """
    if not _check_tree_sitter():
        return None

    # Используем tree-sitter напрямую для получения Tree (не BslSymbol[])
    # bsl_tree_sitter возвращает BslSymbol[], а нам нужен Tree для ast_analyzer
    try:
        import tree_sitter
        import tree_sitter_bsl

        language = tree_sitter.Language(tree_sitter_bsl.language())
        parser = tree_sitter.Parser(language)
        code_bytes = code.encode("utf-8", errors="replace")
        return parser.parse(code_bytes)
    except Exception as e:
        logger.debug("parse_bsl failed: %s", e)
        return None


def is_tree_sitter_available() -> bool:
    """Проверить, доступен ли tree-sitter-bsl.

    P1-A-Integration: делегирует в bsl_tree_sitter.is_available().
    """
    return _check_tree_sitter()


def get_ast_node_types(code: str) -> list[str]:
    """
    D3.2: Получить список типов AST узлов для BSL кода.

    Полезно для отладки и понимания структуры AST.

    Args:
        code: BSL исходный код.

    Returns:
        Список типов узлов (строки), или пустой список если tree-sitter недоступен.
    """
    tree = parse_bsl(code)
    if tree is None:
        return []

    types: list[str] = []

    def walk(node: Any) -> None:
        types.append(node.type)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return types


def has_syntax_errors(code: str) -> bool:
    """
    D3.2: Проверить BSL код на синтаксические ошибки через tree-sitter.

    Args:
        code: BSL исходный код.

    Returns:
        True если есть синтаксические ошибки, False если код валиден.
        Возвращает False если tree-sitter недоступен (fallback).
    """
    tree = parse_bsl(code)
    if tree is None:
        return False  # Fallback: не можем проверить

    return tree.root_node.has_error
