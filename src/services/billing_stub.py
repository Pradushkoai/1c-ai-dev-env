"""
billing_stub.py — Заглушка для учёта usage по namespace (S1).

Не реализует реальную оплату. Только учёт вызовов MCP tools
по namespace для будущего billing integration.

Использование:
    from src.services.billing_stub import BillingStub

    billing = BillingStub()
    billing.record_usage(namespace="team_a", tool="search_1c_methods", calls=1)
    report = billing.get_usage_report(namespace="team_a")
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Запись об использовании tool."""

    namespace: str
    tool: str
    calls: int = 0
    last_used: str = ""


class BillingStub:
    """Заглушка billing для S1 SaaS-подготовки.

    Учитывает вызовы MCP tools по namespace.
    Не реализует реальную оплату — только data collection.

    Attributes:
        _usage: dict[namespace, dict[tool, UsageRecord]]
        _storage_path: Путь для сохранения usage данных (опционально)
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        """Инициализация billing stub.

        Args:
            storage_path: Путь для persistence usage данных (JSON).
                Если None — только in-memory.
        """
        self._usage: dict[str, dict[str, UsageRecord]] = defaultdict(dict)
        self._storage_path = storage_path

        if storage_path and storage_path.exists():
            self._load_from_file()

    def record_usage(
        self,
        namespace: str | None = None,
        tool: str = "",
        calls: int = 1,
    ) -> None:
        """Записать использование tool.

        Args:
            namespace: Namespace команды (default: из env MCP_NAMESPACE или "default").
            tool: Имя MCP tool.
            calls: Количество вызовов (default: 1).
        """
        if namespace is None:
            namespace = os.environ.get("MCP_NAMESPACE", "default")

        if tool not in self._usage[namespace]:
            self._usage[namespace][tool] = UsageRecord(namespace=namespace, tool=tool, calls=0)

        self._usage[namespace][tool].calls += calls
        self._usage[namespace][tool].last_used = datetime.now().isoformat()

    def get_usage_report(self, namespace: str | None = None) -> dict[str, Any]:
        """Получить отчёт об использовании.

        Args:
            namespace: Namespace (если None — все namespaces).

        Returns:
            {namespace, total_calls, tools: {tool: {calls, last_used}}}
        """
        if namespace is None:
            namespace = os.environ.get("MCP_NAMESPACE", "default")

        ns_usage = self._usage.get(namespace, {})
        total = sum(r.calls for r in ns_usage.values())

        return {
            "namespace": namespace,
            "total_calls": total,
            "tools": {tool: {"calls": rec.calls, "last_used": rec.last_used} for tool, rec in ns_usage.items()},
        }

    def get_all_reports(self) -> list[dict[str, Any]]:
        """Получить отчёты по всем namespaces.

        Returns:
            Список отчётов по каждому namespace.
        """
        return [self.get_usage_report(ns) for ns in self._usage]

    def reset(self, namespace: str | None = None) -> None:
        """Сбросить usage (для тестов).

        Args:
            namespace: Namespace для сброса (если None — все).
        """
        if namespace is None:
            self._usage.clear()
        else:
            self._usage.pop(namespace, None)

    def save(self) -> None:
        """Сохранить usage данные в файл (если storage_path задан)."""
        if not self._storage_path:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        for ns, tools in self._usage.items():
            data[ns] = {tool: {"calls": rec.calls, "last_used": rec.last_used} for tool, rec in tools.items()}

        self._storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_from_file(self) -> None:
        """Загрузить usage данные из файла."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            for ns, tools in data.items():
                for tool, info in tools.items():
                    self._usage[ns][tool] = UsageRecord(
                        namespace=ns,
                        tool=tool,
                        calls=info.get("calls", 0),
                        last_used=info.get("last_used", ""),
                    )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load billing data: %s", e)
