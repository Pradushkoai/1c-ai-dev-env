"""
Тесты для src/mcpserver/handlers/dsl_cfe.py — DSL, CFE, SKD, depgraph handlers.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.dsl_cfe import (
    handle_build_dependency_graph,
    handle_cfe_borrow,
    handle_cfe_diff,
    handle_cfe_patch_method,
    handle_dependency_query,
    handle_dsl_compile_form,
    handle_dsl_compile_meta,
    handle_dsl_compile_mxl,
    handle_dsl_compile_role,
    handle_dsl_compile_skd,
    handle_skd_trace,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = Path(__file__).parent.parent
    project.paths.scripts_dir = Path("/scripts")
    return project


# ─── DSL compilers ───


class TestDslCompileMeta:
    @pytest.mark.asyncio
    async def test_missing_output_dir(self):
        project = _make_project()
        data = _parse(await handle_dsl_compile_meta(project, {"definition": {}}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.dsl.DslCompiler"):
            data = _parse(await handle_dsl_compile_meta(project, {"definition": {}, "output_dir": "/tmp/out"}))
            # Will fail because DslCompiler is mocked but not configured
            assert "error" in data or "object_type" in data


class TestDslCompileForm:
    @pytest.mark.asyncio
    async def test_missing_output_path(self):
        project = _make_project()
        data = _parse(await handle_dsl_compile_form(project, {"definition": {}}))
        assert "error" in data


class TestDslCompileSkd:
    @pytest.mark.asyncio
    async def test_missing_output_path(self):
        project = _make_project()
        data = _parse(await handle_dsl_compile_skd(project, {"definition": {}}))
        assert "error" in data


class TestDslCompileMxl:
    @pytest.mark.asyncio
    async def test_missing_output_path(self):
        project = _make_project()
        data = _parse(await handle_dsl_compile_mxl(project, {"definition": {}}))
        assert "error" in data


class TestDslCompileRole:
    @pytest.mark.asyncio
    async def test_missing_output_dir(self):
        project = _make_project()
        data = _parse(await handle_dsl_compile_role(project, {"definition": {}}))
        assert "error" in data


# ─── CFE ───


class TestCfeBorrow:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        project = _make_project()
        data = _parse(await handle_cfe_borrow(project, {"extension_path": "/ext"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_all_missing(self):
        project = _make_project()
        data = _parse(await handle_cfe_borrow(project, {}))
        assert "error" in data


class TestCfePatchMethod:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        project = _make_project()
        data = _parse(await handle_cfe_patch_method(project, {"extension_path": "/ext"}))
        assert "error" in data


class TestCfeDiff:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        project = _make_project()
        data = _parse(await handle_cfe_diff(project, {"extension_path": "/ext"}))
        assert "error" in data


# ─── SKD trace ───


class TestSkdTrace:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        project = _make_project()
        data = _parse(await handle_skd_trace(project, {"template_path": "/tmp/t.xml"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_all_missing(self):
        project = _make_project()
        data = _parse(await handle_skd_trace(project, {}))
        assert "error" in data


# ─── Dependency graph ───


class TestBuildDependencyGraph:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_build_dependency_graph(project, {}))
        assert "error" in data


class TestDependencyQuery:
    @pytest.mark.asyncio
    async def test_missing_params(self):
        project = _make_project()
        data = _parse(await handle_dependency_query(project, {"config_name": "ut11"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_all_missing(self):
        project = _make_project()
        data = _parse(await handle_dependency_query(project, {}))
        assert "error" in data
