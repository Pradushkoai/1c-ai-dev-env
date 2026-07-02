"""
analyzers.py — handlers для анализаторов BSL, генерации и EPF.

P2.2: вынесено из mcp_server.py (группа 3).
Handlers: analyze_bsl, check_standards, audit_security, get_code_metrics,
          check_transactions, analyze_queries, analyze_architecture,
          check_form_quality, check_skd_quality, diff_configs,
          generate_processing, generate_report, build_epf, validate_generated,
          epf_factory_create, epf_factory_templates
"""

from __future__ import annotations

# Заглушка — handlers будут перенесены поэтапно
ANALYZER_HANDLERS: dict = {}
