"""
S8.9 (2026-07-05): Audit log — логирование всех MCP tool calls.

Каждый вызов MCP tool логируется с: timestamp, user, tool_name, args (sanitized),
result_status, duration. Persistence в runtime/audit-log.jsonl.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class AuditLogger:
    """S8.9: Audit logger для MCP tool calls."""

    def __init__(self, log_path: Path | None = None) -> None:
        if log_path is None:
            log_path = Path("runtime") / "audit-log.jsonl"
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result_status: str,
        duration_ms: float = 0,
        error: str = "",
    ) -> None:
        """Записать audit entry в JSONL файл.

        Args:
            tool_name: Имя MCP tool.
            args: Аргументы (санитизированные — без секретов).
            result_status: "success" | "error" | "blocked".
            duration_ms: Длительность в мс.
            error: Сообщение об ошибке (если есть).
        """
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": tool_name,
            "args_keys": list(args.keys()) if isinstance(args, dict) else [],
            "status": result_status,
            "duration_ms": round(duration_ms, 2),
            "error": error[:200] if error else "",
            "user": os.environ.get("USER", "unknown"),
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Прочитать последние N записей.

        Args:
            count: Количество записей.

        Returns:
            Список audit entries (новые последними).
        """
        if not self._log_path.exists():
            return []
        lines = self._log_path.read_text(encoding="utf-8").strip().splitlines()
        recent = lines[-count:] if len(lines) > count else lines
        return [json.loads(line) for line in recent if line.strip()]

    def clear(self) -> None:
        """Очистить audit log."""
        self._log_path.write_text("", encoding="utf-8")
