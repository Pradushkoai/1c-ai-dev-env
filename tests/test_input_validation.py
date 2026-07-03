"""
S5: Тесты для input validation и rate limiting.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.services.input_validation import (
    check_rate_limit,
    reset_rate_limits,
    validate_input,
)


# ============================================================================
# Тесты — validate_input
# ============================================================================


class TestValidateInput:
    """Проверка validate_input()."""

    def test_valid_input_with_required_params(self) -> None:
        """Валидный input с required params → is_valid=True."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "найти", "limit": 5},
            required_params=["query"],
        )
        assert is_valid is True
        assert msg == ""

    def test_missing_required_param(self) -> None:
        """Отсутствует required param → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"limit": 5},
            required_params=["query"],
        )
        assert is_valid is False
        assert "query" in msg

    def test_empty_required_param(self) -> None:
        """Пустой required param → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "  "},
            required_params=["query"],
        )
        assert is_valid is False
        assert "empty" in msg

    def test_none_required_param(self) -> None:
        """None required param → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": None},
            required_params=["query"],
        )
        assert is_valid is False
        assert "None" in msg

    def test_wrong_type_string_param(self) -> None:
        """Неверный тип string param → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": 123},
            required_params=["query"],
        )
        assert is_valid is False
        assert "str" in msg

    def test_wrong_type_int_param(self) -> None:
        """Неверный тип int param → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "test", "limit": "five"},
            required_params=["query"],
        )
        assert is_valid is False
        assert "int" in msg

    def test_limit_zero(self) -> None:
        """limit=0 → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "test", "limit": 0},
            required_params=["query"],
        )
        assert is_valid is False
        assert "> 0" in msg

    def test_limit_too_large(self) -> None:
        """limit > 1000 → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "test", "limit": 5000},
            required_params=["query"],
        )
        assert is_valid is False
        assert "<= 1000" in msg

    def test_valid_limit(self) -> None:
        """limit=10 → is_valid=True."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            {"query": "test", "limit": 10},
            required_params=["query"],
        )
        assert is_valid is True

    def test_non_dict_arguments(self) -> None:
        """arguments не dict → is_valid=False."""
        is_valid, msg = validate_input(
            "search_1c_methods",
            "not a dict",  # type: ignore[arg-type]
            required_params=["query"],
        )
        assert is_valid is False
        assert "dict" in msg

    def test_no_required_params(self) -> None:
        """Нет required params → всегда is_valid=True."""
        is_valid, msg = validate_input(
            "list_configs",
            {},
            required_params=[],
        )
        assert is_valid is True


# ============================================================================
# Тесты — check_rate_limit
# ============================================================================


class TestRateLimit:
    """Проверка check_rate_limit()."""

    def setup_method(self) -> None:
        """Сброс rate limits перед каждым тестом."""
        reset_rate_limits()

    def test_first_call_allowed(self) -> None:
        """Первый вызов → allowed=True."""
        is_allowed, msg = check_rate_limit("test_tool", max_calls=10)
        assert is_allowed is True
        assert msg == ""

    def test_within_limit_allowed(self) -> None:
        """Вызовы в пределах лимита → allowed=True."""
        for _ in range(5):
            is_allowed, _ = check_rate_limit("test_tool", max_calls=10)
            assert is_allowed is True

    def test_exceeds_limit_blocked(self) -> None:
        """Превышение лимита → allowed=False."""
        for _ in range(3):
            check_rate_limit("test_tool", max_calls=3)

        is_allowed, msg = check_rate_limit("test_tool", max_calls=3)
        assert is_allowed is False
        assert "rate limit" in msg.lower()

    def test_disabled_when_zero(self) -> None:
        """max_calls=0 → rate limiting отключено."""
        is_allowed, _ = check_rate_limit("test_tool", max_calls=0)
        assert is_allowed is True

    def test_env_var_default(self) -> None:
        """MCP_RATE_LIMIT env var используется по умолчанию."""
        with patch.dict(os.environ, {"MCP_RATE_LIMIT": "2"}):
            reset_rate_limits()
            check_rate_limit("test_env_tool")
            check_rate_limit("test_env_tool")
            is_allowed, msg = check_rate_limit("test_env_tool")
            assert is_allowed is False
            assert "rate limit" in msg.lower()

    def test_different_tools_independent(self) -> None:
        """Разные tools имеют независимые лимиты."""
        for _ in range(3):
            check_rate_limit("tool_a", max_calls=3)

        # tool_b должен быть allowed, хотя tool_a исчерпан
        is_allowed, _ = check_rate_limit("tool_b", max_calls=3)
        assert is_allowed is True

    def test_reset_clears_all(self) -> None:
        """reset_rate_limits() очищает все лимиты."""
        for _ in range(5):
            check_rate_limit("test_tool", max_calls=5)

        reset_rate_limits()
        is_allowed, _ = check_rate_limit("test_tool", max_calls=5)
        assert is_allowed is True
