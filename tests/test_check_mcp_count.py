"""
Тесты для scripts/check_mcp_count.py — CI blocking gate.

Этот скрипт используется в .github/workflows/ci.yml для блокировки PR
при рассинхронизации кол-ва MCP tools между:
- src/mcp_server.py (list_tools handler) — фактическое кол-во
- src/mcp_server.py (_get_tools_description) — статическое описание
- manifest.json (mcp_tools_count)
- README.md (badge + inline mentions)
- docs/MCP_INTEGRATION.md
- docs/ARCHITECTURE.md
- AGENTS.md

Regression: P1.6 (snapshot testing) зафиксировал контракт 45 tools.
Любое изменение требует обновления всех источников.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts/ to sys.path
_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from check_mcp_count import get_actual_tools_count, get_static_tools_count, main  # noqa: E402


# ============================================================================
# Тесты — функции подсчёта
# ============================================================================


class TestGetActualToolsCount:
    """get_actual_tools_count() — кол-во tools из list_tools handler."""

    def test_returns_positive_count(self) -> None:
        """Должно возвращать положительное число (45 tools)."""
        count = get_actual_tools_count()
        assert count > 0, "Should return positive count"
        assert count == 45, f"Expected 45 tools (per snapshot contract), got {count}"

    def test_returns_int(self) -> None:
        """Должно возвращать int (не float/str)."""
        count = get_actual_tools_count()
        assert isinstance(count, int)

    def test_works_with_mocked_project(self) -> None:
        """Должно работать с mocked Project (не требует реальной конфигурации 1С)."""
        with patch("src.project.Project"):
            count = get_actual_tools_count()
            assert count == 45


class TestGetStaticToolsCount:
    """get_static_tools_count() — кол-во tools из _get_tools_description()."""

    def test_returns_positive_count(self) -> None:
        count = get_static_tools_count()
        assert count > 0
        assert count == 45, f"Expected 45 (per snapshot), got {count}"

    def test_returns_int(self) -> None:
        count = get_static_tools_count()
        assert isinstance(count, int)

    def test_matches_actual_count(self) -> None:
        """Статическое описание должно совпадать с фактическим list_tools handler.

        Это критический инвариант: если кто-то добавит tool в list_tools,
        но забудет обновить _get_tools_description() (или наоборот) —
        этот тест упадёт.
        """
        actual = get_actual_tools_count()
        static = get_static_tools_count()
        assert actual == static, (
            f"Drift detected: list_tools={actual}, _get_tools_description={static}. "
            f"Run check_mcp_count.py to investigate."
        )


# ============================================================================
# Тесты — main() exit codes
# ============================================================================


class TestMainExitCodes:
    """main() должна возвращать 0 при консистентности, 1 при расхождениях."""

    def test_main_returns_zero_on_consistent_state(self) -> None:
        """На текущем репозитории main() должна вернуть 0 (всё консистентно)."""
        # Меняем cwd на repo root, так как main() использует Path(__file__).parent.parent
        # Но через import мы уже находимся в правильном контексте
        exit_code = main()
        assert exit_code == 0, (
            "main() should return 0 when all sources are consistent. "
            "If this fails, run `python3 scripts/check_mcp_count.py` to see drift."
        )

    def test_main_returns_one_on_manifest_drift(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """При рассинхронизации manifest.json main() должна вернуть 1."""
        # Создаём временный manifest с неправильным count
        # Это сложно тестировать изолированно, потому что main() использует
        # Path(__file__).parent.parent для поиска repo root.
        # Вместо этого — мокаем manifest.json content.
        repo_root = _REPO_ROOT

        # Backup и подмена manifest.json
        manifest_path = repo_root / "manifest.json"
        original_content = manifest_path.read_text(encoding="utf-8")

        try:
            # Меняем mcp_tools_count на неправильное значение
            manifest_data = json.loads(original_content)
            original_count = manifest_data.get("mcp_tools_count")
            manifest_data["mcp_tools_count"] = 999  # заведомо неверное
            manifest_path.write_text(
                json.dumps(manifest_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            exit_code = main()
            assert exit_code == 1, "Should return 1 when manifest.json has wrong count"
        finally:
            # Восстанавливаем оригинальный manifest
            manifest_path.write_text(original_content, encoding="utf-8")

    def test_main_returns_one_on_readme_badge_drift(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """При рассинхронизации README badge main() должна вернуть 1."""
        repo_root = _REPO_ROOT
        readme_path = repo_root / "README.md"
        original_content = readme_path.read_text(encoding="utf-8")

        try:
            # Меняем badge MCP%20tools-45 на MCP%20tools-99
            modified = original_content.replace("MCP%20tools-45", "MCP%20tools-99")
            assert modified != original_content, "Test setup failed: badge pattern not found"
            readme_path.write_text(modified, encoding="utf-8")

            exit_code = main()
            assert exit_code == 1, "Should return 1 when README badge has wrong count"
        finally:
            readme_path.write_text(original_content, encoding="utf-8")


# ============================================================================
# Тесты — источник истины
# ============================================================================


class TestSourcesOfTruth:
    """Все источники должны сходиться к одному числу — 45."""

    def test_manifest_json_has_correct_count(self) -> None:
        """manifest.json: mcp_tools_count должен быть 45."""
        manifest_path = _REPO_ROOT / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest.get("mcp_tools_count") == 45, (
            f"manifest.json mcp_tools_count={manifest.get('mcp_tools_count')}, expected 45"
        )

    def test_readme_badge_has_correct_count(self) -> None:
        """README.md: badge MCP%20tools-XX должен быть 45."""
        readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
        import re

        match = re.search(r"MCP%20tools-(\d+)", readme)
        assert match is not None, "MCP tools badge not found in README.md"
        assert int(match.group(1)) == 45, f"README badge={match.group(1)}, expected 45"

    def test_actual_count_matches_snapshot(self) -> None:
        """Фактическое кол-во tools должно совпадать со snapshot тестом.

        Snapshot: tests/snapshots/test_mcp_tools_snapshot/test_tool_count_snapshot/tool_count.txt
        """
        snapshot_path = _REPO_ROOT / "tests/snapshots/test_mcp_tools_snapshot/test_tool_count_snapshot/tool_count.txt"
        snapshot_content = snapshot_path.read_text(encoding="utf-8")
        # Snapshot format: "Total MCP tools: 45\n"
        import re

        match = re.search(r"Total MCP tools:\s*(\d+)", snapshot_content)
        assert match is not None, f"Snapshot file format unexpected: {snapshot_content!r}"
        snapshot_count = int(match.group(1))

        actual_count = get_actual_tools_count()
        assert actual_count == snapshot_count, (
            f"Drift: actual={actual_count}, snapshot={snapshot_count}. "
            f"Run: pytest tests/test_mcp_tools_snapshot.py --snapshot-update"
        )
