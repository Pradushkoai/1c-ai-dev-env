"""
Тесты для Dockerfile — проверка security best practices (P1.6).

До фикса: Dockerfile не содержал директивы USER — контейнер запускался от root,
что критично при компрометации MCP-сервера (атакующий получает root в контейнере
и потенциально доступ к docker socket на хосте).

После фикса: добавлен non-root пользователь 1c-ai (UID/GID 1000), директива
USER 1c-ai переключает runtime контекста.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"


# ============================================================================
# Тесты
# ============================================================================


class TestDockerfileSecurity:
    """Security-проверки Dockerfile."""

    def test_dockerfile_exists(self) -> None:
        """Dockerfile присутствует в репозитории."""
        assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"

    def test_dockerfile_has_user_directive(self) -> None:
        """Dockerfile должен содержать директиву USER non-root.

        Regression для P1.6: до фикса Dockerfile не содержал USER —
        контейнер работал от root, что критично для безопасности.
        """
        content = DOCKERFILE.read_text(encoding="utf-8")
        # Ищем USER <name> (не USER root, не USER 0)
        match = re.search(r"^USER\s+(\S+)\s*$", content, re.MULTILINE)
        assert match is not None, (
            "Dockerfile must contain 'USER <name>' directive (P1.6 fix). Container must not run as root."
        )
        username = match.group(1)
        assert username not in ("root", "0"), f"USER must not be 'root' or '0', got: {username}"
        assert username == "1c-ai", f"Expected USER 1c-ai, got USER {username}"

    def test_dockerfile_creates_non_root_user(self) -> None:
        """Должны быть команды создания пользователя (useradd/groupadd)."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "useradd" in content or "adduser" in content, (
            "Dockerfile must create a non-root user via useradd/adduser"
        )
        assert "1c-ai" in content, "Created user should be named '1c-ai'"

    def test_user_directive_after_chown(self) -> None:
        """USER должен идти AFTER chown -R 1c-ai /app.

        Иначе файлы будут принадлежать root, и 1c-ai не сможет их читать/писать.
        """
        content = DOCKERFILE.read_text(encoding="utf-8")
        chown_pos = content.find("chown -R 1c-ai")
        user_pos = content.find("\nUSER 1c-ai")
        assert chown_pos != -1, "Dockerfile must have 'chown -R 1c-ai' before USER"
        assert user_pos != -1, "Dockerfile must have 'USER 1c-ai'"
        assert chown_pos < user_pos, (
            "chown -R 1c-ai must come BEFORE 'USER 1c-ai' — otherwise the 1c-ai user cannot read/write /app files"
        )

    def test_no_root_in_healthcheck_or_runtime(self) -> None:
        """HEALTHCHECK и ENTRYPOINT не должны явно использовать root."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        # После USER 1c-ai не должно быть переключения обратно на root
        user_match = re.search(r"^USER\s+(\S+)", content, re.MULTILINE)
        assert user_match is not None
        # Все USER directives (если их несколько) должны быть 1c-ai
        all_users = re.findall(r"^USER\s+(\S+)\s*$", content, re.MULTILINE)
        assert all(u == "1c-ai" for u in all_users), f"All USER directives must be '1c-ai', got: {all_users}"

    def test_uid_is_1000(self) -> None:
        """UID 1000 — стандартный непривилегированный UID в Debian/Ubuntu.

        UID 1000 соответствует первому пользователю, создаваемому установщиком ОС.
        Использование system UID (<1000) или root UID (0) — плохая практика.
        """
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "--uid 1000" in content, "Dockerfile should use UID 1000 for non-root user"
        assert "--gid 1000" in content, "Dockerfile should use GID 1000 for non-root user group"

    def test_user_directive_comes_before_entrypoint(self) -> None:
        """USER должен идти перед ENTRYPOINT/CMD — чтобы они выполнялись от 1c-ai."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        user_pos = content.find("\nUSER 1c-ai")
        entrypoint_pos = content.find("\nENTRYPOINT")
        cmd_pos = content.find("\nCMD")
        assert user_pos != -1, "USER 1c-ai directive missing"
        assert entrypoint_pos != -1, "ENTRYPOINT missing"
        assert user_pos < entrypoint_pos, "USER 1c-ai must come before ENTRYPOINT — otherwise container starts as root"
        if cmd_pos != -1:
            assert user_pos < cmd_pos, "USER 1c-ai must come before CMD"


class TestDockerfileBuildIntegrity:
    """Проверка целостности Dockerfile — после добавления USER сборка
    не должна сломаться."""

    def test_dockerfile_can_be_parsed(self) -> None:
        """Dockerfile должен иметь валидный синтаксис (основные инструкции)."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        # Должны быть FROM, WORKDIR, COPY, RUN
        assert "FROM" in content, "Dockerfile must have FROM"
        assert "WORKDIR" in content, "Dockerfile must have WORKDIR"
        assert "COPY" in content, "Dockerfile must have COPY"
        assert "RUN" in content, "Dockerfile must have RUN"

    def test_pip_install_before_user_switch(self) -> None:
        """pip install должен идти ДО USER 1c-ai — иначе не сможет ставить пакеты."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        user_pos = content.find("\nUSER 1c-ai")
        pip_install_pos = content.rfind("pip install", 0, user_pos)
        assert pip_install_pos != -1, (
            "pip install must come before USER 1c-ai — non-root user cannot install packages system-wide"
        )

    def test_mkdir_before_user_switch(self) -> None:
        """mkdir -p для директорий должен идти ДО USER 1c-ai (или с chown)."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        user_pos = content.find("\nUSER 1c-ai")
        mkdir_pos = content.find("mkdir -p /app/data")
        assert mkdir_pos != -1, "mkdir for /app/data must exist"
        assert mkdir_pos < user_pos, "mkdir must come before USER 1c-ai (or use chown after)"
