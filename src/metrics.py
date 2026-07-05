"""
metrics.py — SLO/SLI метрики для MCP-сервера.

P3.7: Мониторинг здоровья MCP-сервера через structlog events.
Метрики логируются в stderr (JSON для CI, console для dev).

SLO (Service Level Objectives):
- tool_call_latency_p99 < 5s (99% запросов быстрее 5 сек)
- tool_call_error_rate < 5% (< 5% запросов завершаются ошибкой)
- tool_call_success_rate > 95%

Использование:
    from src.metrics import MetricsCollector

    mc = MetricsCollector()
    mc.record_call("list_configs", success=True, latency_ms=42)
    mc.record_call("analyze_bsl", success=False, latency_ms=3000, error="timeout")

    stats = mc.get_stats()
    # {"total_calls": 2, "success_rate": 0.5, "avg_latency_ms": 1521, ...}
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Запись об одном вызове MCP tool."""

    tool_name: str
    success: bool
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    error: str = ""


class MetricsCollector:
    """Сборщик SLO/SLI метрик для MCP tools.

    Потокобезопасность: НЕ потокобезопасен (MCP-сервер однопоточный через stdio).
    """

    def __init__(self) -> None:
        self._calls: list[ToolCall] = []
        self._start_time: float = time.time()

    def record_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: str = "",
    ) -> None:
        """Записать вызов MCP tool."""
        self._calls.append(
            ToolCall(
                tool_name=tool_name,
                success=success,
                latency_ms=latency_ms,
                error=error,
            )
        )

    def get_stats(self) -> dict[str, Any]:
        """Получить агрегированные метрики.

        Returns:
            dict[str, Any] с ключами:
            - total_calls: общее кол-во вызовов
            - success_count / error_count
            - success_rate: 0.0-1.0
            - error_rate: 0.0-1.0
            - avg_latency_ms: средняя задержка
            - p50_latency_ms: медиана
            - p99_latency_ms: 99-й перцентиль
            - uptime_seconds: время работы
            - by_tool: метрики по каждому tool
        """
        if not self._calls:
            return {
                "total_calls": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "uptime_seconds": time.time() - self._start_time,
                "by_tool": {},
            }

        total = len(self._calls)
        successes = sum(1 for c in self._calls if c.success)
        errors = total - successes
        latencies = sorted(c.latency_ms for c in self._calls)

        # Перцентили
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0]

        # По каждому tool
        by_tool: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "errors": 0, "total_latency": 0.0})
        for call in self._calls:
            by_tool[call.tool_name]["calls"] += 1
            if not call.success:
                by_tool[call.tool_name]["errors"] += 1
            by_tool[call.tool_name]["total_latency"] += call.latency_ms

        # Финализируем by_tool
        tool_stats: dict[str, Any] = {}
        for name, s in by_tool.items():
            tool_stats[name] = {
                "calls": s["calls"],
                "errors": s["errors"],
                "success_rate": (s["calls"] - s["errors"]) / s["calls"] if s["calls"] > 0 else 0.0,
                "avg_latency_ms": s["total_latency"] / s["calls"] if s["calls"] > 0 else 0.0,
            }

        return {
            "total_calls": total,
            "success_count": successes,
            "error_count": errors,
            "success_rate": successes / total if total > 0 else 0.0,
            "error_rate": errors / total if total > 0 else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": p50,
            "p99_latency_ms": p99,
            "uptime_seconds": time.time() - self._start_time,
            "by_tool": dict[str, Any](tool_stats),
        }

    def check_slo(self) -> dict[str, bool]:
        """Проверить SLO (Service Level Objectives).

        Returns:
            dict[str, Any] с ключами-результатами SLO проверок
        """
        stats = self.get_stats()

        # Нет данных — все SLO pass (нет evidence нарушения)
        if stats["total_calls"] == 0:
            return {
                "slo_latency_p99_lt_5s": True,
                "slo_error_rate_lt_5pct": True,
                "slo_success_rate_gt_95pct": True,
                "all_slo_met": True,
            }

        # SLO: p99 latency < 5000ms (5 секунд)
        slo_latency = stats["p99_latency_ms"] < 5000

        # SLO: error rate < 5%
        slo_error_rate = stats["error_rate"] < 0.05

        # SLO: success rate > 95%
        slo_success_rate = stats["success_rate"] > 0.95

        return {
            "slo_latency_p99_lt_5s": slo_latency,
            "slo_error_rate_lt_5pct": slo_error_rate,
            "slo_success_rate_gt_95pct": slo_success_rate,
            "all_slo_met": slo_latency and slo_error_rate and slo_success_rate,
        }

    def reset(self) -> None:
        """Сбросить метрики (для тестов)."""
        self._calls.clear()
        self._start_time = time.time()


# Глобальный экземпляр (singleton)
_global_collector: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Получить глобальный MetricsCollector (singleton)."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def reset_metrics() -> None:
    """Сбросить глобальный MetricsCollector (для тестов)."""
    global _global_collector
    if _global_collector is not None:
        _global_collector.reset()
