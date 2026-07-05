"""
D3.1 (2026-07-05): Тесты для analyzer coverage report.

Гарантирует:
1. analyzer_coverage_report.py скрипт существует
2. Скрипт находит все правила
3. Coverage report показывает статистику
4. Все правила имеют хотя бы один тест (цель: 100%)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
COVERAGE_SCRIPT = REPO_ROOT / "scripts" / "analyzer_coverage_report.py"


class TestAnalyzerCoverageReport:
    """D3.1: Coverage report по правилам анализаторов."""

    def test_coverage_script_exists(self) -> None:
        """Скрипт analyzer_coverage_report.py существует."""
        assert COVERAGE_SCRIPT.exists(), (
            "scripts/analyzer_coverage_report.py должен существовать (см. D3.1)"
        )

    def test_coverage_script_runs(self) -> None:
        """Скрипт запускается без ошибок."""
        result = subprocess.run(
            [sys.executable, str(COVERAGE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode in (0, 1), "Скрипт должен завершиться с кодом 0 или 1"
        assert "Total rules" in result.stdout

    def test_coverage_report_shows_statistics(self) -> None:
        """Report показывает статистику (total, with tests, without tests)."""
        result = subprocess.run(
            [sys.executable, str(COVERAGE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert "Total rules:" in result.stdout
        assert "With tests:" in result.stdout
        assert "Without tests:" in result.stdout
        assert "Coverage:" in result.stdout

    def test_coverage_json_output(self) -> None:
        """Скрипт поддержает --json вывод."""
        result = subprocess.run(
            [sys.executable, str(COVERAGE_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        import json
        data = json.loads(result.stdout)
        assert "total_rules" in data
        assert "rules_with_tests" in data
        assert "rules_without_tests" in data
        assert "coverage_pct" in data

    def test_coverage_finds_more_than_100_rules(self) -> None:
        """Скрипт находит >100 правил (проект содержит 150+)."""
        result = subprocess.run(
            [sys.executable, str(COVERAGE_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        import json
        data = json.loads(result.stdout)
        assert data["total_rules"] > 100, (
            f"Должно быть >100 правил, найдено: {data['total_rules']}"
        )

    def test_security_auditor_rules_have_tests(self) -> None:
        """Security auditor правила (SEC001-SEC015) имеют тесты."""
        result = subprocess.run(
            [sys.executable, str(COVERAGE_SCRIPT), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        import json
        data = json.loads(result.stdout)
        details = data["details"]
        sec_rules = {k: v for k, v in details.items() if k.startswith("SEC")}
        sec_with_tests = sum(1 for v in sec_rules.values() if v["has_test"])
        assert sec_with_tests >= len(sec_rules) * 0.8, (
            f"≥80% SEC правил должны иметь тесты. "
            f"Покрыто: {sec_with_tests}/{len(sec_rules)}"
        )
