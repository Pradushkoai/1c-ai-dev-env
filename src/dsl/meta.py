"""meta — компилятор JSON DSL → XML для метаданных 1С (23 типа)."""

from __future__ import annotations
from typing import Any

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    NS_MD,
    NS_V8,
    NS_XR,
    NS_XS,
    NS_XSI,
    TYPE_MAP,
    CompileResult,
    _camel_to_words,
    _gen_uuid,
    _make_type_element,
    _normalize_object_type,
    _normalize_type,
    _parse_attribute,
)


class MetaCompiler:
    """Компилятор JSON DSL → XML для объектов метаданных 1С (23 типа)."""

    def compile(
        self,
        definition: str | dict | Path,
        output_dir: str | Path,
    ) -> CompileResult:
        """Скомпилировать JSON DSL → XML.

        Args:
            definition: JSON-определение объекта (dict, JSON-строка или путь к файлу)
            output_dir: каталог выгрузки конфигурации (где Catalogs/, Documents/, и т.д.)

        Returns:
            CompileResult с путями к созданным файлам
        """
        # Парсим definition
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                with open(def_path, encoding="utf-8") as f:
                    def_dict = json.load(f)
            else:
                # JSON-строка
                def_dict = json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        # Нормализуем тип объекта
        object_type = _normalize_object_type(def_dict.get("type", ""))
        if not object_type or object_type not in TYPE_MAP:
            raise ValueError(
                f"Неподдерживаемый тип объекта: {def_dict.get('type')}. Поддерживается {len(TYPE_MAP)} типов."
            )

        object_name = def_dict.get("name", "")
        if not object_name:
            raise ValueError("Имя объекта не указано (поле 'name')")

        # Синоним (авто из CamelCase если не указан)
        synonym = def_dict.get("synonym") or _camel_to_words(object_name)

        result = CompileResult(
            object_type=object_type,
            object_name=object_name,
        )

        type_info = TYPE_MAP[object_type]
        output_dir = Path(output_dir)

        # Создаём каталог объекта
        obj_dir = output_dir / type_info["dir"] / object_name
        obj_dir.mkdir(parents=True, exist_ok=True)

        # Создаём XML объекта
        xml_path = output_dir / type_info["dir"] / f"{object_name}.xml"
        self._write_object_xml(xml_path, object_type, object_name, synonym, def_dict)
        result.xml_path = xml_path

        # Создаём модули BSL (если нужно)
        module_paths = self._create_modules(obj_dir, object_type, def_dict)
        result.module_paths = module_paths

        # Регистрируем в Configuration.xml (если есть)
        config_xml = output_dir / "Configuration.xml"
        if config_xml.exists():
            result.registered_in_config = self._register_in_config(config_xml, object_type, object_name)

        return result

    def _write_object_xml(
        self,
        xml_path: Path,
        object_type: str,
        object_name: str,
        synonym: str,
        def_dict: dict[str, Any],
    ) -> None:
        """Записать XML объекта метаданных."""
        # Регистрируем namespaces
        for prefix, uri in [("md", NS_MD), ("xr", NS_XR), ("v8", NS_V8), ("xs", NS_XS), ("xsi", NS_XSI)]:
            ET.register_namespace(prefix, uri)

        type_info = TYPE_MAP[object_type]
        root = ET.Element(f"{{{NS_MD}}}{type_info['xml_tag']}")
        root.set("uuid", _gen_uuid())
        root.set("name", object_name)

        # InternalInfo (для объектов с reference)
        if object_type in (
            "Catalog",
            "Document",
            "Enum",
            "InformationRegister",
            "AccumulationRegister",
            "ChartOfAccounts",
        ):
            internal_info = ET.SubElement(root, f"{{{NS_MD}}}InternalInfo")
            if object_type in ("Catalog", "Document", "Enum"):
                # GeneratedType
                gen_type = ET.SubElement(internal_info, f"{{{NS_XR}}}GeneratedType")
                gen_type.set(
                    "name", f"Catalog.{object_name}" if object_type == "Catalog" else f"Document.{object_name}"
                )
                gen_type.set("category", "Ref")
                type_id = ET.SubElement(gen_type, f"{{{NS_XR}}}TypeId")
                type_id.text = _gen_uuid()
                value_id = ET.SubElement(gen_type, f"{{{NS_XR}}}ValueId")
                value_id.text = _gen_uuid()

        # Properties
        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name_elem.text = object_name

        syn_elem = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
        content = ET.SubElement(item, f"{{{NS_V8}}}content")
        content.text = synonym

        # Comment
        comment = def_dict.get("comment", "")
        if comment:
            c_elem = ET.SubElement(props, f"{{{NS_XR}}}Comment")
            c_elem.text = comment

        # StandardAttributes
        self._add_standard_attributes(props, object_type)

        # Type-specific properties
        self._add_type_specific_props(props, object_type, def_dict)

        # ChildObjects
        child_objects = ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")
        self._add_child_objects(child_objects, object_type, def_dict)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    def _add_standard_attributes(self, props_elem: ET.Element, object_type: str) -> None:
        """Добавить стандартные реквизиты (Ref, Code, Description, и т.д.)."""
        std_attrs_map = {
            "Catalog": [
                "PredefinedDataName",
                "Predefined",
                "Ref",
                "DeletionMark",
                "IsFolder",
                "Owner",
                "Parent",
                "Description",
                "Code",
            ],
            "Document": ["Posted", "Ref", "DeletionMark", "Date", "Number"],
            "Enum": ["Order", "Ref"],
            "InformationRegister": ["Active", "LineNumber", "Recorder", "Period"],
            "AccumulationRegister": ["Active", "LineNumber", "Recorder", "Period"],
        }

        attrs = std_attrs_map.get(object_type, [])
        for attr_name in attrs:
            std_attr = ET.SubElement(props_elem, f"{{{NS_XR}}}StandardAttribute")
            std_attr.set("name", attr_name)
            ET.SubElement(std_attr, f"{{{NS_XR}}}LinkByType")
            fill_check = ET.SubElement(std_attr, f"{{{NS_XR}}}FillChecking")
            fill_check.text = "DontCheck"

    def _add_type_specific_props(self, props_elem: ET.Element, object_type: str, def_dict: dict[str, Any]) -> None:
        """Добавить свойства специфичные для типа объекта."""
        if object_type == "Catalog":
            # Hierarchical, CodeLength, DescriptionLength
            hier = ET.SubElement(props_elem, f"{{{NS_XR}}}Hierarchical")
            hier.text = "false" if not def_dict.get("hierarchical") else "true"

            code_length = ET.SubElement(props_elem, f"{{{NS_XR}}}CodeLength")
            code_length.text = str(def_dict.get("codeLength", 9))

            desc_length = ET.SubElement(props_elem, f"{{{NS_XR}}}DescriptionLength")
            desc_length.text = str(def_dict.get("descriptionLength", 25))

            autonumbering = ET.SubElement(props_elem, f"{{{NS_XR}}}Autonumbering")
            autonumbering.text = "true" if def_dict.get("autonumbering", True) else "false"

        elif object_type == "Document":
            number_length = ET.SubElement(props_elem, f"{{{NS_XR}}}NumberLength")
            number_length.text = str(def_dict.get("numberLength", 11))

            check_unique = ET.SubElement(props_elem, f"{{{NS_XR}}}CheckUnique")
            check_unique.text = "true" if def_dict.get("checkUnique", True) else "false"

            posting = ET.SubElement(props_elem, f"{{{NS_XR}}}Posting")
            posting.text = def_dict.get("posting", "Allow")

            autonumbering = ET.SubElement(props_elem, f"{{{NS_XR}}}Autonumbering")
            autonumbering.text = "true" if def_dict.get("autonumbering", True) else "false"

        elif object_type == "InformationRegister":
            # Periodicity, WriteModal, etc.
            periodicity = ET.SubElement(props_elem, f"{{{NS_XR}}}Periodicity")
            periodicity.text = def_dict.get("periodicity", "Nonperiodical")

        elif object_type == "Constant":
            # Type
            type_container = ET.SubElement(props_elem, f"{{{NS_XR}}}Type")
            value_type = _normalize_type(def_dict.get("valueType", "String"))
            _make_type_element(type_container, value_type)

    def _add_child_objects(self, child_objects_elem: ET.Element, object_type: str, def_dict: dict[str, Any]) -> None:
        """Добавить дочерние объекты (реквизиты, ТЧ, формы, значения enum)."""
        # Реквизиты (attributes)
        attributes = def_dict.get("attributes", [])
        for attr_def in attributes:
            attr = _parse_attribute(attr_def)
            self._write_attribute(child_objects_elem, attr, "Attribute")

        # Табличные части
        tabular_sections = def_dict.get("tabularSections", {})
        if isinstance(tabular_sections, dict):
            for ts_name, ts_attrs in tabular_sections.items():
                ts_elem = ET.SubElement(child_objects_elem, f"{{{NS_MD}}}TabularSection")
                ts_props = ET.SubElement(ts_elem, f"{{{NS_MD}}}Properties")
                name_elem = ET.SubElement(ts_props, f"{{{NS_XR}}}Name")
                name_elem.text = ts_name
                if object_type == "Catalog":
                    use = ET.SubElement(ts_props, f"{{{NS_XR}}}Use")
                    use.text = "ForItem"
                # Реквизиты ТЧ
                for attr_def in ts_attrs:
                    attr = _parse_attribute(attr_def)
                    self._write_attribute(ts_elem, attr, "Attribute")

        # Значения перечисления (для Enum)
        if object_type == "Enum":
            values = def_dict.get("values", [])
            for val_def in values:
                if isinstance(val_def, str):
                    val_name = val_def
                    val_synonym = _camel_to_words(val_name)
                else:
                    val_name = val_def.get("name", "")
                    val_synonym = val_def.get("synonym") or _camel_to_words(val_name)

                enum_val = ET.SubElement(child_objects_elem, f"{{{NS_MD}}}EnumValue")
                val_props = ET.SubElement(enum_val, f"{{{NS_MD}}}Properties")
                name_elem = ET.SubElement(val_props, f"{{{NS_XR}}}Name")
                name_elem.text = val_name
                syn_elem = ET.SubElement(val_props, f"{{{NS_XR}}}Synonym")
                item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
                content = ET.SubElement(item, f"{{{NS_V8}}}content")
                content.text = val_synonym

    def _write_attribute(self, parent: ET.Element, attr: dict[str, Any], tag_name: str = "Attribute") -> None:
        """Записать реквизит как <Attribute>."""
        attr_elem = ET.SubElement(parent, f"{{{NS_MD}}}{tag_name}")
        attr_props = ET.SubElement(attr_elem, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(attr_props, f"{{{NS_XR}}}Name")
        name_elem.text = attr["name"]

        if attr.get("synonym"):
            syn_elem = ET.SubElement(attr_props, f"{{{NS_XR}}}Synonym")
            item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = attr["synonym"]

        # Type
        type_container = ET.SubElement(attr_props, f"{{{NS_XR}}}Type")
        _make_type_element(type_container, attr["type"])

        # FillChecking
        if attr.get("fillChecking"):
            fc = ET.SubElement(attr_props, f"{{{NS_XR}}}FillChecking")
            fc.text = attr["fillChecking"]

        # Indexing
        if attr.get("indexing"):
            idx = ET.SubElement(attr_props, f"{{{NS_XR}}}Indexing")
            idx.text = attr["indexing"]

    def _create_modules(self, obj_dir: Path, object_type: str, def_dict: dict[str, Any]) -> list[Path]:
        """Создать BSL-модули объекта (ObjectModule, ManagerModule)."""
        modules: list[Path] = []

        # ObjectModule для Catalog, Document, InformationRegister, и т.д.
        types_with_object_module = {
            "Catalog",
            "Document",
            "InformationRegister",
            "AccumulationRegister",
            "ChartOfAccounts",
            "BusinessProcess",
            "Task",
            "Report",
            "DataProcessor",
        }
        if object_type in types_with_object_module:
            module_dir = obj_dir / "Ext"
            module_dir.mkdir(parents=True, exist_ok=True)
            module_path = module_dir / "ObjectModule.bsl"
            module_path.write_text(self._default_object_module(object_type, def_dict), encoding="utf-8")
            modules.append(module_path)

        return modules

    def _default_object_module(self, object_type: str, def_dict: dict[str, Any]) -> str:
        """Шаблон ObjectModule.bsl с регионами."""
        return (
            f"// Объект: {object_type} {def_dict.get('name', '')}\n"
            f"// Сгенерировано DSL Compiler\n"
            f"\n"
            f"#Область ПрограммныйИнтерфейс\n"
            f"\n"
            f"// TODO: Описание API объекта\n"
            f"\n"
            f"#КонецОбласти\n"
            f"\n"
            f"#Область СлужебныйПрограммныйИнтерфейс\n"
            f"\n"
            f"// TODO: Служебные методы\n"
            f"\n"
            f"#КонецОбласти\n"
            f"\n"
            f"#Область СлужебныеПроцедурыИФункции\n"
            f"\n"
            f"// TODO: Внутренние методы\n"
            f"\n"
            f"#КонецОбласти\n"
        )

    def _register_in_config(self, config_xml: Path, object_type: str, object_name: str) -> bool:
        """Зарегистрировать объект в ChildObjects Configuration.xml."""
        try:
            tree = ET.parse(config_xml)
            root = tree.getroot()
            type_info = TYPE_MAP.get(object_type)
            if not type_info:
                return False

            # Ищем <ChildObjects>
            child_objects = None
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "ChildObjects":
                    child_objects = elem
                    break

            if child_objects is None:
                child_objects = ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")

            # Проверяем — не зарегистрирован ли уже
            xml_tag = type_info["xml_tag"]
            for child in child_objects:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == xml_tag and child.text == object_name:
                    return True  # уже зарегистрирован

            # Добавляем
            new_elem = ET.SubElement(child_objects, f"{{{NS_MD}}}{xml_tag}")
            new_elem.text = object_name

            tree.write(config_xml, encoding="utf-8", xml_declaration=True)
            return True
        except (ET.ParseError, OSError):
            return False


# ============================================================================
# FORM COMPILE — компиляция управляемых форм
# ============================================================================
