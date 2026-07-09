"""
Phase C — Тесты для QueryExplainer и QueryOptimizer.
"""

from __future__ import annotations

import pytest

from src.services.analyzers.query_explainer import (
    QueryExplainer,
    QueryExplanation,
    explain_query,
)
from src.services.analyzers.query_optimizer import (
    OptimizationResult,
    OptimizationSuggestion,
    QueryOptimizer,
    optimize_query,
)


# ============================================================================
# QUERY EXPLAINER
# ============================================================================


class TestQueryExplainer:
    """Тесты объяснения запросов."""

    def test_explain_simple_select(self):
        """Объяснение простого SELECT."""
        q = "ВЫБРАТЬ Т.Ссылка, Т.Наименование ИЗ Справочник.Номенклатура КАК Т"
        result = explain_query(q)
        assert result.summary != ""
        assert len(result.tables) >= 1
        assert len(result.fields) >= 1

    def test_explain_with_aggregate(self):
        """Объяснение запроса с агрегатом."""
        q = """ВЫБРАТЬ Рег.Номенклатура, СУММА(Рег.Выручка) КАК Сумма
        ИЗ РегистрНакопления.Продажи КАК Рег СГРУППИРОВАТЬ ПО Рег.Номенклатура"""
        result = explain_query(q)
        assert len(result.aggregates) >= 1
        assert result.aggregates[0]["function"] == "SUM"

    def test_explain_with_grouping(self):
        """Объяснение запроса с группировкой."""
        q = """ВЫБРАТЬ Т.Склад, СУММА(Т.Сумма) КАК Сумма
        ИЗ РегистрНакопления.Продажи КАК Т СГРУППИРОВАТЬ ПО Т.Склад"""
        result = explain_query(q)
        assert len(result.grouping) >= 1

    def test_explain_with_parameters(self):
        """Объяснение запроса с параметрами."""
        q = """ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Номенклатура КАК Т
        ГДЕ Т.Код = &Код"""
        result = explain_query(q)
        assert "Код" in result.parameters

    def test_explain_empty_query(self):
        """Объяснение пустого запроса."""
        result = explain_query("")
        assert "Пустой" in result.summary or result.summary == ""

    def test_explain_result_shape(self):
        """Описание структуры результата."""
        # Сводная таблица
        q = "ВЫБРАТЬ Т.Группа, СУММА(Т.Сумма) ИЗ РегистрНакопления.Продажи КАК Т СГРУППИРОВАТЬ ПО Т.Группа"
        result = explain_query(q)
        assert "Сводная" in result.result_shape or "групп" in result.result_shape.lower()

    def test_explain_to_dict(self):
        """Сериализация в dict."""
        q = "ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Номенклатура КАК Т"
        result = explain_query(q)
        d = result.to_dict()
        assert "summary" in d
        assert "tables" in d
        assert "fields" in d


# ============================================================================
# QUERY OPTIMIZER
# ============================================================================


class TestQueryOptimizer:
    """Тесты оптимизатора запросов."""

    def test_optimize_select_star(self):
        """Обнаружение SELECT *."""
        q = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура"
        result = optimize_query(q)
        # Должно быть предложение про SELECT *
        all_suggestions = result.issues + result.suggestions
        assert any("SELECT *" in s.message or "ВЫБРАТЬ *" in s.message for s in all_suggestions)

    def test_optimize_like_start_percent(self):
        """Обнаружение ПОДОБНО '%...'."""
        q = 'ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Номенклатура КАК Т ГДЕ Т.Наименование ПОДОБНО "%текст"'
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("ПОДОБНО" in s.message for s in all_suggestions)

    def test_optimize_or_in_where(self):
        """Обнаружение ИЛИ в WHERE."""
        q = "ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Т КАК Т ГДЕ Т.А = &А ИЛИ Т.Б = &Б"
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("ИЛИ" in s.message or "O002" == s.rule_id for s in all_suggestions)

    def test_optimize_virtual_table_without_filter(self):
        """Виртуальная таблица без фильтра в параметрах + WHERE."""
        q = """ВЫБРАТЬ Остатки.Номенклатура
        ИЗ РегистрНакопления.Товары.Остатки(&Период) КАК Остатки
        ГДЕ Остатки.Склад = &Склад"""
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("O005" == s.rule_id for s in all_suggestions)

    def test_optimize_join_with_subquery(self):
        """JOIN с подзапросом."""
        q = """ВЫБРАТЬ Т.Ссылка
        ИЗ Справочник.Т КАК Т
        ЛЕВОЕ СОЕДИНЕНИЕ (ВЫБРАТЬ ... СГРУППИРОВАТЬ ПО ...) КАК Итоги ПО Т.Ключ = Итоги.Ключ"""
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("O004" == s.rule_id for s in all_suggestions)

    def test_optimize_temp_table_without_index(self):
        """Временная таблица без индекса."""
        q = """ВЫБРАТЬ Т.Ссылка ПОМЕСТИТЬ ВТДанные ИЗ Справочник.Т КАК Т;
        ВЫБРАТЬ ВТ.Ссылка ИЗ ВТДанные КАК ВТ"""
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("O007" == s.rule_id for s in all_suggestions)

    def test_optimize_select_top_without_order(self):
        """SELECT TOP без ORDER BY."""
        q = "ВЫБРАТЬ ПЕРВЫЕ 10 Т.Ссылка ИЗ Справочник.Т КАК Т"
        result = optimize_query(q)
        all_suggestions = result.issues + result.suggestions
        assert any("O001" == s.rule_id for s in all_suggestions)

    def test_optimize_clean_query(self):
        """Чистый запрос — нет проблем."""
        q = """ВЫБРАТЬ Т.Ссылка, Т.Наименование
        ИЗ Справочник.Номенклатура КАК Т
        ГДЕ Т.Код = &Код
        УПОРЯДОЧИТЬ ПО Т.Наименование"""
        result = optimize_query(q)
        # Должно быть минимум проблем
        assert result.total_issues == 0 or result.total_issues <= 1

    def test_optimize_summary(self):
        """Summary содержит информацию о проблемах."""
        q = "ВЫБРАТЬ * ИЗ Справочник.Т"
        result = optimize_query(q)
        assert result.summary != ""

    def test_optimize_to_dict(self):
        """Сериализация в dict."""
        q = "ВЫБРАТЬ * ИЗ Справочник.Т"
        result = optimize_query(q)
        d = result.to_dict()
        assert "issues" in d
        assert "suggestions" in d
        assert "summary" in d

    def test_optimize_pattern_refs(self):
        """Ссылки на паттерны knowledge base."""
        q = "ВЫБРАТЬ * ИЗ Справочник.Т"
        result = optimize_query(q)
        # Должна быть ссылка на no-select-star
        assert any("no-select-star" in ref for ref in result.pattern_refs)

    def test_optimize_empty_query(self):
        """Пустой запрос."""
        result = optimize_query("")
        assert "Пустой" in result.summary or result.total_issues == 0
