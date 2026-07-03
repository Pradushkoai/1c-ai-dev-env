"""
S4: Performance optimization — caching layer для MCP tools.

LRU cache для search_1c_methods, get_api_reference, list_configs.
Уменьшает latency повторных вызовов с ~50ms до <1ms.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class LRUCache:
    """LRU (Least Recently Used) cache для результатов MCP tools.

    Потокобезопасность: НЕ потокобезопасен. Для async использования
    нужен lock на уровне caller.

    Attributes:
        maxsize: Максимум элементов в кэше.
        ttl: Time-to-live в секундах (0 = без ограничения).
    """

    def __init__(self, maxsize: int = 128, ttl: float = 300.0) -> None:
        """Инициализация LRU cache.

        Args:
            maxsize: Максимум элементов (default: 128).
            ttl: TTL в секундах (default: 300 = 5 минут).
        """
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Получить значение из кэша.

        Args:
            key: Ключ.

        Returns:
            Значение или None если нет/expired.
        """
        if key not in self._cache:
            self._misses += 1
            return None

        timestamp, value = self._cache[key]

        # Проверка TTL
        if self._ttl > 0 and (time.monotonic() - timestamp) > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Установить значение в кэш.

        Args:
            key: Ключ.
            value: Значение.
        """
        if key in self._cache:
            self._cache.move_to_end(key)

        self._cache[key] = (time.monotonic(), value)

        # Evict oldest if over capacity
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate(self, key: str | None = None) -> None:
        """Инвалидировать кэш.

        Args:
            key: Ключ для инвалидации (если None — весь кэш).
        """
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    def stats(self) -> dict[str, int | float]:
        """Статистика кэша.

        Returns:
            {size, maxsize, ttl, hits, misses, hit_rate}
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "ttl": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
        }

    def reset_stats(self) -> None:
        """Сбросить статистику hits/misses."""
        self._hits = 0
        self._misses = 0


# Глобальные кэши для MCP tools
_search_cache = LRUCache(maxsize=64, ttl=300)  # 5 min TTL
_api_cache = LRUCache(maxsize=32, ttl=600)  # 10 min TTL
_configs_cache = LRUCache(maxsize=4, ttl=60)  # 1 min TTL


def get_search_cache() -> LRUCache:
    """Получить кэш для search operations."""
    return _search_cache


def get_api_cache() -> LRUCache:
    """Получить кэш для API reference operations."""
    return _api_cache


def get_configs_cache() -> LRUCache:
    """Получить кэш для list_configs operations."""
    return _configs_cache


def invalidate_all_caches() -> None:
    """Инвалидировать все кэши (например, при config build)."""
    _search_cache.invalidate()
    _api_cache.invalidate()
    _configs_cache.invalidate()
    logger.info("All caches invalidated")


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Создать cache key из аргументов функции.

    Args:
        *args, **kwargs: Аргументы функции.

    Returns:
        Строковый key для использования в LRUCache.
    """
    key_parts: list[str] = []
    for arg in args:
        key_parts.append(str(arg))
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode("utf-8")).hexdigest()


def cached(
    cache: LRUCache | None = None,
    key_func: Callable[..., str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор для кэширования результатов функции.

    Args:
        cache: LRUCache instance (если None — создаётся новый).
        key_func: Функция для генерации cache key (если None — make_cache_key).

    Usage:
        @cached(get_search_cache())
        def search_1c_methods(query: str, limit: int = 10):
            ...
    """
    if cache is None:
        cache = LRUCache(maxsize=64, ttl=300)
    if key_func is None:
        key_func = make_cache_key

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_func(*args, **kwargs)
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug("Cache hit: %s.%s", func.__module__, func.__name__)
                return cached_value

            result = func(*args, **kwargs)
            cache.set(key, result)
            logger.debug("Cache miss: %s.%s", func.__module__, func.__name__)
            return result

        wrapper._cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
