"""
inspect_data.py — handlers для inspect и data_status.

P2.2: вынесено из mcp_server.py (группа 5).
Handlers: inspect, data_status
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as _ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

import mcp.types as types

if TYPE_CHECKING:
    from src.project import Project


def _strip_ns(tag: str) -> str:
    """Убрать namespace из тега."""
    return tag.split("}")[-1] if "}" in tag else tag


async def handle_inspect(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Единый inspect — анализ объектов 1С с режимами."""
    target = arguments.get("target", "cf")
    mode = arguments.get("mode", "overview")
    path_str = arguments.get("path", "")
    field_name = arguments.get("name", "")

    if not path_str:
        return [types.TextContent(type="text", text=json.dumps({"error": "path required"}, ensure_ascii=False))]

    path = Path(path_str)
    if not path.exists():
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"File not found: {path}"}, ensure_ascii=False))
        ]

    try:
        if target == "cf":
            if path.is_dir():
                path = path / "Configuration.xml"
            tree = _ET.parse(path)
            root = tree.getroot()

            config = None
            for elem in root.iter():
                if _strip_ns(elem.tag) == "Configuration":
                    config = elem
                    break

            result: dict[str, Any] = {"target": "cf", "path": str(path)}
            if config is not None:
                props = None
                for elem in config:
                    if _strip_ns(elem.tag) == "Properties":
                        props = elem
                        break
                if props is not None:
                    result["properties"] = {_strip_ns(p.tag): p.text for p in props if p.text and len(p.text) < 200}

                child_objects = None
                for elem in config:
                    if _strip_ns(elem.tag) == "ChildObjects":
                        child_objects = elem
                        break
                if child_objects is not None:
                    type_counts: dict[str, int] = {}
                    for child in child_objects:
                        tag = _strip_ns(child.tag)
                        type_counts[tag] = type_counts.get(tag, 0) + 1
                    result["objects_by_type"] = type_counts
                    result["total_objects"] = sum(type_counts.values())

            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif target == "skd" and mode == "trace":
            import sys as _sys

            _sys.path.insert(0, str(project.paths.scripts_dir))
            from skd_parser import trace_field as _trace

            if path.is_dir():
                path = path / "Ext" / "Template.xml"

            if not field_name:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": "name required for trace mode"}, ensure_ascii=False),
                    )
                ]

            result = _trace(path, field_name)
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif target == "depgraph":
            config_name = arguments.get("config_name", "")
            if not config_name:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": "config_name required for depgraph"}, ensure_ascii=False),
                    )
                ]

            from src.services.dependency_graph import DependencyGraph

            dg = DependencyGraph()
            build_result = dg.build_from_metadata_index(config_name, project.paths)

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "target": "depgraph",
                            "config_name": build_result.config_name,
                            "nodes": len(build_result.nodes),
                            "edges": len(build_result.edges),
                            "stats": dg.get_stats(),
                            "warnings": build_result.warnings,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            ]

        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": f"target '{target}' with mode '{mode}' not yet implemented",
                            "available": ["cf", "skd+trace", "depgraph"],
                        },
                        ensure_ascii=False,
                    ),
                )
            ]

    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_data_status(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Статус данных проекта."""
    from src.services.data_package import DataPackage

    dp = DataPackage(project.paths)
    status = dp.status()
    response = {
        "has_platform_index": status["has_platform_index"],
        "has_platform_methods": status["has_platform_methods"],
        "configs": status["configs"],
        "autosave_available": status["autosave_available"],
    }
    if status.get("autosave_info"):
        ai = status["autosave_info"]
        response["autosave_info"] = {
            "size_mb": ai.get("size_mb", 0),
            "total_files": ai.get("total_files", 0),
            "created_at": ai.get("manifest", {}).get("created_at", "")[:19] if ai.get("manifest") else "",
        }
        response["autoload_command"] = "1c-ai data autoload"
    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


# Реестр handlers группы 5
INSPECT_DATA_HANDLERS: dict[str, Any] = {
    "inspect": handle_inspect,
    "data_status": handle_data_status,
}
