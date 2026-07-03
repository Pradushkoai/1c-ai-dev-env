"""
Тесты для install.sh — проверка, что все python-команды, на которые он ссылается,
реально существуют в репозитории (P0.3 regression).

До фикса install.sh:218 вызывал scripts/register_config.py, которого не было в
репозитории — установка падала на шаге регистрации ZIP-конфигурации.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


# ============================================================================
# Helpers
# ============================================================================


def _extract_python_commands(install_sh_text: str) -> list[str]:
    """Извлекает все python3 -m src.cli ... и python3 scripts/... вызовы."""
    commands: list[str] = []
    # Ищем строки вида: python3 -m src.cli config add ...
    # или: python3 -m src.cli validate
    for match in re.finditer(
        r"python3\s+(-m\s+src\.cli\s+\S+(?:\s+\S+)*?|scripts/\S+)",
        install_sh_text,
    ):
        commands.append(match.group(1).strip())
    return commands


# ============================================================================
# Тесты
# ============================================================================


class TestInstallShCommandsExist:
    """Все python-команды в install.sh должны ссылаться на существующие модули/скрипты."""

    def test_install_sh_exists(self) -> None:
        """install.sh присутствует в репозитории."""
        assert INSTALL_SH.exists(), f"install.sh not found at {INSTALL_SH}"
        assert INSTALL_SH.is_file()

    def test_install_sh_bash_syntax_valid(self) -> None:
        """Bash-синтаксис install.sh корректен (bash -n)."""
        result = subprocess.run(
            ["bash", "-n", str(INSTALL_SH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"install.sh has bash syntax errors:\n{result.stderr}"

    def test_no_references_to_nonexistent_register_config(self) -> None:
        """install.sh НЕ должен вызывать scripts/register_config.py (он удалён).

        Regression для P0.3: до фикса install.sh:218,236,276-277 ссылался на
        scripts/register_config.py, которого не существует — установка падала
        с FileNotFoundError.
        """
        content = INSTALL_SH.read_text(encoding="utf-8")
        # Находим все ВЫЗОВЫ register_config.py (не комментарии)
        call_pattern = re.compile(r"^\s*python3\s+.*register_config\.py", re.MULTILINE)
        matches = call_pattern.findall(content)
        assert not matches, f"install.sh still calls register_config.py (P0.3 regression):\n{matches}"

    def test_install_sh_uses_src_cli_config_commands(self) -> None:
        """install.sh должен использовать `python3 -m src.cli config add/build`."""
        content = INSTALL_SH.read_text(encoding="utf-8")
        assert "python3 -m src.cli config add" in content, (
            "install.sh should call 'python3 -m src.cli config add' (P0.3 fix)"
        )
        assert "python3 -m src.cli config build" in content, (
            "install.sh should call 'python3 -m src.cli config build' (P0.3 fix)"
        )

    @pytest.mark.parametrize(
        "cli_subcommand",
        ["config", "config add", "config build", "config list", "validate"],
    )
    def test_src_cli_subcommands_exist(self, cli_subcommand: str) -> None:
        """Каждая используемая в install.sh CLI-подкоманда должна работать через
        `python3 -m src.cli <subcommand> --help`."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli"] + cli_subcommand.split() + ["--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"`python3 -m src.cli {cli_subcommand} --help` failed:\nstderr={result.stderr}\nstdout={result.stdout}"
        )

    def test_install_sh_final_report_uses_src_cli(self) -> None:
        """Финальный отчёт install.sh должен показывать `python3 -m src.cli config ...`
        как рекомендуемую команду (а не register_config.py)."""
        content = INSTALL_SH.read_text(encoding="utf-8")
        # Секция финального отчёта
        assert "python3 -m src.cli config list" in content, (
            "install.sh final report should mention 'python3 -m src.cli config list'"
        )
        assert "python3 -m src.cli config build --name X" in content, (
            "install.sh final report should mention 'python3 -m src.cli config build --name X'"
        )


class TestInstallShQuotedProperly:
    """Дополнительная проверка: команды должны быть корректно заквочены для
    передачи путей с пробелами/кириллицей."""

    def test_zip_path_quoted(self) -> None:
        """--zip "$CFG_ZIP" должен быть в кавычках (путь может содержать пробелы)."""
        content = INSTALL_SH.read_text(encoding="utf-8")
        assert '--zip "$CFG_ZIP"' in content

    def test_name_quoted(self) -> None:
        """--name "$CFG_NAME" должен быть в кавычках."""
        content = INSTALL_SH.read_text(encoding="utf-8")
        assert '--name "$CFG_NAME"' in content
