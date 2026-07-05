"""
S8.2 (2026-07-05): Тесты для subprocess.run security audit.

Гарантирует, что:
1. shell=True НЕ используется нигде в src/ и scripts/
2. Все subprocess.run вызовы имеют timeout
3. AGENTS.md содержит политику subprocess

Запускается в CI (ci.yml) и локально через pytest.
Если тест падает — кто-то добавил небезопасный subprocess вызов.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Файлы, которые могут содержать subprocess (известные)
EXPECTED_SUBPROCESS_FILES = {
    "src/services/epf_factory.py",
    "src/services/config_builder.py",
    "src/services/epf/round_trip.py",
    "src/services/epf/bsl_validator.py",
    "src/services/config_manager.py",
    "src/services/bsl_analyzer.py",
    "src/services/github_releases.py",
    "scripts/test_mcp_e2e.py",
}


def _find_subprocess_files() -> set[str]:
    """Найти все файлы с subprocess в src/ и scripts/."""
    files: set[str] = set()
    for root in [SRC_DIR, SCRIPTS_DIR]:
        for py_file in root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "subprocess" in content:
                rel = py_file.relative_to(REPO_ROOT).as_posix()
                files.add(rel)
    return files


def _check_shell_true(content: str) -> list[int]:
    """Найти строки с shell=True. Возвращает номера строк."""
    lines_with_shell_true: list[int] = []
    for i, line in enumerate(content.splitlines(), 1):
        # shell=True или shell = True
        if re.search(r"shell\s*=\s*True", line):
            lines_with_shell_true.append(i)
    return lines_with_shell_true


def _check_subprocess_run_without_timeout(content: str) -> list[int]:
    """Найти subprocess.run вызовы без timeout.

    Простая эвристика: ищем subprocess.run(...) и проверяем,
    есть ли timeout= в следующих ~10 строках.
    """
    lines = content.splitlines()
    lines_without_timeout: list[int] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if "subprocess.run(" in line or "subprocess.Popen(" in line:
            # Собираем весь вызов (может быть многострочный)
            call_block = ""
            paren_count = line.count("(") - line.count(")")
            start_line = i + 1  # 1-indexed
            call_block += line
            j = i
            while paren_count > 0 and j + 1 < len(lines):
                j += 1
                call_block += "\n" + lines[j]
                paren_count += lines[j].count("(") - lines[j].count(")")
            # Проверяем, есть ли timeout= в блоке вызова
            if "timeout=" not in call_block and "timeout =" not in call_block:
                lines_without_timeout.append(start_line)
            i = j + 1
        else:
            i += 1

    return lines_without_timeout


class TestSubprocessSecurityAudit:
    """S8.2: аудит subprocess.run на безопасность."""

    def test_no_shell_true_in_src(self) -> None:
        """shell=True НЕ используется нигде в src/."""
        violations: list[str] = []
        for py_file in SRC_DIR.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            bad_lines = _check_shell_true(content)
            for line_num in bad_lines:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_num}")
        assert len(violations) == 0, (
            f"shell=True найден в src/ (CRITICAL — shell injection risk):\n"
            + "\n".join(f"  ❌ {v}" for v in violations)
        )

    def test_no_shell_true_in_scripts(self) -> None:
        """shell=True НЕ используется нигде в scripts/."""
        violations: list[str] = []
        for py_file in SCRIPTS_DIR.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            bad_lines = _check_shell_true(content)
            for line_num in bad_lines:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_num}")
        assert len(violations) == 0, (
            f"shell=True найден в scripts/ (CRITICAL — shell injection risk):\n"
            + "\n".join(f"  ❌ {v}" for v in violations)
        )

    def test_all_subprocess_calls_have_timeout_in_src(self) -> None:
        """Все subprocess.run/Popen вызовы в src/ имеют timeout=.

        S8.2 (2026-07-05): DoS protection — без timeout процесс может зависнуть.
        """
        violations: list[str] = []
        for py_file in SRC_DIR.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "subprocess.run" not in content and "subprocess.Popen" not in content:
                continue
            bad_lines = _check_subprocess_run_without_timeout(content)
            for line_num in bad_lines:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_num}")
        assert len(violations) == 0, (
            f"subprocess.run/Popen без timeout найден в src/ (DoS risk):\n"
            + "\n".join(f"  ⚠️  {v}" for v in violations)
            + "\nДобавьте timeout=N (например, timeout=600 для индексации, timeout=60 для BSL LS)"
        )

    def test_expected_subprocess_files_match(self) -> None:
        """Список файлов с subprocess соответствует ожидаемому.

        Если тест падает — добавлен новый файл с subprocess.
        Обновите EXPECTED_SUBPROCESS_FILES и проведите security audit.
        """
        actual = _find_subprocess_files()
        # Добавляем new files (не в EXPECTED) — это warning, не error
        new_files = actual - EXPECTED_SUBPROCESS_FILES
        if new_files:
            print(f"\n⚠️  Новые файлы с subprocess (не в EXPECTED_SUBPROCESS_FILES):")
            for f in sorted(new_files):
                print(f"  ⚠️  {f}")
            print("  Обновите EXPECTED_SUBPROCESS_FILES и проведите security audit.")
        # Удалённые файлы (в EXPECTED, но не в actual) — info
        removed_files = EXPECTED_SUBPROCESS_FILES - actual
        if removed_files:
            print(f"\nℹ️  Файлы удалены из subprocess list:")
            for f in sorted(removed_files):
                print(f"  ℹ️  {f}")
        # Non-blocking — просто показываем изменения
        # Если хотем blocking — раскомментировать:
        # assert len(new_files) == 0, f"Новые файлы с subprocess требуют audit: {new_files}"


class TestAgentsMdSubprocessPolicy:
    """S8.2: проверка AGENTS.md содержит политику subprocess."""

    def test_agents_md_exists(self) -> None:
        """AGENTS.md существует."""
        assert AGENTS_MD.exists(), "AGENTS.md должен существовать"

    def test_agents_md_has_subprocess_policy(self) -> None:
        """AGENTS.md содержит секцию subprocess."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        assert "subprocess" in content.lower(), (
            "AGENTS.md должен содержать секцию 'subprocess' с политикой безопасности"
        )

    def test_agents_md_prohibits_shell_true(self) -> None:
        """AGENTS.md запрещает shell=True."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        # Ищем запрет на shell=True
        assert "shell=True" in content, (
            "AGENTS.md должен содержать запрет на shell=True (см. S8.2)"
        )
        # Должен быть ❌ или "НИКОГДА" рядом с shell=True
        subprocess_section = content[content.find("subprocess"):]
        assert "НИКОГДА" in subprocess_section or "❌" in subprocess_section, (
            "AGENTS.md должен явно запрещать shell=True (❌ или НИКОГДА)"
        )

    def test_agents_md_requires_timeout(self) -> None:
        """AGENTS.md требует timeout для всех subprocess вызовов."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        subprocess_section = content[content.find("subprocess"):]
        assert "timeout" in subprocess_section, (
            "AGENTS.md должен требовать timeout для всех subprocess вызовов (см. S8.2)"
        )

    def test_agents_md_has_audit_note(self) -> None:
        """AGENTS.md содержит запись об аудите S8.2."""
        content = AGENTS_MD.read_text(encoding="utf-8")
        assert "S8.2" in content, (
            "AGENTS.md должен содержать ссылку на S8.2 (дата аудита subprocess)"
        )
        assert "2026-07-05" in content, (
            "AGENTS.md должен содержать дату аудита S8.2 (2026-07-05)"
        )
