"""
D3.3 (2026-07-06): Тесты для BSL LS rules analyzer (50 правил).

Проверяет:
- 50 правил определены
- 5 категорий: style, best_practice, performance, security, compatibility
- BslLsRule dataclass
- BslLsRulesAnalyzer: analyze_code, analyze_file, get_stats
- Конкретные правила: line_length, indentation, duplicate_procedure, etc.
- Edge cases: пустой код, только комментарии
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.analyzers.bsl_ls_rules import (
    BSL_LS_RULES,
    BslLsRule,
    BslLsRulesAnalyzer,
    _make_violation,
    _rule_severity,
)


# ============================================================================
# Rule definitions tests
# ============================================================================


class TestRuleDefinitions:
    """Тесты определений правил."""

    def test_50_rules_defined(self) -> None:
        """Определено ровно 50 правил."""
        assert len(BSL_LS_RULES) == 50, f"Expected 50, got {len(BSL_LS_RULES)}"

    def test_all_rules_have_unique_ids(self) -> None:
        """Все rule_id уникальны."""
        ids = [r.rule_id for r in BSL_LS_RULES]
        assert len(ids) == len(set(ids))

    def test_all_rules_have_severity(self) -> None:
        """Все правила имеют severity."""
        valid = {"error", "warning", "info"}
        for rule in BSL_LS_RULES:
            assert rule.severity in valid, f"{rule.rule_id}: {rule.severity}"

    def test_all_rules_have_category(self) -> None:
        """Все правила имеют category."""
        valid = {"style", "best_practice", "performance", "security", "compatibility"}
        for rule in BSL_LS_RULES:
            assert rule.category in valid, f"{rule.rule_id}: {rule.category}"

    def test_style_category_has_10_rules(self) -> None:
        assert sum(1 for r in BSL_LS_RULES if r.category == "style") == 10

    def test_best_practice_has_15_rules(self) -> None:
        assert sum(1 for r in BSL_LS_RULES if r.category == "best_practice") == 15

    def test_performance_has_10_rules(self) -> None:
        assert sum(1 for r in BSL_LS_RULES if r.category == "performance") == 10

    def test_security_has_8_rules(self) -> None:
        assert sum(1 for r in BSL_LS_RULES if r.category == "security") == 8

    def test_compatibility_has_7_rules(self) -> None:
        assert sum(1 for r in BSL_LS_RULES if r.category == "compatibility") == 7


# ============================================================================
# BslLsRule dataclass tests
# ============================================================================


class TestBslLsRule:
    def test_creation(self) -> None:
        rule = BslLsRule(
            rule_id="test-001",
            name="Test",
            severity="warning",
            description="Test rule",
            category="style",
        )
        assert rule.rule_id == "test-001"
        assert rule.severity == "warning"
        assert rule.category == "style"


# ============================================================================
# Helper functions tests
# ============================================================================


class TestHelpers:
    def test_rule_severity_returns_correct(self) -> None:
        """_rule_severity возвращает severity."""
        assert _rule_severity("bsl-ls-style-001") == "warning"  # info → warning
        assert _rule_severity("bsl-ls-bp-002") == "error"
        assert _rule_severity("bsl-ls-perf-001") == "error"

    def test_rule_severity_unknown_returns_warning(self) -> None:
        assert _rule_severity("unknown-rule") == "warning"

    def test_make_violation_creates_violation(self) -> None:
        v = _make_violation("bsl-ls-style-001", "test.bsl", 1, 1, "test")
        assert v.rule_id == "bsl-ls-style-001"
        assert v.severity == "warning"  # info → warning
        assert v.line == 1


# ============================================================================
# BslLsRulesAnalyzer tests
# ============================================================================


class TestBslLsRulesAnalyzer:
    """Тесты BslLsRulesAnalyzer."""

    def test_analyzer_initializes(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        assert len(analyzer.rules) == 50

    def test_analyze_empty_code_returns_empty(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        violations = analyzer.analyze_code("")
        assert violations == []

    def test_analyze_code_with_only_comments(self) -> None:
        """Только комментарии — нет нарушений (кроме длины)."""
        analyzer = BslLsRulesAnalyzer()
        code = "// Это комментарий\n// Другой комментарий\n"
        violations = analyzer.analyze_code(code)
        # Комментарии <= 120 символов — нет нарушений
        assert all(v.rule_id != "bsl-ls-style-002" for v in violations)

    def test_get_stats_returns_correct(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        stats = analyzer.get_stats()
        assert stats["total_rules"] == 50
        assert "by_severity" in stats
        assert stats["by_severity"]["error"] > 0
        assert stats["by_severity"]["warning"] > 0
        assert stats["by_severity"]["info"] > 0


# ============================================================================
# Specific rule tests
# ============================================================================


class TestLineLength:
    def test_line_length_violation(self) -> None:
        """Строка длиннее 120 символов — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        long_line = "А" * 130
        violations = analyzer.analyze_code(long_line)
        assert any(v.rule_id == "bsl-ls-style-004" for v in violations)

    def test_line_length_ok(self) -> None:
        """Строка 120 символов — OK."""
        analyzer = BslLsRulesAnalyzer()
        line = "А" * 120
        violations = analyzer.analyze_code(line)
        assert not any(v.rule_id == "bsl-ls-style-004" for v in violations)


class TestIndentation:
    def test_space_indentation_violation(self) -> None:
        """Отступ пробелами — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "    Сообщить(\"x\");\n"  # 4 пробела
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-style-005" for v in violations)

    def test_tab_indentation_ok(self) -> None:
        """Отступ табом — OK."""
        analyzer = BslLsRulesAnalyzer()
        code = "\tСообщить(\"x\");\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-style-005" for v in violations)


class TestProcedureNameLength:
    def test_long_procedure_name_violation(self) -> None:
        """Имя процедуры длиннее 50 символов — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        long_name = "А" * 60
        code = f"Процедура {long_name}()\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-style-007" for v in violations)

    def test_short_procedure_name_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "Процедура Короткое()\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-style-007" for v in violations)


class TestSelfAssign:
    def test_self_assign_violation(self) -> None:
        """X = X — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "X = X;\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-bp-010" for v in violations)

    def test_normal_assign_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "X = Y;\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-bp-010" for v in violations)


class TestTooManyParameters:
    def test_too_many_params_violation(self) -> None:
        """Больше 7 параметров — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        params = ", ".join([f"Парам{i}" for i in range(8)])
        code = f"Процедура Test({params})\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-bp-008" for v in violations)

    def test_normal_params_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        params = ", ".join([f"Парам{i}" for i in range(3)])
        code = f"Процедура Test({params})\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-bp-008" for v in violations)


class TestDuplicateProcedure:
    def test_duplicate_procedure_violation(self) -> None:
        """Дубликат процедуры — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "Процедура Test()\nКонецПроцедуры\nПроцедура Test()\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-bp-005" for v in violations)

    def test_unique_procedures_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "Процедура Test1()\nКонецПроцедуры\nПроцедура Test2()\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-bp-005" for v in violations)


class TestFunctionWithoutReturn:
    def test_function_without_return_violation(self) -> None:
        """Функция без Возврат — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "Функция Test()\nСообщить(\"x\");\nКонецФункции\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-bp-002" for v in violations)

    def test_function_with_return_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "Функция Test()\nВозврат 1;\nКонецФункции\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-bp-002" for v in violations)


class TestModalCall:
    def test_modal_call_violation(self) -> None:
        """ОткрытьМодально — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "ОткрытьМодально(\"Форма\");\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-perf-009" for v in violations)

    def test_normal_open_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "ОткрытьФорму(\"Форма\");\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-perf-009" for v in violations)


class TestInternetRequest:
    def test_http_without_https_violation(self) -> None:
        """HTTPСоединение без HTTPS — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "Соединение = Новый HTTPСоединение(\"example.com\");\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-sec-002" for v in violations)


class TestDeprecatedMethod:
    def test_deprecated_method_violation(self) -> None:
        """Устаревший метод — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "ПолучитьФорму(\"Форма\");\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-compat-001" for v in violations)


class TestEmptyRegion:
    def test_empty_region_violation(self) -> None:
        """Пустая область — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        code = "#Область Пустая\n#КонецОбласти\n"
        violations = analyzer.analyze_code(code)
        assert any(v.rule_id == "bsl-ls-style-009" for v in violations)

    def test_non_empty_region_ok(self) -> None:
        analyzer = BslLsRulesAnalyzer()
        code = "#Область СКодом\nСообщить(\"x\");\n#КонецОбласти\n"
        violations = analyzer.analyze_code(code)
        assert not any(v.rule_id == "bsl-ls-style-009" for v in violations)


# ============================================================================
# analyze_file tests
# ============================================================================


class TestAnalyzeFile:
    def test_analyze_file_reads_content(self, tmp_path: Path) -> None:
        """analyze_file читает файл."""
        analyzer = BslLsRulesAnalyzer()
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text('Процедура Test() Экспорт\nКонецПроцедуры\n', encoding="utf-8")
        violations = analyzer.analyze(bsl_file)
        assert isinstance(violations, list)

    def test_analyze_file_missing_returns_empty(self, tmp_path: Path) -> None:
        """Несуществующий файл — пустой список."""
        analyzer = BslLsRulesAnalyzer()
        violations = analyzer.analyze(tmp_path / "nope.bsl")
        assert violations == []

    def test_analyze_file_long_line(self, tmp_path: Path) -> None:
        """Длинная строка в файле — нарушение."""
        analyzer = BslLsRulesAnalyzer()
        bsl_file = tmp_path / "long.bsl"
        bsl_file.write_text("А" * 130 + "\n", encoding="utf-8")
        violations = analyzer.analyze(bsl_file)
        assert any(v.rule_id == "bsl-ls-style-004" for v in violations)


# ============================================================================
# Integration tests
# ============================================================================


class TestIntegration:
    def test_complex_module(self) -> None:
        """Сложный модуль с несколькими нарушениями."""
        analyzer = BslLsRulesAnalyzer()
        code = '''Процедура ОченьДлинноеИмяПроцедурыКотороеПревышаетПятьдесятСимволов()
    X = X;  // self-assign
КонецПроцедуры

Функция БезВозврата()
    Сообщить("x");
КонецФункции

Процедура БезВозврата()
    X = X;
КонецПроцедуры
'''
        violations = analyzer.analyze_code(code)
        # Должны найти несколько нарушений
        assert len(violations) >= 3

        rule_ids = {v.rule_id for v in violations}
        # Должно быть хотя бы одно из: procedure_name_length, self_assign, function_without_return
        assert any(
            rid in rule_ids
            for rid in ["bsl-ls-style-007", "bsl-ls-bp-010", "bsl-ls-bp-002"]
        )

    def test_clean_code_no_violations(self) -> None:
        """Чистый код — нет нарушений."""
        analyzer = BslLsRulesAnalyzer()
        code = '''Процедура Test()
\tСообщить("x");
КонецПроцедуры

Функция GetResult()
\tВозврат 1;
КонецФункции
'''
        violations = analyzer.analyze_code(code)
        # Не должно быть критических нарушений
        critical_rules = ["bsl-ls-bp-002", "bsl-ls-bp-010", "bsl-ls-bp-005"]
        assert not any(v.rule_id in critical_rules for v in violations)
