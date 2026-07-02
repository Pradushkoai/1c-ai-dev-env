"""form — компилятор JSON DSL → XML для управляемых форм (Form.xml)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    NS_MD,
    NS_V8,
    NS_XR,
    CompileResult,
)


class FormCompiler:
    """Компилятор JSON DSL → Form.xml для управляемых форм 1С."""

    def compile(
        self,
        definition: str | dict | Path,
        output_path: str | Path,
    ) -> CompileResult:
        """Скомпилировать JSON DSL → Form.xml.

        Args:
            definition: JSON-определение формы (dict, JSON-строка или путь к файлу)
            output_path: путь к выходному Form.xml

        Returns:
            CompileResult
        """
        # Парсим definition
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                with open(def_path, encoding="utf-8") as f:
                    def_dict = json.load(f)
            else:
                def_dict = json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        form_name = def_dict.get("name", "Форма")
        result = CompileResult(
            object_type="Form",
            object_name=form_name,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Регистрируем namespaces
        for prefix, uri in [("md", NS_MD), ("xr", NS_XR), ("v8", NS_V8), ("v8ui", "http://v8.1c.ru/8.1/data/ui")]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_MD}}}Form")
        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name_elem.text = form_name

        syn_elem = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
        content = ET.SubElement(item, f"{{{NS_V8}}}content")
        content.text = def_dict.get("synonym", form_name)

        # AutoTitle
        auto_title = ET.SubElement(props, f"{{{NS_XR}}}AutoTitle")
        auto_title.text = "false" if def_dict.get("customTitle") else "true"

        # Items — элементы формы
        items_container = ET.SubElement(root, f"{{{NS_MD}}}Items")
        for item_def in def_dict.get("items", []):
            self._write_form_item(items_container, item_def)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        result.xml_path = output_path

        return result

    def _write_form_item(self, parent: ET.Element, item_def: dict) -> None:
        """Записать элемент формы."""
        item_type = item_def.get("type", "Label")
        item_elem = ET.SubElement(parent, f"{{{NS_MD}}}{item_type}")

        name = item_def.get("name", "")
        if name:
            item_elem.set("name", name)

        props = ET.SubElement(item_elem, f"{{{NS_MD}}}Properties")

        if name:
            name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
            name_elem.text = name

        # Title
        title = item_def.get("title")
        if title:
            title_elem = ET.SubElement(props, f"{{{NS_XR}}}Title")
            item_v8 = ET.SubElement(title_elem, f"{{{NS_V8}}}item")
            content = ET.SubElement(item_v8, f"{{{NS_V8}}}content")
            content.text = title

        # DataPath (для InputField и других связанных с данными)
        data_path = item_def.get("dataPath")
        if data_path:
            dp_elem = ET.SubElement(props, f"{{{NS_XR}}}DataPath")
            dp_elem.text = data_path

        # Visible
        if "visible" in item_def:
            vis = ET.SubElement(props, f"{{{NS_XR}}}Visible")
            vis.text = "true" if item_def["visible"] else "false"

        # ChildItems
        for child_def in item_def.get("children", []):
            self._write_form_item(item_elem, child_def)


# ============================================================================
# SKD COMPILE — компиляция схем компоновки данных
# ============================================================================
