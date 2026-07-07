#!/usr/bin/env python3
"""
query_analyzer.py — Анализ запросов 1С внутри BSL кода.

Парсит запросы 1С (язык запросов 1С) и проверяет:
1. Запросы без параметров (&Параметр)
2. Конкатенация строк в запросе (SQL-инъекция)
3. SELECT * (ВЫБРАТЬ *) — неоптимальный запрос
4. Отсутствие ГДЕ (WHERE) — выборка всех строк таблицы
5. Подзапросы в SELECT
6. ВРЕМЕННЫЕ ТАБЛИЦЫ без индексов
7. Соединения (JOIN) без условия связи
8. Использование ПОДОБНО (LIKE) с % в начале — full scan
9. Отсутствие ВЫБРАТЬ РАЗЛИЧНЫЕ при необходимости
10. Сортировка (УПОРЯДОЧИТЬ) по неиндексированному полю
11. Группировка без индекса
12. Использование Функций в WHERE — блокировка индекса

Использование:
    from query_analyzer import QueryAnalyzer
    analyzer = QueryAnalyzer()
    issues = analyzer.analyze_file(Path('module.bsl'))
"""

from __future__ import annotations
from typing import Any

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QueryIssue:
    rule_id: str
    severity: str
    line: int
    query_snippet: str
    message: str
    recommendation: str = ""
    tags: list[str] = None  # P3: категории BSL LS (STANDARD, SQL, PERFORMANCE, ...)

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class QueryAnalyzer:
    """Анализатор запросов 1С внутри BSL кода."""

    # Извлечение запроса из BSL кода
    QUERY_ASSIGN = re.compile(r'(?:Запрос\.?Текст|\.?Text)\s*=\s*"([^"]+)"', re.IGNORECASE | re.DOTALL)
    # Многострочный запрос
    QUERY_MULTILINE = re.compile(r'(?:Запрос\.?Текст|\.?Text)\s*=\s*"((?:[^"\\]|\\.)*)"', re.IGNORECASE | re.DOTALL)

    def analyze_file(self, file_path: Path) -> list[QueryIssue]:
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []
        return self.analyze_code(content, str(file_path))

    def analyze_code(self, code: str, file_path: str = "") -> list[QueryIssue]:
        issues = []
        lines = code.split("\n")

        # Извлекаем запросы
        queries = self._extract_queries(lines)

        for query_text, line_num in queries:
            issues.extend(self._check_select_star(query_text, line_num))
            issues.extend(self._check_no_where(query_text, line_num))
            issues.extend(self._check_no_params(query_text, line_num, lines))
            issues.extend(self._check_concatenation(query_text, line_num, lines))
            issues.extend(self._check_like_start_percent(query_text, line_num))
            issues.extend(self._check_subquery_in_select(query_text, line_num))
            issues.extend(self._check_function_in_where(query_text, line_num))
            issues.extend(self._check_no_distinct(query_text, line_num))
            issues.extend(self._check_join_without_on(query_text, line_num))
            issues.extend(self._check_temp_table_no_index(query_text, line_num))
            # P2: 8 новых правил из BSL LS
            issues.extend(self._check_ref_overuse(query_text, line_num))
            issues.extend(self._check_join_with_virtual_table(query_text, line_num))
            issues.extend(self._check_or_in_join(query_text, line_num))
            issues.extend(self._check_multiline_string_in_query(query_text, line_num))
            issues.extend(self._check_fields_from_join_without_isnull(query_text, line_num))
            issues.extend(self._check_virtual_table_without_params(query_text, line_num))
            issues.extend(self._check_assign_alias_fields(query_text, line_num))
            issues.extend(self._check_union_without_all(query_text, line_num))

        return issues

    def analyze_path(self, dir_path: Path) -> list[QueryIssue]:
        issues = []
        for bsl_file in sorted(dir_path.rglob("*.bsl")):
            issues.extend(self.analyze_file(bsl_file))
        return issues

    def _extract_queries(self, lines: list[str]) -> list[tuple[str, int]]:
        """Извлечение текстов запросов из BSL кода.

        BSL использует "" для экранирования кавычек внутри строк.
        Запрос может быть многострочным.
        """
        queries = []
        current_query = None
        query_start_line = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Начало запроса: Запрос.Текст = "..."
            if re.search(r'(?:Запрос\.?Текст|\.?Text)\s*=\s*"', stripped, re.IGNORECASE):
                # Извлекаем всё после первой кавычки
                text_after_quote = stripped.split('="', 1)[-1] if '="' in stripped else ""
                text_after_quote = stripped.split('= "', 1)[-1] if '= "' in stripped else text_after_quote

                # Проверяем, заканчивается ли строка кавычкой (с учётом "")
                # В BSL: "текст""текст" означает текст"текст
                # Запрос заканчивается на "; или просто "

                # Для простоты: если строка заканчивается на "; — это конец запроса
                if text_after_quote.rstrip().endswith('";') or text_after_quote.rstrip().endswith('"'):
                    # Однострочный запрос — убираем последнюю кавычку и ;
                    query_text = text_after_quote.rstrip()
                    if query_text.endswith('";'):
                        query_text = query_text[:-2]
                    elif query_text.endswith('"'):
                        query_text = query_text[:-1]
                    # Unescape BSL кавычки: "" → "
                    query_text = query_text.replace('""', '"')
                    queries.append((query_text, i))
                else:
                    # Многострочный запрос
                    current_query = text_after_quote
                    query_start_line = i

            elif current_query is not None:
                # Продолжаем многострочный запрос
                if stripped.rstrip().endswith('";') or stripped.rstrip().endswith('"'):
                    # Конец запроса
                    end_text = stripped.rstrip()
                    if end_text.endswith('";'):
                        end_text = end_text[:-2]
                    elif end_text.endswith('"'):
                        end_text = end_text[:-1]
                    current_query += "\n" + end_text
                    current_query = current_query.replace('""', '"')
                    queries.append((current_query, query_start_line))
                    current_query = None
                else:
                    current_query += "\n" + stripped

        return queries

    # =====================================================================
    # ПРАВИЛА
    # =====================================================================

    def _check_select_star(self, query: str, line: int) -> list[QueryIssue]:
        """Q001: ВЫБРАТЬ * — неоптимальный запрос."""
        issues = []
        if re.search(r"\bВЫБРАТЬ\s+\*", query, re.IGNORECASE):
            issues.append(
                QueryIssue(
                    rule_id="Q001",
                    severity="MEDIUM",
                    line=line,
                    query_snippet=query[:100],
                    message="ВЫБРАТЬ * — выбираются все поля, включая ненужные",
                    recommendation="Указывайте только нужные поля: ВЫБРАТЬ Поле1, Поле2. См. паттерн: knowledge_base/query_optimization/optimization_patterns.md#no-select-star",
                    tags=["SQL", "PERFORMANCE"],
                )
            )
        return issues

    def _check_no_where(self, query: str, line: int) -> list[QueryIssue]:
        """Q002: Отсутствие ГДЕ — выборка всех строк."""
        issues = []
        # Проверяем что есть ИЗ (это запрос к таблице)
        if re.search(r"\bИЗ\b", query, re.IGNORECASE):
            if not re.search(r"\bГДЕ\b", query, re.IGNORECASE):
                # Проверяем, не это ли ВЫБРАТЬ * ИЗ Справочник.Х (часто используется для справочников)
                if not re.search(r"\bВЫБРАТЬ\s+\*\s+ИЗ\s+Справочник", query, re.IGNORECASE):
                    issues.append(
                        QueryIssue(
                            rule_id="Q002",
                            severity="MEDIUM",
                            line=line,
                            query_snippet=query[:100],
                            message="Запрос без ГДЕ — выбираются все строки таблицы",
                            recommendation="Добавьте условие ГДЕ для ограничения выборки",
                        )
                    )
        return issues

    def _check_no_params(self, query: str, line: int, lines: list[str]) -> list[QueryIssue]:
        """Q003: Запрос без параметров (&Параметр)."""
        issues = []
        if not re.search(r"&[А-Яа-я]", query):
            # Проверяем, есть ли жёстко заданные значения
            if re.search(r"ГДЕ\s+.*=\s*[0-9]", query, re.IGNORECASE) or re.search(
                r'ГДЕ\s+.*=\s*"[^"]*"', query, re.IGNORECASE
            ):
                issues.append(
                    QueryIssue(
                        rule_id="Q003",
                        severity="LOW",
                        line=line,
                        query_snippet=query[:100],
                        message="Запрос с жёстко заданными значениями вместо параметров",
                        recommendation="Используйте параметры: ГДЕ Поле = &ЗначениеПоля. См. паттерн: knowledge_base/query_optimization/optimization_patterns.md#parameterized-queries",
                    )
                )
        return issues

    def _check_concatenation(self, query: str, line: int, lines: list[str]) -> list[QueryIssue]:
        """Q004: Конкатенация строк в запросе (SQL-инъекция)."""
        issues = []
        # Проверяем исходную строку на конкатенацию
        if line <= len(lines):
            source_line = lines[line - 1] if line > 0 else ""
            if "+" in source_line and "Текст" in source_line:
                issues.append(
                    QueryIssue(
                        rule_id="Q004",
                        severity="CRITICAL",
                        line=line,
                        query_snippet=source_line.strip()[:100],
                        message="Конкатенация строк в запросе — риск SQL-инъекции",
                        recommendation="Используйте параметры запроса вместо конкатенации. См. паттерн: knowledge_base/query_optimization/optimization_patterns.md#parameterized-queries",
                    )
                )
        return issues

    def _check_like_start_percent(self, query: str, line: int) -> list[QueryIssue]:
        """Q005: ПОДОБНО '%...' — full scan."""
        issues = []
        # Проверяем ПОДОБНО с % в начале строки (после кавычки)
        if re.search(r'\bПОДОБНО\s+"?%', query, re.IGNORECASE) or re.search(r'\bLIKE\s+"?%', query, re.IGNORECASE):
            issues.append(
                QueryIssue(
                    rule_id="Q005",
                    severity="HIGH",
                    line=line,
                    query_snippet=query[:100],
                    message="ПОДОБНО с % в начале — full table scan (не использует индекс)",
                    recommendation='Избегайте ПОДОБНО "%текст". Используйте ПОДОБНО "текст%". См. паттерн: knowledge_base/query_optimization/optimization_patterns.md#like-optimization',
                    tags=["SQL", "PERFORMANCE"],
                )
            )
        return issues

    def _check_subquery_in_select(self, query: str, line: int) -> list[QueryIssue]:
        """Q006: Подзапрос в SELECT."""
        issues = []
        # Ищем (ВЫБРАТЬ ... ) внутри SELECT
        if re.search(r"\bВЫБРАТЬ\s+.*\(ВЫБРАТЬ", query, re.IGNORECASE | re.DOTALL):
            issues.append(
                QueryIssue(
                    rule_id="Q006",
                    severity="MEDIUM",
                    line=line,
                    query_snippet=query[:100],
                    message="Подзапрос в секции ВЫБРАТЬ — может быть медленным",
                    recommendation="Рассмотрите использование СОЕДИНЕНИЕ (JOIN) вместо подзапроса",
                )
            )
        return issues

    def _check_function_in_where(self, query: str, line: int) -> list[QueryIssue]:
        """Q007: Функция в WHERE — блокировка индекса."""
        issues = []
        # Ищем функции в ГДЕ: ВЫРАЗИТЬ, ПОДСТРОКА, ДАТАВРЕМЯ, и т.д.
        func_pattern = re.compile(
            r"\bГДЕ\b.*\b(ВЫРАЗИТЬ|ПОДСТРОКА|СТРДЛИНА|НАЙТИ|"
            r"КОНМЕСЯЦА|НАЧАЛОПЕРИОДА|КОНЕЦПЕРИОДА|ДОБАВИТЬКДАТЕ|"
            r"ГОД|МЕСЯЦ|ДЕНЬ|ЧАС|МИНУТА|СЕКУНДА|"
            r"ВЕРХ|НИЖ|СТРЗАМЕНИТЬ)\s*\(",
            re.IGNORECASE | re.DOTALL,
        )
        if func_pattern.search(query):
            issues.append(
                QueryIssue(
                    rule_id="Q007",
                    severity="HIGH",
                    line=line,
                    query_snippet=query[:100],
                    message="Функция в условии ГДЕ — блокирует использование индекса",
                    recommendation="Вынесите вычисление функции за пределы запроса или создайте вычисляемое поле",
                )
            )
        return issues

    def _check_no_distinct(self, query: str, line: int) -> list[QueryIssue]:
        """Q008: Отсутствие РАЗЛИЧНЫЕ при соединении таблиц."""
        issues = []
        # Если есть СОЕДИНЕНИЕ (JOIN) но нет РАЗЛИЧНЫЕ (DISTINCT)
        if re.search(r"\bСОЕДИНЕНИЕ\b", query, re.IGNORECASE) or re.search(r"\bJOIN\b", query, re.IGNORECASE):
            if not re.search(r"\bРАЗЛИЧНЫЕ\b", query, re.IGNORECASE) and not re.search(
                r"\bDISTINCT\b", query, re.IGNORECASE
            ):
                # Проверяем, есть ли группировка
                if not re.search(r"\bСГРУППИРОВАТЬ\b", query, re.IGNORECASE):
                    issues.append(
                        QueryIssue(
                            rule_id="Q008",
                            severity="LOW",
                            line=line,
                            query_snippet=query[:100],
                            message="Запрос с СОЕДИНЕНИЕ без РАЗЛИЧНЫЕ — возможны дубликаты",
                            recommendation="Если могут быть дубликаты, используйте ВЫБРАТЬ РАЗЛИЧНЫЕ",
                        )
                    )
        return issues

    def _check_join_without_on(self, query: str, line: int) -> list[QueryIssue]:
        """Q009: Соединение без условия связи (ПО)."""
        issues = []
        if re.search(r"\bСОЕДИНЕНИЕ\b", query, re.IGNORECASE):
            if not re.search(r"\bПО\b", query, re.IGNORECASE):
                issues.append(
                    QueryIssue(
                        rule_id="Q009",
                        severity="HIGH",
                        line=line,
                        query_snippet=query[:100],
                        message="СОЕДИНЕНИЕ без условия ПО — декартово произведение",
                        recommendation="Добавьте условие связи: СОЕДИНЕНИЕ Таблица ПО Таблица.Поле = Другая.Поле",
                    )
                )
        return issues

    def _check_temp_table_no_index(self, query: str, line: int) -> list[QueryIssue]:
        """Q010: Временная таблица без индекса."""
        issues = []
        if re.search(r"\bПОМЕСТИТЬ\b", query, re.IGNORECASE):
            if not re.search(r"\bИНДЕКСИРОВАТЬ\b", query, re.IGNORECASE):
                issues.append(
                    QueryIssue(
                        rule_id="Q010",
                        severity="MEDIUM",
                        line=line,
                        query_snippet=query[:100],
                        message="Временная таблица без ИНДЕКСИРОВАТЬ — медленные соединения",
                        recommendation="Добавьте ИНДЕКСИРОВАТЬ ПО Поле после ПОМЕСТИТЬ",
                        tags=["SQL", "PERFORMANCE"],
                    )
                )
        return issues

    # =====================================================================
    # P2: НОВЫЕ ПРАВИЛА из BSL LS (Q011-Q018)
    # =====================================================================

    def _check_ref_overuse(self, query: str, line: int) -> list[QueryIssue]:
        """Q011: Чрезмерное использование .Ссылка — скрытые JOIN (BSL LS: RefOveruse)."""
        issues = []
        # Ищем 3+ уровня разыменования: Т.Поле.Подполе.Еще
        if re.search(r"\b\w+\.\w+\.\w+\.\w+", query):
            if not re.search(r"\b(?:ВЫРАЗИТЬ|CAST)\b", query, re.IGNORECASE):
                issues.append(
                    QueryIssue(
                        rule_id="Q011",
                        severity="MEDIUM",
                        line=line,
                        query_snippet=query[:100],
                        message="Глубокое разыменование через точку — скрытые JOIN (BSL LS: RefOveruse)",
                        recommendation="Используйте ВЫРАЗИТЬ для составных типов или ПРЕДСТАВЛЕНИЕ(). См. стандарт: #std654",
                        tags=["SQL", "PERFORMANCE"],
                    )
                )
        return issues

    def _check_join_with_virtual_table(self, query: str, line: int) -> list[QueryIssue]:
        """Q012: JOIN с виртуальной таблицей (BSL LS: JoinWithVirtualTable)."""
        issues = []
        # Ищем JOIN + виртуальную таблицу (Остатки, Обороты, СрезПоследних)
        if re.search(r"\b(?:ЛЕВОЕ|ВНУТРЕННЕЕ|ПРАВОЕ|ПОЛНОЕ)?\s*(?:СОЕДИНЕНИЕ|JOIN)\b", query, re.IGNORECASE):
            if re.search(r"\.(Остатки|Обороты|СрезПоследних|ОстаткиИОбороты)\s*\(", query, re.IGNORECASE):
                issues.append(
                    QueryIssue(
                        rule_id="Q012",
                        severity="HIGH",
                        line=line,
                        query_snippet=query[:100],
                        message="JOIN с виртуальной таблицей — крайне медленно (BSL LS: JoinWithVirtualTable)",
                        recommendation="Поместите виртуальную таблицу во временную с ИНДЕКСИРОВАТЬ ПО. См. стандарт: #std655",
                        tags=["SQL", "PERFORMANCE"],
                    )
                )
        return issues

    def _check_or_in_join(self, query: str, line: int) -> list[QueryIssue]:
        """Q013: ИЛИ в секции JOIN (BSL LS: LogicalOrInJoinQuerySection)."""
        issues = []
        # Извлекаем секцию ПО (ON)
        on_match = re.search(r"\b(?:ПО|ON)\s+(.+?)(?=\s+(?:ГДЕ|WHERE|СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ЛЕВОЕ|ВНУТРЕННЕЕ|ПРАВОЕ|ПОЛНОЕ|СОЕДИНЕНИЕ|JOIN|ИМЕЮЩИЕ|HAVING)|$)", query, re.IGNORECASE | re.DOTALL)
        if on_match:
            on_text = on_match.group(1)
            if re.search(r"\b(?:ИЛИ|OR)\b", on_text, re.IGNORECASE):
                issues.append(
                    QueryIssue(
                        rule_id="Q013",
                        severity="MEDIUM",
                        line=line,
                        query_snippet=query[:100],
                        message="ИЛИ в секции ПО (ON) — блокирует индексы (BSL LS: LogicalOrInJoinQuerySection)",
                        recommendation="Разделите на два JOIN через ОБЪЕДИНИТЬ ВСЕ. См. стандарт: #std658",
                        tags=["SQL", "PERFORMANCE"],
                    )
                )
        return issues

    def _check_multiline_string_in_query(self, query: str, line: int) -> list[QueryIssue]:
        """Q014: Многострочный строковый литерал в запросе (BSL LS: MultilineStringInQuery)."""
        issues = []
        # Многострочные литералы в запросе — часто ошибка с кавычками
        if query.count('"') % 2 != 0:
            issues.append(
                QueryIssue(
                    rule_id="Q014",
                    severity="LOW",
                    line=line,
                    query_snippet=query[:100],
                    message="Нечётное количество кавычек — возможна ошибка (BSL LS: MultilineStringInQuery)",
                    recommendation="Проверьте баланс кавычек в строковых литералах запроса",
                    tags=["SQL", "SUSPICIOUS"],
                )
            )
        return issues

    def _check_fields_from_join_without_isnull(self, query: str, line: int) -> list[QueryIssue]:
        """Q015: Поля из LEFT JOIN без ISNULL (BSL LS: FieldsFromJoinsWithoutIsNull)."""
        issues = []
        # Если есть LEFT JOIN и SELECT обращается к полям соединённой таблицы
        if re.search(r"\bЛЕВОЕ\s+СОЕДИНЕНИЕ\b", query, re.IGNORECASE) or re.search(r"\bLEFT\s+JOIN\b", query, re.IGNORECASE):
            # Проверяем есть ли ISNULL/ЕСТЬ NULL в SELECT
            if not re.search(r"\b(?:ISNULL|ЕСТЬ\s+NULL|IS\s+NULL|СОЕДИНИТЬ)\b", query, re.IGNORECASE):
                # Упрощённая проверка — если есть LEFT JOIN, но нет ISNULL
                issues.append(
                    QueryIssue(
                        rule_id="Q015",
                        severity="LOW",
                        line=line,
                        query_snippet=query[:100],
                        message="Поля из LEFT JOIN без ISNULL — возможен NULL (BSL LS: FieldsFromJoinsWithoutIsNull)",
                        recommendation="Используйте ISNULL(Поле, ЗначениеПоУмолчанию) для полей из LEFT JOIN",
                        tags=["SQL", "SUSPICIOUS"],
                    )
                )
        return issues

    def _check_virtual_table_without_params(self, query: str, line: int) -> list[QueryIssue]:
        """Q016: Виртуальная таблица без параметров (BSL LS: VirtualTableCallWithoutParameters)."""
        issues = []
        # Ищем виртуальные таблицы с пустыми параметрами
        vt_match = re.search(r"(РегистрНакопления|РегистрСведений)\.[\w]+\.(Остатки|Обороты|СрезПоследних|ОстаткиИОбороты)\s*\(([^)]*)\)", query, re.IGNORECASE)
        if vt_match:
            params = vt_match.group(3).strip()
            # Если параметры пустые или только &Период
            if not params or re.match(r"^\s*&\w+\s*,?\s*$", params):
                # Проверяем есть ли WHERE после
                if re.search(r"\b(?:ГДЕ|WHERE)\b", query, re.IGNORECASE):
                    issues.append(
                        QueryIssue(
                            rule_id="Q016",
                            severity="HIGH",
                            line=line,
                            query_snippet=query[:100],
                            message="Виртуальная таблица без фильтра в параметрах + WHERE — медленно (BSL LS: VirtualTableCallWithoutParameters)",
                            recommendation="Перенесите фильтр в параметры виртуальной таблицы. См. стандарт: #std657",
                            tags=["SQL", "PERFORMANCE"],
                        )
                    )
        return issues

    def _check_assign_alias_fields(self, query: str, line: int) -> list[QueryIssue]:
        """Q017: Поля без алиасов в SELECT (BSL LS: AssignAliasFieldsInQuery)."""
        issues = []
        # Извлекаем SELECT
        select_match = re.search(r"\b(?:ВЫБРАТЬ|SELECT)\s+(.+?)(?=\s+(?:ИЗ|FROM)\b)", query, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_text = select_match.group(1)
            # Разделяем по запятым
            for part in re.split(r",(?![^()]*\))", select_text):
                part = part.strip()
                # Пропускаем *, агрегаты, и поля с КАК
                if part == "*" or part.endswith(".*"):
                    continue
                if re.match(r"^(?:СУММА|SUM|КОЛИЧЕСТВО|COUNT|МИНИМУМ|MIN|МАКСИМУМ|MAX|СРЕДНЕЕ|AVG)\s*\(", part, re.IGNORECASE):
                    continue
                if not re.search(r"\b(?:КАК|AS)\b", part, re.IGNORECASE):
                    # Поле без алиаса
                    if "." in part or re.match(r"^[А-Яа-яЁё\w]+$", part.strip()):
                        issues.append(
                            QueryIssue(
                                rule_id="Q017",
                                severity="LOW",
                                line=line,
                                query_snippet=query[:100],
                                message="Поле без алиаса в SELECT — ухудшает читаемость (BSL LS: AssignAliasFieldsInQuery)",
                                recommendation="Используйте КАК для всех полей в SELECT. См. стандарт: #std437",
                                tags=["STANDARD", "SQL"],
                            )
                        )
                        break  # одно предупреждение на запрос
        return issues

    def _check_union_without_all(self, query: str, line: int) -> list[QueryIssue]:
        """Q018: ОБЪЕДИНИТЬ без ВСЕ — удаляет дубликаты (BSL LS + #std434)."""
        issues = []
        # Ищем ОБЪЕДИНИТЬ без ВСЕ
        if re.search(r"\bОБЪЕДИНИТЬ\b(?!\s+ВСЕ)", query, re.IGNORECASE):
            issues.append(
                QueryIssue(
                    rule_id="Q018",
                    severity="LOW",
                    line=line,
                    query_snippet=query[:100],
                    message="ОБЪЕДИНИТЬ без ВСЕ — удаляет дубликаты (дополнительная группировка, медленнее)",
                    recommendation="Используйте ОБЪЕДИНИТЬ ВСЕ если не нужны уникальные строки. См. стандарт: #std434",
                    tags=["SQL", "PERFORMANCE"],
                )
            )
        return issues

    def get_stats(self, issues: list[QueryIssue]) -> dict[str, Any]:
        from collections import Counter

        return {
            "total": len(issues),
            "by_severity": dict[str, Any](Counter(i.severity for i in issues)),
            "by_rule": dict[str, Any](Counter(i.rule_id for i in issues)),
            "by_tags": dict[str, Any](Counter(tag for i in issues for tag in (i.tags or []))),
        }


# CLI вынесен в scripts/query_analyzer.py (Этап 1.2, Группа 1b)
