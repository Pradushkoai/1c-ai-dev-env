"""
ПРАВИЛА — АРХИТЕКТУРА И БЕЗОПАСНОСТЬ

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py (god-файл 1685 LOC).
Логика без изменений — только перенос.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ._common import Violation

# ============================================================================
# ПРАВИЛА — АРХИТЕКТУРА И БЕЗОПАСНОСТЬ
# ============================================================================

# ============================================================================
# НОВЫЕ ПРАВИЛА (v3.0.0) — на основе ai_rules_1c и стандартов ITS
# ============================================================================

# Сообщить() — запрещено, использовать ОбщегоНазначения.СообщитьПользователю
SOOBSHIT_PATTERN = re.compile(r"\bСообщить\s*\(")

# Выполнить() — запрещено (dynamic code execution)
# Исключаем .Выполнить() — это метод объекта Запрос, не глобальная функция
VYPOLNIT_PATTERN = re.compile(r"(?<!\.)\bВыполнить\s*\(")

# Вычислить() — запрещено (dynamic code evaluation)
VYCHISLIT_PATTERN = re.compile(r"\bВычислить\s*\(")

# ?(условие, з1, з2) — тернарный оператор запрещён
TERNARY_PATTERN = re.compile(r"\?\s*\(")

# = Истина / = Ложь — булевы сравнения запрещены
BOOL_COMPARE_PATTERN = re.compile(r"=\s*(Истина|Ложь|True|False)\b", re.IGNORECASE)

# Yoda syntax: Если 0 = Сумма (число/строка слева от =)
YODA_PATTERN = re.compile(r'\bЕсли\s+["\d][^=]*=\s*[А-Яа-я]', re.IGNORECASE)

# Попытка...Исключение вокруг DB operations (грубая эвристика)
TRY_DB_PATTERN = re.compile(r"Попытка.*?(Запрос|Выполнить|Записать|Удалить|Прочитать)", re.IGNORECASE | re.DOTALL)

# Запрос в цикле (грубая эвристика: Новый Запрос внутри Для/Пока)
QUERY_IN_LOOP_PATTERN = re.compile(r"(Для\s+|Пока\s+).*?Новый\s+Запрос", re.IGNORECASE | re.DOTALL)

# Точечная нотация: Объект.Реквизит (но не вызов метода)
# Исключаем: точки в числах (1.5), вызовы методов (.Метод()), цепочки (ОбщегоНазначения.Метод)
DOT_NOTATION_PATTERN = re.compile(
    r"\b([А-Яа-я][а-яё]+)\.([А-Я][а-яё]+)\b(?!\s*\()"  # Слово.Слово без скобок после
)

# Хардкод паролей/токенов
HARDCODED_CRED_PATTERN = re.compile(
    r'["\'].*?(пароль|password|токен|token|secret|api_key|apikey)["\']\s*[:=]', re.IGNORECASE
)

# Области модуля — должны быть в определённом порядке
REQUIRED_REGIONS = ["ПрограммныйИнтерфейс", "СлужебныйПрограммныйИнтерфейс", "СлужебныеПроцедурыИФункции"]


def rule_no_soobshit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Сообщить() — использовать ОбщегоНазначения.СообщитьПользователю."""
    for i, line in enumerate(lines, 1):
        # Пропускаем комментарии
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if SOOBSHIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-soobshit",
                severity="warning",
                message="Сообщить() запрещено — используйте ОбщегоНазначения.СообщитьПользователю (ai_rules_1c)",
            )


def rule_no_vypolnit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Выполнить() — dynamic code execution."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if VYPOLNIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-vypolnit",
                severity="error",
                message="Выполнить() запрещено — dynamic code execution (ai_rules_1c)",
            )


def rule_no_vychislit(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено Вычислить() — dynamic code evaluation."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if VYCHISLIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-vychislit",
                severity="error",
                message="Вычислить() запрещено — dynamic code evaluation (ai_rules_1c)",
            )


def rule_no_ternary(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён тернарный оператор ?(условие, з1, з2)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if TERNARY_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-ternary",
                severity="warning",
                message="?(...) тернарный оператор запрещён — используйте Если...Иначе (ai_rules_1c)",
            )


def rule_no_boolean_compare(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещено = Истина / = Ложь — используйте булево выражение напрямую."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        for match in BOOL_COMPARE_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-boolean-compare",
                severity="warning",
                message=f"Сравнение = {match.group(1)} избыточно — используйте выражение напрямую (ai_rules_1c)",
            )


def rule_no_yoda_syntax(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён Yoda syntax: Если 0 = Сумма."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if YODA_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-yoda-syntax",
                severity="warning",
                message="Yoda syntax запрещён — условие должно быть слева от = (ai_rules_1c)",
            )


def rule_no_query_in_loop(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """CRITICAL: Запрос в цикле — O(n) DB calls → O(1).

    Важно: анализирует только реальный код, без комментариев и строковых литералов.
    Иначе docstring-примеры с 'Для ... Цикл' вызывают ложные срабатывания.
    """
    # Удаляем комментарии (// ... до конца строки) и строковые литералы ("...")
    # Это позволяет избежать ложных срабатываний на docstring-примерах.
    code_only_lines = []
    for line in lines:
        # Удаляем однострочные комментарии (// ...)
        # В BSL нет многострочных комментариев, только //
        comment_pos = _find_comment_start(line)
        if comment_pos >= 0:
            line = line[:comment_pos]
        # Удаляем строковые литералы ("...") — заменяем на пустую строку
        # Важно: не трогаем строки внутри запросов, т.к. там ключевые слова
        # в тексте запроса не влияют на detection циклов
        line = re.sub(r'"[^"]*"', '""', line)
        code_only_lines.append(line)

    full_text = "\n".join(code_only_lines)
    for match in QUERY_IN_LOOP_PATTERN.finditer(full_text):
        # Вычисляем номер строки
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-query-in-loop",
            severity="error",
            message="Запрос в цикле — CRITICAL антипаттерн, используйте batch-запрос с ВТ (ai_rules_1c)",
        )


def _find_comment_start(line: str) -> int:
    """Найти позицию начала комментария (//) в строке, игнорируя // внутри строк.

    BSL использует // для комментариев. Но // может быть внутри строкового литерала,
    например в тексте запроса "http://...". Ищем первый //, который не внутри "...".
    """
    in_string = False
    i = 0
    while i < len(line) - 1:
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != "|"):
            # Входим/выходим из строкового литерала
            # Примечание: в BSL строки в запросах начинаются с |" — не считаем
            in_string = not in_string
        elif not in_string and ch == "/" and line[i + 1] == "/":
            return i
        i += 1
    return -1


def rule_no_dot_notation(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Точечная нотация Объект.Реквизит — использовать ОбщегоНазначения."""
    # Исключения: вызовы методов, стандартные свойства
    EXCLUDE_WORDS = {
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
        # Имена таблиц в запросах:
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
    }
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Пропускаем строки внутри текстов запросов
        if "ВЫБРАТЬ" in line.upper() or "ИЗ " in line.upper() or "СОЕДИНЕНИЕ" in line.upper():
            continue
        for match in DOT_NOTATION_PATTERN.finditer(line):
            obj_name = match.group(1)
            attr_name = match.group(2)
            # Пропускаем стандартные объекты
            if obj_name in EXCLUDE_WORDS:
                continue
            # Пропускаем если это вызов метода (после точки есть скобки)
            after = line[match.end() : match.end() + 5]
            if "(" in after:
                continue
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-dot-notation",
                severity="warning",
                message=f"Точечная нотация '{obj_name}.{attr_name}' — используйте ОбщегоНазначения.ЗначениеРеквизитаОбъекта (ai_rules_1c)",
            )


def rule_no_hardcoded_credentials(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Хардкод паролей/токенов в коде запрещён."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if HARDCODED_CRED_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
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
        if stripped.startswith("//"):
            continue
        # Пропускаем строки в кавычках
        code_only = re.sub(r'"[^"]*"', "", line)
        for match in MAGIC_NUM_PATTERN.finditer(code_only):
            num = match.group(1)
            # Пропускаем если это часть идентификатора
            before = code_only[max(0, match.start() - 1) : match.start()]
            after = code_only[match.end() : match.end() + 1]
            if before.isalpha() or after.isalpha():
                continue
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-magic-numbers",
                severity="warning",
                message=f"Магическое число {num} — извлеките в именованную переменную (ai_rules_1c)",
            )


def rule_module_structure(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Проверка структуры модуля — области ПрограммныйИнтерфейс и т.д."""
    full_text = "\n".join(lines)
    has_any_region = "#Область" in full_text or "#КонецОбласти" in full_text

    if not has_any_region:
        # Если модуль маленький — ок без областей
        if len(lines) < 20:
            return
        yield Violation(
            file=str(file_path),
            line=1,
            col=1,
            rule_id="module-structure",
            severity="warning",
            message="Модуль > 20 строк без областей — добавьте #Область ПрограммныйИнтерфейс (STD 455)",
        )
        return

    # Проверяем наличие обязательных областей
    for region in REQUIRED_REGIONS:
        if f"#Область {region}" not in full_text:
            yield Violation(
                file=str(file_path),
                line=1,
                col=1,
                rule_id="module-structure",
                severity="warning",
                message=f"Нет области '#Область {region}' — обязательная структура модуля (STD 455)",
            )


def rule_no_try_around_db(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Попытка...Исключение вокруг DB operations запрещена."""
    full_text = "\n".join(lines)
    # Ищем Попытка ... Исключение блоки с DB operations внутри
    try_blocks = re.finditer(r"Попытка\s*(.*?)\s*Исключение", full_text, re.IGNORECASE | re.DOTALL)
    for match in try_blocks:
        block_content = match.group(1)
        # Проверяем есть ли DB operations внутри
        if re.search(r"\b(Запрос|\.Записать\(|\.Удалить\(|\.Прочитать\()", block_content, re.IGNORECASE):
            line_num = full_text[: match.start()].count("\n") + 1
            yield Violation(
                file=str(file_path),
                line=line_num,
                col=1,
                rule_id="no-try-around-db",
                severity="error",
                message="Попытка...Исключение вокруг DB operations запрещена (ai_rules_1c)",
            )


# Список правил в этом модуле
RULES = [
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
]
