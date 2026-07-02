"""
Тесты для src/metrics.py — SLO/SLI метрики для MCP.
"""

from __future__ import annotations

import time

import pytest

from src.metrics import MetricsCollector, get_metrics, reset_metrics


class TestMetricsCollector:
    def test_empty_stats(self):
        mc = MetricsCollector()
        stats = mc.get_stats()
        assert stats["total_calls"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["by_tool"] == {}

    def test_single_successful_call(self):
        mc = MetricsCollector()
        mc.record_call("list_configs", success=True, latency_ms=42)
        stats = mc.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_count"] == 1
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["avg_latency_ms"] == 42

    def test_single_failed_call(self):
        mc = MetricsCollector()
        mc.record_call("analyze_bsl", success=False, latency_ms=3000, error="timeout")
        stats = mc.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_count"] == 0
        assert stats["error_count"] == 1
        assert stats["error_rate"] == 1.0
        assert stats["avg_latency_ms"] == 3000

    def test_mixed_calls(self):
        mc = MetricsCollector()
        mc.record_call("list_configs", success=True, latency_ms=10)
        mc.record_call("analyze_bsl", success=True, latency_ms=100)
        mc.record_call("search", success=False, latency_ms=500, error="not found")
        mc.record_call("list_configs", success=True, latency_ms=20)
        stats = mc.get_stats()
        assert stats["total_calls"] == 4
        assert stats["success_count"] == 3
        assert stats["error_count"] == 1
        assert stats["success_rate"] == 0.75
        assert stats["error_rate"] == 0.25

    def test_percentiles(self):
        mc = MetricsCollector()
        for i in range(100):
            mc.record_call("tool", success=True, latency_ms=float(i + 1))
        stats = mc.get_stats()
        # p50 = latency[50] = 51
        assert 49 <= stats["p50_latency_ms"] <= 52
        # p99 = latency[99] = 100
        assert 98 <= stats["p99_latency_ms"] <= 100

    def test_by_tool_stats(self):
        mc = MetricsCollector()
        mc.record_call("list_configs", success=True, latency_ms=10)
        mc.record_call("list_configs", success=True, latency_ms=30)
        mc.record_call("search", success=False, latency_ms=500)
        stats = mc.get_stats()
        assert "list_configs" in stats["by_tool"]
        assert "search" in stats["by_tool"]
        assert stats["by_tool"]["list_configs"]["calls"] == 2
        assert stats["by_tool"]["list_configs"]["errors"] == 0
        assert stats["by_tool"]["list_configs"]["success_rate"] == 1.0
        assert stats["by_tool"]["search"]["calls"] == 1
        assert stats["by_tool"]["search"]["errors"] == 1
        assert stats["by_tool"]["search"]["success_rate"] == 0.0

    def test_avg_latency_by_tool(self):
        mc = MetricsCollector()
        mc.record_call("tool_a", success=True, latency_ms=100)
        mc.record_call("tool_a", success=True, latency_ms=300)
        stats = mc.get_stats()
        assert stats["by_tool"]["tool_a"]["avg_latency_ms"] == 200

    def test_uptime(self):
        mc = MetricsCollector()
        time.sleep(0.1)
        stats = mc.get_stats()
        assert stats["uptime_seconds"] >= 0.1

    def test_reset(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=10)
        mc.reset()
        stats = mc.get_stats()
        assert stats["total_calls"] == 0

    def test_error_message_stored(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=False, latency_ms=100, error="something went wrong")
        # Error message is stored in the call record
        assert len(mc._calls) == 1
        assert mc._calls[0].error == "something went wrong"


class TestSLO:
    def test_all_slo_met_with_no_calls(self):
        mc = MetricsCollector()
        slo = mc.check_slo()
        # Empty — all SLOs pass (no data to fail)
        assert slo["all_slo_met"] is True

    def test_slo_latency_pass(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=100)
        slo = mc.check_slo()
        assert slo["slo_latency_p99_lt_5s"] is True

    def test_slo_latency_fail(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=6000)
        slo = mc.check_slo()
        assert slo["slo_latency_p99_lt_5s"] is False

    def test_slo_error_rate_pass(self):
        mc = MetricsCollector()
        for _ in range(100):
            mc.record_call("tool", success=True, latency_ms=10)
        mc.record_call("tool", success=False, latency_ms=10)  # 1/101 = ~1%
        slo = mc.check_slo()
        assert slo["slo_error_rate_lt_5pct"] is True

    def test_slo_error_rate_fail(self):
        mc = MetricsCollector()
        for _ in range(10):
            mc.record_call("tool", success=True, latency_ms=10)
        for _ in range(10):
            mc.record_call("tool", success=False, latency_ms=10)  # 50%
        slo = mc.check_slo()
        assert slo["slo_error_rate_lt_5pct"] is False

    def test_slo_success_rate_pass(self):
        mc = MetricsCollector()
        for _ in range(96):
            mc.record_call("tool", success=True, latency_ms=10)
        for _ in range(4):
            mc.record_call("tool", success=False, latency_ms=10)  # 96%
        slo = mc.check_slo()
        assert slo["slo_success_rate_gt_95pct"] is True

    def test_slo_success_rate_fail(self):
        mc = MetricsCollector()
        for _ in range(90):
            mc.record_call("tool", success=True, latency_ms=10)
        for _ in range(10):
            mc.record_call("tool", success=False, latency_ms=10)  # 90%
        slo = mc.check_slo()
        assert slo["slo_success_rate_gt_95pct"] is False

    def test_all_slo_met_all_pass(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=True, latency_ms=100)
        slo = mc.check_slo()
        assert slo["all_slo_met"] is True

    def test_all_slo_met_one_fails(self):
        mc = MetricsCollector()
        mc.record_call("tool", success=False, latency_ms=100)
        slo = mc.check_slo()
        assert slo["all_slo_met"] is False


class TestGlobalMetrics:
    def test_singleton(self):
        reset_metrics()
        mc1 = get_metrics()
        mc2 = get_metrics()
        assert mc1 is mc2

    def test_global_reset(self):
        reset_metrics()
        mc = get_metrics()
        mc.record_call("tool", success=True, latency_ms=10)
        assert mc.get_stats()["total_calls"] == 1
        reset_metrics()
        mc = get_metrics()
        assert mc.get_stats()["total_calls"] == 0
