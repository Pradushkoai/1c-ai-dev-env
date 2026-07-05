"""
metrics.py — Prometheus metrics для MCP tools и наблюдения за производительностью.

P1.5: добавлены метрики для observability production.
Отслеживает: latency, error rate, usage count для каждого MCP tool.

Метрики:
- mcp_tool_calls_total: Counter (tool_name, status) — всего вызовов
- mcp_tool_errors_total: Counter (tool_name, error_type) — всего ошибок
- mcp_tool_latency_seconds: Histogram (tool_name) — латентность
- mcp_active_configs: Gauge — количество активных конфигураций
- mcp_index_size_bytes: Gauge (index_type) — размер индексов

Использование:
    from src.services.metrics import with_metrics, get_metrics

    # Декоратор для MCP handler
    @with_metrics("search_1c_methods")
    async def handle_search(query, limit):
        ...

    # HTTP endpoint для Prometheus scrape
    get_metrics().start_http_server(8001)

    # Или получить текстовый вывод метрик
    metrics_text = get_metrics().get_metrics_text()

Зависимости: prometheus_client (extras [metrics])
Fallback: если prometheus_client не установлен — метрики становятся no-op.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import prometheus_client
_PROMETHEUS_AVAILABLE: bool | None = None
_REGISTRY: Any = None  # MetricsRegistry singleton


def _check_prometheus() -> bool:
    """Проверить доступность prometheus_client (с кэшированием)."""
    global _PROMETHEUS_AVAILABLE
    if _PROMETHEUS_AVAILABLE is None:
        try:
            from prometheus_client import Counter, Gauge, Histogram  # noqa: F401

            _PROMETHEUS_AVAILABLE = True
        except ImportError:
            _PROMETHEUS_AVAILABLE = False
            logger.debug("prometheus_client не установлен. pip install -e '.[metrics]' для observability.")
    return _PROMETHEUS_AVAILABLE


class NoOpMetric:
    """No-op метрика для fallback когда prometheus_client недоступен."""

    def labels(self, *args: Any, **kwargs: Any) -> NoOpMetric:
        return self

    def inc(self, amount: float = 1.0) -> None:
        pass

    def observe(self, amount: float) -> None:
        pass

    def set(self, value: float) -> None:
        pass

    def dec(self, amount: float = 1.0) -> None:
        pass


class NoOpRegistry:
    """No-op registry когда prometheus_client недоступен."""

    def __init__(self) -> None:
        self.tool_calls = NoOpMetric()
        self.tool_errors = NoOpMetric()
        self.tool_latency = NoOpMetric()
        self.active_configs = NoOpMetric()
        self.index_size = NoOpMetric()

    def start_http_server(self, port: int = 8001) -> None:
        logger.warning("prometheus_client не установлен — /metrics endpoint недоступен")

    def get_metrics_text(self) -> str:
        return "# prometheus_client not installed\n"

    def record_tool_call(self, tool_name: str, status: str = "success") -> None:
        pass

    def record_tool_error(self, tool_name: str, error_type: str) -> None:
        pass

    def observe_latency(self, tool_name: str, latency_seconds: float) -> None:
        pass

    def set_active_configs(self, count: int) -> None:
        pass

    def set_index_size(self, index_type: str, size_bytes: int) -> None:
        pass


class PrometheusRegistry:
    """Реестр Prometheus метрик (singleton).

    Содержит все метрики проекта:
    - mcp_tool_calls_total: Counter (tool_name, status)
    - mcp_tool_errors_total: Counter (tool_name, error_type)
    - mcp_tool_latency_seconds: Histogram (tool_name)
    - mcp_active_configs: Gauge
    - mcp_index_size_bytes: Gauge (index_type)
    """

    def __init__(self) -> None:
        if not _check_prometheus():
            raise RuntimeError("prometheus_client не установлен")

        from prometheus_client import Counter, Gauge, Histogram

        self.tool_calls = Counter(
            "mcp_tool_calls_total",
            "Total MCP tool calls",
            ["tool_name", "status"],  # status: success, error
        )

        self.tool_errors = Counter(
            "mcp_tool_errors_total",
            "Total MCP tool errors",
            ["tool_name", "error_type"],
        )

        self.tool_latency = Histogram(
            "mcp_tool_latency_seconds",
            "MCP tool latency in seconds",
            ["tool_name"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        self.active_configs = Gauge(
            "mcp_active_configs",
            "Number of active 1C configurations",
        )

        self.index_size = Gauge(
            "mcp_index_size_bytes",
            "Size of index files in bytes",
            ["index_type"],  # metadata, api, skd, forms, platform
        )

    def start_http_server(self, port: int = 8001) -> None:
        """Запустить HTTP endpoint /metrics для Prometheus scrape.

        Args:
            port: Порт для HTTP сервера (default 8001).
        """
        from prometheus_client import start_http_server

        start_http_server(port)
        logger.info("Prometheus /metrics endpoint started on port %d", port)

    def get_metrics_text(self) -> str:
        """Получить метрики в текстовом формате Prometheus.

        Returns:
            Строка с метриками для /metrics endpoint.
        """
        from prometheus_client import generate_latest

        return generate_latest().decode("utf-8")

    def record_tool_call(self, tool_name: str, status: str = "success") -> None:
        """Записать вызов tool.

        Args:
            tool_name: Имя MCP tool.
            status: 'success' или 'error'.
        """
        self.tool_calls.labels(tool_name=tool_name, status=status).inc()

    def record_tool_error(self, tool_name: str, error_type: str) -> None:
        """Записать ошибку tool.

        Args:
            tool_name: Имя MCP tool.
            error_type: Тип ошибки (exception class name).
        """
        self.tool_errors.labels(tool_name=tool_name, error_type=error_type).inc()

    def observe_latency(self, tool_name: str, latency_seconds: float) -> None:
        """Записать латентность tool.

        Args:
            tool_name: Имя MCP tool.
            latency_seconds: Время выполнения в секундах.
        """
        self.tool_latency.labels(tool_name=tool_name).observe(latency_seconds)

    def set_active_configs(self, count: int) -> None:
        """Установить количество активных конфигураций.

        Args:
            count: Количество активных конфигураций.
        """
        self.active_configs.set(count)

    def set_index_size(self, index_type: str, size_bytes: int) -> None:
        """Установить размер индекса.

        Args:
            index_type: Тип индекса (metadata, api, skd, forms, platform).
            size_bytes: Размер в байтах.
        """
        self.index_size.labels(index_type=index_type).set(size_bytes)


def get_metrics() -> PrometheusRegistry | NoOpRegistry:
    """Получить singleton metrics registry.

    Returns:
        PrometheusRegistry если prometheus_client установлен,
        иначе NoOpRegistry (все операции no-op).
    """
    global _REGISTRY
    if _REGISTRY is None:
        if _check_prometheus():
            try:
                _REGISTRY = PrometheusRegistry()
            except Exception as e:
                logger.warning("Failed to init PrometheusRegistry: %s", e)
                _REGISTRY = NoOpRegistry()
        else:
            _REGISTRY = NoOpRegistry()
    return _REGISTRY  # type: ignore[no-any-return]


def with_metrics(tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор для инструментирования MCP handler метриками.

    Автоматически:
    - Записывает вызов (Counter)
    - Измеряет латентность (Histogram)
    - При ошибке — записывает error (Counter)

    Args:
        tool_name: Имя MCP tool для метрик.

    Usage:
        @with_metrics("search_1c_methods")
        async def handle_search(query, limit):
            ...

        @with_metrics("analyze_bsl")
        def handle_analyze(file_path):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Проверяем async или sync функция
        import asyncio

        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                registry = get_metrics()
                start_time = time.monotonic()
                try:
                    result = await func(*args, **kwargs)
                    registry.record_tool_call(tool_name, "success")
                    return result
                except Exception as e:
                    registry.record_tool_call(tool_name, "error")
                    registry.record_tool_error(tool_name, type(e).__name__)
                    raise
                finally:
                    latency = time.monotonic() - start_time
                    registry.observe_latency(tool_name, latency)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                registry = get_metrics()
                start_time = time.monotonic()
                try:
                    result = func(*args, **kwargs)
                    registry.record_tool_call(tool_name, "success")
                    return result
                except Exception as e:
                    registry.record_tool_call(tool_name, "error")
                    registry.record_tool_error(tool_name, type(e).__name__)
                    raise
                finally:
                    latency = time.monotonic() - start_time
                    registry.observe_latency(tool_name, latency)

            return sync_wrapper

    return decorator


def maybe_start_metrics_server() -> None:
    """Запустить /metrics HTTP сервер если задан MCP_METRICS_PORT env var.

    Env vars:
        MCP_METRICS_PORT: Порт для Prometheus scrape (default: не запускается).

    Usage:
        # В mcp_server.py при старте:
        from src.services.metrics import maybe_start_metrics_server
        maybe_start_metrics_server()

        # Запуск MCP сервера с метриками:
        MCP_METRICS_PORT=8001 python -m src.cli mcp serve
    """
    port_str = os.environ.get("MCP_METRICS_PORT")
    if port_str:
        try:
            port = int(port_str)
            registry = get_metrics()
            registry.start_http_server(port)
        except ValueError:
            logger.warning("Invalid MCP_METRICS_PORT: %s", port_str)
        except Exception as e:
            logger.warning("Failed to start metrics server: %s", e)
