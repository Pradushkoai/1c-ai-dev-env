from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class UniversalObjectParser:
    """Универсальный парсер для любого типа объекта метаданных 1С.

    Парсит XML файл метаданных и извлекает:
    - Базовые свойства (Name, UUID, Synonym, Comment)
    - Все Properties (динамически — все теги внутри <Properties>)
    - ChildObjects (рекурсивно — Attributes, TabularSections, Forms, Commands, и т.д.)
    - StandardAttributes
    - Специфичные свойства (CodeLength, NumberLength, и т.д.)
    """

    def __init__(self):
        self.utils = XMLUtils()

    def parse(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит XML файл метаданных объекта.

        Args:
            xml_path: Путь к XML файлу

        Returns:
            dict[str, Any] с метаданными объекта или None при ошибке
        """
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        # Корневой тег = тип объекта (Catalog, Document, и т.д.)
        # Ищем первый дочерний элемент (не MetaDataObject)
        obj_elem = None
        obj_type = ""

        root_tag = XMLUtils.get_root_tag(root)
        if root_tag == "MetaDataObject":
            # Ищем первый дочерний элемент внутри MetaDataObject
            for child in root:
                obj_elem = child
                obj_type = XMLUtils.strip_ns(child.tag)
                break
        else:
            obj_elem = root
            obj_type = root_tag

        if obj_elem is None:
            return None

        uuid = obj_elem.get("uuid", "")

        # Парсим Properties
        properties = XMLUtils.get_child(obj_elem, "Properties")
        props = self._parse_properties(properties)

        # Парсим ChildObjects
        child_objects = XMLUtils.get_child(obj_elem, "ChildObjects")
        children = self._parse_child_objects(child_objects)

        # Парсим StandardAttributes (если есть)
        std_attrs = []
        if properties is not None:
            for sa in XMLUtils.get_children(properties, "StandardAttributes"):
                std_attrs.append(self._parse_standard_attribute(sa))

        # Парсим InternalInfo (если есть)
        internal_info = XMLUtils.get_child(obj_elem, "InternalInfo")

        result = {
            "type": obj_type,
            "name": props.get("Name", ""),
            "uuid": uuid,
            "synonym": props.get("Synonym", ""),
            "comment": props.get("Comment", ""),
            "properties": props,
            "standard_attributes": std_attrs,
            "child_objects": children,
            "file": str(xml_path.name),
        }

        # Убираем Name/Synonym/Comment из properties (они уже в верхнем уровне)
        for key in ("Name", "Synonym", "Comment"):
            props.pop(key, None)

        return result

    def _parse_properties(self, properties_elem) -> dict[str, Any]:
        """Парсит ВСЕ свойства из <Properties> — динамически."""
        if properties_elem is None:
            return {}

        props = {}
        for child in properties_elem:
            tag = XMLUtils.strip_ns(child.tag)

            # Synonym — особый случай
            if tag == "Synonym":
                props["Synonym"] = XMLUtils.get_synonym(properties_elem)
                continue

            # StandardAttributes — обрабатываем отдельно
            if tag == "StandardAttributes":
                continue

            # Простой текст
            if child.text and child.text.strip():
                props[tag] = child.text.strip()
            else:
                # Проверяем есть ли вложенные Item (RegisterRecords)
                items = XMLUtils.get_children(child, "Item")
                if items:
                    # Это список (например RegisterRecords → Item)
                    item_list = []
                    for item in items:
                        if item.text and item.text.strip():
                            item_list.append(item.text.strip())
                    if item_list:
                        props[tag] = item_list
                    else:
                        props[tag] = ""
                else:
                    # Проверяем есть ли вложенный v8:item
                    items = XMLUtils.get_children(child, "item")
                    if items:
                        # Это локализованное поле
                        for item in items:
                            content = XMLUtils.get_text(item, "content")
                            if content:
                                props[tag] = content
                                break
                    else:
                        # Пустой тег
                        props[tag] = ""

        return props

    def _parse_child_objects(self, child_objects_elem) -> dict[str, Any]:
        """Парсит <ChildObjects> — рекурсивно извлекает все вложенные объекты."""
        if child_objects_elem is None:
            return {}

        result = {
            "attributes": [],
            "tabular_sections": [],
            "forms": [],
            "commands": [],
            "enum_values": [],
            "predefined": [],
            "templates": [],
            "other": [],
        }

        for child in child_objects_elem:
            tag = XMLUtils.strip_ns(child.tag)

            if tag == "Attribute":
                result["attributes"].append(self._parse_attribute(child))
            elif tag == "TabularSection":
                result["tabular_sections"].append(self._parse_tabular_section(child))
            elif tag == "Form":
                result["forms"].append({"name": child.text or "", "uuid": child.get("uuid", "")})
            elif tag == "Command":
                result["commands"].append({"name": child.text or "", "uuid": child.get("uuid", "")})
            elif tag == "EnumValue":
                enum_props = XMLUtils.get_child(child, "Properties")
                result["enum_values"].append(
                    {
                        "name": XMLUtils.get_text(enum_props, "Name") if enum_props is not None else "",
                        "synonym": XMLUtils.get_synonym(enum_props) if enum_props is not None else "",
                        "uuid": child.get("uuid", ""),
                    }
                )
            elif tag == "Template":
                result["templates"].append({"name": child.text or "", "uuid": child.get("uuid", "")})
            elif tag in ("Dimension", "Resource"):
                # Для регистров: измерения и ресурсы
                attr = self._parse_attribute(child)
                attr["kind"] = tag
                result["attributes"].append(attr)
            else:
                # Другие вложенные объекты
                result["other"].append(
                    {
                        "type": tag,
                        "name": child.text or XMLUtils.get_text(child, "Name"),
                        "uuid": child.get("uuid", ""),
                    }
                )

        return result

    def _parse_attribute(self, attr_elem) -> dict[str, Any]:
        """Парсит <Attribute> — реквизит объекта."""
        uuid = attr_elem.get("uuid", "")
        properties = XMLUtils.get_child(attr_elem, "Properties")

        result = {
            "name": XMLUtils.get_text(properties, "Name") if properties is not None else "",
            "uuid": uuid,
            "synonym": XMLUtils.get_synonym(properties) if properties is not None else "",
            "comment": XMLUtils.get_text(properties, "Comment") if properties is not None else "",
            "types": [],
            "fill_checking": XMLUtils.get_text(properties, "FillChecking") if properties is not None else "",
            "use": XMLUtils.get_text(properties, "Use") if properties is not None else "",
            "indexing": XMLUtils.get_text(properties, "Indexing") if properties is not None else "",
        }

        if properties is not None:
            type_elem = XMLUtils.get_child(properties, "Type")
            result["types"] = XMLUtils.parse_type(type_elem)

        return result

    def _parse_tabular_section(self, ts_elem) -> dict[str, Any]:
        """Парсит <TabularSection> — табличную часть."""
        uuid = ts_elem.get("uuid", "")
        properties = XMLUtils.get_child(ts_elem, "Properties")

        result = {
            "name": XMLUtils.get_text(properties, "Name") if properties is not None else "",
            "uuid": uuid,
            "synonym": XMLUtils.get_synonym(properties) if properties is not None else "",
            "attributes": [],
        }

        # Реквизиты табличной части — в ChildObjects
        child_objects = XMLUtils.get_child(ts_elem, "ChildObjects")
        if child_objects is not None:
            for child in child_objects:
                if XMLUtils.strip_ns(child.tag) == "Attribute":
                    result["attributes"].append(self._parse_attribute(child))

        return result

    def _parse_standard_attribute(self, attr_elem) -> dict[str, Any]:
        """Парсит <xr:StandardAttribute> — стандартный реквизит."""
        return {
            "name": attr_elem.get("name", ""),
            "fill_checking": XMLUtils.get_text(attr_elem, "FillChecking"),
            "fill_from_filling_value": XMLUtils.get_bool(attr_elem, "FillFromFillingValue"),
            "create_on_input": XMLUtils.get_text(attr_elem, "CreateOnInput"),
            "data_history": XMLUtils.get_text(attr_elem, "DataHistory"),
        }


# ============================================================================
# ПАРСЕР КОНФИГУРАЦИИ
# ============================================================================


