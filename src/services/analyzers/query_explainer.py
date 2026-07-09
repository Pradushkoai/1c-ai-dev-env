"""
query_explainer.py — Объяснение запросов 1С человекочитаемым языком.

Phase C of Query Intelligence plan: принимает текст запроса → возвращает
человекочитаемое описание что этот запрос делает.

Алгоритм:
1. Парсинг запроса через SDBL (если доступен) или regex fallback
2. Для каждой таблицы — найти описание в metadata (синоним, тип)
3. Для каждого поля — найти тип и описание
4. Сгенерировать человекочитаемое описание на русском

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
class QueryExplanation:
    """Человекочитаемое объяснение запроса."""

    summary: str = ""  # краткое описание (1-2 предложения)
    tables: list[dict[str, str]] = field(default_factory=list)  # [{name, synonym, type}]
    fields: list[dict[str, str]] = field(default_factory=list)  # [{name, type, description}]
    filters: list[str] = field(default_factory=list)  # условия фильтрации
    grouping: list[str] = field(default_factory=list)  # поля группировки
    joins: list[dict[str, str]] = field(default_factory=list)  # [{table, condition, type}]
    aggregates: list[dict[str, str]] = field(default_factory=list)  # [{function, field}]
    order_by: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    result_shape: str = ""  # структура результата

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "tables": self.tables,
            "fields": self.fields,
            "filters": self.filters,
            "grouping": self.grouping,
            "joins": self.joins,
            "aggregates": self.aggregates,
            "order_by": self.order_by,
            "parameters": self.parameters,
            "result_shape": self.result_shape,
        }


# ============================================================================
# EXPLAINER
# ============================================================================


class QueryExplainer:
    """Объясняет что делает запрос 1С.

    Использует:
    - SDBL parser (опционально) для точного AST-обхода
    - regex fallback когда SDBL недоступен
    - metadata_index для получения синонимов и типов
    """

    def __init__(self, metadata_index: dict[str, Any] | None = None):
        self.metadata = metadata_index or {}
        self._init_parser()

    def _init_parser(self):
        """Инициализация парсера."""
        try:
            from src.services.analyzers.sdbl_parser import SDBLQueryParser, is_sdbl_available

            self._sdbl_available = is_sdbl_available()
            if self._sdbl_available:
                self._sdbl_parser = SDBLQueryParser()
            else:
                self._sdbl_parser = None
        except ImportError:
            self._sdbl_available = False
            self._sdbl_parser = None

    def explain(self, query_text: str, config_name: str = "") -> QueryExplanation:
        """Объяснить что делает запрос.

        Args:
            query_text: Текст запроса 1С
            config_name: Имя конфигурации (для metadata lookup)

        Returns:
            QueryExplanation с человекочитаемым описанием.
        """
        if not query_text or not query_text.strip():
            return QueryExplanation(summary="Пустой запрос")

        explanation = QueryExplanation()

        # Парсинг запроса
        parsed = self._parse_query(query_text)
        if parsed is None:
            explanation.summary = "Не удалось распарсить запрос"
            return explanation

        # Извлечение таблиц
        explanation.tables = self._extract_tables_info(parsed)

        # Извлечение полей
        explanation.fields = self._extract_fields_info(parsed)

        # Извлечение фильтров
        explanation.filters = self._extract_filters(parsed)

        # Извлечение группировки
        explanation.grouping = self._extract_grouping(parsed)

        # Извлечение JOIN
        explanation.joins = self._extract_joins(parsed)

        # Извлечение агрегатов
        explanation.aggregates = self._extract_aggregates(parsed)

        # Извлечение ORDER BY
        explanation.order_by = self._extract_order_by(parsed)

        # Извлечение параметров
        explanation.parameters = self._extract_parameters(query_text, parsed)

        # Генерация summary
        explanation.summary = self._generate_summary(explanation)

        # Генерация result_shape
        explanation.result_shape = self._generate_result_shape(explanation)

        return explanation

    def _parse_query(self, query_text: str) -> dict[str, Any] | None:
        """Парсит запрос и возвращает структурированные данные."""
        # Пытаемся SDBL
        if self._sdbl_available and self._sdbl_parser:
            try:
                batch = self._sdbl_parser.parse(query_text)
                if batch.queries:
                    q = batch.queries[0]
                    return {
                        "tables": [
                            {"full_name": t.full_name, "alias": t.alias,
                             "object_type": t.object_type, "object_name": t.object_name,
                             "virtual_table": t.virtual_table, "join_type": t.join_type}
                            for t in q.tables
                        ],
                        "select_fields": [
                            {"raw": f.raw, "alias": f.alias, "aggregate": f.aggregate,
                             "aggregate_arg": f.aggregate_arg}
                            for f in q.select_fields
                        ],
                        "where_fields": [{"raw": f.raw} for f in q.where_fields],
                        "group_by_fields": [{"raw": f.raw} for f in q.group_by_fields],
                        "parameters": q.parameters,
                        "has_syntax_error": batch.has_syntax_error,
                    }
            except Exception:
                pass

        # Regex fallback
        return self._parse_regex(query_text)

    def _parse_regex(self, query_text: str) -> dict[str, Any]:
        """Regex-based fallback парсер."""
        text = query_text

        # Извлекаем таблицы из FROM
        tables = []
        from_match = re.search(r"\b(?:ИЗ|FROM)\s+(.+?)(?=\s+(?:ГДЕ|WHERE|СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING)|$)", text, re.IGNORECASE | re.DOTALL)
        if from_match:
            from_text = from_match.group(1)
            # Ищем Тип.Имя[.ВиртТаблица]
            table_matches = re.findall(r"([А-Яа-яЁёA-Za-z_][\w]*(?:\.[А-Яа-яЁёA-Za-z_][\w]*){1,2})", from_text)
            for tm in table_matches:
                parts = tm.split(".")
                table_info = {"full_name": tm, "alias": "", "object_type": parts[0], "object_name": parts[1] if len(parts) > 1 else ""}
                if len(parts) > 2:
                    table_info["virtual_table"] = parts[2]
                # Ищем алиас
                alias_match = re.search(re.escape(tm) + r"\s+(?:КАК\s+)?([А-Яа-яЁёA-Za-z_]\w*)", from_text)
                if alias_match:
                    table_info["alias"] = alias_match.group(1)
                tables.append(table_info)

        # Извлекаем поля SELECT
        select_fields = []
        select_match = re.search(r"\b(?:ВЫБРАТЬ|SELECT)\s+(.+?)(?=\s+(?:ИЗ|FROM)\b)", text, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_text = select_match.group(1)
            # Разбиваем по запятым (упрощённо)
            for part in re.split(r",(?![^()]*\))", select_text):
                part = part.strip()
                if part and part != "*":
                    field_info = {"raw": part, "alias": "", "aggregate": "", "aggregate_arg": ""}
                    # Проверяем агрегат
                    agg_match = re.match(r"(СУММА|SUM|КОЛИЧЕСТВО|COUNT|МИНИМУМ|MIN|МАКСИМУМ|MAX|СРЕДНЕЕ|AVG)\s*\(([^)]+)\)", part, re.IGNORECASE)
                    if agg_match:
                        agg_name = agg_match.group(1).upper()
                        agg_map = {"СУММА": "SUM", "SUM": "SUM", "КОЛИЧЕСТВО": "COUNT", "COUNT": "COUNT",
                                   "МИНИМУМ": "MIN", "MIN": "MIN", "МАКСИМУМ": "MAX", "MAX": "MAX",
                                   "СРЕДНЕЕ": "AVG", "AVG": "AVG"}
                        field_info["aggregate"] = agg_map.get(agg_name, agg_name)
                        field_info["aggregate_arg"] = agg_match.group(2).strip()
                    # Извлекаем алиас
                    alias_match = re.search(r"\s+(?:КАК|AS)\s+([А-Яа-яЁёA-Za-z_]\w*)", part)
                    if alias_match:
                        field_info["alias"] = alias_match.group(1)
                    select_fields.append(field_info)

        # Извлекаем WHERE
        where_fields = []
        where_match = re.search(r"\b(?:ГДЕ|WHERE)\s+(.+?)(?=\s+(?:СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING)|$)", text, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_text = where_match.group(1)
            field_refs = re.findall(r"([А-Яа-яA-Za-z_][\w]*\.[А-Яа-яA-Za-z_][\w]*)", where_text)
            for ref in field_refs:
                where_fields.append({"raw": ref})

        # Извлекаем GROUP BY
        group_by_fields = []
        group_match = re.search(r"\b(?:СГРУППИРОВАТЬ|GROUP)\s+(?:ПО|BY)\s+(.+?)(?=\s+(?:УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING)|$)", text, re.IGNORECASE | re.DOTALL)
        if group_match:
            for part in group_match.group(1).split(","):
                part = part.strip()
                if part:
                    group_by_fields.append({"raw": part})

        # Извлекаем параметры
        parameters = list(set(re.findall(r"&([А-Яа-яA-Za-z_]\w*)", text)))

        return {
            "tables": tables,
            "select_fields": select_fields,
            "where_fields": where_fields,
            "group_by_fields": group_by_fields,
            "parameters": parameters,
            "has_syntax_error": False,
        }

    def _extract_tables_info(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        """Извлекает информацию о таблицах с описаниями из metadata."""
        tables_info = []
        for t in parsed.get("tables", []):
            info = {
                "name": t.get("full_name", ""),
                "type": t.get("object_type", ""),
                "alias": t.get("alias", ""),
                "virtual_table": t.get("virtual_table", ""),
            }
            # Ищем синоним в metadata
            obj = self._find_object_in_metadata(t.get("object_name", ""), t.get("object_type", ""))
            if obj:
                info["synonym"] = obj.get("synonym", "")
            tables_info.append(info)
        return tables_info

    def _extract_fields_info(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        """Извлекает информацию о полях SELECT."""
        fields_info = []
        for f in parsed.get("select_fields", []):
            info = {
                "name": f.get("raw", ""),
                "alias": f.get("alias", ""),
                "aggregate": f.get("aggregate", ""),
            }
            fields_info.append(info)
        return fields_info

    def _extract_filters(self, parsed: dict[str, Any]) -> list[str]:
        """Извлекает условия фильтрации."""
        return [f.get("raw", "") for f in parsed.get("where_fields", [])]

    def _extract_grouping(self, parsed: dict[str, Any]) -> list[str]:
        """Извлекает поля группировки."""
        return [f.get("raw", "") for f in parsed.get("group_by_fields", [])]

    def _extract_joins(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        """Извлекает информацию о JOIN."""
        joins = []
        for t in parsed.get("tables", []):
            if t.get("join_type"):
                joins.append({
                    "table": t.get("full_name", ""),
                    "type": t.get("join_type", ""),
                })
        return joins

    def _extract_aggregates(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        """Извлекает агрегатные функции."""
        aggregates = []
        for f in parsed.get("select_fields", []):
            if f.get("aggregate"):
                aggregates.append({
                    "function": f["aggregate"],
                    "field": f.get("aggregate_arg", f.get("raw", "")),
                })
        return aggregates

    def _extract_order_by(self, parsed: dict[str, Any]) -> list[str]:
        """Извлекает ORDER BY (упрощённо)."""
        # TODO: добавить извлечение ORDER BY из SDBL AST
        return []

    def _extract_parameters(self, text: str, parsed: dict[str, Any]) -> list[str]:
        """Извлекает параметры запроса."""
        return parsed.get("parameters", [])

    def _find_object_in_metadata(self, name: str, obj_type: str) -> dict[str, Any] | None:
        """Ищет объект в metadata по имени и типу."""
        if not name:
            return None
        for type_plural, objs in self.metadata.get("objects", {}).items():
            for obj in objs:
                if obj.get("name", "").lower() == name.lower():
                    return obj
        return None

    def _generate_summary(self, explanation: QueryExplanation) -> str:
        """Генерирует краткое описание запроса."""
        parts = []

        # Что выбирается
        if explanation.aggregates:
            agg_desc = ", ".join(f"{a['function']}({a['field']})" for a in explanation.aggregates)
            parts.append(f"Вычисляет {agg_desc}")
        elif explanation.fields:
            field_names = [f["alias"] or f["name"] for f in explanation.fields[:3]]
            parts.append(f"Выбирает поля: {', '.join(field_names)}")

        # Откуда
        if explanation.tables:
            table_descs = []
            for t in explanation.tables:
                desc = t.get("synonym") or t.get("name", "")
                if t.get("virtual_table"):
                    desc += f" ({t['virtual_table']})"
                table_descs.append(desc)
            parts.append(f"из {' '.join(table_descs[:2])}")

        # Группировка
        if explanation.grouping:
            parts.append(f"с группировкой по {', '.join(explanation.grouping[:2])}")

        # Фильтр
        if explanation.filters:
            parts.append(f"с фильтром по {', '.join(explanation.filters[:2])}")

        # JOIN
        if explanation.joins:
            join_descs = [f"{j['type']} JOIN с {j['table']}" for j in explanation.joins]
            parts.append(f"с {', '.join(join_descs)}")

        return ". ".join(parts) + "." if parts else "Запрос без явной структуры."

    def _generate_result_shape(self, explanation: QueryExplanation) -> str:
        """Генерирует описание структуры результата."""
        if explanation.grouping and explanation.aggregates:
            return "Сводная таблица: группы + агрегаты"
        elif explanation.aggregates:
            return "Одна строка с агрегатами"
        elif explanation.grouping:
            return "Сгруппированные данные"
        else:
            return "Список записей"


# ============================================================================
# PUBLIC API
# ============================================================================


def explain_query(
    query_text: str,
    metadata_index: dict[str, Any] | None = None,
    config_name: str = "",
) -> QueryExplanation:
    """Удобная функция для объяснения запроса.

    Args:
        query_text: Текст запроса 1С
        metadata_index: Метаданные конфигурации (опционально)
        config_name: Имя конфигурации

    Returns:
        QueryExplanation с человекочитаемым описанием.
    """
    explainer = QueryExplainer(metadata_index)
    return explainer.explain(query_text, config_name)
