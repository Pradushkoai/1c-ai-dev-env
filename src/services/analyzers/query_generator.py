"""
query_generator.py — Генератор запросов 1С по описанию задачи.

Phase B of Query Intelligence plan: пользователь описывает задачу → получает
готовый текст запроса.

Алгоритм:
1. Парсинг описания — извлечь ключевые слова (период, группировка, фильтр, сортировка)
2. Поиск объектов — по ключевым словам найти подходящие таблицы в metadata_index
3. Выбор шаблона — matching описания с шаблонами из QueryTemplates
4. Заполнение шаблона — подставить реальные имена полей из metadata
5. Валидация — прогнать через SDBL парсер (если доступен)
6. Объяснение — сгенерировать человекочитаемое описание

Лицензия: MIT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.services.analyzers.query_templates import (
    ALL_TEMPLATES,
    QueryTemplate,
    fill_template,
    find_templates_by_keywords,
)


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class GeneratedQuery:
    """Результат генерации запроса."""

    text: str = ""
    parameters: list[str] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    explanation: str = ""
    pattern_used: str = ""
    template_name: str = ""
    warnings: list[str] = field(default_factory=list)
    has_syntax_error: bool = False
    parse_error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "parameters": self.parameters,
            "tables_used": self.tables_used,
            "explanation": self.explanation,
            "pattern_used": self.pattern_used,
            "template_name": self.template_name,
            "warnings": self.warnings,
            "has_syntax_error": self.has_syntax_error,
            "parse_error_message": self.parse_error_message,
        }


# ============================================================================
# АНАЛИЗ ОПИСАНИЯ ЗАДАЧИ
# ============================================================================


@dataclass
class TaskAnalysis:
    """Анализ описания задачи — извлечённые параметры."""

    task_type: str = ""  # 'select', 'balances', 'turnovers', 'top_n', 'sales', 'tree'
    has_period: bool = False
    has_grouping: bool = False
    has_aggregate: bool = False
    has_filter: bool = False
    has_top_n: bool = False
    has_join: bool = False
    limit_n: int = 0
    keywords_found: list[str] = field(default_factory=list)
    object_hints: list[str] = field(default_factory=list)


def analyze_task(task_description: str) -> TaskAnalysis:
    """Анализирует описание задачи и извлекает параметры.

    Args:
        task_description: Описание задачи на русском или английском

    Returns:
        TaskAnalysis с извлечёнными параметрами.
    """
    text_lower = task_description.lower()
    analysis = TaskAnalysis()

    # Период
    period_keywords = ["период", "за месяц", "за год", "за неделю", "по месяцам",
                       "по периодам", "за последний", "за текущий", "прошлый",
                       "period", "by month", "by year", "date range", "last year"]
    if any(kw in text_lower for kw in period_keywords):
        analysis.has_period = True
        analysis.keywords_found.append("period")

    # Группировка
    group_keywords = ["группа", "группировка", "по группам", "по номенклатуре",
                      "по складу", "group", "grouping", "by"]
    if any(kw in text_lower for kw in group_keywords):
        analysis.has_grouping = True
        analysis.keywords_found.append("grouping")

    # Агрегаты
    agg_keywords = ["сумма", "количество", "итог", "sum", "count", "total"]
    if any(kw in text_lower for kw in agg_keywords):
        analysis.has_aggregate = True
        analysis.keywords_found.append("aggregate")

    # Фильтр
    filter_keywords = ["фильтр", "поиск", "найти", "где", "по коду",
                       "по наименованию", "filter", "search", "where"]
    if any(kw in text_lower for kw in filter_keywords):
        analysis.has_filter = True
        analysis.keywords_found.append("filter")

    # Топ-N
    top_match = re.search(r"(?:топ|top)\s*[-]?\s*(\d+)", text_lower)
    if top_match:
        analysis.has_top_n = True
        analysis.limit_n = int(top_match.group(1))
        analysis.keywords_found.append("top_n")
    elif any(kw in text_lower for kw in ["топ", "лучшие", "top", "best"]):
        analysis.has_top_n = True
        analysis.limit_n = 10  # по умолчанию
        analysis.keywords_found.append("top_n")

    # JOIN
    join_keywords = ["соединение", "join", "связь", "объединить", "connect", "link"]
    if any(kw in text_lower for kw in join_keywords):
        analysis.has_join = True
        analysis.keywords_found.append("join")

    # Тип задачи
    if any(kw in text_lower for kw in ["остаток", "остатки", "на складе", "balance", "stock"]):
        analysis.task_type = "balances"
    elif any(kw in text_lower for kw in ["оборот", "обороты", "движения", "turnover"]):
        analysis.task_type = "turnovers"
    elif analysis.has_top_n:
        analysis.task_type = "top_n"
    elif any(kw in text_lower for kw in ["продажи", "выручка", "sales", "revenue"]):
        analysis.task_type = "sales"
    elif any(kw in text_lower for kw in ["дерево", "иерархия", "tree", "hierarchy"]):
        analysis.task_type = "tree"
    else:
        analysis.task_type = "select"

    return analysis


# ============================================================================
# ПОИСК ОБЪЕКТОВ В МЕТАДАННЫХ
# ============================================================================


def find_objects_in_metadata(
    task_description: str,
    metadata_index: dict[str, Any],
    object_hints: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Находит подходящие объекты метаданных по описанию задачи.

    Args:
        task_description: Описание задачи
        metadata_index: Содержимое unified-metadata-index.json
        object_hints: Подсказки какие объекты использовать

    Returns:
        Список найденных объектов метаданных.
    """
    if object_hints:
        # Используем подсказки — ищем конкретные объекты
        results: list[dict[str, Any]] = []
        all_objects: list[dict[str, Any]] = []
        for obj_type, objs in metadata_index.get("objects", {}).items():
            for obj in objs:
                obj_dict = dict(obj)
                obj_dict["type_plural"] = obj_type
                all_objects.append(obj_dict)

        # Маппинг английских типов (из metadata) на русские (из hints)
        type_ru_to_en = {
            "Справочник": "Catalog",
            "Документ": "Document",
            "РегистрНакопления": "AccumulationRegister",
            "РегистрСведений": "InformationRegister",
            "РегистрБухгалтерии": "AccountingRegister",
            "РегистрРасчета": "CalculationRegister",
            "ПланСчетов": "ChartOfAccounts",
            "ПланВидовХарактеристик": "ChartOfCharacteristicTypes",
            "ПланВидовРасчета": "ChartOfCalculationTypes",
            "ПланОбмена": "ExchangePlan",
            "БизнесПроцесс": "BusinessProcess",
            "Задача": "Task",
            "Перечисление": "Enum",
            "Константа": "Constant",
            "Обработка": "DataProcessor",
            "Отчет": "Report",
        }
        type_en_to_ru = {v: k for k, v in type_ru_to_en.items()}

        for hint in object_hints:
            hint_lower = hint.lower()
            for obj in all_objects:
                name = obj.get("name", "").lower()
                synonym = obj.get("synonym", "").lower()
                obj_type = obj.get("type", "")
                # Полное имя в двух вариантах: русском и английском
                ru_type = type_en_to_ru.get(obj_type, obj_type)
                full_name_ru = f"{ru_type}.{obj.get('name', '')}".lower()
                full_name_en = f"{obj_type}.{obj.get('name', '')}".lower()
                if hint_lower in name or hint_lower in synonym or hint_lower in full_name_ru or hint_lower in full_name_en or name in hint_lower:
                    if obj not in results:
                        results.append(obj)
        return results

    # Автопоиск по ключевым словам в описании
    text_lower = task_description.lower()
    results = []
    all_objects = []
    for obj_type, objs in metadata_index.get("objects", {}).items():
        for obj in objs:
            obj_dict = dict(obj)
            obj_dict["type_plural"] = obj_type
            all_objects.append(obj_dict)

    for obj in all_objects:
        name = obj.get("name", "").lower()
        synonym = obj.get("synonym", "").lower()
        # Проверяем вхождение слов из описания в имя или синоним
        words = re.findall(r"[а-яёa-z]{3,}", text_lower)
        score = 0
        for word in words:
            if word in name or word in synonym:
                score += 1
        if score > 0:
            results.append({**obj, "_score": score})

    # Сортируем по релевантности
    results.sort(key=lambda x: -x.get("_score", 0))
    return results[:10]  # топ-10


# ============================================================================
# ГЕНЕРАТОР
# ============================================================================


class QueryGenerator:
    """Генератор запросов 1С по описанию задачи.

    Использует:
    - QueryTemplates для выбора шаблона
    - metadata_index для поиска реальных объектов и полей
    - SDBL parser (опционально) для валидации сгенерированного запроса
    """

    def __init__(self, metadata_index: dict[str, Any] | None = None):
        self.metadata = metadata_index or {}
        self._init_sdbl()

    def _init_sdbl(self):
        """Инициализация SDBL парсера (опционально)."""
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

    def generate(
        self,
        task_description: str,
        config_name: str = "",
        object_hints: list[str] | None = None,
    ) -> GeneratedQuery:
        """Сгенерировать запрос по описанию задачи.

        Args:
            task_description: Описание задачи на русском
                Примеры: "продажи по месяцам за последний год",
                         "остатки товаров на складе",
                         "топ-10 клиентов по выручке"
            config_name: Имя конфигурации для поиска объектов
            object_hints: Подсказки какие объекты использовать
                Пример: ["РегистрНакопления.Продажи", "Справочник.Номенклатура"]

        Returns:
            GeneratedQuery с текстом, параметрами, объяснением
        """
        result = GeneratedQuery()

        # 1. Анализ описания задачи
        analysis = analyze_task(task_description)
        result.warnings.append(f"Тип задачи: {analysis.task_type}")

        # 2. Поиск подходящих шаблонов
        templates = find_templates_by_keywords(task_description)
        if not templates:
            # Fallback — выбираем по типу задачи
            templates = self._fallback_templates(analysis)

        if not templates:
            result.warnings.append("Не найден подходящий шаблон. Используйте query_templates для просмотра доступных.")
            return result

        template = templates[0]
        result.template_name = template.name
        result.pattern_used = template.pattern_ref

        # 3. Поиск объектов в метаданных
        objects = find_objects_in_metadata(
            task_description, self.metadata, object_hints
        )

        # 4. Заполнение шаблона
        try:
            params = self._extract_params(task_description, template, objects, analysis)
            query_text = fill_template(template, **params)
            result.text = query_text
            result.tables_used = [params.get("table_name", params.get("register_name", params.get("catalog_name", "")))]
        except (ValueError, KeyError) as e:
            result.warnings.append(f"Не удалось заполнить шаблон: {e}")
            # Возвращаем пример шаблона
            result.text = template.example
            return result

        # 5. Извлечение параметров (&Параметр)
        result.parameters = re.findall(r"&([А-Яа-яA-Za-z_]\w*)", query_text)

        # 6. Валидация через SDBL (опционально)
        if self._sdbl_available and self._sdbl_parser:
            try:
                batch = self._sdbl_parser.parse(query_text)
                if batch.has_syntax_error:
                    result.has_syntax_error = True
                    result.parse_error_message = batch.parse_error_message
                    result.warnings.append(f"SDBL syntax error: {batch.parse_error_message}")
            except Exception as e:
                result.warnings.append(f"SDBL validation failed: {e}")

        # 7. Объяснение
        result.explanation = self._generate_explanation(template, analysis, params)

        return result

    def _fallback_templates(self, analysis: TaskAnalysis) -> list[QueryTemplate]:
        """Выбирает шаблоны по типу задачи, если keywords не сработали."""
        from src.services.analyzers.query_templates import (
            TEMPLATE_BATCH_WITH_TEMP_TABLE,
            TEMPLATE_CATALOG_TREE,
            TEMPLATE_REGISTER_BALANCES,
            TEMPLATE_REGISTER_TURNOVERS,
            TEMPLATE_SALES_BY_PERIOD,
            TEMPLATE_SELECT_WITH_FILTER,
            TEMPLATE_SELECT_WITH_GROUPING,
            TEMPLATE_SELECT_WITH_JOIN,
            TEMPLATE_SIMPLE_SELECT,
            TEMPLATE_TOP_N_BY_METRIC,
        )

        type_to_templates = {
            "balances": [TEMPLATE_REGISTER_BALANCES],
            "turnovers": [TEMPLATE_REGISTER_TURNOVERS],
            "top_n": [TEMPLATE_TOP_N_BY_METRIC],
            "sales": [TEMPLATE_SALES_BY_PERIOD],
            "tree": [TEMPLATE_CATALOG_TREE],
            "select": [TEMPLATE_SIMPLE_SELECT, TEMPLATE_SELECT_WITH_FILTER],
        }
        return type_to_templates.get(analysis.task_type, [TEMPLATE_SIMPLE_SELECT])

    def _extract_params(
        self,
        task_description: str,
        template: QueryTemplate,
        objects: list[dict[str, Any]],
        analysis: TaskAnalysis,
    ) -> dict[str, str]:
        """Извлекает параметры для заполнения шаблона."""
        params: dict[str, str] = {}

        # table_name / register_name / catalog_name / document_name
        full_name = ""
        if objects:
            obj = objects[0]
            obj_type = obj.get("type", "")
            obj_name = obj.get("name", "")
            # Маппинг типов
            type_map = {
                "Catalog": "Справочник",
                "Document": "Документ",
                "AccumulationRegister": "РегистрНакопления",
                "InformationRegister": "РегистрСведений",
                "AccountingRegister": "РегистрБухгалтерии",
            }
            ru_type = type_map.get(obj_type, obj_type)
            full_name = f"{ru_type}.{obj_name}"

        if "table_name" in template.required_params:
            params["table_name"] = full_name or "Справочник.Номенклатура"
        if "register_name" in template.required_params:
            params["register_name"] = obj_name if objects else "Продажи"
        if "catalog_name" in template.required_params:
            params["catalog_name"] = obj_name if objects else "Номенклатура"
        if "document_name" in template.required_params:
            params["document_name"] = obj_name if objects else "ЗаказКлиента"
        if "main_table" in template.required_params:
            params["main_table"] = full_name or "Документ.ЗаказКлиента"
        if "join_table" in template.required_params:
            params["join_table"] = "Справочник.Контрагенты"

        # Поля
        if "filter_field" in template.required_params:
            params["filter_field"] = "Код"
        if "group_field" in template.required_params:
            params["group_field"] = "Номенклатура"
        if "sum_field" in template.required_params:
            params["sum_field"] = "Сумма"
        if "amount_field" in template.required_params:
            params["amount_field"] = "Сумма"
        if "metric_field" in template.required_params:
            params["metric_field"] = "Сумма"
        if "main_field" in template.required_params:
            params["main_field"] = "Контрагент"
        if "join_field" in template.required_params:
            params["join_field"] = "Ссылка"
        if "value_field" in template.required_params:
            params["value_field"] = "Значение"
        if "dimension_field" in template.required_params:
            params["dimension_field"] = "Номенклатура"
        if "balance_field" in template.required_params:
            params["balance_field"] = "КоличествоОстаток"
        if "turnover_field" in template.required_params:
            params["turnover_field"] = "СуммаОборот"
        if "attribute_field" in template.required_params:
            params["attribute_field"] = "ВидНоменклатуры"
        if "date_field" in template.required_params:
            params["date_field"] = "Дата"
        if "index_field" in template.required_params:
            params["index_field"] = "Код"
        if "temp_name" in template.required_params:
            params["temp_name"] = "ВТДанные"

        # Limit для топ-N
        if "limit" in template.required_params or "limit" in template.optional_params:
            params["limit"] = str(analysis.limit_n or 10)

        # Period function
        if "period_function" in template.optional_params:
            if "по месяцам" in task_description.lower() or "by month" in task_description.lower():
                params["period_function"] = "МЕСЯЦ"
            elif "по неделям" in task_description.lower():
                params["period_function"] = "НЕДЕЛЯ"
            elif "по годам" in task_description.lower() or "by year" in task_description.lower():
                params["period_function"] = "ГОД"
            elif "по дням" in task_description.lower():
                params["period_function"] = "ДЕНЬ"

        return params

    def _generate_explanation(
        self,
        template: QueryTemplate,
        analysis: TaskAnalysis,
        params: dict[str, str],
    ) -> str:
        """Генерирует человекочитаемое объяснение запроса."""
        parts: list[str] = []

        parts.append(f"Шаблон: {template.name} — {template.description}")
        parts.append(f"Тип задачи: {analysis.task_type}")

        if params.get("table_name") or params.get("register_name") or params.get("catalog_name"):
            table = (
                params.get("table_name")
                or params.get("register_name")
                or params.get("catalog_name")
                or ""
            )
            parts.append(f"Источник данных: {table}")

        if analysis.has_grouping:
            parts.append(f"Группировка по: {params.get('group_field', 'не указано')}")

        if analysis.has_aggregate:
            parts.append("Агрегатные функции: СУММА, КОЛИЧЕСТВО")

        if analysis.has_filter:
            parts.append(f"Фильтр по: {params.get('filter_field', 'не указано')}")

        if analysis.has_top_n:
            parts.append(f"Ограничение: ТОП-{analysis.limit_n}")

        if analysis.has_period:
            parts.append("Период: &ДатаНачала И &ДатаКонца")

        if template.pattern_ref:
            parts.append(f"Паттерн: {template.pattern_ref}")

        return ". ".join(parts) + "."


# ============================================================================
# PUBLIC API
# ============================================================================


def generate_query(
    task_description: str,
    metadata_index: dict[str, Any] | None = None,
    config_name: str = "",
    object_hints: list[str] | None = None,
) -> GeneratedQuery:
    """Удобная функция для генерации запроса.

    Args:
        task_description: Описание задачи
        metadata_index: Метаданные конфигурации (опционально)
        config_name: Имя конфигурации
        object_hints: Подсказки какие объекты использовать

    Returns:
        GeneratedQuery с текстом запроса.
    """
    generator = QueryGenerator(metadata_index)
    return generator.generate(task_description, config_name, object_hints)
