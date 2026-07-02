"""
dsl_cfe.py — handlers для DSL компиляторов, CFE, СКД и графа зависимостей.

P2.2: вынесено из mcp_server.py (группа 2).
Handlers: dsl_compile_*, cfe_*, skd_trace, build_dependency_graph, dependency_query
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import mcp.types as types

if TYPE_CHECKING:
    from src.project import Project


# ─── DSL compilers ───


async def handle_dsl_compile_meta(project: Project, arguments: dict) -> list[types.TextContent]:
    """Компиляция JSON DSL → XML метаданных 1С."""
    from src.services.dsl_compiler import DslCompiler

    definition = arguments.get("definition", {})
    output_dir = arguments.get("output_dir", "")

    if not output_dir:
        return [types.TextContent(type="text", text=json.dumps({"error": "output_dir required"}, ensure_ascii=False))]

    try:
        compiler = DslCompiler()
        result = compiler.compile_meta(definition, output_dir)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_path": str(result.xml_path) if result.xml_path else None,
                        "module_paths": [str(p) for p in result.module_paths],
                        "registered_in_config": result.registered_in_config,
                        "warnings": result.warnings,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_dsl_compile_form(project: Project, arguments: dict) -> list[types.TextContent]:
    """Компиляция JSON DSL → XML управляемой формы."""
    from src.services.dsl_compiler import DslCompiler

    definition = arguments.get("definition", {})
    output_path = arguments.get("output_path", "")

    if not output_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "output_path required"}, ensure_ascii=False))]

    try:
        compiler = DslCompiler()
        result = compiler.compile_form(definition, output_path)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_path": str(result.xml_path) if result.xml_path else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_dsl_compile_skd(project: Project, arguments: dict) -> list[types.TextContent]:
    """Компиляция JSON DSL → XML схемы компоновки данных."""
    from src.services.dsl_compiler import DslCompiler

    definition = arguments.get("definition", {})
    output_path = arguments.get("output_path", "")

    if not output_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "output_path required"}, ensure_ascii=False))]

    try:
        compiler = DslCompiler()
        result = compiler.compile_skd(definition, output_path)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_path": str(result.xml_path) if result.xml_path else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_dsl_compile_mxl(project: Project, arguments: dict) -> list[types.TextContent]:
    """Компиляция JSON DSL → XML MXL-макета."""
    from src.services.dsl_compiler import DslCompiler

    definition = arguments.get("definition", {})
    output_path = arguments.get("output_path", "")

    if not output_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "output_path required"}, ensure_ascii=False))]

    try:
        compiler = DslCompiler()
        result = compiler.compile_mxl(definition, output_path)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_path": str(result.xml_path) if result.xml_path else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_dsl_compile_role(project: Project, arguments: dict) -> list[types.TextContent]:
    """Компиляция JSON DSL → XML роли 1С."""
    from src.services.dsl_compiler import DslCompiler

    definition = arguments.get("definition", {})
    output_dir = arguments.get("output_dir", "")

    if not output_dir:
        return [types.TextContent(type="text", text=json.dumps({"error": "output_dir required"}, ensure_ascii=False))]

    try:
        compiler = DslCompiler()
        result = compiler.compile_role(definition, output_dir)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_path": str(result.xml_path) if result.xml_path else None,
                        "module_paths": [str(p) for p in result.module_paths],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


# ─── CFE ───


async def handle_cfe_borrow(project: Project, arguments: dict) -> list[types.TextContent]:
    """Заимствование объекта в расширение CFE."""
    from src.services.cfe_manager import CfeManager

    extension_path = arguments.get("extension_path", "")
    config_path = arguments.get("config_path", "")
    object_ref = arguments.get("object_ref", "")

    if not all([extension_path, config_path, object_ref]):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "extension_path, config_path, object_ref required"}, ensure_ascii=False),
            )
        ]

    try:
        manager = CfeManager()
        result = manager.borrow_object(Path(extension_path), Path(config_path), object_ref)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "object_ref": result.object_ref,
                        "object_type": result.object_type,
                        "object_name": result.object_name,
                        "xml_created": [str(p) for p in result.xml_created],
                        "registered_in_config": result.registered_in_config,
                        "warnings": result.warnings,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_cfe_patch_method(project: Project, arguments: dict) -> list[types.TextContent]:
    """Генерация &Перед/&После/&ИзменениеИКонтроль для метода."""
    from src.services.cfe_manager import CfeManager

    extension_path = arguments.get("extension_path", "")
    module_path = arguments.get("module_path", "")
    method_name = arguments.get("method_name", "")
    interceptor_type = arguments.get("interceptor_type", "Before")
    context = arguments.get("context", "НаСервере")
    is_function = arguments.get("is_function", False)

    if not all([extension_path, module_path, method_name]):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "extension_path, module_path, method_name required"}, ensure_ascii=False),
            )
        ]

    try:
        manager = CfeManager()
        result = manager.patch_method(
            Path(extension_path), module_path, method_name, interceptor_type, context, is_function
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "module_path": result.module_path,
                        "method_name": result.method_name,
                        "interceptor_type": result.interceptor_type,
                        "bsl_file": str(result.bsl_file) if result.bsl_file else None,
                        "bsl_content": result.bsl_content,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_cfe_diff(project: Project, arguments: dict) -> list[types.TextContent]:
    """Анализ расширения: что заимствовано, что перехвачено."""
    from src.services.cfe_manager import CfeManager

    extension_path = arguments.get("extension_path", "")
    config_path = arguments.get("config_path", "")

    if not all([extension_path, config_path]):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "extension_path, config_path required"}, ensure_ascii=False),
            )
        ]

    try:
        manager = CfeManager()
        result = manager.diff(Path(extension_path), Path(config_path))
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "extension_path": str(result.extension_path),
                        "config_path": str(result.config_path),
                        "borrowed_objects": result.borrowed_objects,
                        "patch_methods": result.patch_methods,
                        "not_in_config": result.not_in_config,
                        "warnings": result.warnings,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


# ─── СКД ───


async def handle_skd_trace(project: Project, arguments: dict) -> list[types.TextContent]:
    """Трассировка поля через всю цепочку СКД."""
    sys.path.insert(0, str(project.paths.scripts_dir))
    from skd_parser import trace_field as _trace_field

    template_path = arguments.get("template_path", "")
    field_name = arguments.get("field_name", "")

    if not all([template_path, field_name]):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "template_path, field_name required"}, ensure_ascii=False),
            )
        ]

    try:
        result = _trace_field(Path(template_path), field_name)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


# ─── Dependency graph ───


async def handle_build_dependency_graph(project: Project, arguments: dict) -> list[types.TextContent]:
    """Построение графа зависимостей метаданных."""
    from src.services.dependency_graph import DependencyGraph

    config_name = arguments.get("config_name", "")

    if not config_name:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

    try:
        dg = DependencyGraph()
        result = dg.build_from_metadata_index(config_name, project.paths)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "config_name": result.config_name,
                        "nodes": result.nodes,
                        "edges": [
                            {"source": e.source, "target": e.target, "relation": e.relation, "detail": e.detail}
                            for e in result.edges
                        ],
                        "warnings": result.warnings,
                        "stats": dg.get_stats(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def handle_dependency_query(project: Project, arguments: dict) -> list[types.TextContent]:
    """Запросы к графу зависимостей."""
    from src.services.dependency_graph import DependencyGraph

    config_name = arguments.get("config_name", "")
    query_type = arguments.get("query_type", "")
    object_ref = arguments.get("object_ref", "")

    if not all([config_name, query_type, object_ref]):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "config_name, query_type, object_ref required"}, ensure_ascii=False),
            )
        ]

    try:
        dg = DependencyGraph()
        dg.build_from_metadata_index(config_name, project.paths)

        if query_type == "what_depends_on":
            result = dg.what_depends_on(object_ref)
        elif query_type == "dependencies_of":
            result = dg.dependencies_of(object_ref)
        elif query_type == "transitive_dependencies":
            result = dg.transitive_dependencies(object_ref)
        elif query_type == "transitive_dependents":
            result = dg.transitive_dependents(object_ref)
        elif query_type == "find_cycles":
            result = dg.find_cycles()
        elif query_type == "find_unused_objects":
            result = dg.find_unused_objects()
        elif query_type == "find_root_objects":
            result = dg.find_root_objects()
        elif query_type == "shortest_path":
            target = arguments.get("target", "")
            result = dg.shortest_path(object_ref, target)
        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown query_type: {query_type}"}, ensure_ascii=False),
                )
            ]

        return [types.TextContent(type="text", text=json.dumps({"result": result}, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


# Реестр handlers группы 2
DSL_CFE_HANDLERS: dict = {
    "dsl_compile_meta": handle_dsl_compile_meta,
    "dsl_compile_form": handle_dsl_compile_form,
    "dsl_compile_skd": handle_dsl_compile_skd,
    "dsl_compile_mxl": handle_dsl_compile_mxl,
    "dsl_compile_role": handle_dsl_compile_role,
    "cfe_borrow": handle_cfe_borrow,
    "cfe_patch_method": handle_cfe_patch_method,
    "cfe_diff": handle_cfe_diff,
    "skd_trace": handle_skd_trace,
    "build_dependency_graph": handle_build_dependency_graph,
    "dependency_query": handle_dependency_query,
}
