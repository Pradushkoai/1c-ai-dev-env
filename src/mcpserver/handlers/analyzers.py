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
    """Проверка .bsl файла на 62 правил стандартов 1С."""
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
    """Сбор контекста для решения задачи 1С + workflow recommendations.

    F2.5: Использует intent classifier вместо keyword matching.
    Возвращает:
    - ctx_dict: контекст из 7 источников (platform_methods, api, metadata, ...)
    - _intent: {name, confidence, target_context_hint, object_type_hint}
    - _workflow: последовательность tools для данного intent
    - _required_sources: какие источники релевантны (для F2.6 source selection)
    - _workflow_hint: короткая подсказка
    """
    from src.services.task_processor import TaskProcessor
    from src.services.intent.classifier import classify_intent, get_intent_description

    query = arguments.get("query", "")
    config = arguments.get("config", "")
    limit = arguments.get("limit", 5)

    # F2.5: Intent classification
    intent = classify_intent(query)

    processor = TaskProcessor(project.paths)
    # F2.6: Source selection — передаём required_sources из intent classifier
    ctx = await run_sync(
        processor.solve,
        query,
        config_name=config,
        limit=limit,
        required_sources=intent.required_sources,
    )
    ctx_dict = ctx.to_dict()

    # F2.5+F2.6: Intent уже классифицирован выше, добавляем metadata в response
    response = {
        **ctx_dict,
        "_intent": {
            "name": intent.name,
            "description": get_intent_description(intent.name),
            "confidence": intent.confidence,
            "target_context_hint": intent.target_context_hint,
            "object_type_hint": intent.object_type_hint,
            "matched_patterns_count": len(intent.matched_patterns),
        },
        "_required_sources": intent.required_sources,
        "_workflow": intent.workflow,
        "_workflow_hint": (
            f"Intent: {intent.name} (confidence={intent.confidence:.2f}). "
            "Следуйте шагам workflow. BSL-контекстные правила — в system prompt сервера."
        ),
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


async def handle_solve_check(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Полная проверка .bsl кода: 7 анализаторов (standard) / 9 (full).

    F2.4: Возвращает приоритизированный результат:
    - summary: must_fix_before_use_count, is_safe_to_use, verdict
    - must_fix_before_use: CRITICAL/HIGH violations (блокируют использование)
    - top_3_priority: топ-3 violation по severity
    - violations: полный список
    - _next_steps: actionable hints для LLM
    """
    from src.services.task_processor import TaskProcessor

    file_path = arguments.get("file_path", "")
    level = arguments.get("level", "standard")

    processor = TaskProcessor(project.paths)
    try:
        # P1.10: check() запускает 7-9 анализаторов — может занимать 5-30 секунд.
        result = await run_sync(processor.check, Path(file_path), level=level)
        result_dict = result.to_dict()

        # F2.4: Добавляем _next_steps на основе приоритизации
        next_steps: list[str] = []
        if result.is_safe_to_use:
            next_steps.append("✅ Код безопасен — можно использовать (нет CRITICAL/HIGH violations)")
            if result.total_warnings > 0:
                next_steps.append(
                    f"Рекомендуется исправить {result.total_warnings} WARNING нарушений "
                    "(не блокирует, но улучшает качество)"
                )
        else:
            next_steps.append(
                f"❌ {result.must_fix_before_use_count} CRITICAL/HIGH violation(s) — "
                "ИСПРАВЬТЕ перед использованием кода"
            )
            # Добавляем конкретные top-3 в next_steps
            for i, v in enumerate(result.top_3_priority, 1):
                next_steps.append(
                    f"  {i}. [{v.severity}] {v.source}:{v.rule_id} line {v.line} — {v.message}"
                )
            next_steps.append(
                "После исправления — повторите solve_check для верификации"
            )

        result_dict["_next_steps"] = next_steps
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result_dict, ensure_ascii=False, indent=2),
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
