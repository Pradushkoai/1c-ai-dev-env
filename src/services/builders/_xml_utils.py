"""
D2.2 (2026-07-05): XML утилиты для builders.

Вынесено из builders/config_index.py (1004 LOC) для переиспользования.
Эти функции используются всеми builder'ами для парсинга XML метаданных 1С.
"""

from __future__ import annotations

from typing import Any


def strip_ns(tag: str) -> str:
    """Убрать namespace из XML тега."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def get_child(elem: Any, tag: str) -> Any:
    """Вернуть первого потомка с указанным тегом (без namespace)."""
    if elem is None:
        return None
    for child in elem:
        if strip_ns(child.tag) == tag:
            return child
    return None


def get_text(elem: Any, tag: str, default: str = "") -> str:
    """Вернуть текст первого потомка с тегом."""
    child = get_child(elem, tag)
    if child is not None:
        return child.text or ""
    return default


def get_synonym_text(parent: Any, tag: str = "Synonym") -> str:
    """Извлечь синоним из элемента."""
    elem = get_child(parent, tag)
    if elem is None:
        return ""
    if elem.text and elem.text.strip():
        return elem.text.strip()
    for item in elem:
        if strip_ns(item.tag) == "item":
            content = get_text(item, "content")
            if content:
                return content
    return ""


def get_type_description(type_elem: Any) -> str:
    """Извлекает описание типа из элемента <Type>."""
    if type_elem is None:
        return ""

    types: list[str] = []
    for child in type_elem:
        tag = strip_ns(child.tag)
        if tag == "Type":
            text = (child.text or "").strip()
            if text:
                types.append(text)

    type_qualifiers: list[str] = []
    number_qualifiers = get_child(type_elem, "NumberQualifiers")
    if number_qualifiers is not None:
        precision = get_text(number_qualifiers, "Precision")
        scale = get_text(number_qualifiers, "Scale")
        if precision:
            type_qualifiers.append(f"({precision},{scale or '0'})")

    string_qualifiers = get_child(type_elem, "StringQualifiers")
    if string_qualifiers is not None:
        length = get_text(string_qualifiers, "Length")
        if length:
            type_qualifiers.append(f"[{length}]")

    result = ", ".join(types) if types else ""
    if type_qualifiers:
        result += " " + " ".join(type_qualifiers)
    return result
