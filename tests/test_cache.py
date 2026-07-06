"""
S4: Тесты для performance optimization — caching layer.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.services.cache import (
    LRUCache,
    cached,
    get_api_cache,
    get_configs_cache,
    get_search_cache,
    invalidate_all_caches,
    make_cache_key,
)


# ============================================================================
# Тесты — LRUCache
# ============================================================================


class TestLRUCache:
    """Проверка LRUCache."""

    def test_init(self) -> None:
        """LRUCache инициализируется."""
        cache = LRUCache(maxsize=10, ttl=60)
        assert cache.stats()["maxsize"] == 10

    def test_set_and_get(self) -> None:
        """set + get работает."""
        cache = LRUCache(maxsize=10, ttl=0)  # no TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_miss(self) -> None:
        """get несуществующего key → None."""
        cache = LRUCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_eviction_lru(self) -> None:
        """LRU eviction: самый старый элемент удаляется."""
        cache = LRUCache(maxsize=2, ttl=0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # "a" должен быть удалён

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_order_after_get(self) -> None:
        """get обновляет LRU порядок."""
        cache = LRUCache(maxsize=2, ttl=0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # "a" теперь most recently used
        cache.set("c", 3)  # "b" должен быть удалён (LRU)

        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_ttl_expiration(self) -> None:
        """TTL истекает → get возвращает None."""
        cache = LRUCache(maxsize=10, ttl=0.1)  # 100ms TTL
        cache.set("key", "value")
        time.sleep(0.15)  # wait for TTL
        assert cache.get("key") is None

    def test_ttl_not_expired(self) -> None:
        """TTL не истёк → get возвращает значение."""
        cache = LRUCache(maxsize=10, ttl=10)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_invalidate_single_key(self) -> None:
        """invalidate(key) удаляет один ключ."""
        cache = LRUCache(maxsize=10, ttl=0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_invalidate_all(self) -> None:
        """invalidate() без key очищает весь кэш."""
        cache = LRUCache(maxsize=10, ttl=0)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_stats(self) -> None:
        """stats возвращает корректную статистику."""
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss

        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["maxsize"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_reset_stats(self) -> None:
        """reset_stats сбрасывает hits/misses."""
        cache = LRUCache(maxsize=10)
        cache.set("a", 1)
        cache.get("a")
        cache.reset_stats()
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


# ============================================================================
# Тесты — cached decorator
# ============================================================================


class TestCachedDecorator:
    """Проверка @cached декоратора."""

    def test_cached_basic(self) -> None:
        """@cached кэширует результат."""
        call_count = 0

        @cached(LRUCache(maxsize=10, ttl=0))
        def expensive_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive_func(5) == 10
        assert expensive_func(5) == 10  # cache hit
        assert call_count == 1  # функция вызвана только 1 раз

    def test_cached_different_args(self) -> None:
        """@cached разделяет кэш по аргументам."""
        call_count = 0

        @cached(LRUCache(maxsize=10, ttl=0))
        def func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        func(5)
        func(10)
        func(5)  # cache hit
        assert call_count == 2

    def test_cached_preserves_function_name(self) -> None:
        """@cached сохраняет __name__."""

        @cached(LRUCache(maxsize=10, ttl=0))
        def my_func() -> None:
            pass

        assert my_func.__name__ == "my_func"

    def test_cached_with_default_cache(self) -> None:
        """@cached без cache аргумента — создаёт новый."""

        @cached()
        def func(x: int) -> int:
            return x * 2

        assert func(5) == 10
        assert func(5) == 10  # cache hit


# ============================================================================
# Тесты — global caches
# ============================================================================


class TestGlobalCaches:
    """Проверка глобальных кэшей."""

    def test_get_search_cache(self) -> None:
        """get_search_cache возвращает LRUCache."""
        cache = get_search_cache()
        assert isinstance(cache, LRUCache)

    def test_get_api_cache(self) -> None:
        """get_api_cache возвращает LRUCache."""
        cache = get_api_cache()
        assert isinstance(cache, LRUCache)

    def test_get_configs_cache(self) -> None:
        """get_configs_cache возвращает LRUCache."""
        cache = get_configs_cache()
        assert isinstance(cache, LRUCache)

    def test_invalidate_all_caches(self) -> None:
        """invalidate_all_caches очищает все кэши."""
        get_search_cache().set("a", 1)
        get_api_cache().set("b", 2)
        get_configs_cache().set("c", 3)

        invalidate_all_caches()

        assert get_search_cache().get("a") is None
        assert get_api_cache().get("b") is None
        assert get_configs_cache().get("c") is None


# ============================================================================
# Тесты — make_cache_key
# ============================================================================


class TestMakeCacheKey:
    """Проверка make_cache_key."""

    def test_same_args_same_key(self) -> None:
        """Одинаковые args → одинаковый key."""
        key1 = make_cache_key("query", limit=10)
        key2 = make_cache_key("query", limit=10)
        assert key1 == key2

    def test_different_args_different_key(self) -> None:
        """Разные args → разный key."""
        key1 = make_cache_key("query1")
        key2 = make_cache_key("query2")
        assert key1 != key2

    def test_kwargs_order_independent(self) -> None:
        """Порядок kwargs не влияет на key."""
        key1 = make_cache_key(a=1, b=2)
        key2 = make_cache_key(b=2, a=1)
        assert key1 == key2

    def test_returns_string(self) -> None:
        """make_cache_key возвращает строку."""
        key = make_cache_key("test")
        assert isinstance(key, str)
        assert len(key) > 0
