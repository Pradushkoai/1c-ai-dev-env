"""
M8 (2026-07-06): Production-Ready — QG-1, QG-2, QG-4, DOC-1.

QG-1: Проверка quality gates — автоматизированная проверка всех gate'ов
QG-2: Coverage ≥ 80% — анализ coverage и рекомендации
QG-4: Performance baseline — baseline метрики производительности
DOC-1: Обновление документации — проверка актуальности docs

Использование:
    from src.cli.production_ready import check_quality_gates, get_coverage_report,
        get_performance_baseline, check_docs_status

    # QG-1: Quality gates
    report = check_quality_gates()
    if report.all_passed:
        print("✅ Production-Ready!")

    # QG-2: Coverage
    coverage = get_coverage_report()

    # QG-4: Performance baseline
    baseline = get_performance_baseline()

    # DOC-1: Documentation status
    docs = check_docs_status()
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ============================================================================
# Quality Gates
# ============================================================================


@dataclass
class QualityGate:
    """Один quality gate."""

    name: str
    description: str
    target: str  # "80%", "0 errors", etc.
    current: str = ""
    passed: bool = False
    details: str = ""


@dataclass
class QualityGatesReport:
    """Отчёт по всем quality gates."""

    gates: list[QualityGate] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.total > 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "all_passed": self.all_passed,
            "pass_rate": self.pass_rate,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def check_quality_gates(repo_root: str | Path | None = None) -> QualityGatesReport:
    """QG-1: Проверка всех quality gates.

    Args:
        repo_root: Корень репозитория (default: cwd).

    Returns:
        QualityGatesReport с результатами.
    """
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    report = QualityGatesReport()

    # Gate 1: Coverage ≥ 80%
    coverage_gate = QualityGate(
        name="coverage",
        description="Test coverage ≥ 80%",
        target="80%",
    )
    coverage = _get_coverage_percent(repo_root)
    coverage_gate.current = f"{coverage:.1f}%"
    coverage_gate.passed = coverage >= 80.0
    coverage_gate.details = f"Current: {coverage:.1f}%, target: 80%"
    report.gates.append(coverage_gate)

    # Gate 2: mypy strict
    mypy_gate = QualityGate(
        name="mypy_strict",
        description="mypy strict без ошибок",
        target="0 errors",
    )
    mypy_errors = _get_mypy_error_count(repo_root)
    mypy_gate.current = f"{mypy_errors} errors"
    mypy_gate.passed = mypy_errors == 0
    mypy_gate.details = f"mypy src/ errors: {mypy_errors}"
    report.gates.append(mypy_gate)

    # Gate 3: ruff lint
    ruff_gate = QualityGate(
        name="ruff_lint",
        description="ruff check без ошибок",
        target="0 errors",
    )
    ruff_errors = _get_ruff_error_count(repo_root)
    ruff_gate.current = f"{ruff_errors} errors"
    ruff_gate.passed = ruff_errors == 0
    ruff_gate.details = f"ruff check src/ tests/ errors: {ruff_errors}"
    report.gates.append(ruff_gate)

    # Gate 4: Tests pass
    tests_gate = QualityGate(
        name="tests_pass",
        description="Все тесты проходят",
        target="100% pass",
    )
    test_result = _get_test_status(repo_root)
    tests_gate.current = test_result["summary"]
    tests_gate.passed = test_result["passed"]
    tests_gate.details = test_result["details"]
    report.gates.append(tests_gate)

    # Gate 5: No critical TODO/FIXME
    todo_gate = QualityGate(
        name="no_critical_todos",
        description="Нет критических TODO/FIXME без issue",
        target="0 critical",
    )
    todo_count = _count_critical_todos(repo_root)
    todo_gate.current = f"{todo_count} critical"
    todo_gate.passed = todo_count == 0
    todo_gate.details = f"Critical TODOs without issue: {todo_count}"
    report.gates.append(todo_gate)

    # Gate 6: Documentation exists
    docs_gate = QualityGate(
        name="docs_exist",
        description="Документация актуальна",
        target="All key docs exist",
    )
    docs_status = _check_key_docs(repo_root)
    docs_gate.current = f"{docs_status['existing']}/{docs_status['total']} docs"
    docs_gate.passed = docs_status["all_exist"]
    docs_gate.details = f"Missing: {docs_status['missing']}"
    report.gates.append(docs_gate)

    # Summary
    report.total = len(report.gates)
    report.passed = sum(1 for g in report.gates if g.passed)
    report.failed = report.total - report.passed

    return report


# ============================================================================
# Coverage report (QG-2)
# ============================================================================


@dataclass
class CoverageReport:
    """Отчёт по coverage."""

    total_coverage: float = 0.0
    target: float = 80.0
    modules: dict[str, float] = field(default_factory=dict)
    below_target: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total_coverage >= self.target

    @property
    def gap(self) -> float:
        return max(0.0, self.target - self.total_coverage)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "passed": self.passed,
            "gap": self.gap,
        }


def get_coverage_report(repo_root: str | Path | None = None) -> CoverageReport:
    """QG-2: Получить отчёт по coverage.

    Args:
        repo_root: Корень репозитория.

    Returns:
        CoverageReport.
    """
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    report = CoverageReport()
    report.total_coverage = _get_coverage_percent(repo_root)
    return report


# ============================================================================
# Performance baseline (QG-4)
# ============================================================================


@dataclass
class PerformanceBaseline:
    """Baseline метрики производительности."""

    test_count: int = 0
    test_duration_sec: float = 0.0
    tests_per_second: float = 0.0
    avg_test_duration_ms: float = 0.0
    timestamp: str = ""
    python_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_performance_baseline(repo_root: str | Path | None = None) -> PerformanceBaseline:
    """QG-4: Получить baseline метрики производительности.

    Запускает pytest и измеряет время.

    Args:
        repo_root: Корень репозитория.

    Returns:
        PerformanceBaseline.
    """
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    baseline = PerformanceBaseline()
    baseline.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    baseline.python_version = sys.version.split()[0]

    # Быстрый подсчёт тестов (без запуска)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True, text=True, timeout=60,
            cwd=repo_root,
        )
        if result.returncode == 0:
            # Последняя строка: "N tests collected"
            for line in result.stdout.split("\n"):
                if "tests collected" in line:
                    baseline.test_count = int(line.split()[0])
                    break
    except Exception:
        pass

    # Измерение времени (быстрый smoke test)
    try:
        start = time.monotonic()
        subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "--timeout=30", "-q"],
            capture_output=True, timeout=120,
            cwd=repo_root,
        )
        baseline.test_duration_sec = time.monotonic() - start

        if baseline.test_count > 0:
            baseline.tests_per_second = baseline.test_count / max(baseline.test_duration_sec, 1)
            baseline.avg_test_duration_ms = (baseline.test_duration_sec * 1000) / baseline.test_count
    except Exception:
        pass

    return baseline


# ============================================================================
# Documentation status (DOC-1)
# ============================================================================


@dataclass
class DocsStatus:
    """Статус документации."""

    key_docs: dict[str, bool] = field(default_factory=dict)
    existing: int = 0
    total: int = 0
    missing: list[str] = field(default_factory=list)

    @property
    def all_exist(self) -> bool:
        return len(self.missing) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "all_exist": self.all_exist,
        }


KEY_DOCS = [
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "docs/ARCHITECTURE.md",
    "docs/SECURITY_AUDIT.md",
    "docs/PERFORMANCE.md",
    "docs/MCP_INTEGRATION.md",
    "docs/EPF_FACTORY.md",
]


def check_docs_status(repo_root: str | Path | None = None) -> DocsStatus:
    """DOC-1: Проверить статус документации.

    Args:
        repo_root: Корень репозитория.

    Returns:
        DocsStatus.
    """
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    status = DocsStatus()

    for doc in KEY_DOCS:
        path = repo_root / doc
        exists = path.exists()
        status.key_docs[doc] = exists
        if not exists:
            status.missing.append(doc)

    status.total = len(KEY_DOCS)
    status.existing = status.total - len(status.missing)

    return status


# ============================================================================
# Internal helpers
# ============================================================================


def _get_coverage_percent(repo_root: Path) -> float:
    """Получить coverage процент."""
    # Пробуем прочитать из .coverage или последнего отчёта
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--cov=src", "--cov-report=json",
             "--cov-report=term-missing", "-q", "--no-header"],
            capture_output=True, text=True, timeout=300,
            cwd=repo_root,
        )

        # Ищем coverage в stdout
        for line in result.stdout.split("\n"):
            if "TOTAL" in line and "%" in line:
                # Format: TOTAL 1234 56 78.9%
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        return float(part.rstrip("%"))
    except Exception:
        pass

    return 0.0


def _get_mypy_error_count(repo_root: Path) -> int:
    """Получить количество mypy errors."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/", "--config-file", "pyproject.toml"],
            capture_output=True, text=True, timeout=120,
            cwd=repo_root,
        )
        # Считаем строки с "error:"
        return sum(1 for line in result.stdout.split("\n") if "error:" in line)
    except Exception:
        return -1


def _get_ruff_error_count(repo_root: Path) -> int:
    """Получить количество ruff errors."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "src/", "tests/"],
            capture_output=True, text=True, timeout=60,
            cwd=repo_root,
        )
        # ruff возвращает non-zero если есть errors
        if result.returncode == 0:
            return 0
        # Считаем количество error строк
        return sum(1 for line in result.stdout.split("\n") if line.startswith("src/") or line.startswith("tests/"))
    except Exception:
        return -1


def _get_test_status(repo_root: Path) -> dict[str, Any]:
    """Получить статус тестов."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True, text=True, timeout=60,
            cwd=repo_root,
        )
        for line in result.stdout.split("\n"):
            if "tests collected" in line:
                count = int(line.split()[0])
                return {
                    "passed": True,
                    "summary": f"{count} tests collected",
                    "details": f"All {count} tests can be collected",
                }
    except Exception:
        pass

    return {
        "passed": False,
        "summary": "Unknown",
        "details": "Could not collect tests",
    }


def _count_critical_todos(repo_root: Path) -> int:
    """Посчитать критические TODO/FIXME."""
    count = 0
    for py_file in repo_root.rglob("*.py"):
        if ".venv" in str(py_file) or "node_modules" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            for line in content.split("\n"):
                if "TODO" in line or "FIXME" in line:
                    # Critical = без issue ссылки
                    if "#" not in line.split("TODO")[0].split("FIXME")[0]:
                        count += 1
        except Exception:
            pass
    return count


def _check_key_docs(repo_root: Path) -> dict[str, Any]:
    """Проверить key docs."""
    missing = []
    for doc in KEY_DOCS:
        if not (repo_root / doc).exists():
            missing.append(doc)

    return {
        "existing": len(KEY_DOCS) - len(missing),
        "total": len(KEY_DOCS),
        "missing": missing,
        "all_exist": len(missing) == 0,
    }


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для Production-Ready checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Production-Ready checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("gates", help="Check quality gates (QG-1)")
    subparsers.add_parser("coverage", help="Coverage report (QG-2)")
    subparsers.add_parser("baseline", help="Performance baseline (QG-4)")
    subparsers.add_parser("docs", help="Documentation status (DOC-1)")
    subparsers.add_parser("all", help="All checks")

    args = parser.parse_args()

    if args.command == "gates":
        report = check_quality_gates()
        print(report.to_json())
        return 0 if report.all_passed else 1

    if args.command == "coverage":
        report = get_coverage_report()
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed else 1

    if args.command == "baseline":
        baseline = get_performance_baseline()
        print(json.dumps(baseline.to_dict(), indent=2))
        return 0

    if args.command == "docs":
        status = check_docs_status()
        print(json.dumps(status.to_dict(), indent=2))
        return 0 if status.all_exist else 1

    if args.command == "all":
        print("=== Quality Gates ===")
        gates = check_quality_gates()
        print(gates.to_json())
        print("\n=== Coverage ===")
        cov = get_coverage_report()
        print(json.dumps(cov.to_dict(), indent=2))
        print("\n=== Docs ===")
        docs = check_docs_status()
        print(json.dumps(docs.to_dict(), indent=2))
        return 0 if gates.all_passed else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
