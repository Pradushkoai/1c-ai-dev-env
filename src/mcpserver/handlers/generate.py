"""
generate.py — handlers для генерации кода и EPF.

P2.2: вынесено из mcp_server.py (группа 7).
Handlers: generate_processing, generate_report, build_epf, validate_generated,
          epf_factory_create, epf_factory_templates
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import mcp.types as types

# Этап 1.2, Группа 2: импортируем напрямую из services (dynamic import удалён)
from src.services.code_generator import generate_processing, generate_report
from src.services.code_validator import validate_generated
from src.services.epf_builder import build_epf

if TYPE_CHECKING:
    from src.project import Project


async def handle_generate_processing(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: generate_processing, generate_report."""
    obj_name = arguments.get("name", "")
    synonym = arguments.get("synonym", "")
    description = arguments.get("description", "")
    author = arguments.get("author", "")
    output_dir = arguments.get("output_dir", "")

    if not obj_name or not synonym:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": "name and synonym are required"}, ensure_ascii=False)
            )
        ]

    # По умолчанию — generated/<name>
    if not output_dir:
        output_dir = str(project.paths.root / "generated" / obj_name)

    result = generate_processing(obj_name, synonym, output_dir, description, author)

    response = {
        "status": "success",
        "object_type": result["stats"]["object_type"],
        "name": obj_name,
        "synonym": synonym,
        "uuid": result["stats"].get("uuid", ""),
        "output_dir": output_dir,
        "total_files": result["stats"]["total_files"],
        "bsl_files": result["stats"]["bsl_files"],
        "xml_files": result["stats"]["xml_files"],
        "files": [
            {"path": f["path"].replace(str(project.paths.root) + "/", ""), "type": f["type"], "size": f["size"]}
            for f in result["files"]
        ],
    }
    return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


async def handle_build_epf(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: build_epf."""
    source_dir = arguments.get("source_dir", "")
    output_path = arguments.get("output_path", "")
    object_name = arguments.get("object_name")
    object_type = arguments.get("object_type", "DataProcessor")

    if not source_dir or not output_path:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "source_dir and output_path are required"}, ensure_ascii=False),
            )
        ]

    # Преобразуем относительные пути
    if not os.path.isabs(source_dir):
        source_dir = str(project.paths.root / source_dir)
    if not os.path.isabs(output_path):
        output_path = str(project.paths.root / output_path)

    if not os.path.exists(source_dir):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"source_dir not found: {source_dir}"}, ensure_ascii=False),
            )
        ]

    try:
        result = build_epf(source_dir, output_path, object_name, object_type)
        response = {
            "status": "success",
            "file_path": result["file_path"],
            "size": result["size"],
            "object_name": result["object_name"],
            "object_type": result["object_type"],
            "uuid": result["uuid"],
            "files_included": result["files_included"],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Build failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_validate_generated(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: validate_generated."""
    source_dir = arguments.get("source_dir", "")

    if not source_dir:
        return [
            types.TextContent(type="text", text=json.dumps({"error": "source_dir is required"}, ensure_ascii=False))
        ]

    # Преобразуем относительный путь
    if not os.path.isabs(source_dir):
        source_dir = str(project.paths.root / source_dir)

    if not os.path.exists(source_dir):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"source_dir not found: {source_dir}"}, ensure_ascii=False),
            )
        ]

    try:
        result = validate_generated(source_dir)
        response = {
            "source_dir": result["source_dir"],
            "verdict": result["verdict"],
            "total_errors": result["total_errors"],
            "total_warnings": result["total_warnings"],
            "structure": result["structure"],
            "bsl_validation": result.get("bsl_validation", []),
            "xml_validation": result.get("xml_validation", []),
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"Validation failed: {str(e)}"}, ensure_ascii=False)
            )
        ]


async def handle_epf_factory_create(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: epf_factory_create."""
    # Создание .epf через EpfFactory
    try:
        from src.services.epf_factory import EpfFactory

        epf_name = arguments.get("name", "")
        if not epf_name:
            return [types.TextContent(type="text", text=json.dumps({"error": "name required"}, ensure_ascii=False))]

        output_path = arguments.get("output_path", "")
        if not output_path:
            return [
                types.TextContent(type="text", text=json.dumps({"error": "output_path required"}, ensure_ascii=False))
            ]

        # BSL-код можно передать прямо или из файла
        bsl_code = arguments.get("bsl_code", "")
        bsl_path = arguments.get("bsl_path", "")
        if not bsl_code and bsl_path:
            from pathlib import Path as PathMod

            p = PathMod(bsl_path)
            if not p.exists():
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"BSL file not found: {bsl_path}"}, ensure_ascii=False),
                    )
                ]
            bsl_code = p.read_text(encoding="utf-8")
        if not bsl_code:
            # Используем минимальный шаблон
            bsl_code = (
                "#Область ПрограммныйИнтерфейс\n\n"
                "#КонецОбласти\n\n"
                "#Область СлужебныеПроцедурыИФункции\n\n"
                "#КонецОбласти\n"
            )

        synonym = arguments.get("synonym") or epf_name
        form_name = arguments.get("form_name", "Форма")
        skip_bsl_validation = arguments.get("skip_bsl_validation", False)
        save_sources = arguments.get("save_sources", False)

        # form_spec может прийти как dict (inline) или путь к файлу
        form_spec = arguments.get("form_spec")
        form_spec_path = arguments.get("form_spec_path")
        if not form_spec and form_spec_path:
            form_spec = form_spec_path  # EpfFactory сам прочитает файл

        factory = EpfFactory()
        result = factory.create_epf(
            name=epf_name,
            synonym=synonym,
            bsl_code=bsl_code,
            output_epf=output_path,
            form_name=form_name,
            form_spec=form_spec,
            save_sources=save_sources,
            skip_bsl_validation=skip_bsl_validation,
        )

        response = {
            "ok": result.ok,
            "error": result.error,
            "epf_path": str(result.epf_path) if result.epf_path else None,
            "size_bytes": result.size_bytes,
            "name": result.name,
            "synonym": result.synonym,
            "proc_uuid": result.proc_uuid,
            "form_uuid": result.form_uuid,
            "bsl_lines": result.bsl_lines,
            "bsl_warnings": result.bsl_warnings,
            "bsl_errors": result.bsl_errors,
            "round_trip_ok": result.round_trip_ok,
            "work_dir": str(result.work_dir) if result.work_dir else None,
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"epf_factory_create failed: {str(e)}"}, ensure_ascii=False),
            )
        ]


async def handle_epf_factory_templates(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: epf_factory_templates."""
    # Список шаблонов epf-factory
    try:
        from src.services.epf_factory import EpfFactory

        templates = EpfFactory.list_templates()
        return [types.TextContent(type="text", text=json.dumps(templates, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"epf_factory_templates failed: {str(e)}"}, ensure_ascii=False),
            )
        ]


async def handle_generate_report(project: Project, arguments: dict) -> list[types.TextContent]:
    """Генерация отчёта 1С через code_generator."""
    obj_name = arguments.get("name", "")
    synonym = arguments.get("synonym", "")
    description = arguments.get("description", "")
    author = arguments.get("author", "")
    output_dir = arguments.get("output_dir", "")
    data_source = arguments.get("data_source", "")
    main_query = arguments.get("main_query", "")

    if not obj_name or not synonym:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": "name and synonym are required"}, ensure_ascii=False)
            )
        ]

    if not output_dir:
        output_dir = str(project.paths.root / "generated" / obj_name)

    result = generate_report(obj_name, synonym, output_dir, description, author, data_source, main_query)

    response = {
        "status": "success",
        "object_type": result["stats"]["object_type"],
        "name": obj_name,
        "synonym": synonym,
        "uuid": result["stats"].get("uuid", ""),
        "output_dir": output_dir,
        "total_files": result["stats"]["total_files"],
        "bsl_files": result["stats"]["bsl_files"],
        "xml_files": result["stats"]["xml_files"],
        "files": [
            {"path": f["path"].replace(str(project.paths.root) + "/", ""), "type": f["type"], "size": f["size"]}
            for f in result["files"]
        ],
    }
    return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]


# Реестр handlers
GENERATE_HANDLERS: dict = {
    "generate_processing": handle_generate_processing,
    "generate_report": handle_generate_report,
    "build_epf": handle_build_epf,
    "validate_generated": handle_validate_generated,
    "epf_factory_create": handle_epf_factory_create,
    "epf_factory_templates": handle_epf_factory_templates,
}
