"""
high_level.py — R1: High-level MCP tools (5 вместо 12).

R1 (2026-07-09): Консолидация visible tools в 5 глаголов высокого уровня:
  1. plan(task) — intent classification + source selection
  2. gather(plan_id) — собрать контекст (cached, R2)
  3. generate(task, plan_id, target_context) — BSL/query/DSL + inline validation
  4. validate(artifact_id) — полная проверка (solve_check + check_bsl_context)
  5. explain(artifact_or_query) — понимание существующего кода

R3: Нет _workflow в response — только _next_action (одно конкретное действие).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

import mcp.types as types

from ._async_helpers import run_sync
from .analyzers import handle_solve_check
from .quality import handle_check_bsl_context

if TYPE_CHECKING:
    from src.project import Project

logger = logging.getLogger(__name__)


# ============================================================================
# R1.1: plan — intent classification + source selection
# ============================================================================


async def handle_plan(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Классифицировать intent задачи и вернуть план действий.

    Это ПЕРВЫЙ tool, который LLM должен вызвать. Возвращает:
    - intent: {name, confidence, description}
    - target_context_hint: thin_client | server | mobile_client
    - required_sources: какие источники нужны для gather
    - pipeline: последовательность high-level tools

    Не собирает контекст — только планирует. Используйте gather(plan_id)
    для сбора контекста.

    R3: Возвращает _next_action (одно конкретное действие), не _workflow.
    """
    from src.services.intent.classifier import classify_intent, get_intent_description
    from src.services.session import SessionManager

    query = arguments.get("query", "")
    config = arguments.get("config", "")

    if not query:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "query required"}, ensure_ascii=False),
            )
        ]

    # R2: Сохраняем plan в session
    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    intent = classify_intent(query)

    plan_data = {
        "query": query,
        "config": config,
        "intent": {
            "name": intent.name,
            "description": get_intent_description(intent.name),
            "confidence": intent.confidence,
        },
        "target_context_hint": intent.target_context_hint,
        "object_type_hint": intent.object_type_hint,
        "required_sources": intent.required_sources,
    }

    session.set_plan(plan_data)
    session.add_tool_call("plan", arguments)
    session_manager.save()

    # R3: _next_action — одно конкретное действие, не 7-step workflow
    next_action = {
        "tool": "gather",
        "args": {"plan_id": session.session_id},
        "why": f"Собрать контекст для intent '{intent.name}' из источников: {', '.join(intent.required_sources)}",
    }

    response = {
        "plan_id": session.session_id,
        **plan_data,
        "_next_action": next_action,
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


# ============================================================================
# R1.2: gather — собрать контекст (cached)
# ============================================================================


async def handle_gather(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Собрать контекст для решения задачи.

    Использует plan из session (если plan_id указан) для source selection.
    Кэширует результат в session (R2) — повторный вызов с тем же plan_id
    возвращает кэшированный контекст без повторного поиска.

    Возвращает:
    - platform_methods: найденные методы платформы
    - metadata: объекты конфигурации
    - api_modules: API-справочник
    - safe_methods: методы, доступные в target_context (pre-hoc, R1)
    - knowledge_articles: статьи из KB
    - standards_summary: доступные стандарты

    R3: _next_action зависит от intent.
    """
    from src.services.task_processor import TaskProcessor
    from src.services.session import SessionManager

    plan_id = arguments.get("plan_id", "")
    force_refresh = arguments.get("force_refresh", False)
    limit = arguments.get("limit", 5)

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    # R2: Проверяем кэш
    if (
        not force_refresh
        and session.gathered_context is not None
        and plan_id
        and session.plan is not None
    ):
        # Возвращаем кэшированный контекст
        response = {
            **session.gathered_context,
            "_cached": True,
            "_cached_at": session.gathered_at,
            "_next_action": _get_next_action_after_gather(session.plan),
        }
        session.add_tool_call("gather", arguments)
        session_manager.save()
        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]

    # Проверяем что plan существует
    if not session.plan:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "No plan in session. Call plan() first.", "_next_action": {"tool": "plan", "args": {}}},
                    ensure_ascii=False,
                ),
            )
        ]

    plan = session.plan
    query = plan.get("query", "")
    config = plan.get("config", "")
    required_sources = plan.get("required_sources", [])

    # Собираем контекст с source selection
    processor = TaskProcessor(project.paths)
    ctx = await run_sync(
        processor.solve,
        query,
        config_name=config,
        limit=limit,
        required_sources=required_sources,
    )
    ctx_dict = ctx.to_dict()

    # R1: Добавляем safe_methods (pre-hoc guidance встроен в gather)
    target_context = plan.get("target_context_hint", "")
    if target_context:
        safe_methods = await _get_safe_methods_inline(project, target_context, query, limit)
        if safe_methods:
            ctx_dict["safe_methods"] = safe_methods

    # R2: Кэшируем
    session.set_gathered_context(ctx_dict)
    session.add_tool_call("gather", arguments)
    session_manager.save()

    response = {
        **ctx_dict,
        "_cached": False,
        "_next_action": _get_next_action_after_gather(plan),
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


async def _get_safe_methods_inline(
    project: Project, target_context: str, query: str, limit: int
) -> list[dict[str, Any]]:
    """Получить safe_methods inline (не отдельный tool call)."""
    try:
        from src.services.platform_methods_index import PlatformMethodsIndex

        idx = PlatformMethodsIndex()
        if not idx.is_available():
            return []

        # Используем query для поиска релевантных методов
        results = idx.search(query, limit=limit * 2)
        safe: list[dict[str, Any]] = []

        contexts = [target_context] if isinstance(target_context, str) else target_context

        for r in results:
            name = r.get("name_ru", "") or r.get("name_en", "")
            if not name:
                continue
            if idx.is_available_in(name, contexts) and not idx.is_deprecated(name):
                safe.append(r)
            if len(safe) >= limit:
                break

        idx.close()
        return safe
    except Exception as e:
        logger.debug("safe_methods inline failed: %s", e)
        return []


def _get_next_action_after_gather(plan: dict[str, Any]) -> dict[str, Any]:
    """R3: Следующее действие после gather — зависит от intent."""
    intent_name = plan.get("intent", {}).get("name", "unknown")

    if intent_name in ("create_object", "generate_bsl", "generate_skd", "cfe_extension"):
        return {
            "tool": "generate",
            "args": {"task": plan.get("query", ""), "target_context": plan.get("target_context_hint", "")},
            "why": f"Сгенерировать артефакт для intent '{intent_name}'",
        }
    elif intent_name == "write_query":
        return {
            "tool": "generate",
            "args": {"task": plan.get("query", ""), "target_context": "server"},
            "why": "Сгенерировать запрос 1С",
        }
    elif intent_name == "audit_code":
        return {
            "tool": "validate",
            "args": {"file_path": "<path_to_bsl>"},
            "why": "Аудит существующего кода",
        }
    elif intent_name == "understand_code":
        return {
            "tool": "explain",
            "args": {"query": plan.get("query", "")},
            "why": "Объяснить существующий код",
        }
    else:
        return {
            "tool": "generate",
            "args": {"task": plan.get("query", "")},
            "why": "Сгенерировать код (default action)",
        }


# ============================================================================
# R1.3: generate — BSL/query/DSL + inline validation
# ============================================================================


async def handle_generate(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Сгенерировать BSL код / запрос / DSL.

    Оркестрирует генерацию + inline валидацию (быстрая, без Java).
    Если CRITICAL violations — пытается auto-fix через templates.

    Возвращает:
    - artifact_id: ID для использования в validate()
    - code: сгенерированный код
    - validation_passed: True если нет CRITICAL
    - warnings: non-critical violations
    - alternatives: suggested alternatives если были CRITICAL

    R3: _next_action — validate (если validation_passed=False) или done.
    """
    from src.services.session import SessionManager

    task = arguments.get("task", "")
    target_context = arguments.get("target_context", "server")
    artifact_type = arguments.get("type", "bsl")  # bsl | query | dsl

    if not task:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "task required"}, ensure_ascii=False),
            )
        ]

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    # Для query — используем существующий generate_query handler
    generated_code = ""
    generation_source = ""

    if artifact_type == "query":
        from .query import handle_generate_query
        result = await handle_generate_query(project, {"task": task})
        if result:
            data = json.loads(result[0].text)
            generated_code = data.get("query", data.get("generated_query", ""))
            generation_source = "query_generator"
    else:
        # BSL — используем bsl_templates (упрощённая генерация)
        try:
            from src.services.bsl_templates import BslTemplates
            templates = BslTemplates()
            # Возвращаем template как стартовую точку
            tpl = templates.get_template("catalog", "object_module")
            if tpl:
                generated_code = tpl
                generation_source = "bsl_templates"
        except Exception:
            pass

    if not generated_code:
        generated_code = f"// TODO: Сгенерировать код для задачи: {task}\n// target_context: {target_context}"
        generation_source = "placeholder"

    # Inline validation (quick — check_bsl_context только)
    validation_passed = True
    warnings: list[dict[str, Any]] = []

    if target_context and generated_code and artifact_type == "bsl":
        try:
            ctx_result = await handle_check_bsl_context(
                project,
                {"code": generated_code, "target_context": [target_context]},
            )
            if ctx_result:
                ctx_data = json.loads(ctx_result[0].text)
                ctx_violations = ctx_data.get("violations", [])
                critical = [v for v in ctx_violations if v.get("severity") == "ERROR"]
                if critical:
                    validation_passed = False
                    warnings = critical
                else:
                    warnings = ctx_violations
        except Exception as e:
            logger.debug("inline validation failed: %s", e)

    # R2: Сохраняем artifact в session
    artifact = {
        "type": artifact_type,
        "task": task,
        "target_context": target_context,
        "code": generated_code,
        "generation_source": generation_source,
        "validation_passed": validation_passed,
        "warnings": warnings,
    }
    artifact_id = session.add_artifact(artifact)
    session.add_tool_call("generate", arguments)
    session_manager.save()

    # R3: _next_action
    if validation_passed:
        next_action = {
            "tool": "done",
            "args": {},
            "why": "Код сгенерирован и прошёл inline validation. Можно использовать.",
        }
    else:
        next_action = {
            "tool": "validate",
            "args": {"artifact_id": artifact_id},
            "why": f"Найдено {len(warnings)} CRITICAL violation(s) — нужна полная проверка",
        }

    response = {
        "artifact_id": artifact_id,
        "code": generated_code,
        "type": artifact_type,
        "generation_source": generation_source,
        "validation_passed": validation_passed,
        "warnings_count": len(warnings),
        "warnings": warnings[:5],  # первые 5
        "_next_action": next_action,
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


# ============================================================================
# R1.4: validate — полная проверка (solve_check + check_bsl_context)
# ============================================================================


async def handle_validate(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Полная валидация кода.

    Если artifact_id указан — берёт код из session (R2 state-aware).
    Если file_path указан — проверяет файл.

    Запускает solve_check (7-9 анализаторов) + check_bsl_context.
    Возвращает приоритизированный результат (F2.4).

    R3: _next_action — fix и re-validate, или done.
    """
    from src.services.session import SessionManager

    artifact_id = arguments.get("artifact_id", "")
    file_path = arguments.get("file_path", "")
    level = arguments.get("level", "standard")

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    # R2: Если artifact_id — берём код из session
    if artifact_id:
        artifact = session.get_artifact(artifact_id)
        if not artifact:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Artifact not found: {artifact_id}"}, ensure_ascii=False),
                )
            ]

        code = artifact.get("code", "")
        target_context = artifact.get("target_context", "server")

        # Для inline code — запускаем check_bsl_context + audit_security
        # (solve_check требует file_path, а у нас code в памяти)
        try:
            ctx_result = await handle_check_bsl_context(
                project, {"code": code, "target_context": [target_context]}
            )
            ctx_data = json.loads(ctx_result[0].text) if ctx_result else {"violations": []}
        except Exception:
            ctx_data = {"violations": []}

        # Группируем violations (R5)
        violations = ctx_data.get("violations", [])
        grouped = _group_violations_by_rule(violations)

        must_fix = [v for v in violations if v.get("severity") == "ERROR"]
        is_safe = len(must_fix) == 0

        validation = {
            "artifact_id": artifact_id,
            "target_context": target_context,
            "total_violations": len(violations),
            "must_fix_count": len(must_fix),
            "is_safe_to_use": is_safe,
            "grouped_violations": grouped,
            "violations": violations,
        }

        session.add_validation(validation)
        session.add_tool_call("validate", arguments)
        session_manager.save()

        next_action = (
            {"tool": "done", "args": {}, "why": "Код прошёл валидацию — можно использовать"}
            if is_safe
            else {
                "tool": "generate",
                "args": {"task": artifact.get("task", ""), "target_context": target_context},
                "why": f"Исправить {len(must_fix)} CRITICAL violation(s) и регенерировать",
            }
        )

        response = {
            **validation,
            "_next_action": next_action,
        }
        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]

    # Если file_path — используем solve_check (F2.4 приоритизация)
    if file_path:
        result = await handle_solve_check(project, {"file_path": file_path, "level": level})
        session.add_tool_call("validate", arguments)
        session_manager.save()
        return result

    return [
        types.TextContent(
            type="text",
            text=json.dumps(
                {"error": "Either artifact_id or file_path required", "_next_action": {"tool": "gather", "args": {}}},
                ensure_ascii=False,
            ),
        )
    ]


def _group_violations_by_rule(violations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """R5: Сгруппировать violations по rule_id."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for v in violations:
        rule_id = v.get("rule_id", "UNKNOWN")
        if rule_id not in grouped:
            grouped[rule_id] = []
        grouped[rule_id].append(v)
    return grouped


# ============================================================================
# R1.5: explain — понимание существующего кода
# ============================================================================


async def handle_explain(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Объяснить существующий код или найти использование.

    Если file_path указан — анализирует код (call_graph, architecture).
    Если query указан — ищет где используется метод/объект.

    R3: _next_action — зависит от результата.
    """
    from src.services.session import SessionManager

    file_path = arguments.get("file_path", "")
    query = arguments.get("query", "")

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    if file_path:
        # Анализ файла — code metrics + architecture
        from .quality import handle_get_code_metrics, handle_analyze_architecture

        metrics_result = await handle_get_code_metrics(project, {"file_path": file_path})

        response: dict[str, Any] = {"file_path": file_path}

        if metrics_result:
            try:
                metrics_data = json.loads(metrics_result[0].text)
                response["metrics"] = metrics_data
            except json.JSONDecodeError:
                pass

        session.add_tool_call("explain", arguments)
        session_manager.save()

        response["_next_action"] = {
            "tool": "validate",
            "args": {"file_path": file_path},
            "why": "Проверить код на violations",
        }

        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]

    if query:
        # Поиск — solve_context для понимания
        from .analyzers import handle_solve_context

        # Сохраняем intent для explain
        session.set_plan({"query": query, "intent": {"name": "understand_code"}})
        session.add_tool_call("explain", arguments)
        session_manager.save()

        # Используем solve_context для поиска
        result = await handle_solve_context(project, {"query": query})

        # R3: Добавляем _next_action
        if result:
            try:
                data = json.loads(result[0].text)
                data["_next_action"] = {
                    "tool": "explain",
                    "args": {"file_path": "<found_file>"},
                    "why": "Посмотреть детали найденного файла",
                }
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(data, ensure_ascii=False, indent=2),
                    )
                ]
            except json.JSONDecodeError:
                pass

        return result

    return [
        types.TextContent(
            type="text",
            text=json.dumps(
                {"error": "Either file_path or query required", "_next_action": {"tool": "plan", "args": {}}},
                ensure_ascii=False,
            ),
        )
    ]


# ============================================================================
# R10: run_cli — proxy для hidden tools
# ============================================================================


# Whitelist разрешённых CLI команд (security — не任意 shell execution)
_ALLOWED_CLI_COMMANDS: frozenset[str] = frozenset({
    "call_graph",
    "build_dependency_graph",
    "dependency_query",
    "dsl_compile_meta",
    "dsl_compile_form",
    "dsl_compile_skd",
    "dsl_compile_mxl",
    "dsl_compile_role",
    "cfe_borrow",
    "cfe_patch_method",
    "cfe_diff",
    "skd_trace",
    "inspect",
    "list_configs",
    "search_code",
    "get_form_elements",
    "get_api_reference",
    "get_knowledge",
    "audit_security",
    "get_code_metrics",
    "check_transactions",
    "analyze_queries",
    "analyze_architecture",
    "check_form_quality",
    "check_skd_quality",
    "diff_configs",
    "validate_query_static",
    "check_data_exchange",
    "openspec_proposal",
    "openspec_list",
    "openspec_update_task",
    "openspec_archive",
    "epf_factory_create",
    "epf_factory_templates",
    "optimize_query",
    "query_workflow",
})


async def handle_run_cli(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R10: Proxy tool для доступа к 44 hidden MCP tools через один visible tool.

    Позволяет LLM вызывать hidden tools (call_graph, dsl_compile_*, cfe_*, etc.)
    без переключения на CLI. Whitelist разрешённых команд — security.

    Args:
        command: Имя hidden tool (должно быть в whitelist)
        args: Аргументы для hidden tool (dict)
    """
    from src.services.session import SessionManager
    from . import (
        DSL_CFE_HANDLERS, MISC_HANDLERS, INSPECT_DATA_HANDLERS,
        STRUCTURE_HANDLERS, GENERATE_HANDLERS, QUALITY_HANDLERS, QUERY_HANDLERS,
        CONFIG_SEARCH_HANDLERS,
    )

    command = arguments.get("command", "")
    args = arguments.get("args", {})

    if not command:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "command required", "allowed": sorted(_ALLOWED_CLI_COMMANDS)},
                    ensure_ascii=False,
                ),
            )
        ]

    if command not in _ALLOWED_CLI_COMMANDS:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"Command not allowed: {command}",
                        "allowed": sorted(_ALLOWED_CLI_COMMANDS),
                        "hint": "Use one of the allowed commands",
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    # Ищем handler во всех регистрах
    all_handlers = {
        **CONFIG_SEARCH_HANDLERS,
        **DSL_CFE_HANDLERS,
        **MISC_HANDLERS,
        **INSPECT_DATA_HANDLERS,
        **STRUCTURE_HANDLERS,
        **GENERATE_HANDLERS,
        **QUALITY_HANDLERS,
        **QUERY_HANDLERS,
    }

    handler = all_handlers.get(command)
    if handler is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Handler not found: {command}"}, ensure_ascii=False),
            )
        ]

    # Вызываем handler
    try:
        result = await handler(project, args if isinstance(args, dict) else {})

        session_manager = SessionManager(project.paths.runtime_dir)
        session = session_manager.get_session()
        session.add_tool_call(f"run_cli:{command}", arguments)
        session_manager.save()

        return result
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Command failed: {e}"}, ensure_ascii=False),
            )
        ]


# ============================================================================
# Реестр high-level handlers
# ============================================================================

HIGH_LEVEL_HANDLERS: dict[str, Any] = {
    "plan": handle_plan,
    "gather": handle_gather,
    "generate": handle_generate,
    "validate": handle_validate,
    "explain": handle_explain,
    "run_cli": handle_run_cli,
}
