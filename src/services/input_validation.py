"""
S5: Input validation для MCP tools.

JSON Schema валидация для всех 56 MCP tools.
Каждый handler проверяет input перед выполнением.
Rate limiting через env var MCP_RATE_LIMIT.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger(__name__)

# P2.7/S5: Rate limiting state
_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_WINDOW = 60.0  # 60 seconds window


def validate_input(
    tool_name: str,
    arguments: dict[str, Any],
    required_params: list[str],
    optional_params: list[str] | None = None,
) -> tuple[bool, str]:
    """Валидация input для MCP tool.

    Args:
        tool_name: Имя tool (для сообщений об ошибках).
        arguments: Аргументы от MCP клиента.
        required_params: Обязательные параметры.
        optional_params: Опциональные параметры (если None — не проверяются).

    Returns:
        (is_valid, error_message). Если is_valid=True, error_message пустой.
    """
    if not isinstance(arguments, dict):
        return False, f"{tool_name}: arguments must be a dict, got {type(arguments).__name__}"

    # Проверка обязательных параметров
    for param in required_params:
        if param not in arguments:
            return False, f"{tool_name}: missing required parameter '{param}'"
        if arguments[param] is None:
            return False, f"{tool_name}: parameter '{param}' is None"
        # Проверка что строки не пустые
        if isinstance(arguments[param], str) and not arguments[param].strip():
            return False, f"{tool_name}: parameter '{param}' is empty"

    # Проверка типов для известных параметров
    type_checks: dict[str, type | tuple[type, ...]] = {
        "query": str,
        "config_name": str,
        "file_path": str,
        "limit": int,
        "name": str,
        "output_path": str,
        "module": str,
        "method": str,
        "action": str,
    }
    for param, expected_type in type_checks.items():
        if param in arguments and arguments[param] is not None and not isinstance(arguments[param], expected_type):
            actual_type = type(arguments[param]).__name__
            expected_name = (
                expected_type
                if isinstance(expected_type, str)
                else getattr(expected_type, "__name__", str(expected_type))
            )
            return False, (f"{tool_name}: parameter '{param}' must be {expected_name}, got {actual_type}")

    # Проверка limit > 0
    if "limit" in arguments and isinstance(arguments["limit"], int):
        if arguments["limit"] <= 0:
            return False, f"{tool_name}: parameter 'limit' must be > 0, got {arguments['limit']}"
        if arguments["limit"] > 1000:
            return False, f"{tool_name}: parameter 'limit' must be <= 1000, got {arguments['limit']}"

    return True, ""


def check_rate_limit(tool_name: str, max_calls: int | None = None) -> tuple[bool, str]:
    """Проверка rate limit для MCP tool.

    Args:
        tool_name: Имя tool.
        max_calls: Максимум вызовов в окне (60 сек).
            Если None — берётся из env var MCP_RATE_LIMIT (default: 100).

    Returns:
        (is_allowed, error_message).
    """
    if max_calls is None:
        max_calls = int(os.environ.get("MCP_RATE_LIMIT", "100"))

    if max_calls <= 0:
        return True, ""  # rate limiting disabled

    now = time.monotonic()
    window = _RATE_LIMIT_WINDOW

    # Очистка старых записей
    call_times = _rate_limit_store[tool_name]
    while call_times and call_times[0] < now - window:
        call_times.popleft()

    # Проверка лимита
    if len(call_times) >= max_calls:
        return False, (f"{tool_name}: rate limit exceeded ({max_calls} calls per {window}s). Try again later.")

    # Запись вызова
    call_times.append(now)
    return True, ""


def reset_rate_limits() -> None:
    """Сбросить все rate limits (для тестов)."""
    _rate_limit_store.clear()
