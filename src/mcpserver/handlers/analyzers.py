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
    """Сбор контекста для решения задачи 1С + workflow recommendations."""
    from src.services.task_processor import TaskProcessor

    query = arguments.get("query", "")
    config = arguments.get("config", "")
    limit = arguments.get("limit", 5)

    processor = TaskProcessor(project.paths)
    ctx = await run_sync(processor.solve, query, config_name=config, limit=limit)
    ctx_dict = ctx.to_dict()

    # Step 3: Generate workflow recommendations based on task type
    query_lower = query.lower()
    workflow: list[dict[str, str]] = []

    # Detect task type and recommend workflow
    if any(w in query_lower for w in ["запрос", "query", "register", "регистр", "выбрать"]):
        # Task: write a query
        workflow = [
            {"step": 1, "tool": "search_1c_methods", "why": "Найти методы работающие с регистром/объектом"},
            {"step": 2, "tool": "get_object_structure", "why": "Получить точные имена полей (ресурсы, измерения) ПЕРЕД написанием запроса"},
            {"step": 3, "tool": "bsl_templates", "why": "Использовать шаблон query_with_filter (SEC001: параметризованный запрос)"},
            {"step": 4, "tool": "audit_security", "why": "Проверить готовый код на SQL-инъекции (SEC001)"},
            {"step": 5, "tool": "check_standards", "why": "Проверить стандарты 1С (ключевые слова, области, тернарные операторы)"},
        ]
    elif any(w in query_lower for w in ["обработк", "epf", "внешняя", "форма"]):
        # Task: create EPF / form
        workflow = [
            {"step": 1, "tool": "search_1c_methods", "why": "Найти похожие реализации"},
            {"step": 2, "tool": "get_object_structure", "why": "Получить структуру объекта для формы"},
            {"step": 3, "tool": "bsl_templates", "why": "Использовать шаблон для генерации BSL кода"},
            {"step": 4, "tool": "epf_factory_create", "why": "Создать .epf файл из сгенерированного кода"},
            {"step": 5, "tool": "audit_security", "why": "Проверить код на безопасность"},
        ]
    elif any(w in query_lower for w in ["аудит", "security", "безопасн", "уязвим"]):
        # Task: security audit
        workflow = [
            {"step": 1, "tool": "audit_security", "why": "Аудит BSL кода (15 правил SEC001-SEC015)"},
            {"step": 2, "tool": "check_standards", "why": "Проверка стандартов 1С (56 правил)"},
            {"step": 3, "tool": "code_sandbox", "why": "Проверка кода в sandbox перед выполнением"},
        ]
    elif any(w in query_lower for w in ["зависим", "архитектур", "call", "вызов"]):
        # Task: architecture analysis
        workflow = [
            {"step": 1, "tool": "inspect", "why": "Получить обзор конфигурации (типы, количество объектов)"},
            {"step": 2, "tool": "build_dependency_graph", "why": "Построить граф зависимостей метаданных"},
            {"step": 3, "tool": "call_graph", "why": "Анализ вызовов методов (callers, callees, cycles, dead-code)"},
        ]
    elif any(w in query_lower for w in ["поиск", "find", "search", "метод"]):
        # Task: search
        workflow = [
            {"step": 1, "tool": "list_configs", "why": "Проверить какие конфигурации загружены"},
            {"step": 2, "tool": "search_1c_methods", "why": "BM25 поиск по методам платформы 1С"},
            {"step": 3, "tool": "search_code", "why": "BM25 поиск по коду конфигурации"},
            {"step": 4, "tool": "get_object_structure", "why": "Получить структуру найденного объекта"},
        ]
    else:
        # Default workflow
        workflow = [
            {"step": 1, "tool": "list_configs", "why": "Проверить доступные конфигурации"},
            {"step": 2, "tool": "search_1c_methods", "why": "Найти релевантные методы"},
            {"step": 3, "tool": "get_object_structure", "why": "Получить структуру объекта"},
            {"step": 4, "tool": "call_graph", "why": "Анализ зависимостей"},
            {"step": 5, "tool": "audit_security", "why": "Проверка безопасности"},
            {"step": 6, "tool": "check_standards", "why": "Проверка стандартов"},
        ]

    response = {
        **ctx_dict,
        "_workflow": workflow,
        "_workflow_hint": "Следуйте шагам workflow выше для решения задачи. Каждый step указывает tool и причину вызова.",
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
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
