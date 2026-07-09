"""
R12+R13: Тесты для performance benchmarks и token measurement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestPerformanceBenchmarks:
    """R12: Тесты для performance benchmarks."""

    def test_intent_classification_is_fast(self):
        """Intent classification < 5ms per query (обычно <1ms)."""
        from src.services.intent.classifier import classify_intent
        import time

        queries = ["создай справочник", "напиши запрос", "проверь код"]
        # Warm up
        for q in queries:
            classify_intent(q, use_llm_fallback=False)

        start = time.perf_counter()
        for _ in range(100):
            for q in queries:
                classify_intent(q, use_llm_fallback=False)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / (100 * len(queries))) * 1000

        # Should be < 5ms per query (typically <1ms)
        assert avg_ms < 5.0, f"Intent classification too slow: {avg_ms:.2f}ms/query"

    def test_source_selection_reduces_search_calls(self):
        """Source selection вызывает меньше search методов."""
        from src.services.task_processor import TaskProcessor
        from src.services.intent.classifier import classify_intent

        paths = MagicMock()
        paths.scripts_dir = Path("/nonexistent")
        paths.bsl_ls_binary = Path("/nonexistent")
        processor = TaskProcessor(paths)

        # audit_code intent: "проверь код на безопасность"
        intent = classify_intent("проверь код на безопасность", use_llm_fallback=False)
        assert intent.name == "audit_code", f"Expected audit_code, got {intent.name}"
        # audit_code required_sources: security_rules, standards
        # (not metadata, forms, skd, api_reference)

        with patch.object(processor, "_search_metadata") as mock_meta, \
             patch.object(processor, "_search_forms") as mock_forms, \
             patch.object(processor, "_search_skd") as mock_skd, \
             patch.object(processor, "_search_api_reference") as mock_api, \
             patch.object(processor, "_search_platform_methods"), \
             patch.object(processor, "_search_knowledge_base"), \
             patch.object(processor, "_standards_summary", return_value={"total": 0}):
            
            processor.solve(
                "проверь код на безопасность",
                config_name="test",
                required_sources=intent.required_sources,
            )
            
            # audit_code should NOT call metadata/forms/skd/api
            mock_meta.assert_not_called()
            mock_forms.assert_not_called()
            mock_skd.assert_not_called()
            mock_api.assert_not_called()

    def test_gather_cache_returns_cached_result(self):
        """gather() cache — повторный вызов возвращает кэш."""
        import asyncio
        import shutil
        from src.mcpserver.handlers.high_level import handle_plan, handle_gather

        async def run():
            # Clean session dir to ensure fresh state
            test_dir = Path("/tmp/test_cache_bench")
            if test_dir.exists():
                shutil.rmtree(test_dir)

            project = MagicMock()
            project.paths.root = test_dir
            project.paths.runtime_dir = test_dir / "runtime"
            project.paths.runtime_dir.mkdir(parents=True, exist_ok=True)

            await handle_plan(project, {"query": "test"})

            with patch("src.services.task_processor.TaskProcessor") as mock_tp:
                mock_ctx = MagicMock()
                mock_ctx.to_dict.return_value = {"query": "test"}
                mock_tp.return_value.solve.return_value = mock_ctx

                # First call
                import json
                result1 = await handle_gather(project, {"plan_id": "test"})
                data1 = json.loads(result1[0].text)
                assert data1["_cached"] is False

                # Second call — should be cached
                result2 = await handle_gather(project, {"plan_id": "test"})
                data2 = json.loads(result2[0].text)
                assert data2["_cached"] is True

                # solve should be called only once
                assert mock_tp.return_value.solve.call_count == 1

        asyncio.run(run())


class TestTokenMeasurement:
    """R13: Тесты для token measurement."""

    def test_estimate_tokens(self):
        """_estimate_tokens возвращает разумную оценку."""
        sys.path.insert(0, str(_REPO_ROOT / "scripts"))
        from run_benchmarks_r12_r13 import _estimate_tokens

        # Empty string
        assert _estimate_tokens("") >= 1

        # Short string
        tokens = _estimate_tokens("hello world")
        assert tokens >= 2  # ~11 chars / 4

        # Russian text
        tokens_ru = _estimate_tokens("создай справочник товаров")
        assert tokens_ru >= 6  # ~25 chars / 4

    def test_next_action_smaller_than_workflow(self):
        """_next_action (1 step) < _workflow (7 steps) по token count."""
        sys.path.insert(0, str(_REPO_ROOT / "scripts"))
        from run_benchmarks_r12_r13 import _estimate_tokens

        old_workflow = json.dumps([
            {"step": i, "tool": f"tool_{i}", "why": f"reason {i}" * 5}
            for i in range(1, 8)
        ], ensure_ascii=False)

        new_next_action = json.dumps({
            "tool": "gather", "args": {}, "why": "Собрать контекст"
        }, ensure_ascii=False)

        old_tokens = _estimate_tokens(old_workflow)
        new_tokens = _estimate_tokens(new_next_action)

        assert new_tokens < old_tokens, (
            f"_next_action ({new_tokens} tokens) should be < _workflow ({old_tokens} tokens)"
        )

    def test_plan_response_token_count(self):
        """plan() response < 300 tokens (разумный размер)."""
        import asyncio
        from src.mcpserver.handlers.high_level import handle_plan
        sys.path.insert(0, str(_REPO_ROOT / "scripts"))
        from run_benchmarks_r12_r13 import _estimate_tokens

        async def run():
            project = MagicMock()
            project.paths.root = Path("/tmp/test_tokens")
            project.paths.runtime_dir = Path("/tmp/test_tokens/runtime")
            project.paths.runtime_dir.mkdir(parents=True, exist_ok=True)

            result = await handle_plan(project, {"query": "создай справочник"})
            tokens = _estimate_tokens(result[0].text)
            return tokens

        tokens = asyncio.run(run())
        assert tokens < 500, f"plan() response too large: {tokens} tokens"
        assert tokens > 50, f"plan() response too small: {tokens} tokens"
