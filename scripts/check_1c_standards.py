#!/usr/bin/env python3
"""
Проверка .bsl файлов на соответствие стандартам разработки 1С.

Основано на:
- ITS standard 456 «Тексты модулей» (https://its.1c.ru/db/v8std#content:456:hdoc)
- ITS standard 454 «Правила образования имен переменных»
- ITS standard 455 «Структура модуля»
- ai_rules_1c/content/rules/anti-patterns.md

Правила, которые проверяет BSL Language Server (Typo, длина строк, отступы),
здесь не дублируются. Этот скрипт фокусируется на стилистических правилах,
которые BSL LS не покрывает или покрывает слабо.

Использование:
    python3 check_1c_standards.py <path>              # проверить файл/директорию
    python3 check_1c_standards.py <path> --format json # JSON вывод для CI
    python3 check_1c_standards.py <path> --severity error  # только errors

Exit codes:
    0 — нет violations уровня error
    1 — есть violations уровня error
    2 — ошибка использования
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator


# ============================================================================
# МОДЕЛИ
# ============================================================================

@dataclass
class Violation:
    """Одно нарушение стандарта 1С."""
    file: str
    line: int
    col: int
    rule_id: str
    severity: str  # error | warning
    message: str

    def format_text(self) -> str:
        """Текстовый формат (как ESLint)."""
        return (
            f"  {self.severity.upper():7} {self.rule_id:20} "
            f"{self.file}:{self.line}:{self.col}  {self.message}"
        )


# ============================================================================
# ПРАВИЛА
# ============================================================================
# Каждое правило — функция (lines: list[str], file_path: Path) -> Iterator[Violation]
# Имена правил начинаются с rule_, имя используется как rule_id.

# --- Регулярки ---

# BSL-конструкции для детекции закомментированного кода
COMMENTED_CODE_PATTERN = re.compile(
    r'^\s*//\s*'
    r'(Если|Иначе|ИначеЕсли|КонецЕсли|Для|Пока|Цикл|КонецЦикла|'
    r'Процедура|КонецПроцедуры|Функция|КонецФункции|'
    r'Возврат|Прервать|Продолжить|Попытка|Исключение|КонецПопытки|'
    r'Перем|Область|КонецОбласти|'
    r'Новый\s|Сообщить\(|Выполнить\(|ЗаписьЖурналаРегистрации\()',
    re.IGNORECASE,
)

# TODO без номера задачи
TODO_PATTERN = re.compile(r'//\s*(TODO|FIXME|HACK|MRG|XXX)\b\s*:?\s*(?!.*№\s*\d)', re.IGNORECASE)

# Авторские пометки: "// Фамилия:" (русское имя с большой буквы + двоеточие)
# Исключаем служебные слова (Область, КонецОбласти, TODO, FIXME и т.д.)
_AUTHOR_EXCLUDE = {
    "область", "конецобласти", "todo", "fixme", "hack", "mrg", "xxx",
    "параметры", "возвращаемое", "пример", "см", "например",
}
AUTHOR_PATTERN = re.compile(r'//\s*([А-ЯЁ][а-яё]{2,20})\s*:')

# Hungarian notation: префиксы типа (м, стр, цел, соотв) перед CamelCase именем.
# Важно: префикс должен быть отдельным словом (boundary), не частью другого слова.
# Поэтому 'Справочники' НЕ детектируется (нет boundary перед 'с').
HUNGARIAN_PREFIXES = r'(?:м|стр|цел|буле|соотв|мас|тз|сп|массив|структура|таблица)'
HUNGARIAN_PATTERN = re.compile(
    r'\bПерем\s+'
    r'(' + HUNGARIAN_PREFIXES + r')'
    r'([А-ЯЁ][а-яё]+)',  # CamelCase: префикс + заглавная буква
    re.IGNORECASE,
)

# Имя переменной < 2 символов (кроме i, j, k, n — счётчики циклов)
SHORT_VAR_PATTERN = re.compile(r'\b(Перем|Для\s+каждого|Для)\s+([A-Za-zА-Яа-яёЁ])\b(?!.*счётчик)', re.IGNORECASE)
COUNTER_NAMES = {"i", "j", "k", "n", "m", "ц", "сч"}

# Переменные, начинающиеся с подчёркивания
UNDERSCORE_VAR_PATTERN = re.compile(r'\b(Перем|Для\s+каждого|Для)\s+(_[A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ0-9_]*)\b', re.IGNORECASE)


# --- Символы ---

NON_BREAKING_SPACES = {
    "\u00A0": "NBSP (U+00A0)",
    "\u2007": "NNBSP (U+2007)",
    "\u2009": "THIN SPACE (U+2009)",
    "\u202F": "NNBSP (U+202F)",
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
                    file=str(file_path), line=i, col=col,
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
                    file=str(file_path), line=i, col=col,
                    rule_id="no-wrong-dash",
                    severity="error",
                    message=f"Тире {WRONG_DASHES[char]} — замените на дефис '-' (STD 456:1.2)",
                )


def rule_no_yo_in_code(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:1.1 — буква 'ё' запрещена в коде (кроме строковых литералов)."""
    for i, line in enumerate(lines, 1):
        # Убираем строковые литералы (простая эвристика)
        code_only = re.sub(r'"[^"]*"', '', line)
        for col, char in enumerate(code_only, 1):
            if char in ("ё", "Ё"):
                yield Violation(
                    file=str(file_path), line=i, col=col,
                    rule_id="no-yo-in-code",
                    severity="warning",
                    message=f"Буква '{char}' в коде — замените на 'е'/'Е' (STD 456:1.1)",
                )


def rule_no_commented_code(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:3 — закомментированный код запрещён."""
    for i, line in enumerate(lines, 1):
        if COMMENTED_CODE_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-commented-code",
                severity="warning",
                message=f"Закомментированный код — удалите после отладки (STD 456:3)",
            )


def rule_todo_with_task(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 456:3 — TODO без номера задачи."""
    for i, line in enumerate(lines, 1):
        if TODO_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="todo-with-task",
                severity="warning",
                message=f"TODO/FIXME без номера задачи — добавьте '№ N' (STD 456:3)",
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
                file=str(file_path), line=i, col=match.start() + 1,
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
                file=str(file_path), line=i, col=match.start() + 1,
                rule_id="no-hungarian-notation",
                severity="warning",
                message=f"Hungarian notation '{prefix}{name}' — имя от терминов предметной области (STD 454:2)",
            )


def rule_no_short_variables(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 454:4 — имена переменных < 2 символов (кроме счётчиков циклов)."""
    for i, line in enumerate(lines, 1):
        # Только объявления (Перем) и параметры цикла
        for match in re.finditer(r'\bПерем\s+([A-Za-zА-Яа-яёЁ])\s*;', line):
            name = match.group(1)
            if name.lower() not in COUNTER_NAMES:
                yield Violation(
                    file=str(file_path), line=i, col=match.start() + 1,
                    rule_id="no-short-variables",
                    severity="warning",
                    message=f"Имя переменной '{name}' < 2 символов — используйте описательное имя (STD 454:4)",
                )


def rule_no_underscore_vars(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD 454:3 — имена переменных не должны начинаться с _."""
    for i, line in enumerate(lines, 1):
        for match in UNDERSCORE_VAR_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path), line=i, col=match.start() + 1,
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
                file=str(file_path), line=i, col=MAX_LEN + 1,
                rule_id="line-too-long",
                severity="warning",
                message=f"Строка {len(stripped)} символов > {MAX_LEN} — разбейте или перенесите (STD 456)",
            )


# ============================================================================
# НОВЫЕ ПРАВИЛА (v3.0.0) — на основе ai_rules_1c и стандартов ITS
# ============================================================================

# Сообщить() — запрещено, использовать ОбщегоНазначения.СообщитьПользователю
SOOBSHIT_PATTERN = re.compile(r'\bСообщить\s*\(')

# Выполнить() — запрещено (dynamic code execution)
# Исключаем .Выполнить() — это метод объекта Запрос, не глобальная функция
VYPOLNIT_PATTERN = re.compile(r'(?<!\.)\bВыполнить\s*\(')

# Вычислить() — запрещено (dynamic code evaluation)
VYCHISLIT_PATTERN = re.compile(r'\bВычислить\s*\(')

# ?(условие, з1, з2) — тернарный оператор запрещён
TERNARY_PATTERN = re.compile(r'\?\s*\(')

# = Истина / = Ложь — булевы сравнения запрещены
BOOL_COMPARE_PATTERN = re.compile(r'=\s*(Истина|Ложь|True|False)\b', re.IGNORECASE)

# Yoda syntax: Если 0 = Сумма (число/строка слева от =)
YODA_PATTERN = re.compile(r'\bЕсли\s+["\d][^=]*=\s*[А-Яа-я]', re.IGNORECASE)

# Попытка...Исключение вокруг DB operations (грубая эвристика)
TRY_DB_PATTERN = re.compile(r'Попытка.*?(Запрос|Выполнить|Записать|Удалить|Прочитать)', re.IGNORECASE | re.DOTALL)

# Запрос в цикле (грубая эвристика: Новый Запрос внутри Для/Пока)
QUERY_IN_LOOP_PATTERN = re.compile(
    r'(Для\s+|Пока\s+).*?Новый\s+Запрос', re.IGNORECASE | re.DOTALL
)

# Точечная нотация: Объект.Реквизит (но не вызов метода)
# Исключаем: точки в числах (1.5), вызовы методов (.Метод()), цепочки (ОбщегоНазначения.Метод)
DOT_NOTATION_PATTERN = re.compile(
    r'\b([А-Яа-я][а-яё]+)\.([А-Я][а-яё]+)\b(?!\s*\()'  # Слово.Слово без скобок после
)

# Хардкод паролей/токенов
HARDCODED_CRED_PATTERN = re.compile(
    r'["\'].*?(пароль|password|токен|token|secret|api_key|apikey)["\']\s*[:=]',
    re.IGNORECASE
)

# Области модуля — должны быть в определённом порядке
REQUIRED_REGIONS = ['ПрограммныйИнтерфейс', 'СлужебныйПрограммныйИнтерфейс', 'СлужебныеПроцедурыИФункции']


def rule_no_soobshit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Сообщить() — использовать ОбщегоНазначения.СообщитьПользователю."""
    for i, line in enumerate(lines, 1):
        # Пропускаем комментарии
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if SOOBSHIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-soobshit",
                severity="warning",
                message="Сообщить() запрещено — используйте ОбщегоНазначения.СообщитьПользователю (ai_rules_1c)",
            )


def rule_no_vypolnit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Выполнить() — dynamic code execution."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if VYPOLNIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-vypolnit",
                severity="error",
                message="Выполнить() запрещено — dynamic code execution (ai_rules_1c)",
            )


def rule_no_vychislit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Вычислить() — dynamic code evaluation."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if VYCHISLIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-vychislit",
                severity="error",
                message="Вычислить() запрещено — dynamic code evaluation (ai_rules_1c)",
            )


def rule_no_ternary(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён тернарный оператор ?(условие, з1, з2)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if TERNARY_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-ternary",
                severity="warning",
                message="?(...) тернарный оператор запрещён — используйте Если...Иначе (ai_rules_1c)",
            )


def rule_no_boolean_compare(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено = Истина / = Ложь — используйте булево выражение напрямую."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        for match in BOOL_COMPARE_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path), line=i, col=match.start() + 1,
                rule_id="no-boolean-compare",
                severity="warning",
                message=f"Сравнение = {match.group(1)} избыточно — используйте выражение напрямую (ai_rules_1c)",
            )


def rule_no_yoda_syntax(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён Yoda syntax: Если 0 = Сумма."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if YODA_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-yoda-syntax",
                severity="warning",
                message="Yoda syntax запрещён — условие должно быть слева от = (ai_rules_1c)",
            )


def rule_no_query_in_loop(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """CRITICAL: Запрос в цикле — O(n) DB calls → O(1)."""
    full_text = '\n'.join(lines)
    for match in QUERY_IN_LOOP_PATTERN.finditer(full_text):
        # Вычисляем номер строки
        line_num = full_text[:match.start()].count('\n') + 1
        yield Violation(
            file=str(file_path), line=line_num, col=1,
            rule_id="no-query-in-loop",
            severity="error",
            message="Запрос в цикле — CRITICAL антипаттерн, используйте batch-запрос с ВТ (ai_rules_1c)",
        )


def rule_no_dot_notation(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Точечная нотация Объект.Реквизит — использовать ОбщегоНазначения."""
    # Исключения: вызовы методов, стандартные свойства
    EXCLUDE_WORDS = {
        'ЭтотОбъект', 'Объект', 'Форма', 'Элементы', 'ЭтаФорма',
        'Справочники', 'Документы', 'Регистры', 'Константы',
        'Метаданные', 'Параметры', 'ПараметрыСеанса',
        'Запрос', 'Результат', 'РезультатЗапроса', 'Выборка',
        'СтрокаТаблицы', 'Элемент', 'Колонка',
        # Имена таблиц в запросах:
        'Справочник', 'Документ', 'РегистрСведений', 'РегистрНакопления',
        'РегистрБухгалтерии', 'РегистрРасчета', 'ПланСчетов',
        'ПланВидовХарактеристик', 'ПланВидовРасчета', 'ПланОбмена',
        'Перечисление', 'БизнесПроцесс', 'Задача',
    }
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        # Пропускаем строки внутри текстов запросов
        if 'ВЫБРАТЬ' in line.upper() or 'ИЗ ' in line.upper() or 'СОЕДИНЕНИЕ' in line.upper():
            continue
        for match in DOT_NOTATION_PATTERN.finditer(line):
            obj_name = match.group(1)
            attr_name = match.group(2)
            # Пропускаем стандартные объекты
            if obj_name in EXCLUDE_WORDS:
                continue
            # Пропускаем если это вызов метода (после точки есть скобки)
            after = line[match.end():match.end() + 5]
            if '(' in after:
                continue
            yield Violation(
                file=str(file_path), line=i, col=match.start() + 1,
                rule_id="no-dot-notation",
                severity="warning",
                message=f"Точечная нотация '{obj_name}.{attr_name}' — используйте ОбщегоНазначения.ЗначениеРеквизитаОбъекта (ai_rules_1c)",
            )


def rule_no_hardcoded_credentials(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Хардкод паролей/токенов в коде запрещён."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if HARDCODED_CRED_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-hardcoded-credentials",
                severity="error",
                message="Хардкод паролей/токенов запрещён — используйте параметры или safe storage (ai_rules_1c)",
            )


def rule_no_magic_numbers(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Магические числа в коде — извлечь в именованные переменные."""
    # Исключения: 0, 1, -1, 100 (проценты), числа в строках
    MAGIC_NUM_PATTERN = re.compile(r'(?<!["\d.А-Яа-я])([2-9]\d{2,}|[1-9]\d{3,})(?!["\d.А-Яа-я])')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        # Пропускаем строки в кавычках
        code_only = re.sub(r'"[^"]*"', '', line)
        for match in MAGIC_NUM_PATTERN.finditer(code_only):
            num = match.group(1)
            # Пропускаем если это часть идентификатора
            before = code_only[max(0, match.start() - 1):match.start()]
            after = code_only[match.end():match.end() + 1]
            if before.isalpha() or after.isalpha():
                continue
            yield Violation(
                file=str(file_path), line=i, col=match.start() + 1,
                rule_id="no-magic-numbers",
                severity="warning",
                message=f"Магическое число {num} — извлеките в именованную переменную (ai_rules_1c)",
            )


def rule_module_structure(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Проверка структуры модуля — области ПрограммныйИнтерфейс и т.д."""
    full_text = '\n'.join(lines)
    has_any_region = '#Область' in full_text or '#КонецОбласти' in full_text

    if not has_any_region:
        # Если модуль маленький — ок без областей
        if len(lines) < 20:
            return
        yield Violation(
            file=str(file_path), line=1, col=1,
            rule_id="module-structure",
            severity="warning",
            message="Модуль > 20 строк без областей — добавьте #Область ПрограммныйИнтерфейс (STD 455)",
        )
        return

    # Проверяем наличие обязательных областей
    for region in REQUIRED_REGIONS:
        if f'#Область {region}' not in full_text:
            yield Violation(
                file=str(file_path), line=1, col=1,
                rule_id="module-structure",
                severity="warning",
                message=f"Нет области '#Область {region}' — обязательная структура модуля (STD 455)",
            )


def rule_no_try_around_db(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Попытка...Исключение вокруг DB operations запрещена."""
    full_text = '\n'.join(lines)
    # Ищем Попытка ... Исключение блоки с DB operations внутри
    try_blocks = re.finditer(
        r'Попытка\s*(.*?)\s*Исключение',
        full_text, re.IGNORECASE | re.DOTALL
    )
    for match in try_blocks:
        block_content = match.group(1)
        # Проверяем есть ли DB operations внутри
        if re.search(r'\b(Запрос|\.Записать\(|\.Удалить\(|\.Прочитать\()', block_content, re.IGNORECASE):
            line_num = full_text[:match.start()].count('\n') + 1
            yield Violation(
                file=str(file_path), line=line_num, col=1,
                rule_id="no-try-around-db",
                severity="error",
                message="Попытка...Исключение вокруг DB operations запрещена (ai_rules_1c)",
            )


# ============================================================================
# НОВЫЕ ПРАВИЛА v3.2.0 — тексты запросов и специфичные конструкции
# ============================================================================

# Перейти — запрещён (STD 456, ограничение на использование оператора Перейти)
PEREYTI_PATTERN = re.compile(r'\bПерейти\s+', re.IGNORECASE)

# ЗаписьЖурналаРегистрации без явной задачи
ZAPIS_ZHURNALA_PATTERN = re.compile(r'\bЗаписьЖурналаРегистрации\s*\(', re.IGNORECASE)

# ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ в запросах
FULL_OUTER_JOIN_PATTERN = re.compile(r'ПОЛНОЕ\s+ВНЕШНЕЕ\s+СОЕДИНЕНИЕ', re.IGNORECASE)

# ОБЪЕДИНИТЬ без ВСЕ (должно быть ОБЪЕДИНИТЬ ВСЕ)
OBYEDINIT_BEZ_VSE_PATTERN = re.compile(r'\bОБЪЕДИНИТЬ\b(?!\s+ВСЕ)', re.IGNORECASE)

# Отсутствие КАК в запросе (источники без псевдонимов)
# Ищем "ИЗ Справочник.Имя" без "КАК"
NO_ALIAS_PATTERN = re.compile(
    r'\b(?:ИЗ|СОЕДИНЕНИЕ|ОБЪЕДИНИТЬ)\s+\S+\s+(?![А-Я])',
    re.IGNORECASE
)

# ОбменДанными.Загрузка в обработчиках событий — должна проверяться
OBMEN_DANNIMI_PATTERN = re.compile(r'\bОбменДанными\.Загрузка\b', re.IGNORECASE)

# Использование Сообщить для предложений внешних компонент
PREDLOZHENIE_VNECHN_PATTERN = re.compile(r'ПоказатьВопрос\(|ПоказатьПредупреждение\(', re.IGNORECASE)


def rule_no_pereyti(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён оператор Перейти (STD 456 — ограничение на использование)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if PEREYTI_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-pereyti",
                severity="error",
                message="Оператор Перейти запрещён — используйте Если/Цикл/Процедура (STD 456)",
            )


def rule_no_zapis_zhurnala(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ЗаписьЖурналаРегистрации без явной задачи — запрещено."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if ZAPIS_ZHURNALA_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-zapis-zhurnala",
                severity="warning",
                message="ЗаписьЖурналаРегистрации() — используйте только по явной задаче (STD 456)",
            )


def rule_no_full_outer_join(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ в запросах — ограничено (STD 03)."""
    # Ищем в строках запросов (внутри кавычек)
    full_text = '\n'.join(lines)
    # Простая эвристика — ищем в многострочных текстах запросов
    for match in FULL_OUTER_JOIN_PATTERN.finditer(full_text):
        line_num = full_text[:match.start()].count('\n') + 1
        yield Violation(
            file=str(file_path), line=line_num, col=1,
            rule_id="no-full-outer-join",
            severity="warning",
            message="ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ — ограничено, используйте ЛЕВОЕ/ПРАВОЕ (STD 03)",
        )


def rule_no_obyedinit_bez_vse(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ОБЪЕДИНИТЬ без ВСЕ — обычно нужно ОБЪЕДИНИТЬ ВСЕ."""
    full_text = '\n'.join(lines)
    for match in OBYEDINIT_BEZ_VSE_PATTERN.finditer(full_text):
        line_num = full_text[:match.start()].count('\n') + 1
        yield Violation(
            file=str(file_path), line=line_num, col=1,
            rule_id="no-obyedinit-bez-vse",
            severity="warning",
            message="ОБЪЕДИНИТЬ без ВСЕ — проверьте, возможно нужно ОБЪЕДИНИТЬ ВСЕ (STD 03)",
        )


def rule_no_query_without_alias(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Источники данных в запросе без псевдонима КАК."""
    full_text = '\n'.join(lines)
    # Ищем только в строках, которые выглядят как текст запроса
    in_query = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        # Определяем начало/конец текста запроса
        if 'Запрос.Текст' in line or '"ВЫБРАТЬ' in line or 'ВЫБРАТЬ' in stripped:
            in_query = True
        if in_query:
            for match in NO_ALIAS_PATTERN.finditer(line):
                # Пропускаем если после идёт КАК
                after = line[match.end():match.end() + 10]
                if 'КАК' in after.upper() or 'ГДЕ' in after.upper():
                    continue
                yield Violation(
                    file=str(file_path), line=i, col=match.start() + 1,
                    rule_id="no-query-without-alias",
                    severity="warning",
                    message="Источник данных без псевдонима КАК — добавьте КАК (STD 03)",
                )
        if '";' in stripped or stripped.endswith('";'):
            in_query = False


def rule_no_obmen_dannimi_bez_proverki(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ОбменДанными.Загрузка должна проверяться в обработчиках событий."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if OBMEN_DANNIMI_PATTERN.search(line):
            # Проверяем — есть ли Если не ОбменДанными.Загрузка рядом
            # Простая эвристика — если в следующих 3 строках нет проверки
            context = lines[i-1:min(i+3, len(lines))]
            context_text = ' '.join(context)
            if 'Если' not in context_text or 'ОбменДанными' not in context_text:
                yield Violation(
                    file=str(file_path), line=i, col=1,
                    rule_id="no-obmen-dannimi-bez-proverki",
                    severity="warning",
                    message="ОбменДанными.Загрузка без проверки — добавьте Если Не ОбменДанными.Загрузка (STD 01)",
                )


def rule_no_predlozhenie_vnechn(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПоказатьВопрос/ПоказатьПредупреждение — проверка наличия."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if PREDLOZHENIE_VNECHN_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-predlozhenie-vnechn",
                severity="warning",
                message="ПоказатьВопрос/ПоказатьПредупреждение — проверьте стандарты UI (STD 08)",
            )


# ============================================================================
# ПРАВИЛА v3.4.0 — из 1c-standards-claude-skill (SKILL.md)
# ============================================================================

# Директивы компиляции
NACLIENTE_PATTERN = re.compile(r'&НаКлиенте', re.IGNORECASE)
NASERVERE_PATTERN = re.compile(r'&НаСервере(?!БезКонтекста)', re.IGNORECASE)

# Транзакции
BEGIN_TRANSACTION_PATTERN = re.compile(r'\bНачатьТранзакцию\s*\(', re.IGNORECASE)

# Привилегированный режим
PRIV_MODE_PATTERN = re.compile(r'\bПривилегированныйРежим\s*\(', re.IGNORECASE)

# ПравоДоступа
PRAVO_DOSTUPA_PATTERN = re.compile(r'\bПравоДоступа\s*\(', re.IGNORECASE)

# Процедуры/Функции вне областей
PROC_OUTSIDE_REGION_PATTERN = re.compile(r'^(Процедура|Функция)\s+', re.IGNORECASE)

# Конкатенация строк в тексте запроса
QUERY_CONCAT_PATTERN = re.compile(r'Запрос\.Текст\s*\+|СтрЗаменить.*Запрос', re.IGNORECASE)

# Ключевые слова запроса должны быть КАПСОМ
QUERY_LOWERCASE_PATTERN = re.compile(r'\b(выбрать|из|где|соединение|объединить|сгруппировать|упорядочить|имеющие|выбрать различные)\b', re.IGNORECASE)

# ОповеститьОбИзменении в серверных процедурах
OPOVESTIT_PATTERN = re.compile(r'\bОповеститьОбИзменении\s*\(', re.IGNORECASE)

# Булевы переменные с отрицанием (НеПроверено, НеНайдено)
BOOL_NEGATIVE_PATTERN = re.compile(r'\bПерем\s+(НеПроверен|НеНайден|НеАктивен|НеГотов|НеЗавершен)\w*', re.IGNORECASE)


def rule_no_transaction_in_nacliente(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """НачатьТранзакцию в &НаКлиенте — запрещено (1c-standards-claude-skill)."""
    in_nacliente = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if NACLIENTE_PATTERN.search(line):
            in_nacliente = True
        if NASERVERE_PATTERN.search(line):
            in_nacliente = False
        if in_nacliente and BEGIN_TRANSACTION_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-transaction-in-nacliente",
                severity="error",
                message="НачатьТранзакцию() в &НаКлиенте — запрещено (1c-standards-claude-skill STD 12)",
            )


def rule_no_db_in_nacliente(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Обращение к БД в &НаКлиенте — запрещено (1c-standards-claude-skill)."""
    in_nacliente = False
    DB_PATTERNS = re.compile(r'\b(Новый\s+Запрос|\.Записать\(|\.Прочитать\(|\.Удалить\(|Справочники\.|Документы\.)', re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if NACLIENTE_PATTERN.search(line):
            in_nacliente = True
        if NASERVERE_PATTERN.search(line):
            in_nacliente = False
        if in_nacliente and DB_PATTERNS.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-db-in-nacliente",
                severity="error",
                message="Обращение к БД в &НаКлиенте — запрещено (1c-standards-claude-skill STD 12)",
            )


def rule_no_server_call_in_loop(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Серверные вызовы в цикле — каждый вызов = roundtrip (1c-standards-claude-skill)."""
    in_loop = False
    loop_depth = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        # Отслеживаем циклы
        if re.search(r'\b(Для|Пока)\s', line, re.IGNORECASE) and 'Цикл' in line:
            in_loop = True
            loop_depth += 1
        if re.search(r'\bКонецЦикла', line, re.IGNORECASE):
            loop_depth -= 1
            if loop_depth <= 0:
                in_loop = False
                loop_depth = 0
        # Проверяем серверные вызовы
        if in_loop and re.search(r'&НаСервере|ВыполнитьНаСервере|ПолучитьНаСервере', line, re.IGNORECASE):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-server-call-in-loop",
                severity="warning",
                message="Серверный вызов в цикле — каждый вызов = roundtrip (1c-standards-claude-skill STD 12)",
            )


def rule_no_privileged_mode_without_reason(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПривилегированныйРежим без обоснования (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if PRIV_MODE_PATTERN.search(line):
            # Проверяем — есть ли комментарий-обоснование в предыдущей строке
            if i > 1:
                prev = lines[i - 2].strip()
                if prev.startswith('//') and ('привилегирован' in prev.lower() or 'право' in prev.lower() or 'rls' in prev.lower()):
                    continue  # есть обоснование
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-privileged-mode-without-reason",
                severity="warning",
                message="ПривилегированныйРежим() без обоснования — добавьте комментарий с причиной (1c-standards-claude-skill STD 13)",
            )


def rule_procedures_outside_regions(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Процедуры/Функции вне областей (1c-standards-claude-skill STD 455)."""
    in_region = False
    has_any_region = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if '#Область' in stripped or '#Region' in stripped:
            in_region = True
            has_any_region = True
        if '#КонецОбласти' in stripped or '#EndRegion' in stripped:
            in_region = False
        # Если есть области, но процедура вне области
        if has_any_region and not in_region and PROC_OUTSIDE_REGION_PATTERN.search(stripped):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="procedure-outside-region",
                severity="warning",
                message="Процедура/Функция вне области — поместите в #Область (1c-standards-claude-skill STD 455)",
            )


def rule_export_in_wrong_region(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Экспортные процедуры должны быть в ПрограммныйИнтерфейс (1c-standards-claude-skill)."""
    current_region = ""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#Область'):
            current_region = stripped.replace('#Область', '').strip()
        if stripped.startswith('#КонецОбласти'):
            current_region = ""
        # Если это экспортная процедура
        if re.search(r'(Процедура|Функция)\s+\w+.*Экспорт', stripped, re.IGNORECASE):
            # Должна быть в ПрограммныйИнтерфейс или СлужебныйПрограммныйИнтерфейс
            if current_region and current_region not in ('ПрограммныйИнтерфейс', 'СлужебныйПрограммныйИнтерфейс', 'Public', 'Private'):
                yield Violation(
                    file=str(file_path), line=i, col=1,
                    rule_id="export-in-wrong-region",
                    severity="warning",
                    message=f"Экспортная процедура в области '{current_region}' — должна быть в ПрограммныйИнтерфейс (1c-standards-claude-skill STD 455)",
                )


def rule_no_doc_comment(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Экспортные процедуры должны иметь комментарий-документацию (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Если это экспортная процедура
        if re.search(r'(Процедура|Функция)\s+\w+.*Экспорт', stripped, re.IGNORECASE):
            # Проверяем предыдущие строки на наличие комментария
            has_comment = False
            if i > 1:
                prev = lines[i - 2].strip() if i >= 2 else ""
                if prev.startswith('//'):
                    has_comment = True
            if not has_comment:
                yield Violation(
                    file=str(file_path), line=i, col=1,
                    rule_id="no-doc-comment",
                    severity="warning",
                    message="Экспортная процедура без комментария-документации — добавьте описание (1c-standards-claude-skill STD 455)",
                )


def rule_no_query_concat(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Конкатенация строк в тексте запроса — использовать параметры (1c-standards-claude-skill STD 03)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if QUERY_CONCAT_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-query-concat",
                severity="warning",
                message="Конкатенация строк в тексте запроса — используйте Запрос.УстановитьПараметр() (1c-standards-claude-skill STD 03)",
            )


def rule_query_keywords_lowercase(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Ключевые слова запроса должны быть КАПСОМ (1c-standards-claude-skill STD 03)."""
    in_query = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'Запрос.Текст' in line or '"ВЫБРАТЬ' in line or 'ВЫБРАТЬ' in stripped:
            in_query = True
        if in_query:
            for match in QUERY_LOWERCASE_PATTERN.finditer(line):
                # Пропускаем если это в строке-комментарии
                if stripped.startswith('//'):
                    continue
                yield Violation(
                    file=str(file_path), line=i, col=match.start() + 1,
                    rule_id="query-keywords-lowercase",
                    severity="warning",
                    message=f"Ключевое слово '{match.group(0)}' в нижнем регистре — должно быть КАПСОМ (1c-standards-claude-skill STD 03)",
                )
        if '";' in stripped:
            in_query = False


def rule_no_opovestit_on_server(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ОповеститьОбИзменении в серверных процедурах без необходимости (1c-standards-claude-skill STD 12)."""
    in_naservere = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if NASERVERE_PATTERN.search(line):
            in_naservere = True
        if NACLIENTE_PATTERN.search(line):
            in_naservere = False
        if in_naservere and OPOVESTIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-opovestit-on-server",
                severity="warning",
                message="ОповеститьОбИзменении в серверной процедуре — проверьте необходимость (1c-standards-claude-skill STD 12)",
            )


def rule_no_bool_negative_names(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Булевы переменные с отрицанием — использовать утверждение (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        for match in BOOL_NEGATIVE_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path), line=i, col=match.start() + 1,
                rule_id="no-bool-negative-names",
                severity="warning",
                message=f"Булева переменная с отрицанием '{match.group(0)}' — используйте утверждение (1c-standards-claude-skill)",
            )


def rule_check_pravo_dostupa_before_write(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Проверка права перед записью/удалением (1c-standards-claude-skill STD 13)."""
    WRITE_PATTERNS = re.compile(r'\b(Объект\.Записать\(|\.Записать\(|\.Удалить\(|\.Провести\()', re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if WRITE_PATTERNS.search(line):
            # Проверяем — есть ли ПравоДоступа в предыдущих 5 строках
            context = lines[max(0, i - 6):i]
            context_text = ' '.join(context)
            if not PRAVO_DOSTUPA_PATTERN.search(context_text):
                yield Violation(
                    file=str(file_path), line=i, col=1,
                    rule_id="check-pravo-dostupa-before-write",
                    severity="warning",
                    message="Запись/удаление без проверки ПравоДоступа — добавьте проверку (1c-standards-claude-skill STD 13)",
                )


def rule_no_com_object_bypass(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Прямой SQL или обход через COM-объекты (1c-standards-claude-skill STD 13)."""
    COM_PATTERN = re.compile(r'\b(COMОбъект|COMObject|ADODB\.Connection|ADODB\.Recordset)\b', re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if COM_PATTERN.search(line):
            yield Violation(
                file=str(file_path), line=i, col=1,
                rule_id="no-com-object-bypass",
                severity="error",
                message="COM-объект/прямой SQL — обход механизма прав 1С (1c-standards-claude-skill STD 13)",
            )


# ============================================================================
# ВСЕ ПРАВИЛА
# ============================================================================

ALL_RULES = [
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
    # v3.0.0:
    rule_no_soobshit,
    rule_no_vypolnit,
    rule_no_vychislit,
    rule_no_ternary,
    rule_no_boolean_compare,
    rule_no_yoda_syntax,
    rule_no_query_in_loop,
    rule_no_dot_notation,
    rule_no_hardcoded_credentials,
    rule_no_magic_numbers,
    rule_module_structure,
    rule_no_try_around_db,
    # v3.2.0:
    rule_no_pereyti,
    rule_no_zapis_zhurnala,
    rule_no_full_outer_join,
    rule_no_obyedinit_bez_vse,
    rule_no_query_without_alias,
    rule_no_obmen_dannimi_bez_proverki,
    rule_no_predlozhenie_vnechn,
    # v3.4.0 — из 1c-standards-claude-skill:
    rule_no_transaction_in_nacliente,
    rule_no_db_in_nacliente,
    rule_no_server_call_in_loop,
    rule_no_privileged_mode_without_reason,
    rule_procedures_outside_regions,
    rule_export_in_wrong_region,
    rule_no_doc_comment,
    rule_no_query_concat,
    rule_query_keywords_lowercase,
    rule_no_opovestit_on_server,
    rule_no_bool_negative_names,
    rule_check_pravo_dostupa_before_write,
    rule_no_com_object_bypass,
]


# ============================================================================
# CHECKER
# ============================================================================

class StandardsChecker:
    """Проверка .bsl файлов на соответствие стандартам 1С."""

    def __init__(self, rules: list | None = None):
        self.rules = rules or ALL_RULES

    def check_file(self, file_path: Path) -> list[Violation]:
        """Проверить один .bsl файл."""
        try:
            # Пробуем UTF-8, если не получится — windows-1251 (часто в 1С)
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="cp1251")
        except OSError as e:
            return [Violation(
                file=str(file_path), line=0, col=0,
                rule_id="read-error",
                severity="error",
                message=f"Не удалось прочитать файл: {e}",
            )]

        lines = content.splitlines()
        violations = []
        for rule_fn in self.rules:
            violations.extend(rule_fn(lines, file_path))
        return violations

    def check_path(self, path: Path) -> list[Violation]:
        """Проверить файл или директорию (рекурсивно)."""
        if path.is_file():
            if path.suffix.lower() == ".bsl":
                return self.check_file(path)
            return []

        violations = []
        for bsl_file in sorted(path.rglob("*.bsl")):
            violations.extend(self.check_file(bsl_file))
        return violations


# ============================================================================
# CLI
# ============================================================================

def format_violations(violations: list[Violation], output_format: str = "text") -> str:
    """Форматировать вывод."""
    if output_format == "json":
        return json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2)

    if not violations:
        return "✅ Нарушений не найдено."

    # Группируем по файлам
    by_file: dict[str, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    lines = []
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    lines.append(f"Найдено: {errors} errors, {warnings} warnings в {len(by_file)} файлах")
    lines.append("")

    for file_path in sorted(by_file.keys()):
        lines.append(f"📋 {file_path}")
        for v in by_file[file_path]:
            lines.append(v.format_text())
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        prog="check_1c_standards",
        description="Проверка .bsl файлов на соответствие стандартам разработки 1С",
    )
    parser.add_argument("path", help="Путь к .bsl файлу или директории")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Формат вывода (по умолчанию: text)",
    )
    parser.add_argument(
        "--severity", choices=["error", "warning", "all"], default="all",
        help="Минимальный уровень severity для вывода (по умолчанию: all)",
    )
    parser.add_argument(
        "--rules", help="Список rule_id через запятую (пусто = все правила)",
    )

    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"❌ Путь не существует: {path}", file=sys.stderr)
        return 2

    # Фильтрация правил
    rules = ALL_RULES
    if args.rules:
        wanted = set(r.strip() for r in args.rules.split(","))
        rules = [r for r in ALL_RULES if r.__name__.replace("rule_", "").replace("-", "_") in wanted]
        if not rules:
            print(f"❌ Не найдено правил: {args.rules}", file=sys.stderr)
            return 2

    checker = StandardsChecker(rules=rules)
    violations = checker.check_path(path)

    # Фильтрация по severity
    if args.severity == "error":
        violations = [v for v in violations if v.severity == "error"]
    elif args.severity == "warning":
        violations = [v for v in violations if v.severity in ("error", "warning")]

    print(format_violations(violations, args.format))

    # Exit code: 1 если есть errors
    has_errors = any(v.severity == "error" for v in violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
