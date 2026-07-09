"""
D-2 (2026-07-06): Тесты для security handler (применение исключений в handlers).

Проверяет:
- resolve_path_or_raise: raise PathTraversalError, ValidationError
- check_rate_limit_or_raise: raise RateLimitExceededError
- validate_input_or_raise: raise ValidationError
- handle_security_errors decorator: перехват и JSON response
- secure_all_handlers: применение ко всем handlers
- Интеграционные тесты с реальными handlers
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import (
    PathTraversalError,
    ProjectError,
    RateLimitExceededError,
    ValidationError,
)
from src.mcpserver.handlers.security_handler import (
    check_rate_limit_or_raise,
    handle_security_errors,
    resolve_path_or_raise,
    secure_all_handlers,
    validate_input_or_raise,
)


# ============================================================================
# resolve_path_or_raise tests
# ============================================================================


class TestResolvePathOrRaise:
    def test_valid_path_returns_resolved(self, tmp_path: Path) -> None:
        """Валидный путь → resolved Path."""
        project = MagicMock()
        project.paths.root = tmp_path
        (tmp_path / "test.bsl").write_text("// ok", encoding="utf-8")

        result = resolve_path_or_raise("test.bsl", project, must_exist=True)
        assert result is not None
        assert result.name == "test.bsl"

    def test_empty_path_raises_validation(self, tmp_path: Path) -> None:
        """Пустой путь → ValidationError."""
        project = MagicMock()
        project.paths.root = tmp_path

        with pytest.raises(ValidationError, match="empty"):
            resolve_path_or_raise("", project)

    def test_whitespace_path_raises_validation(self, tmp_path: Path) -> None:
        """Whitespace путь → ValidationError."""
        project = MagicMock()
        project.paths.root = tmp_path

        with pytest.raises(ValidationError, match="empty"):
            resolve_path_or_raise("   ", project)

    def test_path_traversal_raises_security(self, tmp_path: Path) -> None:
        """Path traversal → PathTraversalError."""
        project = MagicMock()
        project.paths.root = tmp_path

        with pytest.raises(PathTraversalError):
            resolve_path_or_raise("../../../etc/passwd", project)

    def test_absolute_outside_raises_security(self, tmp_path: Path) -> None:
        """Абсолютный путь вне project → PathTraversalError."""
        project = MagicMock()
        project.paths.root = tmp_path

        with pytest.raises(PathTraversalError):
            resolve_path_or_raise("/etc/passwd", project)

    def test_sensitive_file_raises_security(self, tmp_path: Path) -> None:
        """Sensitive file → PathTraversalError."""
        project = MagicMock()
        project.paths.root = tmp_path

        with pytest.raises(PathTraversalError):
            resolve_path_or_raise(".env", project)


# ============================================================================
# check_rate_limit_or_raise tests
# ============================================================================


class TestCheckRateLimitOrRaise:
    def setup_method(self) -> None:
        from src.services.input_validation import reset_rate_limits
        reset_rate_limits()

    def teardown_method(self) -> None:
        from src.services.input_validation import reset_rate_limits
        reset_rate_limits()

    def test_under_limit_no_raise(self) -> None:
        """Under limit — no exception."""
        # Should not raise
        check_rate_limit_or_raise("test_tool", max_calls=10)

    def test_over_limit_raises(self) -> None:
        """Over limit → RateLimitExceededError."""
        for _ in range(5):
            check_rate_limit_or_raise("test_tool", max_calls=5)

        with pytest.raises(RateLimitExceededError):
            check_rate_limit_or_raise("test_tool", max_calls=5)

    def test_disabled_limit_no_raise(self) -> None:
        """max_calls=0 — disabled."""
        for _ in range(100):
            check_rate_limit_or_raise("test_tool", max_calls=0)


# ============================================================================
# validate_input_or_raise tests
# ============================================================================


class TestValidateInputOrRaise:
    def test_valid_input_no_raise(self) -> None:
        """Valid input — no exception."""
        validate_input_or_raise(
            "test_tool",
            {"query": "test"},
            required_params=["query"],
        )

    def test_missing_required_raises(self) -> None:
        """Missing required param → ValidationError."""
        with pytest.raises(ValidationError, match="missing"):
            validate_input_or_raise(
                "test_tool",
                {},
                required_params=["query"],
            )

    def test_none_param_raises(self) -> None:
        """None param → ValidationError."""
        with pytest.raises(ValidationError):
            validate_input_or_raise(
                "test_tool",
                {"query": None},
                required_params=["query"],
            )

    def test_empty_string_raises(self) -> None:
        """Empty string → ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            validate_input_or_raise(
                "test_tool",
                {"query": ""},
                required_params=["query"],
            )

    def test_invalid_type_raises(self) -> None:
        """Invalid type → ValidationError."""
        with pytest.raises(ValidationError):
            validate_input_or_raise(
                "test_tool",
                {"query": 123},  # int вместо str
                required_params=["query"],
            )


# ============================================================================
# handle_security_errors decorator tests
# ============================================================================


class TestHandleSecurityErrors:
    def test_decorator_preserves_function(self) -> None:
        """Декоратор сохраняет функцию."""
        @handle_security_errors
        def my_handler():
            return "ok"

        assert my_handler() == "ok"

    def test_path_traversal_caught(self) -> None:
        """PathTraversalError перехватывается."""
        @handle_security_errors
        def my_handler():
            raise PathTraversalError("test traversal")

        result = my_handler()
        assert isinstance(result, list)
        # Should contain error response
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["error_type"] == "path_traversal"

    def test_rate_limit_caught(self) -> None:
        """RateLimitExceededError перехватывается."""
        @handle_security_errors
        def my_handler():
            raise RateLimitExceededError("test_tool", 100, 60.0)

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["error_type"] == "rate_limit"

    def test_validation_error_caught(self) -> None:
        """ValidationError перехватывается."""
        @handle_security_errors
        def my_handler():
            raise ValidationError("test validation")

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["error_type"] == "validation"

    def test_project_error_caught(self) -> None:
        """ProjectError перехватывается."""
        @handle_security_errors
        def my_handler():
            raise ProjectError("test project error")

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["error_type"] == "project_error"

    def test_other_exceptions_not_caught(self) -> None:
        """Другие исключения НЕ перехватываются."""
        @handle_security_errors
        def my_handler():
            raise RuntimeError("not security error")

        with pytest.raises(RuntimeError):
            my_handler()

    def test_recovery_hint_in_response(self) -> None:
        """Recovery hint попадает в response."""
        @handle_security_errors
        def my_handler():
            raise ValidationError(
                "test",
                recovery_hint="fix it like this",
            )

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["recovery_hint"] == "fix it like this"

    def test_async_function_supported(self) -> None:
        """Асинхронные функции поддерживаются."""
        @handle_security_errors
        async def my_handler():
            raise ValidationError("async test")

        result = asyncio.run(my_handler())
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert data["error_type"] == "validation"


# ============================================================================
# secure_all_handlers tests
# ============================================================================


class TestSecureAllHandlers:
    def test_secures_handlers_in_module(self) -> None:
        """secure_all_handlers применяет декоратор к handle_* функциям."""
        # Create a mock module with handlers
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        def handle_test():
            return "ok"

        def handle_another():
            return "ok"

        def not_a_handler():
            return "ok"

        mock_module.handle_test = handle_test
        mock_module.handle_another = handle_another
        mock_module.not_a_handler = not_a_handler

        secured = secure_all_handlers(mock_module)

        assert "handle_test" in secured
        assert "handle_another" in secured
        assert "not_a_handler" not in secured

    def test_secured_handler_has_security_wrapped_flag(self) -> None:
        """Secured handler помечен _security_wrapped."""
        # Используем SimpleNamespace вместо MagicMock для корректной работы setattr
        from types import SimpleNamespace

        module = SimpleNamespace(__name__="test_module")

        def handle_test():
            return "ok"

        module.handle_test = handle_test

        secure_all_handlers(module)

        assert hasattr(module.handle_test, "_security_wrapped")
        assert module.handle_test._security_wrapped is True

    def test_already_secured_not_re_wrapped(self) -> None:
        """Уже secured handler не оборачивается повторно."""
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        def handle_test():
            return "ok"

        handle_test._security_wrapped = True
        mock_module.handle_test = handle_test

        secured = secure_all_handlers(mock_module)
        # Should not re-wrap
        assert "handle_test" not in secured


# ============================================================================
# Integration tests with real handlers
# ============================================================================


class TestIntegrationWithHandlers:
    """Интеграционные тесты с реальными handlers."""

    def test_quality_handlers_have_security_decorator(self) -> None:
        """Все handle_* в quality.py могут быть secured."""
        from src.mcpserver.handlers import quality

        # Применяем security
        secured = secure_all_handlers(quality)

        # Должны быть secured все handle_* functions
        assert len(secured) > 0
        for name in secured:
            assert name.startswith("handle_")

    def test_path_traversal_in_handler_returns_json_error(
        self, tmp_path: Path
    ) -> None:
        """Handler с path traversal возвращает JSON error, не crash."""
        from src.mcpserver.handlers import quality

        # Secure the handlers
        secure_all_handlers(quality)

        project = MagicMock()
        project.paths.root = tmp_path
        project.paths.scripts_dir = tmp_path / "scripts"
        (tmp_path / "scripts").mkdir(exist_ok=True)

        # Try path traversal
        result = asyncio.run(quality.handle_audit_security(
            project=project,
            arguments={"file_path": "../../../etc/passwd"},
        ))

        # Should return error response, not crash
        assert isinstance(result, list)
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert "error" in data

    def test_missing_required_param_returns_json_error(
        self, tmp_path: Path
    ) -> None:
        """Handler с missing param возвращает JSON error."""
        from src.mcpserver.handlers import quality

        secure_all_handlers(quality)

        project = MagicMock()
        project.paths.root = tmp_path

        # Call without required file_path
        result = asyncio.run(quality.handle_audit_security(
            project=project,
            arguments={},
        ))

        assert isinstance(result, list)
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)
        assert "error" in data


# ============================================================================
# Error response format tests
# ============================================================================


class TestErrorResponseFormat:
    def test_error_response_has_all_fields(self) -> None:
        """Error response содержит все поля."""
        @handle_security_errors
        def my_handler():
            raise ValidationError(
                "test error",
                recovery_hint="fix it",
            )

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)

        assert "error" in data
        assert "error_type" in data
        assert "recovery_hint" in data

    def test_error_response_without_recovery_hint(self) -> None:
        """Error response без recovery_hint."""
        @handle_security_errors
        def my_handler():
            raise ValidationError("test error")  # no recovery_hint

        result = my_handler()
        text = result[0].text if hasattr(result[0], "text") else result[0]["text"]
        data = json.loads(text)

        assert "error" in data
        assert "error_type" in data
        # recovery_hint может отсутствовать
