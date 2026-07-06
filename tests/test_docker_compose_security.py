"""
Тесты для docker-compose.yml — проверка безопасности (P1.7).

До фикса: docker-compose.yml содержал строку '- ${HOME}:/host:ro' в volumes
сервиса cli — это давало контейнеру доступ на чтение ко всему $HOME
пользователя, включая SSH-ключи, AWS-credentials, GPG-ключи, docker config,
kube config.

После фикса: монтировка удалена, в комментарии указано как явно
примонтировать конкретную директорию с .bsl-файлами.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


# ============================================================================
# Тесты
# ============================================================================


class TestDockerComposeSecurity:
    """Security-проверки docker-compose.yml."""

    def test_compose_file_exists(self) -> None:
        """docker-compose.yml присутствует."""
        assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"

    def test_compose_yaml_valid(self) -> None:
        """YAML-синтаксис docker-compose.yml корректен."""
        with open(COMPOSE_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert "services" in cfg, "docker-compose.yml must have 'services' section"
        assert len(cfg["services"]) > 0

    def test_no_home_mount_in_any_service(self) -> None:
        """Ни один сервис НЕ должен монтировать $HOME.

        Regression для P1.7: до фикса сервис 'cli' содержал
          - ${HOME}:/host:ro
        что давало доступ к ~/.ssh, ~/.aws, ~/.gnupg, ~/.docker, ~/.kube.
        """
        with open(COMPOSE_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        for svc_name, svc in cfg.get("services", {}).items():
            vols = svc.get("volumes", []) or []
            for v in vols:
                v_str = str(v)
                # ${HOME} или $HOME — оба варианта запрещены
                assert "${HOME}" not in v_str, f"Service '{svc_name}' mounts ${{HOME}}: {v_str} (P1.7 violation)"
                assert "$HOME" not in v_str, f"Service '{svc_name}' mounts $HOME: {v_str} (P1.7 violation)"
                # /host:ro может присутствовать только если это конкретная директория
                # (не $HOME). Допускаем ./host:/app/host:ro и подобные.

    def test_no_home_mount_in_raw_text(self) -> None:
        """В сыром тексте docker-compose.yml не должно быть активной монтировки $HOME.

        Допускаются только комментарии, упоминающие $HOME как пример/предупреждение.
        Активная монтировка = строка вида '- ${HOME}:/...' не в комментарии.
        """
        content = COMPOSE_FILE.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            # Пропускаем комментарии
            if stripped.startswith("#"):
                continue
            # Активная монтировка $HOME
            assert "${HOME}" not in stripped, f"Line {line_num}: active ${{HOME}} mount: {line}"
            # Проверяем что /host:ro не используется с $HOME
            if "/host:ro" in stripped and not stripped.startswith("#"):
                # Допускаем только явные относительные пути (./...) или именованные volumes
                if "-" in stripped:
                    parts = stripped.split("-", 1)[1].strip().split(":")
                    if len(parts) >= 2:
                        source = parts[0].strip()
                        assert source.startswith(".") or not source.startswith("$"), (
                            f"Line {line_num}: suspicious /host:ro mount source: {source}"
                        )

    def test_data_volumes_preserved(self) -> None:
        """Persist-монтировки data/derived/runtime должны остаться."""
        with open(COMPOSE_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cli_vols = cfg["services"]["cli"].get("volumes", [])
        vol_strs = [str(v) for v in cli_vols]
        assert any("./data:/app/data" in s for s in vol_strs), "cli service must mount ./data:/app/data"
        assert any("./derived:/app/derived" in s for s in vol_strs), "cli service must mount ./derived:/app/derived"
        assert any("./runtime:/app/runtime" in s for s in vol_strs), "cli service must mount ./runtime:/app/runtime"

    def test_comment_documents_replacement(self) -> None:
        """В комментарии должно быть указано как явно примонтировать конкретную
        директорию вместо $HOME — для удобства пользователей."""
        content = COMPOSE_FILE.read_text(encoding="utf-8")
        # Должен быть комментарий с инструкцией
        assert "bsl-sources" in content or "конкретную директорию" in content, (
            "docker-compose.yml should have a comment explaining how to mount a specific directory instead of $HOME"
        )
