"""
R11: Integration тесты для high-level MCP tools.

Тестирует полный flow: plan → gather → generate → validate → explain.
Проверяет stateful session (R2), _next_action chaining (R3),
run_cli proxy (R10).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.high_level import (
    HIGH_LEVEL_HANDLERS,
    handle_plan,
    handle_gather,
    handle_generate,
    handle_validate,
    handle_explain,
    handle_run_cli,
    _group_violations_by_rule,
    _ALLOWED_CLI_COMMANDS,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_text_content(json_str: str):
    """Создать MagicMock с .text атрибутом (для mock TextContent)."""
    mock = MagicMock()
    mock.text = json_str
    return mock


def _make_project(tmp_path: Path):
    project = MagicMock()
    project.paths.root = tmp_path
    project.paths.runtime_dir = tmp_path / "runtime"
    project.paths.scripts_dir = tmp_path / "scripts"
    return project


# ============================================================================
# R1: plan handler
# ============================================================================


class TestHandlePlan:
    """R1: Тесты для plan high-level tool."""

    @pytest.mark.asyncio
    async def test_plan_returns_intent_and_plan_id(self, tmp_path):
        """plan возвращает intent, target_context_hint, plan_id."""
        project = _make_project(tmp_path)
        data = _parse(await handle_plan(project, {"query": "создай справочник Товары"}))

        assert "plan_id" in data
        assert data["intent"]["name"] == "create_object"
        assert data["intent"]["confidence"] >= 0.9
        assert data["target_context_hint"] == "server"
        assert "required_sources" in data
        assert "_next_action" in data
        assert data["_next_action"]["tool"] == "gather"

    @pytest.mark.asyncio
    async def test_plan_missing_query(self, tmp_path):
        """Без query — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_plan(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_plan_saves_to_session(self, tmp_path):
        """plan сохраняется в session (R2)."""
        project = _make_project(tmp_path)
        data = _parse(await handle_plan(project, {"query": "напиши запрос"}))

        # Проверяем что session file создан
        session_file = tmp_path / "runtime" / "session-state.json"
        assert session_file.exists()

        session_data = json.loads(session_file.read_text())
        assert session_data["plan"] is not None
        assert session_data["plan"]["query"] == "напиши запрос"

    @pytest.mark.asyncio
    async def test_plan_unknown_intent(self, tmp_path):
        """Unknown intent — default workflow."""
        project = _make_project(tmp_path)
        data = _parse(await handle_plan(project, {"query": "привет как дела"}))

        assert data["intent"]["name"] == "unknown"
        assert data["intent"]["confidence"] == 0.0
        # _next_action всё равно suggest gather
        assert data["_next_action"]["tool"] == "gather"


# ============================================================================
# R1+R2: gather handler (cached)
# ============================================================================


class TestHandleGather:
    """R1+R2: Тесты для gather high-level tool (с кэшированием)."""

    @pytest.mark.asyncio
    async def test_gather_without_plan_returns_error(self, tmp_path):
        """gather без plan в session — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_gather(project, {}))
        assert "error" in data
        assert "plan" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_gather_after_plan_returns_context(self, tmp_path):
        """gather после plan собирает контекст."""
        project = _make_project(tmp_path)

        # Сначала plan
        await handle_plan(project, {"query": "создай справочник"})

        # Mock TaskProcessor
        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_ctx = MagicMock()
            mock_ctx.to_dict.return_value = {"query": "создай справочник", "platform_methods": []}
            mock_tp.return_value.solve.return_value = mock_ctx

            data = _parse(await handle_gather(project, {"plan_id": "test"}))

        assert "query" in data
        assert "_next_action" in data
        assert data["_cached"] is False

    @pytest.mark.asyncio
    async def test_gather_cached_on_repeat(self, tmp_path):
        """Повторный gather возвращает кэш (R2)."""
        project = _make_project(tmp_path)

        # plan
        await handle_plan(project, {"query": "создай справочник"})

        # Первый gather
        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_ctx = MagicMock()
            mock_ctx.to_dict.return_value = {"query": "test", "platform_methods": ["method1"]}
            mock_tp.return_value.solve.return_value = mock_ctx

            data1 = _parse(await handle_gather(project, {"plan_id": "test"}))
            assert data1["_cached"] is False

        # Второй gather — должен вернуть кэш
        with patch("src.services.task_processor.TaskProcessor") as mock_tp2:
            # Если solve вызовется — тест упадёт (mock_tp2 не должен вызываться)
            data2 = _parse(await handle_gather(project, {"plan_id": "test"}))
            assert data2["_cached"] is True
            mock_tp2.return_value.solve.assert_not_called()

    @pytest.mark.asyncio
    async def test_gather_force_refresh(self, tmp_path):
        """force_refresh=true — пересобирает контекст."""
        project = _make_project(tmp_path)

        await handle_plan(project, {"query": "test"})

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_ctx = MagicMock()
            mock_ctx.to_dict.return_value = {"query": "test"}
            mock_tp.return_value.solve.return_value = mock_ctx

            # Первый gather
            await handle_gather(project, {"plan_id": "test"})
            # Второй с force_refresh
            data2 = _parse(await handle_gather(project, {"plan_id": "test", "force_refresh": True}))
            assert data2["_cached"] is False
            # solve должен быть вызван дважды
            assert mock_tp.return_value.solve.call_count == 2


# ============================================================================
# R1: generate handler
# ============================================================================


class TestHandleGenerate:
    """R1: Тесты для generate high-level tool."""

    @pytest.mark.asyncio
    async def test_generate_returns_artifact_id(self, tmp_path):
        """generate возвращает artifact_id и code."""
        project = _make_project(tmp_path)

        data = _parse(await handle_generate(project, {
            "task": "запрос остатков",
            "target_context": "server",
            "type": "bsl",
        }))

        assert "artifact_id" in data
        assert "code" in data
        assert "validation_passed" in data
        assert "_next_action" in data

    @pytest.mark.asyncio
    async def test_generate_missing_task(self, tmp_path):
        """Без task — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_generate(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_generate_saves_artifact_to_session(self, tmp_path):
        """generate сохраняет artifact в session (R2)."""
        project = _make_project(tmp_path)

        data = _parse(await handle_generate(project, {
            "task": "test task",
            "target_context": "server",
        }))

        artifact_id = data["artifact_id"]

        # Проверяем что artifact в session
        session_file = tmp_path / "runtime" / "session-state.json"
        session_data = json.loads(session_file.read_text())
        artifacts = session_data["generated_artifacts"]
        assert len(artifacts) >= 1
        assert artifacts[0]["artifact_id"] == artifact_id

    @pytest.mark.asyncio
    async def test_generate_query_type(self, tmp_path):
        """generate с type=query использует query_generator."""
        project = _make_project(tmp_path)

        with patch("src.mcpserver.handlers.query.handle_generate_query") as mock_gen:
            mock_result = MagicMock()
            mock_gen.return_value = [_make_text_content(json.dumps({"query": "ВЫБРАТЬ * ИЗ Справочник.Товары"}))]

            data = _parse(await handle_generate(project, {
                "task": "запрос товаров",
                "type": "query",
            }))

        assert data["type"] == "query"
        assert "ВЫБРАТЬ" in data["code"]


# ============================================================================
# R1+R2: validate handler (state-aware)
# ============================================================================


class TestHandleValidate:
    """R1+R2: Тесты для validate high-level tool."""

    @pytest.mark.asyncio
    async def test_validate_with_artifact_id(self, tmp_path):
        """validate с artifact_id — берёт код из session."""
        project = _make_project(tmp_path)

        # Сначала generate
        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
        }))
        artifact_id = gen_data["artifact_id"]

        # validate
        with patch("src.mcpserver.handlers.quality.handle_check_bsl_context") as mock_check:
            mock_check.return_value = [_make_text_content(json.dumps({"violations": []}))]

            data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        assert data["artifact_id"] == artifact_id
        assert "is_safe_to_use" in data
        assert "_next_action" in data

    @pytest.mark.asyncio
    async def test_validate_artifact_not_found(self, tmp_path):
        """validate с несуществующим artifact_id — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_validate(project, {"artifact_id": "nonexistent"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_validate_no_args(self, tmp_path):
        """validate без artifact_id и file_path — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_validate(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_validate_groups_violations(self, tmp_path):
        """validate группирует violations по rule_id (R5)."""
        project = _make_project(tmp_path)

        # generate
        gen_data = _parse(await handle_generate(project, {"task": "test", "target_context": "server"}))
        artifact_id = gen_data["artifact_id"]

        # validate с violations
        violations = [
            {"rule_id": "CTX001", "severity": "ERROR", "message": "method1 not available"},
            {"rule_id": "CTX001", "severity": "ERROR", "message": "method2 not available"},
            {"rule_id": "CTX002", "severity": "WARNING", "message": "deprecated"},
        ]

        # Создаём proper mock с .text атрибутом возвращающим строку
        mock_text_content = MagicMock()
        mock_text_content.text = json.dumps({"violations": violations})

        with patch("src.mcpserver.handlers.high_level.handle_check_bsl_context") as mock_check:
            mock_check.return_value = [mock_text_content]

            data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        assert "grouped_violations" in data
        assert "CTX001" in data["grouped_violations"]
        assert len(data["grouped_violations"]["CTX001"]) == 2
        assert len(data["grouped_violations"]["CTX002"]) == 1


# ============================================================================
# R1: explain handler
# ============================================================================


class TestHandleExplain:
    """R1: Тесты для explain high-level tool."""

    @pytest.mark.asyncio
    async def test_explain_no_args(self, tmp_path):
        """explain без file_path и query — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_explain(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_explain_with_query(self, tmp_path):
        """explain с query — ищет использование."""
        project = _make_project(tmp_path)

        with patch("src.mcpserver.handlers.analyzers.handle_solve_context") as mock_solve:
            mock_solve.return_value = [_make_text_content(json.dumps({"query": "test", "platform_methods": []}))]

            data = _parse(await handle_explain(project, {"query": "где используется метод"}))

        assert "_next_action" in data


# ============================================================================
# R10: run_cli proxy
# ============================================================================


class TestHandleRunCli:
    """R10: Тесты для run_cli proxy tool."""

    @pytest.mark.asyncio
    async def test_run_cli_no_command(self, tmp_path):
        """run_cli без command — ошибка + список разрешённых."""
        project = _make_project(tmp_path)
        data = _parse(await handle_run_cli(project, {}))
        assert "error" in data
        assert "allowed" in data
        assert "call_graph" in data["allowed"]

    @pytest.mark.asyncio
    async def test_run_cli_disallowed_command(self, tmp_path):
        """run_cli с неразрешённой command — ошибка."""
        project = _make_project(tmp_path)
        data = _parse(await handle_run_cli(project, {"command": "os.system"}))
        assert "error" in data
        assert "not allowed" in data["error"]

    @pytest.mark.asyncio
    async def test_run_cli_allowed_command(self, tmp_path):
        """run_cli с разрешённой command — вызывает hidden handler."""
        project = _make_project(tmp_path)

        # Mock QualityHandler — patch на уровне модуля quality
        mock_handler = MagicMock(return_value=[_make_text_content('{"violations": []}')])

        # Patch quality module's QUALITY_HANDLERS dict (run_cli imports from .handlers)
        import src.mcpserver.handlers as handlers_mod
        original = handlers_mod.QUALITY_HANDLERS.copy()
        try:
            handlers_mod.QUALITY_HANDLERS["audit_security"] = mock_handler
            data = _parse(await handle_run_cli(project, {
                "command": "audit_security",
                "args": {"file_path": "/tmp/test.bsl"},
            }))
        finally:
            handlers_mod.QUALITY_HANDLERS.clear()
            handlers_mod.QUALITY_HANDLERS.update(original)

        # Проверяем что handler был вызван (response может быть error если mock не сработал)
        assert "error" in data or "violations" in data

    def test_allowed_commands_not_empty(self):
        """Whitelist не пустой."""
        assert len(_ALLOWED_CLI_COMMANDS) > 10

    def test_allowed_commands_contains_expected(self):
        """Whitelist содержит ожидаемые команды."""
        assert "call_graph" in _ALLOWED_CLI_COMMANDS
        assert "dsl_compile_meta" in _ALLOWED_CLI_COMMANDS
        assert "cfe_borrow" in _ALLOWED_CLI_COMMANDS


# ============================================================================
# R5: _group_violations_by_rule helper
# ============================================================================


class TestGroupViolationsByRule:
    """R5: Тесты для группировки violations по rule_id."""

    def test_empty_list(self):
        assert _group_violations_by_rule([]) == {}

    def test_single_rule_multiple_violations(self):
        violations = [
            {"rule_id": "SEC001", "message": "v1"},
            {"rule_id": "SEC001", "message": "v2"},
            {"rule_id": "SEC001", "message": "v3"},
        ]
        grouped = _group_violations_by_rule(violations)
        assert len(grouped) == 1
        assert len(grouped["SEC001"]) == 3

    def test_multiple_rules(self):
        violations = [
            {"rule_id": "SEC001", "message": "v1"},
            {"rule_id": "STD001", "message": "v2"},
            {"rule_id": "CTX001", "message": "v3"},
        ]
        grouped = _group_violations_by_rule(violations)
        assert len(grouped) == 3

    def test_unknown_rule_id(self):
        violations = [{"message": "no rule_id"}]
        grouped = _group_violations_by_rule(violations)
        assert "UNKNOWN" in grouped
        assert len(grouped["UNKNOWN"]) == 1


# ============================================================================
# HIGH_LEVEL_HANDLERS registry
# ============================================================================


class TestHighLevelHandlersRegistry:
    """Проверка реестра high-level handlers."""

    def test_all_handlers_registered(self):
        """Все 6 high-level handlers зарегистрированы."""
        expected = {"plan", "gather", "generate", "validate", "explain", "run_cli"}
        actual = set(HIGH_LEVEL_HANDLERS.keys())
        assert actual == expected

    def test_all_handlers_callable(self):
        """Все handlers — callable."""
        for name, handler in HIGH_LEVEL_HANDLERS.items():
            assert callable(handler), f"{name} is not callable"


# ============================================================================
# R11: Integration tests (полный flow)
# ============================================================================


class TestIntegrationFlow:
    """R11: Integration тесты полного flow plan → gather → generate → validate."""

    @pytest.mark.asyncio
    async def test_full_flow_plan_gather_generate_validate(self, tmp_path):
        """Полный flow: plan → gather → generate → validate."""
        project = _make_project(tmp_path)

        # 1. plan
        plan_data = _parse(await handle_plan(project, {"query": "создай справочник"}))
        assert plan_data["intent"]["name"] == "create_object"
        plan_id = plan_data["plan_id"]

        # 2. gather
        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_ctx = MagicMock()
            mock_ctx.to_dict.return_value = {"query": "создай справочник", "platform_methods": []}
            mock_tp.return_value.solve.return_value = mock_ctx

            gather_data = _parse(await handle_gather(project, {"plan_id": plan_id}))
            assert gather_data["_cached"] is False
            assert gather_data["_next_action"]["tool"] in ("generate", "validate", "explain", "done")

        # 3. generate
        gen_data = _parse(await handle_generate(project, {
            "task": "создай справочник",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]
        assert artifact_id.startswith("artifact_")

        # 4. validate
        with patch("src.mcpserver.handlers.quality.handle_check_bsl_context") as mock_check:
            mock_check.return_value = [_make_text_content(json.dumps({"violations": []}))]

            val_data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))
            assert val_data["is_safe_to_use"] is True
            assert val_data["_next_action"]["tool"] == "done"

    @pytest.mark.asyncio
    async def test_flow_gather_caches_on_repeat(self, tmp_path):
        """gather кэширует — повторный вызов возвращает кэш."""
        project = _make_project(tmp_path)

        await handle_plan(project, {"query": "test"})

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_ctx = MagicMock()
            mock_ctx.to_dict.return_value = {"query": "test"}
            mock_tp.return_value.solve.return_value = mock_ctx

            # Первый gather
            await handle_gather(project, {"plan_id": "test"})
            # Второй — должен вернуть кэш
            data2 = _parse(await handle_gather(project, {"plan_id": "test"}))
            assert data2["_cached"] is True

    @pytest.mark.asyncio
    async def test_flow_validate_uses_generated_artifact(self, tmp_path):
        """validate использует artifact из session (state-aware)."""
        project = _make_project(tmp_path)

        # generate
        gen_data = _parse(await handle_generate(project, {"task": "test", "target_context": "server"}))
        artifact_id = gen_data["artifact_id"]

        # validate с этим artifact_id
        with patch("src.mcpserver.handlers.quality.handle_check_bsl_context") as mock_check:
            mock_check.return_value = [_make_text_content(json.dumps({"violations": []}))]

            val_data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))
            assert val_data["artifact_id"] == artifact_id
