"""
D3.2 + 14.2 (2026-07-05): BSL tree-sitter adapter.

Интегрирует tree-sitter-bsl для замены regex-based правил на AST-based.
Опциональная зависимость: pip install tree-sitter tree-sitter-bsl

Если tree-sitter не установлен — fallback на regex (существующие правила).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_TREE_SITTER_AVAILABLE: bool | None = None
_BS_LANGUAGE: Any = None
_BS_PARSER: Any = None


def _check_tree_sitter() -> bool:
    """Проверить доступность tree-sitter + tree-sitter-bsl."""
    global _TREE_SITTER_AVAILABLE, _BS_LANGUAGE, _BS_PARSER
    if _TREE_SITTER_AVAILABLE is None:
        try:
            import tree_sitter
            import tree_sitter_bsl

            _BS_LANGUAGE = tree_sitter.Language(tree_sitter_bsl.language())
            _BS_PARSER = tree_sitter.Parser(_BS_LANGUAGE)
            _TREE_SITTER_AVAILABLE = True
        except ImportError:
            _TREE_SITTER_AVAILABLE = False
            logger.debug(
                "tree-sitter-bsl не установлен. "
                "pip install tree-sitter tree-sitter-bsl для AST-based правил."
            )
    return _TREE_SITTER_AVAILABLE


def parse_bsl(code: str) -> Any:
    """
    D3.2/14.2: Распарсить BSL код через tree-sitter → AST.

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

    code_bytes = code.encode("utf-8")
    return _BS_PARSER.parse(code_bytes)


def is_tree_sitter_available() -> bool:
    """Проверить, доступен ли tree-sitter-bsl."""
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
