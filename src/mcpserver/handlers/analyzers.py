"""
analyzers.py — handlers для анализаторов BSL, генерации и EPF.

P2.2: вынесено из mcp_server.py (группа 3 + 4).
Handlers: analyze_bsl, check_standards, solve_context, solve_check,
          audit_security, get_code_metrics, check_transactions, analyze_queries,
          analyze_architecture, check_form_quality, check_skd_quality,
          diff_configs, generate_processing, generate_report, build_epf,
          validate_generated, epf_factory_create, epf_factory_templates
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import mcp.types as types

from ._async_helpers import run_sync

if TYPE_CHECKING:
    from src.project import Project


# ─── BSL анализаторы ───


async def handle_analyze_bsl(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Анализ .bsl файла через BSL Language Server."""
    file_path = arguments.get("file_path", "")
    try:
        # P1.10: BSL LS analysis может занимать секунды — не блокируем event loop.
        result = await run_sync(project.bsl_analyzer.analyze, Path(file_path))
        response = {
            "total": result.total,
            "by_code": result.by_code,
            "diagnostics": result.diagnostics[:50],  # ограничиваем
        }
        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
            )
        ]


async def handle_check_standards(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Проверка .bsl файла на 56 правил стандартов 1С."""
    file_path = arguments.get("file_path", "")
    try:
        # Этап 1.2, Группа 1f: dynamic import заменён на прямой импорт из src.services.analyzers
        from src.services.analyzers.check_1c_standards import StandardsChecker

        checker = StandardsChecker()
        violations = checker.check_file(Path(file_path))
        response = [
            {
                "rule_id": v.rule_id,
                "severity": v.severity,
                "line": v.line,
                "message": v.message,
            }
            for v in violations
        ]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
            )
        ]


async def handle_solve_context(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Сбор контекста для решения задачи 1С."""
    from src.services.task_processor import TaskProcessor

    query = arguments.get("query", "")
    config = arguments.get("config", "")
    limit = arguments.get("limit", 5)

    processor = TaskProcessor(project.paths)
    # P1.10: solve() собирает контекст из 7 источников — sync I/O тяжелый.
    ctx = await run_sync(processor.solve, query, config_name=config, limit=limit)

    return [
        types.TextContent(
            type="text",
            text=json.dumps(ctx.to_dict(), ensure_ascii=False, indent=2),
        )
    ]


async def handle_solve_check(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Полная проверка .bsl кода: 7 анализаторов."""
    from src.services.task_processor import TaskProcessor

    file_path = arguments.get("file_path", "")
    level = arguments.get("level", "standard")

    processor = TaskProcessor(project.paths)
    try:
        # P1.10: check() запускает 7 анализаторов (BSL LS, security_auditor, etc) —
        # может занимать 5-30 секунд. Без to_thread блокирует event loop MCP-сервера.
        result = await run_sync(processor.check, Path(file_path), level=level)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            )
        ]
    except FileNotFoundError as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
            )
        ]


# Реестр handlers группы 3a (BSL анализаторы)
# Остальные handlers будут добавлены в следующих коммитах
ANALYZER_HANDLERS: dict[str, Any] = {
    "analyze_bsl": handle_analyze_bsl,
    "check_standards": handle_check_standards,
    "solve_context": handle_solve_context,
    "solve_check": handle_solve_check,
}
