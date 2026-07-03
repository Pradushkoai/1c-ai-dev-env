"""
Regression-тесты для P1.8: path traversal protection в MCP handlers.

До фикса: handlers в src/mcpserver/handlers/quality.py принимали file_path
без проверки, что резолвнутый путь находится внутри project.paths.root.
Это позволяло MCP-клиенту передать file_path='../../../../etc/passwd' и
получить содержимое любого файла, доступного процессу.

После фикса: все handlers используют resolve_path_within_project() из
_security.py, который через os.path.realpath() раскрывает '..' и симлинки,
затем проверяет что путь внутри project.paths.root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mcpserver.handlers._security import (
    is_path_within_project,
    resolve_path_within_project,
)
from src.mcpserver.handlers.quality import (
    handle_analyze_architecture,
    handle_audit_security,
    handle_check_transactions,
    handle_diff_configs,
    handle_get_code_metrics,
)


# ============================================================================
# Helpers
# ============================================================================


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project(tmp_path: Path) -> MagicMock:
    """Project с реальным root во tmp_path (для realpath-проверок)."""
    project = MagicMock()
    project.paths.root = tmp_path
    # Создаём scripts/ директорию для handler'ов, которые её ищут
    (tmp_path / "scripts").mkdir(exist_ok=True)
    return project


# ============================================================================
# Тесты самого helper'а resolve_path_within_project
# ============================================================================


class TestResolvePathWithinProject:
    """Юнит-тесты для _security.resolve_path_within_project."""

    def test_relative_path_resolved_against_project_root(self, tmp_path: Path) -> None:
        """Относительный путь считается относительно project.paths.root."""
        project = _make_project(tmp_path)
        result = resolve_path_within_project("data/file.bsl", project)
        assert result == (tmp_path / "data" / "file.bsl").resolve()

    def test_absolute_path_inside_project_ok(self, tmp_path: Path) -> None:
        """Абсолютный путь внутри проекта — OK."""
        project = _make_project(tmp_path)
        abs_path = str(tmp_path / "src" / "module.py")
        result = resolve_path_within_project(abs_path, project)
        assert result is not None
        assert result == (tmp_path / "src" / "module.py").resolve()

    def test_dotdot_traversal_blocked(self, tmp_path: Path) -> None:
        """'../../../etc/passwd' — path traversal, должен вернуть None."""
        project = _make_project(tmp_path)
        result = resolve_path_within_project("../../../etc/passwd", project)
        assert result is None, (
            f"Path traversal via '..' must be blocked — got: {result} (would allow access to files outside project)"
        )

    def test_absolute_path_outside_project_blocked(self, tmp_path: Path) -> None:
        """/etc/passwd — абсолютный путь вне проекта, должен вернуть None."""
        project = _make_project(tmp_path)
        result = resolve_path_within_project("/etc/passwd", project)
        assert result is None

    def test_empty_path_returns_none(self, tmp_path: Path) -> None:
        """Пустая строка → None."""
        project = _make_project(tmp_path)
        assert resolve_path_within_project("", project) is None

    def test_must_exist_flag(self, tmp_path: Path) -> None:
        """must_exist=True → None если файл не существует."""
        project = _make_project(tmp_path)
        # Файл не существует
        result = resolve_path_within_project("nonexistent.bsl", project, must_exist=True)
        assert result is None
        # Создаём файл
        (tmp_path / "exists.bsl").write_text("// ok", encoding="utf-8")
        result = resolve_path_within_project("exists.bsl", project, must_exist=True)
        assert result is not None

    def test_nested_dotdot_within_project_ok(self, tmp_path: Path) -> None:
        """'data/../src/file.bsl' — '..' внутри проекта, должен пройти."""
        project = _make_project(tmp_path)
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "file.bsl").write_text("// ok", encoding="utf-8")
        result = resolve_path_within_project("data/../src/file.bsl", project)
        assert result is not None
        assert result == (tmp_path / "src" / "file.bsl").resolve()

    def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        """Симлинк, указывающий за пределы проекта, должен быть заблокирован.

        os.path.realpath раскрывает симлинки, поэтому атака через симлинк
        не проходит.
        """
        project = _make_project(tmp_path)
        # Создаём /tmp/secret вне проекта
        secret_file = tmp_path.parent / "secret_outside.txt"
        try:
            secret_file.write_text("SECRET", encoding="utf-8")
            # Создаём симлинк внутри проекта, указывающий на secret_file
            link = tmp_path / "link_to_secret.bsl"
            try:
                os.symlink(secret_file, link)
            except OSError:
                pytest.skip("symlink creation not supported on this platform")
            # Через симлинк пытаемся прочитать secret
            result = resolve_path_within_project("link_to_secret.bsl", project)
            assert result is None, f"Symlink escape must be blocked — got: {result} (would allow reading {secret_file})"
        finally:
            if secret_file.exists():
                secret_file.unlink()


# ============================================================================
# Тесты handlers — path traversal блокируется
# ============================================================================


class TestHandlerPathTraversalBlocked:
    """Все handlers с file_path должны блокировать path traversal."""

    @pytest.mark.asyncio
    async def test_audit_security_blocks_traversal(self, tmp_path: Path) -> None:
        """handle_audit_security('file_path=../../../etc/passwd') → error."""
        project = _make_project(tmp_path)
        result = await handle_audit_security(project, {"file_path": "../../../etc/passwd"})
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_code_metrics_blocks_traversal(self, tmp_path: Path) -> None:
        """handle_get_code_metrics('file_path=../../../etc/passwd') → error."""
        project = _make_project(tmp_path)
        result = await handle_get_code_metrics(project, {"file_path": "../../../etc/passwd"})
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_check_transactions_blocks_traversal(self, tmp_path: Path) -> None:
        """handle_check_transactions('file_path=../../../etc/passwd') → error."""
        project = _make_project(tmp_path)
        result = await handle_check_transactions(project, {"file_path": "../../../etc/passwd"})
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_analyze_architecture_blocks_traversal(self, tmp_path: Path) -> None:
        """handle_analyze_architecture('config_dir=../../../etc') → error."""
        project = _make_project(tmp_path)
        result = await handle_analyze_architecture(project, {"config_dir": "../../../etc"})
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_diff_configs_blocks_traversal_in_old_path(self, tmp_path: Path) -> None:
        """handle_diff_configs('old_path=../../../etc/passwd', ...) → error."""
        project = _make_project(tmp_path)
        result = await handle_diff_configs(
            project,
            {
                "old_path": "../../../etc/passwd",
                "new_path": "data/new.json",
            },
        )
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_diff_configs_blocks_traversal_in_new_path(self, tmp_path: Path) -> None:
        """handle_diff_configs('new_path=../../../etc/passwd', ...) → error."""
        project = _make_project(tmp_path)
        result = await handle_diff_configs(
            project,
            {
                "old_path": "data/old.json",
                "new_path": "../../../etc/passwd",
            },
        )
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_audit_security_blocks_absolute_outside(self, tmp_path: Path) -> None:
        """handle_audit_security('file_path=/etc/passwd') → error."""
        project = _make_project(tmp_path)
        result = await handle_audit_security(project, {"file_path": "/etc/passwd"})
        data = _parse(result)
        assert "error" in data
        assert "path traversal" in data["error"].lower()


# ============================================================================
# Тесты handlers — валидные пути работают как прежде
# ============================================================================


class TestHandlerValidPathsStillWork:
    """После P1.8 валидные пути внутри проекта продолжают работать."""

    @pytest.mark.asyncio
    async def test_audit_security_valid_path_no_traversal_error(self, tmp_path: Path) -> None:
        """handle_audit_security с валидным путём НЕ возвращает path traversal."""
        project = _make_project(tmp_path)
        # Создаём .bsl файл внутри проекта
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("// empty", encoding="utf-8")
        # security_auditor.py не существует → другой error, но НЕ path traversal
        result = await handle_audit_security(project, {"file_path": "test.bsl"})
        data = _parse(result)
        # Ожидаем либо success, либо error про security_auditor.py — но НЕ path traversal
        assert "path traversal" not in data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_audit_security_relative_path_resolves(self, tmp_path: Path) -> None:
        """Относительный путь резолвится относительно project root."""
        project = _make_project(tmp_path)
        # Создаём .bsl в подпапке
        (tmp_path / "src").mkdir(exist_ok=True)
        bsl_file = tmp_path / "src" / "test.bsl"
        bsl_file.write_text("// empty", encoding="utf-8")
        result = await handle_audit_security(project, {"file_path": "src/test.bsl"})
        data = _parse(result)
        # Должен пройти path traversal check (возможно другая ошибка —
        # security_auditor.py отсутствует, но это OK)
        assert "path traversal" not in data.get("error", "").lower()


# ============================================================================
# Тесты — backward compatibility
# ============================================================================


class TestHandlerBackwardCompatibility:
    """Существующее поведение для отсутствующих/пустых параметров сохранено."""

    @pytest.mark.asyncio
    async def test_audit_security_missing_file_path_still_error(self, tmp_path: Path) -> None:
        """handle_audit_security({}) → 'file_path is required' (как раньше)."""
        project = _make_project(tmp_path)
        result = await handle_audit_security(project, {})
        data = _parse(result)
        assert "error" in data
        assert "file_path is required" in data["error"]

    @pytest.mark.asyncio
    async def test_diff_configs_missing_paths_still_error(self, tmp_path: Path) -> None:
        """handle_diff_configs({}) → 'old_path and new_path required'."""
        project = _make_project(tmp_path)
        result = await handle_diff_configs(project, {})
        data = _parse(result)
        assert "error" in data
        assert "old_path and new_path required" in data["error"]
