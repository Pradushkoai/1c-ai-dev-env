"""
query.py — CLI команды для Query Intelligence.

Phase E of Query Intelligence plan: 6 CLI команд для работы с запросами 1С.

Команды:
- 1c-ai query gen <task> [--config <name>] [--output <file>]
- 1c-ai query explain [--file <path> | --text <query>] [--config <name>]
- 1c-ai query validate [--file <path> | --text <query>] --config <name>
- 1c-ai query optimize [--file <path> | --text <query>] [--config <name>]
- 1c-ai query analyze --file <path>
- 1c-ai query templates [--category <cat>] [--list]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_metadata(config_name: str) -> dict[str, Any]:
    """Загружает metadata_index для конфигурации."""
    if not config_name:
        return {}
    try:
        from src.project import Project

        project = Project()
        metadata_path = project.paths.derived / "configs" / config_name / "unified-metadata-index.json"
        if metadata_path.exists():
            with open(metadata_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _read_query(file_path: str | None, text: str | None) -> str:
    """Читает запрос из файла или текста."""
    if file_path:
        path = Path(file_path)
        if not path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8-sig", errors="replace")
    elif text:
        return text
    else:
        print("Error: Either --file or --text is required", file=sys.stderr)
        sys.exit(1)


def _print_result(data: dict[str, Any], format: str = "text") -> None:
    """Выводит результат в указанном формате."""
    if format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        # Text format — человекочитаемый
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 200:
                print(f"{key}:")
                print(value)
            elif isinstance(value, (list, dict)):
                print(f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
            else:
                print(f"{key}: {value}")


# ============================================================================
# COMMANDS
# ============================================================================


def cmd_query_gen(args) -> None:
    """1c-ai query gen <task> — генерация запроса по описанию."""
    from src.services.analyzers.query_generator import QueryGenerator

    task = args.task
    config_name = args.config or ""
    output = args.output
    fmt = args.format or "text"

    metadata_index = _load_metadata(config_name)
    generator = QueryGenerator(metadata_index)
    result = generator.generate(task, config_name)

    if output:
        # Сохраняем в файл (BSL код)
        from src.mcpserver.handlers.query import _generate_bsl_wrapper

        bsl_code = _generate_bsl_wrapper(result)
        Path(output).write_text(bsl_code, encoding="utf-8")
        print(f"Saved to: {output}")
    else:
        _print_result(result.to_dict(), fmt)


def cmd_query_explain(args) -> None:
    """1c-ai query explain — объяснение запроса."""
    from src.services.analyzers.query_explainer import QueryExplainer

    query_text = _read_query(args.file, args.text)
    config_name = args.config or ""
    fmt = args.format or "text"

    metadata_index = _load_metadata(config_name)
    explainer = QueryExplainer(metadata_index)
    result = explainer.explain(query_text, config_name)

    _print_result(result.to_dict(), fmt)


def cmd_query_validate(args) -> None:
    """1c-ai query validate — валидация запроса."""
    from src.services.analyzers.query_validator_static import StaticQueryValidator

    query_text = _read_query(args.file, args.text)
    config_name = args.config or ""
    fmt = args.format or "text"

    metadata_index = _load_metadata(config_name)
    if not metadata_index:
        print(f"Error: metadata index not found for '{config_name}'.", file=sys.stderr)
        print("Run: 1c-ai config build --name <name>", file=sys.stderr)
        sys.exit(1)

    validator = StaticQueryValidator(metadata_index)
    result = validator.validate(query_text)

    _print_result(result.to_dict(), fmt)

    if not result.valid:
        sys.exit(1)  # non-zero exit для CI


def cmd_query_optimize(args) -> None:
    """1c-ai query optimize — оптимизация запроса."""
    from src.services.analyzers.query_optimizer import QueryOptimizer

    query_text = _read_query(args.file, args.text)
    config_name = args.config or ""
    fmt = args.format or "text"

    metadata_index = _load_metadata(config_name)
    optimizer = QueryOptimizer(metadata_index)
    result = optimizer.optimize(query_text, config_name)

    _print_result(result.to_dict(), fmt)

    if result.total_issues > 0:
        sys.exit(1)  # non-zero exit для CI


def cmd_query_analyze(args) -> None:
    """1c-ai query analyze — анализ запросов в BSL файле."""
    from src.services.analyzers.query_analyzer import QueryAnalyzer

    file_path = args.file
    fmt = args.format or "text"

    if not file_path:
        print("Error: --file is required", file=sys.stderr)
        sys.exit(1)

    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    analyzer = QueryAnalyzer()
    issues = analyzer.analyze_file(path)
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

    _print_result(response, fmt)


def cmd_query_templates(args) -> None:
    """1c-ai query templates — список шаблонов запросов."""
    from src.services.analyzers.query_templates import (
        ALL_TEMPLATES,
        get_templates_by_category,
        list_all_categories,
    )

    category = args.category or ""
    fmt = args.format or "text"
    list_only = args.list

    if category:
        templates = get_templates_by_category(category)
    else:
        templates = ALL_TEMPLATES

    if list_only:
        for t in templates:
            print(f"  {t.name:30s}  {t.description}")
        print(f"\nTotal: {len(templates)} templates")
        if not category:
            print(f"Categories: {', '.join(list_all_categories())}")
    else:
        response = {
            "total": len(templates),
            "categories": list_all_categories(),
            "templates": [
                {
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "required_params": t.required_params,
                    "example": t.example,
                }
                for t in templates
            ],
        }
        _print_result(response, fmt)


# ============================================================================
# PARSER SETUP
# ============================================================================


def setup_query_parser(subparsers) -> None:
    """Настраивает subparser для команды 'query'."""
    p_query = subparsers.add_parser(
        "query",
        help="Query Intelligence: генерация, объяснение, валидация, оптимизация запросов 1С",
    )
    query_sub = p_query.add_subparsers(dest="query_command", help="Query commands")

    # query gen
    p_gen = query_sub.add_parser("gen", help="Сгенерировать запрос по описанию задачи")
    p_gen.add_argument("task", help="Описание задачи (напр. 'продажи по месяцам')")
    p_gen.add_argument("--config", default="", help="Имя конфигурации")
    p_gen.add_argument("--output", "-o", help="Сохранить BSL код в файл")
    p_gen.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_gen.set_defaults(func=cmd_query_gen)

    # query explain
    p_explain = query_sub.add_parser("explain", help="Объяснить что делает запрос")
    p_explain.add_argument("--file", help="Файл с запросом")
    p_explain.add_argument("--text", help="Текст запроса")
    p_explain.add_argument("--config", default="", help="Имя конфигурации")
    p_explain.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_explain.set_defaults(func=cmd_query_explain)

    # query validate
    p_validate = query_sub.add_parser("validate", help="Валидировать запрос по метаданным")
    p_validate.add_argument("--file", help="Файл с запросом")
    p_validate.add_argument("--text", help="Текст запроса")
    p_validate.add_argument("--config", required=True, help="Имя конфигурации")
    p_validate.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_validate.set_defaults(func=cmd_query_validate)

    # query optimize
    p_optimize = query_sub.add_parser("optimize", help="Предложения по оптимизации запроса")
    p_optimize.add_argument("--file", help="Файл с запросом")
    p_optimize.add_argument("--text", help="Текст запроса")
    p_optimize.add_argument("--config", default="", help="Имя конфигурации")
    p_optimize.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_optimize.set_defaults(func=cmd_query_optimize)

    # query analyze
    p_analyze = query_sub.add_parser("analyze", help="Анализ запросов в BSL файле")
    p_analyze.add_argument("--file", required=True, help="BSL файл для анализа")
    p_analyze.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_analyze.set_defaults(func=cmd_query_analyze)

    # query templates
    p_templates = query_sub.add_parser("templates", help="Список шаблонов запросов")
    p_templates.add_argument("--category", default="", help="Категория (basic, virtual_tables, batch, analytics, catalogs, documents)")
    p_templates.add_argument("--list", "-l", action="store_true", help="Только список имён")
    p_templates.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Формат вывода")
    p_templates.set_defaults(func=cmd_query_templates)
