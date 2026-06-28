"""
End-to-end тест MCP-сервера через stdio: initialize + tools/list.
Это проверяет, что сервер реально запускается и отвечает по протоколу MCP.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path('/home/z/my-project/repo_work')


def send_jsonrpc(proc, msg: dict) -> None:
    """Отправить JSON-RPC сообщение в процесс."""
    data = json.dumps(msg) + '\n'
    proc.stdin.write(data)
    proc.stdin.flush()


def read_jsonrpc(proc) -> dict:
    """Прочитать одно JSON-RPC сообщение из stdout."""
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("Пустой ответ от сервера")
    return json.loads(line)


def main():
    """Запускаем MCP-сервер и тестируем протокол."""
    # Запускаем MCP-сервер
    proc = subprocess.Popen(
        [sys.executable, '-m', 'src.cli', 'mcp', 'serve'],
        cwd=str(REPO_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # 1. initialize
        send_jsonrpc(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        })

        resp = read_jsonrpc(proc)
        assert resp["id"] == 1, f"Wrong id: {resp}"
        assert "result" in resp, f"No result: {resp}"
        assert "protocolVersion" in resp["result"], f"No protocolVersion: {resp}"
        assert "serverInfo" in resp["result"], f"No serverInfo: {resp}"
        assert resp["result"]["serverInfo"]["name"] == "1c-ai-dev-env"
        print("✅ initialize OK")

        # 2. Отправляем initialized notification
        send_jsonrpc(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })

        # 3. tools/list
        send_jsonrpc(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })

        resp = read_jsonrpc(proc)
        assert resp["id"] == 2, f"Wrong id: {resp}"
        assert "result" in resp, f"No result: {resp}"
        assert "tools" in resp["result"], f"No tools: {resp}"
        tools = resp["result"]["tools"]
        assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"

        expected_names = {
            'list_configs', 'search_1c_methods', 'get_api_reference',
            'analyze_bsl', 'check_standards', 'solve_context', 'solve_check',
            'data_status'
        }
        actual_names = {t['name'] for t in tools}
        assert expected_names == actual_names, f"Tool names mismatch: {actual_names}"

        print(f"✅ tools/list OK ({len(tools)} tools)")
        for t in tools:
            print(f"   • {t['name']}")

        # 4. call list_configs
        send_jsonrpc(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_configs",
                "arguments": {}
            }
        })

        resp = read_jsonrpc(proc)
        assert resp["id"] == 3, f"Wrong id: {resp}"
        assert "result" in resp, f"No result: {resp}"
        assert "content" in resp["result"], f"No content: {resp}"
        assert len(resp["result"]["content"]) > 0
        text = resp["result"]["content"][0]["text"]
        data = json.loads(text)
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✅ tools/call list_configs OK (got {len(data)} configs)")

        print("\n✅ Все E2E тесты прошли!")

    finally:
        proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main()
