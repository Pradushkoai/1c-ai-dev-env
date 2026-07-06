"""
structure.py — handlers для получения структуры объектов 1С.

P2.2: вынесено из mcp_server.py (группа 6).
Handlers: get_object_structure, get_skd_schema, get_form_structure
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

import mcp.types as types

if TYPE_CHECKING:
    from src.project import Project


async def handle_get_object_structure(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Структура объекта метаданных из unified-metadata-index.json."""
    config_name = arguments.get("config_name", "")
    object_name = arguments.get("object_name", "")
    object_type = arguments.get("object_type", "")

    if not config_name:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

    unified_path = project.paths.root / "derived" / "configs" / config_name / "unified-metadata-index.json"
    old_path = project.paths.root / "derived" / "configs" / config_name / "metadata-index.json"

    if unified_path.exists():
        with open(unified_path, encoding="utf-8") as f:
            metadata = json.load(f)
        all_objects = []
        for _type_name, objs in metadata.get("objects", {}).items():
            all_objects.extend(objs)
        for section in ("roles", "subsystems", "event_subscriptions", "scheduled_jobs"):
            for obj in metadata.get(section, []):
                all_objects.append(obj)
        stats = metadata.get("stats", {})
        config_info = metadata.get("configuration", {})
    elif old_path.exists():
        with open(old_path, encoding="utf-8") as f:
            metadata = json.load(f)
        all_objects = metadata.get("objects", [])
        stats = metadata.get("stats", {})
        config_info = {}
    else:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"unified-metadata-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/metadata_extractor.py data/configs/"
                        + config_name
                        + " derived/configs/"
                        + config_name
                        + "/unified-metadata-index.json",
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    if not object_name:
        if object_type:
            all_objects = [o for o in all_objects if o.get("type") == object_type]
        summary = []
        for obj in all_objects:
            children = obj.get("child_objects", {})
            summary.append(
                {
                    "name": obj.get("name", ""),
                    "type": obj.get("type", ""),
                    "synonym": obj.get("synonym", ""),
                    "attributes_count": len(children.get("attributes", [])),
                    "tabular_sections_count": len(children.get("tabular_sections", [])),
                    "forms_count": len(children.get("forms", [])),
                }
            )
        response = {
            "config": config_name,
            "total_objects": len(summary),
            "stats": stats,
            "configuration": config_info.get("properties", {}) if config_info else {},
            "objects": summary,
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]

    found = None
    for obj in all_objects:
        if obj.get("name", "").lower() == object_name.lower():
            if object_type and obj.get("type") != object_type:
                continue
            found = obj
            break

    if not found:
        suggestions = [o["name"] for o in all_objects if object_name.lower() in o.get("name", "").lower()][:10]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"Object '{object_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    # Tool chaining: подсказываем следующий шаг на основе типа объекта
    obj_type = found.get("type", "")
    obj_name = found.get("name", "")
    next_steps: list[str] = []

    if obj_type in ("AccumulationRegister", "InformationRegister"):
        next_steps.append(f"bsl_templates — используйте шаблон query_with_filter для запроса к {obj_name}")
        next_steps.append(f"search_1c_methods(query='{obj_name}') — найти методы работающие с регистром")
        next_steps.append("audit_security(file_path='<код>') — проверить запрос на SQL-инъекции (SEC001)")
    elif obj_type in ("Catalog", "Document"):
        next_steps.append(f"search_1c_methods(query='{obj_name}') — найти методы работающие с объектом")
        next_steps.append(f"call_graph(config_name='{config_name}', action='callers', module='{obj_name}') — кто обращается к объекту")
    elif obj_type == "CommonModule":
        next_steps.append(f"call_graph(config_name='{config_name}', action='callees', module='{obj_name}', method='<метод>') — что вызывает модуль")
        next_steps.append("audit_security(file_path='<путь_к_Module.bsl>') — аудит безопасности кода модуля")
        next_steps.append("check_standards(file_path='<путь_к_Module.bsl>') — проверка стандартов 1С")
    else:
        next_steps.append("search_1c_methods(query='...') — поиск связанных методов")
        next_steps.append("call_graph(config_name='<name>', action='stats') — граф вызовов")

    response = {
        "object": found,
        "_next_steps": next_steps,
    }
    return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_get_skd_schema(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Схема СКД из skd-index.json."""
    config_name = arguments.get("config_name", "")
    report_name = arguments.get("report_name", "")

    if not config_name:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

    skd_index_path = project.paths.root / "derived" / "configs" / config_name / "skd-index.json"
    if not skd_index_path.exists():
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"skd-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/skd_parser.py data/configs/"
                        + config_name
                        + " derived/configs/"
                        + config_name
                        + "/skd-index.json",
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    with open(skd_index_path, encoding="utf-8") as f:
        skd_data = json.load(f)

    schemas = skd_data.get("schemas", [])

    if not report_name:
        summary = []
        for s in schemas:
            summary.append(
                {
                    "name": s.get("name", ""),
                    "parent_type": s.get("parent_type", ""),
                    "parent_name": s.get("parent_name", ""),
                    "data_sets_count": len(s.get("schema", {}).get("data_sets", [])),
                    "parameters_count": len(s.get("schema", {}).get("parameters", [])),
                    "fields_count": sum(len(ds.get("fields", [])) for ds in s.get("schema", {}).get("data_sets", [])),
                }
            )
        response = {"config": config_name, "stats": skd_data.get("stats", {}), "schemas": summary}
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]

    found = None
    for s in schemas:
        if s.get("parent_name", "").lower() == report_name.lower():
            found = s
            break
        if s.get("name", "").lower() == report_name.lower():
            found = s
            break

    if not found:
        suggestions = list(
            {s.get("parent_name", "") for s in schemas if report_name.lower() in s.get("parent_name", "").lower()}
        )[:10]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"SKD schema for '{report_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    return [types.TextContent(type="text", text=json.dumps(found, ensure_ascii=False, indent=2))]


async def handle_get_form_structure(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Структура формы из form-index.json."""
    config_name = arguments.get("config_name", "")
    form_name = arguments.get("form_name", "")
    parent_name = arguments.get("parent_name", "")

    if not config_name:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

    form_index_path = project.paths.root / "derived" / "configs" / config_name / "form-index.json"
    if not form_index_path.exists():
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"form-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/form_analyzer.py data/configs/"
                        + config_name
                        + " derived/configs/"
                        + config_name
                        + "/form-index.json",
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    with open(form_index_path, encoding="utf-8") as f:
        form_data = json.load(f)

    forms = form_data.get("forms", [])

    if not form_name:
        summary = []
        for fr in forms:
            if parent_name and fr.get("parent_name", "").lower() != parent_name.lower():
                continue
            summary.append(
                {
                    "name": fr.get("name", ""),
                    "parent_type": fr.get("parent_type", ""),
                    "parent_name": fr.get("parent_name", ""),
                    "element_count": fr.get("form", {}).get("element_count", 0),
                    "events_count": len(fr.get("form", {}).get("events", [])),
                }
            )
        response = {"config": config_name, "stats": form_data.get("stats", {}), "forms": summary}
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]

    found = None
    for fr in forms:
        if fr.get("name", "").lower() == form_name.lower():
            if parent_name and fr.get("parent_name", "").lower() != parent_name.lower():
                continue
            found = fr
            break

    if not found:
        suggestions = list(
            {
                f"{fr.get('parent_name', '')}.{fr.get('name', '')}"
                for fr in forms
                if form_name.lower() in fr.get("name", "").lower()
            }
        )[:10]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"Form '{form_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    return [types.TextContent(type="text", text=json.dumps(found, ensure_ascii=False, indent=2))]


STRUCTURE_HANDLERS: dict[str, Any] = {
    "get_object_structure": handle_get_object_structure,
    "get_skd_schema": handle_get_skd_schema,
    "get_form_structure": handle_get_form_structure,
}
