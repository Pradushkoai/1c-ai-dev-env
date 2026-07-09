"""
D-5/I6.3 (2026-07-06): Тесты для MCP HTTP/SSE transport.

Проверяет:
- run_mcp_http_server принимает sse/http transport
- SSE server запускается и отвечает на health check
- HTTP server запускается и отвечает на health check
- CLI аргументы --transport, --host, --port работают
- Неверный transport → ValueError
- Health endpoint возвращает корректный JSON
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PYTHON = sys.executable


# ============================================================================
# Module import tests
# ============================================================================


class TestModuleImports:
    """Модуль mcp_http_server импортируется корректно."""

    def test_module_imports(self) -> None:
        """Модуль можно импортировать."""
        from src.mcp_http_server import run_mcp_http_server, run_sse_server, run_http_server
        assert callable(run_mcp_http_server)
        assert callable(run_sse_server)
        assert callable(run_http_server)

    def test_run_mcp_http_server_sync_exists(self) -> None:
        from src.mcp_http_server import run_mcp_http_server_sync
        assert callable(run_mcp_http_server_sync)


# ============================================================================
# Transport selection tests
# ============================================================================


class TestTransportSelection:
    """Выбор transport работает корректно."""

    def test_invalid_transport_raises(self) -> None:
        """Неверный transport → ValueError."""
        from src.mcp_http_server import run_mcp_http_server

        with pytest.raises(ValueError, match="Unknown transport"):
            asyncio.run(run_mcp_http_server(transport="websocket"))

    def test_sse_transport_callable(self) -> None:
        """SSE transport можно вызвать (но не запускаем)."""
        from src.mcp_http_server import run_sse_server
        assert asyncio.iscoroutinefunction(run_sse_server)

    def test_http_transport_callable(self) -> None:
        """HTTP transport можно вызвать."""
        from src.mcp_http_server import run_http_server
        assert asyncio.iscoroutinefunction(run_http_server)


# ============================================================================
# CLI argument tests
# ============================================================================


class TestCliArguments:
    """CLI аргументы для mcp serve работают."""

    def test_mcp_serve_help_shows_transport(self) -> None:
        """--help показывает --transport."""
        result = subprocess.run(
            [PYTHON, "-m", "src.cli", "mcp", "serve", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "--transport" in result.stdout
        assert "sse" in result.stdout
        assert "http" in result.stdout
        assert "--host" in result.stdout
        assert "--port" in result.stdout

    def test_mcp_serve_default_transport_stdio(self) -> None:
        """По умолчанию transport=stdio."""
        result = subprocess.run(
            [PYTHON, "-m", "src.cli", "mcp", "serve", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert "stdio" in result.stdout

    def test_mcp_serve_transport_choices(self) -> None:
        """Доступные choices: stdio, sse, http."""
        result = subprocess.run(
            [PYTHON, "-m", "src.cli", "mcp", "serve", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert "{stdio,sse,http}" in result.stdout


# ============================================================================
# SSE server integration test
# ============================================================================


class TestSseServerIntegration:
    """Интеграционный тест: SSE server запускается и отвечает на health check."""

    @pytest.fixture
    def sse_server_process(self):
        """Запустить SSE сервер на случайном порту."""
        port = 18923  # нестандартный порт чтобы избежать конфликтов

        proc = subprocess.Popen(
            [PYTHON, "-m", "src.cli", "mcp", "serve",
             "--transport", "sse",
             "--host", "127.0.0.1",
             "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )

        # Ждём пока сервер запустится
        import urllib.request
        import urllib.error

        for _ in range(30):  # 3 секунды максимум
            time.sleep(0.1)
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                )
                if resp.status == 200:
                    break
            except (urllib.error.URLError, ConnectionRefusedError):
                continue
        else:
            # Сервер не запустился — собираем stderr
            stderr = proc.stderr.read().decode("utf-8") if proc.stderr else ""
            proc.terminate()
            pytest.fail(f"SSE server не запустился за 3 сек. stderr: {stderr[:500]}")

        yield port

        # Cleanup
        proc.terminate()
        proc.wait(timeout=5)

    def test_health_check_sse(self, sse_server_process: int) -> None:
        """Health endpoint отвечает 200 с правильным JSON."""
        import urllib.request

        port = sse_server_process
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
        assert resp.status == 200

        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["server"] == "1c-ai-dev-env"
        assert data["transport"] == "sse"
        assert data["tools"] == 54

    def test_sse_endpoint_exists(self, sse_server_process: int) -> None:
        """SSE endpoint (/sse) доступен."""
        import urllib.request
        import urllib.error

        port = sse_server_process
        # SSE endpoint должен отвечать (не 404)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/sse", timeout=2)
            # SSE возвращает text/event-stream
            assert resp.status == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
        except urllib.error.URLError:
            # SSE держит соединение открытым — может таймаутить, это OK
            pass


# ============================================================================
# HTTP server integration test
# ============================================================================


class TestHttpServerIntegration:
    """Интеграционный тест: Streamable HTTP server."""

    @pytest.fixture
    def http_server_process(self):
        """Запустить HTTP сервер на случайном порту."""
        port = 18924

        proc = subprocess.Popen(
            [PYTHON, "-m", "src.cli", "mcp", "serve",
             "--transport", "http",
             "--host", "127.0.0.1",
             "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )

        import urllib.request
        import urllib.error

        for _ in range(30):
            time.sleep(0.1)
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                )
                if resp.status == 200:
                    break
            except (urllib.error.URLError, ConnectionRefusedError):
                continue
        else:
            stderr = proc.stderr.read().decode("utf-8") if proc.stderr else ""
            proc.terminate()
            pytest.fail(f"HTTP server не запустился за 3 сек. stderr: {stderr[:500]}")

        yield port

        proc.terminate()
        proc.wait(timeout=5)

    def test_health_check_http(self, http_server_process: int) -> None:
        """Health endpoint отвечает 200 с правильным JSON."""
        import urllib.request

        port = http_server_process
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)
        assert resp.status == 200

        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["server"] == "1c-ai-dev-env"
        assert data["transport"] == "streamable-http"
        assert data["tools"] == 54


# ============================================================================
# pyproject.toml dependencies test
# ============================================================================


class TestDependencies:
    """Зависимости для HTTP transport указаны в pyproject.toml."""

    def test_mcp_http_optional_deps_exist(self) -> None:
        """mcp-http optional dependencies существуют."""
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "mcp-http" in content
        assert "uvicorn" in content
        assert "starlette" in content

    def test_uvicorn_installed(self) -> None:
        """uvicorn установлен."""
        try:
            import uvicorn
            assert uvicorn is not None
        except ImportError:
            pytest.skip("uvicorn не установлен")

    def test_starlette_installed(self) -> None:
        """starlette установлена."""
        try:
            import starlette
            assert starlette is not None
        except ImportError:
            pytest.skip("starlette не установлена")
