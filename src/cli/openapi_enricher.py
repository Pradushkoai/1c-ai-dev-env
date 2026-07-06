"""
M7 (2026-07-06): OpenAPI improvements — A-2, A-3, A-4.

A-2: Response schemas в OpenAPI — добавить components/schemas
A-3: Examples в OpenAPI — добавить examples в request/response
A-4: Tags в OpenAPI — категоризация tools

Скрипт enrich_openapi.py:
1. Читает docs/mcp-openapi.json
2. Добавляет components/schemas (response models)
3. Добавляет examples для request/response
4. Добавляет tags по категориям (Analyzers, Search, EPF, CFE, etc.)
5. Сохраняет обновлённый spec

Использование:
    python -m src.cli.openapi_enricher
    python -m src.cli.openapi_enricher --input spec.json --output enriched.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ============================================================================
# Tag categories (A-4)
# ============================================================================

TOOL_CATEGORIES: dict[str, list[str]] = {
    "Analyzers": [
        "analyze_architecture", "audit_security", "check_transactions",
        "diff_configs", "get_code_metrics",
    ],
    "Search": [
        "search_1c_methods", "search_code", "search_hybrid",
        "build_api_reference",
    ],
    "EPF": [
        "create_epf", "validate_bsl", "inspect_epf",
    ],
    "CFE": [
        "borrow_object", "patch_method", "diff_cfe",
    ],
    "Inspect": [
        "inspect_cf", "inspect_form", "inspect_meta", "inspect_mxl",
        "inspect_role", "inspect_skd", "inspect_subsystem",
    ],
    "DSL": [
        "compile_dsl", "round_trip_dsl",
    ],
    "Config": [
        "list_configs", "build_config_index", "get_config_stats",
    ],
    "Misc": [
        "get_help", "get_version", "check_health",
    ],
}


# ============================================================================
# Response schemas (A-2)
# ============================================================================

RESPONSE_SCHEMAS: dict[str, dict[str, Any]] = {
    "ErrorResponse": {
        "type": "object",
        "properties": {
            "error": {"type": "string"},
            "error_type": {"type": "string"},
            "details": {"type": "string"},
        },
        "required": ["error"],
    },
    "SearchResult": {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "name_ru": {"type": "string"},
            "name_en": {"type": "string"},
            "syntax": {"type": "string"},
            "description": {"type": "string"},
            "context": {"type": "string"},
        },
    },
    "AnalysisResult": {
        "type": "object",
        "properties": {
            "rule_id": {"type": "string"},
            "severity": {"type": "string"},
            "line": {"type": "integer"},
            "message": {"type": "string"},
            "recommendation": {"type": "string"},
        },
    },
    "EpfCreationResult": {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "epf_path": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "name": {"type": "string"},
        },
    },
    "StatsResult": {
        "type": "object",
        "properties": {
            "total": {"type": "integer"},
            "by_category": {"type": "object"},
            "duration_ms": {"type": "number"},
        },
    },
}


# ============================================================================
# Examples (A-3)
# ============================================================================

EXAMPLES: dict[str, dict[str, Any]] = {
    "search_request": {
        "summary": "Search request example",
        "value": {"query": "найти элемент по коду", "limit": 10},
    },
    "search_response": {
        "summary": "Search response example",
        "value": [
            {
                "score": 0.95,
                "name_ru": "НайтиПоКоду",
                "name_en": "FindByCode",
                "syntax": "НайтиПоКоду(Код)",
                "description": "Находит элемент справочника по коду",
                "context": "Справочник",
            }
        ],
    },
    "analysis_response": {
        "summary": "Analysis result example",
        "value": [
            {
                "rule_id": "SEC001",
                "severity": "CRITICAL",
                "line": 42,
                "message": "SQL Injection detected",
                "recommendation": "Use parameterized queries",
            }
        ],
    },
    "epf_request": {
        "summary": "EPF creation request",
        "value": {
            "name": "МояОбработка",
            "synonym": "Моя обработка",
            "bsl_code": "Процедура МояОбработка() Экспорт\nКонецПроцедуры",
        },
    },
    "error_response": {
        "summary": "Error response example",
        "value": {
            "error": "Configuration not found",
            "error_type": "not_found",
            "details": "Configuration 'ut11' does not exist",
        },
    },
}


# ============================================================================
# Enricher
# ============================================================================


def enrich_openapi_spec(spec_path: Path) -> dict[str, Any]:
    """A-2/A-3/A-4: Обогатить OpenAPI spec.

    Args:
        spec_path: Путь к docs/mcp-openapi.json

    Returns:
        Обогащённый spec как dict.
    """
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    # A-4: Добавить tags в top-level
    if "tags" not in spec:
        spec["tags"] = []
    existing_tags = {t["name"] for t in spec["tags"]}
    for category in TOOL_CATEGORIES:
        if category not in existing_tags:
            spec["tags"].append({
                "name": category,
                "description": f"Tools for {category.lower()}",
            })

    # Построить map: tool_name → category
    tool_to_category: dict[str, str] = {}
    for category, tools in TOOL_CATEGORIES.items():
        for tool in tools:
            tool_to_category[tool] = category

    # A-4: Обновить tags для каждого path
    for path, methods in spec.get("paths", {}).items():
        for method, info in methods.items():
            if not isinstance(info, dict):
                continue
            # Извлекаем tool name из path (последний сегмент)
            tool_name = path.strip("/").split("/")[-1]
            category = tool_to_category.get(tool_name, "MCP Tools")
            info["tags"] = [category]

    # A-2: Добавить components/schemas
    if "components" not in spec:
        spec["components"] = {}
    spec["components"]["schemas"] = RESPONSE_SCHEMAS

    # A-2: Добавить response schemas для каждого path
    for path, methods in spec.get("paths", {}).items():
        for method, info in methods.items():
            if not isinstance(info, dict):
                continue
            if "responses" not in info:
                info["responses"] = {}

            # 200 response с schema
            if "200" not in info["responses"]:
                info["responses"]["200"] = {
                    "description": "Successful response",
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        },
                    },
                }

            # 400 error response
            if "400" not in info["responses"]:
                info["responses"]["400"] = {
                    "description": "Bad request",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                }

    # A-3: Добавить examples
    if "components" not in spec:
        spec["components"] = {}
    spec["components"]["examples"] = EXAMPLES

    return spec


def save_enriched_spec(spec: dict[str, Any], output_path: Path) -> None:
    """Сохранить обогащённый spec."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)


def main() -> int:
    """CLI для OpenAPI enricher."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich OpenAPI spec (A-2, A-3, A-4)")
    parser.add_argument(
        "--input", "-i",
        default="docs/mcp-openapi.json",
        help="Input OpenAPI spec path",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output path (default: overwrite input)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return 1

    output_path = Path(args.output) if args.output else input_path

    spec = enrich_openapi_spec(input_path)
    save_enriched_spec(spec, output_path)

    print(f"✅ Enriched spec saved: {output_path}")
    print(f"   Paths: {len(spec.get('paths', {}))}")
    print(f"   Tags: {len(spec.get('tags', []))}")
    print(f"   Schemas: {len(spec.get('components', {}).get('schemas', {}))}")
    print(f"   Examples: {len(spec.get('components', {}).get('examples', {}))}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
