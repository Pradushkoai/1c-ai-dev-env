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


# ============================================================================
# F2.7: data_status actionable _missing_prerequisites
# ============================================================================


class TestHandleDataStatusActionable:
    """F2.7: Тесты для actionable _missing_prerequisites в data_status."""

    @pytest.mark.asyncio
    async def test_missing_prerequisites_when_no_platform_index(self):
        """Если нет platform_index — _missing_prerequisites содержит component."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": False,
                "has_platform_methods": False,
                "has_platform_methods_db": False,
                "configs": [],
                "autosave_available": False,
            }
            data = _parse(await handle_data_status(project, {}))

            assert "_missing_prerequisites" in data
            assert len(data["_missing_prerequisites"]) == 4  # all missing

            # Check platform_index component
            platform_idx = next(
                (m for m in data["_missing_prerequisites"] if m["component"] == "platform_index"),
                None,
            )
            assert platform_idx is not None
            assert "fix_command" in platform_idx
            assert "impact" in platform_idx
            assert "1c-ai platform build-index" in platform_idx["fix_command"]

    @pytest.mark.asyncio
    async def test_missing_prerequisites_when_no_platform_methods_db(self):
        """Если нет platform_methods_db — _missing_prerequisites содержит component."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": True,
                "has_platform_methods": True,
                "has_platform_methods_db": False,
                "configs": ["ut11"],
                "autosave_available": True,
            }
            data = _parse(await handle_data_status(project, {}))

            assert "_missing_prerequisites" in data
            # Only platform_methods_db is missing
            assert len(data["_missing_prerequisites"]) == 1
            assert data["_missing_prerequisites"][0]["component"] == "platform_methods_db"
            assert "build_platform_methods_index" in data["_missing_prerequisites"][0]["fix_command"]

    @pytest.mark.asyncio
    async def test_missing_prerequisites_when_no_configs(self):
        """Если нет configs — _missing_prerequisites содержит configurations."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": True,
                "has_platform_methods": True,
                "has_platform_methods_db": True,
                "configs": [],
                "autosave_available": True,
            }
            data = _parse(await handle_data_status(project, {}))

            configs_missing = next(
                (m for m in data["_missing_prerequisites"] if m["component"] == "configurations"),
                None,
            )
            assert configs_missing is not None
            assert "1c-ai config add" in configs_missing["fix_command"]

    @pytest.mark.asyncio
    async def test_no_missing_prerequisites_when_all_ready(self):
        """Если всё готово — _missing_prerequisites пустой, _action_hint ✅."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": True,
                "has_platform_methods": True,
                "has_platform_methods_db": True,
                "configs": ["ut11"],
                "autosave_available": True,
            }
            data = _parse(await handle_data_status(project, {}))

            assert data["_missing_prerequisites"] == []
            assert "✅" in data["_action_hint"]

    @pytest.mark.asyncio
    async def test_action_hint_mentions_count(self):
        """_action_hint упоминает количество missing components."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": False,
                "has_platform_methods": False,
                "has_platform_methods_db": False,
                "configs": [],
                "autosave_available": False,
            }
            data = _parse(await handle_data_status(project, {}))

            assert "4 component(s)" in data["_action_hint"]
            assert "fix_command" in data["_action_hint"]

    @pytest.mark.asyncio
    async def test_each_missing_has_required_fields(self):
        """Каждый missing prerequisite имеет все обязательные поля."""
        project = _make_project()
        with patch("src.services.data_package.DataPackage") as mock_dp_class:
            dp = mock_dp_class.return_value
            dp.status.return_value = {
                "has_platform_index": False,
                "has_platform_methods": False,
                "has_platform_methods_db": False,
                "configs": [],
                "autosave_available": False,
            }
            data = _parse(await handle_data_status(project, {}))

            for m in data["_missing_prerequisites"]:
                assert "component" in m
                assert "issue" in m
                assert "impact" in m
                assert "fix_command" in m
                assert "fix_description" in m
