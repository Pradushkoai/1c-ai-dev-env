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


# ============================================================================
# P1.4: Tests — install.sh не должен содержать хардкод /home/z/my-project
# ============================================================================


class TestInstallShNoHardcodedPath:
    """P1.4: install.sh не должен хардкодить /home/z/my-project как дефолт.

    Regression: до P1.4 строка 14 содержала:
        PROJECT_DIR="${PROJECT_DIR:-/home/z/my-project}"
    Это делало установку непортабельной. P1.4 требует явного указания
    целевой директории через --target или ONEC_AI_DEV_ENV_ROOT env var.
    """

    def test_no_hardcoded_default_in_project_dir_assignment(self) -> None:
        """Строка PROJECT_DIR не должна содержать дефолт /home/z/my-project."""
        content = INSTALL_SH.read_text(encoding="utf-8")
        # Ищем pattern: PROJECT_DIR="${...:-/home/z/my-project}"
        # или PROJECT_DIR="/home/z/my-project"
        import re

        # Pattern 1: PROJECT_DIR="${VAR:-/home/z/my-project}"
        pattern1 = re.compile(r'PROJECT_DIR\s*=\s*"\$\{[^}]*:-/home/z/my-project\}"')
        # Pattern 2: PROJECT_DIR="/home/z/my-project" (без env var)
        pattern2 = re.compile(r'PROJECT_DIR\s*=\s*"/home/z/my-project"')
        assert not pattern1.search(content), (
            "install.sh содержит хардкод /home/z/my-project в PROJECT_DIR "
            "(P1.4 regression). Используйте --target или ONEC_AI_DEV_ENV_ROOT."
        )
        assert not pattern2.search(content), (
            "install.sh содержит хардкод /home/z/my-project в PROJECT_DIR "
            "(P1.4 regression). Используйте --target или ONEC_AI_DEV_ENV_ROOT."
        )

    def test_install_sh_requires_target_or_env_var(self) -> None:
        """install.sh без аргументов и env var должен завершаться с ошибкой (exit 1)."""
        # Запускаем без аргументов и без env var
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin"}
        result = subprocess.run(
            ["bash", str(INSTALL_SH)],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert result.returncode == 1, (
            f"install.sh без аргументов должен exit 1, got {result.returncode}.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "целевая директория не указана" in result.stdout or "не указана" in result.stdout, (
            f"install.sh должен показать сообщение об ошибке.\nstdout={result.stdout}"
        )

    def test_install_sh_help_works(self) -> None:
        """install.sh --help должен показать справку и exit 0."""
        result = subprocess.run(
            ["bash", str(INSTALL_SH), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "ONEC_AI_DEV_ENV_ROOT" in result.stdout, "install.sh --help должен упоминать ONEC_AI_DEV_ENV_ROOT"
        assert "--target" in result.stdout, "install.sh --help должен упоминать --target"

    def test_install_sh_target_arg_accepted(self) -> None:
        """install.sh --target /tmp/... должен принять путь (не упасть на arg parsing).

        Установка может занять минуты (pip install, git clone), поэтому
        проверяем только arg parsing: запускаем с коротким timeout и
        проверяем, что 'целевая директория не указана' НЕ выведено,
        а 'Путь: /tmp/...' выведено. TimeoutExpired приемлем.
        """
        import shutil

        try:
            result = subprocess.run(
                ["bash", str(INSTALL_SH), "--target", "/tmp/test-p1x-install", "--non-interactive"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            stdout = result.stdout
        except subprocess.TimeoutExpired as e:
            # Timeout OK — значит arg parsing прошёл и установка началась
            stdout = (
                (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )

        assert "целевая директория не указана" not in stdout, (
            f"--target должен принять путь, но получена ошибка.\nstdout={stdout}"
        )
        assert "Путь: /tmp/test-p1x-install" in stdout, (
            f"install.sh должен показать 'Путь: /tmp/test-p1x-install'.\nstdout={stdout}"
        )
        # Cleanup
        shutil.rmtree("/tmp/test-p1x-install", ignore_errors=True)

    def test_install_sh_onec_ai_dev_env_root_env_var_accepted(self) -> None:
        """ONEC_AI_DEV_ENV_ROOT env var должна приниматься как целевая директория."""
        import shutil

        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": "/tmp",
            "ONEC_AI_DEV_ENV_ROOT": "/tmp/test-p1x-env-install",
        }
        try:
            result = subprocess.run(
                ["bash", str(INSTALL_SH), "--non-interactive"],
                capture_output=True,
                text=True,
                timeout=8,
                env=env,
            )
            stdout = result.stdout
        except subprocess.TimeoutExpired as e:
            stdout = (
                (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )

        assert "целевая директория не указана" not in stdout, f"ONEC_AI_DEV_ENV_ROOT должна приняться.\nstdout={stdout}"
        assert "Путь: /tmp/test-p1x-env-install" in stdout, (
            f"install.sh должен показать путь из env var.\nstdout={stdout}"
        )
        # Cleanup
        shutil.rmtree("/tmp/test-p1x-env-install", ignore_errors=True)

    def test_install_sh_project_dir_legacy_env_var_still_works(self) -> None:
        """PROJECT_DIR env var (legacy) должна работать для backward compat."""
        import shutil

        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": "/tmp",
            "PROJECT_DIR": "/tmp/test-p1x-legacy-install",
        }
        try:
            result = subprocess.run(
                ["bash", str(INSTALL_SH), "--non-interactive"],
                capture_output=True,
                text=True,
                timeout=8,
                env=env,
            )
            stdout = result.stdout
        except subprocess.TimeoutExpired as e:
            stdout = (
                (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            )

        assert "целевая директория не указана" not in stdout, f"PROJECT_DIR (legacy) должна приняться.\nstdout={stdout}"
        # Cleanup
        shutil.rmtree("/tmp/test-p1x-legacy-install", ignore_errors=True)

    def test_install_sh_unknown_arg_rejected(self) -> None:
        """Неизвестный аргумент должен вызвать ошибку (exit 1)."""
        result = subprocess.run(
            ["bash", str(INSTALL_SH), "--unknown-flag"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 1, f"Неизвестный аргумент должен exit 1, got {result.returncode}"
        assert "Неизвестный аргумент" in result.stdout or "Неизвестный аргумент" in result.stderr, (
            f"Должно быть сообщение 'Неизвестный аргумент'.\nstdout={result.stdout}\nstderr={result.stderr}"
        )
