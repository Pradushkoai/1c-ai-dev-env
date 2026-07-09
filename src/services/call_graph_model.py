"""
call_graph_model.py — Модель графа вызовов.

Phase 3.4 of refactoring: выделение модели из call_graph.py.

Содержит:
- CallEdge — ребро графа (кто → кого вызывает)
- CallGraph — граф с индексами для быстрого поиска
- Алгоритмы: get_callers, get_callees, find_cycles, find_dead_code, get_stats
- Сериализация: to_dict, from_dict, save, load

Не содержит логику парсинга BSL — см. call_graph_parser.py.
Не содержит оркестрацию build_call_graph — см. call_graph_builder.py.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CallEdge:
    """Ребро графа вызовов: кто → кого вызывает."""

    caller_module: str
    caller_method: str
    callee_module: str  # модуль вызываемого метода ("" если локальный)
    callee_method: str
    line: int
    file: str


@dataclass
class CallGraph:
    """Граф вызовов методов конфигурации."""

    config_name: str
    edges: list[CallEdge] = field(default_factory=list)
    # Индексы для быстрого поиска
    _callers: dict[str, list[CallEdge]] = field(default_factory=dict)
    _callees: dict[str, list[CallEdge]] = field(default_factory=dict)

    def _key(self, module: str, method: str) -> str:
        return f"{module}.{method}"

    def _reindex(self) -> None:
        self._callers.clear()
        self._callees.clear()
        for edge in self.edges:
            callee_key = self._key(edge.callee_module, edge.callee_method)
            caller_key = self._key(edge.caller_module, edge.caller_method)
            self._callers.setdefault(callee_key, []).append(edge)
            self._callees.setdefault(caller_key, []).append(edge)

    def get_callers(self, module: str, method: str) -> list[dict]:
        """Кто вызывает данный метод?"""
        key = self._key(module, method)
        return [
            {
                "module": e.caller_module,
                "method": e.caller_method,
                "line": e.line,
                "file": e.file,
            }
            for e in self._callers.get(key, [])
        ]

    def get_callees(self, module: str, method: str) -> list[dict]:
        """Кого вызывает данный метод?"""
        key = self._key(module, method)
        return [
            {
                "module": e.callee_module,
                "method": e.callee_method,
                "line": e.line,
                "file": e.file,
            }
            for e in self._callees.get(key, [])
        ]

    def find_cycles(self) -> list[list[str]]:
        """Найти циклические зависимости (DFS)."""
        adj: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            caller = self._key(edge.caller_module, edge.caller_method)
            callee = self._key(edge.callee_module, edge.callee_method)
            if caller != callee:  # без self-calls
                adj[caller].add(callee)

        cycles = []
        visited: set[str] = set()
        stack: list[str] = []
        stack_set: set[str] = set()

        def dfs(node: str) -> None:
            if node in stack_set:
                idx = stack.index(node)
                cycle = stack[idx:] + [node]
                cycles.append(cycle)
                return
            if node in visited:
                return
            visited.add(node)
            stack.append(node)
            stack_set.add(node)
            for neighbor in adj.get(node, []):
                dfs(neighbor)
            stack.pop()
            stack_set.discard(node)

        for node in adj:
            if node not in visited:
                dfs(node)

        return cycles

    def find_dead_code(self, export_methods: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Найти экспортные методы, которые никто не вызывает (мёртвый код)."""
        called = set()
        for edge in self.edges:
            key = self._key(edge.callee_module, edge.callee_method)
            called.add(key)
        return [(mod, meth) for mod, meth in export_methods if self._key(mod, meth) not in called]

    def get_stats(self) -> dict[str, Any]:
        """Статистика графа."""
        nodes = set()
        for edge in self.edges:
            nodes.add(self._key(edge.caller_module, edge.caller_method))
            nodes.add(self._key(edge.callee_module, edge.callee_method))
        return {
            "total_edges": len(self.edges),
            "total_nodes": len(nodes),
            "unique_callers": len({self._key(e.caller_module, e.caller_method) for e in self.edges}),
            "unique_callees": len({self._key(e.callee_module, e.callee_method) for e in self.edges}),
        }

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict для JSON."""
        return {
            "config_name": self.config_name,
            "stats": self.get_stats(),
            "edges": [
                {
                    "caller_module": e.caller_module,
                    "caller_method": e.caller_method,
                    "callee_module": e.callee_module,
                    "callee_method": e.callee_method,
                    "line": e.line,
                    "file": e.file,
                }
                for e in self.edges
            ],
        }

    def save(self, path: Path) -> None:
        """Сохранить граф в JSON файл для последующей быстрой загрузки."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CallGraph:
        """Десериализация из dict (после json.load)."""
        graph = cls(config_name=data.get("config_name", ""))
        for e in data.get("edges", []):
            graph.edges.append(CallEdge(
                caller_module=e["caller_module"],
                caller_method=e["caller_method"],
                callee_module=e["callee_module"],
                callee_method=e["callee_method"],
                line=e.get("line", 0),
                file=e.get("file", ""),
            ))
        graph._reindex()
        return graph

    @classmethod
    def load(cls, path: Path) -> CallGraph | None:
        """Загрузить граф из JSON файла. Возвращает None если файл не существует."""
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to load call graph from %s: %s", path, e)
            return None
