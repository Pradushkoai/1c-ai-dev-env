"""
D-2 (2026-07-06): Security error handler для MCP handlers.

Применяет security исключения из src/exceptions.py в MCP handlers:
- PathTraversalError — при path traversal попытках
- RateLimitExceededError — при превышении rate limit
- ValidationError — при неверных входных данных

Декоратор @handle_security_errors перехватывает security исключения
и возвращает стандартизированный JSON error response.

Использование:
    from src.mcpserver.handlers.security_handler import handle_security_errors

    @handle_security_errors
    def my_handler(arguments, project):
        path = resolve_path_or_raise(file_path, project)
        check_rate_limit_or_raise(tool_name)
        # ... business logic ...
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable

from src.exceptions import (
    PathTraversalError,
    ProjectError,
    RateLimitExceededError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper functions (raise exceptions instead of returning None)
# ============================================================================


def resolve_path_or_raise(
    raw_path: str,
    project: Any,
    *,
    must_exist: bool = False,
    operation: str = "read",
) -> Any:
    """Resolve path и raise PathTraversalError при попытке обхода.

    Args:
        raw_path: Путь от user input.
        project: Project instance.
        must_exist: Если True, путь должен существовать.
        operation: "read" или "write" для hardened checks.

    Returns:
        Resolved Path.

    Raises:
        PathTraversalError: Если путь вне project root.
        ValidationError: Если путь пустой.
    """
    from src.mcpserver.handlers._security import resolve_path_hardened

    if not raw_path or not raw_path.strip():
        raise ValidationError(
            "Path is empty",
            recovery_hint="Provide a non-empty file_path parameter",
        )

    resolved = resolve_path_hardened(
        raw_path, project, operation=operation, must_exist=must_exist
    )
    if resolved is None:
        # PathTraversalError конструктор принимает path: str
        raise PathTraversalError(raw_path[:200])

    return resolved


def check_rate_limit_or_raise(
    tool_name: str,
    max_calls: int | None = None,
) -> None:
    """Check rate limit и raise RateLimitExceededError при превышении.

    Args:
        tool_name: Имя MCP tool.
        max_calls: Максимум вызовов (None = env var MCP_RATE_LIMIT).

    Raises:
        RateLimitExceededError: Если rate limit превышен.
    """
    from src.services.input_validation import check_rate_limit, _RATE_LIMIT_WINDOW

    allowed, error = check_rate_limit(tool_name, max_calls=max_calls)
    if not allowed:
        # RateLimitExceededError конструктор принимает (tool_name, max_calls, window)
        actual_max = max_calls if max_calls is not None else 100
        raise RateLimitExceededError(tool_name, actual_max, _RATE_LIMIT_WINDOW)


def validate_input_or_raise(
    tool_name: str,
    arguments: dict[str, Any],
    required_params: list[str],
    optional_params: list[str] | None = None,
) -> None:
    """Validate input и raise ValidationError при ошибках.

    Args:
        tool_name: Имя tool.
        arguments: Аргументы от MCP клиента.
        required_params: Обязательные параметры.
        optional_params: Опциональные параметры.

    Raises:
        ValidationError: При неверных входных данных.
    """
    from src.services.input_validation import validate_input

    is_valid, error = validate_input(
        tool_name, arguments, required_params, optional_params
    )
    if not is_valid:
        raise ValidationError(
            error,
            recovery_hint=f"Check required parameters: {', '.join(required_params)}",
        )


# ============================================================================
# Decorator: handle security errors in MCP handlers
# ============================================================================


def handle_security_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Декоратор для MCP handlers: перехват security exceptions.

    Перехватывает:
    - PathTraversalError → JSON error with "path_traversal" error_type
    - RateLimitExceededError → JSON error with "rate_limit" error_type
    - ValidationError → JSON error with "validation" error_type
    - ProjectError (базовый) → JSON error with "project_error" error_type

    Возвращает стандартизированный JSON error response:
    {
        "error": "<message>",
        "error_type": "<type>",
        "recovery_hint": "<hint>"
    }

    Поддерживает как sync, так и async функции.
    """
    import asyncio
    import inspect

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except PathTraversalError as e:
                logger.warning("PathTraversalError in %s: %s", func.__name__, e)
                return _make_error_response(
                    error=str(e),
                    error_type="path_traversal",
                    recovery_hint=getattr(e, "recovery_hint", ""),
                )
            except RateLimitExceededError as e:
                logger.warning("RateLimitExceededError in %s: %s", func.__name__, e)
                return _make_error_response(
                    error=str(e),
                    error_type="rate_limit",
                    recovery_hint=getattr(e, "recovery_hint", ""),
                )
            except ValidationError as e:
                logger.warning("ValidationError in %s: %s", func.__name__, e)
                return _make_error_response(
                    error=str(e),
                    error_type="validation",
                    recovery_hint=getattr(e, "recovery_hint", ""),
                )
            except ProjectError as e:
                logger.warning("ProjectError in %s: %s", func.__name__, e)
                return _make_error_response(
                    error=str(e),
                    error_type="project_error",
                    recovery_hint=getattr(e, "recovery_hint", ""),
                )
        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except PathTraversalError as e:
            logger.warning("PathTraversalError in %s: %s", func.__name__, e)
            return _make_error_response(
                error=str(e),
                error_type="path_traversal",
                recovery_hint=getattr(e, "recovery_hint", ""),
            )
        except RateLimitExceededError as e:
            logger.warning("RateLimitExceededError in %s: %s", func.__name__, e)
            return _make_error_response(
                error=str(e),
                error_type="rate_limit",
                recovery_hint=getattr(e, "recovery_hint", ""),
            )
        except ValidationError as e:
            logger.warning("ValidationError in %s: %s", func.__name__, e)
            return _make_error_response(
                error=str(e),
                error_type="validation",
                recovery_hint=getattr(e, "recovery_hint", ""),
            )
        except ProjectError as e:
            logger.warning("ProjectError in %s: %s", func.__name__, e)
            return _make_error_response(
                error=str(e),
                error_type="project_error",
                recovery_hint=getattr(e, "recovery_hint", ""),
            )

    return wrapper


def _make_error_response(
    error: str,
    error_type: str,
    recovery_hint: str = "",
) -> list:
    """Создать стандартизированный error response для MCP.

    Returns:
        List с одним TextContent element (MCP protocol format).
    """
    # Import here to avoid circular import
    try:
        from mcp import types

        error_data = {
            "error": error,
            "error_type": error_type,
        }
        if recovery_hint:
            error_data["recovery_hint"] = recovery_hint

        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_data, ensure_ascii=False),
            )
        ]
    except ImportError:
        # Fallback if mcp types not available
        return [{"type": "text", "text": json.dumps({"error": error, "error_type": error_type})}]


# ============================================================================
# Convenience: apply security to all handlers in a module
# ============================================================================


def secure_all_handlers(module: Any) -> list[str]:
    """Применить @handle_security_errors ко всем handler функциям в модуле.

    Args:
        module: Модуль с handler функциями (начинаются с handle_).

    Returns:
        Список имён обработанных функций.
    """
    secured: list[str] = []
    for name in dir(module):
        if name.startswith("handle_"):
            func = getattr(module, name)
            if callable(func) and not hasattr(func, "_security_wrapped"):
                wrapped = handle_security_errors(func)
                wrapped._security_wrapped = True  # type: ignore[attr-defined]
                setattr(module, name, wrapped)
                secured.append(name)

    logger.info("Secured %d handlers in %s", len(secured), module.__name__)
    return secured
