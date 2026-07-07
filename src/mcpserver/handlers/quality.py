"""
quality.py — handlers для анализаторов качества, безопасности и аудита.

P2.2: вынесено из mcp_server.py (группа 8).
Handlers: get_knowledge, audit_security, get_code_metrics, check_transactions,
          analyze_queries, analyze_architecture, check_form_quality,
          check_skd_quality, diff_configs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

import mcp.types as types

from ._security import resolve_path_within_project

if TYPE_CHECKING:
    from src.project import Project


async def handle_get_knowledge(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: get_knowledge."""
    query = arguments.get("query", "")
    item_id = arguments.get("item_id", "")
    category = arguments.get("category", "")

    try:
        from src.services.knowledge_base import KnowledgeBase

        kb = KnowledgeBase()

        # Если item_id указан — возвращаем полный текст
        if item_id:
            item = kb.get_item(item_id)
            if item:
                return [types.TextContent(type="text", text=json.dumps(item, ensure_ascii=False, indent=2))]
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"Item not found: {item_id}"}, ensure_ascii=False),
                    )
                ]

        # Если query указан — поиск
        if query:
            results = kb.search(query, category=category if category else None, limit=20)
            response = {
                "query": query,
                "category": category or "all",
                "total_results": len(results),
                "results": results,
            }
            return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]

        # Если ничего не указано — список всех
        items = kb.list_all()
        response = {
            "stats": kb.get_stats(),
            "items": items,
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"Knowledge base error: {str(e)}"}, ensure_ascii=False)
            )
        ]


async def handle_audit_security(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: audit_security."""
    file_path = arguments.get("file_path", "")

    if not file_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "file_path is required"}, ensure_ascii=False))]

    # P1.8: path traversal protection — резолвим и проверяем что путь внутри проекта.
    resolved = resolve_path_within_project(file_path, project)
    if resolved is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    file_path = str(resolved)

    if not os.path.exists(file_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)
            )
        ]

    # Этап 1.2, Группа 1e: dynamic import заменён на прямой импорт из src.services.analyzers
    from src.services.analyzers.security_auditor import SecurityAuditor

    try:
        auditor = SecurityAuditor()
        violations = auditor.audit_file(Path(file_path))
        stats = auditor.get_stats(violations)

        response = {
            "file_path": file_path,
            "total_violations": stats["total_violations"],
            "by_severity": stats["by_severity"],
            "critical_count": stats["critical_count"],
            "high_count": stats["high_count"],
            "medium_count": stats["medium_count"],
            "low_count": stats["low_count"],
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "line": v.line,
                    "message": v.message,
                    "recommendation": v.recommendation,
                }
                for v in violations
            ],
        }
        # Tool chaining hints
        if violations:
            critical = [v for v in violations if v.severity in ("CRITICAL", "HIGH")]
            if critical:
                response["_next_steps"] = [
                    "Исправьте CRITICAL/HIGH нарушения перед использованием кода",
                    "check_standards(file_path='<тот_же_файл>') — проверка стандартов 1С",
                    "bsl_templates — используйте безопасные шаблоны (SEC001: параметризованные запросы)",
                ]
            else:
                response["_next_steps"] = [
                    "check_standards(file_path='<тот_же_файл>') — полная проверка стандартов 1С",
                    "code_sandbox — проверка кода в sandbox перед выполнением",
                ]
        else:
            response["_next_steps"] = [
                "check_standards(file_path='<тот_же_файл>') — проверка стандартов 1С",
                "Код безопасен — можно использовать",
            ]
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Audit failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_get_code_metrics(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: get_code_metrics."""
    file_path = arguments.get("file_path", "")

    if not file_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "file_path is required"}, ensure_ascii=False))]

    # P1.8: path traversal protection
    resolved = resolve_path_within_project(file_path, project)
    if resolved is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    file_path = str(resolved)

    if not os.path.exists(file_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)
            )
        ]

    # Этап 1.2, Группа 1c: dynamic import заменён на прямой импорт из src.services.analyzers
    from src.services.analyzers.code_metrics import CodeMetricsAnalyzer

    try:
        analyzer = CodeMetricsAnalyzer()
        metrics = analyzer.analyze_file(Path(file_path))

        response = {
            "file_path": file_path,
            "total_lines": metrics.total_lines,
            "code_lines": metrics.code_lines,
            "comment_lines": metrics.comment_lines,
            "blank_lines": metrics.blank_lines,
            "procedures_count": metrics.procedures_count,
            "functions_count": metrics.functions_count,
            "export_count": metrics.export_count,
            "total_cyclomatic": metrics.total_cyclomatic,
            "avg_cyclomatic": round(metrics.avg_cyclomatic, 2),
            "max_cyclomatic": metrics.max_cyclomatic,
            "total_cognitive": metrics.total_cognitive,
            "max_cognitive": metrics.max_cognitive,
            "max_nesting": metrics.max_nesting,
            "duplicate_blocks": metrics.duplicate_blocks,
            "duplicate_lines": metrics.duplicate_lines,
            "is_god_object": metrics.is_god_object,
            "long_methods_count": len(metrics.long_methods),
            "too_many_params_count": len(metrics.too_many_params),
            "technical_debt_minutes": metrics.technical_debt_minutes,
            "health_score": round(metrics.health_score, 1),
            "issues": metrics.issues,
            "methods": [
                {
                    "name": m.name,
                    "type": m.method_type,
                    "loc": m.loc,
                    "lloc": m.lloc,
                    "cyclomatic": m.cyclomatic_complexity,
                    "cognitive": m.cognitive_complexity,
                    "nesting": m.max_nesting_depth,
                    "params": m.param_count,
                    "export": m.is_export,
                }
                for m in metrics.methods[:20]  # первые 20 методов
            ],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Metrics failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_check_transactions(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: check_transactions.

    Проверка транзакций BSL: несбалансированные, без Try/Catch, интерактив в транзакции.
    """
    file_path = arguments.get("file_path", "")
    if not file_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "file_path required"}, ensure_ascii=False))]
    # P1.8: path traversal protection
    resolved = resolve_path_within_project(file_path, project)
    if resolved is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    file_path = str(resolved)
    if not os.path.exists(file_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)
            )
        ]

    # Этап 1.2, Группа 1b: dynamic import заменён на прямые импорты
    from src.services.analyzers.transaction_checker import TransactionChecker

    try:
        checker = TransactionChecker()
        violations = checker.check_file(Path(file_path))
        stats = checker.get_stats(violations)
        response = {
            "file_path": file_path,
            "total_violations": stats["total"],
            "by_severity": stats["by_severity"],
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "line": v.line,
                    "message": v.message,
                    "recommendation": v.recommendation,
                }
                for v in violations
            ],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Analysis failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_analyze_queries(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: analyze_queries.

    Phase A.1: разделён с check_transactions. Анализ запросов 1С в BSL коде —
    10 эвристик (SELECT *, LIKE %, функции в WHERE, JOIN без ON, и т.д.).

    Использует QueryAnalyzer (regex-based) с опциональным SDBL AST fallback.
    """
    file_path = arguments.get("file_path", "")
    if not file_path:
        return [types.TextContent(type="text", text=json.dumps({"error": "file_path required"}, ensure_ascii=False))]
    # P1.8: path traversal protection
    resolved = resolve_path_within_project(file_path, project)
    if resolved is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    file_path = str(resolved)
    if not os.path.exists(file_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)
            )
        ]

    from src.services.analyzers.query_analyzer import QueryAnalyzer

    try:
        analyzer = QueryAnalyzer()
        issues = analyzer.analyze_file(Path(file_path))
        stats = analyzer.get_stats(issues)
        response = {
            "file_path": file_path,
            "total_issues": stats["total"],
            "by_severity": stats["by_severity"],
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "severity": i.severity,
                    "line": i.line,
                    "message": i.message,
                    "recommendation": i.recommendation,
                }
                for i in issues
            ],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Analysis failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_analyze_architecture(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: analyze_architecture."""
    config_dir = arguments.get("config_dir", "")
    if not config_dir:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_dir required"}, ensure_ascii=False))]
    # P1.8: path traversal protection
    resolved = resolve_path_within_project(config_dir, project)
    if resolved is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    config_dir = str(resolved)
    if not os.path.exists(config_dir):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Directory not found: {config_dir}"}, ensure_ascii=False),
            )
        ]

    # Этап 1.2, Группа 1d: dynamic import заменён на прямой импорт из src.services.analyzers
    from src.services.analyzers.architecture_analyzer import ArchitectureAnalyzer

    try:
        analyzer = ArchitectureAnalyzer()
        issues, modules = analyzer.analyze_config(Path(config_dir))
        stats = analyzer.get_stats(issues)
        response = {
            "config_dir": config_dir,
            "total_modules": len(modules),
            "total_issues": stats["total_issues"],
            "by_severity": stats["by_severity"],
            "by_rule": stats["by_rule"],
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "severity": i.severity,
                    "module": i.module,
                    "line": i.line,
                    "message": i.message,
                }
                for i in issues[:50]
            ],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Analysis failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_check_form_quality(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: check_form_quality, check_skd_quality."""
    config_name = arguments.get("config_name", "")
    if not config_name:
        return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

    # Этап 1.2, Группа 1a: dynamic import заменён на прямой импорт из src.services.analyzers
    from src.services.analyzers.form_quality_checker import FormQualityChecker

    if True:  # check_form_quality
        index_path = project.paths.root / "derived" / "configs" / config_name / "form-index.json"
        checker_class = FormQualityChecker
    else:  # check_skd_quality — заглушка (P3 split), не вызывается
        from src.services.analyzers.skd_quality_checker import SKDQualityChecker

        index_path = project.paths.root / "derived" / "configs" / config_name / "skd-index.json"
        checker_class = SKDQualityChecker

    if not index_path.exists():
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"Index not found: {index_path}"}, ensure_ascii=False)
            )
        ]

    try:
        checker = checker_class()
        issues = (
            checker.check_form_index(index_path)
            if True  # check_form_quality
            else checker.check_skd_index(index_path)
        )
        stats = checker.get_stats(issues)
        response = {
            "config_name": config_name,
            "total_issues": stats["total"],
            "by_severity": stats["by_severity"],
            "by_rule": stats["by_rule"],
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "severity": i.severity,
                    "form_name": getattr(i, "form_name", getattr(i, "schema_name", "")),
                    "message": i.message,
                }
                for i in issues[:50]
            ],
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Check failed: {str(e)}"}, ensure_ascii=False))
        ]


async def handle_diff_configs(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handler для MCP tool: diff_configs."""
    old_path = arguments.get("old_path", "")
    new_path = arguments.get("new_path", "")
    if not old_path or not new_path:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": "old_path and new_path required"}, ensure_ascii=False)
            )
        ]
    # P1.8: path traversal protection for BOTH old_path and new_path
    resolved_old = resolve_path_within_project(old_path, project)
    resolved_new = resolve_path_within_project(new_path, project)
    if resolved_old is None or resolved_new is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Path outside project root — possible path traversal attempt"},
                    ensure_ascii=False,
                ),
            )
        ]
    old_path = str(resolved_old)
    new_path = str(resolved_new)
    if not os.path.exists(old_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"Old index not found: {old_path}"}, ensure_ascii=False)
            )
        ]
    if not os.path.exists(new_path):
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": f"New index not found: {new_path}"}, ensure_ascii=False)
            )
        ]

    # Этап 1.2, Группа 3: dynamic import заменён на прямой импорт из src.services.diff
    from src.services.diff import DiffAnalyzer

    try:
        analyzer = DiffAnalyzer()
        diff = analyzer.compare(Path(old_path), Path(new_path))
        response = {
            "summary": diff.summary,
            "added_objects": [{"type": c.object_type, "name": c.object_name} for c in diff.added_objects[:50]],
            "removed_objects": [{"type": c.object_type, "name": c.object_name} for c in diff.removed_objects[:50]],
            "modified_objects": [
                {"type": c.object_type, "name": c.object_name, "details": c.details} for c in diff.modified_objects[:50]
            ],
            "added_roles": diff.added_roles,
            "removed_roles": diff.removed_roles,
            "added_subsystems": diff.added_subsystems,
            "removed_subsystems": diff.removed_subsystems,
            "added_event_subscriptions": diff.added_event_subscriptions,
            "removed_event_subscriptions": diff.removed_event_subscriptions,
            "added_scheduled_jobs": diff.added_scheduled_jobs,
            "removed_scheduled_jobs": diff.removed_scheduled_jobs,
        }
        return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [
            types.TextContent(type="text", text=json.dumps({"error": f"Diff failed: {str(e)}"}, ensure_ascii=False))
        ]


# ─── P1.5: Статический валидатор запросов ───


async def handle_validate_query_static(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Валидация ИЛИ объяснение запроса 1С по метаданным (без живой базы).

    mode=validate (по умолчанию): проверка существования таблиц и полей,
    доступность виртуальных таблиц, типы в агрегатных функциях.
    mode=explain: человекочитаемое описание что делает запрос.
    """
    query_text = arguments.get("query", "")
    config_name = arguments.get("config_name", "")
    mode = arguments.get("mode", "validate")  # validate | explain

    if not query_text.strip():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "query is required"}, ensure_ascii=False),
            )
        ]

    # Mode: explain — человекочитаемое описание запроса
    if mode == "explain":
        from src.services.analyzers.query_explainer import QueryExplainer

        # Загружаем metadata для enriched объяснения
        metadata_index: dict[str, Any] = {}
        configs_root = project.paths.derived / "configs"
        if config_name:
            candidate = configs_root / config_name / "unified-metadata-index.json"
            if candidate.exists():
                try:
                    with open(candidate, encoding="utf-8") as f:
                        metadata_index = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
        elif configs_root.exists():
            for cfg_dir in sorted(configs_root.iterdir()):
                candidate = cfg_dir / "unified-metadata-index.json"
                if candidate.exists():
                    try:
                        with open(candidate, encoding="utf-8") as f:
                            metadata_index = json.load(f)
                        config_name = cfg_dir.name
                    except (json.JSONDecodeError, OSError):
                        pass
                    break

        explainer = QueryExplainer(metadata_index)
        result = explainer.explain(query_text, config_name)
        response = result.to_dict()
        response["config_name"] = config_name
        return [
            types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )
        ]

    # Mode: validate (по умолчанию)
    # Ищем metadata index для указанной (или любой) конфигурации
    metadata_path = None
    configs_root = project.paths.derived / "configs"
    if config_name:
        candidate = configs_root / config_name / "unified-metadata-index.json"
        if candidate.exists():
            metadata_path = candidate
    else:
        if configs_root.exists():
            for cfg_dir in sorted(configs_root.iterdir()):
                candidate = cfg_dir / "unified-metadata-index.json"
                if candidate.exists():
                    metadata_path = candidate
                    break

    if metadata_path is None:
        available: list[str] = []
        if configs_root.exists():
            available = [
                d.name
                for d in configs_root.iterdir()
                if (d / "unified-metadata-index.json").exists()
            ]
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "metadata index not found",
                        "hint": "Run: 1c-ai config build --name <name>",
                        "config_name": config_name,
                        "available_configs": available,
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    try:
        from src.services.analyzers.query_validator_static import StaticQueryValidator

        validator = StaticQueryValidator.from_metadata_file(metadata_path)
        result = validator.validate(query_text)
        response = result.to_dict()
        response["metadata_file"] = str(metadata_path)
        response["config_name"] = config_name or metadata_path.parent.name
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
                text=json.dumps(
                    {"error": f"Validation failed: {str(e)}"},
                    ensure_ascii=False,
                ),
            )
        ]


# Реестр handlers
QUALITY_HANDLERS: dict[str, Any] = {
    "get_knowledge": handle_get_knowledge,
    "audit_security": handle_audit_security,
    "get_code_metrics": handle_get_code_metrics,
    "check_transactions": handle_check_transactions,
    "analyze_queries": handle_analyze_queries,  # Phase A.1: разделён с check_transactions
    "analyze_architecture": handle_analyze_architecture,
    "check_form_quality": handle_check_form_quality,
    "check_skd_quality": handle_check_form_quality,  # P3: split into separate handler
    "diff_configs": handle_diff_configs,
    "validate_query_static": handle_validate_query_static,  # P1.5: статический валидатор запросов
}
