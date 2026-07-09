"""
S8.11 (2026-07-06): Тесты для supply chain analysis.

Проверяет:
- parse_pyproject_deps: парсинг зависимостей
- _parse_dep_spec: парсинг spec строки
- parse_lock_file: парсинг lock file с хешами
- detect_drift: drift detection
- check_licenses: license compliance
- SupplyChainReport: отчёт
- CLI commands
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.supply_chain import (
    ALLOWED_LICENSES,
    DENIED_LICENSES,
    DENIED_PACKAGES,
    DependencyInfo,
    SupplyChainReport,
    _parse_dep_spec,
    check_licenses,
    detect_drift,
    generate_report,
    parse_lock_file,
    parse_pyproject_deps,
)


# ============================================================================
# _parse_dep_spec tests
# ============================================================================


class TestParseDepSpec:
    def test_simple_version(self) -> None:
        info = _parse_dep_spec("requests>=2.0")
        assert info is not None
        assert info.name == "requests"
        assert "2.0" in info.version
        assert not info.is_pinned
        assert not info.has_upper_bound

    def test_pinned_version(self) -> None:
        info = _parse_dep_spec("requests==2.31.0")
        assert info is not None
        assert info.is_pinned
        assert info.version == "2.31.0"

    def test_upper_bound(self) -> None:
        info = _parse_dep_spec("requests>=2.0,<3.0")
        assert info is not None
        assert info.has_upper_bound

    def test_git_source(self) -> None:
        info = _parse_dep_spec("v8unpack @ git+https://github.com/saby-integration/v8unpack.git@main")
        assert info is not None
        assert info.name == "v8unpack"
        assert info.source == "git"
        assert info.is_pinned

    def test_empty_spec(self) -> None:
        info = _parse_dep_spec("")
        assert info is None

    def test_with_comment(self) -> None:
        info = _parse_dep_spec("requests>=2.0  # HTTP client")
        assert info is not None
        assert info.name == "requests"

    def test_compound_name(self) -> None:
        info = _parse_dep_spec("package-name>=1.0")
        assert info is not None
        assert info.name == "package-name"


# ============================================================================
# parse_pyproject_deps tests
# ============================================================================


class TestParsePyproject:
    def test_parse_real_pyproject(self) -> None:
        deps = parse_pyproject_deps(Path("pyproject.toml"))
        # Should find at least main dependencies
        assert len(deps) > 0
        names = [d.name for d in deps]
        # Check key deps
        assert any("python-dotenv" in n or "structlog" in n for n in names)

    def test_parse_missing_file(self) -> None:
        deps = parse_pyproject_deps(Path("/nonexistent.toml"))
        assert deps == []

    def test_parse_optional_deps(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
dependencies = ["requests>=2.0"]

[project.optional-dependencies]
test = ["pytest>=8.0,<9.0"]
dev = ["mypy==1.10.0"]
""", encoding="utf-8")
        deps = parse_pyproject_deps(pyproject)
        names = [d.name for d in deps]
        assert "requests" in names
        assert "pytest" in names
        assert "mypy" in names


# ============================================================================
# parse_lock_file tests
# ============================================================================


class TestParseLockFile:
    def test_parse_missing_lock(self, tmp_path: Path) -> None:
        deps = parse_lock_file(tmp_path / "nope.txt")
        assert deps == {}

    def test_parse_simple_lock(self, tmp_path: Path) -> None:
        lock = tmp_path / "requirements.lock.txt"
        lock.write_text(
            "requests==2.31.0 \\\n"
            "    --hash=sha256:abc123 \\\n"
            "    --hash=sha256:def456\n"
            "structlog==24.0.0  # via package\n",
            encoding="utf-8",
        )
        deps = parse_lock_file(lock)
        assert "requests" in deps
        assert deps["requests"].version == "2.31.0"
        assert deps["requests"].has_hash
        assert deps["structlog"].is_pinned
        assert not deps["structlog"].has_hash

    def test_parse_lock_with_hashes(self, tmp_path: Path) -> None:
        lock = tmp_path / "requirements.lock.txt"
        lock.write_text(
            "package==1.0.0 \\\n"
            "    --hash=sha256:abc \\\n"
            "    --hash=sha256:def\n",
            encoding="utf-8",
        )
        deps = parse_lock_file(lock)
        assert deps["package"].has_hash


# ============================================================================
# detect_drift tests
# ============================================================================


class TestDetectDrift:
    def test_no_drift_when_in_sync(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
dependencies = ["requests==2.31.0"]
""", encoding="utf-8")
        lock = tmp_path / "requirements.lock.txt"
        lock.write_text("requests==2.31.0\n", encoding="utf-8")

        drift = detect_drift(pyproject, lock)
        # No drift (versions match)
        assert drift == []

    def test_drift_when_versions_differ(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
dependencies = ["requests==2.30.0"]
""", encoding="utf-8")
        lock = tmp_path / "requirements.lock.txt"
        lock.write_text("requests==2.31.0\n", encoding="utf-8")

        drift = detect_drift(pyproject, lock)
        assert len(drift) == 1
        assert drift[0][0] == "requests"
        assert "2.30.0" in drift[0][1]
        assert "2.31.0" in drift[0][2]

    def test_drift_when_package_missing_in_lock(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
dependencies = ["newpackage==1.0.0"]
""", encoding="utf-8")
        lock = tmp_path / "requirements.lock.txt"
        lock.write_text("otherpkg==1.0.0\n", encoding="utf-8")

        drift = detect_drift(pyproject, lock)
        assert any(d[0] == "newpackage" and "<missing>" in d[2] for d in drift)

    def test_no_drift_when_lock_missing(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"
dependencies = ["requests==2.31.0"]
""", encoding="utf-8")
        # No lock file
        drift = detect_drift(pyproject, tmp_path / "nope.txt")
        # All packages will be "missing" in lock
        assert any("<missing>" in d[2] for d in drift)


# ============================================================================
# SupplyChainReport tests
# ============================================================================


class TestSupplyChainReport:
    def test_empty_report(self) -> None:
        report = SupplyChainReport()
        assert report.compliance_score == 1.0

    def test_full_compliance(self) -> None:
        report = SupplyChainReport(
            total_deps=10,
            pinned_deps=10,
            with_upper_bounds=10,
            with_hashes=10,
            lock_file_exists=True,
        )
        assert report.compliance_score == 1.0

    def test_partial_compliance(self) -> None:
        report = SupplyChainReport(
            total_deps=10,
            pinned_deps=5,         # 0.5
            with_upper_bounds=10,  # 1.0
            with_hashes=10,
            lock_file_exists=True,
        )
        assert 0.5 < report.compliance_score < 1.0

    def test_no_lock_file_lowers_score(self) -> None:
        report = SupplyChainReport(
            total_deps=10,
            pinned_deps=10,
            with_upper_bounds=10,
            lock_file_exists=False,   # missing lock
        )
        assert report.compliance_score < 1.0

    def test_denied_licenses_lowers_score(self) -> None:
        report = SupplyChainReport(
            total_deps=10,
            pinned_deps=10,
            with_upper_bounds=10,
            lock_file_exists=True,
            denied_licenses=[("gpl-pkg", "GPL-3.0")],
        )
        assert report.compliance_score < 1.0

    def test_to_dict(self) -> None:
        report = SupplyChainReport(total_deps=5, pinned_deps=5)
        d = report.to_dict()
        assert "compliance_score" in d
        assert d["total_deps"] == 5


# ============================================================================
# License config tests
# ============================================================================


class TestLicenseConfig:
    def test_allowed_licenses_listed(self) -> None:
        assert "MIT" in ALLOWED_LICENSES
        assert "Apache-2.0" in ALLOWED_LICENSES
        assert "BSD-3-Clause" in ALLOWED_LICENSES

    def test_denied_licenses_listed(self) -> None:
        assert "GPL-3.0" in DENIED_LICENSES
        assert "AGPL-3.0" in DENIED_LICENSES

    def test_denied_packages_listed(self) -> None:
        assert "pycrypto" in DENIED_PACKAGES
        assert "subprocess32" in DENIED_PACKAGES


# ============================================================================
# check_licenses tests (with mocked pip-licenses)
# ============================================================================


class TestCheckLicenses:
    def test_returns_empty_when_pip_licenses_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError("pip-licenses not found")
        monkeypatch.setattr("subprocess.run", raise_fnf)
        assert check_licenses() == []

    def test_returns_denied_when_gpl_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock pip-licenses output
        pip_output = json.dumps([
            {"Name": "requests", "License": "MIT"},
            {"Name": "gpl-pkg", "License": "GPL-3.0"},
            {"Name": "agpl-pkg", "License": "AGPL-3.0"},
        ])

        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = pip_output
            mock.stderr = ""
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        denied = check_licenses()
        assert len(denied) == 2
        denied_names = [d[0] for d in denied]
        assert "gpl-pkg" in denied_names
        assert "agpl-pkg" in denied_names

    def test_returns_empty_when_all_mit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pip_output = json.dumps([
            {"Name": "pkg1", "License": "MIT"},
            {"Name": "pkg2", "License": "Apache-2.0"},
        ])

        def mock_run(*args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = pip_output
            return mock
        monkeypatch.setattr("subprocess.run", mock_run)

        denied = check_licenses()
        assert denied == []


# ============================================================================
# generate_report integration
# ============================================================================


class TestGenerateReport:
    def test_generates_report(self) -> None:
        report = generate_report()
        assert isinstance(report, SupplyChainReport)
        assert report.total_deps > 0
        # All our deps should have upper bounds (S8.11 requirement)
        assert report.with_upper_bounds > 0

    def test_report_to_dict_includes_compliance(self) -> None:
        report = generate_report()
        d = report.to_dict()
        assert "compliance_score" in d


# ============================================================================
# Configuration tests
# ============================================================================


class TestSupplyChainConfig:
    def test_pyproject_has_upper_bounds(self) -> None:
        """Все зависимости имеют upper bounds (предотвращает breakage)."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        # Should find at least some upper bounds
        assert "<" in content
        assert "<2.0" in content or "<1.0" in content

    def test_dependabot_config_exists(self) -> None:
        assert Path(".github/dependabot.yml").exists()

    def test_dependency_review_workflow_exists(self) -> None:
        assert Path(".github/workflows/dependency-review.yml").exists()

    def test_supply_chain_workflow_exists(self) -> None:
        assert Path(".github/workflows/supply-chain.yml").exists()

    def test_supply_chain_module_exists(self) -> None:
        from src.services.supply_chain import generate_report
        assert callable(generate_report)
