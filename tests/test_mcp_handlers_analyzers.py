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
            # F2.6: solve теперь вызывается с required_sources (из intent classifier)
            # Для unknown intent — default required_sources
            call_args = mock_tp.solve.call_args
            assert call_args.args == ("test",) or call_args.args[0] == "test"
            assert call_args.kwargs.get("config_name") == ""
            assert call_args.kwargs.get("limit") == 5
            # required_sources должен быть передан (даже для unknown intent)
            assert "required_sources" in call_args.kwargs
            assert isinstance(call_args.kwargs["required_sources"], list)

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
            # F2.4: настраиваем атрибуты для приоритизации
            result.is_safe_to_use = True
            result.total_warnings = 0
            result.must_fix_before_use_count = 0
            result.top_3_priority = []
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
            # F2.4: настраиваем атрибуты для приоритизации
            result.is_safe_to_use = True
            result.total_warnings = 1
            result.must_fix_before_use_count = 0
            result.top_3_priority = []
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
            # F2.4: настраиваем атрибуты для приоритизации
            result.is_safe_to_use = True
            result.total_warnings = 0
            result.must_fix_before_use_count = 0
            result.top_3_priority = []
            mock_tp.check.return_value = result

            await handle_solve_check(project, {"file_path": "/tmp/test.bsl"})
            mock_tp.check.assert_called_once_with(Path("/tmp/test.bsl"), level="standard")


# ============================================================================
# F2.4: Prioritization in solve_check — must_fix_before_use, top_3_priority
# ============================================================================


class TestCheckResultPrioritization:
    """F2.4: Тесты для приоритизации violations в CheckResult."""

    def test_must_fix_before_use_filters_critical(self):
        """must_fix_before_use возвращает только CRITICAL/HIGH/ERROR."""
        from src.models.task import CheckResult, Violation

        result = CheckResult(file="test.bsl", level="standard")
        result.violations = [
            Violation(source="security", rule_id="SEC001", severity="CRITICAL", line=10, message="SQL injection"),
            Violation(source="standards", rule_id="STD001", severity="WARNING", line=20, message="Style issue"),
            Violation(source="security", rule_id="SEC002", severity="HIGH", line=30, message="Hardcoded password"),
            Violation(source="bsl_ls", rule_id="BSL001", severity="INFO", line=40, message="Typo"),
        ]

        must_fix = result.must_fix_before_use
        assert len(must_fix) == 2
        assert all(v.severity.lower() in ("critical", "error", "high") for v in must_fix)
        assert result.must_fix_before_use_count == 2
        assert result.is_safe_to_use is False

    def test_is_safe_to_use_when_no_critical(self):
        """is_safe_to_use=True когда нет CRITICAL/HIGH."""
        from src.models.task import CheckResult, Violation

        result = CheckResult(file="test.bsl", level="standard")
        result.violations = [
            Violation(source="standards", rule_id="STD001", severity="WARNING", line=20, message="Style"),
            Violation(source="bsl_ls", rule_id="BSL001", severity="INFO", line=40, message="Typo"),
        ]

        assert result.must_fix_before_use_count == 0
        assert result.is_safe_to_use is True

    def test_is_safe_to_use_when_no_violations(self):
        """is_safe_to_use=True когда нет violations вообще."""
        from src.models.task import CheckResult

        result = CheckResult(file="test.bsl", level="standard")
        assert result.is_safe_to_use is True
        assert result.must_fix_before_use_count == 0

    def test_top_3_priority_sorted_by_severity(self):
        """top_3_priority возвращает 3 самых критичных violation."""
        from src.models.task import CheckResult, Violation

        result = CheckResult(file="test.bsl", level="standard")
        result.violations = [
            Violation(source="std", rule_id="STD001", severity="INFO", line=10, message="info"),
            Violation(source="sec", rule_id="SEC001", severity="CRITICAL", line=20, message="critical"),
            Violation(source="std", rule_id="STD002", severity="WARNING", line=30, message="warning"),
            Violation(source="sec", rule_id="SEC002", severity="HIGH", line=40, message="high"),
            Violation(source="std", rule_id="STD003", severity="ERROR", line=50, message="error"),
        ]

        top3 = result.top_3_priority
        assert len(top3) == 3
        # CRITICAL (rank 5) должен быть первым
        assert top3[0].severity == "CRITICAL"
        # Потом ERROR или HIGH (rank 4)
        assert top3[1].severity in ("ERROR", "HIGH")
        assert top3[2].severity in ("ERROR", "HIGH")

    def test_top_3_priority_empty(self):
        """top_3_priority пуст когда нет violations."""
        from src.models.task import CheckResult

        result = CheckResult(file="test.bsl", level="standard")
        assert result.top_3_priority == []

    def test_to_dict_includes_prioritization(self):
        """to_dict() включает summary, must_fix_before_use, top_3_priority."""
        from src.models.task import CheckResult, Violation

        result = CheckResult(file="test.bsl", level="standard")
        result.violations = [
            Violation(source="sec", rule_id="SEC001", severity="CRITICAL", line=10, message="SQL injection"),
            Violation(source="std", rule_id="STD001", severity="WARNING", line=20, message="Style"),
        ]

        d = result.to_dict()
        assert "summary" in d
        assert d["summary"]["must_fix_before_use_count"] == 1
        assert d["summary"]["is_safe_to_use"] is False
        assert d["summary"]["verdict"] == "errors"
        assert d["summary"]["total_violations"] == 2

        assert "must_fix_before_use" in d
        assert len(d["must_fix_before_use"]) == 1
        assert d["must_fix_before_use"][0]["rule_id"] == "SEC001"

        assert "top_3_priority" in d
        assert len(d["top_3_priority"]) == 2  # только 2 violations

        assert "violations" in d
        assert len(d["violations"]) == 2

    def test_violation_has_recommendation_field(self):
        """Violation имеет recommendation поле (F2.4)."""
        from src.models.task import Violation

        v = Violation(
            source="sec",
            rule_id="SEC001",
            severity="CRITICAL",
            line=10,
            message="SQL injection",
            recommendation="Используйте параметризованный запрос: Запрос.УстановитьПараметр()",
        )
        assert v.recommendation == "Используйте параметризованный запрос: Запрос.УстановитьПараметр()"

    def test_violation_recommendation_defaults_empty(self):
        """Violation.recommendation по умолчанию пустая строка."""
        from src.models.task import Violation

        v = Violation(source="sec", rule_id="SEC001", severity="CRITICAL", line=10, message="test")
        assert v.recommendation == ""


class TestHandleSolveCheckNextSteps:
    """F2.4: Тесты для _next_steps в handle_solve_check."""

    @pytest.mark.asyncio
    async def test_next_steps_safe_code(self):
        """Когда код безопасен — _next_steps содержит ✅."""
        from src.mcpserver.handlers.analyzers import handle_solve_check
        from src.services.task_processor import TaskProcessor
        from src.models.task import CheckResult, Violation

        project = MagicMock()
        project.paths = MagicMock()

        # Mock TaskProcessor.check чтобы вернуть безопасный result
        safe_result = CheckResult(file="test.bsl", level="standard")
        safe_result.violations = [
            Violation(source="std", rule_id="STD001", severity="WARNING", line=10, message="Style"),
        ]
        safe_result.analyzers_run = ["check_1c_standards"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            mock_tp.check.return_value = safe_result
            data = _parse(await handle_solve_check(project, {"file_path": "/tmp/test.bsl"}))

        assert "_next_steps" in data
        assert any("✅" in s for s in data["_next_steps"])
        assert data["summary"]["is_safe_to_use"] is True

    @pytest.mark.asyncio
    async def test_next_steps_unsafe_code(self):
        """Когда есть CRITICAL — _next_steps содержит ❌ и top-3."""
        from src.mcpserver.handlers.analyzers import handle_solve_check
        from src.services.task_processor import TaskProcessor
        from src.models.task import CheckResult, Violation

        project = MagicMock()
        project.paths = MagicMock()

        unsafe_result = CheckResult(file="test.bsl", level="standard")
        unsafe_result.violations = [
            Violation(source="sec", rule_id="SEC001", severity="CRITICAL", line=10, message="SQL injection"),
            Violation(source="sec", rule_id="SEC002", severity="HIGH", line=20, message="Hardcoded password"),
        ]
        unsafe_result.analyzers_run = ["security_auditor"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            mock_tp.check.return_value = unsafe_result
            data = _parse(await handle_solve_check(project, {"file_path": "/tmp/test.bsl"}))

        assert "_next_steps" in data
        assert any("❌" in s for s in data["_next_steps"])
        assert any("SEC001" in s for s in data["_next_steps"])
        assert any("SEC002" in s for s in data["_next_steps"])
        assert data["summary"]["is_safe_to_use"] is False
        assert data["summary"]["must_fix_before_use_count"] == 2
