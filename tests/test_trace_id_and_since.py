"""
F1.5 + F1.7 (2026-07-05): Тесты для trace_id и @since/@deprecated.
"""

from __future__ import annotations

import warnings

import pytest

from src.since import since, deprecated, get_since_version, is_deprecated, get_deprecation_info
from src.services.logger import new_trace_id, set_trace_id, get_trace_id, clear_trace_id


class TestTraceId:
    """F1.5: trace_id для сквозной трассировки."""

    def test_new_trace_id_returns_string(self) -> None:
        """new_trace_id возвращает строку."""
        clear_trace_id()
        tid = new_trace_id()
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_new_trace_id_is_unique(self) -> None:
        """Каждый вызов new_trace_id генерирует уникальный ID."""
        tid1 = new_trace_id()
        tid2 = new_trace_id()
        assert tid1 != tid2

    def test_get_trace_id_returns_current(self) -> None:
        """get_trace_id возвращает текущий trace_id."""
        tid = new_trace_id()
        assert get_trace_id() == tid

    def test_set_trace_id_custom(self) -> None:
        """set_trace_id устанавливает custom ID."""
        set_trace_id("custom-trace-id")
        assert get_trace_id() == "custom-trace-id"

    def test_clear_trace_id(self) -> None:
        """clear_trace_id очищает trace_id."""
        new_trace_id()
        clear_trace_id()
        assert get_trace_id() == ""

    def test_trace_id_is_hex(self) -> None:
        """new_trace_id возвращает hex строку (UUID)."""
        clear_trace_id()
        tid = new_trace_id()
        # UUID hex — 32 символа, только hex digits
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)


class TestSinceDecorator:
    """F1.7: @since декоратор."""

    def test_since_sets_version(self) -> None:
        """@since устанавливает _since_version."""

        @since("6.0.0")
        def my_func() -> None:
            pass

        assert get_since_version(my_func) == "6.0.0"

    def test_since_works_on_class(self) -> None:
        """@since работает на классах."""

        @since("6.1.0")
        class MyClass:
            pass

        assert get_since_version(MyClass) == "6.1.0"

    def test_get_since_version_empty_if_not_marked(self) -> None:
        """get_since_version возвращает '' если не помечен."""

        def unmarked() -> None:
            pass

        assert get_since_version(unmarked) == ""

    def test_since_preserves_function(self) -> None:
        """@since сохраняет функциональность функции."""

        @since("6.0.0")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5


class TestDeprecatedDecorator:
    """F1.7: @deprecated декоратор."""

    def test_deprecated_emits_warning(self) -> None:
        """@deprecated emits DeprecationWarning."""

        @deprecated("6.1.0", "new_func()")
        def old_func() -> int:
            return 42

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            assert result == 42
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "6.1.0" in str(w[0].message)
            assert "new_func()" in str(w[0].message)

    def test_is_deprecated_true(self) -> None:
        """is_deprecated возвращает True для deprecated функций."""

        @deprecated("6.1.0")
        def old_func() -> None:
            pass

        assert is_deprecated(old_func) is True

    def test_is_deprecated_false(self) -> None:
        """is_deprecated возвращает False для обычных функций."""

        def normal_func() -> None:
            pass

        assert is_deprecated(normal_func) is False

    def test_deprecation_info(self) -> None:
        """get_deprecation_info возвращает полную информацию."""

        @deprecated("6.1.0", "new_func()", "7.0.0")
        def old_func() -> None:
            pass

        info = get_deprecation_info(old_func)
        assert info["deprecated_in"] == "6.1.0"
        assert info["replacement"] == "new_func()"
        assert info["removal_version"] == "7.0.0"

    def test_deprecation_info_empty_if_not_deprecated(self) -> None:
        """get_deprecation_info возвращает {} для обычных функций."""

        def normal_func() -> None:
            pass

        assert get_deprecation_info(normal_func) == {}

    def test_deprecated_preserves_function(self) -> None:
        """@deprecated сохраняет функциональность."""

        @deprecated("6.1.0")
        def compute() -> int:
            return 100

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert compute() == 100
