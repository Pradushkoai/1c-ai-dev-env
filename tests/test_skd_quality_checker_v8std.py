#!/usr/bin/env python3
"""Тесты для усиленных правил SKDQualityChecker (SKD011-SKD015).

Усиление по стандартам v8std.ru / ITS:
- SKD011: Поля периодов без стандартных имён (#std672)
- SKD012: Вариант с именем «Основной» (#std674)
- SKD013: Запрос с РАЗЛИЧНЫЕ/СГРУППИРОВАТЬ ПО в динамическом списке (#std732)
- SKD014: Группировка более 3 уровней вложенности (#std676)
- SKD015: Иерархический список с РаскрыватьВсеУровни (#std489)
"""

import pytest

from src.services.analyzers.skd_quality_checker import SKDIssue, SKDQualityChecker


@pytest.fixture
def checker():
    return SKDQualityChecker()


class TestSKD011NonStandardPeriodFields:
    """SKD011: Поля периодов без стандартных имён (#std672)."""

    def test_non_standard_period_field_detected(self, checker):
        """Поле 'ПериодМесяц' (без точки) — нестандартное."""
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [
                    {
                        "query": "ВЫБРАТЬ ПериодМесяц ИЗ Т",
                        "fields": [{"name": "ПериодМесяц"}],
                    }
                ],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD011" for i in issues)

    def test_standard_period_field_ok(self, checker):
        """Поле 'Период.Месяц' — стандартное."""
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [
                    {
                        "query": "ВЫБРАТЬ Период.Месяц ИЗ Т",
                        "fields": [{"name": "Период.Месяц"}],
                    }
                ],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD011" for i in issues)

    def test_recommendation_contains_std672(self, checker):
        """Recommendation должна ссылаться на #std672."""
        schema = {
            "name": "T",
            "parent_name": "T",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ ПериодГод ИЗ Т", "fields": [{"name": "ПериодГод"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        skd011_issues = [i for i in issues if i.rule_id == "SKD011"]
        assert skd011_issues
        assert "std672" in skd011_issues[0].recommendation


class TestSKD012DefaultVariantName:
    """SKD012: Вариант с именем «Основной» (#std674)."""

    def test_default_variant_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
                "variants": [{"name": "Основной"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD012" for i in issues)

    def test_meaningful_variant_ok(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
                "variants": [{"name": "Анализ продаж"}],
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD012" for i in issues)


class TestSKD013DynamicListDistinct:
    """SKD013: РАЗЛИЧНЫЕ/СГРУППИРОВАТЬ ПО в динамическом списке (#std732)."""

    def test_distinct_in_dynamic_list_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "is_dynamic_list": True,
            "schema": {
                "data_sets": [
                    {"query": "ВЫБРАТЬ РАЗЛИЧНЫЕ Номенклатура ИЗ Т", "fields": [{"name": "F1"}]}
                ],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD013" for i in issues)

    def test_group_by_in_dynamic_list_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "is_dynamic_list": True,
            "schema": {
                "data_sets": [
                    {"query": "ВЫБРАТЬ Ном ИЗ Т СГРУППИРОВАТЬ ПО Ном", "fields": [{"name": "F1"}]}
                ],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD013" for i in issues)

    def test_no_distinct_in_static_schema_ok(self, checker):
        """Не динамический список — РАЗЛИЧНЫЕ разрешено."""
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "is_dynamic_list": False,
            "schema": {
                "data_sets": [
                    {"query": "ВЫБРАТЬ РАЗЛИЧНЫЕ Ном ИЗ Т", "fields": [{"name": "F1"}]}
                ],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD013" for i in issues)


class TestSKD014GroupingNesting:
    """SKD014: Группировка более 3 уровней вложенности (#std676)."""

    def test_deep_nesting_detected(self, checker):
        """4 уровня вложенности — нарушение."""
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
                "settings": {
                    "groupings": [
                        {
                            "name": "L1",
                            "items": [
                                {
                                    "name": "L2",
                                    "items": [
                                        {"name": "L3", "items": [{"name": "L4"}]},
                                    ],
                                }
                            ],
                        }
                    ]
                },
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD014" for i in issues)

    def test_three_levels_ok(self, checker):
        """3 уровня — норма."""
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [{"name": "Сумма"}],
                "data_sources": [{"name": "Src1"}],
                "settings": {
                    "groupings": [
                        {
                            "name": "L1",
                            "items": [{"name": "L2", "items": [{"name": "L3"}]}],
                        }
                    ]
                },
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD014" for i in issues)


class TestSKD015HierarchicalExpandAll:
    """SKD015: Иерархический список с РаскрыватьВсеУровни (#std489)."""

    def test_expand_all_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "is_dynamic_list": True,
            "initial_tree_view": "РаскрыватьВсеУровни",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD015" for i in issues)

    def test_no_expand_ok(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "is_dynamic_list": True,
            "initial_tree_view": "НеРаскрывать",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Т", "fields": [{"name": "F1"}]}],
                "parameters": [{"name": "P1", "types": ["Строка"]}],
                "filters": [{"name": "F1"}],
                "total_fields": [],
                "data_sources": [{"name": "Src1"}],
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD015" for i in issues)


class TestMaxGroupingNestingHelper:
    """Тест утилиты _max_grouping_nesting."""

    def test_empty_list(self, checker):
        assert checker._max_grouping_nesting([]) == 0

    def test_flat_list(self, checker):
        assert checker._max_grouping_nesting([{"name": "A"}, {"name": "B"}]) == 0

    def test_one_level(self, checker):
        data = [{"name": "A", "items": [{"name": "B"}]}]
        assert checker._max_grouping_nesting(data) == 1

    def test_two_levels(self, checker):
        data = [{"name": "A", "items": [{"name": "B", "items": [{"name": "C"}]}]}]
        assert checker._max_grouping_nesting(data) == 2
