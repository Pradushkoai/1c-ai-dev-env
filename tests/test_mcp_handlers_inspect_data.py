"""
Тесты для src/mcpserver/handlers/inspect_data.py — inspect и data_status.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.inspect_data import handle_data_status, handle_inspect


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = Path("/repo")
    project.paths.scripts_dir = Path("/scripts")
    return project


class TestHandleInspect:
    @pytest.mark.asyncio
    async def test_missing_path(self):
        project = _make_project()
        data = _parse(await handle_inspect(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        project = _make_project()
        data = _parse(await handle_inspect(project, {"path": "/nonexistent"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unsupported_target(self, tmp_path):
        project = _make_project()
        test_file = tmp_path / "test.xml"
        test_file.write_text("<root/>", encoding="utf-8")
        data = _parse(await handle_inspect(project, {"path": str(test_file), "target": "unknown"}))
        assert "error" in data
        assert "available" in data

    @pytest.mark.asyncio
    async def test_depgraph_missing_config_name(self, tmp_path):
        project = _make_project()
        test_file = tmp_path / "test.xml"
        test_file.write_text("<root/>", encoding="utf-8")
        data = _parse(await handle_inspect(project, {"path": str(test_file), "target": "depgraph"}))
        assert "error" in data
        assert "config_name" in data["error"]

    @pytest.mark.asyncio
    async def test_skd_trace_missing_field_name(self, tmp_path):
        project = _make_project()
        test_file = tmp_path / "test.xml"
        test_file.write_text("<root/>", encoding="utf-8")
        data = _parse(await handle_inspect(project, {"path": str(test_file), "target": "skd", "mode": "trace"}))
        assert "error" in data
        assert "name" in data["error"]


class TestHandleDataStatus:
    @pytest.mark.asyncio
    async def test_returns_status(self):
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": True,
                "has_platform_methods": True,
                "configs": ["ut11", "edo2"],
                "autosave_available": False,
            }
            data = _parse(await handle_data_status(project, {}))
            assert data["has_platform_index"] is True
            assert len(data["configs"]) == 2

    @pytest.mark.asyncio
    async def test_with_autosave_info(self):
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": True,
                "has_platform_methods": True,
                "configs": [],
                "autosave_available": True,
                "autosave_info": {
                    "size_mb": 146.2,
                    "total_files": 60191,
                    "manifest": {"created_at": "2026-07-02T12:00:00Z"},
                },
            }
            data = _parse(await handle_data_status(project, {}))
            assert data["autosave_available"] is True
            assert data["autosave_info"]["size_mb"] == 146.2
            assert data["autoload_command"] == "1c-ai data autoload"

    @pytest.mark.asyncio
    async def test_empty_status(self):
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": False,
                "has_platform_methods": False,
                "configs": [],
                "autosave_available": False,
            }
            data = _parse(await handle_data_status(project, {}))
            assert data["has_platform_index"] is False
            assert data["configs"] == []
