"""
query.py — MCP handlers для Query Intelligence.

Phase D of Query Intelligence plan: 5 MCP tools для работы с запросами 1С.

Handlers:
- handle_generate_query: генерация запроса по описанию задачи
- handle_explain_query: объяснение что делает запрос
- handle_optimize_query: предложения по оптимизации
- handle_query_templates: список доступных шаблонов
- handle_query_workflow: мета-tool — оркестрация generate→validate→optimize
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import mcp.types as types

if TYPE_CHECKING:
    from src.project import Project


# ============================================================================
# HANDLERS
# ============================================================================


async def handle_generate_query(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Генерация запроса 1С по описанию задачи.

    Использует QueryGenerator + QueryTemplates (15 шаблонов).
    """
    from src.services.analyzers.query_generator import QueryGenerator

    task = arguments.get("task", "")
    config_name = arguments.get("config_name", "")
    object_hints = arguments.get("object_hints", [])

    if not task.strip():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "task is required"}, ensure_ascii=False),
            )
        ]

    # Загружаем metadata_index если есть
    metadata_index = _load_metadata_index(project, config_name)

    generator = QueryGenerator(metadata_index)
    result = generator.generate(task, config_name, object_hints)

    response = result.to_dict()
    response["task"] = task
    response["config_name"] = config_name

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


async def handle_explain_query(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Объяснение что делает запрос 1С.

    Использует QueryExplainer для человекочитаемого описания.
    """
    from src.services.analyzers.query_explainer import QueryExplainer

    query_text = arguments.get("query", "")
    config_name = arguments.get("config_name", "")

    if not query_text.strip():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "query is required"}, ensure_ascii=False),
            )
        ]

    metadata_index = _load_metadata_index(project, config_name)

    explainer = QueryExplainer(metadata_index)
    result = explainer.explain(query_text, config_name)

    return [
        types.TextContent(
            type="text",
            text=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        )
    ]


async def handle_optimize_query(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Предложения по оптимизации запроса 1С.

    18 правил: 10 базовых (Q001-Q010) + 8 производительности (O001-O008).
    """
    from src.services.analyzers.query_optimizer import QueryOptimizer

    query_text = arguments.get("query", "")
    config_name = arguments.get("config_name", "")

    if not query_text.strip():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "query is required"}, ensure_ascii=False),
            )
        ]

    metadata_index = _load_metadata_index(project, config_name)

    optimizer = QueryOptimizer(metadata_index)
    result = optimizer.optimize(query_text, config_name)

    return [
        types.TextContent(
            type="text",
            text=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        )
    ]


async def handle_query_templates(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Список доступных шаблонов запросов.

    Возвращает 15 шаблонов в 6 категориях.
    """
    from src.services.analyzers.query_templates import (
        ALL_TEMPLATES,
        get_templates_by_category,
        list_all_categories,
    )

    category = arguments.get("category", "")

    if category:
        templates = get_templates_by_category(category)
    else:
        templates = ALL_TEMPLATES

    response = {
        "total": len(templates),
        "categories": list_all_categories(),
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "keywords": t.keywords,
                "required_params": t.required_params,
                "optional_params": t.optional_params,
                "example": t.example,
                "pattern_ref": t.pattern_ref,
            }
            for t in templates
        ],
    }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


async def handle_query_workflow(project: Project, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Мета-tool: оркестрация generate → validate → optimize в одном вызове.

    Принимает описание задачи, генерирует запрос, валидирует, оптимизирует —
    всё в одном ответе.
    """
    from src.services.analyzers.query_generator import QueryGenerator
    from src.services.analyzers.query_explainer import QueryExplainer
    from src.services.analyzers.query_optimizer import QueryOptimizer

    task = arguments.get("task", "")
    config_name = arguments.get("config_name", "")
    object_hints = arguments.get("object_hints", [])
    auto_validate = arguments.get("auto_validate", True)
    auto_optimize = arguments.get("auto_optimize", True)

    if not task.strip():
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "task is required"}, ensure_ascii=False),
            )
        ]

    metadata_index = _load_metadata_index(project, config_name)

    workflow_steps: list[str] = []
    response: dict[str, Any] = {"task": task, "config_name": config_name}

    # Step 1: Generate
    generator = QueryGenerator(metadata_index)
    generated = generator.generate(task, config_name, object_hints)
    response["generated_query"] = generated.to_dict()
    if generated.text:
        workflow_steps.append(f"generate_query → OK (template: {generated.template_name})")
    else:
        workflow_steps.append("generate_query → WARN (no template matched)")

    # Step 2: Validate (если есть сгенерированный запрос)
    if auto_validate and generated.text:
        try:
            from src.services.analyzers.query_validator_static import StaticQueryValidator

            if metadata_index:
                validator = StaticQueryValidator(metadata_index)
                validation = validator.validate(generated.text)
                response["validation"] = validation.to_dict()
                workflow_steps.append(f"validate_query_static → {'OK' if validation.valid else 'ISSUES'} ({validation.total_errors} errors)")
            else:
                response["validation"] = {"skipped": "metadata_index not available"}
                workflow_steps.append("validate_query_static → SKIPPED (no metadata)")
        except Exception as e:
            response["validation"] = {"error": str(e)}
            workflow_steps.append(f"validate_query_static → ERROR: {e}")

    # Step 3: Optimize (если есть сгенерированный запрос)
    if auto_optimize and generated.text:
        optimizer = QueryOptimizer(metadata_index)
        optimization = optimizer.optimize(generated.text, config_name)
        response["optimization"] = optimization.to_dict()
        workflow_steps.append(f"optimize_query → {'OK' if optimization.total_issues == 0 else 'ISSUES'} ({optimization.total_issues} issues, {optimization.total_suggestions} suggestions)")

    # Step 4: Explain (что делает сгенерированный запрос)
    if generated.text:
        explainer = QueryExplainer(metadata_index)
        explanation = explainer.explain(generated.text, config_name)
        response["explanation"] = explanation.to_dict()
        workflow_steps.append("explain_query → OK")

    # Step 5: BSL code wrapper (готовый BSL код с запросом)
    if generated.text:
        bsl_code = _generate_bsl_wrapper(generated)
        response["bsl_code"] = bsl_code
        workflow_steps.append("bsl_code → OK (готовый BSL код сгенерирован)")

    response["workflow_steps"] = workflow_steps

    return [
        types.TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    ]


# ============================================================================
# HELPERS
# ============================================================================


def _load_metadata_index(project: Project, config_name: str) -> dict[str, Any]:
    """Загружает metadata_index для указанной конфигурации."""
    if not config_name:
        # Берём любую доступную
        configs_root = project.paths.derived / "configs"
        if configs_root.exists():
            for cfg_dir in sorted(configs_root.iterdir()):
                candidate = cfg_dir / "unified-metadata-index.json"
                if candidate.exists():
                    config_name = cfg_dir.name
                    break

    if not config_name:
        return {}

    metadata_path = project.paths.derived / "configs" / config_name / "unified-metadata-index.json"
    if not metadata_path.exists():
        return {}

    try:
        with open(metadata_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _generate_bsl_wrapper(generated: Any) -> str:
    """Генерирует BSL код с запросом и параметрами."""
    query_text = generated.text
    # Экранируем кавычки для BSL строки
    escaped = query_text.replace('"', '""')

    bsl = f"""// Сгенерировано 1c-ai-dev-env Query Intelligence
// Задача: {generated.explanation}
// Шаблон: {generated.template_name}

Функция ВыполнитьЗапрос() Экспорт

    Запрос = Новый Запрос;
    Запрос.Текст =
        "{escaped}";
"""

    # Добавляем установку параметров
    for param in generated.parameters:
        bsl += f'\n    // Запрос.УстановитьПараметр("{param}", <значение>);'

    bsl += """

    Результат = Запрос.Выполнить();
    Возврат Результат;

КонецФункции"""

    return bsl


# ============================================================================
# REGISTRY
# ============================================================================

QUERY_HANDLERS: dict[str, Any] = {
    "generate_query": handle_generate_query,
    "explain_query": handle_explain_query,
    "optimize_query": handle_optimize_query,
    "query_templates": handle_query_templates,
    "query_workflow": handle_query_workflow,
}
