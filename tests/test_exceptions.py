"""
F1.4 (2026-07-05): Тесты для расширенной иерархии исключений.

Гарантирует:
1. Все 8 базовых классов существуют и наследуются от ProjectError
2. recovery_hint работает для каждого класса
3. Специфичные подклассы имеют правильные атрибуты
4. Backward compat: существующие исключения не сломаны
"""

from __future__ import annotations

import pytest

from src.exceptions import (
    # Базовые
    ProjectError,
    # Конфигурации
    ConfigError,
    ConfigAlreadyExistsError,
    ConfigNotFoundError,
    ConfigNotActiveError,
    # Архивация
    ArchiveError,
    ArchiveNotFoundError,
    ArchiveCorruptedError,
    # BSL
    BSLAnalysisError,
    BSLBinaryNotFoundError,
    BSLAnalysisTimeoutError,
    # Индексация
    IndexBuildError,
    # F1.4: Безопасность
    SecurityError,
    PathTraversalError,
    RateLimitExceededError,
    # F1.4: Внешние инструменты
    ExternalToolError,
    V8UnpackError,
    # F1.4: Валидация
    ValidationError,
    InvalidParameterError,
    # F1.4: Парсинг
    ParseError,
    XMLParseError,
    BSLParseError,
)


class TestExceptionHierarchy:
    """F1.4: Все базовые классы наследуются от ProjectError."""

    @pytest.mark.parametrize("exc_class", [
        ConfigError,
        ArchiveError,
        BSLAnalysisError,
        IndexBuildError,
        SecurityError,
        ExternalToolError,
        ValidationError,
        ParseError,
    ])
    def test_base_classes_inherit_from_project_error(self, exc_class: type) -> None:
        """Все 8 базовых классов наследуются от ProjectError."""
        assert issubclass(exc_class, ProjectError), (
            f"{exc_class.__name__} должен наследоваться от ProjectError"
        )


class TestRecoveryHint:
    """F1.4: recovery_hint работает для каждого класса."""

    def test_project_error_has_recovery_hint(self) -> None:
        """ProjectError имеет атрибут recovery_hint."""
        exc = ProjectError("test", recovery_hint="do something")
        assert exc.recovery_hint == "do something"

    def test_project_error_default_recovery_hint(self) -> None:
        """ProjectError без recovery_hint имеет пустую строку."""
        exc = ProjectError("test")
        assert exc.recovery_hint == ""

    def test_config_not_found_has_recovery_hint(self) -> None:
        """ConfigNotFoundError содержит recovery_hint с командой."""
        exc = ConfigNotFoundError("ut11")
        assert "1c-ai config add" in exc.recovery_hint
        assert "ut11" in exc.recovery_hint

    def test_bsl_binary_not_found_has_recovery_hint(self) -> None:
        """BSLBinaryNotFoundError содержит recovery_hint про install.sh."""
        exc = BSLBinaryNotFoundError("/path/to/bsl")
        assert "install.sh" in exc.recovery_hint

    def test_path_traversal_has_recovery_hint(self) -> None:
        """PathTraversalError содержит recovery_hint."""
        exc = PathTraversalError("../../etc/passwd")
        assert exc.recovery_hint != ""
        assert "проект" in exc.recovery_hint.lower() or "project" in exc.recovery_hint.lower()

    def test_rate_limit_has_recovery_hint(self) -> None:
        """RateLimitExceededError содержит recovery_hint."""
        exc = RateLimitExceededError("search_1c_methods", 100, 60.0)
        assert "MCP_RATE_LIMIT" in exc.recovery_hint

    def test_v8unpack_error_has_recovery_hint(self) -> None:
        """V8UnpackError содержит recovery_hint."""
        exc = V8UnpackError("build", "timeout")
        assert "v8unpack" in exc.recovery_hint

    def test_invalid_parameter_has_recovery_hint(self) -> None:
        """InvalidParameterError содержит recovery_hint."""
        exc = InvalidParameterError("file_path", "is empty")
        assert "file_path" in exc.recovery_hint

    def test_xml_parse_error_has_recovery_hint(self) -> None:
        """XMLParseError содержит recovery_hint."""
        exc = XMLParseError("/path/to/file.xml", "syntax error")
        assert "file.xml" in exc.recovery_hint

    def test_bsl_parse_error_has_recovery_hint(self) -> None:
        """BSLParseError содержит recovery_hint."""
        exc = BSLParseError("/path/to/module.bsl", 42, "syntax")
        assert "module.bsl" in exc.recovery_hint


class TestSecurityErrors:
    """F1.4: SecurityError и подклассы."""

    def test_path_traversal_inherits_security_error(self) -> None:
        """PathTraversalError наследуется от SecurityError."""
        assert issubclass(PathTraversalError, SecurityError)

    def test_rate_limit_inherits_security_error(self) -> None:
        """RateLimitExceededError наследуется от SecurityError."""
        assert issubclass(RateLimitExceededError, SecurityError)

    def test_path_traversal_has_path_attr(self) -> None:
        """PathTraversalError имеет атрибут path."""
        exc = PathTraversalError("../../etc/passwd")
        assert exc.path == "../../etc/passwd"

    def test_rate_limit_has_attrs(self) -> None:
        """RateLimitExceededError имеет атрибуты tool_name, max_calls, window."""
        exc = RateLimitExceededError("search", 100, 60.0)
        assert exc.tool_name == "search"
        assert exc.max_calls == 100
        assert exc.window == 60.0


class TestExternalToolErrors:
    """F1.4: ExternalToolError и подклассы."""

    def test_v8unpack_inherits_external_tool_error(self) -> None:
        """V8UnpackError наследуется от ExternalToolError."""
        assert issubclass(V8UnpackError, ExternalToolError)

    def test_v8unpack_has_tool_name(self) -> None:
        """V8UnpackError имеет атрибут tool_name."""
        exc = V8UnpackError("build", "timeout")
        assert exc.tool_name == "v8unpack"

    def test_v8unpack_has_operation(self) -> None:
        """V8UnpackError имеет атрибут operation."""
        exc = V8UnpackError("build", "timeout")
        assert exc.operation == "build"


class TestValidationErrors:
    """F1.4: ValidationError и подклассы."""

    def test_invalid_parameter_inherits_validation_error(self) -> None:
        """InvalidParameterError наследуется от ValidationError."""
        assert issubclass(InvalidParameterError, ValidationError)

    def test_invalid_parameter_has_param_name(self) -> None:
        """InvalidParameterError имеет атрибут param_name."""
        exc = InvalidParameterError("file_path", "is empty")
        assert exc.param_name == "file_path"


class TestParseErrors:
    """F1.4: ParseError и подклассы."""

    def test_xml_parse_inherits_parse_error(self) -> None:
        """XMLParseError наследуется от ParseError."""
        assert issubclass(XMLParseError, ParseError)

    def test_bsl_parse_inherits_parse_error(self) -> None:
        """BSLParseError наследуется от ParseError."""
        assert issubclass(BSLParseError, ParseError)

    def test_xml_parse_has_file_path(self) -> None:
        """XMLParseError имеет атрибут file_path."""
        exc = XMLParseError("/path/to/file.xml", "syntax error")
        assert exc.file_path == "/path/to/file.xml"

    def test_bsl_parse_has_line(self) -> None:
        """BSLParseError имеет атрибут line."""
        exc = BSLParseError("/path/to/module.bsl", 42, "syntax")
        assert exc.line == 42


class TestBackwardCompat:
    """F1.4: Backward compatibility — существующие исключения не сломаны."""

    def test_config_already_exists_still_works(self) -> None:
        """ConfigAlreadyExistsError работает как раньше."""
        exc = ConfigAlreadyExistsError("test")
        assert exc.name == "test"
        assert "уже существует" in str(exc)

    def test_config_not_found_still_works(self) -> None:
        """ConfigNotFoundError работает как раньше."""
        exc = ConfigNotFoundError("test")
        assert exc.name == "test"
        assert "не найдена" in str(exc)

    def test_archive_not_found_still_works(self) -> None:
        """ArchiveNotFoundError работает как раньше."""
        exc = ArchiveNotFoundError("test")
        assert exc.name == "test"
        assert "не найден" in str(exc)

    def test_index_build_error_still_works(self) -> None:
        """IndexBuildError работает как раньше."""
        exc = IndexBuildError("test", "detail")
        assert exc.config_name == "test"
        assert "test" in str(exc)

    def test_bsl_timeout_still_works(self) -> None:
        """BSLAnalysisTimeoutError работает как раньше."""
        exc = BSLAnalysisTimeoutError(60)
        assert exc.timeout == 60
        assert "60" in str(exc)
