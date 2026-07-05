"""
I7.9 (2026-07-05): Тесты для SBOM (Software Bill of Materials) generation.

Гарантирует:
1. CI workflow для SBOM существует
2. Workflow использует cyclonedx-py
3. SBOM загружается как artifact и в GitHub Release
4. AGENTS.md содержит политику SBOM
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SBOM_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sbom-generation.yml"
AGENTS_MD = REPO_ROOT / "AGENTS.md"


class TestSbomWorkflow:
    """I7.9: CI workflow для SBOM generation."""

    def test_workflow_exists(self) -> None:
        """CI workflow для SBOM существует."""
        assert SBOM_WORKFLOW.exists(), (
            ".github/workflows/sbom-generation.yml должен существовать. "
            "См. I7.9 (2026-07-05): SBOM generation."
        )

    def test_workflow_uses_cyclonedx(self) -> None:
        """Workflow использует cyclonedx-py."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "cyclonedx" in content.lower(), (
            "Workflow должен использовать cyclonedx-py для SBOM generation"
        )

    def test_workflow_generates_json(self) -> None:
        """Workflow генерирует sbom.json."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "sbom.json" in content, "Workflow должен генерировать sbom.json"

    def test_workflow_validates_sbom(self) -> None:
        """Workflow валидирует SBOM (проверяет bomFormat, specVersion, components)."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "bomFormat" in content, "Workflow должен валидировать SBOM (bomFormat)"
        assert "CycloneDX" in content, "Workflow должен проверять bomFormat == CycloneDX"

    def test_workflow_uploads_artifact(self) -> None:
        """Workflow загружает SBOM как artifact."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "upload-artifact" in content, (
            "Workflow должен загружать SBOM как artifact"
        )

    def test_workflow_uploads_to_release(self) -> None:
        """Workflow загружает SBOM в GitHub Release при публикации."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "release" in content.lower(), (
            "Workflow должен загружать SBOM в GitHub Release"
        )

    def test_workflow_triggers_on_release(self) -> None:
        """Workflow запускается при публикации release."""
        if not SBOM_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = SBOM_WORKFLOW.read_text(encoding="utf-8")
        assert "release" in content and "published" in content, (
            "Workflow должен запускаться при release published"
        )


class TestAgentsMdSbomPolicy:
    """I7.9: AGENTS.md содержит политику SBOM."""

    def test_agents_md_has_sbom_policy(self) -> None:
        """AGENTS.md содержит упоминание SBOM."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        assert any(word in content.upper() for word in ["SBOM", "CYCLONEDX"]), (
            "AGENTS.md должен содержать политику SBOM (см. I7.9)"
        )
