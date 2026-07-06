"""
Тесты для src/mcpserver/handlers/analyzers.py — BSL анализаторы.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.analyzers import (
    handle_analyze_bsl,
    handle_check_standards,
    handle_solve_check,
    handle_solve_context,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.scripts_dir = Path("/scripts")
    project.paths.root = Path("/root")
    return project


# ─── handle_analyze_bsl ───


class TestHandleAnalyzeBsl:
    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        project = _make_project()
        result = MagicMock()
        result.total = 5
        result.by_code = {"STD001": 3, "STD002": 2}
        result.diagnostics = []
        project.bsl_analyzer.analyze.return_value = result

        data = _parse(await handle_analyze_bsl(project, {"file_path": "/tmp/test.bsl"}))
        assert data["total"] == 5
        assert data["by_code"]["STD001"] == 3

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        project.bsl_analyzer.analyze.side_effect = RuntimeError("fail")
        data = _parse(await handle_analyze_bsl(project, {"file_path": "/tmp/test.bsl"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_diagnostics_truncated(self):
        project = _make_project()
        result = MagicMock()
        result.total = 100
        result.by_code = {}
        result.diagnostics = [{"code": f"D{i}"} for i in range(100)]
        project.bsl_analyzer.analyze.return_value = result

        data = _parse(await handle_analyze_bsl(project, {"file_path": "/tmp/test.bsl"}))
        assert len(data["diagnostics"]) == 50  # truncated


# ─── handle_check_standards ───


class TestHandleCheckStandards:
    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        # Этап 1.2, Группа 1f: handler использует прямой импорт из src.services.analyzers.
        # При несуществующем файле StandardsChecker возвращает violation с rule_id='read-error'.
        data = _parse(await handle_check_standards(project, {"file_path": "/tmp/test.bsl"}))
        # data — это список violations (не dict с error), поскольку прямой импорт всегда доступен.
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(v.get("rule_id") == "read-error" or v.get("severity") == "error" for v in data)

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_check_standards(project, {}))
        # Should handle empty file_path gracefully
        assert "error" in data or isinstance(data, list)


# ─── handle_solve_context ───


class TestHandleSolveContext:
    @pytest.mark.asyncio
    async def test_successful_context(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            ctx = MagicMock()
            ctx.to_dict.return_value = {"query": "test", "results": []}
            mock_tp.solve.return_value = ctx

            data = _parse(await handle_solve_context(project, {"query": "test", "config": "ut11"}))
            assert data["query"] == "test"

    @pytest.mark.asyncio
    async def test_default_limit(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            ctx = MagicMock()
            ctx.to_dict.return_value = {}
            mock_tp.solve.return_value = ctx

            await handle_solve_context(project, {"query": "test"})
            mock_tp.solve.assert_called_once_with("test", config_name="", limit=5)

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            mock_tp.solve.side_effect = RuntimeError("fail")

            # solve_context doesn't have try/except, will propagate
            with pytest.raises(RuntimeError):
                await handle_solve_context(project, {"query": "test"})


# ─── handle_solve_check ───


class TestHandleSolveCheck:
    @pytest.mark.asyncio
    async def test_successful_check(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            result = MagicMock()
            result.to_dict.return_value = {"verdict": "ready", "total_errors": 0}
            mock_tp.check.return_value = result

            data = _parse(await handle_solve_check(project, {"file_path": "/tmp/test.bsl"}))
            assert data["verdict"] == "ready"

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            mock_tp.check.side_effect = FileNotFoundError("not found")

            data = _parse(await handle_solve_check(project, {"file_path": "/missing.bsl"}))
            assert "error" in data

    @pytest.mark.asyncio
    async def test_custom_level(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            result = MagicMock()
            result.to_dict.return_value = {"verdict": "warnings"}
            mock_tp.check.return_value = result

            await handle_solve_check(project, {"file_path": "/tmp/test.bsl", "level": "full"})
            mock_tp.check.assert_called_once_with(Path("/tmp/test.bsl"), level="full")

    @pytest.mark.asyncio
    async def test_default_level(self):
        project = _make_project()
        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            result = MagicMock()
            result.to_dict.return_value = {}
            mock_tp.check.return_value = result

            await handle_solve_check(project, {"file_path": "/tmp/test.bsl"})
            mock_tp.check.assert_called_once_with(Path("/tmp/test.bsl"), level="standard")
