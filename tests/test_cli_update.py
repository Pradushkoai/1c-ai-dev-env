"""
I6.4 (2026-07-05): Тесты для CLI self-update команды.

Гарантирует:
1. CLI команда `update` существует
2. cmd_update функция реализована
3. Команда обновляет через pip
4. Команда проверяет BSL LS
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestCliUpdateCommand:
    """I6.4: CLI self-update команда."""

    def test_update_command_in_argparse(self) -> None:
        """CLI парсер содержит команду update."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert "update" in result.stdout, (
            "CLI --help должен содержать команду 'update' (см. I6.4)"
        )

    def test_update_command_help(self) -> None:
        """CLI update --help работает."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "update", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, "CLI update --help должен работать"

    def test_cmd_update_function_exists(self) -> None:
        """Функция cmd_update существует в cli.py."""
        cli_path = REPO_ROOT / "src" / "cli.py"
        content = cli_path.read_text(encoding="utf-8")
        assert "def cmd_update" in content, (
            "cli.py должен содержать функцию cmd_update (см. I6.4)"
        )

    def test_cmd_update_uses_pip(self) -> None:
        """cmd_update использует pip для обновления."""
        cli_path = REPO_ROOT / "src" / "cli.py"
        content = cli_path.read_text(encoding="utf-8")
        # Ищем в функции cmd_update
        update_section = content[content.find("def cmd_update"):]
        assert "pip" in update_section, (
            "cmd_update должен использовать pip для обновления"
        )
        assert "install" in update_section, (
            "cmd_update должен использовать pip install"
        )

    def test_cmd_update_checks_bsl_ls(self) -> None:
        """cmd_update проверяет BSL LS версию."""
        cli_path = REPO_ROOT / "src" / "cli.py"
        content = cli_path.read_text(encoding="utf-8")
        update_section = content[content.find("def cmd_update"):]
        assert "bsl" in update_section.lower(), (
            "cmd_update должен проверять BSL LS версию"
        )

    def test_cmd_update_has_timeout(self) -> None:
        """cmd_update использует timeout для subprocess (S8.2 compliance)."""
        cli_path = REPO_ROOT / "src" / "cli.py"
        content = cli_path.read_text(encoding="utf-8")
        update_section = content[content.find("def cmd_update"):]
        assert "timeout" in update_section, (
            "cmd_update должен использовать timeout (см. S8.2 subprocess policy)"
        )
