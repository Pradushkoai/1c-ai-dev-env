"""
M8 (2026-07-06): Тесты для Production-Ready checks (QG-1, QG-2, QG-4, DOC-1).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.production_ready import (
    CoverageReport,
    DocsStatus,
    KEY_DOCS,
    PerformanceBaseline,
    QualityGate,
    QualityGatesReport,
    check_docs_status,
    check_quality_gates,
    get_coverage_report,
    get_performance_baseline,
)


# ============================================================================
# QualityGate dataclass tests
# ============================================================================


class TestQualityGate:
    def test_creation(self) -> None:
        g = QualityGate(name="test", description="Test gate", target="100%")
        assert g.name == "test"
        assert g.passed is False
        assert g.current == ""

    def test_passed_flag(self) -> None:
        g = QualityGate(name="test", description="Test", target="0", passed=True)
        assert g.passed is True


class TestQualityGatesReport:
    def test_defaults(self) -> None:
        r = QualityGatesReport()
        assert r.gates == []
        assert r.total == 0
        assert r.all_passed is False

    def test_all_passed_true(self) -> None:
        r = QualityGatesReport()
        r.gates = [QualityGate("a", "A", "1", passed=True)]
        r.total = 1
        r.passed = 1
        assert r.all_passed is True

    def test_all_passed_false(self) -> None:
        r = QualityGatesReport()
        r.gates = [
            QualityGate("a", "A", "1", passed=True),
            QualityGate("b", "B", "1", passed=False),
        ]
        r.total = 2
        r.passed = 1
        r.failed = 1
        assert r.all_passed is False

    def test_pass_rate(self) -> None:
        r = QualityGatesReport()
        r.total = 4
        r.passed = 3
        assert r.pass_rate == 0.75

    def test_to_json(self) -> None:
        r = QualityGatesReport()
        r.gates = [QualityGate("a", "A", "1", passed=True)]
        r.total = 1
        r.passed = 1
        js = r.to_json()
        data = json.loads(js)
        assert data["all_passed"] is True


# ============================================================================
# check_quality_gates tests
# ============================================================================


class TestCheckQualityGates:
    def test_returns_report(self, tmp_path: Path) -> None:
        """Возвращает QualityGatesReport."""
        # Создаём минимальную структуру
        (tmp_path / "README.md").write_text("# Test", encoding="utf-8")
        (tmp_path / "ROADMAP.md").write_text("# Roadmap", encoding="utf-8")

        report = check_quality_gates(tmp_path)
        assert isinstance(report, QualityGatesReport)
        assert report.total > 0

    def test_includes_coverage_gate(self, tmp_path: Path) -> None:
        report = check_quality_gates(tmp_path)
        names = [g.name for g in report.gates]
        assert "coverage" in names

    def test_includes_mypy_gate(self, tmp_path: Path) -> None:
        report = check_quality_gates(tmp_path)
        names = [g.name for g in report.gates]
        assert "mypy_strict" in names

    def test_includes_ruff_gate(self, tmp_path: Path) -> None:
        report = check_quality_gates(tmp_path)
        names = [g.name for g in report.gates]
        assert "ruff_lint" in names

    def test_includes_tests_gate(self, tmp_path: Path) -> None:
        report = check_quality_gates(tmp_path)
        names = [g.name for g in report.gates]
        assert "tests_pass" in names

    def test_includes_docs_gate(self, tmp_path: Path) -> None:
        report = check_quality_gates(tmp_path)
        names = [g.name for g in report.gates]
        assert "docs_exist" in names

    def test_docs_gate_passed_when_docs_exist(self, tmp_path: Path) -> None:
        """Docs gate проходит когда все docs существуют."""
        # Создаём все key docs
        for doc in KEY_DOCS:
            doc_path = tmp_path / doc
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(f"# {doc}", encoding="utf-8")

        report = check_quality_gates(tmp_path)
        docs_gate = next(g for g in report.gates if g.name == "docs_exist")
        assert docs_gate.passed


# ============================================================================
# Coverage report tests (QG-2)
# ============================================================================


class TestCoverageReport:
    def test_defaults(self) -> None:
        r = CoverageReport()
        assert r.total_coverage == 0.0
        assert r.target == 80.0

    def test_passed_when_above_target(self) -> None:
        r = CoverageReport(total_coverage=85.0, target=80.0)
        assert r.passed is True

    def test_failed_when_below_target(self) -> None:
        r = CoverageReport(total_coverage=70.0, target=80.0)
        assert r.passed is False

    def test_gap_calculation(self) -> None:
        r = CoverageReport(total_coverage=72.0, target=80.0)
        assert r.gap == 8.0

    def test_gap_zero_when_above_target(self) -> None:
        r = CoverageReport(total_coverage=85.0, target=80.0)
        assert r.gap == 0.0


class TestGetCoverageReport:
    def test_returns_report(self, tmp_path: Path) -> None:
        report = get_coverage_report(tmp_path)
        assert isinstance(report, CoverageReport)


# ============================================================================
# Performance baseline tests (QG-4)
# ============================================================================


class TestPerformanceBaseline:
    def test_defaults(self) -> None:
        b = PerformanceBaseline()
        assert b.test_count == 0
        assert b.test_duration_sec == 0.0

    def test_to_dict(self) -> None:
        b = PerformanceBaseline(test_count=100, test_duration_sec=10.0)
        d = b.to_dict()
        assert d["test_count"] == 100


class TestGetPerformanceBaseline:
    def test_returns_baseline(self, tmp_path: Path) -> None:
        baseline = get_performance_baseline(tmp_path)
        assert isinstance(baseline, PerformanceBaseline)
        assert baseline.timestamp  # не пустой
        assert baseline.python_version  # не пустой


# ============================================================================
# Documentation status tests (DOC-1)
# ============================================================================


class TestDocsStatus:
    def test_defaults(self) -> None:
        s = DocsStatus()
        assert s.key_docs == {}
        assert s.missing == []

    def test_all_exist_true(self) -> None:
        s = DocsStatus()
        s.total = 5
        s.existing = 5
        assert s.all_exist is True

    def test_all_exist_false(self) -> None:
        s = DocsStatus()
        s.total = 5
        s.existing = 3
        s.missing = ["doc1", "doc2"]
        assert s.all_exist is False


class TestCheckDocsStatus:
    def test_returns_status(self, tmp_path: Path) -> None:
        status = check_docs_status(tmp_path)
        assert isinstance(status, DocsStatus)
        assert status.total == len(KEY_DOCS)

    def test_missing_docs_detected(self, tmp_path: Path) -> None:
        """Несуществующие docs обнаруживаются."""
        status = check_docs_status(tmp_path)
        assert len(status.missing) > 0
        assert status.all_exist is False

    def test_all_docs_exist(self, tmp_path: Path) -> None:
        """Все docs существуют."""
        for doc in KEY_DOCS:
            doc_path = tmp_path / doc
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(f"# {doc}", encoding="utf-8")

        status = check_docs_status(tmp_path)
        assert status.all_exist is True
        assert len(status.missing) == 0

    def test_key_docs_includes_readme(self) -> None:
        assert "README.md" in KEY_DOCS

    def test_key_docs_includes_roadmap(self) -> None:
        assert "ROADMAP.md" in KEY_DOCS


# ============================================================================
# Integration tests
# ============================================================================


class TestIntegration:
    def test_all_checks_run_without_crash(self, tmp_path: Path) -> None:
        """Все checks запускаются без crash."""
        # Создаём минимальные docs
        (tmp_path / "README.md").write_text("# Test", encoding="utf-8")

        gates = check_quality_gates(tmp_path)
        assert isinstance(gates, QualityGatesReport)

        coverage = get_coverage_report(tmp_path)
        assert isinstance(coverage, CoverageReport)

        docs = check_docs_status(tmp_path)
        assert isinstance(docs, DocsStatus)

    def test_quality_gates_report_is_serializable(self, tmp_path: Path) -> None:
        """Отчёт quality gates сериализуется в JSON."""
        report = check_quality_gates(tmp_path)
        js = report.to_json()
        data = json.loads(js)
        assert "gates" in data
        assert "all_passed" in data
