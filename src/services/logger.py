"""
Структурированное логирование через structlog.

Почему structlog а не logging:
- Контекстные биндинги (log.bind(tool=..., config=...))
- JSON-вывод для машинной обработки (в MCP/CI)
- Pretty-вывод для разработки (с цветами)
- Совместимость со стандартным logging (structlog обёртка)

Использование:
    from src.services.logger import get_logger
    log = get_logger(__name__)
    log.info("config_built", config="ut11", indexes=4)
    log.warning("parser_failed", parser="metadata", error=str(e))

Конфигурация через env:
- LOG_LEVEL=DEBUG|INFO|WARNING|ERROR (default: INFO)
- LOG_FORMAT=console|json (default: console; json для CI/MCP)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

# structlog может быть не установлен — fallback на logging
try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


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
