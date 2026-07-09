#!/usr/bin/env python3
"""
generate_openapi.py — Генерация OpenAPI 3.0 спецификации для MCP tools.

Создаёт openapi.json из _get_tools_description() в src/mcp_server.py.
Каждый MCP tool становится endpoint в OpenAPI spec.

Использование:
    python3 scripts/generate_openapi.py [output_path]

По умолчанию: docs/mcp-openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Добавляем repo root в path
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.mcp_server import _get_tools_description


def _read_pyproject_version() -> str:
    """F2.1: Прочитать версию из pyproject.toml (без зависимости tomli для Python 3.10+)."""
    pyproject_path = _REPO_ROOT / "pyproject.toml"
    try:
        content = pyproject_path.read_text(encoding="utf-8")
        # Простой парсинг: ищем version = "X.Y.Z" в [project] секции
        import re

        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "0.0.0"


def tool_to_openapi(tool: dict) -> dict:
    """Конвертировать MCP tool описание в OpenAPI endpoint."""
    name = tool["name"]
    description = tool.get("description", "")
    required_params = tool.get("required_params", [])
    optional_params = tool.get("optional_params", [])

    # Строим schema для request body
    properties = {}
    required = []

    for param in required_params:
        properties[param] = {
            "type": "string",
            "description": f"Required parameter: {param}",
        }
        required.append(param)

    for param in optional_params:
        properties[param] = {
            "type": "string",
            "description": f"Optional parameter: {param}",
        }

    # OpenAPI endpoint
    return {
        "summary": name,
        "description": description,
        "operationId": name,
        "tags": ["MCP Tools"],
        "requestBody": {
            "required": bool(required),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    }
                }
            },
        },
        "responses": {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {"type": "object"},
                    }
                },
            },
            "400": {
                "description": "Bad request — missing required parameters",
            },
            "500": {
                "description": "Internal server error",
            },
        },
    }


def generate_openapi() -> dict:
    """Сгенерировать OpenAPI 3.0 spec из MCP tools."""
    tools = _get_tools_description()

    paths = {}
    for tool in tools:
        name = tool["name"]
        # Каждый tool — POST endpoint
        paths[f"/tools/{name}"] = {
            "post": tool_to_openapi(tool),
        }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "1C AI Dev Environment — MCP Tools API",
            "description": (
                "MCP (Model Context Protocol) tools for 1C development.\n\n"
                "Каждый endpoint соответствует MCP tool. "
                "Параметры передаются в JSON body."
            ),
            # F2.1 (2026-07-09): версия читается из pyproject.toml динамически.
            # Ранее была захардкожена 6.0.0 — рассинхрон с pyproject.toml 7.0.0.
            "version": _read_pyproject_version(),
            "contact": {
                "name": "Pradushkoai",
                "url": "https://github.com/Pradushkoai/1c-ai-dev-env",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        },
        "servers": [
            {
                "url": "stdio://1c-ai-mcp",
                "description": "MCP server (stdio transport)",
            }
        ],
        "paths": paths,
        "tags": [
            {
                "name": "MCP Tools",
                "description": "All MCP tools for 1C AI Dev Environment",
            }
        ],
    }


def main() -> int:
    output_path = sys.argv[1] if len(sys.argv) > 1 else "docs/mcp-openapi.json"
    output = Path(output_path)

    spec = generate_openapi()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    tool_count = len(spec["paths"])
    print(f"✅ OpenAPI spec generated: {output}")
    print(f"   Tools: {tool_count}")
    print(f"   Size: {output.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
