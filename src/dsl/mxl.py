"""mxl — компилятор JSON DSL → XML для MXL-макетов (печатные формы)."""

from __future__ import annotations
from typing import Any

import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    NS_SSD,
    NS_SSDX,
    NS_V8,
    CompileResult,
)


class MxlCompiler:
    """Компилятор JSON DSL → Template.xml для табличных документов 1С (MXL).

    Поддерживает: columns, columnWidths, fonts, styles, areas (rows/cells),
    params, text, span, detail.
    """

    def compile(
        self,
        definition: str | dict | Path,
        output_path: str | Path,
    ) -> CompileResult:
        """Скомпилировать JSON DSL → MXL Template.xml.

        Args:
            definition: JSON-определение MXL-макета
            output_path: путь к выходному Template.xml
        """
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                import json as _json

                with open(def_path, encoding="utf-8") as f:
                    def_dict = _json.load(f)
            else:
                import json as _json

                def_dict = _json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        result = CompileResult(
            object_type="SpreadsheetDocument",
            object_name=def_dict.get("name", "Макет"),
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Регистрируем namespaces
        for prefix, uri in [
            ("ssd", NS_SSD),
            ("ssdx", NS_SSDX),
            ("v8", NS_V8),
        ]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_SSD}}}spreadsheetDocument")

        # Columns
        columns = def_dict.get("columns", 10)
        # Page width (auto-calc defaultWidth)
        total_width: int | None = None
        if "page" in def_dict:
            page_map = {"A4-landscape": 780, "A4-portrait": 540}
            page = def_dict["page"]
            if isinstance(page, str):
                total_width = page_map.get(page)
            elif isinstance(page, int):
                total_width = page

        # Default column width
        default_width = def_dict.get("defaultWidth", 10)

        # Column widths (dict with keys like "1", "2-8", "5,7,9")
        column_widths = def_dict.get("columnWidths", {})

        # Parse column widths into per-column widths
        widths_list = self._parse_column_widths(column_widths, columns, default_width, total_width)

        # Write columns
        cols_elem = ET.SubElement(root, f"{{{NS_SSD}}}columns")
        for i, w in enumerate(widths_list, 1):
            col = ET.SubElement(cols_elem, f"{{{NS_SSD}}}column")
            col.set("index", str(i))
            w_elem = ET.SubElement(col, f"{{{NS_SSD}}}width")
            w_elem.text = str(w)

        # Fonts
        fonts = def_dict.get("fonts", {})
        if not fonts:
            fonts = {"default": {"face": "Arial", "size": 10}}
        fonts_elem = ET.SubElement(root, f"{{{NS_SSD}}}fonts")
        for fname, fdef in fonts.items():
            font_elem = ET.SubElement(fonts_elem, f"{{{NS_SSD}}}font")
            font_elem.set("name", fname)
            face = ET.SubElement(font_elem, f"{{{NS_SSD}}}face")
            face.text = fdef.get("face", "Arial")
            size = ET.SubElement(font_elem, f"{{{NS_SSD}}}size")
            size.text = str(fdef.get("size", 10))
            if fdef.get("bold"):
                bold = ET.SubElement(font_elem, f"{{{NS_SSD}}}bold")
                bold.text = "true"
            if fdef.get("italic"):
                italic = ET.SubElement(font_elem, f"{{{NS_SSD}}}italic")
                italic.text = "true"

        # Styles
        styles = def_dict.get("styles", {})
        if not styles:
            styles = {"default": {}}
        styles_elem = ET.SubElement(root, f"{{{NS_SSD}}}styles")
        for sname, sdef in styles.items():
            style_elem = ET.SubElement(styles_elem, f"{{{NS_SSD}}}style")
            style_elem.set("name", sname)
            if sdef.get("font"):
                style_elem.set("font", sdef["font"])
            if sdef.get("align"):
                align = ET.SubElement(style_elem, f"{{{NS_SSD}}}horizontalAlign")
                align.text = sdef["align"]
            if sdef.get("border"):
                self._add_borders(style_elem, sdef["border"])

        # Areas
        areas = def_dict.get("areas", [])
        areas_elem = ET.SubElement(root, f"{{{NS_SSD}}}areas")
        for area_def in areas:
            self._write_area(areas_elem, area_def)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        result.xml_path = output_path

        return result

    def _parse_column_widths(
        self, column_widths: dict[str, Any], columns: int, default_width: int, total_width: int | None = None
    ) -> list[int]:
        """Парсит columnWidths dict в список ширин по колонкам."""
        widths = [default_width] * columns
        for key, val in column_widths.items():
            # Ключи: "1", "2-8", "5,7,9"
            indices = self._parse_column_keys(key, columns)
            # Значение: число или "Nx"
            w = int(float(val[:-1]) * default_width) if isinstance(val, str) and val.endswith("x") else int(val)
            for idx in indices:
                if 1 <= idx <= columns:
                    widths[idx - 1] = w
        # Если total_width задан — масштабируем
        if total_width and sum(widths) != total_width:
            scale = total_width / sum(widths) if sum(widths) > 0 else 1
            widths = [max(1, int(w * scale)) for w in widths]
        return widths

    @staticmethod
    def _parse_column_keys(key: str, columns: int) -> list[int]:
        """Парсит '1', '2-8', '5,7,9' в список индексов."""
        result: list[int] = []
        for part in key.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                result.extend(range(int(start), int(end) + 1))
            elif part.isdigit():
                result.append(int(part))
        return result

    def _add_borders(self, style_elem: ET.Element, border: str) -> None:
        """Добавить границы в стиль."""
        border_map = {
            "all": ["left", "top", "right", "bottom"],
            "top": ["top"],
            "bottom": ["bottom"],
            "left": ["left"],
            "right": ["right"],
        }
        sides = border_map.get(border, [border])
        borders_elem = ET.SubElement(style_elem, f"{{{NS_SSD}}}border")
        for side in sides:
            b = ET.SubElement(borders_elem, f"{{{NS_SSD}}}{side}")
            b.set("style", "Single")

    def _write_area(self, parent: ET.Element, area_def: dict[str, Any]) -> None:
        """Записать область MXL-макета."""
        area_elem = ET.SubElement(parent, f"{{{NS_SSD}}}area")
        area_elem.set("name", area_def.get("name", ""))

        rows = area_def.get("rows", [])
        rows_elem = ET.SubElement(area_elem, f"{{{NS_SSD}}}rows")
        for row_def in rows:
            self._write_row(rows_elem, row_def)

    def _write_row(self, parent: ET.Element, row_def: dict[str, Any]) -> None:
        """Записать строку области."""
        row_elem = ET.SubElement(parent, f"{{{NS_SSD}}}row")
        if "height" in row_def:
            h = ET.SubElement(row_elem, f"{{{NS_SSD}}}height")
            h.text = str(row_def["height"])
        if "rowStyle" in row_def:
            row_elem.set("style", row_def["rowStyle"])

        cells = row_def.get("cells", [])
        cells_elem = ET.SubElement(row_elem, f"{{{NS_SSD}}}cells")
        for cell_def in cells:
            self._write_cell(cells_elem, cell_def)

    def _write_cell(self, parent: ET.Element, cell_def: dict[str, Any]) -> None:
        """Записать ячейку."""
        cell_elem = ET.SubElement(parent, f"{{{NS_SSD}}}cell")
        cell_elem.set("col", str(cell_def.get("col", 1)))
        if "span" in cell_def:
            cell_elem.set("span", str(cell_def["span"]))
        if "style" in cell_def:
            cell_elem.set("style", cell_def["style"])

        # Text content
        if "text" in cell_def:
            text_elem = ET.SubElement(cell_elem, f"{{{NS_SSD}}}text")
            text_elem.text = cell_def["text"]
        elif "param" in cell_def:
            param_elem = ET.SubElement(cell_elem, f"{{{NS_SSD}}}parameter")
            param_elem.set("name", cell_def["param"])
            # Detail (для расшифровки)
            if "detail" in cell_def:
                detail = ET.SubElement(cell_elem, f"{{{NS_SSD}}}detail")
                detail.text = cell_def["detail"]
