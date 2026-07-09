"""
D3.5 (2026-07-06): Тесты для расширенных AST analyzers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.analyzers.ast_analyzers_extended import (
    AstAnalysisResult,
    AstPatternViolation,
    ComplexityAnalyzer,
    ComplexityMetrics,
    PatternAnalyzer,
    analyze_ast_full,
    get_complexity_summary,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_bsl() -> str:
    """Sample BSL код с разными метриками."""
    return '''Процедура SimpleProc()
    Сообщить("Hello");
КонецПроцедуры

Функция ComplexFunc(Парам1, Парам2, Парам3, Парам4, Парам5, Парам6)
    Если Парам1 Тогда
        Для Индекс = 1 По 10 Цикл
            Если Парам2 Тогда
                Сообщить("deep");
            КонецЕсли;
        КонецЦикла;
    КонецЕсли;
    Возврат Парам1;
КонецФункции

Процедура LongProc()
    Сообщить("1"); Сообщить("2"); Сообщить("3");
    Сообщить("4"); Сообщить("5"); Сообщить("6");
    Сообщить("7"); Сообщить("8"); Сообщить("9");
    Сообщить("10"); Сообщить("11"); Сообщить("12");
    Сообщить("13"); Сообщить("14"); Сообщить("15");
    Сообщить("16"); Сообщить("17"); Сообщить("18");
    Сообщить("19"); Сообщить("20"); Сообщить("21");
    Сообщить("22"); Сообщить("23"); Сообщить("24");
    Сообщить("25"); Сообщить("26"); Сообщить("27");
    Сообщить("28"); Сообщить("29"); Сообщить("30");
    Сообщить("31"); Сообщить("32"); Сообщить("33");
    Сообщить("34"); Сообщить("35"); Сообщить("36");
    Сообщить("37"); Сообщить("38"); Сообщить("39");
    Сообщить("40"); Сообщить("41"); Сообщить("42");
    Сообщить("43"); Сообщить("44"); Сообщить("45");
    Сообщить("46"); Сообщить("47"); Сообщить("48");
    Сообщить("49"); Сообщить("50"); Сообщить("51");
КонецПроцедуры
'''


@pytest.fixture
def sample_bsl_file(tmp_path: Path, sample_bsl: str) -> Path:
    """Sample BSL файл."""
    bsl_file = tmp_path / "test.bsl"
    bsl_file.write_text(sample_bsl, encoding="utf-8")
    return bsl_file


# ============================================================================
# ComplexityMetrics dataclass tests
# ============================================================================


class TestComplexityMetrics:
    def test_defaults(self) -> None:
        m = ComplexityMetrics(name="test")
        assert m.name == "test"
        assert m.cyclomatic_complexity == 1
        assert m.nesting_depth == 0
        assert m.lines_of_code == 0

    def test_with_values(self) -> None:
        m = ComplexityMetrics(
            name="test", cyclomatic_complexity=5,
            nesting_depth=3, lines_of_code=20, parameter_count=4,
        )
        assert m.cyclomatic_complexity == 5
        assert m.nesting_depth == 3


# ============================================================================
# ComplexityAnalyzer tests
# ============================================================================


class TestComplexityAnalyzer:
    def test_analyze_returns_list(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        assert isinstance(result, list)

    def test_analyze_finds_functions(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        # Должны найти SimpleProc, ComplexFunc, LongProc
        names = [m.name for m in result]
        assert "SimpleProc" in names
        assert "ComplexFunc" in names
        assert "LongProc" in names

    def test_simple_proc_low_complexity(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        simple = next(m for m in result if m.name == "SimpleProc")
        # SimpleProc без decision points
        assert simple.cyclomatic_complexity == 1

    def test_complex_func_higher_complexity(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        complex_func = next(m for m in result if m.name == "ComplexFunc")
        # ComplexFunc имеет Если + Для + Если = 3 decision points
        assert complex_func.cyclomatic_complexity > 1

    def test_complex_func_has_nesting(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        complex_func = next(m for m in result if m.name == "ComplexFunc")
        assert complex_func.nesting_depth >= 2

    def test_param_count(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        complex_func = next(m for m in result if m.name == "ComplexFunc")
        assert complex_func.parameter_count == 6

    def test_simple_proc_zero_params(self, sample_bsl_file: Path) -> None:
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze(sample_bsl_file)
        simple = next(m for m in result if m.name == "SimpleProc")
        assert simple.parameter_count == 0


# ============================================================================
# PatternAnalyzer tests
# ============================================================================


class TestPatternAnalyzer:
    def test_analyze_returns_list(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(name="test", cyclomatic_complexity=1)]
        result = analyzer.analyze(metrics)
        assert isinstance(result, list)

    def test_detects_deep_nesting(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(name="deep", nesting_depth=6)]
        violations = analyzer.analyze(metrics)
        assert any(v.pattern == "deep-nesting" for v in violations)

    def test_detects_long_function(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(name="long", lines_of_code=60)]
        violations = analyzer.analyze(metrics)
        assert any(v.pattern == "long-function" for v in violations)

    def test_detects_too_many_params(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(name="params", parameter_count=8)]
        violations = analyzer.analyze(metrics)
        assert any(v.pattern == "too-many-params" for v in violations)

    def test_detects_high_complexity(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(name="complex", cyclomatic_complexity=15)]
        violations = analyzer.analyze(metrics)
        assert any(v.pattern == "high-complexity" for v in violations)

    def test_no_violations_for_clean_code(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(
            name="clean",
            cyclomatic_complexity=3,
            nesting_depth=2,
            lines_of_code=20,
            parameter_count=3,
        )]
        violations = analyzer.analyze(metrics)
        assert violations == []

    def test_multiple_violations(self) -> None:
        analyzer = PatternAnalyzer()
        metrics = [ComplexityMetrics(
            name="bad",
            cyclomatic_complexity=15,
            nesting_depth=6,
            lines_of_code=60,
            parameter_count=8,
        )]
        violations = analyzer.analyze(metrics)
        assert len(violations) == 4  # all 4 patterns


# ============================================================================
# analyze_ast_full tests
# ============================================================================


class TestAnalyzeAstFull:
    def test_returns_result(self, sample_bsl_file: Path) -> None:
        result = analyze_ast_full(sample_bsl_file)
        assert isinstance(result, AstAnalysisResult)

    def test_includes_complexity(self, sample_bsl_file: Path) -> None:
        result = analyze_ast_full(sample_bsl_file)
        assert len(result.complexity) > 0

    def test_includes_patterns(self, sample_bsl_file: Path) -> None:
        result = analyze_ast_full(sample_bsl_file)
        # LongProc должен trigger long-function pattern
        assert len(result.patterns) > 0

    def test_total_lines(self, sample_bsl_file: Path) -> None:
        result = analyze_ast_full(sample_bsl_file)
        assert result.total_lines > 0

    def test_file_path(self, sample_bsl_file: Path) -> None:
        result = analyze_ast_full(sample_bsl_file)
        assert str(sample_bsl_file) in result.file_path or result.file_path == str(sample_bsl_file)

    def test_missing_file(self, tmp_path: Path) -> None:
        result = analyze_ast_full(tmp_path / "nope.bsl")
        assert result.error  # должна быть ошибка


# ============================================================================
# get_complexity_summary tests
# ============================================================================


class TestComplexitySummary:
    def test_empty_metrics(self) -> None:
        summary = get_complexity_summary([])
        assert summary["total_functions"] == 0

    def test_single_function(self) -> None:
        metrics = [ComplexityMetrics(
            name="test",
            cyclomatic_complexity=5,
            nesting_depth=2,
            lines_of_code=20,
            parameter_count=3,
        )]
        summary = get_complexity_summary(metrics)
        assert summary["total_functions"] == 1
        assert summary["max_complexity"] == 5
        assert summary["max_nesting"] == 2
        assert summary["max_lines"] == 20
        assert summary["max_params"] == 3

    def test_multiple_functions(self) -> None:
        metrics = [
            ComplexityMetrics(name="f1", cyclomatic_complexity=3, nesting_depth=1, lines_of_code=10, parameter_count=2),
            ComplexityMetrics(name="f2", cyclomatic_complexity=8, nesting_depth=4, lines_of_code=30, parameter_count=5),
        ]
        summary = get_complexity_summary(metrics)
        assert summary["total_functions"] == 2
        assert summary["max_complexity"] == 8
        assert summary["max_nesting"] == 4
        assert summary["max_lines"] == 30
        assert summary["avg_complexity"] == 5.5  # (3+8)/2


# ============================================================================
# AstPatternViolation dataclass tests
# ============================================================================


class TestAstPatternViolation:
    def test_creation(self) -> None:
        v = AstPatternViolation(
            rule_id="test-001",
            pattern="test-pattern",
            line=10,
            message="test message",
        )
        assert v.rule_id == "test-001"
        assert v.severity == "warning"  # default
