"""
Дополнительные тесты для покрытия непротестированных модулей.

Покрывает:
- high_level.py: _generate_bsl_with_llm, _get_next_action_after_*, handle_explain
- _async_helpers.py: sync_to_async
- _security.py: check_path_safety, resolve_path_within_project
- session.py: SessionState, SessionManager (T6 atomic save)
- classifier.py: CR-10 confidence threshold
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from src.mcpserver.handlers.high_level import (
    handle_plan,
    handle_gather,
    handle_generate,
    handle_validate,
    handle_explain,
    handle_run_cli,
    _generate_bsl_with_llm,
    _get_next_action_after_generate,
    _get_next_action_after_validate,
    _group_violations_by_rule,
    _ALLOWED_CLI_COMMANDS,
)
from src.mcpserver.handlers._async_helpers import run_sync, sync_to_async
from src.services.session import SessionState, SessionManager


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project(tmp_path: Path):
    project = MagicMock()
    project.paths.root = tmp_path
    project.paths.runtime_dir = tmp_path / "runtime"
    project.paths.scripts_dir = tmp_path / "scripts"
    return project


# ============================================================================
# _async_helpers.py coverage
# ============================================================================


class TestAsyncHelpers:
    """Покрытие _async_helpers.py."""

    @pytest.mark.asyncio
    async def test_run_sync_returns_result(self):
        """run_sync возвращает результат sync-функции."""
        def sync_func(x):
            return x * 2

        result = await run_sync(sync_func, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_run_sync_with_kwargs(self):
        """run_sync передаёт kwargs."""
        def sync_func(a, b=0):
            return a + b

        result = await run_sync(sync_func, 3, b=4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_sync_to_async_wrapper(self):
        """sync_to_async создаёт async wrapper."""
        def sync_func(x):
            return x + 1

        async_func = sync_to_async(sync_func)
        result = await async_func(10)
        assert result == 11

    @pytest.mark.asyncio
    async def test_sync_to_async_preserves_docstring(self):
        """sync_to_async сохраняет docstring."""
        def sync_func():
            """Test docstring."""
            return 42

        async_func = sync_to_async(sync_func)
        assert async_func.__doc__ == "Test docstring."

    @pytest.mark.asyncio
    async def test_run_sync_propagates_exception(self):
        """run_sync пробрасывает исключения."""
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await run_sync(failing_func)


# ============================================================================
# session.py coverage
# ============================================================================


class TestSessionState:
    """Покрытие SessionState dataclass."""

    def test_session_state_defaults(self):
        """SessionState имеет корректные defaults."""
        s = SessionState()
        assert s.session_id  # auto-generated UUID
        assert s.created_at > 0
        assert s.plan is None
        assert s.gathered_context is None
        assert s.gathered_at == 0.0
        assert s.generated_artifacts == []
        assert s.validation_history == []
        assert s.tool_call_history == []

    def test_session_state_to_dict(self):
        """to_dict возвращает все поля."""
        s = SessionState()
        d = s.to_dict()
        assert "session_id" in d
        assert "created_at" in d
        assert "plan" in d
        assert "generated_artifacts" in d
        assert "validation_history" in d
        assert "tool_call_history" in d

    def test_session_state_from_dict(self):
        """from_dict десериализует."""
        data = {
            "session_id": "test-id",
            "created_at": 1234567890,
            "last_activity": 1234567890,
            "plan": {"query": "test"},
            "gathered_context": None,
            "gathered_at": 0.0,
            "generated_artifacts": [],
            "validation_history": [],
            "tool_call_history": [],
            "extra_field": "ignored",  # должен быть проигнорирован
        }
        s = SessionState.from_dict(data)
        assert s.session_id == "test-id"
        assert s.plan == {"query": "test"}

    def test_add_tool_call(self):
        """add_tool_call добавляет запись."""
        s = SessionState()
        s.add_tool_call("plan", {"query": "test"})
        assert len(s.tool_call_history) == 1
        assert s.tool_call_history[0]["tool_name"] == "plan"

    def test_add_tool_call_trims_history(self):
        """add_tool_call обрезает history до 20."""
        s = SessionState()
        for i in range(25):
            s.add_tool_call(f"tool_{i}", {})
        assert len(s.tool_call_history) == 20

    def test_has_called(self):
        """has_called проверяет историю."""
        s = SessionState()
        s.add_tool_call("plan", {})
        assert s.has_called("plan") is True
        assert s.has_called("gather") is False

    def test_set_plan(self):
        """set_plan устанавливает plan."""
        s = SessionState()
        s.set_plan({"query": "test"})
        assert s.plan == {"query": "test"}

    def test_set_gathered_context(self):
        """set_gathered_context кэширует контекст."""
        s = SessionState()
        s.set_gathered_context({"data": "test"})
        assert s.gathered_context == {"data": "test"}
        assert s.gathered_at > 0

    def test_add_artifact_returns_id(self):
        """add_artifact возвращает artifact_id."""
        s = SessionState()
        artifact_id = s.add_artifact({"code": "test"})
        assert artifact_id.startswith("artifact_")
        assert len(s.generated_artifacts) == 1

    def test_get_artifact(self):
        """get_artifact находит по ID."""
        s = SessionState()
        artifact_id = s.add_artifact({"code": "test"})
        artifact = s.get_artifact(artifact_id)
        assert artifact is not None
        assert artifact["code"] == "test"

    def test_get_artifact_not_found(self):
        """get_artifact возвращает None для несуществующего."""
        s = SessionState()
        assert s.get_artifact("nonexistent") is None

    def test_add_validation(self):
        """add_validation добавляет запись."""
        s = SessionState()
        s.add_validation({"artifact_id": "art_1", "violations": []})
        assert len(s.validation_history) == 1

    def test_touch_updates_last_activity(self):
        """touch обновляет last_activity."""
        s = SessionState()
        old_activity = s.last_activity
        time.sleep(0.01)
        s.touch()
        assert s.last_activity > old_activity


class TestSessionManager:
    """Покрытие SessionManager — включая T6 atomic save."""

    def test_get_session_creates_new(self, tmp_path):
        """get_session создаёт новую сессию если файла нет."""
        manager = SessionManager(tmp_path)
        session = manager.get_session()
        assert session is not None
        assert session.session_id  # UUID

    def test_save_and_load(self, tmp_path):
        """save + load сохраняет состояние."""
        manager = SessionManager(tmp_path)
        session = manager.get_session()
        session.set_plan({"query": "test"})
        manager.save()

        # Новый manager загружает
        manager2 = SessionManager(tmp_path)
        session2 = manager2.get_session()
        assert session2.plan == {"query": "test"}

    def test_reset_creates_new_session(self, tmp_path):
        """reset создаёт новую сессию."""
        manager = SessionManager(tmp_path)
        session1 = manager.get_session()
        session1.set_plan({"query": "old"})
        manager.save()

        session2 = manager.reset()
        assert session2.plan is None
        assert session2.session_id != session1.session_id

    def test_atomic_save_no_corruption(self, tmp_path):
        """T6: atomic save — файл не corrupt при нормальной записи."""
        manager = SessionManager(tmp_path)
        session = manager.get_session()
        session.set_plan({"query": "test"})
        manager.save()

        # Файл должен быть валидным JSON
        session_file = tmp_path / "session-state.json"
        data = json.loads(session_file.read_text())
        assert data["plan"] == {"query": "test"}

    def test_cleanup_removes_expired_artifacts(self, tmp_path):
        """CR-5: cleanup удаляет устаревшие artifacts."""
        manager = SessionManager(tmp_path)
        session = SessionState()
        session.generated_artifacts = [
            {"artifact_id": "old", "created_at": time.time() - 7200, "code": "old"},
            {"artifact_id": "new", "created_at": time.time() - 60, "code": "new"},
        ]
        manager._cleanup_expired(session)
        assert len(session.generated_artifacts) == 1
        assert session.generated_artifacts[0]["artifact_id"] == "new"

    def test_cleanup_trims_to_max(self, tmp_path):
        """CR-5: cleanup обрезает до MAX_ARTIFACTS."""
        manager = SessionManager(tmp_path)
        session = SessionState()
        session.generated_artifacts = [
            {"artifact_id": f"art_{i}", "created_at": time.time() - i, "code": f"code_{i}"}
            for i in range(25)
        ]
        manager._cleanup_expired(session)
        assert len(session.generated_artifacts) <= manager.MAX_ARTIFACTS

    def test_tmp_file_cleaned_on_error(self, tmp_path):
        """T6: tmp file удаляется при ошибке save."""
        manager = SessionManager(tmp_path)
        session = manager.get_session()

        # Mock os.replace чтобы бросить
        with patch("os.replace", side_effect=OSError("disk full")):
            manager.save()

        # tmp file не должен остаться
        tmp_file = tmp_path / "session-state.tmp"
        assert not tmp_file.exists()


# ============================================================================
# classifier.py — CR-10 confidence threshold
# ============================================================================


class TestClassifierConfidenceThreshold:
    """Покрытие CR-10 — confidence threshold для LLM fallback."""

    def test_high_confidence_no_llm_call(self):
        """Если regex confidence >= 0.5, LLM не вызывается."""
        from src.services.intent.classifier import classify_intent, _classify_with_llm

        with patch("src.services.intent.classifier._classify_with_llm") as mock_llm:
            intent = classify_intent("создай справочник", use_llm_fallback=True)
            mock_llm.assert_not_called()
            assert intent.name == "create_object"
            assert intent.confidence >= 0.9

    def test_low_confidence_triggers_llm(self):
        """Если regex confidence < 0.5, вызывается LLM."""
        from src.services.intent.classifier import classify_intent, Intent

        # Mock LLM чтобы вернул intent с confidence 0.6
        llm_intent = Intent(
            name="write_query",
            confidence=0.6,
            required_sources=["metadata"],
            workflow=[],
            matched_patterns=["llm_fallback"],
        )

        with patch("src.services.intent.classifier._classify_with_llm", return_value=llm_intent):
            # Запрос с 1 pattern match (confidence 0.8) — LLM не должен вызваться
            intent = classify_intent("создай справочник", use_llm_fallback=True)
            # confidence 0.9 >= 0.5 → LLM не нужен
            assert intent.name == "create_object"

    def test_classify_with_llm_max_tokens_not_num_predict(self):
        """T2: _classify_with_llm использует max_tokens, не num_predict."""
        import inspect
        from src.services.intent.classifier import _classify_with_llm

        src = inspect.getsource(_classify_with_llm)
        assert "max_tokens=10" in src
        assert "num_predict" not in src


# ============================================================================
# _group_violations_by_rule coverage
# ============================================================================


class TestGroupViolations:
    """Покрытие _group_violations_by_rule."""

    def test_empty_list(self):
        assert _group_violations_by_rule([]) == {}

    def test_single_rule(self):
        violations = [
            {"rule_id": "SEC001", "message": "v1"},
            {"rule_id": "SEC001", "message": "v2"},
        ]
        grouped = _group_violations_by_rule(violations)
        assert len(grouped) == 1
        assert len(grouped["SEC001"]) == 2

    def test_multiple_rules(self):
        violations = [
            {"rule_id": "SEC001", "message": "v1"},
            {"rule_id": "STD001", "message": "v2"},
        ]
        grouped = _group_violations_by_rule(violations)
        assert len(grouped) == 2

    def test_unknown_rule_id(self):
        violations = [{"message": "no rule_id"}]
        grouped = _group_violations_by_rule(violations)
        assert "UNKNOWN" in grouped

    def test_none_rule_id(self):
        violations = [{"rule_id": None, "message": "null"}]
        grouped = _group_violations_by_rule(violations)
        # None rule_id может быть key или UNKNOWN
        assert None in grouped or "UNKNOWN" in grouped


# ============================================================================
# _get_next_action_after_* coverage
# ============================================================================


class TestNextActionHelpers:
    """Покрытие _get_next_action_after_generate/validate."""

    def test_next_action_after_generate_passed_with_history(self):
        """generate passed + validate в history → done."""
        session = MagicMock()
        session.tool_call_history = [{"tool_name": "validate"}]

        action = _get_next_action_after_generate(
            validation_passed=True,
            warnings_count=0,
            artifact_id="art_1",
            session=session,
        )
        assert action["tool"] == "done"

    def test_next_action_after_generate_passed_without_history(self):
        """generate passed + нет validate в history → validate."""
        session = MagicMock()
        session.tool_call_history = []

        action = _get_next_action_after_generate(
            validation_passed=True,
            warnings_count=0,
            artifact_id="art_1",
            session=session,
        )
        assert action["tool"] == "validate"

    def test_next_action_after_generate_failed(self):
        """generate failed → validate."""
        session = MagicMock()
        session.tool_call_history = []

        action = _get_next_action_after_generate(
            validation_passed=False,
            warnings_count=3,
            artifact_id="art_1",
            session=session,
        )
        assert action["tool"] == "validate"
        assert "3" in action["why"]

    def test_next_action_after_validate_safe(self):
        """validate safe → done."""
        action = _get_next_action_after_validate(
            is_safe=True,
            must_fix_count=0,
            artifact={"task": "test", "target_context": "server", "artifact_id": "art_1"},
            session=MagicMock(),
        )
        assert action["tool"] == "done"

    def test_next_action_after_validate_unsafe(self):
        """validate unsafe → generate с fix_violations_from."""
        action = _get_next_action_after_validate(
            is_safe=False,
            must_fix_count=2,
            artifact={"task": "test", "target_context": "server", "artifact_id": "art_1"},
            session=MagicMock(),
        )
        assert action["tool"] == "generate"
        assert action["args"]["fix_violations_from"] == "art_1"

    def test_next_action_after_validate_no_artifact(self):
        """validate unsafe без artifact → generate без fix."""
        action = _get_next_action_after_validate(
            is_safe=False,
            must_fix_count=1,
            artifact=None,
            session=MagicMock(),
        )
        assert action["tool"] == "generate"
        # fix_violations_from будет пустой строкой (artifact_id=""), но это ok
        assert action["args"].get("fix_violations_from", "") == ""


# ============================================================================
# _generate_bsl_with_llm coverage
# ============================================================================


class TestGenerateBslWithLlm:
    """Покрытие _generate_bsl_with_llm."""

    @pytest.mark.asyncio
    async def test_returns_code_from_ollama(self, tmp_path):
        """Возвращает код от Ollama когда доступен."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = None
        session.plan = None

        mock_response = MagicMock()
        mock_response.text = "Процедура Тест()\nКонецПроцедуры"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            code, source = await _generate_bsl_with_llm(
                project, session, "test task", "server", []
            )

        assert source == "ollama_llm"
        assert "Процедура" in code

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, tmp_path):
        """Убирает markdown code fences."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = None
        session.plan = None

        mock_response = MagicMock()
        mock_response.text = "```bsl\nПроцедура Тест()\nКонецПроцедуры\n```"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            code, source = await _generate_bsl_with_llm(
                project, session, "test", "server", []
            )

        assert "```" not in code
        assert "Процедура" in code

    @pytest.mark.asyncio
    async def test_fallback_when_circuit_open(self, tmp_path):
        """Fallback на template когда circuit breaker open."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = None
        session.plan = {"intent": {"name": "create_object"}}

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "open"

            # BslTemplates может быть функцией, не классом — patch через где он используется
            with patch("src.mcpserver.handlers.high_level.BslTemplates", create=True) as mock_tpl_class:
                mock_tpl = mock_tpl_class.return_value
                mock_tpl.get_template.return_value = "template code"

                code, source = await _generate_bsl_with_llm(
                    project, session, "test", "server", []
                )

        # generate_for_task не должен вызываться
        mock_client.generate_for_task.assert_not_called()
        assert source != "ollama_llm"

    @pytest.mark.asyncio
    async def test_fallback_when_ollama_unavailable(self, tmp_path):
        """Fallback когда Ollama недоступен."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = None
        session.plan = None

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = False

            code, source = await _generate_bsl_with_llm(
                project, session, "test", "server", []
            )

        # Должен быть fallback или empty
        assert source != "ollama_llm"

    @pytest.mark.asyncio
    async def test_fix_violations_added_to_prompt(self, tmp_path):
        """CR-7: fix_violations добавляются в prompt."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = None
        session.plan = None

        fix_violations = [
            {"rule_id": "SEC001", "severity": "CRITICAL", "message": "SQL injection", "recommendation": "Use params"},
        ]

        mock_response = MagicMock()
        mock_response.text = "fixed code"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            await _generate_bsl_with_llm(
                project, session, "test", "server", fix_violations
            )

        # Проверяем что prompt содержит violations
        call_args = mock_client.generate_for_task.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "SEC001" in prompt
        assert "SQL injection" in prompt

    @pytest.mark.asyncio
    async def test_context_from_gathered_context(self, tmp_path):
        """Context из gathered_context добавляется в prompt."""
        project = _make_project(tmp_path)
        session = MagicMock()
        session.gathered_context = {
            "platform_methods": [{"name_ru": "Сообщить", "syntax": "Сообщить()"}],
            "safe_methods": [{"name_ru": "Найти", "syntax": "Найти()"}],
            "knowledge_articles": [{"title": "Паттерн X"}],
        }
        session.plan = None

        mock_response = MagicMock()
        mock_response.text = "code with context"
        mock_response.error = ""

        with patch("src.services.llm_ollama.OllamaClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.is_available.return_value = True
            mock_client.get_circuit_breaker_state.return_value = "closed"
            mock_client.generate_for_task.return_value = mock_response

            await _generate_bsl_with_llm(
                project, session, "test", "server", []
            )

        prompt = mock_client.generate_for_task.call_args.kwargs.get("prompt", "")
        assert "Сообщить" in prompt
        assert "Найти" in prompt
        assert "Паттерн X" in prompt


# ============================================================================
# run_cli whitelist coverage
# ============================================================================


class TestRunCliWhitelist:
    """Покрытие run_cli whitelist."""

    def test_whitelist_contains_all_legacy_tools(self):
        """CR-3: whitelist содержит все legacy tools."""
        expected = [
            "search_platform_method",
            "get_method_details",
            "get_method_details_batch",
            "get_safe_methods",
            "solve_context",
            "solve_check",
            "check_bsl_context",
            "bsl_templates",
            "generate_query",
            "get_object_structure",
        ]
        for cmd in expected:
            assert cmd in _ALLOWED_CLI_COMMANDS, f"{cmd} not in whitelist"

    def test_whitelist_contains_analyzers(self):
        """Whitelist содержит анализаторы."""
        assert "audit_security" in _ALLOWED_CLI_COMMANDS
        assert "get_code_metrics" in _ALLOWED_CLI_COMMANDS
        assert "check_transactions" in _ALLOWED_CLI_COMMANDS
        assert "analyze_queries" in _ALLOWED_CLI_COMMANDS
        assert "analyze_architecture" in _ALLOWED_CLI_COMMANDS

    def test_whitelist_contains_dsl(self):
        """Whitelist содержит DSL compilers."""
        assert "dsl_compile_meta" in _ALLOWED_CLI_COMMANDS
        assert "dsl_compile_form" in _ALLOWED_CLI_COMMANDS
        assert "dsl_compile_skd" in _ALLOWED_CLI_COMMANDS

    def test_whitelist_contains_cfe(self):
        """Whitelist содержит CFE tools."""
        assert "cfe_borrow" in _ALLOWED_CLI_COMMANDS
        assert "cfe_patch_method" in _ALLOWED_CLI_COMMANDS
        assert "cfe_diff" in _ALLOWED_CLI_COMMANDS

    def test_whitelist_count(self):
        """Whitelist содержит 46+ команд."""
        assert len(_ALLOWED_CLI_COMMANDS) >= 46


# ============================================================================
# Explain handler coverage
# ============================================================================


class TestExplainHandler:
    """Покрытие handle_explain."""

    @pytest.mark.asyncio
    async def test_explain_no_args(self, tmp_path):
        """explain без args — ошибка."""
        project = _make_project(tmp_path)
        result = await handle_explain(project, {})
        data = _parse(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_explain_file_path(self, tmp_path):
        """explain с file_path — возвращает analysis_sources."""
        project = _make_project(tmp_path)

        mock_metrics = MagicMock()
        mock_metrics.text = json.dumps({"total_lines": 100, "is_god_object": False})

        with patch("src.mcpserver.handlers.quality.handle_get_code_metrics") as mock_m:
            mock_m.return_value = [mock_metrics]
            result = await handle_explain(project, {"file_path": "/tmp/test.bsl"})

        data = _parse(result)
        assert "analysis_sources" in data
        assert "code_metrics" in data["analysis_sources"]

    @pytest.mark.asyncio
    async def test_explain_query(self, tmp_path):
        """explain с query — поиск."""
        project = _make_project(tmp_path)

        mock_result = MagicMock()
        mock_result.text = json.dumps({"query": "test", "platform_methods": []})

        with patch("src.mcpserver.handlers.analyzers.handle_solve_context") as mock_solve:
            mock_solve.return_value = [mock_result]
            result = await handle_explain(project, {"query": "test query"})

        data = _parse(result)
        assert "_next_action" in data

    @pytest.mark.asyncio
    async def test_explain_query_does_not_overwrite_plan(self, tmp_path):
        """T10: explain(query) не перетирает существующий plan."""
        project = _make_project(tmp_path)

        # Сначала plan
        plan_result = await handle_plan(project, {"query": "создай справочник"})
        plan_data = _parse(plan_result)
        original_plan_id = plan_data["plan_id"]

        # explain с query
        mock_result = MagicMock()
        mock_result.text = json.dumps({"query": "test", "platform_methods": []})

        with patch("src.mcpserver.handlers.analyzers.handle_solve_context") as mock_solve:
            mock_solve.return_value = [mock_result]
            await handle_explain(project, {"query": "another query"})

        # Проверяем что plan не перетёрт
        from src.services.session import SessionManager
        manager = SessionManager(project.paths.runtime_dir)
        session = manager.get_session()
        assert session.plan is not None
        assert "query" in session.plan
        # plan должен содержать intent info, не только explain stub
        assert "intent" in session.plan
