"""
src/mcpserver/handlers/analyze.py — Домен анализа: BSL + security + standards.

Phase 3.2 of refactoring: aggregate module для анализаторов.

Объединяет handlers из:
- analyzers.py (analyze_bsl, check_standards, solve_context, solve_check)
- quality.py (get_knowledge, audit_security, get_code_metrics, check_transactions,
  analyze_queries, analyze_architecture, check_form_quality, check_skd_quality,
  diff_configs, validate_query_static)

Реэкспортирует для нового пути импорта:
    from src.mcpserver.handlers.analyze import handle_analyze_bsl

Существующие пути импорта продолжают работать (backward compat).
"""

from __future__ import annotations

# Re-export из analyzers.py
from .analyzers import (
    ANALYZER_HANDLERS,
    handle_analyze_bsl,
    handle_check_standards,
    handle_solve_check,
    handle_solve_context,
)

# Re-export из quality.py
from .quality import (
    QUALITY_HANDLERS,
    handle_analyze_architecture,
    handle_analyze_queries,
    handle_audit_security,
    handle_check_form_quality,
    handle_check_transactions,
    handle_diff_configs,
    handle_get_code_metrics,
    handle_get_knowledge,
    handle_validate_query_static,
)

__all__ = [
    "ANALYZER_HANDLERS",
    "QUALITY_HANDLERS",
    "handle_analyze_architecture",
    "handle_analyze_bsl",
    "handle_analyze_queries",
    "handle_audit_security",
    "handle_check_form_quality",
    "handle_check_standards",
    "handle_check_transactions",
    "handle_diff_configs",
    "handle_get_code_metrics",
    "handle_get_knowledge",
    "handle_solve_check",
    "handle_solve_context",
    "handle_validate_query_static",
]
