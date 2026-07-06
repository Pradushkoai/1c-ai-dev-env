#!/usr/bin/env python3
"""
check_mcp_count.py — Проверка консистентности кол-ва MCP-инструментов.

Скрипт сверяет фактическое кол-во MCP-инструментов (из src/mcp_server.py)
с заявленным в manifest.json, README.md и docs/.

Использование:
    python3 scripts/check_mcp_count.py

Exit codes:
    0 — всё консистентно
    1 — найдены расхождения
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Ensure repo root is in sys.path so 'src' module is importable
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def get_actual_tools_count() -> int:
    """Получить фактическое кол-во tools из list_tools handler."""
    import asyncio
    from unittest.mock import patch

    with patch("src.project.Project"):
        from mcp.types import ListToolsRequest

        from src.mcp_server import create_mcp_server

        server = create_mcp_server()
        handler = next(
            (h for req_type, h in server.request_handlers.items() if req_type == ListToolsRequest),
            None,
        )
        if handler is None:
            return 0
        result = asyncio.run(handler(ListToolsRequest(method="tools/list")))
        return len(result.root.tools)


def get_static_tools_count() -> int:
    """Получить кол-во tools из _get_tools_description (статическое описание)."""
    from src.mcp_server import _get_tools_description

    return len(_get_tools_description())


def main() -> int:
    repo_root = Path(__file__).parent.parent
    errors: list[str] = []

    actual_count = get_actual_tools_count()
    static_count = get_static_tools_count()

    print(f"Фактическое кол-во MCP tools (list_tools handler): {actual_count}")
    print(f"Статическое описание (_get_tools_description):     {static_count}")
    print()

    # Проверка manifest.json
    manifest_path = repo_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_count = manifest.get("mcp_tools_count")
    if manifest_count != actual_count:
        errors.append(f"manifest.json: mcp_tools_count={manifest_count}, но фактическое кол-во={actual_count}")

    # Проверка README.md (badge + текст)
    readme_path = repo_root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    # Badge: MCP%20tools-XX
    badge_match = re.search(r"MCP%20tools-(\d+)", readme)
    if badge_match:
        badge_count = int(badge_match.group(1))
        if badge_count != actual_count:
            errors.append(f"README.md: badge MCP tools={badge_count}, но фактическое кол-во={actual_count}")
    # Inline mentions: "XX MCP tools"
    inline_matches = re.findall(r"(\d+)\s+MCP\s+tools", readme, re.IGNORECASE)
    for m in inline_matches:
        if int(m) != actual_count:
            errors.append(f'README.md: inline "{m} MCP tools", но фактическое кол-во={actual_count}')

    # Проверка docs/MCP_INTEGRATION.md
    mcp_doc_path = repo_root / "docs" / "MCP_INTEGRATION.md"
    if mcp_doc_path.exists():
        mcp_doc = mcp_doc_path.read_text(encoding="utf-8")
        # Только не-исторические упоминания (без префикса версии vN.N.N)
        # Пропускаем строки с историей версий
        for line_num, line in enumerate(mcp_doc.split("\n"), 1):
            if re.search(r"v\d+\.\d+\.\d+", line):
                continue  # историческая запись
            matches = re.findall(r"(\d+)\s+tools", line)
            for m in matches:
                if int(m) != actual_count:
                    errors.append(
                        f'docs/MCP_INTEGRATION.md:{line_num}: "{m} tools", но фактическое кол-во={actual_count}'
                    )

    # Проверка docs/ARCHITECTURE.md
    arch_doc_path = repo_root / "docs" / "ARCHITECTURE.md"
    if arch_doc_path.exists():
        arch_doc = arch_doc_path.read_text(encoding="utf-8")
        matches = re.findall(r"MCP-сервер\s+\((\d+)\s+tools\)", arch_doc)
        for m in matches:
            if int(m) != actual_count:
                errors.append(f'docs/ARCHITECTURE.md: "MCP-сервер ({m} tools)", но фактическое кол-во={actual_count}')

    # Проверка AGENTS.md
    agents_path = repo_root / "AGENTS.md"
    if agents_path.exists():
        agents = agents_path.read_text(encoding="utf-8")
        matches = re.findall(r"(\d+)\s+tools", agents)
        for m in matches:
            if int(m) != actual_count:
                errors.append(f'AGENTS.md: "{m} tools", но фактическое кол-во={actual_count}')

    if errors:
        print("❌ Найдены расхождения:")
        for e in errors:
            print(f"   - {e}")
        return 1

    print(f"✅ Все документы консистентны: {actual_count} MCP tools")
    return 0


if __name__ == "__main__":
    sys.exit(main())
