"""
S8.6 (2026-07-05): Тесты для secrets management.

Гарантирует:
1. .env.example существует и содержит placeholder значения (не реальные секреты)
2. .gitignore покрывает секрет-файлы (.env, .git-credentials, *.pem, *.key)
3. .pre-commit-config.yaml содержит detect-secrets hook
4. .secrets.baseline существует и валиден
5. AGENTS.md содержит политику secrets
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
GITIGNORE = REPO_ROOT / ".gitignore"
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
SECRETS_BASELINE = REPO_ROOT / ".secrets.baseline"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
SECRET_SCAN_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "secret-scanning.yml"


class TestEnvExample:
    """S8.6: .env.example — шаблон переменных окружения."""

    def test_env_example_exists(self) -> None:
        """.env.example существует."""
        assert ENV_EXAMPLE.exists(), (
            ".env.example должен существовать как шаблон для разработчиков. "
            "См. S8.6 (2026-07-05): Secrets management."
        )

    def test_env_example_has_no_real_secrets(self) -> None:
        """.env.example НЕ содержит реальные секреты (только placeholders).

        Проверяем только незакомментированные строки (без # в начале).
        Закомментированные строки с placeholder (например, # GITHUB_TOKEN=github_pat_xxx)
        допустимы — это пример, не реальный секрет.
        """
        if not ENV_EXAMPLE.exists():
            pytest.skip(".env.example not found")
        content = ENV_EXAMPLE.read_text(encoding="utf-8")
        # Проверяем только незакомментированные строки
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue  # Закомментированные строки и пустые — OK
            # В незакомментированных строках не должно быть реальных токенов
            forbidden_patterns = [
                "ghp_",  # GitHub classic PAT
                "github_pat_",  # GitHub fine-grained PAT (как значение, не placeholder)
                "sk-",  # Stripe/OpenAI keys
                "AKIA",  # AWS access key
            ]
            for pattern in forbidden_patterns:
                # Допускаем pattern в placeholder (например, "github_pat_your_token_here")
                if pattern in stripped and "your_" not in stripped and "xxx" not in stripped:
                    pytest.fail(
                        f".env.example строка {line_num} содержит возможный реальный секрет: {stripped}"
                    )

    def test_env_example_has_placeholder_values(self) -> None:
        """.env.example использует placeholder значения (закомментированные)."""
        if not ENV_EXAMPLE.exists():
            pytest.skip(".env.example not found")
        content = ENV_EXAMPLE.read_text(encoding="utf-8")
        # Все значения должны быть закомментированы (# в начале строки)
        # или использовать placeholder
        env_lines = [l for l in content.splitlines() if "=" in l and not l.strip().startswith("#")]
        # Если есть незакомментированные строки с =, проверяем что они placeholders
        for line in env_lines:
            # Допускаем только если значение явно placeholder
            assert any(placeholder in line.lower() for placeholder in [
                "your_", "example", "placeholder", "xxx", "change_me"
            ]), (
                f"Незакомментированная строка без placeholder: {line}. "
                f"Закомментируйте (#) или используйте placeholder."
            )


class TestGitignoreSecrets:
    """S8.6: .gitignore покрывает секрет-файлы."""

    def test_gitignore_covers_env(self) -> None:
        """.gitignore содержит .env."""
        content = GITIGNORE.read_text(encoding="utf-8")
        assert ".env" in content, (
            ".gitignore должен содержать .env (предотвращает accidental commit секретов)"
        )

    def test_gitignore_covers_git_credentials(self) -> None:
        """.gitignore содержит .git-credentials."""
        content = GITIGNORE.read_text(encoding="utf-8")
        assert ".git-credentials" in content, (
            ".gitignore должен содержать .git-credentials"
        )

    def test_gitignore_covers_pem_keys(self) -> None:
        """.gitignore содержит *.pem и *.key."""
        content = GITIGNORE.read_text(encoding="utf-8")
        assert "*.pem" in content, ".gitignore должен содержать *.pem"
        assert "*.key" in content, ".gitignore должен содержать *.key"

    def test_gitignore_covers_credentials_pattern(self) -> None:
        """.gitignore содержит *.credentials."""
        content = GITIGNORE.read_text(encoding="utf-8")
        assert "*.credentials" in content, ".gitignore должен содержать *.credentials"


class TestPreCommitDetectSecrets:
    """S8.6: detect-secrets в pre-commit config."""

    def test_precommit_has_detect_secrets(self) -> None:
        """.pre-commit-config.yaml содержит detect-secrets hook."""
        content = PRECOMMIT_CONFIG.read_text(encoding="utf-8")
        assert "detect-secrets" in content, (
            ".pre-commit-config.yaml должен содержать detect-secrets hook. "
            "См. S8.6 (2026-07-05)."
        )

    def test_precommit_uses_baseline(self) -> None:
        """detect-secrets hook использует .secrets.baseline."""
        content = PRECOMMIT_CONFIG.read_text(encoding="utf-8")
        assert ".secrets.baseline" in content, (
            "detect-secrets hook должен использовать --baseline .secrets.baseline"
        )


class TestSecretsBaseline:
    """S8.6: .secrets.baseline — baseline для detect-secrets."""

    def test_baseline_exists(self) -> None:
        """.secrets.baseline существует."""
        assert SECRETS_BASELINE.exists(), (
            ".secrets.baseline должен существовать. "
            "Запустите: detect-secrets scan --baseline .secrets.baseline"
        )

    def test_baseline_is_valid_json(self) -> None:
        """.secrets.baseline — валидный JSON."""
        if not SECRETS_BASELINE.exists():
            pytest.skip(".secrets.baseline not found")
        with open(SECRETS_BASELINE, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict), "Baseline должен быть dict"
        assert "version" in data, "Baseline должен содержать version"
        assert "plugins_used" in data, "Baseline должен содержать plugins_used"
        assert "results" in data, "Baseline должен содержать results"


class TestSecretScanningCI:
    """S8.6: CI workflow для secret scanning."""

    def test_workflow_exists(self) -> None:
        """CI workflow для secret scanning существует."""
        assert SECRET_SCAN_WORKFLOW.exists(), (
            ".github/workflows/secret-scanning.yml должен существовать. "
            "См. S8.6 (2026-07-05)."
        )

    def test_workflow_uses_detect_secrets(self) -> None:
        """Workflow использует detect-secrets."""
        if not SECRET_SCAN_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SECRET_SCAN_WORKFLOW.read_text(encoding="utf-8")
        assert "detect-secrets" in content, (
            "Workflow должен использовать detect-secrets для сканирования"
        )

    def test_workflow_checks_gitignore(self) -> None:
        """Workflow проверяет .gitignore покрывает секреты."""
        if not SECRET_SCAN_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SECRET_SCAN_WORKFLOW.read_text(encoding="utf-8")
        assert ".git-credentials" in content or "git-credentials" in content, (
            "Workflow должен проверять .git-credentials в .gitignore"
        )


class TestAgentsMdSecretsPolicy:
    """S8.6: AGENTS.md содержит политику secrets."""

    def test_agents_md_has_secrets_policy(self) -> None:
        """AGENTS.md содержит секцию secrets."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        # Ищем упоминание secrets/секретов
        assert any(word in content.lower() for word in ["secret", "секрет", ".env", "token"]), (
            "AGENTS.md должен содержать политику secrets (см. S8.6)"
        )
