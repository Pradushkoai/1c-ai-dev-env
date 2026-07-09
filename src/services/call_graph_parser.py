"""
call_graph_parser.py — Парсеры BSL для построения графа вызовов.

Phase 3.4 of refactoring: выделение парсеров из call_graph.py.

Содержит:
- Константы: BSL_KEYWORDS, STANDARD_OBJECTS, regex-паттерны
- Helper functions: _get_module_name_from_path, _find_current_procedure, _strip_comments
- _parse_bsl_file_with_tree_sitter — AST-based извлечение рёбер (P1-A-Integration)
- _parse_bsl_file_with_regex — regex fallback

Не содержит модель CallGraph/CallEdge — см. call_graph_model.py.
Не содержит оркестрацию build_call_graph — см. call_graph_builder.py.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .call_graph_model import CallEdge
from .path_manager import PathManager

logger = logging.getLogger(__name__)

# P1-A-Integration: проверяем доступность tree-sitter-bsl
try:
    from .bsl_tree_sitter import is_available as _ts_is_available, extract_symbols as _ts_extract_symbols
    _TREE_SITTER_AVAILABLE = _ts_is_available()
except ImportError:
    _TREE_SITTER_AVAILABLE = False


# ============================================================================
# REGEX ПАТТЕРНЫ
# ============================================================================

# Паттерн вызова: Модуль.Метод( — где Модуль — кириллица/латиница, Метод — кириллица/латиница
CROSS_MODULE_CALL_PATTERN = re.compile(r"\b([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\.\s*([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(")

# Паттерн локального вызова: Метод( — внутри того же модуля
LOCAL_CALL_PATTERN = re.compile(r"^\t*([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(")

BSL_KEYWORDS = {
    "Если", "Иначе", "ИначеЕсли", "КонецЕсли",
    "Для", "Пока", "Цикл", "КонецЦикла",
    "Процедура", "КонецПроцедуры",
    "Функция", "КонецФункции",
    "Возврат", "Прервать", "Продолжить",
    "Попытка", "Исключение", "КонецПопытки",
    "Перем", "Новый",
    "И", "ИЛИ", "НЕ", "Тогда",
    "Экспорт", "Знач",
    "Неопределено", "Истина", "Ложь", "Сред",
}

STANDARD_OBJECTS = {
    "ЭтотОбъект", "Объект", "Форма", "Элементы", "ЭтаФорма",
    "Справочники", "Документы", "Регистры", "Константы", "Метаданные",
    "Параметры", "ПараметрыСеанса", "Запрос", "Результат", "РезультатЗапроса",
    "Выборка", "СтрокаТаблицы", "Элемент", "Колонка",
    "Структура", "Массив", "ТаблицаЗначений", "ДеревоЗначений",
    "Справочник", "Документ", "РегистрСведений", "РегистрНакопления",
    "РегистрБухгалтерии", "РегистрРасчета", "ПланСчетов", "ПланВидовХарактеристик",
    "ПланВидовРасчета", "ПланОбмена", "Перечисление", "БизнесПроцесс", "Задача",
    "ДоставляемыеУведомления", "СредстваМультимедиа", "ФоновыеЗадания",
    "ИнформацияОбИнтернетСоединении", "ЖурналРегистрации", "Пользователи",
    "ПользователиИнформационнойБазы", "ДвоичныеДанные", "ХранилищеЗначения",
    "ЧтениеJSON", "ЗаписьJSON", "ЧтениеXML", "ЗаписьXML",
    "HTTPСоединение", "HTTPЗапрос", "HTTPОтвет",
    "КомпоновщикНастроек", "ПроцессорВывода", "ТабличныйДокумент",
    "ТекстовыйДокумент", "ОписаниеОповещения", "ДиалогВыбораФайла",
    "ЗащищенноеСоединениеOpenSSL",
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _get_module_name_from_path(bsl_path: Path, configs_dir: Path) -> str:
    """Извлекает имя модуля из пути файла.

    /data/configs/obhod/CommonModules/ОбменДокументы/Ext/Module.bsl → ОбменДокументы
    /data/configs/obhod/Ext/ManagedApplicationModule.bsl → ManagedApplicationModule
    /data/configs/obhod/CommonForms/ФормаАвторизации/Ext/Form/Module.bsl → ФормаАвторизации
    """
    rel = bsl_path.relative_to(configs_dir)
    parts = rel.parts

    if len(parts) >= 2:
        if parts[0] == "CommonModules":
            return parts[1]
        if parts[0] == "Ext":
            return Path(parts[-1]).stem
        if parts[0] == "CommonForms" and len(parts) >= 3:
            return parts[1]
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


# ============================================================================
# ПАРСЕРЫ
# ============================================================================


def _parse_bsl_file_with_tree_sitter(
    bsl_path: Path,
    config_dir: Path,
    mod_name: str,
    module_names: set[str],
    export_methods: set[str],
) -> list[CallEdge]:
    """P1-A-Integration: извлекает рёбра графа вызовов через AST tree-sitter-bsl.

    Точнее regex-подхода: не путает вызовы в строках и комментариях с реальными,
    корректно определяет границы процедур/функций (включая вложенные if/for/while).
    """
    if not _TREE_SITTER_AVAILABLE:
        return []

    try:
        content = bsl_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return []

    try:
        symbols = _ts_extract_symbols(content)
    except Exception as e:
        logger.debug("tree-sitter parsing failed for %s: %s, falling back", bsl_path, e)
        return []

    edges: list[CallEdge] = []
    rel_path = str(bsl_path.relative_to(config_dir))
    symbol_names = {s.name for s in symbols}

    for symbol in symbols:
        caller_method = symbol.name

        for call_name in symbol.calls:
            # Локальный вызов: Метод() — внутри того же модуля
            if call_name != caller_method:
                if f"{mod_name}.{call_name}" in export_methods or call_name in symbol_names:
                    edges.append(CallEdge(
                        caller_module=mod_name,
                        caller_method=caller_method,
                        callee_module=mod_name,
                        callee_method=call_name,
                        line=symbol.start_line,
                        file=rel_path,
                    ))

    return edges


def _parse_bsl_file_with_regex(
    bsl_path: Path,
    config_dir: Path,
    mod_name: str,
    module_names: set[str],
    export_methods: set[str],
) -> list[CallEdge]:
    """Regex-based fallback для извлечения рёбер графа вызовов.

    Используется когда tree-sitter-bsl не установлен.
    Поведение идентично версии до P1-A-Integration.
    """
    try:
        content = bsl_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return []

    lines = content.split("\n")
    edges: list[CallEdge] = []
    rel_path = str(bsl_path.relative_to(config_dir))

    for i, raw_line in enumerate(lines):
        line = _strip_comments(raw_line)
        if not line.strip():
            continue

        current_proc = _find_current_procedure(lines, i)

        # 1. Кросс-модульные вызовы: Модуль.Метод(
        for m in CROSS_MODULE_CALL_PATTERN.finditer(line):
            obj_name = m.group(1)
            method_name = m.group(2)

            if obj_name in STANDARD_OBJECTS:
                continue

            if obj_name in module_names:
                edges.append(CallEdge(
                    caller_module=mod_name,
                    caller_method=current_proc,
                    callee_module=obj_name,
                    callee_method=method_name,
                    line=i + 1,
                    file=rel_path,
                ))

        # 2. Локальные вызовы: Метод( — внутри того же модуля
        stripped = line.strip()
        local_m = re.match(r"([А-Яа-яЁё][А-Яа-яЁё\w]*)\s*\(", stripped)
        if local_m:
            method_name = local_m.group(1)
            if method_name not in BSL_KEYWORDS and method_name != current_proc:
                if f"{mod_name}.{method_name}" in export_methods:
                    edges.append(CallEdge(
                        caller_module=mod_name,
                        caller_method=current_proc,
                        callee_module=mod_name,
                        callee_method=method_name,
                        line=i + 1,
                        file=rel_path,
                    ))

    return edges
