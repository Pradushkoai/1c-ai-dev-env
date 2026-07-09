"""
src/mcpserver/handlers/config.py — Домен конфигурации: поиск + inspect.

Phase 3.2 of refactoring: aggregate module для конфигурационных handlers.

Объединяет handlers из:
- config_search.py (list_configs, search_1c_methods, search_code, call_graph,
  get_form_elements, get_api_reference)
- inspect_data.py (inspect, data_status)

Реэкспортирует для нового пути импорта:
    from src.mcpserver.handlers.config import handle_list_configs

Существующие пути импорта продолжают работать (backward compat).
"""

from __future__ import annotations

# Re-export из config_search.py
from .config_search import (
    CONFIG_SEARCH_HANDLERS,
    handle_call_graph,
    handle_get_api_reference,
    handle_get_form_elements,
    handle_list_configs,
    handle_search_1c_methods,
    handle_search_code,
)

# Re-export из inspect_data.py
from .inspect_data import (
    INSPECT_DATA_HANDLERS,
    handle_data_status,
    handle_inspect,
)

__all__ = [
    "CONFIG_SEARCH_HANDLERS",
    "INSPECT_DATA_HANDLERS",
    "handle_call_graph",
    "handle_data_status",
    "handle_get_api_reference",
    "handle_get_form_elements",
    "handle_inspect",
    "handle_list_configs",
    "handle_search_1c_methods",
    "handle_search_code",
]
