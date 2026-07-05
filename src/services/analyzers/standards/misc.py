"""
ПРАВИЛА — РАЗНОЕ

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py (god-файл 1685 LOC).
Логика без изменений — только перенос.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ._common import Violation

# ============================================================================
# ПРАВИЛА — РАЗНОЕ
# ============================================================================

# ============================================================================
# ПРАВИЛА v3.5.0 — из ИТС, Инфостарт, ai_rules_1c, 1c-standards
# ============================================================================

# Отказ = Ложь в обработчиках событий (STD 686)
OTKAZ_LOZH_PATTERN = re.compile(r"\bОтказ\s*=\s*Ложь\b", re.IGNORECASE)

# Глобальные переменные в модулях (STD 456)
GLOBAL_VAR_PATTERN = re.compile(r"\bПерем\s+\w+(?:\s*,\s*\w+)*\s*;", re.IGNORECASE)

# Имена из глобального контекста как переменные
GLOBAL_CONTEXT_NAMES = {
    "Документы",
    "Справочники",
    "Регистры",
    "Метаданные",
    "Константы",
    "Пользователи",
    "Сеансы",
    "ПараметрыСеанса",
    "Обработки",
    "Отчеты",
    "Перечисления",
    "ПланыСчетов",
    "ПланыОбмена",
    "ПланыВидовРасчета",
    "ПланыВидовХарактеристик",
    "БизнесПроцессы",
    "Задачи",
}
GLOBAL_CONTEXT_VAR_PATTERN = re.compile(r"\bПерем\s+(" + "|".join(GLOBAL_CONTEXT_NAMES) + r")\b", re.IGNORECASE)

# Псевдо-области через комментарии (//--- Область ---)
PSEUDO_REGION_PATTERN = re.compile(r"//\s*[-=]+\s*(Область|Region|---)", re.IGNORECASE)

# Subquery in SELECT (вложенный запрос в SELECT)
SUBQUERY_IN_SELECT_PATTERN = re.compile(r"ВЫБРАТЬ\s+.*?\(ВЫБРАТЬ", re.IGNORECASE | re.DOTALL)

# Virtual Table Filter in WHERE (вместо параметров ВТ)
VT_IN_WHERE_PATTERN = re.compile(
    r"\.\s*(Изменения|СрезПоследних|Остатки|Обороты|Движения)\s*\."
    r".*?ГДЕ\s+",
    re.IGNORECASE | re.DOTALL,
)

# Missing ПЕРВЫЕ N в запросах (для выборок с ограничением)
# Сложно определить автоматически — пропускаем

# &НаСервере вместо &НаСервереБезКонтекста (когда контекст не нужен)
# Сложно определить автоматически — нужна семантика

# Deep Nesting (>5 уровней вложенности)
DEEP_NESTING_PATTERN = re.compile(r"(\s*(Если|Для|Пока|Процедура|Функция)\s)", re.IGNORECASE)

# Пустой() вместо выгрузки для проверки (STD 438)
VYGRUZKA_EMPTY_CHECK_PATTERN = re.compile(
    r"\.Выгрузить\(\).*\.Количество\(\)\s*=\s*0|\.Выгрузить\(\).*Пустая", re.IGNORECASE
)

# ПОДОБНО с % в начале (плохо для индексов)
PODOBNO_PERCENT_START_PATTERN = re.compile(r'ПОДОБНО\s+["\']%[^"\']*["\']', re.IGNORECASE)

# Диалоги внутри транзакции ( locks-and-transactions )
DIALOG_IN_TRANSACTION_PATTERN = re.compile(
    r"(НачатьТранзакцию|НачалоТранзакции).*?(ВопросАсинх|ПоказатьВопрос|ПоказатьЗначение|ПоказатьПредупреждение|НачатьПомещениеФайла)",
    re.IGNORECASE | re.DOTALL,
)

# ОтменитьТранзакцию без ВызватьИсключение
OTMENIT_WITHOUT_RAISE_PATTERN = re.compile(
    r"(ОтменитьТранзакцию\s*\(\s*\))(?!.*ВызватьИсключение)", re.IGNORECASE | re.DOTALL
)

# Отступы пробелами вместо табуляции (STD 456)
SPACE_INDENT_PATTERN = re.compile(r"^( +)\S")

# Один оператор в строке (STD 456: два и более ; на одной строке)
MULTI_SEMICOLON_PATTERN = re.compile(r";[^;\n]*;")

# Найти вместо НайтиСтроки для поиска по колонке (Инфостарт)
NAITI_PATTERN = re.compile(r'\.Найти\(\s*[^,]+,\s*["\']', re.IGNORECASE)

# Пробел после // (STD 456, ai_rules_1c)
NO_SPACE_AFTER_COMMENT_PATTERN = re.compile(r"//[^\s/]")


def rule_no_otkaz_lozh(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Отказ = Ложь в обработчиках событий — запрещено (STD 686)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if OTKAZ_LOZH_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-otkaz-lozh",
                severity="error",
                message="Отказ = Ложь в обработчике — не сбрасывайте Отказ (STD 686)",
            )


def rule_no_global_context_vars(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Имена из глобального контекста как переменные — запрещено (ai_rules_1c)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        for match in GLOBAL_CONTEXT_VAR_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-global-context-vars",
                severity="warning",
                message=f"Имя '{match.group(1)}' из глобального контекста — не используйте как переменную (ai_rules_1c)",
            )


def rule_no_pseudo_regions(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Псевдо-области через комментарии — запрещено (ai_rules_1c)."""
    for i, line in enumerate(lines, 1):
        if PSEUDO_REGION_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-pseudo-regions",
                severity="warning",
                message="Псевдо-область через комментарий — используйте #Область (ai_rules_1c)",
            )


def rule_no_subquery_in_select(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Вложенный подзапрос в SELECT — антипаттерн (ai_rules_1c)."""
    full_text = "\n".join(lines)
    for match in SUBQUERY_IN_SELECT_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-subquery-in-select",
            severity="warning",
            message="Вложенный подзапрос в SELECT — N+1 query (ai_rules_1c antipattern)",
        )


def rule_no_vt_filter_in_where(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Фильтрация виртуальной таблицы через ГДЕ вместо параметров (ai_rules_1c)."""
    full_text = "\n".join(lines)
    for match in VT_IN_WHERE_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-vt-filter-in-where",
            severity="warning",
            message="Фильтрация ВТ через ГДЕ — используйте параметры ВТ (ai_rules_1c antipattern)",
        )


def rule_no_podobno_percent_start(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПОДОБНО с % в начале — плохо для индексов (STD 03)."""
    full_text = "\n".join(lines)
    in_query = False
    for i, line in enumerate(lines, 1):
        if "ВЫБРАТЬ" in line.upper() or "Запрос.Текст" in line:
            in_query = True
        if in_query and PODOBNO_PERCENT_START_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-podobno-percent-start",
                severity="warning",
                message="ПОДОБНО с % в начале — не использует индекс (STD 03)",
            )
        if '";' in line:
            in_query = False


def rule_no_dialog_in_transaction(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Диалоги внутри транзакции — запрещено (locks-and-transactions)."""
    full_text = "\n".join(lines)
    for match in DIALOG_IN_TRANSACTION_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-dialog-in-transaction",
            severity="error",
            message="Диалог внутри транзакции — блокирует другие сессии (locks-and-transactions)",
        )


def rule_no_otmenit_without_raise(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ОтменитьТранзакцию без ВызватьИсключение — ошибка глушится (locks-and-transactions)."""
    full_text = "\n".join(lines)
    for match in re.finditer(r"ОтменитьТранзакцию\s*\(\s*\)", full_text, re.IGNORECASE):
        # Проверяем — есть ли ВызватьИсключение в следующих 3 строках
        after = full_text[match.end() : match.end() + 500]
        if "ВызватьИсключение" not in after[:300]:
            line_num = full_text[: match.start()].count("\n") + 1
            yield Violation(
                file=str(file_path),
                line=line_num,
                col=1,
                rule_id="no-otmenit-without-raise",
                severity="error",
                message="ОтменитьТранзакцию без ВызватьИсключение — ошибка глушится (locks-and-transactions)",
            )


def rule_no_space_indent(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Отступы пробелами вместо табуляции (STD 456)."""
    for i, line in enumerate(lines, 1):
        # Пропускаем пустые строки
        if not line.strip():
            continue
        # Проверяем — есть ли пробелы в начале строки
        match = SPACE_INDENT_PATTERN.match(line)
        if match:
            # Проверяем что это не табуляция + пробел
            indent = match.group(1)
            # Если отступ состоит только из пробелов (нет табов)
            if "\t" not in indent and len(indent) >= 2:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="no-space-indent",
                    severity="warning",
                    message="Отступ пробелами — используйте табуляцию (STD 456)",
                )


def rule_no_multi_semicolon(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Несколько операторов в одной строке (STD 456)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if MULTI_SEMICOLON_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-multi-semicolon",
                severity="warning",
                message="Несколько операторов в строке — один оператор на строку (STD 456)",
            )


def rule_no_naiti_for_column(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Найти вместо НайтиСтроки для поиска по колонке (Инфостарт)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if NAITI_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-naiti-for-column",
                severity="warning",
                message="Найти(значение, 'Колонка') — используйте НайтиСтроки для поиска (Инфостарт)",
            )


def rule_no_space_after_comment(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Пробел после // обязателен (STD 456, ai_rules_1c)."""
    for i, line in enumerate(lines, 1):
        # Ищем // без пробела после (но не /// и не //http)
        for match in NO_SPACE_AFTER_COMMENT_PATTERN.finditer(line):
            char_after = line[match.end() : match.end() + 1]
            # Пропускаем если это URL (//http)
            if char_after == "/" or char_after == ":":
                continue
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-space-after-comment",
                severity="warning",
                message="Пробел после // обязателен (STD 456, ai_rules_1c)",
            )


def rule_no_vygruzka_empty_check(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Выгрузка для проверки пустоты — использовать Пустой() (STD 438)."""
    full_text = "\n".join(lines)
    for match in VYGRUZKA_EMPTY_CHECK_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-vygruzka-empty-check",
            severity="warning",
            message="Выгрузка для проверки пустоты — используйте Пустой() (STD 438)",
        )


def rule_no_deep_nesting(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Глубокая вложенность > 5 уровней (ai_rules_1c antipattern)."""
    depth = 0
    max_depth = 5
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Увеличиваем вложенность
        if re.search(r"\b(Если|Для|Пока)\s", stripped, re.IGNORECASE) and ("Тогда" in stripped or "Цикл" in stripped):
            depth += 1
            if depth > max_depth:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="no-deep-nesting",
                    severity="warning",
                    message=f"Вложенность {depth} > {max_depth} — вынесите во вспомогательную функцию (ai_rules_1c)",
                )
        # Уменьшаем вложенность
        if re.search(r"\b(КонецЕсли|КонецЦикла)\b", stripped, re.IGNORECASE):
            depth = max(0, depth - 1)


# Список правил в этом модуле
RULES = [
    rule_no_otkaz_lozh,
    rule_no_global_context_vars,
    rule_no_pseudo_regions,
    rule_no_subquery_in_select,
    rule_no_vt_filter_in_where,
    rule_no_podobno_percent_start,
    rule_no_dialog_in_transaction,
    rule_no_otmenit_without_raise,
    rule_no_space_indent,
    rule_no_multi_semicolon,
    rule_no_naiti_for_column,
    rule_no_space_after_comment,
    rule_no_vygruzka_empty_check,
    rule_no_deep_nesting,
]
