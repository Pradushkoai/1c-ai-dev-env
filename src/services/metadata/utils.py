from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

class XMLUtils:
    """Общие утилиты для работы с XML 1С — без дублирования."""

    @staticmethod
    def strip_ns(tag: str) -> str:
        """Убирает namespace из тега."""
        return tag.split("}")[1] if "}" in tag else tag

    @staticmethod
    def get_child(elem, tag: str):
        """Возвращает первого потомка с указанным тегом (без namespace)."""
        if elem is None:
            return None
        for child in elem:
            if XMLUtils.strip_ns(child.tag) == tag:
                return child
        return None

    @staticmethod
    def get_children(elem, tag: str) -> list[Any]:
        """Возвращает всех потомков с указанным тегом."""
        if elem is None:
            return []
        return [child for child in elem if XMLUtils.strip_ns(child.tag) == tag]

    @staticmethod
    def get_text(elem, tag: str, default: str = "") -> str:
        """Возвращает текст первого потомка с тегом."""
        child = XMLUtils.get_child(elem, tag)
        if child is not None:
            return child.text or ""
        return default

    @staticmethod
    def get_bool(elem, tag: str, default: bool = False) -> bool:
        """Возвращает bool из текста тега."""
        text = XMLUtils.get_text(elem, tag)
        if text == "true":
            return True
        if text == "false":
            return False
        return default

    @staticmethod
    def get_int(elem, tag: str, default: int = 0) -> int:
        """Возвращает int из текста тега."""
        text = XMLUtils.get_text(elem, tag)
        try:
            return int(text) if text else default
        except ValueError:
            return default

    @staticmethod
    def get_synonym(properties_elem) -> str:
        """Извлекает синоним из v8:item/v8:content."""
        if properties_elem is None:
            return ""
        syn_elem = XMLUtils.get_child(properties_elem, "Synonym")
        if syn_elem is None:
            return ""
        for item in syn_elem:
            if XMLUtils.strip_ns(item.tag) == "item":
                content = XMLUtils.get_text(item, "content")
                if content:
                    return content
        return ""

    @staticmethod
    def parse_type(type_elem) -> list[str]:
        """Парсит элемент <Type> и возвращает список типов."""
        if type_elem is None:
            return []
        types = []
        for child in type_elem:
            if XMLUtils.strip_ns(child.tag) == "Type":
                if child.text:
                    types.append(child.text)
        return types

    @staticmethod
    def get_root_tag(root) -> str:
        """Возвращает тег корневого элемента без namespace."""
        return XMLUtils.strip_ns(root.tag)

    @staticmethod
    def safe_parse(xml_path: Path) -> tuple[ET.Element | None, str]:
        """Безопасный парсинг XML. Возвращает (root, error)."""
        try:
            tree = ET.parse(xml_path)
            return tree.getroot(), ""
        except ET.ParseError as e:
            return None, str(e)
        except Exception as e:
            return None, str(e)


# ============================================================================
# УНИВЕРСАЛЬНЫЙ ПАРСЕР ОБЪЕКТОВ
# ============================================================================


