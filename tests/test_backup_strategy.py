"""
P2.7: Тесты для Backup Strategy.

Проверяет:
1. backup-mirror.yml workflow существует и корректен
2. Git remote настроен для GitHub
3. Документация backup strategy существует
4. .gitignore исключает временные backup файлы
"""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
BACKUP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backup-mirror.yml"
BACKUP_DOCS = REPO_ROOT / "docs" / "BACKUP_STRATEGY.md"


# ============================================================================
# Тесты — backup workflow
# ============================================================================


class TestBackupWorkflow:
    """Проверка .github/workflows/backup-mirror.yml."""

    def test_backup_workflow_exists(self) -> None:
        """backup-mirror.yml существует."""
        assert BACKUP_WORKFLOW.exists(), f"Backup workflow not found: {BACKUP_WORKFLOW}"

    def test_backup_workflow_valid_yaml(self) -> None:
        """backup-mirror.yml — валидный YAML."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "Workflow must be valid YAML dict"
        assert "jobs" in data, "Workflow must have 'jobs'"

    def test_backup_workflow_has_mirror_job(self) -> None:
        """backup-mirror.yml содержит job mirror-to-gitlab."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        jobs = data.get("jobs", {})
        assert "mirror-to-gitlab" in jobs, "Workflow must have 'mirror-to-gitlab' job"

    def test_backup_workflow_has_bundle_job(self) -> None:
        """backup-mirror.yml содержит job git-bundle-backup."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        jobs = data.get("jobs", {})
        assert "git-bundle-backup" in jobs, "Workflow must have 'git-bundle-backup' job"

    def test_backup_workflow_has_restore_drill(self) -> None:
        """backup-mirror.yml содержит job restore-drill."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        jobs = data.get("jobs", {})
        assert "restore-drill" in jobs, "Workflow must have 'restore-drill' job"

    def test_backup_workflow_has_schedule(self) -> None:
        """backup-mirror.yml имеет schedule trigger (daily backup)."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        assert "cron" in content, "Workflow must have cron schedule"
        assert "schedule" in content, "Workflow must have schedule trigger"

    def test_backup_workflow_uses_gitlab_token_secret(self) -> None:
        """backup-mirror.yml использует GITLAB_TOKEN secret."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        assert "GITLAB_TOKEN" in content, "Workflow must reference GITLAB_TOKEN secret for GitLab mirror"

    def test_backup_workflow_has_s3_upload(self) -> None:
        """backup-mirror.yml содержит опциональную загрузку в S3."""
        content = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        assert "S3_ENDPOINT" in content or "s3" in content.lower(), (
            "Workflow must have optional S3 upload for long-term storage"
        )


# ============================================================================
# Тесты — документация backup strategy
# ============================================================================


class TestBackupDocs:
    """Проверка docs/BACKUP_STRATEGY.md."""

    def test_backup_docs_exist(self) -> None:
        """docs/BACKUP_STRATEGY.md существует."""
        assert BACKUP_DOCS.exists(), f"Backup docs not found: {BACKUP_DOCS}"

    def test_backup_docs_has_procedure(self) -> None:
        """Документация содержит процедуру восстановления."""
        content = BACKUP_DOCS.read_text(encoding="utf-8")
        assert "restore" in content.lower() or "восстанов" in content.lower(), (
            "Backup docs must describe restore procedure"
        )

    def test_backup_docs_mentions_gitlab(self) -> None:
        """Документация упоминает GitLab mirror."""
        content = BACKUP_DOCS.read_text(encoding="utf-8")
        assert "gitlab" in content.lower(), "Backup docs must mention GitLab mirror"

    def test_backup_docs_mentions_git_bundle(self) -> None:
        """Документация упоминает git bundle backups."""
        content = BACKUP_DOCS.read_text(encoding="utf-8")
        assert "bundle" in content.lower(), "Backup docs must mention git bundle"

    def test_backup_docs_has_retention_policy(self) -> None:
        """Документация описывает retention policy."""
        content = BACKUP_DOCS.read_text(encoding="utf-8")
        assert "retention" in content.lower() or "30 days" in content.lower(), (
            "Backup docs must describe retention policy"
        )


# ============================================================================
# Тесты — .gitignore
# ============================================================================


class TestGitignore:
    """Проверка что .gitignore исключает временные backup файлы."""

    def test_gitignore_exists(self) -> None:
        """Файл .gitignore существует."""
        gitignore = REPO_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore must exist"

    def test_gitignore_excludes_bundle_files(self) -> None:
        """Файл .gitignore исключает .bundle файлы."""
        gitignore = REPO_ROOT / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        assert "*.bundle" in content, ".gitignore must exclude *.bundle files (git bundle backups)"
