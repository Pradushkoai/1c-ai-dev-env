"""
Тесты для src/mcpserver/handlers/generate.py — генерация кода и EPF.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.generate import (
    handle_build_epf,
    handle_epf_factory_create,
    handle_epf_factory_templates,
    handle_generate_processing,
    handle_validate_generated,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = MagicMock()
    project.paths.root.__truediv__ = MagicMock(return_value=MagicMock())
    return project


class TestHandleGenerateProcessing:
    @pytest.mark.asyncio
    async def test_missing_name(self):
        project = _make_project()
        data = _parse(await handle_generate_processing(project, {"synonym": "test"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_missing_synonym(self):
        project = _make_project()
        data = _parse(await handle_generate_processing(project, {"name": "test"}))
        assert "error" in data


class TestHandleBuildEpf:
    @pytest.mark.asyncio
    async def test_missing_source_dir(self):
        project = _make_project()
        data = _parse(await handle_build_epf(project, {"output_path": "/tmp/out.epf"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_missing_output_path(self):
        project = _make_project()
        data = _parse(await handle_build_epf(project, {"source_dir": "/tmp/src"}))
        assert "error" in data


class TestHandleValidateGenerated:
    @pytest.mark.asyncio
    async def test_missing_source_dir(self):
        project = _make_project()
        data = _parse(await handle_validate_generated(project, {}))
        assert "error" in data


class TestHandleEpfFactoryCreate:
    @pytest.mark.asyncio
    async def test_missing_name(self):
        project = _make_project()
        data = _parse(await handle_epf_factory_create(project, {"output_path": "/tmp/out.epf"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_missing_output_path(self):
        project = _make_project()
        data = _parse(await handle_epf_factory_create(project, {"name": "Test"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_successful_create(self, tmp_path):
        project = _make_project()
        with patch("src.services.epf_factory.EpfFactory") as mock_factory_class:
            factory = mock_factory_class.return_value
            result = MagicMock()
            result.ok = True
            result.error = ""
            result.epf_path = tmp_path / "Test.epf"
            result.size_bytes = 1024
            result.name = "Test"
            result.synonym = "Test"
            result.proc_uuid = "abc"
            result.form_uuid = "def"
            result.bsl_lines = 10
            result.bsl_warnings = 0
            result.bsl_errors = 0
            result.round_trip_ok = True
            result.work_dir = None
            factory.create_epf.return_value = result

            data = _parse(
                await handle_epf_factory_create(
                    project,
                    {"name": "Test", "output_path": str(tmp_path / "Test.epf"), "bsl_code": "// code"},
                )
            )
            assert data["ok"] is True
            assert data["name"] == "Test"

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.epf_factory.EpfFactory") as mock_factory_class:
            mock_factory_class.side_effect = RuntimeError("fail")
            data = _parse(await handle_epf_factory_create(project, {"name": "Test", "output_path": "/tmp/out.epf"}))
            assert "error" in data


class TestHandleEpfFactoryTemplates:
    @pytest.mark.asyncio
    async def test_returns_templates(self):
        project = _make_project()
        with patch("src.services.epf_factory.EpfFactory") as mock_factory_class:
            mock_factory_class.list_templates.return_value = {
                "ext_proc": "/path/to/ext_proc.json",
                "form": "/path/to/form.json",
            }
            data = _parse(await handle_epf_factory_templates(project, {}))
            assert "ext_proc" in data

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.epf_factory.EpfFactory") as mock_factory_class:
            mock_factory_class.list_templates.side_effect = RuntimeError("fail")
            data = _parse(await handle_epf_factory_templates(project, {}))
            assert "error" in data
