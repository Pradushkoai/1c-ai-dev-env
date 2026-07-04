"""
ПРАВИЛА — СТИЛЬ КОДА

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py (god-файл 1685 LOC).
Логика без изменений — только перенос.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ._common import Violation

# ============================================================================
# ПРАВИЛА — СТИЛЬ КОДА
# ============================================================================

# --- Регулярки ---

# BSL-конструкции для детекции закомментированного кода
COMMENTED_CODE_PATTERN = re.compile(
    r"^\s*//\s*"
    r"(Если|Иначе|ИначеЕсли|КонецЕсли|Для|Пока|Цикл|КонецЦикла|"
    r"Процедура|КонецПроцедуры|Функция|КонецФункции|"
    r"Возврат|Прервать|Продолжить|Попытка|Исключение|КонецПопытки|"
    r"Перем|Область|КонецОбласти|"
    r"Новый\s|Сообщить\(|Выполнить\(|ЗаписьЖурналаРегистрации\()",
    re.IGNORECASE,
)

# TODO без номера задачи
TODO_PATTERN = re.compile(r"//\s*(TODO|FIXME|HACK|MRG|XXX)\b\s*:?\s*(?!.*№\s*\d)", re.IGNORECASE)

# Авторские пометки: "// Фамилия:" (русское имя с большой буквы + двоеточие)
# Исключаем служебные слова (Область, КонецОбласти, TODO, FIXME и т.д.)
_AUTHOR_EXCLUDE = {
    "область",
    "конецобласти",
    "todo",
    "fixme",
    "hack",
    "mrg",
    "xxx",
    "параметры",
    "возвращаемое",
    "пример",
    "см",
    "например",
}
AUTHOR_PATTERN = re.compile(r"//\s*([А-ЯЁ][а-яё]{2,20})\s*:")

# Hungarian notation: префиксы типа (м, стр, цел, соотв) перед CamelCase именем.
# Важно: префикс должен быть отдельным словом (boundary), не частью другого слова.
# Поэтому 'Справочники' НЕ детектируется (нет boundary перед 'с').
HUNGARIAN_PREFIXES = r"(?:м|стр|цел|буле|соотв|мас|тз|сп|массив|структура|таблица)"
HUNGARIAN_PATTERN = re.compile(
    r"\bПерем\s+"
    r"(" + HUNGARIAN_PREFIXES + r")"
    r"([А-ЯЁ][а-яё]+)",  # CamelCase: префикс + заглавная буква
    re.IGNORECASE,
)

# Имя переменной < 2 символов (кроме i, j, k, n — счётчики циклов)
SHORT_VAR_PATTERN = re.compile(r"\b(Перем|Для\s+каждого|Для)\s+([A-Za-zА-Яа-яёЁ])\b(?!.*счётчик)", re.IGNORECASE)
COUNTER_NAMES = {"i", "j", "k", "n", "m", "ц", "сч"}

# Переменные, начинающиеся с подчёркивания
UNDERSCORE_VAR_PATTERN = re.compile(
    r"\b(Перем|Для\s+каждого|Для)\s+(_[A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ0-9_]*)\b", re.IGNORECASE
)


# --- Символы ---

NON_BREAKING_SPACES = {
    "\u00a0": "NBSP (U+00A0)",
    "\u2007": "NNBSP (U+2007)",
    "\u2009": "THIN SPACE (U+2009)",
    "\u202f": "NNBSP (U+202F)",
}

WRONG_DASHES = {
    "\u2014": "EM DASH (—)",
    "\u2013": "EN DASH (–)",
    "\u2012": "FIGURE DASH (‒)",
    "\u2015": "HORIZONTAL BAR (―)",
}


def rule_no_non_breaking_spaces(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD-456:1.2 — неразрывные пробелы запрещены в коде."""
    for i, line in enumerate(lines, 1):
        for col, char in enumerate(line, 1):
            if char in NON_BREAKING_SPACES:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=col,
                    rule_id="no-non-breaking-space",
                    severity="error",
                    message=f"Неразрывный пробел {NON_BREAKING_SPACES[char]} — замените на обычный пробел (STD 456:1.2)",
                )


def rule_no_wrong_dashes(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD-456:1.2 — em/en-dash запрещены, используйте -."""
    for i, line in enumerate(lines, 1):
        for col, char in enumerate(line, 1):
            if char in WRONG_DASHES:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=col,
                    rule_id="no-wrong-dash",
                    severity="error",
                    message=f"Тире {WRONG_DASHES[char]} — замените на дефис '-' (STD 456:1.2)",
                )


def rule_no_yo_in_code(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:1.1 — буква 'ё' запрещена в коде (кроме строковых литералов)."""
    for i, line in enumerate(lines, 1):
        # Убираем строковые литералы (простая эвристика)
        code_only = re.sub(r'"[^"]*"', "", line)
        for col, char in enumerate(code_only, 1):
            if char in ("ё", "Ё"):
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=col,
                    rule_id="no-yo-in-code",
                    severity="warning",
                    message=f"Буква '{char}' в коде — замените на 'е'/'Е' (STD 456:1.1)",
                )


def rule_no_commented_code(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:3 — закомментированный код запрещён.

    Отличие docstring от закомментированного кода:
    - Docstring: '// Текст' (после // есть пробел) — описывает API
    - Закомментированный код: '//Если ...' (после // НЕТ пробела) — отладочный код

    Дополнительно: если строка с паттерном (// Если/Для/...) находится внутри
    блока из 3+ подряд идущих // с пробелом — это docstring, не flagged.
    """
    for i, line in enumerate(lines, 1):
        match = COMMENTED_CODE_PATTERN.search(line)
        if not match:
            continue

        # Проверяем: есть ли пробел после // (то есть это docstring-стиль)
        # COMMENTED_CODE_PATTERN = r'^\s*//\s*(Если|...)'
        # Паттерн уже требует \s* после //, значит матчит только docstring-стиль.
        # Но реальный закомментированный код может быть как '//Если' (без пробела),
        # так и '// Если' (с пробелом, если код скопирован из редактора).

        # Эвристика: смотрим, является ли строка частью docstring-блока
        # (3+ подряд // с пробелом). Если да — это документация.
        idx = i - 1  # 0-indexed
        if _is_in_docstring_block(lines, idx):
            continue

        yield Violation(
            file=str(file_path),
            line=i,
            col=1,
            rule_id="no-commented-code",
            severity="warning",
            message="Закомментированный код — удалите после отладки (STD 456:3)",
        )


def _is_in_docstring_block(lines: list[str], idx: int) -> bool:
    """Проверяет, находится ли строка idx внутри docstring-блока.

    Docstring-блок — 3+ подряд идущих строк, начинающихся с '// ' (с пробелом).
    Одиночные // или //word (без пробела) — НЕ docstring.
    """
    # Проверяем, что строка сама начинается с '// ' (с пробелом)
    line = lines[idx].strip() if idx < len(lines) else ""
    if not line.startswith("// "):
        return False

    # Считаем длину блока // (с пробелом) вокруг этой строки
    count_back = 0
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("// "):
        count_back += 1
        j -= 1

    count_forward = 0
    j = idx + 1
    while j < len(lines) and lines[j].strip().startswith("// "):
        count_forward += 1
        j += 1

    # Всего строк в блоке включая текущую
    total = count_back + 1 + count_forward
    return total >= 3


def rule_todo_with_task(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:3 — TODO без номера задачи."""
    for i, line in enumerate(lines, 1):
        if TODO_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="todo-with-task",
                severity="warning",
                message="TODO/FIXME без номера задачи — добавьте '№ N' (STD 456:3)",
            )


def rule_no_author_marks(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:3 — авторские пометки '// Иванов:' запрещены."""
    for i, line in enumerate(lines, 1):
        for match in AUTHOR_PATTERN.finditer(line):
            name = match.group(1)
            # Исключаем служебные слова (с маленькой буквой сравниваем)
            if name.lower() in _AUTHOR_EXCLUDE:
                continue
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-author-marks",
                severity="warning",
                message=f"Авторская пометка '{name}:' — удалите (STD 456:3)",
            )


def rule_no_hungarian_notation(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 454:2 — Hungarian notation запрещена (м, с, стр и т.д.)."""
    for i, line in enumerate(lines, 1):
        for match in HUNGARIAN_PATTERN.finditer(line):
            prefix = match.group(1)
            name = match.group(2)
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-hungarian-notation",
                severity="warning",
                message=f"Hungarian notation '{prefix}{name}' — имя от терминов предметной области (STD 454:2)",
            )


def rule_no_short_variables(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 454:4 — имена переменных < 2 символов (кроме счётчиков циклов)."""
    for i, line in enumerate(lines, 1):
        # Только объявления (Перем) и параметры цикла
        for match in re.finditer(r"\bПерем\s+([A-Za-zА-Яа-яёЁ])\s*;", line):
            name = match.group(1)
            if name.lower() not in COUNTER_NAMES:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=match.start() + 1,
                    rule_id="no-short-variables",
                    severity="warning",
                    message=f"Имя переменной '{name}' < 2 символов — используйте описательное имя (STD 454:4)",
                )


def rule_no_underscore_vars(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 454:3 — имена переменных не должны начинаться с _."""
    for i, line in enumerate(lines, 1):
        for match in UNDERSCORE_VAR_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-underscore-vars",
                severity="error",
                message=f"Имя переменной '{match.group(2)}' начинается с _ — запрещено (STD 454:3)",
            )


def rule_line_too_long(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456 — длина строки не более 120 символов."""
    MAX_LEN = 120
    for i, line in enumerate(lines, 1):
        # Учитываем только значимые символы (без trailing whitespace)
        stripped = line.rstrip("\n\r")
        if len(stripped) > MAX_LEN:
            yield Violation(
                file=str(file_path),
                line=i,
                col=MAX_LEN + 1,
                rule_id="line-too-long",
                severity="warning",
                message=f"Строка {len(stripped)} символов > {MAX_LEN} — разбейте или перенесите (STD 456)",
            )


# Список правил в этом модуле
RULES = [
    rule_no_non_breaking_spaces,
    rule_no_wrong_dashes,
    rule_no_yo_in_code,
    rule_no_commented_code,
    rule_todo_with_task,
    rule_no_author_marks,
    rule_no_hungarian_notation,
    rule_no_short_variables,
    rule_no_underscore_vars,
    rule_line_too_long,
]
