"""
D-5/I6.3 (2026-07-06): HTTP/SSE transport для MCP сервера.

Добавляет возможность запускать MCP сервер с сетевым доступом:
- SSE (Server-Sent Events) — для совместимости со старыми MCP клиентами
- Streamable HTTP — современный transport (MCP 2025-03-26 spec)

Запуск:
    # SSE transport (порт 8080)
    1c-ai mcp serve --transport sse --port 8080 --host 0.0.0.0

    # Streamable HTTP (порт 8080)
    1c-ai mcp serve --transport http --port 8080 --host 0.0.0.0

    # stdio (по умолчанию, как раньше)
    1c-ai mcp serve

Подключение клиента (Cursor/Claude Desktop):
    {
      "mcpServers": {
        "1c-ai-dev-env": {
          "transport": {
            "type": "sse",
            "url": "http://your-server:8080/sse"
          }
        }
      }
    }

Безопасность:
- По умолчанию слушает только localhost (127.0.0.1)
- Для external доступа: --host 0.0.0.0 + firewall + рекомендуется reverse proxy с TLS
- CORS: по умолчанию разрешены все origins (для reverse proxy)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server

from .mcp_server import create_mcp_server

logger = logging.getLogger(__name__)


# ============================================================================
# SSE Transport
# ============================================================================


async def run_sse_server(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Запустить MCP сервер с SSE transport.

    SSE (Server-Sent Events) — однонаправленный stream от сервера к клиенту.
    Клиент отправляет POST запросы, сервер отвечает через SSE stream.

    Args:
        host: Хост для прослушивания (127.0.0.1 = только локально,
              0.0.0.0 = все интерфейсы).
        port: Порт для прослушивания.
    """
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse
    import uvicorn

    server = create_mcp_server()
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request: Any) -> Any:
        """SSE endpoint — клиент подключается сюда для получения событий."""
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    async def handle_health(request: Any) -> Any:
        """Health check endpoint."""
        return JSONResponse({
            "status": "ok",
            "server": "1c-ai-dev-env",
            "transport": "sse",
            "tools": 45,
        })

    @asynccontextmanager
    async def lifespan(app: Any) -> Any:
        """Lifespan: логируем старт/остановку."""
        logger.info("MCP SSE server starting on %s:%d", host, port)
        yield
        logger.info("MCP SSE server stopped")

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
            Route("/health", endpoint=handle_health),
        ],
        lifespan=lifespan,
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


# ============================================================================
# Streamable HTTP Transport
# ============================================================================


async def run_http_server(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Запустить MCP сервер со Streamable HTTP transport.

    Streamable HTTP — современный transport (MCP 2025-03-26 spec).
    Поддерживает stateless и stateful режимы, лучше для production.

    Args:
        host: Хост для прослушивания.
        port: Порт для прослушивания.
    """
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse
    import uvicorn

    server = create_mcp_server()
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=False,
    )

    async def handle_http(request: Any) -> Any:
        """HTTP endpoint для MCP протокола."""
        async with session_manager.handle_request(
            request.scope, request.receive, request._send
        ) as stream:
            # stream — это контекстный менеджер с read/write streams
            pass  # session_manager.handle_request обрабатывает всё внутри

    async def handle_health(request: Any) -> Any:
        """Health check endpoint."""
        return JSONResponse({
            "status": "ok",
            "server": "1c-ai-dev-env",
            "transport": "streamable-http",
            "tools": 45,
        })

    @asynccontextmanager
    async def lifespan(app: Any) -> Any:
        """Lifespan: инициализация session manager."""
        logger.info("MCP HTTP server starting on %s:%d", host, port)
        async with session_manager.run():
            yield
        logger.info("MCP HTTP server stopped")

    app = Starlette(
        debug=False,
        routes=[
            Mount("/mcp", app=handle_http),
            Route("/health", endpoint=handle_health),
        ],
        lifespan=lifespan,
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


# ============================================================================
# Unified entry point
# ============================================================================


async def run_mcp_http_server(
    transport: str = "sse",
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Запустить MCP сервер с HTTP transport.

    Args:
        transport: "sse" или "http" (streamable HTTP).
        host: Хост.
        port: Порт.

    Raises:
        ValueError: При неизвестном transport.
    """
    if transport == "sse":
        await run_sse_server(host=host, port=port)
    elif transport in ("http", "streamable-http"):
        await run_http_server(host=host, port=port)
    else:
        raise ValueError(
            f"Unknown transport: '{transport}'. Use 'sse', 'http', or 'stdio'."
        )


def run_mcp_http_server_sync(
    transport: str = "sse",
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Синхронная обёртка для CLI."""
    asyncio.run(run_mcp_http_server(transport=transport, host=host, port=port))
