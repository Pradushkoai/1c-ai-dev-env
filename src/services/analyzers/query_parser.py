"""
query_parser.py — Парсер запросов 1С (язык запросов 1С:Предприятие).

P1.5 (Шаг 2): извлекает из текста запроса 1С структурированную информацию,
необходимую статическому валидатору для проверки:

- Имена таблиц и алиасы (FROM / JOIN)
- Поля в SELECT, WHERE, GROUP BY, ORDER BY
- Виртуальные таблицы (Остатки, Обороты, СрезПоследних, ...)
- Параметры виртуальных таблиц (например, &Период в Остатки(&Период, ...))
- Агрегатные функции (СУММА, КОЛИЧЕСТВО, МИНИМУМ, МАКСИМУМ, СРЕДНЕЕ)
- JOIN-условия (ЛЕВОЕ/ВНУТРЕННЕЕ/ПОЛНОЕ ... ПО ...)
- Параметры запроса (&Параметр)
- Временные таблицы (ПОМЕСТИТЬ / ВРЕМЕННАЯТАБЛИЦА)
- Пакетные запросы (несколько ВЫБРАТЬ подряд)

Поддерживает как русские (ВЫБРАТЬ, ИЗ, ГДЕ), так и английские
(SELECT, FROM, WHERE) ключевые слова.

Лицензия: MIT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class QueryField:
    """Поле в запросе 1С."""

    # Полное имя поля: 'Рег.Номенклатура', 'Рег.Сумма', 'Номенклатура.Наименование'
    raw: str
    # Алиас таблицы (часть до '.') или пусто, если без алиаса
    table_alias: str = ""
    # Имя поля (часть после '.') или всё raw, если без алиаса
    field_name: str = ""
    # Алиас поля (после КАК / AS)
    alias: str = ""
    # Если это агрегатная функция — её имя и аргумент
    aggregate: str = ""
    aggregate_arg: str = ""
    # Контекст: 'select', 'where', 'group_by', 'order_by', 'having', 'join_on'
    context: str = ""
    # Строка в исходном тексте (1-based)
    line: int = 0

    def __post_init__(self):
        if not self.field_name and "." in self.raw:
            parts = self.raw.split(".", 1)
            self.table_alias = parts[0]
            self.field_name = parts[1]
        elif not self.field_name:
            self.field_name = self.raw


@dataclass
class QueryTable:
    """Таблица в запросе 1С (источник данных)."""

    # Полное имя источника: 'РегистрНакопления.ВыручкаСебестоимость'
    full_name: str
    # Тип объекта: 'РегистрНакопления', 'Справочник', 'Документ', и т.д.
    object_type: str = ""
    # Имя объекта: 'ВыручкаСебестоимость'
    object_name: str = ""
    # Имя виртуальной таблицы (если есть): 'Остатки', 'Обороты', 'СрезПоследних'
    virtual_table: str = ""
    # Параметры виртуальной таблицы (текст внутри скобок)
    virtual_table_params: str = ""
    # Алиас таблицы (после КАК / AS)
    alias: str = ""
    # Тип соединения: '' (для FROM), 'LEFT', 'INNER', 'RIGHT', 'FULL'
    join_type: str = ""
    # Условие соединения (после ПО / ON) — для JOIN
    join_condition: str = ""
    # Строка в исходном тексте
    line: int = 0

    def __post_init__(self):
        if not self.object_type and "." in self.full_name:
            parts = self.full_name.split(".", 1)
            self.object_type = parts[0]
            # Если 3 части (РегистрНакопления.Имя.Остатки) — это виртуальная таблица
            rest = parts[1]
            if "." in rest:
                name_parts = rest.split(".", 1)
                self.object_name = name_parts[0]
                self.virtual_table = name_parts[1]
            else:
                self.object_name = rest


@dataclass
class ParsedQuery:
    """Распарсенный запрос 1С (один SELECT)."""

    # Список таблиц (FROM + JOINs)
    tables: list[QueryTable] = field(default_factory=list)
    # Поля в SELECT
    select_fields: list[QueryField] = field(default_factory=list)
    # Поля в WHERE (упрощённо — как строки)
    where_fields: list[QueryField] = field(default_factory=list)
    # Поля в GROUP BY
    group_by_fields: list[QueryField] = field(default_factory=list)
    # Поля в ORDER BY
    order_by_fields: list[QueryField] = field(default_factory=list)
    # Поля в HAVING
    having_fields: list[QueryField] = field(default_factory=list)
    # Параметры запроса (&Параметр)
    parameters: list[str] = field(default_factory=list)
    # Временные таблицы (созданные через ПОМЕСТИТЬ)
    temp_tables: list[str] = field(default_factory=list)
    # Имена таблиц, на которые ссылается INTO / ПОМЕСТИТЬ (для INSERT INTO)
    into_temp_table: str = ""
    # Сырой текст запроса
    raw_text: str = ""
    # Количество строк в исходном тексте
    line_count: int = 0

    def get_table_by_alias(self, alias: str) -> QueryTable | None:
        """Возвращает таблицу по алиасу."""
        for t in self.tables:
            if t.alias == alias or t.object_name == alias or t.full_name == alias:
                return t
        return None


@dataclass
class ParsedBatch:
    """Пакет запросов 1С (несколько SELECT подряд)."""

    queries: list[ParsedQuery] = field(default_factory=list)
    raw_text: str = ""

    def get_all_tables(self) -> list[QueryTable]:
        """Все таблицы из всех запросов пакета."""
        result: list[QueryTable] = []
        for q in self.queries:
            result.extend(q.tables)
        return result

    def get_temp_table_definition(self, name: str) -> ParsedQuery | None:
        """Возвращает запрос, который создаёт временную таблицу с данным именем."""
        for q in self.queries:
            if q.into_temp_table == name:
                return q
        return None


# ============================================================================
# КЛЮЧЕВЫЕ СЛОВА
# ============================================================================

# Русские и английские ключевые слова
KEYWORDS_SELECT = {"ВЫБРАТЬ", "SELECT", "ВЫБРАТЬРАЗЛИЧНЫЕ", "SELECTDISTINCT"}
KEYWORDS_FROM = {"ИЗ", "FROM"}
KEYWORDS_WHERE = {"ГДЕ", "WHERE"}
KEYWORDS_GROUP = {"СГРУППИРОВАТЬ", "GROUP"}
KEYWORDS_BY = {"ПО", "BY"}
KEYWORDS_ORDER = {"УПОРЯДОЧИТЬ", "ORDER"}
KEYWORDS_HAVING = {"ИМЕЮЩИЕ", "HAVING"}
# Типы соединений: имя (рус/англ) → тип
JOIN_TYPES: dict[str, str] = {
    "ЛЕВОЕ": "LEFT",
    "LEFT": "LEFT",
    "ВНУТРЕННЕЕ": "INNER",
    "INNER": "INNER",
    "ПРАВОЕ": "RIGHT",
    "RIGHT": "RIGHT",
    "ПОЛНОЕ": "FULL",
    "FULL": "FULL",
    "СОЕДИНЕНИЕ": "INNER",  # СОЕДИНЕНИЕ без спецификации — внутреннее
    "JOIN": "INNER",
}
# Set ключевых слов JOIN для быстрой проверки
KEYWORDS_JOIN: set[str] = set(JOIN_TYPES.keys())
KEYWORDS_ON = {"ПО", "ON"}
KEYWORDS_AS = {"КАК", "AS"}
KEYWORDS_INTO = {"ПОМЕСТИТЬ", "INTO"}
KEYWORDS_UNION = {"ОБЪЕДИНИТЬ", "UNION"}
KEYWORDS_ALL = {"ВСЕ", "ALL"}

# Агрегатные функции
AGGREGATE_FUNCTIONS = {
    "СУММА": "SUM",
    "SUM": "SUM",
    "КОЛИЧЕСТВО": "COUNT",
    "COUNT": "COUNT",
    "МИНИМУМ": "MIN",
    "MIN": "MIN",
    "МАКСИМУМ": "MAX",
    "MAX": "MAX",
    "СРЕДНЕЕ": "AVG",
    "AVG": "AVG",
}

# Типы объектов 1С, которые могут быть источниками в запросе
OBJECT_TYPES_RU = {
    "Справочник",
    "Документ",
    "ЖурналДокументов",
    "Перечисление",
    "РегистрСведений",
    "РегистрНакопления",
    "РегистрБухгалтерии",
    "РегистрРасчета",
    "ПланСчетов",
    "ПланВидовХарактеристик",
    "ПланВидовРасчета",
    "ПланОбмена",
    "БизнесПроцесс",
    "Задача",
    "Константа",
    "Обработка",  # только для временных таблиц
    "Отчет",
}
OBJECT_TYPES_EN = {
    "Catalog",
    "Document",
    "DocumentJournal",
    "Enum",
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
    "ChartOfAccounts",
    "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes",
    "ExchangePlan",
    "BusinessProcess",
    "Task",
    "Constant",
    "DataProcessor",
    "Report",
}
ALL_OBJECT_TYPES = OBJECT_TYPES_RU | OBJECT_TYPES_EN


# ============================================================================
# ПАРСЕР
# ============================================================================


class QueryParser:
    """Парсер запросов 1С."""

    def parse(self, query_text: str) -> ParsedBatch:
        """Разбирает текст запроса 1С (пакетный режим поддерживается).

        Args:
            query_text: Текст запроса 1С (один или несколько SELECT'ов)

        Returns:
            ParsedBatch с распарсенными запросами.
        """
        batch = ParsedBatch(raw_text=query_text)

        # 1. Разбиваем на отдельные SELECT-запросы (по ВЫБРАТЬ / SELECT в начале строки)
        statements = self._split_into_statements(query_text)

        for stmt_text in statements:
            query = self._parse_single(stmt_text)
            batch.queries.append(query)

        return batch

    def parse_single(self, query_text: str) -> ParsedQuery:
        """Разбирает один SELECT-запрос."""
        batch = self.parse(query_text)
        return batch.queries[0] if batch.queries else ParsedQuery()

    def _split_into_statements(self, text: str) -> list[str]:
        """Разделяет пакетный запрос на отдельные SELECT-запросы.

        Разделитель — точка с запятой и/или начало следующего ВЫБРАТЬ.
        Также обрабатывает ПОМЕСТИТЬ — если запрос заканчивается на ПОМЕСТИТЬ Имя,
        то следующий запрос — отдельный.
        """
        if not text.strip():
            return []

        # Удаляем комментарии
        text = self._strip_comments(text)

        # Разбиваем по ';' (но не внутри строк и скобок)
        statements: list[str] = []
        current: list[str] = []
        depth = 0
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_string = not in_string
            elif ch == ";" and depth == 0 and not in_string:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
            current.append(ch)
            i += 1

        last = "".join(current).strip()
        if last:
            statements.append(last)

        return statements

    def _strip_comments(self, text: str) -> str:
        """Удаляет комментарии // и /* */."""
        # Блочные комментарии
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        # Строчные комментарии
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            # Не трогаем // внутри строк
            in_str = False
            i = 0
            result = []
            while i < len(line):
                if line[i] == '"' and (i == 0 or line[i - 1] != "\\"):
                    in_str = not in_str
                if not in_str and i + 1 < len(line) and line[i] == "/" and line[i + 1] == "/":
                    break
                result.append(line[i])
                i += 1
            cleaned.append("".join(result))
        return "\n".join(cleaned)

    def _parse_single(self, text: str) -> ParsedQuery:
        """Парсит один SELECT-запрос."""
        query = ParsedQuery(raw_text=text, line_count=text.count("\n") + 1)

        # Извлекаем параметры (&Параметр)
        query.parameters = self._extract_parameters(text)

        # Извлекаем временную таблицу (ПОМЕСТИТЬ Имя / INTO Имя)
        query.into_temp_table = self._extract_into_temp(text)

        # Извлекаем временные таблицы, используемые в этом запросе
        query.temp_tables = self._extract_temp_table_refs(text)

        # Извлекаем таблицы (FROM + JOIN)
        query.tables = self._extract_tables(text)

        # Извлекаем поля SELECT
        query.select_fields = self._extract_select_fields(text)

        # Извлекаем поля WHERE
        query.where_fields = self._extract_where_fields(text)

        # Извлекаем поля GROUP BY
        query.group_by_fields = self._extract_group_by_fields(text)

        # Извлекаем поля ORDER BY
        query.order_by_fields = self._extract_order_by_fields(text)

        return query

    def _extract_parameters(self, text: str) -> list[str]:
        """Извлекает параметры запроса вида &ИмяПараметра."""
        # Не путать с && (логическое И)
        params = re.findall(r"(?<!&)&([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)", text)
        # Уникальные, сохраняя порядок
        seen: set[str] = set()
        result: list[str] = []
        for p in params:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result

    def _extract_into_temp(self, text: str) -> str:
        """Извлекает имя временной таблицы из ПОМЕСТИТЬ Имя / INTO Имя."""
        # ПОМЕСТИТЬ Имя / INTO Имя — в конце запроса
        m = re.search(
            r"(?:ПОМЕСТИТЬ|INTO)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        return ""

    def _extract_temp_table_refs(self, text: str) -> list[str]:
        """Извлекает ссылки на временные таблицы в тексте.

        Это нетривиально — мы можем только предположить, что любые имена в FROM,
        не соответствующие типам 1С, — это временные таблицы.
        Реальная проверка делается валидатором.
        """
        return []  # Заглушка — валидатор сам определит по контексту

    def _extract_tables(self, text: str) -> list[QueryTable]:
        """Извлекает все таблицы запроса (FROM + JOINs)."""
        tables: list[QueryTable] = []

        # Шаблон: (ИЗ|FROM) Тип.Имя[.ВиртТаблица[(...)]][ КАК Алиас]
        #         (ЛЕВОЕ|ВНУТРЕННЕЕ|...) СОЕДИНЕНИЕ Тип.Имя[.ВиртТаблица] КАК Алиас ПО ...
        # Делаем это в несколько проходов для надёжности.

        # 1. Сначала находим все позиции ключевых слов FROM/JOIN
        tokens = self._tokenize_query(text)

        i = 0
        while i < len(tokens):
            tok_upper = tokens[i].upper()

            # FROM
            if tok_upper in KEYWORDS_FROM:
                i += 1
                if i < len(tokens):
                    table = self._parse_table_tokens(tokens, i, join_type="")
                    if table:
                        tables.append(table)
                        # Пропускаем до следующего ключевого слова
                        i = self._skip_to_next_clause(tokens, i + 1)
                        continue
            # JOIN
            elif tok_upper in KEYWORDS_JOIN:
                join_type = JOIN_TYPES[tok_upper]
                # Может быть "ЛЕВОЕ СОЕДИНЕНИЕ" — нужно съесть СОЕДИНЕНИЕ
                i += 1
                if i < len(tokens) and tokens[i].upper() in {"СОЕДИНЕНИЕ", "JOIN"}:
                    i += 1
                if i < len(tokens):
                    table = self._parse_table_tokens(tokens, i, join_type=join_type)
                    if table:
                        # Извлекаем условие ПО / ON
                        table.join_condition = self._extract_join_condition(tokens, i)
                        tables.append(table)
                        i = self._skip_to_next_clause(tokens, i + 1)
                        continue
            i += 1

        return tables

    def _tokenize_query(self, text: str) -> list[str]:
        """Разбивает текст запроса на токены (грубо, по пробелам и спецсимволам)."""
        # Заменяем переводы строк на пробелы
        # Сохраняем точки, запятые, скобки как отдельные токены
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # Оборачиваем спецсимволы пробелами
        for ch in ",()":
            text = text.replace(ch, f" {ch} ")
        # Разбиваем по пробелам
        raw_tokens = text.split()
        # Объединяем строки в кавычках обратно
        tokens: list[str] = []
        i = 0
        while i < len(raw_tokens):
            tok = raw_tokens[i]
            if tok.startswith('"') and not (len(tok) > 1 and tok.endswith('"')):
                # Строка в кавычках, разбитая пробелом — собираем обратно
                combined = tok
                i += 1
                while i < len(raw_tokens) and not raw_tokens[i].endswith('"'):
                    combined += " " + raw_tokens[i]
                    i += 1
                if i < len(raw_tokens):
                    combined += " " + raw_tokens[i]
                tokens.append(combined)
            else:
                tokens.append(tok)
            i += 1
        return tokens

    def _parse_table_tokens(
        self, tokens: list[str], start: int, join_type: str
    ) -> QueryTable | None:
        """Парсит определение таблицы начиная с позиции start.

        Ожидаемый формат: Тип.Имя[.ВиртТаблица[(параметры)]] [КАК Алиас]
        """
        if start >= len(tokens):
            return None

        i = start
        first_token = tokens[i]

        # Первый токен должен содержать точку (Тип.Имя)
        if "." not in first_token:
            return None

        # Убираем trailing запятую/точку с запятой
        base = first_token.rstrip(",").rstrip(";")
        full_name = base
        i += 1

        # Если следующий токен — '(' — это параметры виртуальной таблицы
        virtual_params = ""
        if i < len(tokens) and tokens[i] == "(":
            i += 1  # пропускаем '('
            params_parts: list[str] = []
            depth = 1
            while i < len(tokens) and depth > 0:
                tok = tokens[i]
                if tok == "(":
                    depth += 1
                    params_parts.append(tok)
                elif tok == ")":
                    depth -= 1
                    if depth > 0:
                        params_parts.append(tok)
                else:
                    params_parts.append(tok)
                i += 1
            virtual_params = " ".join(params_parts).strip()

        # Ищем алиас (КАК Алиас или просто Алиас)
        alias = ""
        if i < len(tokens) and tokens[i].upper() in KEYWORDS_AS:
            i += 1
            if i < len(tokens):
                alias = tokens[i].rstrip(",").rstrip(";")
                i += 1
        elif i < len(tokens):
            candidate = tokens[i].rstrip(",").rstrip(";").strip()
            all_keywords = (
                KEYWORDS_WHERE | KEYWORDS_GROUP | KEYWORDS_ORDER | KEYWORDS_HAVING
                | KEYWORDS_JOIN | KEYWORDS_FROM | KEYWORDS_UNION | KEYWORDS_INTO
                | KEYWORDS_BY
            )
            if (
                candidate
                and candidate.upper() not in all_keywords
                and candidate not in ("(", ")", ",")
                and not candidate.startswith("&")
            ):
                alias = candidate
                i += 1

        # Определяем имя виртуальной таблицы
        virtual_table = ""
        if "." in full_name:
            parts = full_name.split(".")
            if len(parts) >= 3:
                virtual_table = parts[2]
                if "(" in virtual_table:
                    virtual_table = virtual_table.split("(")[0]

        table = QueryTable(
            full_name=full_name,
            virtual_table=virtual_table,
            virtual_table_params=virtual_params,
            alias=alias,
            join_type=join_type,
        )
        return table

    def _skip_to_next_clause(self, tokens: list[str], start: int) -> int:
        """Пропускает токены до следующей ключевой секции (WHERE/GROUP/ORDER/JOIN)."""
        i = start
        while i < len(tokens):
            tok = tokens[i].upper()
            if tok in KEYWORDS_WHERE or tok in KEYWORDS_GROUP or tok in KEYWORDS_ORDER:
                return i
            if tok in KEYWORDS_HAVING or tok in KEYWORDS_JOIN:
                return i
            if tok in KEYWORDS_UNION or tok in KEYWORDS_INTO:
                return i
            i += 1
        return i

    def _extract_join_condition(self, tokens: list[str], start: int) -> str:
        """Извлекает условие JOIN ПО ... до следующего ключевого слова."""
        i = start
        # Сначала пропускаем таблицу и её алиас
        # Ищем ПО / ON
        while i < len(tokens):
            tok = tokens[i].upper()
            if tok in KEYWORDS_ON:
                i += 1
                break
            if tok in (KEYWORDS_WHERE | KEYWORDS_GROUP | KEYWORDS_ORDER | KEYWORDS_HAVING
                       | KEYWORDS_JOIN | KEYWORDS_UNION | KEYWORDS_INTO):
                return ""
            i += 1

        # Собираем условие до следующей секции
        condition_parts: list[str] = []
        while i < len(tokens):
            tok = tokens[i].upper()
            if tok in (KEYWORDS_WHERE | KEYWORDS_GROUP | KEYWORDS_ORDER | KEYWORDS_HAVING
                       | KEYWORDS_JOIN | KEYWORDS_UNION | KEYWORDS_INTO):
                break
            condition_parts.append(tokens[i])
            i += 1
        return " ".join(condition_parts)

    def _extract_select_fields(self, text: str) -> list[QueryField]:
        """Извлекает поля из секции SELECT."""
        # Находим SELECT ... до FROM
        m = re.search(
            r"(?:ВЫБРАТЬ(?:\s+РАЗЛИЧНЫЕ)?|SELECT(?:\s+DISTINCT)?)\s+(.*?)\s+(?:ИЗ|FROM)\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []

        select_text = m.group(1)
        return self._parse_field_list(select_text, context="select")

    def _extract_where_fields(self, text: str) -> list[QueryField]:
        """Извлекает поля из секции WHERE."""
        # WHERE ... до GROUP/ORDER/HAVING/UNION/INSERT или конец
        m = re.search(
            r"\b(?:ГДЕ|WHERE)\s+(.*?)(?=\s+(?:СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION|ПОМЕСТИТЬ|INTO)\b|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []

        where_text = m.group(1)
        return self._extract_field_references(where_text, context="where")

    def _extract_group_by_fields(self, text: str) -> list[QueryField]:
        """Извлекает поля из секции GROUP BY."""
        m = re.search(
            r"\b(?:СГРУППИРОВАТЬ|GROUP)\s+(?:ПО|BY)\s+(.*?)(?=\s+(?:УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION|ПОМЕСТИТЬ|INTO)\b|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []
        return self._parse_field_list(m.group(1), context="group_by")

    def _extract_order_by_fields(self, text: str) -> list[QueryField]:
        """Извлекает поля из секции ORDER BY."""
        m = re.search(
            r"\b(?:УПОРЯДОЧИТЬ|ORDER)\s+(?:ПО|BY)\s+(.*?)(?=\s+(?:ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION|ПОМЕСТИТЬ|INTO)\b|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []
        return self._parse_field_list(m.group(1), context="order_by")

    def _parse_field_list(self, text: str, context: str) -> list[QueryField]:
        """Парсит список полей через запятую."""
        fields: list[QueryField] = []
        # Разделяем по запятым верхнего уровня
        parts = self._split_by_top_level_commas(text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Пропускаем * (SELECT *)
            if part == "*" or part == ".*":
                continue
            # Пропускаем пустые поля
            field = self._parse_single_field(part, context)
            if field:
                fields.append(field)
        return fields

    def _split_by_top_level_commas(self, text: str) -> list[str]:
        """Разделяет строку по запятым верхнего уровня (не внутри скобок)."""
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
            current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    def _parse_single_field(self, text: str, context: str) -> QueryField | None:
        """Парсит одно поле (с возможной агрегатной функцией и алиасом)."""
        text = text.strip()
        if not text:
            return None

        # Удаляем leading/trailing артефакты
        text = text.strip(";").strip()

        # Проверяем агрегатную функцию: ИМЯ(аргумент) [КАК Алиас]
        # Поддерживаем СУММА(РАЗЛИЧНЫЕ аргумент) / SUM(DISTINCT аргумент)
        agg_match = re.match(
            r"(СУММА|SUM|КОЛИЧЕСТВО|COUNT|МИНИМУМ|MIN|МАКСИМУМ|MAX|СРЕДНЕЕ|AVG)\s*\(\s*((?:РАЗЛИЧНЫЕ|DISTINCT)?\s*[^)]*?)\s*\)",
            text,
            re.IGNORECASE,
        )
        aggregate = ""
        aggregate_arg = ""
        if agg_match:
            agg_name = agg_match.group(1).upper()
            aggregate = AGGREGATE_FUNCTIONS.get(agg_name, agg_name)
            raw_arg = agg_match.group(2).strip()
            # Убираем РАЗЛИЧНЫЕ / DISTINCT из аргумента
            raw_arg = re.sub(r"^(?:РАЗЛИЧНЫЕ|DISTINCT)\s+", "", raw_arg, flags=re.IGNORECASE).strip()
            aggregate_arg = raw_arg
            # Извлекаем алиас если есть
            alias = ""
            after_agg = text[agg_match.end():].strip()
            alias_match = re.match(
                r"(?:КАК|AS)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)",
                after_agg,
                re.IGNORECASE,
            )
            if alias_match:
                alias = alias_match.group(1)
            elif after_agg and not after_agg.upper().startswith(
                tuple(KEYWORDS_AS | KEYWORDS_FROM | KEYWORDS_WHERE)
            ):
                # Может быть алиас без КАК
                alias = after_agg.split()[0]

            # Если аргумент агрегатной функции — это поле, используем его
            raw = aggregate_arg
            if aggregate_arg in ("*", "РАЗЛИЧНЫЕ *", "DISTINCT *"):
                raw = "*"
            # Если аргумент содержит выражение (математика) — берём только ссылки на поля
            # через _extract_field_references
            if raw != "*" and any(op in raw for op in ["+", "-", "*", "/"]):
                # Выражение внутри агрегата — возвращаем как есть, валидатор разберётся
                return QueryField(
                    raw=raw,
                    alias=alias,
                    aggregate=aggregate,
                    aggregate_arg=aggregate_arg,
                    context=context,
                )
            return QueryField(
                raw=raw,
                alias=alias,
                aggregate=aggregate,
                aggregate_arg=aggregate_arg,
                context=context,
            )

        # Обычное поле: ВозможноСпецификатор.ИмяПоля [КАК Алиас]
        alias = ""
        # Ищем КАК / AS
        alias_match = re.search(
            r"\s+(?:КАК|AS)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*$",
            text,
            re.IGNORECASE,
        )
        if alias_match:
            alias = alias_match.group(1)
            text = text[: alias_match.start()].strip()

        # Если есть выражение (математика, конкатенация) — извлекаем поля из выражения
        if any(op in text for op in [" + ", " - ", " * ", " / "]) or any(
            op in text for op in ["+", "-"] if " " in text
        ):
            # Выражение — пропускаем как одно поле, валидатор не будет проверять
            return None

        # Убираем trailing запятую
        text = text.rstrip(",").strip()

        if not text:
            return None

        return QueryField(raw=text, alias=alias, context=context)

    def _extract_field_references(self, text: str, context: str) -> list[QueryField]:
        """Извлекает все ссылки на поля из произвольного текста (например WHERE).

        Ищет паттерны вида Алиас.ИмяПоля или ИмяПоля.
        """
        fields: list[QueryField] = []
        # Сначала извлечём агрегатные функции
        agg_matches = re.findall(
            r"(СУММА|SUM|КОЛИЧЕСТВО|COUNT|МИНИМУМ|MIN|МАКСИМУМ|MAX|СРЕДНЕЕ|AVG)\s*\(\s*([^)]+?)\s*\)",
            text,
            re.IGNORECASE,
        )
        for agg_name, arg in agg_matches:
            agg = AGGREGATE_FUNCTIONS.get(agg_name.upper(), agg_name.upper())
            arg = arg.strip()
            if arg and arg != "*":
                fields.append(
                    QueryField(
                        raw=arg,
                        aggregate=agg,
                        aggregate_arg=arg,
                        context=context,
                    )
                )

        # Извлекаем все Идентификатор.Идентификатор (поля с алиасом)
        # Не берём: ключевые слова, литералы, типы
        all_refs = re.findall(
            r"\b([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*\.[А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*(?:\.[А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)*)\b",
            text,
        )
        keywords = (
            KEYWORDS_FROM | KEYWORDS_WHERE | KEYWORDS_GROUP | KEYWORDS_ORDER
            | KEYWORDS_HAVING | KEYWORDS_JOIN | KEYWORDS_AS | KEYWORDS_INTO
            | KEYWORDS_UNION | KEYWORDS_BY
        )
        for ref in all_refs:
            # Проверяем, что первая часть не ключевое слово
            first_part = ref.split(".")[0].upper()
            if first_part in keywords:
                continue
            # Пропускаем если это тип объекта (Справочник.Имя — это таблица, не поле)
            if first_part in ALL_OBJECT_TYPES:
                continue
            fields.append(QueryField(raw=ref, context=context))

        return fields
