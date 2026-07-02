#!/usr/bin/env python3
"""
xml_parser.py — Универсальный безопасный XML парсер с поддержкой lxml (опционально).

Использует lxml если установлен (быстрее, C-based), иначе fallback на xml.etree.
Оба варианта безопасны от XXE атак.
"""

from __future__ import annotations

from pathlib import Path

# Пытаемся импортировать lxml (быстрее), fallback на xml.etree
try:
    from lxml import etree as _etree

    _HAS_LXML = True
    _PARSER_NAME = "lxml"
except ImportError:
    import xml.etree.ElementTree as _etree

    _HAS_LXML = False
    _PARSER_NAME = "xml.etree"


def get_parser_name() -> str:
    """Возвращает имя используемого XML парсера."""
    return _PARSER_NAME


def has_lxml() -> bool:
    """Проверяет, доступен ли lxml."""
    return _HAS_LXML


def parse_xml(xml_path: Path | str):
    """Парсит XML файл. Возвращает root Element.

    Использует lxml если доступен (в 3-5 раз быстрее на больших файлах).
    Оба варианта безопасны от XXE.

    Args:
        xml_path: Путь к XML файлу

    Returns:
        Element: корневой элемент

    Raises:
        ParseError: при ошибке парсинга
    """
    xml_path = Path(xml_path)

    if _HAS_LXML:
        # lxml: отключаем external entities (защита от XXE)
        parser = _etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            dtd_validation=False,
            load_dtd=False,
        )
        tree = _etree.parse(str(xml_path), parser=parser)
        return tree.getroot()
    else:
        # xml.etree: по умолчанию безопасен от XXE
        tree = _etree.parse(str(xml_path))
        return tree.getroot()


def fromstring(xml_string: str):
    """Парсит XML из строки."""
    if _HAS_LXML:
        parser = _etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            dtd_validation=False,
            load_dtd=False,
        )
        return _etree.fromstring(xml_string.encode("utf-8"), parser=parser)
    else:
        return _etree.fromstring(xml_string)


def strip_ns(tag: str) -> str:
    """Убирает namespace из тега."""
    if _HAS_LXML and isinstance(tag, bytes):
        tag = tag.decode("utf-8")
    return tag.split("}")[-1] if "}" in tag else tag
