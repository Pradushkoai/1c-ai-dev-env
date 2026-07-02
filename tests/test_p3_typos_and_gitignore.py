"""
Regression-тесты для P3.18, P3.19, P3.20.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestP318CallGraphTypo:
    """P3.18: 'Сре' → 'Сред' в BSL_KEYWORDS."""

    def test_no_truncated_sre(self) -> None:
        """В call_graph.py не должно быть 'Сре' (truncated)."""
        result = subprocess.run(
            ["grep", "-rn", '"Сре"', str(REPO_ROOT / "src")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            f"Found truncated 'Сре' (should be 'Сред'):\n{result.stdout}"
        )

    def test_sred_present(self) -> None:
        """BSL_KEYWORDS должен содержать 'Сред' (Mid function)."""
        call_graph = REPO_ROOT / "src" / "services" / "call_graph.py"
        content = call_graph.read_text(encoding="utf-8")
        assert '"Сред"' in content, "BSL_KEYWORDS must contain 'Сред' (P3.18 fix)"


class TestP319LoggerTypo:
    """P3.19: '多次' → 'многократно' в logger.py."""

    def test_no_chinese_characters(self) -> None:
        """В logger.py не должно быть китайских иероглифов."""
        logger = REPO_ROOT / "src" / "services" / "logger.py"
        content = logger.read_text(encoding="utf-8")
        # Простой поиск CJK иероглифов
        for char in content:
            if "\u4e00" <= char <= "\u9fff":
                pytest.fail(
                    f"Chinese character '{char}' found in logger.py "
                    f"(should be Russian after P3.19 fix)"
                )

    def test_mnogokratno_present(self) -> None:
        """В docstring должно быть 'многократно'."""
        logger = REPO_ROOT / "src" / "services" / "logger.py"
        content = logger.read_text(encoding="utf-8")
        assert "многократно" in content


class TestP320Gitignore:
    """P3.20: .gitignore расширен IDE и логами."""

    def test_vscode_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".vscode/" in content

    def test_idea_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".idea/" in content

    def test_log_files_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "*.log" in content

    def test_pytest_cache_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".pytest_cache/" in content

    def test_venv_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".venv/" in content

    def test_ds_store_ignored(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".DS_Store" in content

    def test_vscode_actually_ignored_by_git(self, tmp_path) -> None:
        """git check-ignore должен игнорировать .vscode/ файлы."""
        # Создаём .vscode/settings.json
        vscode_dir = REPO_ROOT / ".vscode"
        test_file = vscode_dir / "settings.json"
        original_exists = test_file.exists()
        if not original_exists:
            vscode_dir.mkdir(exist_ok=True)
            test_file.write_text("{}", encoding="utf-8")
        try:
            result = subprocess.run(
                ["git", "check-ignore", str(test_file)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f".vscode/settings.json should be gitignored, got: {result.stderr}"
            )
        finally:
            if not original_exists:
                test_file.unlink(missing_ok=True)
                # Не удаляем .vscode/ — может быть у разработчика
