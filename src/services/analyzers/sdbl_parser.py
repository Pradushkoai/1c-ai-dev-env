"""
sdbl_parser.py — Python wrapper над ANTLR4 SDBL грамматикой.

Phase A.0 of Query Intelligence plan: настоящий AST-парсер языка запросов 1С
через SDBL (Structured Database Language) грамматику от 1c-syntax.

Источники:
- SDBLParser.g4 / SDBLLexer.g4 — LGPL-3.0, https://github.com/1c-syntax/bsl-parser
- ANTLR4 Python target — BSD-3-Clause, https://www.antlr.org/

Лицензия: LGPL-3.0-or-later (для .g4 файлов и сгенерированного Python кода).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ANTLR4 runtime
try:
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.tree.Tree import TerminalNode, ErrorNode

    _ANTLR_AVAILABLE = True
except ImportError:
    _ANTLR_AVAILABLE = False

# Сгенерированные SDBL парсеры
_GENERATED_DIR = Path(__file__).parent / "sdbl" / "generated"
if _ANTLR_AVAILABLE and _GENERATED_DIR.exists():
    # Добавляем директорию в path для импорта
    if str(_GENERATED_DIR) not in sys.path:
        sys.path.insert(0, str(_GENERATED_DIR))
    try:
        from SDBLLexer import SDBLLexer
        from SDBLParser import SDBLParser
        from SDBLParserVisitor import SDBLParserVisitor

        _SDBL_AVAILABLE = True
    except ImportError:
        _SDBL_AVAILABLE = False
else:
    _SDBL_AVAILABLE = False


# ============================================================================
# DATA CLASSES (совместимы с query_parser.py для backward compat)
# ============================================================================


@dataclass
class SDBLField:
    """Поле в запросе 1С (извлечённое из SDBL AST)."""

    raw: str
    table_alias: str = ""
    field_name: str = ""
    alias: str = ""
    aggregate: str = ""
    aggregate_arg: str = ""
    context: str = ""
    line: int = 0

    def __post_init__(self):
        if not self.field_name and "." in self.raw:
            parts = self.raw.split(".", 1)
            self.table_alias = parts[0]
            self.field_name = parts[1]
        elif not self.field_name:
            self.field_name = self.raw


@dataclass
class SDBLTable:
    """Таблица в запросе 1С (источник данных)."""

    full_name: str
    object_type: str = ""
    object_name: str = ""
    virtual_table: str = ""
    virtual_table_params: str = ""
    alias: str = ""
    join_type: str = ""
    join_condition: str = ""
    line: int = 0

    def __post_init__(self):
        if not self.object_type and "." in self.full_name:
            parts = self.full_name.split(".", 1)
            self.object_type = parts[0]
            rest = parts[1]
            if "." in rest:
                name_parts = rest.split(".", 1)
                self.object_name = name_parts[0]
                self.virtual_table = name_parts[1]
                if "(" in self.virtual_table:
                    self.virtual_table = self.virtual_table.split("(")[0]
            else:
                self.object_name = rest


@dataclass
class SDBLQuery:
    """Распарсенный запрос 1С (один SELECT) из SDBL AST."""

    tables: list[SDBLTable] = field(default_factory=list)
    select_fields: list[SDBLField] = field(default_factory=list)
    where_fields: list[SDBLField] = field(default_factory=list)
    group_by_fields: list[SDBLField] = field(default_factory=list)
    order_by_fields: list[SDBLField] = field(default_factory=list)
    having_fields: list[SDBLField] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    temp_tables: list[str] = field(default_factory=list)
    into_temp_table: str = ""
    raw_text: str = ""
    line_count: int = 0
    has_syntax_error: bool = False
    parse_error_message: str = ""

    def get_table_by_alias(self, alias: str) -> SDBLTable | None:
        """Возвращает таблицу по алиасу."""
        for t in self.tables:
            if t.alias == alias or t.object_name == alias or t.full_name == alias:
                return t
        return None


@dataclass
class SDBLBatch:
    """Пакет запросов 1С (несколько SELECT подряд)."""

    queries: list[SDBLQuery] = field(default_factory=list)
    raw_text: str = ""
    has_syntax_error: bool = False
    parse_error_message: str = ""

    def get_all_tables(self) -> list[SDBLTable]:
        """Все таблицы из всех запросов пакета."""
        result: list[SDBLTable] = []
        for q in self.queries:
            result.extend(q.tables)
        return result

    def get_temp_table_definition(self, name: str) -> SDBLQuery | None:
        """Возвращает запрос, который создаёт временную таблицу."""
        for q in self.queries:
            if q.into_temp_table == name:
                return q
        return None


# ============================================================================
# SDBL AST VISITOR — извлечение структуры из ANTLR4 дерева
# ============================================================================


class SDBLStructureVisitor(SDBLParserVisitor if _SDBL_AVAILABLE else object):
    """Посетитель SDBL AST — извлекает таблицы, поля, параметры."""

    def __init__(self):
        super().__init__()
        self.current_query: SDBLQuery | None = None
        self.current_table_alias: str = ""

    def visitQueryPackage(self, ctx):
        """queryPackage: queries (SEMICOLON queries)* SEMICOLON? EOF"""
        batch = SDBLBatch()
        for child in ctx.queries() or []:
            query = self.visit(child)
            if query:
                batch.queries.append(query)
        return batch

    def visitSelectQuery(self, ctx):
        """selectQuery: subquery (...)"""
        query = SDBLQuery()
        self.current_query = query
        # subquery содержит основной запрос и unions
        subquery_ctx = ctx.subquery()
        if subquery_ctx:
            main_ctx = subquery_ctx.main
            if main_ctx:
                self.visit(main_ctx)
        return query

    def visitDropTableQuery(self, ctx):
        """dropTableQuery: DROP temporaryTableName=identifier"""
        # Это удаление временной таблицы, не SELECT
        query = SDBLQuery()
        name_ctx = ctx.temporaryTableName
        if name_ctx:
            query.temp_tables.append(name_ctx.getText())
        return query

    def visitQuery(self, ctx):
        """query: SELECT limitations? selectedFields (INTO temporaryTable)? FROM? WHERE? GROUP_BY? HAVING? FOR_UPDATE? INDEX_BY?"""
        if not self.current_query:
            return None

        # SELECT fields
        selected_fields_ctx = ctx.columns
        if selected_fields_ctx:
            self._extract_select_fields(selected_fields_ctx, self.current_query)

        # INTO temporaryTable
        temp_name_ctx = ctx.temporaryTableName
        if temp_name_ctx:
            self.current_query.into_temp_table = temp_name_ctx.getText()

        # FROM dataSources
        from_ctx = ctx.from_
        if from_ctx:
            self._extract_data_sources(from_ctx, self.current_query)

        # WHERE — извлекаем поля и параметры
        where_ctx = ctx.where
        if where_ctx:
            where_text = where_ctx.getText()
            self._extract_fields_from_text(where_text, self.current_query.where_fields, "where")
            self._extract_parameters_from_text(where_text, self.current_query)

        # GROUP BY
        group_ctx = ctx.groupBy
        if group_ctx:
            for expr_ctx in group_ctx:
                if expr_ctx:
                    text = expr_ctx.getText()
                    self.current_query.group_by_fields.append(SDBLField(raw=text, context="group_by"))

        # HAVING
        having_ctx = ctx.having
        if having_ctx:
            having_text = having_ctx.getText()
            self._extract_fields_from_text(having_text, self.current_query.having_fields, "having")

        return self.current_query

    def _extract_select_fields(self, selected_fields_ctx, query: SDBLQuery):
        """Извлекает поля из selectedFields контекста."""
        fields = selected_fields_ctx.fields
        if not fields:
            return
        for field_ctx in fields:
            if not field_ctx:
                continue
            # selectedField может быть: asteriskField, columnField, emptyTableField,
            # inlineTableField, expressionField
            field_text = field_ctx.getText()
            # Пропускаем звёздочки
            if field_text == "*" or field_text.endswith(".*"):
                continue

            # Извлекаем алиас
            alias = ""
            alias_ctx = field_ctx.alias()
            if alias_ctx:
                alias = alias_ctx.getText()

            # Проверяем на агрегатную функцию
            aggregate = ""
            aggregate_arg = ""
            # В SDBL агрегаты это функции в выражениях — упрощённая проверка
            upper_text = field_text.upper()
            for agg_name, agg_code in [
                ("СУММА", "SUM"), ("SUM", "SUM"),
                ("КОЛИЧЕСТВО", "COUNT"), ("COUNT", "COUNT"),
                ("МИНИМУМ", "MIN"), ("MIN", "MIN"),
                ("МАКСИМУМ", "MAX"), ("MAX", "MAX"),
                ("СРЕДНЕЕ", "AVG"), ("AVG", "AVG"),
            ]:
                if upper_text.startswith(agg_name + "("):
                    aggregate = agg_code
                    # Извлекаем аргумент
                    start = field_text.find("(") + 1
                    end = field_text.rfind(")")
                    if start > 0 and end > start:
                        aggregate_arg = field_text[start:end].strip()
                    break

            # Очищаем raw от алиаса
            raw = field_text
            if alias and raw.endswith(alias):
                raw = raw[: -len(alias)].rstrip()

            query.select_fields.append(SDBLField(
                raw=raw,
                alias=alias,
                aggregate=aggregate,
                aggregate_arg=aggregate_arg,
                context="select",
            ))

    def _extract_data_sources(self, from_ctx, query: SDBLQuery):
        """Извлекает таблицы из dataSources контекста."""
        # dataSources содержит list of dataSource
        # Каждый dataSource: table (alias) | join
        sources = []
        try:
            # Пытаемся получить list источников
            for attr in ["dataSource", "sources"]:
                if hasattr(from_ctx, attr):
                    val = getattr(from_ctx, attr)
                    if val:
                        if isinstance(val, list):
                            sources.extend(val)
                        else:
                            sources.append(val)
                        break

            # Альтернативный путь — обходим детей
            if not sources:
                for child in from_ctx.getChildren():
                    if hasattr(child, "getRuleContext") and child.getRuleContext():
                        sources.append(child)
        except Exception:
            pass

        # Извлекаем информацию о таблицах
        for source_ctx in sources:
            try:
                text = source_ctx.getText()
                # Упрощённое извлечение: первый identifier — имя таблицы
                # КАК Алиас — алиас
                table = self._parse_table_from_text(text)
                if table:
                    query.tables.append(table)
            except Exception:
                continue

        # Fallback: если structured извлечение не сработало, парсим текст FROM
        if not query.tables:
            from_text = from_ctx.getText()
            self._parse_tables_from_from_text(from_text, query)

    def _parse_table_from_text(self, text: str) -> SDBLTable | None:
        """Упрощённое извлечение таблицы из текста dataSource."""
        if not text or len(text) < 3:
            return None
        # Ищем имя таблицы — последовательность идентификаторов через точку
        import re
        # Сначала ищем "Тип.Имя[.ВиртТаблица]"
        m = re.match(r"^([А-Яа-яЁёA-Za-z_][\w]*(?:\.[А-Яа-яЁёA-Za-z_][\w]*){1,2})", text)
        if not m:
            return None
        full_name = m.group(1)

        # Ищем алиас после КАК / AS
        alias = ""
        alias_match = re.search(r"(?:КАК|AS)\s+([А-Яа-яЁёA-Za-z_]\w*)", text, re.IGNORECASE)
        if alias_match:
            alias = alias_match.group(1)

        # Проверяем на JOIN
        join_type = ""
        join_match = re.match(r"^(ЛЕВОЕ|LEFT|ВНУТРЕННЕЕ|INNER|ПРАВОЕ|RIGHT|ПОЛНОЕ|FULL)", text, re.IGNORECASE)
        if join_match:
            jt = join_match.group(1).upper()
            join_map = {
                "ЛЕВОЕ": "LEFT", "LEFT": "LEFT",
                "ВНУТРЕННЕЕ": "INNER", "INNER": "INNER",
                "ПРАВОЕ": "RIGHT", "RIGHT": "RIGHT",
                "ПОЛНОЕ": "FULL", "FULL": "FULL",
            }
            join_type = join_map.get(jt, "INNER")

        # Параметры виртуальной таблицы
        virtual_params = ""
        if "(" in text:
            start = text.find("(")
            end = text.rfind(")")
            if end > start:
                virtual_params = text[start + 1 : end].strip()

        return SDBLTable(
            full_name=full_name,
            alias=alias,
            join_type=join_type,
            virtual_table_params=virtual_params,
        )

    def _parse_tables_from_from_text(self, from_text: str, query: SDBLQuery):
        """Fallback: парсим таблицы из текста FROM."""
        import re
        # Удаляем FROM в начале
        text = re.sub(r"^(ИЗ|FROM)\s+", "", from_text, flags=re.IGNORECASE)
        # Разбиваем по JOIN keywords
        parts = re.split(r"\s+(ЛЕВОЕ\s+СОЕДИНЕНИЕ|LEFT\s+JOIN|ВНУТРЕННЕЕ\s+СОЕДИНЕНИЕ|INNER\s+JOIN|ПРАВОЕ\s+СОЕДИНЕНИЕ|RIGHT\s+JOIN|ПОЛНОЕ\s+СОЕДИНЕНИЕ|FULL\s+JOIN|СОЕДИНЕНИЕ|JOIN)\s+", text, flags=re.IGNORECASE)

        current_join_type = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Проверяем, это JOIN keyword?
            join_map = {
                "ЛЕВОЕ СОЕДИНЕНИЕ": "LEFT", "LEFT JOIN": "LEFT",
                "ВНУТРЕННЕЕ СОЕДИНЕНИЕ": "INNER", "INNER JOIN": "INNER",
                "ПРАВОЕ СОЕДИНЕНИЕ": "RIGHT", "RIGHT JOIN": "RIGHT",
                "ПОЛНОЕ СОЕДИНЕНИЕ": "FULL", "FULL JOIN": "FULL",
                "СОЕДИНЕНИЕ": "INNER", "JOIN": "INNER",
            }
            if part.upper() in join_map:
                current_join_type = join_map[part.upper()]
                continue

            table = self._parse_table_from_text(part)
            if table:
                table.join_type = current_join_type
                query.tables.append(table)
                current_join_type = ""

    def _extract_fields_from_text(self, text: str, fields: list[SDBLField], context: str):
        """Извлекает ссылки на поля из произвольного текста (WHERE, HAVING)."""
        import re
        # Алиас.ИмяПоля
        refs = re.findall(
            r"\b([А-Яа-яA-Za-z_][\w]*\.[А-Яа-яA-Za-z_][\w]*(?:\.[А-Яа-яA-Za-z_][\w]*)*)\b",
            text,
        )
        keywords = {
            "ИЗ", "FROM", "ГДЕ", "WHERE", "СГРУППИРОВАТЬ", "GROUP",
            "УПОРЯДОЧИТЬ", "ORDER", "ИМЕЮЩИЕ", "HAVING", "ПО", "BY",
            "И", "AND", "ИЛИ", "OR", "НЕ", "NOT",
            "МЕЖДУ", "BETWEEN", "ПОДОБНО", "LIKE",
            "В", "IN", "СРЕД", "AVG", "СУММА", "SUM",
            "КОЛИЧЕСТВО", "COUNT", "МИНИМУМ", "MIN", "МАКСИМУМ", "MAX",
            "ВЫБРАТЬ", "SELECT", "КАК", "AS", "ПОМЕСТИТЬ", "INTO",
        }
        for ref in refs:
            first_part = ref.split(".")[0].upper()
            if first_part in keywords:
                continue
            fields.append(SDBLField(raw=ref, context=context))

    def _extract_parameters_from_text(self, text: str, query: SDBLQuery):
        """Извлекает параметры (&Параметр) из текста."""
        import re
        params = re.findall(r"(?<!&)&([А-Яа-яA-Za-z_][\w]*)", text)
        seen: set[str] = set()
        for p in params:
            if p not in seen:
                seen.add(p)
                query.parameters.append(p)


# ============================================================================
# PUBLIC API — совместимо с query_parser.py
# ============================================================================


class SDBLQueryParser:
    """AST-парсер языка запросов 1С через SDBL ANTLR4 грамматику.

    Заменяет regex-based QueryParser на настоящий AST.
    Backward compatible: возвращает SDBLBatch (совместим с ParsedBatch).

    Требует установленных:
    - antlr4-python3-runtime (pip install antlr4-python3-runtime)
    - Сгенерированные SDBL*.py файлы в src/services/analyzers/sdbl/generated/
    """

    def __init__(self):
        if not _SDBL_AVAILABLE:
            raise ImportError(
                "SDBL parser недоступен. Требуется: pip install antlr4-python3-runtime"
            )
        self._visitor = SDBLStructureVisitor()

    def parse(self, query_text: str) -> SDBLBatch:
        """Разбирает текст запроса 1С (пакетный режим поддерживается).

        Args:
            query_text: Текст запроса 1С (один или несколько SELECT)

        Returns:
            SDBLBatch с распарсенными запросами.
        """
        if not query_text or not query_text.strip():
            return SDBLBatch()

        try:
            input_stream = InputStream(query_text)
            lexer = SDBLLexer(input_stream)
            stream = CommonTokenStream(lexer)
            parser = SDBLParser(stream)
            tree = parser.queryPackage()

            # Проверяем синтаксические ошибки
            if parser.getNumberOfSyntaxErrors() > 0:
                batch = SDBLBatch(
                    raw_text=query_text,
                    has_syntax_error=True,
                    parse_error_message=f"SDBL syntax errors: {parser.getNumberOfSyntaxErrors()}",
                )
                return batch

            batch = self._visitor.visitQueryPackage(tree)
            if batch is None:
                batch = SDBLBatch()
            batch.raw_text = query_text
            batch.queries = [q for q in batch.queries if q is not None]
            for q in batch.queries:
                q.raw_text = query_text
                q.line_count = query_text.count("\n") + 1
                # Извлекаем параметры из всего текста запроса
                self._extract_all_parameters(query_text, q)

            return batch
        except Exception as e:
            return SDBLBatch(
                raw_text=query_text,
                has_syntax_error=True,
                parse_error_message=f"SDBL parse error: {e}",
            )

    def parse_single(self, query_text: str) -> SDBLQuery:
        """Разбирает один SELECT-запрос."""
        batch = self.parse(query_text)
        return batch.queries[0] if batch.queries else SDBLQuery()

    def _extract_all_parameters(self, text: str, query: SDBLQuery):
        """Извлекает все параметры из текста запроса."""
        import re
        params = re.findall(r"(?<!&)&([А-Яа-яA-Za-z_][\w]*)", text)
        seen: set[str] = set(query.parameters)
        for p in params:
            if p not in seen:
                seen.add(p)
                query.parameters.append(p)


def is_sdbl_available() -> bool:
    """Проверяет, доступен ли SDBL AST парсер."""
    return _SDBL_AVAILABLE


# ============================================================================
# SINGLETON
# ============================================================================

_PARSER_SINGLETON: SDBLQueryParser | None = None


def get_parser() -> SDBLQueryParser:
    """Возвращает singleton-экземпляр SDBL парсера."""
    global _PARSER_SINGLETON
    if _PARSER_SINGLETON is None:
        _PARSER_SINGLETON = SDBLQueryParser()
    return _PARSER_SINGLETON


# ============================================================================
# COMPAT FUNCTIONS — совместимы с query_parser.py
# ============================================================================


def extract_symbols_from_query(query_text: str) -> SDBLBatch:
    """Совместимо с query_parser.QueryParser.parse().

    Возвращает SDBLBatch (совместим с ParsedBatch по интерфейсу).
    """
    if not _SDBL_AVAILABLE:
        raise ImportError("SDBL parser не установлен.")
    return get_parser().parse(query_text)
