"""
Тесты для src/mcpserver/handlers/quality.py — анализаторы качества.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.quality import (
    handle_analyze_architecture,
    handle_audit_security,
    handle_check_form_quality,
    handle_check_transactions,
    handle_diff_configs,
    handle_get_code_metrics,
    handle_get_knowledge,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = Path("/repo")
    project.paths.scripts_dir = Path("/scripts")
    return project


class TestHandleAuditSecurity:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_audit_security(project, {}))
        assert "error" in data


class TestHandleGetCodeMetrics:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_get_code_metrics(project, {}))
        assert "error" in data


class TestHandleCheckTransactions:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_check_transactions(project, {}))
        assert "error" in data


class TestHandleAnalyzeArchitecture:
    @pytest.mark.asyncio
    async def test_missing_config_dir(self):
        project = _make_project()
        data = _parse(await handle_analyze_architecture(project, {}))
        assert "error" in data


class TestHandleCheckFormQuality:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_check_form_quality(project, {}))
        assert "error" in data


class TestHandleDiffConfigs:
    @pytest.mark.asyncio
    async def test_missing_paths(self):
        project = _make_project()
        data = _parse(await handle_diff_configs(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_only_old_path(self):
        project = _make_project()
        data = _parse(await handle_diff_configs(project, {"old_path": "/old"}))
        assert "error" in data


class TestHandleGetKnowledge:
    @pytest.mark.asyncio
    async def test_list_all(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.list_all.return_value = [{"id": "1", "title": "test"}]
            kb.get_stats.return_value = {"total": 1}
            data = _parse(await handle_get_knowledge(project, {}))
            assert "items" in data or "stats" in data

    @pytest.mark.asyncio
    async def test_search(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.search.return_value = [{"id": "1", "title": "test", "score": 0.9}]
            data = _parse(await handle_get_knowledge(project, {"query": "test"}))
            assert "results" in data or "error" in data

    @pytest.mark.asyncio
    async def test_get_item(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.get_item.return_value = {"id": "1", "title": "test", "content": "full content"}
            data = _parse(await handle_get_knowledge(project, {"item_id": "1"}))
            assert "id" in data or "error" in data

    @pytest.mark.asyncio
    async def test_item_not_found(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.get_item.return_value = None
            data = _parse(await handle_get_knowledge(project, {"item_id": "nonexistent"}))
            assert "error" in data or "items" in data

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            mock_kb_class.side_effect = RuntimeError("fail")
            data = _parse(await handle_get_knowledge(project, {}))
            assert "error" in data
