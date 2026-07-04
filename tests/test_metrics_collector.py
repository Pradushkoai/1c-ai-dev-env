"""
Тесты для src.metrics — MetricsCollector для SLO/SLI метрик MCP tools.

Этап 5.2: добавлены тесты для поднятия coverage.
"""

from __future__ import annotations

import time

import pytest

from src.metrics import MetricsCollector, ToolCall


class TestToolCall:
    """Тесты dataclass ToolCall."""

    def test_create_with_defaults(self):
        """ToolCall создаётся с timestamp по умолчанию."""
        call = ToolCall(tool_name="test", success=True, latency_ms=42.0)
        assert call.tool_name == "test"
        assert call.success is True
        assert call.latency_ms == 42.0
        assert call.timestamp > 0
        assert call.error == ""

    def test_create_with_error(self):
        """ToolCall с ошибкой."""
        call = ToolCall(tool_name="test", success=False, latency_ms=100.0, error="timeout")
        assert call.success is False
        assert call.error == "timeout"


class TestMetricsCollectorEmpty:
    """Тесты пустого MetricsCollector."""

    def test_empty_stats(self):
        """Пустой collector возвращает zero stats."""
        mc = MetricsCollector()
        stats = mc.get_stats()
        assert stats["total_calls"] == 0
        assert stats["success_count"] == 0
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["error_rate"] == 0.0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["p50_latency_ms"] == 0.0
        assert stats["p99_latency_ms"] == 0.0
        assert stats["uptime_seconds"] >= 0.0
        assert stats["by_tool"] == {}


class TestMetricsCollectorRecordCall:
    """Тесты record_call."""

    def test_record_single_success(self):
        """Запись одного успешного вызова."""
        mc = MetricsCollector()
        mc.record_call("list_configs", success=True, latency_ms=42.0)
        stats = mc.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_count"] == 1
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["avg_latency_ms"] == 42.0

    def test_record_single_error(self):
        """Запись одного неуспешного вызова."""
        mc = MetricsCollector()
        mc.record_call("analyze_bsl", success=False, latency_ms=3000.0, error="timeout")
        stats = mc.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_count"] == 0
        assert stats["error_count"] == 1
        assert stats["success_rate"] == 0.0
        assert stats["error_rate"] == 1.0

    def test_record_multiple_calls(self):
        """Запись нескольких вызовов."""
        mc = MetricsCollector()
        mc.record_call("tool1", success=True, latency_ms=10.0)
        mc.record_call("tool1", success=True, latency_ms=20.0)
        mc.record_call("tool2", success=False, latency_ms=30.0, error="err")
        stats = mc.get_stats()
        assert stats["total_calls"] == 3
        assert stats["success_count"] == 2
        assert stats["error_count"] == 1
        assert stats["success_rate"] == pytest.approx(2 / 3)
        assert stats["avg_latency_ms"] == pytest.approx(20.0)


class TestMetricsCollectorPercentiles:
    """Тесты перцентилей."""

    def test_p50_p99_single_call(self):
        """p50 и p99 для одного вызова."""
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=100.0)
        stats = mc.get_stats()
        assert stats["p50_latency_ms"] == 100.0
        assert stats["p99_latency_ms"] == 100.0

    def test_p50_p99_multiple_calls(self):
        """p50 и p99 для нескольких вызовов."""
        mc = MetricsCollector()
        for latency in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            mc.record_call("tool", success=True, latency_ms=float(latency))
        stats = mc.get_stats()
        # p50 = median = 50 или 60 (зависит от реализации — 5-й или 6-й элемент)
        assert stats["p50_latency_ms"] in (50.0, 60.0)
        # p99 должен быть близок к максимуму
        assert stats["p99_latency_ms"] >= 90.0


class TestMetricsCollectorByTool:
    """Тесты метрик по каждому tool."""

    def test_by_tool_aggregation(self):
        """Агрегация метрик по tool."""
        mc = MetricsCollector()
        mc.record_call("tool1", success=True, latency_ms=10.0)
        mc.record_call("tool1", success=True, latency_ms=20.0)
        mc.record_call("tool2", success=False, latency_ms=30.0, error="err")
        stats = mc.get_stats()
        by_tool = stats["by_tool"]
        assert "tool1" in by_tool
        assert "tool2" in by_tool
        assert by_tool["tool1"]["calls"] == 2
        assert by_tool["tool1"]["errors"] == 0
        assert by_tool["tool2"]["calls"] == 1
        assert by_tool["tool2"]["errors"] == 1


class TestMetricsCollectorFormat:
    """Тесты форматирования."""

    def test_format_stats_as_json(self):
        """Форматирование stats как JSON (если поддерживается)."""
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=10.0)
        stats = mc.get_stats()
        # Проверяем, что stats — dict (сериализуемый в JSON)
        import json

        json_str = json.dumps(stats, default=str)
        assert "total_calls" in json_str


class TestMetricsCollectorUptime:
    """Тесты uptime."""

    def test_uptime_increases(self):
        """uptime_seconds увеличивается со временем."""
        mc = MetricsCollector()
        stats1 = mc.get_stats()
        time.sleep(0.01)
        stats2 = mc.get_stats()
        assert stats2["uptime_seconds"] >= stats1["uptime_seconds"]


class TestMetricsCollectorSLO:
    """Тесты SLO проверок."""

    def test_slo_empty_passes(self):
        """Пустой collector — все SLO pass."""
        mc = MetricsCollector()
        slo = mc.check_slo()
        assert slo["slo_latency_p99_lt_5s"] is True
        assert slo["slo_error_rate_lt_5pct"] is True
        assert slo["slo_success_rate_gt_95pct"] is True
        assert slo["all_slo_met"] is True

    def test_slo_all_pass(self):
        """Все SLO pass при хороших метриках."""
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=100.0)
        mc.record_call("tool", success=True, latency_ms=200.0)
        mc.record_call("tool", success=True, latency_ms=150.0)
        slo = mc.check_slo()
        assert slo["slo_latency_p99_lt_5s"] is True
        assert slo["slo_error_rate_lt_5pct"] is True
        assert slo["slo_success_rate_gt_95pct"] is True
        assert slo["all_slo_met"] is True

    def test_slo_latency_fails(self):
        """SLO latency fails при p99 >= 5s."""
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=6000.0)
        slo = mc.check_slo()
        assert slo["slo_latency_p99_lt_5s"] is False
        assert slo["all_slo_met"] is False

    def test_slo_error_rate_fails(self):
        """SLO error rate fails при >= 5% ошибок."""
        mc = MetricsCollector()
        # 1 успех, 1 ошибка = 50% error rate
        mc.record_call("tool", success=True, latency_ms=100.0)
        mc.record_call("tool", success=False, latency_ms=100.0, error="err")
        slo = mc.check_slo()
        assert slo["slo_error_rate_lt_5pct"] is False
        assert slo["all_slo_met"] is False


class TestMetricsCollectorReset:
    """Тесты reset."""

    def test_reset_clears_calls(self):
        """reset очищает вызовы."""
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=100.0)
        assert mc.get_stats()["total_calls"] == 1
        mc.reset()
        assert mc.get_stats()["total_calls"] == 0

    def test_reset_resets_start_time(self):
        """reset обновляет start_time."""
        mc = MetricsCollector()
        time.sleep(0.01)
        stats1 = mc.get_stats()
        mc.reset()
        stats2 = mc.get_stats()
        # uptime после reset должен быть меньше
        assert stats2["uptime_seconds"] <= stats1["uptime_seconds"]


class TestGlobalMetrics:
    """Тесты глобального singleton."""

    def test_get_metrics_singleton(self):
        """get_metrics возвращает тот же экземпляр."""
        from src.metrics import get_metrics, reset_metrics

        reset_metrics()
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_reset_metrics(self):
        """reset_metrics сбрасывает глобальный collector."""
        from src.metrics import get_metrics, reset_metrics

        mc = get_metrics()
        mc.record_call("tool", success=True, latency_ms=100.0)
        assert mc.get_stats()["total_calls"] == 1
        reset_metrics()
        assert mc.get_stats()["total_calls"] == 0
