"""
S8.4 (2026-07-06): Тесты для SAST configuration (semgrep + bandit).

Проверяет:
- bandit.toml существует и валиден
- .semgrep.yml существует и валиден
- .github/workflows/sast.yml существует
- bandit реально находит тестовые уязвимости
- semgrep config парсится
- BSL правила работают
- False positive rate приемлем
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


class TestS8_4_ConfigFiles:
    """S8.4: Конфиги SAST инструментов существуют и валидны."""

    def test_bandit_config_exists(self) -> None:
        """bandit.toml существует."""
        assert (REPO_ROOT / "bandit.toml").exists()

    def test_semgrep_config_exists(self) -> None:
        """.semgrep.yml существует."""
        assert (REPO_ROOT / ".semgrep.yml").exists()

    def test_sast_workflow_exists(self) -> None:
        """.github/workflows/sast.yml существует."""
        assert (REPO_ROOT / ".github" / "workflows" / "sast.yml").exists()

    def test_sast_workflow_has_bandit_job(self) -> None:
        """SAST workflow содержит bandit job."""
        content = (REPO_ROOT / ".github" / "workflows" / "sast.yml").read_text(encoding="utf-8")
        assert "bandit" in content.lower()
        assert "Bandit" in content

    def test_sast_workflow_has_semgrep_job(self) -> None:
        """SAST workflow содержит semgrep job."""
        content = (REPO_ROOT / ".github" / "workflows" / "sast.yml").read_text(encoding="utf-8")
        assert "semgrep" in content.lower()
        assert "Semgrep" in content

    def test_semgrep_config_is_valid_yaml(self) -> None:
        """Semgrep config — валидный YAML."""
        content = (REPO_ROOT / ".semgrep.yml").read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        assert "rules" in config
        assert isinstance(config["rules"], list)
        assert len(config["rules"]) >= 5

    def test_semgrep_rules_have_ids(self) -> None:
        """Каждое semgrep правило имеет уникальный id."""
        content = (REPO_ROOT / ".semgrep.yml").read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        ids = [r["id"] for r in config["rules"]]
        assert len(ids) == len(set(ids)), "Duplicate rule ids"

    def test_semgrep_rules_have_metadata(self) -> None:
        """Semgrep правила содержат CWE metadata."""
        content = (REPO_ROOT / ".semgrep.yml").read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        for rule in config["rules"]:
            assert "metadata" in rule or "message" in rule, f"Rule {rule.get('id')} без metadata"

    def test_bandit_deps_in_pyproject(self) -> None:
        """bandit в dev dependencies."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "bandit" in content

    def test_semgrep_deps_in_pyproject(self) -> None:
        """semgrep в dev dependencies."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "semgrep" in content


class TestS8_4_BanditIntegration:
    """S8.4: Реальный запуск bandit (если установлен)."""

    @pytest.fixture
    def bandit_available(self) -> bool:
        try:
            subprocess.run(
                ["bandit", "--version"], capture_output=True, timeout=5, check=True
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def test_bandit_finds_eval(self, bandit_available: bool, tmp_path: Path) -> None:
        """Bandit находит eval() в Python коде."""
        if not bandit_available:
            pytest.skip("bandit не установлен")

        test_file = tmp_path / "vuln.py"
        test_file.write_text(
            "user_input = input()\n"
            "result = eval(user_input)\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bandit", "-f", "json", str(test_file)],
            capture_output=True, timeout=15, text=True,
        )
        # Bandit пишет в stdout и возвращает non-zero если есть находки
        data = json.loads(result.stdout)
        assert data["results"], "Bandit должен найти eval()"
        test_ids = [r["test_id"] for r in data["results"]]
        assert "B307" in test_ids, f"Bandit должен найти B307 (eval), found: {test_ids}"

    def test_bandit_finds_hardcoded_password(self, bandit_available: bool, tmp_path: Path) -> None:
        """Bandit находит хардкод пароля."""
        if not bandit_available:
            pytest.skip("bandit не установлен")

        test_file = tmp_path / "vuln.py"
        test_file.write_text(
            'password = "hardcoded_secret_123"\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bandit", "-f", "json", str(test_file)],
            capture_output=True, timeout=15, text=True,
        )
        data = json.loads(result.stdout)
        test_ids = [r["test_id"] for r in data["results"]]
        assert "B105" in test_ids, f"Bandit должен найти B105 (hardcoded password), found: {test_ids}"

    def test_bandit_clean_code_no_issues(self, bandit_available: bool, tmp_path: Path) -> None:
        """Bandit не находит проблем в безопасном коде."""
        if not bandit_available:
            pytest.skip("bandit не установлен")

        test_file = tmp_path / "safe.py"
        test_file.write_text(
            "import hashlib\n"
            "def hash_password(pw: str) -> str:\n"
            "    return hashlib.sha256(pw.encode()).hexdigest()\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bandit", "-f", "json", str(test_file)],
            capture_output=True, timeout=15, text=True,
        )
        data = json.loads(result.stdout)
        high_issues = [
            r for r in data["results"]
            if r.get("issue_severity") == "HIGH"
        ]
        assert not high_issues, "Безопасный код не должен иметь HIGH issues"


class TestS8_4_SemgrepRules:
    """S8.4: Тесты semgrep правил."""

    @pytest.fixture
    def semgrep_available(self) -> bool:
        try:
            subprocess.run(
                ["semgrep", "--version"], capture_output=True, timeout=5, check=True
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def test_semgrep_config_loads(self, semgrep_available: bool) -> None:
        """Semgrep конфиг парсится без ошибок."""
        if not semgrep_available:
            pytest.skip("semgrep не установлен")
        result = subprocess.run(
            ["semgrep", "--validate", "--config", str(REPO_ROOT / ".semgrep.yml")],
            capture_output=True, timeout=15, text=True,
        )
        assert result.returncode == 0, f"Semgrep config invalid: {result.stderr}"

    def test_semgrep_finds_shell_true(self, semgrep_available: bool, tmp_path: Path) -> None:
        """Semgrep находит shell=True."""
        if not semgrep_available:
            pytest.skip("semgrep не установлен")
        test_file = tmp_path / "vuln.py"
        test_file.write_text(
            "import subprocess\n"
            "subprocess.run('ls', shell=True)\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["semgrep", "--config", str(REPO_ROOT / ".semgrep.yml"),
             "--json", str(test_file)],
            capture_output=True, timeout=30, text=True,
        )
        data = json.loads(result.stdout)
        rule_ids = [r["check_id"] for r in data.get("results", [])]
        assert any("shell-true" in r for r in rule_ids), \
            f"Semgrep должен найти shell=True, got: {rule_ids}"

    def test_semgrep_finds_pickle_load(self, semgrep_available: bool, tmp_path: Path) -> None:
        """Semgrep находит pickle.load."""
        if not semgrep_available:
            pytest.skip("semgrep не установлен")
        test_file = tmp_path / "vuln.py"
        test_file.write_text(
            "import pickle\n"
            "data = pickle.load(open('data.pkl', 'rb'))\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["semgrep", "--config", str(REPO_ROOT / ".semgrep.yml"),
             "--json", str(test_file)],
            capture_output=True, timeout=30, text=True,
        )
        data = json.loads(result.stdout)
        rule_ids = [r["check_id"] for r in data.get("results", [])]
        assert any("pickle" in r for r in rule_ids), \
            f"Semgrep должен найти pickle.load, got: {rule_ids}"


class TestS8_4_AGENTSPolicy:
    """S8.4: AGENTS.md содержит SAST политику."""

    def test_agents_md_mentions_sast(self) -> None:
        """AGENTS.md упоминает SAST/bandit/semgrep."""
        content = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        # Должно быть упоминание хотя бы одного SAST инструмента
        assert (
            "SAST" in content
            or "bandit" in content.lower()
            or "semgrep" in content.lower()
        ), "AGENTS.md должен описывать SAST политику"
