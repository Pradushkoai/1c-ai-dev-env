"""
CR-4 + CR-5: Тесты для explain full analysis и session cleanup.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.high_level import handle_explain
from src.services.session import SessionManager, SessionState


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project(tmp_path: Path):
    project = MagicMock()
    project.paths.root = tmp_path
    project.paths.runtime_dir = tmp_path / "runtime"
    project.paths.scripts_dir = tmp_path / "scripts"
    return project


class TestExplainFull:
    """CR-4: Тесты для полного explain с 3 источниками."""

    @pytest.mark.asyncio
    async def test_explain_returns_analysis_sources(self, tmp_path):
        """CR-4: explain возвращает analysis_sources список."""
        project = _make_project(tmp_path)

        mock_metrics = MagicMock()
        mock_metrics.text = json.dumps({"total_lines": 100, "is_god_object": False})

        # handle_get_code_metrics импортируется внутри функции из .quality
        with patch("src.mcpserver.handlers.quality.handle_get_code_metrics") as mock_m:
            mock_m.return_value = [mock_metrics]
            data = _parse(await handle_explain(project, {"file_path": "/tmp/test.bsl"}))

        assert "analysis_sources" in data
        assert "code_metrics" in data["analysis_sources"]

    @pytest.mark.asyncio
    async def test_explain_adaptive_next_action_with_issues(self, tmp_path):
        """CR-4: _next_action=validate если есть issues."""
        project = _make_project(tmp_path)

        mock_metrics = MagicMock()
        mock_metrics.text = json.dumps({"total_lines": 500, "is_god_object": True})

        with patch("src.mcpserver.handlers.quality.handle_get_code_metrics") as mock_m:
            mock_m.return_value = [mock_metrics]
            data = _parse(await handle_explain(project, {"file_path": "/tmp/test.bsl"}))

        assert data["_next_action"]["tool"] == "validate"

    @pytest.mark.asyncio
    async def test_explain_adaptive_next_action_no_issues(self, tmp_path):
        """CR-4: _next_action=done если нет issues."""
        project = _make_project(tmp_path)

        mock_metrics = MagicMock()
        mock_metrics.text = json.dumps({"total_lines": 50, "is_god_object": False})

        with patch("src.mcpserver.handlers.quality.handle_get_code_metrics") as mock_m:
            mock_m.return_value = [mock_metrics]
            data = _parse(await handle_explain(project, {"file_path": "/tmp/test.bsl"}))

        assert data["_next_action"]["tool"] == "done"


class TestSessionCleanup:
    """CR-5: Тесты для session cleanup и TTL."""

    def test_cleanup_removes_expired_artifacts(self, tmp_path):
        """CR-5: Удаляет artifacts старше TTL."""
        manager = SessionManager(tmp_path)
        session = SessionState()
        session.generated_artifacts = [
            {"artifact_id": "old", "created_at": time.time() - 7200, "code": "old"},
            {"artifact_id": "new", "created_at": time.time() - 60, "code": "new"},
        ]

        manager._cleanup_expired(session)

        assert len(session.generated_artifacts) == 1
        assert session.generated_artifacts[0]["artifact_id"] == "new"

    def test_cleanup_trims_to_max_artifacts(self, tmp_path):
        """CR-5: Обрезает до MAX_ARTIFACTS."""
        manager = SessionManager(tmp_path)
        session = SessionState()
        session.generated_artifacts = [
            {"artifact_id": f"art_{i}", "created_at": time.time() - i, "code": f"code_{i}"}
            for i in range(25)
        ]

        manager._cleanup_expired(session)

        assert len(session.generated_artifacts) <= manager.MAX_ARTIFACTS

    def test_cleanup_trims_validation_history(self, tmp_path):
        """CR-5: Обрезает validation_history."""
        manager = SessionManager(tmp_path)
        session = SessionState()
        session.validation_history = [
            {"artifact_id": f"val_{i}", "validated_at": time.time() - i}
            for i in range(25)
        ]

        manager._cleanup_expired(session)

        assert len(session.validation_history) <= manager.MAX_VALIDATIONS

    def test_save_triggers_cleanup(self, tmp_path):
        """CR-5: save() вызывает cleanup."""
        manager = SessionManager(tmp_path)
        session = manager.get_session()

        for i in range(25):
            session.generated_artifacts.append({
                "artifact_id": f"art_{i}",
                "created_at": time.time() - i,
                "code": f"code_{i}",
            })

        manager.save()

        manager2 = SessionManager(tmp_path)
        session2 = manager2.get_session()

        assert len(session2.generated_artifacts) <= manager.MAX_ARTIFACTS
