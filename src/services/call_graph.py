"""
Граф вызовов методов конфигурации 1С.

Парсит .bsl файлы, находит вызовы Модуль.Метод() и Метод()
(внутри того же модуля), строит directed graph.

Пример:
    from src.services.call_graph import build_call_graph, get_callers, get_callees
    graph = build_call_graph("obhod", paths)           # построить граф
    callers = get_callers(graph, "ОбменДокументы", "ВыполнитьПолныйОбмен")
    callees = get_callees(graph, "ОбменДокументы", "ВыполнитьПолныйОбмен")
"""

from __future__ import annotations
from typing import Any

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .path_manager import PathManager


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
    _callers: dict[str, list[CallEdge]] = field(default_factory=dict)  # "модуль.метод" → кто вызывает
    _callees: dict[str, list[CallEdge]] = field(default_factory=dict)  # "модуль.метод" → кого вызывает

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
        # Строим adjacency list
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
                # Нашли цикл
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


# ============================================================================
# ПАРСЕР .bsl ФАЙЛОВ
# ============================================================================

# Паттерн вызова: Модуль.Метод( — где Модуль — кириллица/латиница, Метод — кириллица/латиница
# Не матчит: точка в числах (1.5), точка в запросах (Таблица.Поле),
# точка после ключевых слов (ЭтотОбъект.Метод — это локальный вызов)
CROSS_MODULE_CALL_PATTERN = re.compile(r"\b([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\.\s*([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(")

# Паттерн локального вызова: Метод( — внутри того же модуля
# Исключаем ключевые слова BSL
BSL_KEYWORDS = {
    "Если",
    "Иначе",
    "ИначеЕсли",
    "КонецЕсли",
    "Для",
    "Пока",
    "Цикл",
    "КонецЦикла",
    "Процедура",
    "КонецПроцедуры",
    "Функция",
    "КонецФункции",
    "Возврат",
    "Прервать",
    "Продолжить",
    "Попытка",
    "Исключение",
    "КонецПопытки",
    "Перем",
    "Новый",
    "И",
    "ИЛИ",
    "НЕ",
    "Тогда",
    "Экспорт",
    "Знач",
    "Неопределено",
    "Истина",
    "Ложь",
    "Сред",
}

LOCAL_CALL_PATTERN = re.compile(r"^\t*([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(")


def _get_module_name_from_path(bsl_path: Path, configs_dir: Path) -> str:
    """Извлекает имя модуля из пути файла.

    /data/configs/obhod/CommonModules/ОбменДокументы/Ext/Module.bsl → ОбменДокументы
    /data/configs/obhod/Ext/ManagedApplicationModule.bsl → ManagedApplicationModule
    /data/configs/obhod/CommonForms/ФормаАвторизации/Ext/Form/Module.bsl → ФормаАвторизации
    """
    rel = bsl_path.relative_to(configs_dir)
    parts = rel.parts

    if len(parts) >= 2:
        # CommonModules/ОбменДокументы/Ext/Module.bsl → ОбменДокументы
        if parts[0] == "CommonModules":
            return parts[1]
        # Ext/ManagedApplicationModule.bsl → ManagedApplicationModule
        if parts[0] == "Ext":
            return Path(parts[-1]).stem
        # CommonForms/ФормаАвторизации/Ext/Form/Module.bsl → ФормаАвторизации
        if parts[0] == "CommonForms" and len(parts) >= 3:
            return parts[1]
        # DataProcessors/.../Forms/Форма/Ext/Form/Module.bsl → последний Forms перед Ext
        # Сложный случай — возвращаем имя родительской папки перед Ext
        if "Ext" in parts:
            ext_idx = parts.index("Ext")
            if ext_idx > 0:
                return parts[ext_idx - 1]

    return bsl_path.stem


def _find_current_procedure(lines: list[str], line_idx: int) -> str:
    """Находит имя процедуры/функции, в которой находится строка line_idx."""
    for i in range(line_idx, -1, -1):
        line = lines[i].strip()
        m = re.match(r"(Процедура|Функция)\s+([А-Яа-яЁё\w]+)", line)
        if m:
            return m.group(2)
    return "<модуль>"


def _strip_comments(line: str) -> str:
    """Удаляет комментарий // из строки (не внутри строк)."""
    in_string = False
    i = 0
    while i < len(line) - 1:
        if line[i] == '"':
            in_string = not in_string
        elif not in_string and line[i] == "/" and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


# Список стандартных объектов/методов, которые не являются вызовами модулей
STANDARD_OBJECTS = {
    "ЭтотОбъект",
    "Объект",
    "Форма",
    "Элементы",
    "ЭтаФорма",
    "Справочники",
    "Документы",
    "Регистры",
    "Константы",
    "Метаданные",
    "Параметры",
    "ПараметрыСеанса",
    "Запрос",
    "Результат",
    "РезультатЗапроса",
    "Выборка",
    "СтрокаТаблицы",
    "Элемент",
    "Колонка",
    "Структура",
    "Массив",
    "ТаблицаЗначений",
    "ДеревоЗначений",
    "Справочник",
    "Документ",
    "РегистрСведений",
    "РегистрНакопления",
    "РегистрБухгалтерии",
    "РегистрРасчета",
    "ПланСчетов",
    "ПланВидовХарактеристик",
    "ПланВидовРасчета",
    "ПланОбмена",
    "Перечисление",
    "БизнесПроцесс",
    "Задача",
    "ДоставляемыеУведомления",
    "СредстваМультимедиа",
    "ФоновыеЗадания",
    "ИнформацияОбИнтернетСоединении",
    "ЖурналРегистрации",
    "Пользователи",
    "ПользователиИнформационнойБазы",
    "ДвоичныеДанные",
    "ХранилищеЗначения",
    "ЧтениеJSON",
    "ЗаписьJSON",
    "ЧтениеXML",
    "ЗаписьXML",
    "HTTPСоединение",
    "HTTPЗапрос",
    "HTTPОтвет",
    "КомпоновщикНастроек",
    "ПроцессорВывода",
    "ТабличныйДокумент",
    "ТекстовыйДокумент",
    "ОписаниеОповещения",
    "ДиалогВыбораФайла",
    "ЗащищенноеСоединениеOpenSSL",
}


def build_call_graph(config_name: str, paths: PathManager | None = None) -> CallGraph:
    """
    Построить граф вызовов для конфигурации.

    Парсит все .bsl файлы, находит:
    1. Кросс-модульные вызовы: ОбменДокументы.ВыполнитьПолныйОбмен()
    2. Локальные вызовы: ВыполнитьЗапрос() внутри того же модуля

    Args:
        config_name: Имя конфигурации (ut11, obhod, ...)
        paths: PathManager (если None — создаётся)

    Returns:
        CallGraph с рёбрами и индексами
    """
    if paths is None:
        paths = PathManager()

    config_dir = paths.config_path(config_name)
    graph = CallGraph(config_name=config_name)

    # Загружаем список экспортных методов из api-reference.json
    api_json = paths.config_api_reference_json(config_name)
    export_methods: set[str] = set()  # "ИмяМодуля.ИмяМетода"
    module_names: set[str] = set()
    if api_json.exists():
        with open(api_json, encoding="utf-8") as f:
            modules = json.load(f)
        for mod in modules:
            mod_name = mod.get("name", "")
            module_names.add(mod_name)
            for method in mod.get("methods", []):
                export_methods.add(f"{mod_name}.{method.get('name', '')}")

    # Парсим все .bsl файлы
    bsl_files = list(config_dir.rglob("*.bsl"))

    for bsl_path in bsl_files:
        mod_name = _get_module_name_from_path(bsl_path, config_dir)

        try:
            content = bsl_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue

        lines = content.split("\n")

        for i, raw_line in enumerate(lines):
            line = _strip_comments(raw_line)
            if not line.strip():
                continue

            current_proc = _find_current_procedure(lines, i)

            # 1. Кросс-модульные вызовы: Модуль.Метод(
            for m in CROSS_MODULE_CALL_PATTERN.finditer(line):
                obj_name = m.group(1)
                method_name = m.group(2)

                # Пропускаем стандартные объекты
                if obj_name in STANDARD_OBJECTS:
                    continue

                # Проверяем — является ли obj_name именем модуля конфигурации
                if obj_name in module_names:
                    edge = CallEdge(
                        caller_module=mod_name,
                        caller_method=current_proc,
                        callee_module=obj_name,
                        callee_method=method_name,
                        line=i + 1,
                        file=str(bsl_path.relative_to(config_dir)),
                    )
                    graph.edges.append(edge)

            # 2. Локальные вызовы: Метод( — внутри того же модуля
            # Ищем вызовы в начале строки (после табов)
            stripped = line.strip()
            local_m = re.match(r"([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(", stripped)
            if local_m:
                method_name = local_m.group(1)
                if method_name not in BSL_KEYWORDS and method_name != current_proc:  # noqa: SIM102
                    # Проверяем — есть ли такой метод в api-reference
                    if f"{mod_name}.{method_name}" in export_methods:
                        edge = CallEdge(
                            caller_module=mod_name,
                            caller_method=current_proc,
                            callee_module=mod_name,
                            callee_method=method_name,
                            line=i + 1,
                            file=str(bsl_path.relative_to(config_dir)),
                        )
                        graph.edges.append(edge)

    graph._reindex()
    return graph
