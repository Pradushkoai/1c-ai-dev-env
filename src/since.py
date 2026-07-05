"""
since.py — Версионирование public API через @since декоратор.

F1.7 (2026-07-05): Вводит версионирование public API.
Каждый публичный класс/функция может быть помечен @since("6.0.0")
для отслеживания когда API был добавлен.

Использование:
    from src.since import since, deprecated

    @since("6.0.0")
    class Config:
        ...

    @since("6.1.0")
    def new_feature():
        ...

    @deprecated("6.1.0", "Используйте Config.from_env()")
    def old_function():
        ...

Breaking changes:
    @deprecated("6.1.0", "Используйте Config", removal_version="7.0.0")
    def old_function():
        ...
"""

from __future__ import annotations

import functools
import warnings
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Текущая версия проекта
_CURRENT_VERSION = "6.0.0"


def since(version: str) -> Callable[[F], F]:
    """Декоратор: пометить функцию/класс как добавленную в версии.

    Args:
        version: Версия, в которой API был добавлен (например, "6.0.0").

    Example:
        @since("6.0.0")
        def my_function():
            ...
    """

    def decorator(obj: F) -> F:
        setattr(obj, "_since_version", version)
        return obj

    return decorator


def deprecated(
    deprecated_in: str,
    replacement: str = "",
    removal_version: str = "",
) -> Callable[[F], F]:
    """Декоратор: пометить функцию как deprecated.

    Args:
        deprecated_in: Версия, в которой API стал deprecated.
        replacement: Что использовать вместо (опционально).
        removal_version: Версия, в которой API будет удалён (опционально).

    Example:
        @deprecated("6.1.0", "Используйте Config.from_env()", "7.0.0")
        def old_function():
            ...
    """

    def decorator(func: F) -> F:
        msg = f"{func.__name__} deprecated since {deprecated_in}"
        if replacement:
            msg += f". Use {replacement}"
        if removal_version:
            msg += f". Will be removed in {removal_version}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        setattr(wrapper, "_deprecated_in", deprecated_in)
        setattr(wrapper, "_replacement", replacement)
        setattr(wrapper, "_removal_version", removal_version)
        setattr(wrapper, "_is_deprecated", True)
        return wrapper  # type: ignore[return-value]

    return decorator


def get_since_version(obj: Any) -> str:
    """Получить версию, в которой API был добавлен.

    Args:
        obj: Функция или класс, помеченный @since.

    Returns:
        Версия (например, "6.0.0") или пустая строка если не помечен.
    """
    return getattr(obj, "_since_version", "")


def is_deprecated(obj: Any) -> bool:
    """Проверить, помечен ли объект как deprecated.

    Args:
        obj: Функция или класс.

    Returns:
        True если объект помечен @deprecated, False иначе.
    """
    return getattr(obj, "_is_deprecated", False)


def get_deprecation_info(obj: Any) -> dict[str, str]:
    """Получить информацию о deprecation.

    Args:
        obj: Функция или класс, помеченный @deprecated.

    Returns:
        dict с ключами: deprecated_in, replacement, removal_version.
        Пустой dict если не помечен.
    """
    if not is_deprecated(obj):
        return {}
    return {
        "deprecated_in": getattr(obj, "_deprecated_in", ""),
        "replacement": getattr(obj, "_replacement", ""),
        "removal_version": getattr(obj, "_removal_version", ""),
    }
