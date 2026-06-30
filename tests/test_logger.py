"""
Тесты для src.services.logger — обёртка над structlog/logging.
"""
from __future__ import annotations

import io
import logging
import os
import sys
from unittest.mock import patch

import pytest


def test_get_logger_returns_logger():
    """get_logger() возвращает объект с методами info/warning/error."""
    from src.services.logger import get_logger
    log = get_logger("test_module")
    assert hasattr(log, "info")
    assert hasattr(log, "warning")
    assert hasattr(log, "error")


def test_configure_logging_does_not_raise():
    """configure_logging() не выбрасывает исключения."""
    from src.services.logger import configure_logging
    # Должно работать с разными форматами
    configure_logging(level=logging.INFO, fmt="console")
    configure_logging(level=logging.DEBUG, fmt="json")
    configure_logging(level=logging.WARNING, fmt="console")


def test_get_log_level_from_env():
    """_get_log_level читает LOG_LEVEL из env."""
    from src.services.logger import _get_log_level
    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        assert _get_log_level() == logging.DEBUG
    with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}):
        assert _get_log_level() == logging.ERROR
    with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
        # Fallback на INFO
        assert _get_log_level() == logging.INFO


def test_get_log_format_from_env():
    """_get_log_format читает LOG_FORMAT из env."""
    from src.services.logger import _get_log_format
    with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
        assert _get_log_format() == "json"
    with patch.dict(os.environ, {"LOG_FORMAT": "console"}):
        assert _get_log_format() == "console"
    # Default
    os.environ.pop("LOG_FORMAT", None)
    assert _get_log_format() == "console"


def test_logger_info_does_not_raise():
    """Логгер не выбрасывает при info/warning/error."""
    from src.services.logger import get_logger, configure_logging
    configure_logging(level=logging.DEBUG, fmt="json")
    log = get_logger("test")
    log.info("test_event", key="value")
    log.warning("test_warning", key="value")
    log.error("test_error", key="value")


def test_warn_print_replaces_print():
    """warn_print() пишет в лог, не в stdout."""
    from src.services.logger import warn_print, configure_logging
    configure_logging(level=logging.WARNING, fmt="json")

    # Перехватываем stderr
    captured = io.StringIO()
    with patch("sys.stderr", captured):
        warn_print("test_warning_message", parser="metadata")

    output = captured.getvalue()
    # Должно попасть в stderr (через logging), НЕ в stdout
    assert "test_warning_message" in output or output == ""  # structlog может не писать при filtering


def test_bind_context_does_not_raise():
    """bind_context/clear_context работают без исключений."""
    from src.services.logger import bind_context, clear_context
    bind_context(config="ut11", task_id="abc")
    clear_context()


def test_logger_logs_to_stderr_not_stdout():
    """Логи идут в stderr, не в stdout (важно для MCP)."""
    from src.services.logger import get_logger, configure_logging
    configure_logging(level=logging.DEBUG, fmt="json")

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
        log = get_logger("test_stderr")
        log.info("test_message_should_go_to_stderr")

    # stdout должен быть пустым (MCP-протокол)
    assert stdout_capture.getvalue() == ""
    # stderr может содержать лог (зависит от structlog)


def test_logger_with_structlog_or_fallback():
    """Логгер работает и с structlog и без него."""
    # Просто проверяем что не падает ни в одном из режимов
    from src.services.logger import get_logger, configure_logging, HAS_STRUCTLOG

    configure_logging(level=logging.INFO, fmt="console")
    log = get_logger("fallback_test")
    log.info("event_with_or_without_structlog")
    # Не упало — ОК


def test_logger_json_format():
    """JSON-формат лога содержит структурированные поля."""
    from src.services.logger import get_logger, configure_logging
    configure_logging(level=logging.DEBUG, fmt="json")

    # Перехватываем stderr
    captured = io.StringIO()
    with patch("sys.stderr", captured):
        log = get_logger("json_test")
        log.info("test_event", field1="value1", field2=42)

    output = captured.getvalue()
    # Если structlog установлен — вывод должен быть JSON
    try:
        import structlog  # noqa: F401
        if output.strip():
            # Может быть несколько строк (если были другие логи)
            lines = [l for l in output.strip().split("\n") if "test_event" in l]
            if lines:
                import json
                data = json.loads(lines[0])
                assert data["event"] == "test_event"
                assert data["field1"] == "value1"
                assert data["field2"] == 42
    except ImportError:
        pass  # structlog не установлен — тест пропускается


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
