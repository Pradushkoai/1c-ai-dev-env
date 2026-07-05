"""
I7.1 (2026-07-05): Тесты для multi-arch Docker build.

Гарантирует:
1. CI workflow для multi-arch Docker существует
2. Workflow собирает для linux/amd64 и linux/arm64
3. Workflow публикует в ghcr.io
4. Dockerfile существует и использует multi-stage build
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DOCKER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-multi-arch.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile"


class TestDockerMultiArchWorkflow:
    """I7.1: CI workflow для multi-arch Docker build."""

    def test_workflow_exists(self) -> None:
        """CI workflow для multi-arch Docker существует."""
        assert DOCKER_WORKFLOW.exists(), (
            ".github/workflows/docker-multi-arch.yml должен существовать. "
            "См. I7.1 (2026-07-05): Multi-arch Docker."
        )

    def test_workflow_uses_qemu(self) -> None:
        """Workflow использует QEMU для кросс-компиляции."""
        if not DOCKER_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        assert "qemu" in content.lower(), "Workflow должен использовать QEMU для arm64"

    def test_workflow_uses_buildx(self) -> None:
        """Workflow использует Docker Buildx."""
        if not DOCKER_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        assert "buildx" in content.lower(), "Workflow должен использовать Docker Buildx"

    def test_workflow_builds_amd64_and_arm64(self) -> None:
        """Workflow собирает для linux/amd64 и linux/arm64."""
        if not DOCKER_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        assert "linux/amd64" in content, "Workflow должен собирать для linux/amd64"
        assert "linux/arm64" in content, "Workflow должен собирать для linux/arm64"

    def test_workflow_pushes_to_ghcr(self) -> None:
        """Workflow публикует образ в GitHub Container Registry (ghcr.io)."""
        if not DOCKER_WORKFLOW.exists():
            pytest.skip("Workflow not found")
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        assert "ghcr.io" in content, "Workflow должен публиковать в ghcr.io"


class TestDockerfile:
    """I7.1: Dockerfile использует multi-stage build (оптимизация размера)."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile существует."""
        assert DOCKERFILE.exists(), "Dockerfile должен существовать"

    def test_dockerfile_uses_multi_stage(self) -> None:
        """Dockerfile использует multi-stage build (AS builder)."""
        if not DOCKERFILE.exists():
            pytest.skip("Dockerfile not found")
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "AS builder" in content or "as builder" in content, (
            "Dockerfile должен использовать multi-stage build (FROM ... AS builder)"
        )

    def test_dockerfile_uses_non_root_user(self) -> None:
        """Dockerfile использует non-root user (security best practice)."""
        if not DOCKERFILE.exists():
            pytest.skip("Dockerfile not found")
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "USER " in content, (
            "Dockerfile должен использовать non-root user (см. P1.6 в CHANGELOG)"
        )
