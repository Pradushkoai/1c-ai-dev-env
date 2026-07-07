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

        # P1.5: добавляем платформенные стандартные реквизиты (Ссылка, Период, Регистратор, ...)
        # Они не описаны в XML, но всегда доступны в запросах 1С.
        try:
            from .standard_attributes import get_standard_attributes

            platform_std_attrs = get_standard_attributes(obj_type, props)
            if platform_std_attrs:
                # Объединяем с распарсенными <StandardAttributes> из XML
                existing_names = {a.get("name") for a in std_attrs}
                for attr in platform_std_attrs:
                    if attr.get("name") not in existing_names:
                        std_attrs.append(attr)
                # Также добавляем в child_objects.attributes для удобства валидатора
                existing_child_names = {a.get("name") for a in children.get("attributes", [])}
                for attr in platform_std_attrs:
                    if attr.get("name") not in existing_child_names:
                        children.setdefault("attributes", []).append(attr)
        except Exception:
            # Если стандартные реквизиты недоступны — не критично
            pass

        # P1.5: разделяем attributes по kind (Dimension / Resource / Attribute / Standard)
        # для удобства статического валидатора запросов.
        dimensions = []
        resources = []
        plain_attributes = []
        standard_attrs_separated = []
        for attr in children.get("attributes", []):
            kind = attr.get("kind", "Attribute")
            if kind == "Dimension":
                dimensions.append(attr)
            elif kind == "Resource":
                resources.append(attr)
            elif kind == "Standard":
                standard_attrs_separated.append(attr)
            else:
                plain_attributes.append(attr)
        children["dimensions"] = dimensions
        children["resources"] = resources
        children["attributes_only"] = plain_attributes
        children["standard_attributes"] = standard_attrs_separated

        # P1.5: ресолвинг типов полей в структурированное представление
        # (CatalogRef.X → {kind: 'ref', ref_kind: 'Catalog', ref_name: 'X'})
        try:
            from .type_resolver import resolve_field_types_from_metadata

            for attr_list_key in ("attributes", "dimensions", "resources", "attributes_only", "standard_attributes"):
                for attr in children.get(attr_list_key, []):
                    if "types" in attr and not attr.get("resolved_type"):
                        attr["resolved_type"] = resolve_field_types_from_metadata(attr["types"]).to_dict()
            # Также для реквизитов табличных частей
            for ts in children.get("tabular_sections", []):
                for attr in ts.get("attributes", []):
                    if "types" in attr and not attr.get("resolved_type"):
                        attr["resolved_type"] = resolve_field_types_from_metadata(attr["types"]).to_dict()
        except Exception:
            pass

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
            elif tag == "PredefinedItem":
                # P1.5: предопределённые элементы справочников/планов видов характеристик
                # Формат XML: <PredefinedItem uuid="..."><Name>...</Name><Code>...</Code>...
                #              <IsFolder>false</IsFolder><Item>...</Item></PredefinedItem>
                # Поддерживается также <Predefined> (без Item-суффикса) — зависит от версии платформы.
                result["predefined"].append(self._parse_predefined_item(child))
            elif tag == "Predefined":
                # Альтернативный формат — вложенный <Predefined> для предопределённых
                predefined_data = self._parse_predefined_data(child)
                if predefined_data:
                    result["predefined"].extend(predefined_data)
            elif tag in ("PredefinedData", "PredefinedValue"):
                # Ещё один вариант имени тега
                predefined_props = XMLUtils.get_child(child, "Properties")
                result["predefined"].append(
                    {
                        "name": XMLUtils.get_text(predefined_props, "Name") if predefined_props is not None else (child.text or ""),
                        "uuid": child.get("uuid", ""),
                        "is_folder": XMLUtils.get_bool(predefined_props, "IsFolder") if predefined_props is not None else False,
                        "code": XMLUtils.get_text(predefined_props, "Code") if predefined_props is not None else "",
                    }
                )
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

    def _parse_predefined_item(self, item_elem) -> dict[str, Any]:
        """P1.5: Парсит <PredefinedItem> — предопределённый элемент.

        Формат:
            <PredefinedItem uuid="...">
                <Name>Услуга</Name>
                <Code>000000001</Code>
                <IsFolder>false</IsFolder>
                <Item .../>   <!-- родитель, если есть -->
            </PredefinedItem>
        """
        props = {
            "name": XMLUtils.get_text(item_elem, "Name"),
            "uuid": item_elem.get("uuid", ""),
            "is_folder": XMLUtils.get_bool(item_elem, "IsFolder"),
            "code": XMLUtils.get_text(item_elem, "Code"),
        }
        # Родитель (для иерархических предопределённых)
        parent_name = ""
        for child in item_elem:
            if XMLUtils.strip_ns(child.tag) == "Item":
                # Item может содержать ссылку на родительский предопределённый
                parent_name = XMLUtils.get_text(child, "Name") or child.text or ""
                break
        if parent_name:
            props["parent"] = parent_name
        return props

    def _parse_predefined_data(self, predefined_elem) -> list[dict[str, Any]]:
        """P1.5: Парсит содержимое <Predefined> — список предопределённых элементов."""
        items: list[dict[str, Any]] = []
        for child in predefined_elem:
            tag = XMLUtils.strip_ns(child.tag)
            if tag in ("PredefinedItem", "PredefinedData", "PredefinedValue", "Item"):
                if tag == "PredefinedItem":
                    items.append(self._parse_predefined_item(child))
                else:
                    props = XMLUtils.get_child(child, "Properties")
                    items.append(
                        {
                            "name": XMLUtils.get_text(props, "Name") if props is not None else (child.text or ""),
                            "uuid": child.get("uuid", ""),
                            "is_folder": XMLUtils.get_bool(props, "IsFolder") if props is not None else False,
                            "code": XMLUtils.get_text(props, "Code") if props is not None else "",
                        }
                    )
        return items

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
            "kind": "Attribute",  # P3: явный kind по умолчанию
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


