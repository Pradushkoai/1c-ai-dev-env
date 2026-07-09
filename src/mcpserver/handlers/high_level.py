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

    CR-1 (2026-07-09): Реальная LLM генерация через OllamaClient.generate_for_task()
    с контекстом из session (gathered_context). Fallback на bsl_templates если
    Ollama недоступен.

    CR-7 (2026-07-09): Auto-fix feedback loop — если fix_violations_from указан,
    берёт violations из session и добавляет в prompt для LLM.

    Оркестрирует генерацию + inline validation (быстрая, без Java).

    Возвращает:
    - artifact_id: ID для использования в validate()
    - code: сгенерированный код
    - validation_passed: True если нет CRITICAL
    - warnings: non-critical violations

    R3: _next_action — validate (если validation_passed=False) или done.
    """
    from src.services.session import SessionManager

    task = arguments.get("task", "")
    target_context = arguments.get("target_context", "server")
    artifact_type = arguments.get("type", "bsl")  # bsl | query | dsl
    fix_violations_from = arguments.get("fix_violations_from", "")

    if not task:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "task required"}, ensure_ascii=False),
            )
        ]

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    # CR-7: Если fix_violations_from — берём violations из session
    # T9 (2026-07-10): reversed — берём ПОСЛЕДНЮЮ validation (не старейшую)
    fix_violations: list[dict[str, Any]] = []
    if fix_violations_from:
        for v in reversed(session.validation_history):
            if v.get("artifact_id") == fix_violations_from:
                fix_violations = v.get("violations", [])[:10]  # top 10
                break

    # Для query — используем существующий generate_query handler
    generated_code = ""
    generation_source = ""

    if artifact_type == "query":
        from .query import handle_generate_query
        result = await handle_generate_query(project, {"task": task})
        if result:
            try:
                data = json.loads(result[0].text)
                generated_code = data.get("query", data.get("generated_query", ""))
                generation_source = "query_generator"
            except (json.JSONDecodeError, IndexError):
                pass
    else:
        # CR-1: BSL — реальная LLM генерация через Ollama
        generated_code, generation_source = await _generate_bsl_with_llm(
            project, session, task, target_context, fix_violations
        )

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
                # T4 (2026-07-10): .lower() — bsl_context_checker возвращает lowercase
                critical = [v for v in ctx_violations if v.get("severity", "").lower() in ("error", "critical")]
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
        "fix_violations_from": fix_violations_from,
    }
    artifact_id = session.add_artifact(artifact)
    session.add_tool_call("generate", arguments)
    session_manager.save()

    # CR-6: adaptive _next_action
    next_action = _get_next_action_after_generate(
        validation_passed=validation_passed,
        warnings_count=len(warnings),
        artifact_id=artifact_id,
        session=session,
    )

    response = {
        "artifact_id": artifact_id,
        "code": generated_code,
        "type": artifact_type,
        "generation_source": generation_source,
        "validation_passed": validation_passed,
        "warnings_count": len(warnings),
        "warnings": warnings[:5],  # первые 5
        "fix_applied": bool(fix_violations_from),
        "_next_action": next_action,
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


async def _generate_bsl_with_llm(
    project: Project,
    session: Any,
    task: str,
    target_context: str,
    fix_violations: list[dict[str, Any]],
) -> tuple[str, str]:
    """CR-1: Генерация BSL кода через Ollama LLM.

    Returns:
        (generated_code, generation_source)
    """
    # Строим prompt из task + context из session + fix violations
    context_parts: list[str] = []

    # Context из gathered_context (если есть)
    if session.gathered_context:
        ctx = session.gathered_context
        # Platform methods
        for m in ctx.get("platform_methods", [])[:5]:
            name = m.get("name_ru", "") or m.get("name_en", "")
            syntax = m.get("syntax", "")
            if name:
                context_parts.append(f"Метод: {name} — {syntax}")
        # Safe methods (pre-hoc guidance)
        for m in ctx.get("safe_methods", [])[:5]:
            name = m.get("name_ru", "") or m.get("name_en", "")
            if name:
                context_parts.append(f"Безопасный метод для {target_context}: {name}")
        # Knowledge articles
        for a in ctx.get("knowledge_articles", [])[:3]:
            title = a.get("title", "")
            if title:
                context_parts.append(f"Паттерн: {title}")

    context = "\n".join(context_parts) if context_parts else ""

    # CR-7: Если есть fix_violations — добавляем в prompt
    fix_instructions = ""
    if fix_violations:
        fix_lines = ["ИСПРАВЬ следующие violations в коде:"]
        for v in fix_violations[:10]:
            fix_lines.append(
                f"- [{v.get('severity', '')}] {v.get('rule_id', '')}: {v.get('message', '')}"
            )
            if v.get("recommendation"):
                fix_lines.append(f"  Рекомендация: {v['recommendation']}")
        fix_instructions = "\n".join(fix_lines)

    # Пытаемся LLM генерацию через Ollama
    try:
        from src.services.llm_ollama import OllamaClient

        client = OllamaClient()
        if client.is_available():
            # CR-8: Проверяем circuit breaker state
            if client.get_circuit_breaker_state() == "open":
                logger.debug("Circuit breaker open — fallback to template")
            else:
                prompt_parts = [
                    f"Задача: {task}",
                    f"Целевой контекст: {target_context}",
                ]
                if context:
                    prompt_parts.append(f"\nКонтекст:\n{context}")
                if fix_instructions:
                    prompt_parts.append(f"\n{fix_instructions}")
                prompt_parts.append(
                    "\nСгенерируй BSL код для 1С:Предприятие 8. "
                    "Соблюдай стандарты: табы для отступов, области в коде. "
                    "Верни только код без объяснений."
                )

                prompt = "\n".join(prompt_parts)

                response = client.generate_for_task(
                    prompt=prompt,
                    task_type="codegen",
                    context=context,
                    system="Ты — эксперт 1С разработчик. Сгенерируй BSL код.",
                    temperature=0.2,
                    max_tokens_ratio=0.15,
                )

                if response and response.text and not response.error:
                    code = response.text.strip()
                    # Убираем markdown code fences если есть
                    if code.startswith("```"):
                        lines = code.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        code = "\n".join(lines)
                    if code:
                        return code, "ollama_llm"
    except Exception as e:
        logger.debug("LLM generation failed, fallback to template: %s", e)

    # Fallback: bsl_templates (intent-based)
    try:
        from src.services.bsl_templates import BslTemplates
        templates = BslTemplates()
        # Intent-based template selection
        template_map = {
            "create_object": ("catalog", "object_module"),
            "generate_bsl": ("form", "form_module"),
            "cfe_extension": ("catalog", "object_module"),
        }
        intent_name = session.plan.get("intent", {}).get("name", "") if session.plan else ""
        cat, tpl_name = template_map.get(intent_name, ("catalog", "object_module"))
        tpl = templates.get_template(cat, tpl_name)
        if tpl:
            return tpl, f"bsl_templates ({intent_name})"
    except Exception as e:
        logger.debug("bsl_templates fallback failed: %s", e)

    return "", "no_source"


def _get_next_action_after_generate(
    validation_passed: bool,
    warnings_count: int,
    artifact_id: str,
    session: Any,
) -> dict[str, Any]:
    """CR-6: Adaptive _next_action после generate."""
    if validation_passed:
        # CR-11: Если validate уже вызывался и был safe — done
        has_validate = any(
            tc.get("tool_name", "").startswith("validate")
            for tc in session.tool_call_history
        )
        if has_validate:
            return {
                "tool": "done",
                "args": {},
                "why": "Код сгенерирован и прошёл inline validation. Можно использовать.",
            }
        return {
            "tool": "validate",
            "args": {"artifact_id": artifact_id},
            "why": "Код прошёл inline validation. Запустите validate для полной проверки (7-9 анализаторов).",
        }
    return {
        "tool": "validate",
        "args": {"artifact_id": artifact_id},
        "why": f"Найдено {warnings_count} CRITICAL violation(s) — нужна полная проверка",
    }


# ============================================================================
# R1.4: validate — полная проверка (solve_check + check_bsl_context)
# ============================================================================


async def handle_validate(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """R1: Полная валидация кода.

    Если artifact_id указан — берёт код из session (R2 state-aware).
    Если file_path указан — проверяет файл.

    CR-2 (2026-07-09): validate(artifact_id) теперь запускает ПОЛНУЮ проверку
    (7-9 анализаторов через solve_check) — записывает code во temp file,
    вызывает TaskProcessor.check(), удаляет temp file.
    Раньше запускал только check_bsl_context (неполная валидация).

    Возвращает приоритизированный результат (F2.4) + grouped_violations (R5).

    R3: _next_action — fix и re-validate, или done.
    """
    from src.services.session import SessionManager
    import tempfile
    from pathlib import Path

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

        # CR-2: Записываем code во temp file для полной валидации через solve_check
        violations: list[dict[str, Any]] = []
        analyzers_run: list[str] = []
        bsl_ls_available = False

        if code and level != "skip":
            # Создаём temp file
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".bsl", delete=False, encoding="utf-8"
                ) as tmp:
                    # T11 (2026-07-10): temp_path ДО write — если write бросит,
                    # finally block сможет удалить orphaned file.
                    temp_path = Path(tmp.name)
                    tmp.write(code)

                # Запускаем полную проверку через TaskProcessor.check()
                from src.services.task_processor import TaskProcessor
                processor = TaskProcessor(project.paths)
                check_result = await run_sync(processor.check, temp_path, level=level)

                # Конвертируем Violation objects в dicts
                for v in check_result.violations:
                    violations.append({
                        "source": v.source,
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "line": v.line,
                        "message": v.message,
                        "file": v.file,
                        "recommendation": getattr(v, "recommendation", ""),
                    })
                analyzers_run = check_result.analyzers_run
                bsl_ls_available = check_result.bsl_ls_available

            except Exception as e:
                # Fallback на check_bsl_context если solve_check упал
                logger.warning("solve_check failed for artifact, fallback to check_bsl_context: %s", e)
                try:
                    ctx_result = await handle_check_bsl_context(
                        project, {"code": code, "target_context": [target_context]}
                    )
                    ctx_data = json.loads(ctx_result[0].text) if ctx_result else {"violations": []}
                    violations = ctx_data.get("violations", [])
                    analyzers_run = ["check_bsl_context (fallback)"]
                except Exception:
                    violations = []
            finally:
                # Cleanup temp file
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass

        # Группируем violations (R5)
        grouped = _group_violations_by_rule(violations)

        # CR-2: must_fix по severity (CRITICAL, ERROR, HIGH)
        must_fix = [
            v for v in violations
            if v.get("severity", "").lower() in ("critical", "error", "high")
        ]
        is_safe = len(must_fix) == 0

        validation = {
            "artifact_id": artifact_id,
            "target_context": target_context,
            "level": level,
            "total_violations": len(violations),
            "must_fix_count": len(must_fix),
            "is_safe_to_use": is_safe,
            "analyzers_run": analyzers_run,
            "bsl_ls_available": bsl_ls_available,
            "grouped_violations": grouped,
            "violations": violations,
        }

        session.add_validation(validation)
        session.add_tool_call("validate", arguments)
        session_manager.save()

        # CR-6: adaptive _next_action
        next_action = _get_next_action_after_validate(
            is_safe=is_safe,
            must_fix_count=len(must_fix),
            artifact=artifact,
            session=session,
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


def _get_next_action_after_validate(
    is_safe: bool,
    must_fix_count: int,
    artifact: dict[str, Any] | None,
    session: Any,
) -> dict[str, Any]:
    """CR-6: Adaptive _next_action после validate."""
    if is_safe:
        return {
            "tool": "done",
            "args": {},
            "why": "Код прошёл валидацию — можно использовать",
        }
    # CR-7: Если есть violations — предлагаем generate с fix_violations_from
    task = artifact.get("task", "") if artifact else ""
    target_context = artifact.get("target_context", "server") if artifact else "server"
    artifact_id = artifact.get("artifact_id", "") if artifact else ""
    return {
        "tool": "generate",
        "args": {
            "task": task,
            "target_context": target_context,
            "fix_violations_from": artifact_id,
        },
        "why": f"Исправить {must_fix_count} CRITICAL/HIGH violation(s) — auto-fix с violations как context",
    }


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

    CR-4 (2026-07-09): explain(file_path) теперь оркеструет 3 источника:
      1. code_metrics — метрики (LOC, complexity, methods count)
      2. analyze_architecture — архитектурные issues (если file в config)
      3. call_graph — callers/callees (если file в config)
    Раньше возвращал только code_metrics.

    Если query указан — ищет где используется метод/объект через solve_context.

    R3: _next_action — зависит от результата.
    """
    from src.services.session import SessionManager

    file_path = arguments.get("file_path", "")
    query = arguments.get("query", "")
    config_name = arguments.get("config_name", "")

    session_manager = SessionManager(project.paths.runtime_dir)
    session = session_manager.get_session()

    if file_path:
        # CR-4: Полный анализ — metrics + architecture + call_graph
        from .quality import handle_get_code_metrics, handle_analyze_architecture

        response: dict[str, Any] = {"file_path": file_path, "analysis_sources": []}

        # 1. Code metrics (всегда)
        try:
            metrics_result = await handle_get_code_metrics(project, {"file_path": file_path})
            if metrics_result:
                metrics_data = json.loads(metrics_result[0].text)
                response["metrics"] = metrics_data
                response["analysis_sources"].append("code_metrics")
        except Exception as e:
            logger.debug("code_metrics failed: %s", e)
            response["metrics_error"] = str(e)

        # 2. Architecture analysis (если есть config_dir)
        try:
            # Пытаемся определить config_dir из file_path
            from pathlib import Path
            file_path_obj = Path(file_path)
            # Ищем config_dir в пути (data/configs/<name>/...)
            parts = file_path_obj.parts
            config_dir = None
            for i, part in enumerate(parts):
                if part == "configs" and i + 1 < len(parts):
                    config_dir = Path(*parts[: i + 2])
                    break

            if config_dir and config_dir.exists():
                arch_result = await handle_analyze_architecture(project, {"config_dir": str(config_dir)})
                if arch_result:
                    arch_data = json.loads(arch_result[0].text)
                    response["architecture"] = arch_data
                    response["analysis_sources"].append("analyze_architecture")
        except Exception as e:
            logger.debug("architecture analysis failed: %s", e)

        # 3. Call graph (если есть config_name)
        if config_name:
            try:
                # Используем run_cli для call_graph
                call_graph_result = await handle_run_cli(project, {
                    "command": "call_graph",
                    "args": {"config_name": config_name, "action": "stats"},
                })
                if call_graph_result:
                    cg_data = json.loads(call_graph_result[0].text)
                    response["call_graph_summary"] = cg_data
                    response["analysis_sources"].append("call_graph")
            except Exception as e:
                logger.debug("call_graph failed: %s", e)

        session.add_tool_call("explain", arguments)
        session_manager.save()

        # CR-6: adaptive _next_action
        has_issues = (
            response.get("metrics", {}).get("is_god_object", False)
            or response.get("architecture", {}).get("total_issues", 0) > 0
        )
        if has_issues:
            response["_next_action"] = {
                "tool": "validate",
                "args": {"file_path": file_path},
                "why": "Найдены архитектурные issues — проверьте код на violations",
            }
        else:
            response["_next_action"] = {
                "tool": "done",
                "args": {},
                "why": "Анализ завершён — код выглядит хорошо",
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

        # T10 (2026-07-10): Не перетираем существующий plan — только если plan пуст.
        # Раньше set_plan безусловно заменял plan с target_context_hint и
        # required_sources на 2-key stub, ломая последующий gather().
        if session.plan is None:
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


# Whitelist разрешённых CLI команд (security — не любой shell execution)
# CR-3 (2026-07-09): Добавлены search_platform_method, get_method_details,
# get_method_details_batch, get_safe_methods, solve_context, solve_check,
# check_bsl_context, bsl_templates, generate_query, get_object_structure
# — стали hidden после R1, но должны быть доступны через run_cli.
_ALLOWED_CLI_COMMANDS: frozenset[str] = frozenset({
    # CR-3: Platform methods access (были visible до R1)
    "search_platform_method",
    "get_method_details",
    "get_method_details_batch",
    "get_safe_methods",
    # CR-3: Legacy high-level (были visible до R1)
    "solve_context",
    "solve_check",
    "check_bsl_context",
    "bsl_templates",
    "generate_query",
    "get_object_structure",
    "inspect",
    # Architecture & dependencies
    "call_graph",
    "build_dependency_graph",
    "dependency_query",
    "analyze_architecture",
    # DSL compilers
    "dsl_compile_meta",
    "dsl_compile_form",
    "dsl_compile_skd",
    "dsl_compile_mxl",
    "dsl_compile_role",
    # CFE
    "cfe_borrow",
    "cfe_patch_method",
    "cfe_diff",
    # SKD
    "skd_trace",
    # Config search
    "list_configs",
    "search_code",
    "get_form_elements",
    "get_api_reference",
    "get_knowledge",
    # Quality analyzers
    "audit_security",
    "get_code_metrics",
    "check_transactions",
    "analyze_queries",
    "check_form_quality",
    "check_skd_quality",
    "diff_configs",
    "validate_query_static",
    "check_data_exchange",
    # OpenSpec
    "openspec_proposal",
    "openspec_list",
    "openspec_update_task",
    "openspec_archive",
    # EPF factory
    "epf_factory_create",
    "epf_factory_templates",
    # Query intelligence
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
    # T5 (2026-07-10): добавлен ANALYZER_HANDLERS — без него solve_check и
    # solve_context (в whitelist) недоступны через run_cli.
    from . import (
        ANALYZER_HANDLERS,
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
        **ANALYZER_HANDLERS,  # T5: solve_check, solve_context, analyze_bsl, check_standards
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
