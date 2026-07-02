"""
Тесты для src/mcpserver/handlers/misc.py — OpenSpec handlers.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.misc import (
    handle_openspec_archive,
    handle_openspec_list,
    handle_openspec_proposal,
    handle_openspec_update_task,
)


def _make_project():
    project = MagicMock()
    project.paths.root = MagicMock()
    project.paths.root.__truediv__ = MagicMock(return_value=MagicMock())
    return project


def _parse_result(result):
    """Parse TextContent list to dict."""
    assert len(result) == 1
    return json.loads(result[0].text)


# ─── handle_openspec_proposal ───


class TestHandleOpenspecProposal:
    @pytest.mark.asyncio
    async def test_missing_change_id(self):
        project = _make_project()
        result = await handle_openspec_proposal(project, {"title": "Test"})
        data = _parse_result(result)
        assert "error" in data
        assert "change_id" in data["error"]

    @pytest.mark.asyncio
    async def test_missing_title(self):
        project = _make_project()
        result = await handle_openspec_proposal(project, {"change_id": "test-change"})
        data = _parse_result(result)
        assert "error" in data
        assert "title" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_proposal(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.exists.return_value = True
            change = MagicMock()
            change.change_id = "test-change"
            change.title = "Test Change"
            change.status = "proposed"
            change.tasks = ["task1", "task2"]
            mock_osm.create_proposal.return_value = change

            result = await handle_openspec_proposal(
                project,
                {"change_id": "test-change", "title": "Test Change", "tasks": ["task1", "task2"]},
            )
            data = _parse_result(result)
            assert data["change_id"] == "test-change"
            assert data["title"] == "Test Change"
            assert data["status"] == "proposed"
            assert data["tasks_count"] == 2

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.exists.side_effect = RuntimeError("fail")

            result = await handle_openspec_proposal(project, {"change_id": "test", "title": "Test"})
            data = _parse_result(result)
            assert "error" in data


# ─── handle_openspec_list ───


class TestHandleOpenspecList:
    @pytest.mark.asyncio
    async def test_list_changes(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.list_changes.return_value = [
                {"change_id": "c1", "title": "Change 1", "status": "proposed"},
                {"change_id": "c2", "title": "Change 2", "status": "archived"},
            ]

            result = await handle_openspec_list(project, {})
            data = _parse_result(result)
            assert "changes" in data
            assert len(data["changes"]) == 2

    @pytest.mark.asyncio
    async def test_list_with_archived(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.list_changes.return_value = []

            result = await handle_openspec_list(project, {"include_archived": True})
            data = _parse_result(result)
            assert "changes" in data

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.list_changes.side_effect = RuntimeError("fail")

            result = await handle_openspec_list(project, {})
            data = _parse_result(result)
            assert "error" in data


# ─── handle_openspec_update_task ───


class TestHandleOpenspecUpdateTask:
    @pytest.mark.asyncio
    async def test_missing_change_id(self):
        project = _make_project()
        result = await handle_openspec_update_task(project, {"task_index": 0})
        data = _parse_result(result)
        assert "error" in data
        assert "change_id" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_update(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.update_task.return_value = True

            result = await handle_openspec_update_task(
                project, {"change_id": "test", "task_index": 0, "completed": True}
            )
            data = _parse_result(result)
            assert data["updated"] is True

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.update_task.side_effect = RuntimeError("fail")

            result = await handle_openspec_update_task(project, {"change_id": "test", "task_index": 0})
            data = _parse_result(result)
            assert "error" in data


# ─── handle_openspec_archive ───


class TestHandleOpenspecArchive:
    @pytest.mark.asyncio
    async def test_missing_change_id(self):
        project = _make_project()
        result = await handle_openspec_archive(project, {})
        data = _parse_result(result)
        assert "error" in data
        assert "change_id" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_archive(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.archive.return_value = True

            result = await handle_openspec_archive(project, {"change_id": "test"})
            data = _parse_result(result)
            assert data["archived"] is True

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.openspec_manager.OpenSpecManager") as mock_osm_class:
            mock_osm = mock_osm_class.return_value
            mock_osm.archive.side_effect = RuntimeError("fail")

            result = await handle_openspec_archive(project, {"change_id": "test"})
            data = _parse_result(result)
            assert "error" in data
