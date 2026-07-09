"""
query_templates.py — Библиотека шаблонов запросов 1С.

Phase B of Query Intelligence plan: 15+ шаблонов для генерации запросов.

Категории:
- Базовые: simple_select, select_with_filter, select_with_grouping, select_with_join
- Виртуальные таблицы: register_balances, register_turnovers, info_register_slice_last
- Пакетные: batch_with_temp_table, multi_step_processing
- Аналитика: top_n_by_metric, sales_by_period, cumulative_total
- Справочники: catalog_tree, catalog_by_attribute
- Документы: documents_by_period, documents_with_totals

Каждый шаблон имеет keywords для matching с описанием задачи.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryTemplate:
    """Шаблон запроса 1С для генерации."""

    name: str
    description: str
    category: str
    keywords: list[str]
    required_params: list[str]
    optional_params: dict[str, str]  # param → default value
    template_text: str
    example: str
    pattern_ref: str = ""


# ============================================================================
# БАЗОВЫЕ ШАБЛОНЫ
# ============================================================================

TEMPLATE_SIMPLE_SELECT = QueryTemplate(
    name="simple_select",
    description="Простой запрос — выбрать все записи из таблицы",
    category="basic",
    keywords=["выбрать", "все", "список", "простой", "select", "all", "list"],
    required_params=["table_name"],
    optional_params={"filter_field": "Код"},
    template_text="""ВЫБРАТЬ
    Т.Ссылка,
    Т.Код,
    Т.Наименование
ИЗ
    {table_name} КАК Т
УПОРЯДОЧИТЬ ПО
    Т.Наименование""",
    example="ВЫБРАТЬ Т.Ссылка, Т.Код, Т.Наименование ИЗ Справочник.Номенклатура КАК Т",
    pattern_ref="optimization_patterns.md#no-select-star",
)

TEMPLATE_SELECT_WITH_FILTER = QueryTemplate(
    name="select_with_filter",
    description="Запрос с параметризованным фильтром",
    category="basic",
    keywords=["фильтр", "поиск", "найти", "где", "filter", "search", "find", "where"],
    required_params=["table_name", "filter_field"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Т.Ссылка,
    Т.Код,
    Т.Наименование
ИЗ
    {table_name} КАК Т
ГДЕ
    Т.{filter_field} = &ЗначениеФильтра
УПОРЯДОЧИТЬ ПО
    Т.Наименование""",
    example="ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Номенклатура КАК Т ГДЕ Т.Код = &Код",
    pattern_ref="optimization_patterns.md#parameterized-queries",
)

TEMPLATE_SELECT_WITH_GROUPING = QueryTemplate(
    name="select_with_grouping",
    description="Запрос с группировкой и агрегатными функциями",
    category="basic",
    keywords=["группа", "группировка", "сумма", "итог", "group", "sum", "total"],
    required_params=["table_name", "group_field", "sum_field"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Т.{group_field} КАК Группа,
    СУММА(Т.{sum_field}) КАК Сумма,
    КОЛИЧЕСТВО(*) КАК Количество
ИЗ
    {table_name} КАК Т
СГРУППИРОВАТЬ ПО
    Т.{group_field}
УПОРЯДОЧИТЬ ПО
    Сумма УБЫВ""",
    example="ВЫБРАТЬ Т.Номенклатура, СУММА(Т.Сумма) ИЗ РегистрНакопления.Продажи КАК Т СГРУППИРОВАТЬ ПО Т.Номенклатура",
    pattern_ref="",
)

TEMPLATE_SELECT_WITH_JOIN = QueryTemplate(
    name="select_with_join",
    description="Запрос с соединением таблиц (LEFT JOIN)",
    category="basic",
    keywords=["соединение", "join", "связь", "объединить", "connect", "link"],
    required_params=["main_table", "join_table", "main_field", "join_field"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Т1.Ссылка,
    Т1.Наименование,
    Т2.Наименование КАК СвязаноеНаименование
ИЗ
    {main_table} КАК Т1
    ЛЕВОЕ СОЕДИНЕНИЕ {join_table} КАК Т2
        ПО Т1.{main_field} = Т2.{join_field}""",
    example="ВЫБРАТЬ Т1.Ссылка, Т2.Наименование ИЗ Документ.Заказ КАК Т1 ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК Т2 ПО Т1.Контрагент = Т2.Ссылка",
    pattern_ref="optimization_patterns.md#join-vs-subquery",
)


# ============================================================================
# ВИРТУАЛЬНЫЕ ТАБЛИЦЫ
# ============================================================================

TEMPLATE_REGISTER_BALANCES = QueryTemplate(
    name="register_balances",
    description="Остатки по регистру накопления (виртуальная таблица Остатки)",
    category="virtual_tables",
    keywords=["остаток", "остатки", "на складе", "balance", "stock", "register"],
    required_params=["register_name"],
    optional_params={"dimension_field": "Номенклатура", "balance_field": "КоличествоОстаток"},
    template_text="""ВЫБРАТЬ
    Остатки.{dimension_field},
    Остатки.{balance_field}
ИЗ
    РегистрНакопления.{register_name}.Остатки(
        &Период,
        {dimension_field} В (&СписокОтбора)
    ) КАК Остатки""",
    example="ВЫБРАТЬ Остатки.Номенклатура, Остатки.КоличествоОстаток ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период,) КАК Остатки",
    pattern_ref="optimization_patterns.md#virtual-table-params",
)

TEMPLATE_REGISTER_TURNOVERS = QueryTemplate(
    name="register_turnovers",
    description="Обороты по регистру накопления (виртуальная таблица Обороты)",
    category="virtual_tables",
    keywords=["оборот", "обороты", "движения", "turnover", "movements"],
    required_params=["register_name"],
    optional_params={"dimension_field": "Номенклатура", "turnover_field": "СуммаОборот"},
    template_text="""ВЫБРАТЬ
    Обороты.{dimension_field},
    Обороты.{turnover_field}
ИЗ
    РегистрНакопления.{register_name}.Обороты(
        &ДатаНачала,
        &ДатаКонца,
        ,
        {dimension_field} В (&СписокОтбора)
    ) КАК Обороты""",
    example="ВЫБРАТЬ Обороты.Номенклатура, Обороты.СуммаОборот ИЗ РегистрНакопления.Продажи.Обороты(&ДатаНачала, &ДатаКонца) КАК Обороты",
    pattern_ref="optimization_patterns.md#virtual-table-params",
)

TEMPLATE_INFO_REGISTER_SLICE_LAST = QueryTemplate(
    name="info_register_slice_last",
    description="Срез последних регистра сведений (виртуальная таблица СрезПоследних)",
    category="virtual_tables",
    keywords=["срез последних", "последнее значение", "актуальное", "slice last", "current"],
    required_params=["register_name"],
    optional_params={"dimension_field": "Объект", "value_field": "Значение"},
    template_text="""ВЫБРАТЬ
    Срез.{dimension_field},
    Срез.{value_field}
ИЗ
    РегистрСведений.{register_name}.СрезПоследних(
        &Период,
        {dimension_field} В (&СписокОтбора)
    ) КАК Срез""",
    example="ВЫБРАТЬ Срез.Объект, Срез.Цена ИЗ РегистрСведений.Цены.СрезПоследних(&Период,) КАК Срез",
    pattern_ref="optimization_patterns.md#virtual-table-params",
)


# ============================================================================
# ПАКЕТНЫЕ ЗАПРОСЫ
# ============================================================================

TEMPLATE_BATCH_WITH_TEMP_TABLE = QueryTemplate(
    name="batch_with_temp_table",
    description="Пакетный запрос с временной таблицей и индексом",
    category="batch",
    keywords=["временная таблица", "пакетный", "многошаговый", "temp table", "batch", "multi-step"],
    required_params=["main_table", "temp_name", "index_field"],
    optional_params={"filter_field": "Код"},
    template_text="""ВЫБРАТЬ
    Т.Ссылка,
    Т.{filter_field}
ПОМЕСТИТЬ {temp_name}
ИЗ
    {main_table} КАК Т
ГДЕ
    Т.{filter_field} В (&СписокОтбора)
ИНДЕКСИРОВАТЬ ПО
    {index_field}
;

ВЫБРАТЬ
    ВТ.Ссылка,
    ВТ.{filter_field}
ИЗ
    {temp_name} КАК ВТ""",
    example="ВЫБРАТЬ Т.Ссылка ПОМЕСТИТЬ ВТДанные ИЗ Справочник.Номенклатура КАК Т ГДЕ Т.Код В (&Список) ИНДЕКСИРОВАТЬ ПО Код; ВЫБРАТЬ ВТ.Ссылка ИЗ ВТДанные КАК ВТ",
    pattern_ref="optimization_patterns.md#temp-table-vs-join-subquery",
)


# ============================================================================
# АНАЛИТИКА
# ============================================================================

TEMPLATE_TOP_N_BY_METRIC = QueryTemplate(
    name="top_n_by_metric",
    description="Топ-N записей по метрике (например, топ-10 клиентов по выручке)",
    category="analytics",
    keywords=["топ", "лучшие", "top", "best", "ранжирование", "ranking"],
    required_params=["table_name", "metric_field", "group_field"],
    optional_params={"limit": "10"},
    template_text="""ВЫБРАТЬ ПЕРВЫЕ {limit}
    Т.{group_field},
    СУММА(Т.{metric_field}) КАК Метрика
ИЗ
    {table_name} КАК Т
СГРУППИРОВАТЬ ПО
    Т.{group_field}
УПОРЯДОЧИТЬ ПО
    Метрика УБЫВ""",
    example="ВЫБРАТЬ ПЕРВЫЕ 10 Т.Контрагент, СУММА(Т.Сумма) КАК Выручка ИЗ РегистрНакопления.Продажи КАК Т СГРУППИРОВАТЬ ПО Т.Контрагент УПОРЯДОЧИТЬ ПО Выручка УБЫВ",
    pattern_ref="optimization_patterns.md#select-top-with-order",
)

TEMPLATE_SALES_BY_PERIOD = QueryTemplate(
    name="sales_by_period",
    description="Продажи по периодам (помесячно/понедельно)",
    category="analytics",
    keywords=["продажи", "по месяцам", "по периодам", "выручка", "sales", "by month", "by period", "revenue"],
    required_params=["register_name", "amount_field"],
    optional_params={"period_function": "МЕСЯЦ", "group_field": "Номенклатура"},
    template_text="""ВЫБРАТЬ
    {period_function}(Рег.Период) КАК Период,
    Рег.{group_field},
    СУММА(Рег.{amount_field}) КАК Сумма
ИЗ
    РегистрНакопления.{register_name} КАК Рег
ГДЕ
    Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
СГРУППИРОВАТЬ ПО
    {period_function}(Рег.Период),
    Рег.{group_field}
УПОРЯДОЧИТЬ ПО
    Период,
    Сумма УБЫВ""",
    example="ВЫБРАТЬ МЕСЯЦ(Рег.Период), Рег.Номенклатура, СУММА(Рег.Сумма) ИЗ РегистрНакопления.Продажи КАК Рег ГДЕ Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца СГРУППИРОВАТЬ ПО МЕСЯЦ(Рег.Период), Рег.Номенклатура",
    pattern_ref="",
)

TEMPLATE_CUMULATIVE_TOTAL = QueryTemplate(
    name="cumulative_total",
    description="Накопительный итог (running total)",
    category="analytics",
    keywords=["накопительный", "нарастающий", "cumulative", "running total"],
    required_params=["table_name", "value_field", "date_field"],
    optional_params={"group_field": "Номенклатура"},
    template_text="""ВЫБРАТЬ
    Т.{date_field},
    Т.{group_field},
    Т.{value_field},
    ЕСТЬNULL(Итоги.НакопленныйИтог, 0) КАК НакопленныйИтог
ИЗ
    {table_name} КАК Т
    ЛЕВОЕ СОЕДИНЕНИЕ (
        ВЫБРАТЬ
            Т2.{group_field},
            Т2.{date_field},
            СУММА(Т2.{value_field}) КАК НакопленныйИтог
        ИЗ
            {table_name} КАК Т2
        ГДЕ
            Т2.{date_field} <= Т.{date_field}
        СГРУППИРОВАТЬ ПО
            Т2.{group_field},
            Т2.{date_field}
    ) КАК Итоги
        ПО Т.{group_field} = Итоги.{group_field}
            И Т.{date_field} = Итоги.{date_field}""",
    example="Сложный запрос с накопительным итогом",
    pattern_ref="optimization_patterns.md#temp-table-vs-join-subquery",
)


# ============================================================================
# СПРАВОЧНИКИ
# ============================================================================

TEMPLATE_CATALOG_TREE = QueryTemplate(
    name="catalog_tree",
    description="Иерархический обход справочника (дерево)",
    category="catalogs",
    keywords=["дерево", "иерархия", "родитель", "tree", "hierarchy", "parent"],
    required_params=["catalog_name"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Элементы.Ссылка,
    Элементы.Наименование,
    Элементы.Родитель
ИЗ
    Справочник.{catalog_name} КАК Элементы
ГДЕ
    Элементы.ПометкаУдаления = ЛОЖЬ
УПОРЯДОЧИТЬ ПО
    Элементы.Наименование
ИТОГИ ПО
    Элементы.Родитель""",
    example="ВЫБРАТЬ Элементы.Ссылка, Элементы.Наименование ИЗ Справочник.Номенклатура КАК Элементы ИТОГИ ПО Элементы.Родитель",
    pattern_ref="",
)

TEMPLATE_CATALOG_BY_ATTRIBUTE = QueryTemplate(
    name="catalog_by_attribute",
    description="Выборка элементов справочника по значению реквизита",
    category="catalogs",
    keywords=["по реквизиту", "по свойству", "по атрибуту", "by attribute", "by property"],
    required_params=["catalog_name", "attribute_field"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Элементы.Ссылка,
    Элементы.Код,
    Элементы.Наименование
ИЗ
    Справочник.{catalog_name} КАК Элементы
ГДЕ
    Элементы.{attribute_field} = &ЗначениеАтрибута
    И Элементы.ПометкаУдаления = ЛОЖЬ
УПОРЯДОЧИТЬ ПО
    Элементы.Наименование""",
    example="ВЫБРАТЬ Элементы.Ссылка ИЗ Справочник.Номенклатура КАК Элементы ГДЕ Элементы.ВидНоменклатуры = &Вид",
    pattern_ref="optimization_patterns.md#parameterized-queries",
)


# ============================================================================
# ДОКУМЕНТЫ
# ============================================================================

TEMPLATE_DOCUMENTS_BY_PERIOD = QueryTemplate(
    name="documents_by_period",
    description="Документы за период",
    category="documents",
    keywords=["документы", "за период", "за месяц", "documents", "by period"],
    required_params=["document_name"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Док.Ссылка,
    Док.Номер,
    Док.Дата,
    Док.Проведен
ИЗ
    Документ.{document_name} КАК Док
ГДЕ
    Док.Дата МЕЖДУ &ДатаНачала И &ДатаКонца
УПОРЯДОЧИТЬ ПО
    Док.Дата""",
    example="ВЫБРАТЬ Док.Ссылка, Док.Номер, Док.Дата ИЗ Документ.ЗаказКлиента КАК Док ГДЕ Док.Дата МЕЖДУ &ДатаНачала И &ДатаКонца",
    pattern_ref="optimization_patterns.md#parameterized-queries",
)

TEMPLATE_DOCUMENTS_WITH_TOTALS = QueryTemplate(
    name="documents_with_totals",
    description="Документы с итогами по сумме",
    category="documents",
    keywords=["документы", "итоги", "сумма", "documents", "totals", "sum"],
    required_params=["document_name", "sum_field"],
    optional_params={},
    template_text="""ВЫБРАТЬ
    Док.Ссылка,
    Док.Номер,
    Док.Дата,
    СУММА(ТЧ.{sum_field}) КАК Сумма
ИЗ
    Документ.{document_name} КАК Док
    ЛЕВОЕ СОЕДИНЕНИЕ Документ.{document_name}.Товары КАК ТЧ
        ПО Док.Ссылка = ТЧ.Ссылка
ГДЕ
    Док.Дата МЕЖДУ &ДатаНачала И &ДатаКонца
СГРУППИРОВАТЬ ПО
    Док.Ссылка,
    Док.Номер,
    Док.Дата
УПОРЯДОЧИТЬ ПО
    Сумма УБЫВ""",
    example="ВЫБРАТЬ Док.Ссылка, СУММА(ТЧ.Сумма) ИЗ Документ.ЗаказКлиента КАК Док ЛЕВОЕ СОЕДИНЕНИЕ Документ.ЗаказКлиента.Товары КАК ТЧ ПО Док.Ссылка = ТЧ.Ссылка СГРУППИРОВАТЬ ПО Док.Ссылка",
    pattern_ref="optimization_patterns.md#join-vs-subquery",
)


# ============================================================================
# РЕЕСТР ВСЕХ ШАБЛОНОВ
# ============================================================================


# P2: Scalar query — возвращает одно число
TEMPLATE_SCALAR_QUERY = QueryTemplate(
    name="scalar_query",
    description="Запрос возвращающий одно значение (число) — СУММА, КОЛИЧЕСТВО",
    category="analytics",
    keywords=["сумма", "количество", "итого", "всего", "общая", "одно число", "sum", "count", "total", "scalar"],
    required_params=["table_name", "value_field"],
    optional_params={"aggregate_function": "СУММА", "filter_field": ""},
    template_text="""ВЫБРАТЬ
    {aggregate_function}(Т.{value_field}) КАК Результат
ИЗ
    {table_name} КАК Т
{filter_clause}""",
    example="ВЫБРАТЬ СУММА(Рег.СуммаВыручки - Рег.Себестоимость) КАК Прибыль ИЗ РегистрНакопления.Продажи КАК Рег ГДЕ Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца",
    pattern_ref="optimization_patterns.md#no-select-star",
)


ALL_TEMPLATES: list[QueryTemplate] = [
    TEMPLATE_SIMPLE_SELECT,
    TEMPLATE_SELECT_WITH_FILTER,
    TEMPLATE_SELECT_WITH_GROUPING,
    TEMPLATE_SELECT_WITH_JOIN,
    TEMPLATE_REGISTER_BALANCES,
    TEMPLATE_REGISTER_TURNOVERS,
    TEMPLATE_INFO_REGISTER_SLICE_LAST,
    TEMPLATE_BATCH_WITH_TEMP_TABLE,
    TEMPLATE_TOP_N_BY_METRIC,
    TEMPLATE_SALES_BY_PERIOD,
    TEMPLATE_CUMULATIVE_TOTAL,
    TEMPLATE_CATALOG_TREE,
    TEMPLATE_CATALOG_BY_ATTRIBUTE,
    TEMPLATE_DOCUMENTS_BY_PERIOD,
    TEMPLATE_DOCUMENTS_WITH_TOTALS,
    # P2: scalar query — возвращает одно число
    TEMPLATE_SCALAR_QUERY,
]


def get_template_by_name(name: str) -> QueryTemplate | None:
    """Возвращает шаблон по имени."""
    for t in ALL_TEMPLATES:
        if t.name == name:
            return t
    return None


def get_templates_by_category(category: str) -> list[QueryTemplate]:
    """Возвращает шаблоны по категории."""
    return [t for t in ALL_TEMPLATES if t.category == category]


def list_all_categories() -> list[str]:
    """Возвращает список всех категорий шаблонов."""
    return sorted({t.category for t in ALL_TEMPLATES})


def find_templates_by_keywords(text: str) -> list[QueryTemplate]:
    """Находит шаблоны по ключевым словам в описании задачи.

    Возвращает отсортированный по количеству совпадений.
    """
    text_lower = text.lower()
    scored: list[tuple[int, QueryTemplate]] = []
    for t in ALL_TEMPLATES:
        score = sum(1 for kw in t.keywords if kw.lower() in text_lower)
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


def fill_template(template: QueryTemplate, **params: str) -> str:
    """Заполняет шаблон параметрами.

    Args:
        template: Шаблон запроса
        **params: Параметры для подстановки (table_name, filter_field, и т.д.)

    Returns:
        Заполненный текст запроса.

    Raises:
        ValueError: Если не передан обязательный параметр.
    """
    # Проверяем обязательные параметры
    for required in template.required_params:
        if required not in params:
            raise ValueError(f"Missing required parameter: {required}")

    # Добавляем optional_params со значениями по умолчанию
    final_params = dict(template.optional_params)
    final_params.update(params)

    return template.template_text.format(**final_params)
