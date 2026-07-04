"""
ПРАВИЛА — КЛИЕНТ-СЕРВЕР

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py (god-файл 1685 LOC).
Логика без изменений — только перенос.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ._common import Violation

# ============================================================================
# ПРАВИЛА — КЛИЕНТ-СЕРВЕР
# ============================================================================

# ============================================================================
# ПРАВИЛА v3.4.0 — из 1c-standards-claude-skill (SKILL.md)
# ============================================================================

# Директивы компиляции
NACLIENTE_PATTERN = re.compile(r"&НаКлиенте", re.IGNORECASE)
NASERVERE_PATTERN = re.compile(r"&НаСервере(?!БезКонтекста)", re.IGNORECASE)

# Транзакции
BEGIN_TRANSACTION_PATTERN = re.compile(r"\bНачатьТранзакцию\s*\(", re.IGNORECASE)

# Привилегированный режим
PRIV_MODE_PATTERN = re.compile(r"\bПривилегированныйРежим\s*\(", re.IGNORECASE)

# ПравоДоступа
PRAVO_DOSTUPA_PATTERN = re.compile(r"\bПравоДоступа\s*\(", re.IGNORECASE)

# Процедуры/Функции вне областей
PROC_OUTSIDE_REGION_PATTERN = re.compile(r"^(Процедура|Функция)\s+", re.IGNORECASE)

# Конкатенация строк в тексте запроса
QUERY_CONCAT_PATTERN = re.compile(r"Запрос\.Текст\s*\+|СтрЗаменить.*Запрос", re.IGNORECASE)

# Ключевые слова запроса должны быть КАПСОМ
QUERY_LOWERCASE_PATTERN = re.compile(
    r"\b(выбрать|из|где|соединение|объединить|сгруппировать|упорядочить|имеющие|выбрать различные)\b", re.IGNORECASE
)

# ОповеститьОбИзменении в серверных процедурах
OPOVESTIT_PATTERN = re.compile(r"\bОповеститьОбИзменении\s*\(", re.IGNORECASE)

# Булевы переменные с отрицанием (НеПроверено, НеНайдено)
BOOL_NEGATIVE_PATTERN = re.compile(r"\bПерем\s+(НеПроверен|НеНайден|НеАктивен|НеГотов|НеЗавершен)\w*", re.IGNORECASE)


def rule_no_transaction_in_nacliente(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """НачатьТранзакцию в &НаКлиенте — запрещено (1c-standards-claude-skill)."""
    in_nacliente = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if NACLIENTE_PATTERN.search(line):
            in_nacliente = True
        if NASERVERE_PATTERN.search(line):
            in_nacliente = False
        if in_nacliente and BEGIN_TRANSACTION_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-transaction-in-nacliente",
                severity="error",
                message="НачатьТранзакцию() в &НаКлиенте — запрещено (1c-standards-claude-skill STD 12)",
            )


def rule_no_db_in_nacliente(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Обращение к БД в &НаКлиенте — запрещено (1c-standards-claude-skill)."""
    in_nacliente = False
    DB_PATTERNS = re.compile(
        r"\b(Новый\s+Запрос|\.Записать\(|\.Прочитать\(|\.Удалить\(|Справочники\.|Документы\.)", re.IGNORECASE
    )
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if NACLIENTE_PATTERN.search(line):
            in_nacliente = True
        if NASERVERE_PATTERN.search(line):
            in_nacliente = False
        if in_nacliente and DB_PATTERNS.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
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
        if stripped.startswith("//"):
            continue
        # Отслеживаем циклы
        if re.search(r"\b(Для|Пока)\s", line, re.IGNORECASE) and "Цикл" in line:
            in_loop = True
            loop_depth += 1
        if re.search(r"\bКонецЦикла", line, re.IGNORECASE):
            loop_depth -= 1
            if loop_depth <= 0:
                in_loop = False
                loop_depth = 0
        # Проверяем серверные вызовы
        if in_loop and re.search(r"&НаСервере|ВыполнитьНаСервере|ПолучитьНаСервере", line, re.IGNORECASE):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-server-call-in-loop",
                severity="warning",
                message="Серверный вызов в цикле — каждый вызов = roundtrip (1c-standards-claude-skill STD 12)",
            )


def rule_no_privileged_mode_without_reason(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПривилегированныйРежим без обоснования (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if PRIV_MODE_PATTERN.search(line):
            # Проверяем — есть ли комментарий-обоснование в предыдущей строке
            if i > 1:
                prev = lines[i - 2].strip()
                if prev.startswith("//") and (
                    "привилегирован" in prev.lower() or "право" in prev.lower() or "rls" in prev.lower()
                ):
                    continue  # есть обоснование
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
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
        if "#Область" in stripped or "#Region" in stripped:
            in_region = True
            has_any_region = True
        if "#КонецОбласти" in stripped or "#EndRegion" in stripped:
            in_region = False
        # Если есть области, но процедура вне области
        if has_any_region and not in_region and PROC_OUTSIDE_REGION_PATTERN.search(stripped):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="procedure-outside-region",
                severity="warning",
                message="Процедура/Функция вне области — поместите в #Область (1c-standards-claude-skill STD 455)",
            )


def rule_export_in_wrong_region(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Экспортные процедуры должны быть в ПрограммныйИнтерфейс (1c-standards-claude-skill)."""
    current_region = ""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#Область"):
            current_region = stripped.replace("#Область", "").strip()
        if stripped.startswith("#КонецОбласти"):
            current_region = ""
        # Если это экспортная процедура
        if re.search(r"(Процедура|Функция)\s+\w+.*Экспорт", stripped, re.IGNORECASE):
            # Должна быть в ПрограммныйИнтерфейс или СлужебныйПрограммныйИнтерфейс
            if current_region and current_region not in (
                "ПрограммныйИнтерфейс",
                "СлужебныйПрограммныйИнтерфейс",
                "Public",
                "Private",
            ):
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="export-in-wrong-region",
                    severity="warning",
                    message=f"Экспортная процедура в области '{current_region}' — должна быть в ПрограммныйИнтерфейс (1c-standards-claude-skill STD 455)",
                )


def rule_no_doc_comment(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Экспортные процедуры должны иметь комментарий-документацию (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Если это экспортная процедура
        if re.search(r"(Процедура|Функция)\s+\w+.*Экспорт", stripped, re.IGNORECASE):
            # Проверяем предыдущие строки на наличие комментария
            has_comment = False
            if i > 1:
                prev = lines[i - 2].strip() if i >= 2 else ""
                if prev.startswith("//"):
                    has_comment = True
            if not has_comment:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="no-doc-comment",
                    severity="warning",
                    message="Экспортная процедура без комментария-документации — добавьте описание (1c-standards-claude-skill STD 455)",
                )


def rule_no_query_concat(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Конкатенация строк в тексте запроса — использовать параметры (1c-standards-claude-skill STD 03)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if QUERY_CONCAT_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-query-concat",
                severity="warning",
                message="Конкатенация строк в тексте запроса — используйте Запрос.УстановитьПараметр() (1c-standards-claude-skill STD 03)",
            )


def rule_query_keywords_lowercase(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Ключевые слова запроса должны быть КАПСОМ (1c-standards-claude-skill STD 03)."""
    in_query = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "Запрос.Текст" in line or '"ВЫБРАТЬ' in line or "ВЫБРАТЬ" in stripped:
            in_query = True
        if in_query:
            for match in QUERY_LOWERCASE_PATTERN.finditer(line):
                # Пропускаем если это в строке-комментарии
                if stripped.startswith("//"):
                    continue
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=match.start() + 1,
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
        if stripped.startswith("//"):
            continue
        if NASERVERE_PATTERN.search(line):
            in_naservere = True
        if NACLIENTE_PATTERN.search(line):
            in_naservere = False
        if in_naservere and OPOVESTIT_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-opovestit-on-server",
                severity="warning",
                message="ОповеститьОбИзменении в серверной процедуре — проверьте необходимость (1c-standards-claude-skill STD 12)",
            )


def rule_no_bool_negative_names(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Булевы переменные с отрицанием — использовать утверждение (1c-standards-claude-skill)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        for match in BOOL_NEGATIVE_PATTERN.finditer(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=match.start() + 1,
                rule_id="no-bool-negative-names",
                severity="warning",
                message=f"Булева переменная с отрицанием '{match.group(0)}' — используйте утверждение (1c-standards-claude-skill)",
            )


def rule_check_pravo_dostupa_before_write(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Проверка права перед записью/удалением (1c-standards-claude-skill STD 13)."""
    WRITE_PATTERNS = re.compile(r"\b(Объект\.Записать\(|\.Записать\(|\.Удалить\(|\.Провести\()", re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if WRITE_PATTERNS.search(line):
            # Проверяем — есть ли ПравоДоступа в предыдущих 5 строках
            context = lines[max(0, i - 6) : i]
            context_text = " ".join(context)
            if not PRAVO_DOSTUPA_PATTERN.search(context_text):
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="check-pravo-dostupa-before-write",
                    severity="warning",
                    message="Запись/удаление без проверки ПравоДоступа — добавьте проверку (1c-standards-claude-skill STD 13)",
                )


def rule_no_com_object_bypass(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Прямой SQL или обход через COM-объекты (1c-standards-claude-skill STD 13)."""
    COM_PATTERN = re.compile(r"\b(COMОбъект|COMObject|ADODB\.Connection|ADODB\.Recordset)\b", re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if COM_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-com-object-bypass",
                severity="error",
                message="COM-объект/прямой SQL — обход механизма прав 1С (1c-standards-claude-skill STD 13)",
            )


# Список правил в этом модуле
RULES = [
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
