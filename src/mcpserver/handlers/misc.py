"""
misc.py — handlers для OpenSpec, inspect, data и контекста.

P2.2: вынесено из mcp_server.py (группа 4).
Handlers: openspec_*, inspect, data_status, get_object_structure,
          get_skd_schema, get_form_structure, get_knowledge
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

import mcp.types as types

if TYPE_CHECKING:
    from src.project import Project


# ─── OpenSpec ───


async def handle_openspec_proposal(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Создание proposal в OpenSpec."""
    from src.services.openspec_manager import OpenSpecManager

    change_id = arguments.get("change_id", "")
    title = arguments.get("title", "")
    context = arguments.get("context", "")
    approach = arguments.get("approach", "")
    tasks = arguments.get("tasks", [])
    files = arguments.get("files", [])

    if not all([change_id, title]):
        return [
            types.TextContent(type="text", text=json.dumps({"error": "change_id, title required"}, ensure_ascii=False))
        ]

    try:
        osm = OpenSpecManager(project_root=project.paths.root)
        if not osm.exists():
            osm.init_project()
        change = osm.create_proposal(
            change_id=change_id,
            title=title,
            context=context,
            approach=approach,
            tasks=tasks,
            files=files,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "change_id": change.change_id,
                        "title": change.title,
                        "status": change.status,
                        "tasks_count": len(change.tasks),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_openspec_list(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Список changes в OpenSpec."""
    from src.services.openspec_manager import OpenSpecManager

    include_archived = arguments.get("include_archived", False)

    try:
        osm = OpenSpecManager(project_root=project.paths.root)
        changes = osm.list_changes(include_archived=include_archived)
        return [types.TextContent(type="text", text=json.dumps({"changes": changes}, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_openspec_update_task(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Обновление task в OpenSpec."""
    from src.services.openspec_manager import OpenSpecManager

    change_id = arguments.get("change_id", "")
    task_index = arguments.get("task_index", 0)
    completed = arguments.get("completed")
    notes = arguments.get("notes", "")

    if not change_id:
        return [types.TextContent(type="text", text=json.dumps({"error": "change_id required"}, ensure_ascii=False))]

    try:
        osm = OpenSpecManager(project_root=project.paths.root)
        result = osm.update_task(change_id, task_index, completed, notes)
        return [types.TextContent(type="text", text=json.dumps({"updated": result}, ensure_ascii=False))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_openspec_archive(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Архивирование change в OpenSpec."""
    from src.services.openspec_manager import OpenSpecManager

    change_id = arguments.get("change_id", "")

    if not change_id:
        return [types.TextContent(type="text", text=json.dumps({"error": "change_id required"}, ensure_ascii=False))]

    try:
        osm = OpenSpecManager(project_root=project.paths.root)
        result = osm.archive(change_id)
        return [types.TextContent(type="text", text=json.dumps({"archived": result}, ensure_ascii=False))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


# Реестр handlers группы 4 (OpenSpec)
# inspect, data_status, get_* — будут добавлены в следующих коммитах
MISC_HANDLERS: dict[str, Any] = {
    "openspec_proposal": handle_openspec_proposal,
    "openspec_list": handle_openspec_list,
    "openspec_update_task": handle_openspec_update_task,
    "openspec_archive": handle_openspec_archive,
}
