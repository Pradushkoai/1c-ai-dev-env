"""
Структурированное логирование через structlog.

F1.5 (2026-07-05): добавлена поддержка trace_id для сквозной трассировки
CLI→MCP→LLM. trace_id генерируется при старте сессии и передаётся через
contextvars во все логи.

Использование:
    from src.services.logger import get_logger, set_trace_id, new_trace_id

    new_trace_id()  # генерирует UUID и привязывает к contextvars
    log = get_logger(__name__)
    log.info("config_built", config="ut11")  # → {"trace_id": "abc123...", ...}

    # Или явная установка:
    set_trace_id("custom-id")
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any

# structlog может быть не установлен — fallback на logging
try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


# F1.5: trace_id для сквозной трассировки
_TRACE_ID_VAR = "trace_id"
_current_trace_id: str = ""


def new_trace_id() -> str:
    """F1.5: Сгенерировать новый trace_id и привязать к contextvars.

    trace_id передаётся во все последующие лог-сообщения через
    structlog.contextvars, обеспечивая сквозную трассировку
    CLI→MCP→LLM запросов.

    Returns:
        Сгенерированный trace_id (UUID hex, 32 символа).
    """
    global _current_trace_id
    trace_id = uuid.uuid4().hex
    _current_trace_id = trace_id
    if HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(**{_TRACE_ID_VAR: trace_id})
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """F1.5: Установить существующий trace_id.

    Используется когда trace_id приходит извне (например, из MCP request).

    Args:
        trace_id: trace_id для привязки к contextvars.
    """
    global _current_trace_id
    _current_trace_id = trace_id
    if HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(**{_TRACE_ID_VAR: trace_id})


def get_trace_id() -> str:
    """F1.5: Получить текущий trace_id.

    Returns:
        Текущий trace_id (пустая строка если не установлен).
    """
    return _current_trace_id


def clear_trace_id() -> None:
    """F1.5: Очистить trace_id из contextvars."""
    global _current_trace_id
    _current_trace_id = ""
    if HAS_STRUCTLOG:
        structlog.contextvars.unbind_contextvars(_TRACE_ID_VAR)


def _get_log_level() -> int:
    """Получить уровень логирования из env."""
    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_str, logging.INFO)


def _get_log_format() -> str:
    """Формат вывода: console (dev) или json (CI/MCP)."""
    return os.environ.get("LOG_FORMAT", "console").lower()


def configure_logging(
    level: int | None = None,
    fmt: str | None = None,
) -> None:
    """Настроить логирование глобально.

    Безопасно вызывать многократно — повторные вызовы игнорируются после первого.

    Args:
        level: уровень (default: из env или INFO)
        fmt: 'console' | 'json' (default: из env или 'console')
    """
    if level is None:
        level = _get_log_level()
    if fmt is None:
        fmt = _get_log_format()

    # Стандартный logging как backend
    logging.basicConfig(
        level=level,
        stream=sys.stderr,  # stdout занят под пользовательский вывод / MCP
        format="%(message)s",
        force=True,  # перенастроить если уже было настроено
    )

    if not HAS_STRUCTLOG:
        return

    # Сбрасываем cached config (structlog кэширует loggers при первом использовании)
    structlog.reset_defaults()

    # structlog processors — порядок важен
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if fmt == "json":
        # JSON для CI/MCP — машиночитаемый
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        # Console для разработки — цветной, читаемый
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )

    # F1.5: авто-генерация trace_id при первой настройке логирования
    if not _current_trace_id:
        new_trace_id()


def get_logger(name: str | None = None) -> Any:
    """Получить логгер.

    Args:
        name: имя модуля (обычно __name__)

    Returns:
        structlog logger если установлен, иначе стандартный logging.Logger
    """
    # Автонастройка при первом вызове
    if not logging.getLogger().handlers:
        configure_logging()

    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


# ─────────────────────────────────────────────
# Контекстные биндинги — для трассировки через весь пайплайн
# ─────────────────────────────────────────────


def bind_context(**kwargs: Any) -> None:
    """Привязать контекстные переменные ко всем последующим логам.

    Пример:
        bind_context(config="ut11", task_id="abc123")
        log.info("build_started")  # → {"config": "ut11", "task_id": "abc123", "event": "build_started"}
    """
    if HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Очистить контекстные переменные."""
    if HAS_STRUCTLOG:
        structlog.contextvars.clear_contextvars()


# ─────────────────────────────────────────────
# Совместимость со старым кодом (drop-in замена print для warnings/errors)
# ─────────────────────────────────────────────


def warn_print(message: str, **kwargs: Any) -> None:
    """Заменитель print() для warnings в services.

    Используется там, где раньше был `print(f'⚠️ ...')` —
    теперь пишет в stderr через structlog, не засоряя stdout/MCP.
    """
    log = get_logger("src.services")
    log.warning(message, **kwargs)


def error_print(message: str, **kwargs: Any) -> None:
    """Заменитель print() для errors в services."""
    log = get_logger("src.services")
    log.error(message, **kwargs)
