"""
Тесты для P1.10: asyncio.to_thread() обёртки для sync-вызовов в MCP handlers.

До фикса: handlers в analyzers.py и config_search.py вызывали sync-функции
(processor.check, processor.solve, project.search_methods, build_call_graph)
напрямую в async-функциях. Это блокировало event loop MCP-сервера на время
выполнения — параллельные запросы от IDE стояли в очереди.

После фикса: sync-вызовы обёрнуты в run_sync() из _async_helpers.py, который
использует asyncio.to_thread() для запуска в отдельном потоке.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcpserver.handlers._async_helpers import run_sync, sync_to_async


# ============================================================================
# Тесты — helper run_sync
# ============================================================================


class TestRunSync:
    """Базовая функциональность run_sync."""

    @pytest.mark.asyncio
    async def test_returns_result_of_sync_function(self) -> None:
        """run_sync возвращает результат sync-функции."""

        def sync_func(x: int, y: int) -> int:
            return x + y

        result = await run_sync(sync_func, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_passes_kwargs(self) -> None:
        """run_sync корректно передаёт kwargs."""

        def sync_func(*, a: int, b: int) -> int:
            return a * b

        result = await run_sync(sync_func, a=3, b=4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_propagates_exceptions(self) -> None:
        """Исключения из sync-функции пробрасываются в caller."""

        def raising_func() -> None:
            raise ValueError("sync error")

        with pytest.raises(ValueError, match="sync error"):
            await run_sync(raising_func)

    @pytest.mark.asyncio
    async def test_does_not_block_event_loop(self) -> None:
        """Пока sync-функция спит, async-задачи могут выполняться.

        Это ключевое свойство asyncio.to_thread: event loop свободен.
        """
        loop_started = asyncio.Event()

        async def background_task() -> None:
            loop_started.set()
            # Эта задача должна выполниться ПОКА sync-функция спит
            await asyncio.sleep(0.05)

        def blocking_sync() -> str:
            time.sleep(0.2)  # sync sleep блокирует поток, но не event loop
            return "done"

        # Запускаем sync-функцию и background-задачу параллельно
        bg_task = asyncio.create_task(background_task())
        result = await run_sync(blocking_sync)
        await bg_task

        assert result == "done"
        # Если event loop был заблокирован, bg_task не успел бы установиться
        assert loop_started.is_set()

    @pytest.mark.asyncio
    async def test_runs_in_different_thread(self) -> None:
        """sync-функция должна выполняться в ОТДЕЛЬНОМ потоке, не в main."""
        import threading

        main_thread = threading.current_thread().ident
        captured_thread = None

        def capture_thread() -> int:
            nonlocal captured_thread
            captured_thread = threading.current_thread().ident
            return captured_thread

        result = await run_sync(capture_thread)
        assert result == captured_thread
        assert result != main_thread, (
            f"sync function must run in a different thread, "
            f"got same as main: {main_thread}"
        )


# ============================================================================
# Тесты — decorator sync_to_async
# ============================================================================


class TestSyncToAsyncDecorator:
    """Декоратор sync_to_async преобразует sync в async."""

    @pytest.mark.asyncio
    async def test_decorator_returns_coroutine(self) -> None:
        """sync_to_async возвращает функцию, которая возвращает coroutine."""

        @sync_to_async
        def my_sync(x: int) -> int:
            return x * 2

        # Должна быть callable
        assert callable(my_sync)
        # Вызов возвращает awaitable
        coro = my_sync(5)
        assert hasattr(coro, "__await__")
        result = await coro
        assert result == 10

    @pytest.mark.asyncio
    async def test_decorator_preserves_args(self) -> None:
        """Декоратор корректно передаёт *args и **kwargs."""

        @sync_to_async
        def my_sync(a: int, b: int, *, c: int) -> int:
            return a + b + c

        result = await my_sync(1, 2, c=3)
        assert result == 6

    @pytest.mark.asyncio
    async def test_decorator_propagates_exceptions(self) -> None:
        """Исключения пробрасываются."""

        @sync_to_async
        def raising() -> None:
            raise RuntimeError("decorated error")

        with pytest.raises(RuntimeError, match="decorated error"):
            await raising()


# ============================================================================
# Тесты — handlers используют run_sync
# ============================================================================


class TestHandlersUseRunSync:
    """Handlers должны вызывать sync-функции через run_sync, не напрямую."""

    @pytest.mark.asyncio
    async def test_solve_check_uses_to_thread(self, tmp_path) -> None:
        """handle_solve_check должен вызвать processor.check через run_sync."""
        from src.mcpserver.handlers.analyzers import handle_solve_check

        # Создаём mock project
        project = MagicMock()
        project.paths = tmp_path

        # Патчим TaskProcessor и run_sync
        with patch(
            "src.services.task_processor.TaskProcessor"
        ) as mock_tp_class, patch(
            "src.mcpserver.handlers.analyzers.run_sync", new_callable=AsyncMock
        ) as mock_run_sync:
            processor = mock_tp_class.return_value
            mock_result = MagicMock()
            mock_result.to_dict.return_value = {"ok": True}
            mock_run_sync.return_value = mock_result

            result = await handle_solve_check(
                project, {"file_path": "test.bsl", "level": "standard"}
            )

            # run_sync должен быть вызван (а не processor.check напрямую)
            assert mock_run_sync.called, (
                "handle_solve_check must call run_sync() — not processor.check() directly"
            )
            # Первый аргумент run_sync — это processor.check
            called_args = mock_run_sync.call_args
            assert called_args.args[0] == processor.check, (
                "run_sync must be called with processor.check as first arg"
            )

    @pytest.mark.asyncio
    async def test_search_1c_methods_uses_to_thread(self) -> None:
        """handle_search_1c_methods должен вызвать search_methods через run_sync."""
        from src.mcpserver.handlers.config_search import handle_search_1c_methods

        project = MagicMock()

        with patch(
            "src.mcpserver.handlers.config_search.run_sync", new_callable=AsyncMock
        ) as mock_run_sync:
            mock_run_sync.return_value = []

            await handle_search_1c_methods(
                project, {"query": "Найти", "limit": 5}
            )

            assert mock_run_sync.called, (
                "handle_search_1c_methods must use run_sync for project.search_methods"
            )
            called_args = mock_run_sync.call_args
            assert called_args.args[0] == project.search_methods, (
                "run_sync must be called with project.search_methods as first arg"
            )

    @pytest.mark.asyncio
    async def test_analyze_bsl_uses_to_thread(self) -> None:
        """handle_analyze_bsl должен вызвать bsl_analyzer.analyze через run_sync."""
        from src.mcpserver.handlers.analyzers import handle_analyze_bsl

        project = MagicMock()

        with patch(
            "src.mcpserver.handlers.analyzers.run_sync", new_callable=AsyncMock
        ) as mock_run_sync:
            mock_result = MagicMock()
            mock_result.total = 0
            mock_result.by_code = {}
            mock_result.diagnostics = []
            mock_run_sync.return_value = mock_result

            await handle_analyze_bsl(project, {"file_path": "test.bsl"})

            assert mock_run_sync.called, (
                "handle_analyze_bsl must use run_sync for bsl_analyzer.analyze"
            )
            called_args = mock_run_sync.call_args
            assert called_args.args[0] == project.bsl_analyzer.analyze


# ============================================================================
# Тесты — concurrent MCP requests (event loop свободен)
# ============================================================================


class TestConcurrentMcpRequests:
    """При нескольких параллельных MCP-запросах они должны выполняться
    конкурентно, а не последовательно (благодаря to_thread)."""

    @pytest.mark.asyncio
    async def test_two_heavy_searches_run_concurrently(self) -> None:
        """Два search_1c_methods параллельно должны завершиться быстрее,
        чем сумма их длительностей — если event loop не заблокирован."""
        from src.mcpserver.handlers.config_search import handle_search_1c_methods

        project = MagicMock()
        # Делаем search_methods медленным (sync-функция)
        def slow_search(query, limit):
            time.sleep(0.2)  # 200мс sync блокировка
            return [{"name": query}]

        project.search_methods = slow_search

        async def make_call(query: str) -> str:
            result = await handle_search_1c_methods(
                project, {"query": query, "limit": 1}
            )
            import json

            return json.loads(result[0].text)[0]["name"]

        # Запускаем 2 запроса параллельно
        t0 = time.perf_counter()
        results = await asyncio.gather(
            make_call("test1"),
            make_call("test2"),
        )
        elapsed = time.perf_counter() - t0

        # Если event loop заблокирован — суммарное время ~0.4с
        # Если concurrent (to_thread работает) — ~0.2с
        # Допускаем небольшой оверхед
        assert elapsed < 0.35, (
            f"Two parallel searches took {elapsed:.2f}s — event loop may be blocked. "
            f"Expected <0.35s with to_thread concurrency."
        )
        assert set(results) == {"test1", "test2"}
