#!/usr/bin/env python3
"""Тесты для code_metrics.py."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from code_metrics import CodeMetrics, CodeMetricsAnalyzer, MethodMetrics


@pytest.fixture
def analyzer():
    return CodeMetricsAnalyzer()


# ============================================================================
# LOC
# ============================================================================


class TestLOC:
    def test_total_lines(self, analyzer):
        code = "Строка1\nСтрока2\nСтрока3\n"
        m = analyzer.analyze_code(code)
        assert m.total_lines == 4  # 3 строки + пустая в конце

    def test_code_lines(self, analyzer):
        code = "А = 1;\nБ = 2;\n// Комментарий\n\nВ = 3;\n"
        m = analyzer.analyze_code(code)
        assert m.code_lines == 3
        assert m.comment_lines == 1
        assert m.blank_lines == 2  # пустая строка + trailing newline


# ============================================================================
# МЕТОДЫ
# ============================================================================


class TestMethods:
    def test_procedure_found(self, analyzer):
        code = "Процедура МояПроцедура()\n\tА = 1;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert len(m.methods) == 1
        assert m.methods[0].name == "МояПроцедура"
        assert m.methods[0].method_type == "Процедура"
        assert m.procedures_count == 1

    def test_function_found(self, analyzer):
        code = "Функция МояФункция()\n\tВозврат 1;\nКонецФункции\n"
        m = analyzer.analyze_code(code)
        assert len(m.methods) == 1
        assert m.methods[0].name == "МояФункция"
        assert m.functions_count == 1

    def test_export_detected(self, analyzer):
        code = "Процедура Экспортная() Экспорт\n\tА = 1;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.methods[0].is_export is True
        assert m.export_count == 1

    def test_params_count(self, analyzer):
        code = "Функция СПараметрами(А, Б, В, Г)\n\tВозврат А;\nКонецФункции\n"
        m = analyzer.analyze_code(code)
        assert m.methods[0].param_count == 4

    def test_no_params(self, analyzer):
        code = "Процедура БезПараметров()\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.methods[0].param_count == 0

    def test_method_loc(self, analyzer):
        code = "Процедура Длинная()\n\tА = 1;\n\tБ = 2;\n\tВ = 3;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.methods[0].loc == 5  # 5 строк включая Процедура и КонецПроцедуры


# ============================================================================
# СЛОЖНОСТЬ
# ============================================================================


class TestComplexity:
    def test_simple_code_complexity(self, analyzer):
        code = "А = 1;\nБ = 2;\n"
        m = analyzer.analyze_code(code)
        assert m.total_cyclomatic >= 1  # базовая сложность

    def test_if_increases_complexity(self, analyzer):
        code = "Если А > 0 Тогда\n\tБ = 1;\nКонецЕсли;\n"
        m = analyzer.analyze_code(code)
        assert m.total_cyclomatic >= 2  # базовая + Если

    def test_loop_increases_complexity(self, analyzer):
        code = "Для i = 1 По 10 Цикл\n\tА = i;\nКонецЦикла;\n"
        m = analyzer.analyze_code(code)
        assert m.total_cyclomatic >= 2

    def test_nested_if_complexity(self, analyzer):
        code = "Если А > 0 Тогда\n\tЕсли Б > 0 Тогда\n\t\tВ = 1;\n\tКонецЕсли;\nКонецЕсли;\n"
        m = analyzer.analyze_code(code)
        assert m.total_cyclomatic >= 3

    def test_method_complexity(self, analyzer):
        code = "Функция Сложная(А)\n\tЕсли А > 0 Тогда\n\t\tВозврат 1;\n\tИначе\n\t\tВозврат 0;\n\tКонецЕсли;\nКонецФункции\n"
        m = analyzer.analyze_code(code)
        assert m.methods[0].cyclomatic_complexity >= 2

    def test_nesting_depth(self, analyzer):
        code = "Процедура Тест()\n\tЕсли А Тогда\n\t\tЕсли Б Тогда\n\t\t\tЕсли В Тогда\n\t\t\t\tА = 1;\n\t\t\tКонецЕсли;\n\t\tКонецЕсли;\n\tКонецЕсли;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.max_nesting >= 3  # 3 уровня Если внутри процедуры


# ============================================================================
# ПРОБЛЕМЫ
# ============================================================================


class TestIssues:
    def test_long_method_detected(self, analyzer):
        code = "Процедура Длинная()\n" + "\tА = 1;\n" * 60 + "КонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert len(m.long_methods) == 1

    def test_short_method_ok(self, analyzer):
        code = "Процедура Короткая()\n\tА = 1;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert len(m.long_methods) == 0

    def test_too_many_params(self, analyzer):
        code = "Процедура МногоПарам(А, Б, В, Г, Д, Е, Ж)\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert len(m.too_many_params) == 1

    def test_god_object_by_lines(self, analyzer):
        code = "А = 1;\n" * 1100
        m = analyzer.analyze_code(code)
        assert m.is_god_object is True

    def test_not_god_object(self, analyzer):
        code = "А = 1;\nБ = 2;\n"
        m = analyzer.analyze_code(code)
        assert m.is_god_object is False


# ============================================================================
# ДУБЛИРОВАНИЕ
# ============================================================================


class TestDuplicates:
    def test_duplicate_blocks_found(self, analyzer):
        block = "\tА = 1;\n\tБ = 2;\n\tВ = 3;\n\tГ = 4;\n\tД = 5;\n\tЕ = 6;\n"
        code = block + "\n// Разделитель\n" + block
        m = analyzer.analyze_code(code)
        assert m.duplicate_blocks >= 1

    def test_no_duplicates(self, analyzer):
        code = "А = 1;\nБ = 2;\nВ = 3;\n"
        m = analyzer.analyze_code(code)
        assert m.duplicate_blocks == 0


# ============================================================================
# HEALTH SCORE
# ============================================================================


class TestHealthScore:
    def test_clean_code_high_score(self, analyzer):
        code = "Процедура Короткая()\n\tА = 1;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.health_score >= 90

    def test_god_object_low_score(self, analyzer):
        code = "А = 1;\n" * 1100
        m = analyzer.analyze_code(code)
        assert m.health_score < 70

    def test_long_method_reduces_score(self, analyzer):
        code = "Процедура Длинная()\n" + "\tА = 1;\n" * 60 + "КонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.health_score < 95


# ============================================================================
# ТЕХДОЛГ
# ============================================================================


class TestTechnicalDebt:
    def test_clean_code_zero_debt(self, analyzer):
        code = "Процедура Короткая()\n\tА = 1;\nКонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.technical_debt_minutes == 0

    def test_long_method_adds_debt(self, analyzer):
        code = "Процедура Длинная()\n" + "\tА = 1;\n" * 60 + "КонецПроцедуры\n"
        m = analyzer.analyze_code(code)
        assert m.technical_debt_minutes > 0

    def test_god_object_adds_debt(self, analyzer):
        code = "А = 1;\n" * 1100
        m = analyzer.analyze_code(code)
        assert m.technical_debt_minutes >= 60


# ============================================================================
# SUMMARY
# ============================================================================


class TestSummary:
    def test_summary_calculated(self, analyzer):
        code1 = "Процедура А()\nКонецПроцедуры\n"
        code2 = "Функция Б()\n\tВозврат 1;\nКонецФункции\n"
        m1 = analyzer.analyze_code(code1, "file1.bsl")
        m2 = analyzer.analyze_code(code2, "file2.bsl")
        summary = analyzer.get_summary([m1, m2])
        assert summary["total_files"] == 2
        assert summary["total_methods"] == 2
        assert summary["god_objects"] == 0


# ============================================================================
# ИНТЕГРАЦИОННЫЙ ТЕСТ
# ============================================================================


class TestIntegrationRealData:
    UT11_DIR = Path("/home/z/my-project/repo_work/data/configs/ut11")

    @pytest.mark.skipif(not UT11_DIR.exists(), reason="UT11 data not available")
    def test_analyze_ut11_common_modules(self, analyzer):
        cm_dir = self.UT11_DIR / "CommonModules"
        if not cm_dir.exists():
            pytest.skip("CommonModules not found")

        results = analyzer.analyze_path(cm_dir)
        summary = analyzer.get_summary(results)

        print(f"\n  Файлов: {summary['total_files']}")
        print(f"  Строк кода: {summary['total_code_lines']}")
        print(f"  Методов: {summary['total_methods']}")
        print(f"  God Objects: {summary['god_objects']}")
        print(f"  Длинных методов: {summary['long_methods']}")
        print(f"  Средний Health: {summary['avg_health']:.0f}/100")
        print(f"  Техдолг: {summary['total_debt_hours']:.1f} ч")

        assert isinstance(results, list)
        assert len(results) > 0
