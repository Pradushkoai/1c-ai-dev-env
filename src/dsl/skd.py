"""skd — компилятор JSON DSL → XML для схем компоновки данных (СКД)."""

from __future__ import annotations
from typing import Any

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    NS_DCS,
    NS_V8,
    NS_XS,
    NS_XSI,
    CompileResult,
)


class SkdCompiler:
    """Компилятор JSON DSL → Template.xml для СКД 1С."""

    def compile(
        self,
        definition: str | dict | Path,
        output_path: str | Path,
    ) -> CompileResult:
        """Скомпилировать JSON DSL → СКД Template.xml.

        Args:
            definition: JSON-определение СКД
            output_path: путь к выходному Template.xml

        Returns:
            CompileResult
        """
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

        result = CompileResult(
            object_type="DataCompositionSchema",
            object_name=def_dict.get("name", "ОсновнаяСхемаКомпоновкиДанных"),
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Регистрируем namespaces
        for prefix, uri in [
            ("s", NS_DCS),
            ("v8", NS_V8),
            ("xs", NS_XS),
            ("xsi", NS_XSI),
        ]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_DCS}}}DataCompositionSchema")

        # Data sources (auto если не указаны)
        data_sources = def_dict.get("dataSources", [])
        if not data_sources:
            data_sources = [{"name": "ИсточникДанных1", "connection": "Local"}]

        ds_container = ET.SubElement(root, f"{{{NS_DCS}}}dataSources")
        for ds_src in data_sources:
            src_elem = ET.SubElement(ds_container, f"{{{NS_DCS}}}dataSource")
            n = ET.SubElement(src_elem, f"{{{NS_DCS}}}name")
            n.text = ds_src["name"]

        # Data sets
        data_sets = def_dict.get("dataSets", [])
        ds_container = ET.SubElement(root, f"{{{NS_DCS}}}dataSets")
        for ds_def in data_sets:
            self._write_data_set(ds_container, ds_def)

        # Calculated fields
        for cf_def in def_dict.get("calculatedFields", []):
            self._write_calculated_field(root, cf_def)

        # Total fields (resources)
        for tf_def in def_dict.get("totalFields", []):
            self._write_total_field(root, tf_def)

        # Parameters
        for param_def in def_dict.get("parameters", []):
            self._write_parameter(root, param_def)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        result.xml_path = output_path

        return result

    def _write_data_set(self, parent: ET.Element, ds_def: dict[str, Any]) -> None:
        """Записать набор данных."""
        ds_type = ds_def.get("type", "query")
        type_map = {
            "query": "DataSetQuery",
            "objectName": "DataSetObject",
            "union": "DataSetUnion",
        }
        ds_type_xml = type_map.get(ds_type, "DataSetQuery")

        ds_elem = ET.SubElement(parent, f"{{{NS_DCS}}}dataSet")
        ds_elem.set(f"{{{NS_XSI}}}type", f"s:{ds_type_xml}")

        n = ET.SubElement(ds_elem, f"{{{NS_DCS}}}name")
        n.text = ds_def.get("name", "НаборДанных1")

        # Query (для DataSetQuery)
        if ds_type == "query" and ds_def.get("query"):
            q = ET.SubElement(ds_elem, f"{{{NS_DCS}}}query")
            q.text = ds_def["query"]

        # ObjectName (для DataSetObject)
        if ds_type == "objectName" and ds_def.get("objectName"):
            on = ET.SubElement(ds_elem, f"{{{NS_DCS}}}objectName")
            on.text = ds_def["objectName"]

        # Fields
        for field_def in ds_def.get("fields", []):
            self._write_dataset_field(ds_elem, field_def)

    def _write_dataset_field(self, parent: ET.Element, field_def: dict[str, Any]) -> None:
        """Записать поле набора данных."""
        f = ET.SubElement(parent, f"{{{NS_DCS}}}field")
        dp = ET.SubElement(f, f"{{{NS_DCS}}}dataPath")
        dp.text = field_def.get("path", field_def.get("name", ""))

        if field_def.get("title"):
            title = ET.SubElement(f, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = field_def["title"]

        if field_def.get("expression"):
            expr = ET.SubElement(f, f"{{{NS_DCS}}}expression")
            expr.text = field_def["expression"]

    def _write_calculated_field(self, parent: ET.Element, cf_def: dict[str, Any]) -> None:
        """Записать вычисляемое поле."""
        cf = ET.SubElement(parent, f"{{{NS_DCS}}}calculatedField")
        dp = ET.SubElement(cf, f"{{{NS_DCS}}}dataPath")
        dp.text = cf_def.get("path", cf_def.get("name", ""))

        if cf_def.get("expression"):
            expr = ET.SubElement(cf, f"{{{NS_DCS}}}expression")
            expr.text = cf_def["expression"]

        if cf_def.get("title"):
            title = ET.SubElement(cf, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = cf_def["title"]

    def _write_total_field(self, parent: ET.Element, tf_def: dict[str, Any]) -> None:
        """Записать итоговое поле (ресурс)."""
        tf = ET.SubElement(parent, f"{{{NS_DCS}}}totalField")
        dp = ET.SubElement(tf, f"{{{NS_DCS}}}dataPath")
        dp.text = tf_def.get("path", tf_def.get("name", ""))

        if tf_def.get("expression"):
            expr = ET.SubElement(tf, f"{{{NS_DCS}}}expression")
            expr.text = tf_def["expression"]

        if tf_def.get("group"):
            grp = ET.SubElement(tf, f"{{{NS_DCS}}}group")
            grp.text = tf_def["group"]

    def _write_parameter(self, parent: ET.Element, param_def: dict[str, Any]) -> None:
        """Записать параметр СКД."""
        p = ET.SubElement(parent, f"{{{NS_DCS}}}parameter")
        n = ET.SubElement(p, f"{{{NS_DCS}}}name")
        n.text = param_def.get("name", "")

        if param_def.get("title"):
            title = ET.SubElement(p, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = param_def["title"]

        # Type
        type_str = param_def.get("type", "String")
        value_type = ET.SubElement(p, f"{{{NS_DCS}}}valueType")
        type_container = ET.SubElement(value_type, f"{{{NS_V8}}}Type")
        type_container.text = f"xs:{'string' if type_str == 'String' else 'decimal' if type_str == 'Number' else 'boolean' if type_str == 'Boolean' else 'dateTime'}"
