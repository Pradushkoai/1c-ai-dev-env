"""
ПРАВИЛА — ЗАПРОСЫ

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py (god-файл 1685 LOC).
Логика без изменений — только перенос.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ._common import Violation

# ============================================================================
# ПРАВИЛА — ЗАПРОСЫ
# ============================================================================

# ============================================================================
# НОВЫЕ ПРАВИЛА v3.2.0 — тексты запросов и специфичные конструкции
# ============================================================================

# Перейти — запрещён (STD 456, ограничение на использование оператора Перейти)
PEREYTI_PATTERN = re.compile(r"\bПерейти\s+", re.IGNORECASE)

# ЗаписьЖурналаРегистрации без явной задачи
ZAPIS_ZHURNALA_PATTERN = re.compile(r"\bЗаписьЖурналаРегистрации\s*\(", re.IGNORECASE)

# ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ в запросах
FULL_OUTER_JOIN_PATTERN = re.compile(r"ПОЛНОЕ\s+ВНЕШНЕЕ\s+СОЕДИНЕНИЕ", re.IGNORECASE)

# ОБЪЕДИНИТЬ без ВСЕ (должно быть ОБЪЕДИНИТЬ ВСЕ)
OBYEDINIT_BEZ_VSE_PATTERN = re.compile(r"\bОБЪЕДИНИТЬ\b(?!\s+ВСЕ)", re.IGNORECASE)

# Отсутствие КАК в запросе (источники без псевдонимов)
# Ищем "ИЗ Справочник.Имя" без "КАК"
NO_ALIAS_PATTERN = re.compile(r"\b(?:ИЗ|СОЕДИНЕНИЕ|ОБЪЕДИНИТЬ)\s+\S+\s+(?![А-Я])", re.IGNORECASE)

# ОбменДанными.Загрузка в обработчиках событий — должна проверяться
OBMEN_DANNIMI_PATTERN = re.compile(r"\bОбменДанными\.Загрузка\b", re.IGNORECASE)

# Использование Сообщить для предложений внешних компонент
PREDLOZHENIE_VNECHN_PATTERN = re.compile(r"ПоказатьВопрос\(|ПоказатьПредупреждение\(", re.IGNORECASE)


def rule_no_pereyti(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Запрещён оператор Перейти (STD 456 — ограничение на использование)."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if PEREYTI_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-pereyti",
                severity="error",
                message="Оператор Перейти запрещён — используйте Если/Цикл/Процедура (STD 456)",
            )


def rule_no_zapis_zhurnala(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ЗаписьЖурналаРегистрации без явной задачи — запрещено."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if ZAPIS_ZHURNALA_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-zapis-zhurnala",
                severity="warning",
                message="ЗаписьЖурналаРегистрации() — используйте только по явной задаче (STD 456)",
            )


def rule_no_full_outer_join(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ в запросах — ограничено (STD 03)."""
    # Ищем в строках запросов (внутри кавычек)
    full_text = "\n".join(lines)
    # Простая эвристика — ищем в многострочных текстах запросов
    for match in FULL_OUTER_JOIN_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-full-outer-join",
            severity="warning",
            message="ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ — ограничено, используйте ЛЕВОЕ/ПРАВОЕ (STD 03)",
        )


def rule_no_obyedinit_bez_vse(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ОБЪЕДИНИТЬ без ВСЕ — обычно нужно ОБЪЕДИНИТЬ ВСЕ."""
    full_text = "\n".join(lines)
    for match in OBYEDINIT_BEZ_VSE_PATTERN.finditer(full_text):
        line_num = full_text[: match.start()].count("\n") + 1
        yield Violation(
            file=str(file_path),
            line=line_num,
            col=1,
            rule_id="no-obyedinit-bez-vse",
            severity="warning",
            message="ОБЪЕДИНИТЬ без ВСЕ — проверьте, возможно нужно ОБЪЕДИНИТЬ ВСЕ (STD 03)",
        )


def rule_no_query_without_alias(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Источники данных в запросе без псевдонима КАК."""
    full_text = "\n".join(lines)
    # Ищем только в строках, которые выглядят как текст запроса
    in_query = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # Определяем начало/конец текста запроса
        if "Запрос.Текст" in line or '"ВЫБРАТЬ' in line or "ВЫБРАТЬ" in stripped:
            in_query = True
        if in_query:
            for match in NO_ALIAS_PATTERN.finditer(line):
                # Пропускаем если после идёт КАК
                after = line[match.end() : match.end() + 10]
                if "КАК" in after.upper() or "ГДЕ" in after.upper():
                    continue
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=match.start() + 1,
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
        if stripped.startswith("//"):
            continue
        if OBMEN_DANNIMI_PATTERN.search(line):
            # Проверяем — есть ли Если не ОбменДанными.Загрузка рядом
            # Простая эвристика — если в следующих 3 строках нет проверки
            context = lines[i - 1 : min(i + 3, len(lines))]
            context_text = " ".join(context)
            if "Если" not in context_text or "ОбменДанными" not in context_text:
                yield Violation(
                    file=str(file_path),
                    line=i,
                    col=1,
                    rule_id="no-obmen-dannimi-bez-proverki",
                    severity="warning",
                    message="ОбменДанными.Загрузка без проверки — добавьте Если Не ОбменДанными.Загрузка (STD 01)",
                )


def rule_no_predlozhenie_vnechn(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """ПоказатьВопрос/ПоказатьПредупреждение — проверка наличия."""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if PREDLOZHENIE_VNECHN_PATTERN.search(line):
            yield Violation(
                file=str(file_path),
                line=i,
                col=1,
                rule_id="no-predlozhenie-vnechn",
                severity="warning",
                message="ПоказатьВопрос/ПоказатьПредупреждение — проверьте стандарты UI (STD 08)",
            )


# Список правил в этом модуле
RULES = [
    rule_no_pereyti,
    rule_no_zapis_zhurnala,
    rule_no_full_outer_join,
    rule_no_obyedinit_bez_vse,
    rule_no_query_without_alias,
    rule_no_obmen_dannimi_bez_proverki,
    rule_no_predlozhenie_vnechn,
]
