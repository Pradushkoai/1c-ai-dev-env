"""
Phase B — Тесты для QueryGenerator и QueryTemplates.

Проверяет:
1. QueryTemplates — 15 шаблонов, поиск по keywords, заполнение
2. QueryGenerator — генерация запросов по описанию задачи
3. TaskAnalysis — извлечение параметров из описания
4. End-to-end: описание → запрос → параметры → объяснение
"""

from __future__ import annotations

import pytest

from src.services.analyzers.query_generator import (
    GeneratedQuery,
    QueryGenerator,
    TaskAnalysis,
    analyze_task,
    find_objects_in_metadata,
    generate_query,
)
from src.services.analyzers.query_templates import (
    ALL_TEMPLATES,
    QueryTemplate,
    fill_template,
    find_templates_by_keywords,
    get_template_by_name,
    get_templates_by_category,
    list_all_categories,
)


# ============================================================================
# 1. QUERY TEMPLATES
# ============================================================================


class TestQueryTemplates:
    """Тесты библиотеки шаблонов."""

    def test_all_templates_count(self):
        """Должно быть минимум 15 шаблонов."""
        assert len(ALL_TEMPLATES) >= 15

    def test_each_template_has_required_fields(self):
        """Каждый шаблон имеет обязательные поля."""
        for t in ALL_TEMPLATES:
            assert t.name, f"Template missing name: {t}"
            assert t.description, f"Template {t.name} missing description"
            assert t.category, f"Template {t.name} missing category"
            assert len(t.keywords) > 0, f"Template {t.name} missing keywords"
            assert len(t.required_params) > 0, f"Template {t.name} missing required_params"
            assert t.template_text, f"Template {t.name} missing template_text"

    def test_get_template_by_name(self):
        """Поиск шаблона по имени."""
        t = get_template_by_name("simple_select")
        assert t is not None
        assert t.name == "simple_select"

        t = get_template_by_name("nonexistent")
        assert t is None

    def test_get_templates_by_category(self):
        """Поиск шаблонов по категории."""
        basic = get_templates_by_category("basic")
        assert len(basic) >= 4

        virtual = get_templates_by_category("virtual_tables")
        assert len(virtual) >= 3

    def test_list_all_categories(self):
        """Список всех категорий."""
        cats = list_all_categories()
        assert "basic" in cats
        assert "virtual_tables" in cats
        assert "analytics" in cats

    def test_find_templates_by_keywords(self):
        """Поиск шаблонов по ключевым словам."""
        # 'остатки' должно найти register_balances
        results = find_templates_by_keywords("показать остатки товаров на складе")
        assert len(results) > 0
        names = [t.name for t in results]
        assert "register_balances" in names

        # 'топ' должно найти top_n_by_metric
        results = find_templates_by_keywords("топ-10 клиентов по выручке")
        assert len(results) > 0
        names = [t.name for t in results]
        assert "top_n_by_metric" in names

    def test_fill_template_basic(self):
        """Заполнение шаблона параметрами."""
        t = get_template_by_name("simple_select")
        result = fill_template(t, table_name="Справочник.Номенклатура")
        assert "Справочник.Номенклатура" in result
        assert "ВЫБРАТЬ" in result

    def test_fill_template_missing_required(self):
        """Ошибка при отсутствии обязательного параметра."""
        t = get_template_by_name("select_with_filter")
        with pytest.raises(ValueError):
            fill_template(t)  # нет table_name

    def test_fill_template_with_optional(self):
        """Заполнение с optional параметрами (defaults)."""
        t = get_template_by_name("simple_select")
        result = fill_template(t, table_name="Справочник.Товары")
        # filter_field имеет default "Код" — не используется в simple_select, но не падает
        assert "Справочник.Товары" in result


# ============================================================================
# 2. TASK ANALYSIS
# ============================================================================


class TestTaskAnalysis:
    """Тесты анализа описания задачи."""

    def test_detect_period(self):
        """Детектор периода."""
        a = analyze_task("продажи за последний год")
        assert a.has_period is True

        a = analyze_task("показать список товаров")
        assert a.has_period is False

    def test_detect_grouping(self):
        """Детектор группировки."""
        a = analyze_task("группировка по номенклатуре")
        assert a.has_grouping is True

    def test_detect_aggregate(self):
        """Детектор агрегатов."""
        a = analyze_task("сумма выручки по месяцам")
        assert a.has_aggregate is True

    def test_detect_top_n(self):
        """Детектор топ-N с числом."""
        a = analyze_task("топ-15 клиентов по выручке")
        assert a.has_top_n is True
        assert a.limit_n == 15

    def test_detect_top_n_default(self):
        """Детектор топ-N без числа (default 10)."""
        a = analyze_task("покажи топ клиентов")
        assert a.has_top_n is True
        assert a.limit_n == 10

    def test_detect_join(self):
        """Детектор JOIN."""
        a = analyze_task("соединение справочников")
        assert a.has_join is True

    def test_task_type_balances(self):
        """Тип задачи: остатки."""
        a = analyze_task("остатки товаров на складе")
        assert a.task_type == "balances"

    def test_task_type_sales(self):
        """Тип задачи: продажи."""
        a = analyze_task("продажи по месяцам")
        assert a.task_type == "sales"

    def test_task_type_top_n(self):
        """Тип задачи: топ-N."""
        a = analyze_task("топ-10 клиентов")
        assert a.task_type == "top_n"


# ============================================================================
# 3. QUERY GENERATOR
# ============================================================================


class TestQueryGenerator:
    """Тесты генератора запросов."""

    def test_generate_sales_by_period(self):
        """Генерация: продажи по месяцам."""
        result = generate_query("продажи по месяцам за последний год")
        assert result.text != ""
        assert "ВЫБРАТЬ" in result.text
        assert "СУММА" in result.text
        assert "МЕСЯЦ" in result.text  # период по месяцам
        assert "ДатаНачала" in result.parameters
        assert "ДатаКонца" in result.parameters
        assert result.template_name == "sales_by_period"

    def test_generate_balances(self):
        """Генерация: остатки на складе."""
        result = generate_query("остатки товаров на складе")
        assert result.text != ""
        assert "Остатки" in result.text
        assert "Период" in result.parameters
        assert result.template_name == "register_balances"

    def test_generate_top_n(self):
        """Генерация: топ-10 клиентов."""
        result = generate_query("топ-10 клиентов по выручке")
        assert result.text != ""
        assert "ПЕРВЫЕ 10" in result.text
        assert "СУММА" in result.text
        assert "УБЫВ" in result.text  # сортировка по убыванию
        assert result.template_name == "top_n_by_metric"

    def test_generate_simple_select(self):
        """Генерация: простой список."""
        result = generate_query("показать список всех товаров")
        assert result.text != ""
        assert "ВЫБРАТЬ" in result.text
        assert "УПОРЯДОЧИТЬ" in result.text

    def test_generate_with_object_hints(self):
        """Генерация с подсказками объектов."""
        result = generate_query(
            "продажи по месяцам",
            object_hints=["РегистрНакопления.Продажи"],
        )
        assert result.text != ""

    def test_generate_has_explanation(self):
        """Результат содержит объяснение."""
        result = generate_query("топ-5 товаров по выручке")
        assert result.explanation != ""
        assert "Шаблон" in result.explanation or "Тип задачи" in result.explanation

    def test_generate_has_warnings(self):
        """Результат содержит warnings (информационные)."""
        result = generate_query("продажи по месяцам")
        assert len(result.warnings) >= 1  # хотя бы тип задачи

    def test_generate_to_dict(self):
        """Сериализация в dict."""
        result = generate_query("продажи по месяцам")
        d = result.to_dict()
        assert "text" in d
        assert "parameters" in d
        assert "explanation" in d
        assert "template_name" in d


# ============================================================================
# 4. FIND OBJECTS IN METADATA
# ============================================================================


class TestFindObjects:
    """Тесты поиска объектов в метаданных."""

    def test_find_with_hints(self):
        """Поиск с подсказками."""
        metadata = {
            "objects": {
                "AccumulationRegisters": [
                    {"name": "Продажи", "type": "AccumulationRegister", "synonym": "Продажи"},
                ],
                "Catalogs": [
                    {"name": "Номенклатура", "type": "Catalog", "synonym": "Номенклатура"},
                ],
            }
        }
        results = find_objects_in_metadata(
            "продажи", metadata, ["РегистрНакопления.Продажи"]
        )
        assert len(results) >= 1
        # Результат может содержать как Продажи, так и Номенклатура
        names = [r.get("name") for r in results]
        assert "Продажи" in names

    def test_find_autosearch(self):
        """Автопоиск по ключевым словам."""
        metadata = {
            "objects": {
                "AccumulationRegisters": [
                    {"name": "Продажи", "type": "AccumulationRegister", "synonym": "Продажи"},
                ],
            }
        }
        results = find_objects_in_metadata("показать продажи", metadata)
        assert len(results) >= 1
        assert results[0].get("name") == "Продажи"


# ============================================================================
# 5. REGRESSION TESTS — реальные сценарии
# ============================================================================


class TestRealScenarios:
    """Тесты на реальных сценариях использования."""

    def test_scenario_sales_report(self):
        """Сценарий: отчёт по продажам."""
        result = generate_query("продажи по месяцам за последний год")
        assert result.text != ""
        assert "СГРУППИРОВАТЬ" in result.text
        assert "МЕЖДУ" in result.text

    def test_scenario_inventory_check(self):
        """Сценарий: проверка остатков."""
        result = generate_query("остатки товаров на складе на текущую дату")
        assert result.text != ""
        assert "Остатки" in result.text

    def test_scenario_top_customers(self):
        """Сценарий: топ клиентов."""
        result = generate_query("топ-10 клиентов по выручке за год")
        assert result.text != ""
        assert "ПЕРВЫЕ 10" in result.text

    def test_scenario_catalog_tree(self):
        """Сценарий: дерево справочника."""
        result = generate_query("показать иерархию справочника дерево")
        assert result.text != ""
        # Должен сработать catalog_tree шаблон (keywords: дерево, иерархия)
        assert result.template_name == "catalog_tree" or "ИТОГИ" in result.text or "Родитель" in result.text

    def test_scenario_documents_by_period(self):
        """Сценарий: документы за период."""
        result = generate_query("документы за период")
        assert result.text != ""
        assert "Документ" in result.text
        assert "Дата" in result.text
