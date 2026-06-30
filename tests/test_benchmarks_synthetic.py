#!/usr/bin/env python3
"""
Synthetic benchmarks — SLA на ключевые операции БЕЗ зависимости от реальных данных.

Эти бенчмарки работают всегда (не нужны UT11 данные).
Запускаются в CI на каждый PR — ловят регрессии производительности.

SLA (Service Level Agreement):
- Configuration roundtrip: < 1 мс
- CheckResult.verdict: < 0.1 мс
- SARIF convert (10 violations): < 5 мс
- TaskContext.to_dict: < 0.5 мс
- JSON serialize CheckResult: < 2 мс

Запуск:
    pytest tests/test_benchmarks_synthetic.py -v --benchmark-only
    pytest tests/test_benchmarks_synthetic.py --benchmark-compare=baseline
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.task import (
    TaskContext,
    CheckResult,
    Violation,
    CodeMetric,
    PlatformMethodHit,
    ModuleApiHit,
)
from src.models.configuration import Configuration
from src.services.sarif_reporter import SarifReporter


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_violations(n: int) -> list[Violation]:
    return [
        Violation(
            source="check_1c_standards",
            rule_id=f"rule-{i}",
            severity="error" if i % 3 == 0 else "warning",
            line=i * 10,
            message=f"Violation {i}: detailed message about the issue",
            file=f"/path/to/file_{i}.bsl",
        )
        for i in range(n)
    ]


def _make_check_result(n_violations: int = 10) -> CheckResult:
    result = CheckResult(
        file="/path/to/module.bsl",
        level="standard",
        violations=_make_violations(n_violations),
        analyzers_run=["check_1c_standards", "security_auditor"],
    )
    return result


def _make_check_result_with_metrics() -> CheckResult:
    result = _make_check_result(15)
    result.metrics = CodeMetric(
        loc=500,
        lloc=400,
        cyclomatic_complexity=42.0,
        cognitive_complexity=120.0,
        max_nesting=5,
        methods_count=12,
        is_god_object=False,
        long_methods=[{"name": "LongMethod", "lloc": 80, "line_start": 50}],
        health_score=72.5,
    )
    return result


# ─────────────────────────────────────────────
# Configuration roundtrip
# ─────────────────────────────────────────────

class TestBenchmarkConfiguration:
    """SLA: Configuration dataclass операции."""

    @pytest.mark.benchmark(group="model")
    def test_bench_configuration_creation(self, benchmark):
        """Создание Configuration dataclass."""
        def create():
            return Configuration(
                name="ut11",
                title="УТ 11",
                version="11.3.4",
                vendor="1C",
                objects_count=7128,
                api_methods_count=21380,
                status="active",
            )
        result = benchmark(create)
        assert result.name == "ut11"

    @pytest.mark.benchmark(group="model")
    def test_bench_configuration_to_dict(self, benchmark):
        """Configuration.to_dict()."""
        cfg = Configuration(
            name="ut11", title="УТ 11", version="11.3.4",
            objects_count=7128, status="active",
        )
        d = benchmark(cfg.to_dict)
        assert d["name"] == "УТ 11"

    @pytest.mark.benchmark(group="model")
    def test_bench_configuration_roundtrip(self, benchmark):
        """Полный roundtrip: to_dict() → from_dict()."""
        cfg = Configuration(
            name="ut11", title="УТ 11", version="11.3.4",
            objects_count=7128, status="active",
        )

        def roundtrip():
            d = cfg.to_dict()
            return Configuration.from_dict("ut11", d, project_root=Path("."))

        result = benchmark(roundtrip)
        assert result.version == "11.3.4"


# ─────────────────────────────────────────────
# CheckResult / Violation
# ─────────────────────────────────────────────

class TestBenchmarkCheckResult:
    """SLA: CheckResult и Violation операции."""

    @pytest.mark.benchmark(group="model")
    def test_bench_violation_creation(self, benchmark):
        """Создание одного Violation."""
        def create():
            return Violation(
                source="check_1c_standards",
                rule_id="no-yo-in-code",
                severity="warning",
                line=42,
                message="Найдена буква ё",
                file="module.bsl",
            )
        v = benchmark(create)
        assert v.line == 42

    @pytest.mark.benchmark(group="model")
    def test_bench_check_result_verdict(self, benchmark):
        """CheckResult.verdict property."""
        result = _make_check_result(50)  # 50 violations
        v = benchmark(lambda: result.verdict)
        assert v in ("ready", "warnings", "errors")

    @pytest.mark.benchmark(group="model")
    def test_bench_check_result_total_errors(self, benchmark):
        """CheckResult.total_errors property."""
        result = _make_check_result(100)  # 100 violations
        n = benchmark(lambda: result.total_errors)
        assert n > 0

    @pytest.mark.benchmark(group="model")
    def test_bench_check_result_to_dict(self, benchmark):
        """CheckResult.to_dict() с 10 violations."""
        result = _make_check_result(10)
        d = benchmark(result.to_dict)
        assert "violations" in d

    @pytest.mark.benchmark(group="model")
    def test_bench_check_result_to_dict_large(self, benchmark):
        """CheckResult.to_dict() с 100 violations."""
        result = _make_check_result(100)
        d = benchmark(result.to_dict)
        assert len(d["violations"]) == 100


# ─────────────────────────────────────────────
# SARIF
# ─────────────────────────────────────────────

class TestBenchmarkSarif:
    """SLA: SARIF конвертация."""

    @pytest.mark.benchmark(group="sarif")
    def test_bench_sarif_convert_10(self, benchmark):
        """SARIF конвертация 10 violations."""
        result = _make_check_result(10)
        reporter = SarifReporter()
        sarif = benchmark(reporter.convert, result)
        assert sarif["version"] == "2.1.0"

    @pytest.mark.benchmark(group="sarif")
    def test_bench_sarif_convert_100(self, benchmark):
        """SARIF конвертация 100 violations."""
        result = _make_check_result(100)
        reporter = SarifReporter()
        sarif = benchmark(reporter.convert, result)
        assert len(sarif["runs"][0]["results"]) >= 100

    @pytest.mark.benchmark(group="sarif")
    def test_bench_sarif_convert_with_metrics(self, benchmark):
        """SARIF конвертация с метриками (full level)."""
        result = _make_check_result_with_metrics()
        reporter = SarifReporter()
        sarif = benchmark(reporter.convert, result)
        assert sarif["version"] == "2.1.0"

    @pytest.mark.benchmark(group="sarif")
    def test_bench_sarif_write(self, benchmark, tmp_path):
        """SARIF запись в файл."""
        result = _make_check_result(20)
        reporter = SarifReporter()
        out = tmp_path / "bench.sarif"

        def write():
            return reporter.write(result, out)

        path = benchmark(write)
        assert path.exists()

    @pytest.mark.benchmark(group="sarif")
    def test_bench_sarif_convert_multiple(self, benchmark):
        """SARIF конвертация 5 CheckResult (multi-file PR)."""
        results = [_make_check_result(10) for _ in range(5)]
        reporter = SarifReporter()
        sarif = benchmark(reporter.convert_multiple, results)
        assert len(sarif["runs"][0]["results"]) >= 50


# ─────────────────────────────────────────────
# TaskContext
# ─────────────────────────────────────────────

class TestBenchmarkTaskContext:
    """SLA: TaskContext операции."""

    @pytest.mark.benchmark(group="task")
    def test_bench_task_context_creation(self, benchmark):
        """Создание TaskContext."""
        def create():
            return TaskContext(query="создать справочник", config_name="ut11")
        ctx = benchmark(create)
        assert ctx.query == "создать справочник"

    @pytest.mark.benchmark(group="task")
    def test_bench_task_context_total_hits(self, benchmark):
        """TaskContext.total_hits property."""
        ctx = TaskContext(query="test")
        ctx.platform_methods = [PlatformMethodHit() for _ in range(10)]
        ctx.api_modules = [ModuleApiHit() for _ in range(5)]
        ctx.metadata_objects = []
        ctx.skd_schemas = []  # убрал object() — нужен SkdSchemaHit
        n = benchmark(lambda: ctx.total_hits)
        assert n == 15

    @pytest.mark.benchmark(group="task")
    def test_bench_task_context_to_dict(self, benchmark):
        """TaskContext.to_dict() с 20 элементами."""
        ctx = TaskContext(query="создать справочник", config_name="ut11")
        ctx.platform_methods = [PlatformMethodHit(name_ru=f"Метод{i}") for i in range(10)]
        ctx.api_modules = [ModuleApiHit(name=f"Module{i}") for i in range(10)]
        d = benchmark(ctx.to_dict)
        assert len(d["platform_methods"]) == 10


# ─────────────────────────────────────────────
# JSON serialization
# ─────────────────────────────────────────────

class TestBenchmarkJsonSerialization:
    """SLA: JSON сериализация (важно для MCP/CLI вывода)."""

    @pytest.mark.benchmark(group="json")
    def test_bench_json_serialize_check_result(self, benchmark):
        """json.dumps(CheckResult.to_dict()) с 10 violations."""
        result = _make_check_result(10)
        d = result.to_dict()
        s = benchmark(json.dumps, d, ensure_ascii=False)
        assert len(s) > 100

    @pytest.mark.benchmark(group="json")
    def test_bench_json_serialize_sarif(self, benchmark):
        """json.dumps(SARIF) с 50 violations."""
        result = _make_check_result(50)
        sarif = SarifReporter().convert(result)
        s = benchmark(json.dumps, sarif, ensure_ascii=False)
        assert '"version": "2.1.0"' in s

    @pytest.mark.benchmark(group="json")
    def test_bench_json_parse_sarif(self, benchmark):
        """json.loads(SARIF строка)."""
        result = _make_check_result(50)
        sarif = SarifReporter().convert(result)
        sarif_str = json.dumps(sarif, ensure_ascii=False)
        d = benchmark(json.loads, sarif_str)
        assert d["version"] == "2.1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
