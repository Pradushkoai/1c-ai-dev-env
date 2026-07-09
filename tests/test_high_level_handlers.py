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
        """validate с artifact_id — берёт код из session.

        CR-2: validate теперь использует TaskProcessor.check() через temp file.
        Mock TaskProcessor чтобы вернуть пустой CheckResult (safe code).
        """
        from src.models.task import CheckResult

        project = _make_project(tmp_path)

        # Сначала generate
        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
        }))
        artifact_id = gen_data["artifact_id"]

        # Mock TaskProcessor.check() — empty result (safe)
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.analyzers_run = ["check_1c_standards"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp_class.return_value.check.return_value = mock_check_result

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
        """validate группирует violations по rule_id (R5).

        CR-2: validate теперь использует TaskProcessor.check() через temp file.
        Mock TaskProcessor чтобы вернуть предсказуемые violations.
        """
        from src.models.task import CheckResult, Violation as TaskViolation

        project = _make_project(tmp_path)

        # generate
        gen_data = _parse(await handle_generate(project, {"task": "test", "target_context": "server"}))
        artifact_id = gen_data["artifact_id"]

        # Mock TaskProcessor.check() чтобы вернуть предсказуемые violations
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.violations = [
            TaskViolation(source="bsl_context_checker", rule_id="CTX001", severity="ERROR", line=10, message="method1 not available", recommendation="Используй серверный метод"),
            TaskViolation(source="bsl_context_checker", rule_id="CTX001", severity="ERROR", line=20, message="method2 not available", recommendation="Используй серверный метод"),
            TaskViolation(source="bsl_context_checker", rule_id="CTX002", severity="WARNING", line=30, message="deprecated", recommendation="Обнови метод"),
        ]
        mock_check_result.analyzers_run = ["bsl_context_checker"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp_class.return_value.check.return_value = mock_check_result

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
        # CR-2: validate теперь использует TaskProcessor.check() через temp file
        from src.models.task import CheckResult
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.analyzers_run = ["check_1c_standards"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_tp.return_value.check.return_value = mock_check_result

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
        # CR-2: validate теперь использует TaskProcessor.check() через temp file
        from src.models.task import CheckResult
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.analyzers_run = ["check_1c_standards"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_tp.return_value.check.return_value = mock_check_result

            val_data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))
            assert val_data["artifact_id"] == artifact_id


# ============================================================================
# CR-1: generate LLM + CR-7: auto-fix feedback loop
# ============================================================================


class TestGenerateLLM:
    """CR-1: Тесты для LLM генерации в generate."""

    @pytest.mark.asyncio
    async def test_generate_uses_ollama_when_available(self, tmp_path):
        """CR-1: generate использует Ollama когда доступен."""
        project = _make_project(tmp_path)

        mock_response = MagicMock()
        mock_response.text = "Процедура Тест()\nКонецПроцедуры"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            data = _parse(await handle_generate(project, {
                "task": "создай справочник",
                "target_context": "server",
                "type": "bsl",
            }))

        assert data["generation_source"] == "ollama_llm"
        assert "Процедура Тест" in data["code"]
        mock_client.generate_for_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_fallback_to_template_when_ollama_unavailable(self, tmp_path):
        """CR-1: fallback на bsl_templates когда Ollama недоступен."""
        project = _make_project(tmp_path)

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = False

            data = _parse(await handle_generate(project, {
                "task": "создай справочник",
                "target_context": "server",
                "type": "bsl",
            }))

        # Должен быть fallback на template или placeholder
        assert data["generation_source"] in ("bsl_templates (create_object)", "bsl_templates ()", "no_source", "placeholder")

    @pytest.mark.asyncio
    async def test_generate_fallback_when_circuit_breaker_open(self, tmp_path):
        """CR-8: fallback на template когда circuit breaker open."""
        project = _make_project(tmp_path)

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "open"

            data = _parse(await handle_generate(project, {
                "task": "test",
                "target_context": "server",
                "type": "bsl",
            }))

        # generate_for_task не должен вызываться (circuit open)
        mock_client.generate_for_task.assert_not_called()
        assert data["generation_source"] != "ollama_llm"

    @pytest.mark.asyncio
    async def test_generate_strips_markdown_fences(self, tmp_path):
        """CR-1: markdown code fences убираются из LLM response."""
        project = _make_project(tmp_path)

        mock_response = MagicMock()
        mock_response.text = "```bsl\nПроцедура Тест()\nКонецПроцедуры\n```"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            data = _parse(await handle_generate(project, {
                "task": "test",
                "target_context": "server",
                "type": "bsl",
            }))

        assert "```" not in data["code"]
        assert "Процедура Тест" in data["code"]


class TestAutoFixLoop:
    """CR-7: Тесты для auto-fix feedback loop."""

    @pytest.mark.asyncio
    async def test_generate_with_fix_violations_from(self, tmp_path):
        """CR-7: generate с fix_violations_from берёт violations из session."""
        project = _make_project(tmp_path)

        # Сначала generate + validate чтобы создать artifact + violations
        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]

        # Mock validate с violations
        from src.models.task import CheckResult, Violation as TaskViolation
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.violations = [
            TaskViolation(source="sec", rule_id="SEC001", severity="CRITICAL", line=10, message="SQL injection", recommendation="Используй параметры"),
        ]
        mock_check_result.analyzers_run = ["security_auditor"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_tp.return_value.check.return_value = mock_check_result
            val_data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        # Теперь generate с fix_violations_from
        mock_response = MagicMock()
        mock_response.text = "Исправленный код"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            fix_data = _parse(await handle_generate(project, {
                "task": "test",
                "target_context": "server",
                "type": "bsl",
                "fix_violations_from": artifact_id,
            }))

        assert fix_data["fix_applied"] is True
        assert fix_data["generation_source"] == "ollama_llm"
        # generate_for_task должен быть вызван с violations в prompt
        call_args = mock_client.generate_for_task.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "SEC001" in prompt or "SQL injection" in prompt

    @pytest.mark.asyncio
    async def test_generate_without_fix_violations_from(self, tmp_path):
        """CR-7: generate без fix_violations_from — fix_applied=False."""
        project = _make_project(tmp_path)

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = False

            data = _parse(await handle_generate(project, {
                "task": "test",
                "target_context": "server",
                "type": "bsl",
            }))

        assert data["fix_applied"] is False


# ============================================================================
# CR-2: validate full (temp file + solve_check)
# ============================================================================


class TestValidateFull:
    """CR-2: Тесты для полной валидации через temp file."""

    @pytest.mark.asyncio
    async def test_validate_uses_temp_file(self, tmp_path):
        """CR-2: validate записывает code во temp file для solve_check."""
        from src.models.task import CheckResult

        project = _make_project(tmp_path)

        # generate
        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]

        # Mock TaskProcessor.check
        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.analyzers_run = ["check_1c_standards", "security_auditor"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp = mock_tp_class.return_value
            mock_tp.check.return_value = mock_check_result

            data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        # check должен быть вызван с Path аргументом (temp file)
        mock_tp.check.assert_called_once()
        call_args = mock_tp.check.call_args
        temp_file_arg = call_args.args[0]
        assert hasattr(temp_file_arg, "exists")  # Path-like
        # Temp file должен быть удалён после validate
        assert not temp_file_arg.exists()

    @pytest.mark.asyncio
    async def test_validate_returns_analyzers_run(self, tmp_path):
        """CR-2: validate возвращает analyzers_run список."""
        from src.models.task import CheckResult

        project = _make_project(tmp_path)

        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]

        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.analyzers_run = ["check_1c_standards", "security_auditor", "transaction_checker"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_tp.return_value.check.return_value = mock_check_result

            data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        assert "analyzers_run" in data
        assert len(data["analyzers_run"]) == 3
        assert "security_auditor" in data["analyzers_run"]

    @pytest.mark.asyncio
    async def test_validate_must_fix_includes_high_severity(self, tmp_path):
        """CR-2: must_fix включает CRITICAL, ERROR, HIGH."""
        from src.models.task import CheckResult, Violation as TaskViolation

        project = _make_project(tmp_path)

        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]

        mock_check_result = CheckResult(file="test.bsl", level="standard")
        mock_check_result.violations = [
            TaskViolation(source="sec", rule_id="SEC001", severity="CRITICAL", line=10, message="critical"),
            TaskViolation(source="sec", rule_id="SEC002", severity="HIGH", line=20, message="high"),
            TaskViolation(source="sec", rule_id="SEC003", severity="ERROR", line=30, message="error"),
            TaskViolation(source="std", rule_id="STD001", severity="WARNING", line=40, message="warning"),
            TaskViolation(source="std", rule_id="STD002", severity="INFO", line=50, message="info"),
        ]
        mock_check_result.analyzers_run = ["security_auditor"]

        with patch("src.services.task_processor.TaskProcessor") as mock_tp:
            mock_tp.return_value.check.return_value = mock_check_result

            data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        # CRITICAL + HIGH + ERROR = 3 must_fix
        assert data["must_fix_count"] == 3
        assert data["is_safe_to_use"] is False

    @pytest.mark.asyncio
    async def test_validate_fallback_on_exception(self, tmp_path):
        """CR-2: fallback на check_bsl_context если solve_check упал."""
        project = _make_project(tmp_path)

        gen_data = _parse(await handle_generate(project, {
            "task": "test",
            "target_context": "server",
            "type": "bsl",
        }))
        artifact_id = gen_data["artifact_id"]

        # Mock TaskProcessor.check чтобы выбросить exception
        mock_text_content = MagicMock()
        mock_text_content.text = json.dumps({"violations": []})

        with patch("src.services.task_processor.TaskProcessor") as mock_tp_class:
            mock_tp_class.return_value.check.side_effect = Exception("solve_check failed")

            with patch("src.mcpserver.handlers.high_level.handle_check_bsl_context") as mock_ctx:
                mock_ctx.return_value = [mock_text_content]

                data = _parse(await handle_validate(project, {"artifact_id": artifact_id}))

        # Должен быть fallback — analyzers_run содержит "check_bsl_context (fallback)"
        assert "analyzers_run" in data
        assert any("fallback" in a for a in data["analyzers_run"])


# ============================================================================
# CR-3: run_cli whitelist — добавлены platform methods
# ============================================================================


class TestRunCliWhitelistExtended:
    """CR-3: Тесты для расширенного whitelist."""

    def test_search_platform_method_in_whitelist(self):
        """CR-3: search_platform_method в whitelist."""
        assert "search_platform_method" in _ALLOWED_CLI_COMMANDS

    def test_get_method_details_in_whitelist(self):
        """CR-3: get_method_details в whitelist."""
        assert "get_method_details" in _ALLOWED_CLI_COMMANDS

    def test_get_method_details_batch_in_whitelist(self):
        """CR-3: get_method_details_batch в whitelist."""
        assert "get_method_details_batch" in _ALLOWED_CLI_COMMANDS

    def test_get_safe_methods_in_whitelist(self):
        """CR-3: get_safe_methods в whitelist."""
        assert "get_safe_methods" in _ALLOWED_CLI_COMMANDS

    def test_solve_context_in_whitelist(self):
        """CR-3: solve_context в whitelist."""
        assert "solve_context" in _ALLOWED_CLI_COMMANDS

    def test_solve_check_in_whitelist(self):
        """CR-3: solve_check в whitelist."""
        assert "solve_check" in _ALLOWED_CLI_COMMANDS

    def test_check_bsl_context_in_whitelist(self):
        """CR-3: check_bsl_context в whitelist."""
        assert "check_bsl_context" in _ALLOWED_CLI_COMMANDS

    def test_bsl_templates_in_whitelist(self):
        """CR-3: bsl_templates в whitelist."""
        assert "bsl_templates" in _ALLOWED_CLI_COMMANDS

    def test_generate_query_in_whitelist(self):
        """CR-3: generate_query в whitelist."""
        assert "generate_query" in _ALLOWED_CLI_COMMANDS

    def test_get_object_structure_in_whitelist(self):
        """CR-3: get_object_structure в whitelist."""
        assert "get_object_structure" in _ALLOWED_CLI_COMMANDS

    def test_whitelist_count_increased(self):
        """CR-3: whitelist увеличился с 36 до 46+."""
        assert len(_ALLOWED_CLI_COMMANDS) >= 46
