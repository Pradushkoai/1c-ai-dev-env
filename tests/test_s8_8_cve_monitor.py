"""
S8.8 (2026-07-06): Тесты для CVE monitor.

Проверяет:
- CveFinding/CveReport dataclasses
- Baseline load/save/add/remove
- Expiration logic
- pip-audit integration (skip если не установлен)
- CLI commands
- JSON report generation
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.cve_monitor import (
    BASELINE_PATH,
    CveFinding,
    CveReport,
    add_to_baseline,
    apply_baseline,
    is_expired,
    load_baseline,
    remove_from_baseline,
    save_baseline,
    scan,
)


# ============================================================================
# Dataclass tests
# ============================================================================


class TestCveFinding:
    def test_creation(self) -> None:
        f = CveFinding(
            package="requests", version="2.20.0",
            vuln_id="CVE-2023-32681", severity="high",
        )
        assert f.package == "requests"
        assert f.severity == "high"
        assert f.fix_versions == []
        assert not f.is_ignored

    def test_to_dict(self) -> None:
        f = CveFinding("pkg", "1.0", "CVE-XX", "medium")
        d = f.to_dict()
        assert d["package"] == "pkg"
        assert d["vuln_id"] == "CVE-XX"


class TestCveReport:
    def test_empty_report(self) -> None:
        r = CveReport()
        assert r.critical_count == 0
        assert r.high_count == 0
        assert r.total_active == 0

    def test_counts(self) -> None:
        r = CveReport()
        r.findings = [
            CveFinding("a", "1", "C1", "critical"),
            CveFinding("b", "1", "C2", "critical", is_ignored=True),
            CveFinding("c", "1", "C3", "high"),
            CveFinding("d", "1", "C4", "medium", is_ignored=True),
            CveFinding("e", "1", "C5", "low"),
        ]
        assert r.critical_count == 1   # 2 critical, 1 ignored
        assert r.high_count == 1
        assert r.total_active == 3

    def test_to_json(self) -> None:
        r = CveReport()
        r.findings.append(CveFinding("pkg", "1.0", "CVE-XX", "low"))
        js = r.to_json()
        data = json.loads(js)
        assert data["findings"][0]["package"] == "pkg"


# ============================================================================
# Baseline tests
# ============================================================================


class TestBaseline:
    """Тесты baseline management."""

    @pytest.fixture
    def baseline_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """Использовать tmp_path для baseline."""
        path = tmp_path / "baseline.json"
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", path)
        return path

    def test_load_empty_baseline(self, baseline_path: Path) -> None:
        assert load_baseline() == {}

    def test_save_and_load(self, baseline_path: Path) -> None:
        save_baseline({"CVE-XX": {"reason": "test", "expires": "2026-12-31"}})
        loaded = load_baseline()
        assert "CVE-XX" in loaded
        assert loaded["CVE-XX"]["reason"] == "test"

    def test_add_to_baseline(self, baseline_path: Path) -> None:
        add_to_baseline("CVE-XX", "Cannot upgrade dep", expires_days=30)
        loaded = load_baseline()
        assert "CVE-XX" in loaded
        assert "Cannot upgrade" in loaded["CVE-XX"]["reason"]

    def test_remove_from_baseline(self, baseline_path: Path) -> None:
        add_to_baseline("CVE-XX", "test", 30)
        remove_from_baseline("CVE-XX")
        loaded = load_baseline()
        assert "CVE-XX" not in loaded


# ============================================================================
# Expiration tests
# ============================================================================


class TestExpiration:
    def test_not_expired(self) -> None:
        future = (datetime.now() + timedelta(days=30)).date().isoformat()
        assert not is_expired(future)

    def test_expired(self) -> None:
        past = (datetime.now() - timedelta(days=1)).date().isoformat()
        assert is_expired(past)

    def test_empty_not_expired(self) -> None:
        assert not is_expired("")

    def test_invalid_date_not_expired(self) -> None:
        assert not is_expired("not-a-date")


# ============================================================================
# apply_baseline tests
# ============================================================================


class TestApplyBaseline:
    def test_mark_ignored(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")
        add_to_baseline("CVE-XX", "test reason", 90)

        findings = [
            CveFinding("pkg", "1.0", "CVE-XX", "high"),
            CveFinding("pkg2", "1.0", "CVE-YY", "medium"),
        ]
        result = apply_baseline(findings)
        assert result[0].is_ignored
        assert result[0].ignore_reason == "test reason"
        assert not result[1].is_ignored

    def test_expired_not_ignored(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")
        # Add with past expiration directly
        save_baseline({
            "CVE-XX": {
                "reason": "old",
                "expires": (datetime.now() - timedelta(days=1)).date().isoformat(),
                "added_at": "2026-01-01",
            }
        })

        findings = [CveFinding("pkg", "1.0", "CVE-XX", "high")]
        result = apply_baseline(findings)
        assert not result[0].is_ignored


# ============================================================================
# scan() integration tests
# ============================================================================


class TestScanIntegration:
    """Тесты scan() с mocked pip-audit."""

    def test_scan_with_no_findings(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")

        # Mock pip-audit returning empty
        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps({"dependencies": []})
            mock.stderr = ""
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        report = scan()
        assert report.total_packages == 0
        assert len(report.findings) == 0

    def test_scan_with_findings(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")

        # Mock pip-audit returning a finding
        audit_output = {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.20.0",
                    "vulns": [
                        {
                            "id": "CVE-2023-32681",
                            "description": "Leak of Authorization header",
                            "fix_versions": ["2.31.0"],
                        }
                    ],
                },
                {"name": "structlog", "version": "24.0.0", "vulns": []},
            ]
        }

        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps(audit_output)
            mock.stderr = ""
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        report = scan()
        assert report.total_packages == 2
        assert len(report.findings) == 1
        assert report.findings[0].package == "requests"
        assert report.findings[0].vuln_id == "CVE-2023-32681"
        assert report.findings[0].fix_versions == ["2.31.0"]

    def test_scan_pip_audit_not_installed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")

        def mock_run(*args, **kwargs):
            raise FileNotFoundError("pip-audit not found")
        monkeypatch.setattr("subprocess.run", mock_run)

        report = scan()
        assert report.total_packages == 0
        assert len(report.findings) == 0


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_scan_no_strict(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")
        monkeypatch.setattr("sys.argv", ["cve_monitor", "scan"])

        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps({"dependencies": []})
            mock.stderr = ""
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        from src.services.cve_monitor import main
        rc = main()
        assert rc == 0

    def test_cli_scan_strict_with_findings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")
        monkeypatch.setattr("sys.argv", ["cve_monitor", "scan", "--strict"])

        audit_output = {
            "dependencies": [{
                "name": "vuln_pkg",
                "version": "1.0",
                "vulns": [{"id": "CVE-XX", "description": "test", "fix_versions": []}],
            }]
        }
        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps(audit_output)
            mock.stderr = ""
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        from src.services.cve_monitor import main
        rc = main()
        assert rc == 1   # strict mode fails on active CVE

    def test_cli_baseline_list_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("src.services.cve_monitor.BASELINE_PATH", tmp_path / "b.json")
        monkeypatch.setattr("sys.argv", ["cve_monitor", "baseline", "list"])

        from src.services.cve_monitor import main
        rc = main()
        assert rc == 0


# ============================================================================
# Configuration tests
# ============================================================================


class TestCVEConfiguration:
    """Проверка конфигурации CVE monitoring."""

    def test_pip_audit_in_deps(self) -> None:
        """pip-audit в dev dependencies."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "pip-audit" in content

    def test_safety_in_deps(self) -> None:
        """safety в dev dependencies."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "safety" in content

    def test_dependency_hygiene_workflow_exists(self) -> None:
        """CI workflow для dependency hygiene существует."""
        assert Path(".github/workflows/dependency-hygiene.yml").exists()

    def test_cve_monitor_module_exists(self) -> None:
        """cve_monitor модуль существует."""
        from src.services.cve_monitor import scan
        assert callable(scan)
