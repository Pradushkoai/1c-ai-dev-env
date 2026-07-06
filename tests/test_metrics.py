"""
Тесты для src/services/metrics.py (P1.5: Prometheus observability).

Проверяет:
1. No-op fallback когда prometheus_client недоступен
2. PrometheusRegistry с prometheus_client (моки)
3. Декоратор @with_metrics (sync и async)
4. get_metrics singleton
5. maybe_start_metrics_server
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from src.services.metrics import (
    NoOpMetric,
    NoOpRegistry,
    PrometheusRegistry,
    _check_prometheus,
    get_metrics,
    maybe_start_metrics_server,
    with_metrics,
)


# ============================================================================
# Тесты No-op fallback
# ============================================================================


class TestNoOpFallback:
    """No-op метрики когда prometheus_client недоступен."""

    def test_noop_metric_methods_exist(self) -> None:
        """NoOpMetric имеет все методы (inc, observe, set, dec, labels)."""
        metric = NoOpMetric()
        # Все методы не должны raise
        metric.inc()
        metric.inc(5.0)
        metric.observe(0.5)
        metric.set(10.0)
        metric.dec()
        metric.dec(2.0)
        # labels возвращает self (для chaining)
        result = metric.labels("foo", "bar")
        assert result is metric

    def test_noop_registry_has_all_metrics(self) -> None:
        """NoOpRegistry содержит все метрики как NoOpMetric."""
        registry = NoOpRegistry()
        assert isinstance(registry.tool_calls, NoOpMetric)
        assert isinstance(registry.tool_errors, NoOpMetric)
        assert isinstance(registry.tool_latency, NoOpMetric)
        assert isinstance(registry.active_configs, NoOpMetric)
        assert isinstance(registry.index_size, NoOpMetric)

    def test_noop_registry_start_http_server_no_raise(self) -> None:
        """start_http_server на NoOpRegistry не падает."""
        registry = NoOpRegistry()
        registry.start_http_server(8001)  # не должно raise

    def test_noop_registry_get_metrics_text(self) -> None:
        """get_metrics_text возвращает строку с пометкой not installed."""
        registry = NoOpRegistry()
        text = registry.get_metrics_text()
        assert isinstance(text, str)
        assert "not installed" in text


# ============================================================================
# Тесты get_metrics singleton
# ============================================================================


class TestGetMetrics:
    """Проверка get_metrics() singleton."""

    def test_get_metrics_returns_noop_without_prometheus(self) -> None:
        """get_metrics() возвращает NoOpRegistry если prometheus недоступен."""
        with patch("src.services.metrics._check_prometheus", return_value=False):
            # Сброс singleton
            import src.services.metrics as metrics_mod

            old_registry = metrics_mod._REGISTRY
            metrics_mod._REGISTRY = None
            try:
                registry = get_metrics()
                assert isinstance(registry, NoOpRegistry)
            finally:
                metrics_mod._REGISTRY = old_registry

    def test_get_metrics_returns_prometheus_when_available(self) -> None:
        """get_metrics() возвращает PrometheusRegistry если prometheus доступен."""
        with (
            patch("src.services.metrics._check_prometheus", return_value=True),
            patch("src.services.metrics.PrometheusRegistry") as MockReg,
        ):
            mock_instance = MockReg.return_value
            import src.services.metrics as metrics_mod

            old_registry = metrics_mod._REGISTRY
            metrics_mod._REGISTRY = None
            try:
                registry = get_metrics()
                assert registry is mock_instance
            finally:
                metrics_mod._REGISTRY = old_registry


# ============================================================================
# Тесты @with_metrics декоратора
# ============================================================================


class TestWithMetricsDecorator:
    """Проверка декоратора @with_metrics."""

    def test_with_metrics_sync_success(self) -> None:
        """@with_metrics для sync функции — success записан."""
        mock_registry = MagicMock()

        @with_metrics("test_tool")
        def my_func(x: int) -> int:
            return x * 2

        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            result = my_func(5)

        assert result == 10
        mock_registry.record_tool_call.assert_called_once_with("test_tool", "success")
        mock_registry.observe_latency.assert_called_once()
        mock_registry.record_tool_error.assert_not_called()

    def test_with_metrics_sync_error(self) -> None:
        """@with_metrics для sync функции — error записан при exception."""
        mock_registry = MagicMock()

        @with_metrics("test_tool")
        def my_func() -> None:
            raise ValueError("test error")

        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            with pytest.raises(ValueError, match="test error"):
                my_func()

        mock_registry.record_tool_call.assert_called_once_with("test_tool", "error")
        mock_registry.record_tool_error.assert_called_once_with("test_tool", "ValueError")
        mock_registry.observe_latency.assert_called_once()

    def test_with_metrics_async_success(self) -> None:
        """@with_metrics для async функции — success записан."""
        mock_registry = MagicMock()

        @with_metrics("async_tool")
        async def my_async_func(x: int) -> int:
            await asyncio.sleep(0.001)
            return x + 1

        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            result = asyncio.run(my_async_func(10))

        assert result == 11
        mock_registry.record_tool_call.assert_called_once_with("async_tool", "success")
        mock_registry.observe_latency.assert_called_once()

    def test_with_metrics_async_error(self) -> None:
        """@with_metrics для async функции — error записан."""
        mock_registry = MagicMock()

        @with_metrics("async_tool")
        async def my_async_func() -> None:
            raise RuntimeError("async error")

        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            with pytest.raises(RuntimeError, match="async error"):
                asyncio.run(my_async_func())

        mock_registry.record_tool_call.assert_called_once_with("async_tool", "error")
        mock_registry.record_tool_error.assert_called_once_with("async_tool", "RuntimeError")

    def test_with_metrics_preserves_function_name(self) -> None:
        """@with_metrics сохраняет __name__ и __doc__."""

        @with_metrics("test")
        def my_func() -> None:
            """My docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."


# ============================================================================
# Тесты maybe_start_metrics_server
# ============================================================================


class TestMaybeStartMetricsServer:
    """Проверка maybe_start_metrics_server()."""

    def test_no_start_without_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без MCP_METRICS_PORT env var — сервер не запускается."""
        monkeypatch.delenv("MCP_METRICS_PORT", raising=False)
        mock_registry = MagicMock()
        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            maybe_start_metrics_server()
        mock_registry.start_http_server.assert_not_called()

    def test_start_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """С MCP_METRICS_PORT env var — сервер запускается."""
        monkeypatch.setenv("MCP_METRICS_PORT", "9001")
        mock_registry = MagicMock()
        with patch("src.services.metrics.get_metrics", return_value=mock_registry):
            maybe_start_metrics_server()
        mock_registry.start_http_server.assert_called_once_with(9001)

    def test_invalid_port_no_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Невалидный порт — не падает."""
        monkeypatch.setenv("MCP_METRICS_PORT", "not-a-number")
        # Не должно raise
        maybe_start_metrics_server()


# ============================================================================
# Тесты PrometheusRegistry (с реальным prometheus_client если доступен)
# ============================================================================


class TestPrometheusRegistry:
    """Проверка PrometheusRegistry с prometheus_client.

    Использует get_metrics() singleton, чтобы избежать конфликта
    повторной регистрации метрик в prometheus_client.
    """

    def test_prometheus_registry_init(self) -> None:
        """PrometheusRegistry инициализируется с prometheus_client."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        assert isinstance(registry, PrometheusRegistry)
        assert registry.tool_calls is not None
        assert registry.tool_errors is not None
        assert registry.tool_latency is not None
        assert registry.active_configs is not None
        assert registry.index_size is not None

    def test_prometheus_record_tool_call(self) -> None:
        """record_tool_call работает с prometheus_client."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        # Не должно raise
        registry.record_tool_call("test_tool", "success")
        registry.record_tool_call("test_tool", "error")

    def test_prometheus_observe_latency(self) -> None:
        """observe_latency работает с prometheus_client."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        registry.observe_latency("test_tool", 0.05)

    def test_prometheus_get_metrics_text(self) -> None:
        """get_metrics_text возвращает строку с метриками."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        registry.record_tool_call("test_tool", "success")
        text = registry.get_metrics_text()
        assert isinstance(text, str)
        assert "mcp_tool_calls_total" in text

    def test_prometheus_set_active_configs(self) -> None:
        """set_active_configs работает."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        registry.set_active_configs(3)
        registry.set_active_configs(0)

    def test_prometheus_set_index_size(self) -> None:
        """set_index_size работает."""
        if not _check_prometheus():
            import pytest

            pytest.skip("prometheus_client не установлен")

        registry = get_metrics()
        registry.set_index_size("metadata", 1024000)
        registry.set_index_size("api", 512000)
