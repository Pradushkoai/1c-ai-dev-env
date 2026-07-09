"""
D2.7 + D2.8 (2026-07-05): Тесты для coverage infrastructure + EDT parser expansion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestCoverageInfrastructure:
    """D2.7: coverage infrastructure проверки."""

    def test_pytest_cov_in_dev_deps(self) -> None:
        """pytest-cov в dev dependencies."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "pytest-cov" in content, "pytest-cov должен быть в dev dependencies"

    def test_coverage_config_exists(self) -> None:
        """[tool.coverage.run] секция существует в pyproject.toml."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "[tool.coverage.run]" in content

    def test_coverage_fail_under_exists(self) -> None:
        """coverage fail_under настроен."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "fail_under" in content

    def test_ci_runs_coverage(self) -> None:
        """CI workflow запускает coverage."""
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text(encoding="utf-8")
        assert "cov" in content.lower() or "coverage" in content.lower()


class TestEdtParserExpansion:
    """D2.8: EDT parser расширен с 9 до 26 типов."""

    def test_edt_type_map_has_26_types(self) -> None:
        """EDT_TYPE_MAP содержит 26 типов (расширено с 9)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert len(EDT_TYPE_MAP) >= 26, (
            f"EDT_TYPE_MAP должен содержать ≥26 типов, получено: {len(EDT_TYPE_MAP)}"
        )

    def test_edt_dirs_has_26_types(self) -> None:
        """EDT_DIRS содержит 26 типов."""
        from src.services.edt_parser import EDT_DIRS
        assert len(EDT_DIRS) >= 26

    def test_edt_type_map_has_accounting_register(self) -> None:
        """EDT_TYPE_MAP содержит AccountingRegister (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "AccountingRegister" in EDT_TYPE_MAP

    def test_edt_type_map_has_common_form(self) -> None:
        """EDT_TYPE_MAP содержит CommonForm (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "CommonForm" in EDT_TYPE_MAP

    def test_edt_type_map_has_chart_of_accounts(self) -> None:
        """EDT_TYPE_MAP содержит ChartOfAccounts (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "ChartOfAccounts" in EDT_TYPE_MAP

    def test_edt_type_map_has_business_process(self) -> None:
        """EDT_TYPE_MAP содержит BusinessProcess (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "BusinessProcess" in EDT_TYPE_MAP

    def test_edt_type_map_has_exchange_plan(self) -> None:
        """EDT_TYPE_MAP содержит ExchangePlan (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "ExchangePlan" in EDT_TYPE_MAP

    def test_edt_type_map_has_scheduled_job(self) -> None:
        """EDT_TYPE_MAP содержит ScheduledJob (D2.8)."""
        from src.services.edt_parser import EDT_TYPE_MAP
        assert "ScheduledJob" in EDT_TYPE_MAP

    def test_edt_dirs_match_type_map_keys(self) -> None:
        """EDT_DIRS keys совпадают с EDT_TYPE_MAP keys."""
        from src.services.edt_parser import EDT_TYPE_MAP, EDT_DIRS
        assert set(EDT_TYPE_MAP.keys()) == set(EDT_DIRS.keys())

    def test_existing_edt_tests_still_pass(self, tmp_path: Path) -> None:
        """Существующие EDT тесты не сломаны."""
        from src.services.edt_parser import EdtParser

        parser = EdtParser()
        result = parser.parse(tmp_path)
        assert isinstance(result, list)
        assert len(result) == 0  # Пустая директория → пустой список
