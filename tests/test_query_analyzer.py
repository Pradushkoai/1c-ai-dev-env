#!/usr/bin/env python3
"""Тесты для query_analyzer.py."""
import os, sys, tempfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from query_analyzer import QueryAnalyzer, QueryIssue


@pytest.fixture
def analyzer():
    return QueryAnalyzer()


class TestSelectStar:
    def test_select_star_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q001' for i in issues)

    def test_select_fields_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ Код, Наименование ИЗ Справочник.Номенклатура";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q001' for i in issues)


class TestNoWhere:
    def test_no_where_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ Код ИЗ Документ.Реализация";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q002' for i in issues)

    def test_with_where_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ Код ИЗ Документ.Реализация ГДЕ Дата > &Начало";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q002' for i in issues)


class TestNoParams:
    def test_hardcoded_value_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ Код ИЗ Справочник.Товары ГДЕ Код = 123";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q003' for i in issues)

    def test_with_params_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ Код ИЗ Справочник.Товары ГДЕ Код = &Код";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q003' for i in issues)


class TestLikePercent:
    def test_like_start_percent_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары ГДЕ Наименование ПОДОБНО \"%текст\"";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q005' for i in issues)

    def test_like_end_percent_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары ГДЕ Наименование ПОДОБНО \"текст%\"";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q005' for i in issues)


class TestFunctionInWhere:
    def test_function_in_where_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.Реализация ГДЕ НАЧАЛОПЕРИОДА(Дата) = &Дата";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q007' for i in issues)

    def test_no_function_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.Реализация ГДЕ Дата = &Дата";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q007' for i in issues)


class TestJoinWithoutOn:
    def test_join_without_on_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары СОЕДИНЕНИЕ Документ.Реализация";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q009' for i in issues)

    def test_join_with_on_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары Т СОЕДИНЕНИЕ Документ.Реализация Д ПО Т.Ссылка = Д.Товар";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q009' for i in issues)


class TestTempTableNoIndex:
    def test_temp_table_no_index_detected(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ПОМЕСТИТЬ ВТ_Товары ИЗ Справочник.Товары";'
        issues = analyzer.analyze_code(code)
        assert any(i.rule_id == 'Q010' for i in issues)

    def test_temp_table_with_index_ok(self, analyzer):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ПОМЕСТИТЬ ВТ_Товары ИЗ Справочник.Товары ИНДЕКСИРОВАТЬ ПО Код";'
        issues = analyzer.analyze_code(code)
        assert not any(i.rule_id == 'Q010' for i in issues)


class TestStats:
    def test_empty(self, analyzer):
        stats = analyzer.get_stats([])
        assert stats['total'] == 0

    def test_mixed(self, analyzer):
        issues = [
            QueryIssue('Q001', 'MEDIUM', 1, 'snip', 'msg'),
            QueryIssue('Q005', 'HIGH', 2, 'snip', 'msg'),
        ]
        stats = analyzer.get_stats(issues)
        assert stats['total'] == 2
        assert 'HIGH' in stats['by_severity']


class TestIntegrationRealData:
    UT11_DIR = Path('/home/z/my-project/repo_work/data/configs/ut11')

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_analyze_ut11(self, analyzer):
        cm_dir = self.UT11_DIR / 'CommonModules'
        if not cm_dir.exists():
            pytest.skip('CommonModules not found')
        issues = analyzer.analyze_path(cm_dir)
        stats = analyzer.get_stats(issues)
        print(f"\n  Найдено проблем: {stats['total']}")
        print(f"  by severity: {stats['by_severity']}")
        assert isinstance(issues, list)
