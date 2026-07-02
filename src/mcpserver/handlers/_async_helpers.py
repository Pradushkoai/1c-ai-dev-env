"""
async_helpers.py — утилиты для async-safe вызовов sync-кода в MCP handlers.

P1.10: MCP-сервер работает в event loop asyncio. Sync-вызовы процессора
(TaskProcessor.solve, TaskProcessor.check, project.search_methods) блокируют
event loop — параллельные MCP-запросы от IDE стоят в очереди.

Решение: оборачивать sync-вызовы в asyncio.to_thread(), который запускает их
в отдельном потоке. event loop остаётся свободным для других запросов.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def run_sync(func: Callable[..., T], /, *args, **kwargs) -> T:
    """
    Запустить sync-функцию в отдельном потоке, не блокируя event loop.

    Обёртка над asyncio.to_thread() с более коротким синтаксисом и
    поддержкой kwargs (через functools.partial под капотом).

    Args:
        func: Синхронная функция для выполнения.
        *args, **kwargs: Аргументы для func.

    Returns:
        Результат func(*args, **kwargs).

    Examples:
        # Вместо:
        #   result = processor.check(Path(file_path), level="standard")
        # Делаем:
        #   result = await run_sync(processor.check, Path(file_path), level="standard")

        # С lambda для сложных выражений:
        #   configs = await run_sync(lambda: project.list_configs_info())
    """
    # asyncio.to_thread поддерживает kwargs начиная с Python 3.9+.
    return await asyncio.to_thread(func, *args, **kwargs)


def sync_to_async(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """
    Декоратор: преобразует sync-функцию в async-функцию через asyncio.to_thread.

    Удобно для создания async-обёрток над sync-методами:

        # В handler:
        async_search = sync_to_async(project.search_methods)
        results = await async_search(query, limit=10)

    Или как декоратор:

        @sync_to_async
        def my_heavy_sync_function(path: Path) -> dict:
            ...

        # Теперь my_heavy_sync_function возвращает coroutine
        result = await my_heavy_sync_function(path)
    """

    async def wrapper(*args, **kwargs) -> T:
        return await asyncio.to_thread(func, *args, **kwargs)

    wrapper.__doc__ = func.__doc__
    wrapper.__name__ = f"async_{getattr(func, '__name__', 'wrapper')}"
    return wrapper
