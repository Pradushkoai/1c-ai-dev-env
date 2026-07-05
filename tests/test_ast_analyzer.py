"""D3.2 (2026-07-05): Тесты для AST-based analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.analyzers.ast_analyzer import AstAnalyzer, AstViolation


@pytest.fixture
def analyzer() -> AstAnalyzer:
    return AstAnalyzer()


class TestAstAnalyzerAvailability:
    def test_is_available(self, analyzer: AstAnalyzer) -> None:
        assert analyzer.is_available() is True  # tree-sitter установлен


class TestAstExecute:
    def test_execute_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\tВыполнить(\"Сообщить(1)\");\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        exec_violations = [v for v in violations if v.rule_id == "AST-EXEC001"]
        assert len(exec_violations) >= 1

    def test_execute_in_comment_not_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\t// Выполнить(\"код\")\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        exec_violations = [v for v in violations if v.rule_id == "AST-EXEC001"]
        assert len(exec_violations) == 0  # Не должно быть false positive


class TestAstEval:
    def test_eval_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\tРезультат = Вычислить(\"1+2\");\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        eval_violations = [v for v in violations if v.rule_id == "AST-EXEC002"]
        assert len(eval_violations) >= 1


class TestAstEmptyProcedure:
    def test_empty_procedure_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Пустая()\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        empty_violations = [v for v in violations if v.rule_id == "AST-QUALITY001"]
        assert len(empty_violations) >= 1

    def test_non_empty_procedure_not_flagged(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Непустая()\n\tСообщить(\"привет\");\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        empty_violations = [v for v in violations if v.rule_id == "AST-QUALITY001"]
        assert len(empty_violations) == 0


class TestAstTodoWithoutIssue:
    def test_todo_without_issue(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\t// TODO: исправить это\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        todo_violations = [v for v in violations if v.rule_id == "AST-STYLE002"]
        assert len(todo_violations) >= 1

    def test_todo_with_issue_not_flagged(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\t// TODO: исправить №123\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        todo_violations = [v for v in violations if v.rule_id == "AST-STYLE002"]
        assert len(todo_violations) == 0


class TestAstHardcodedPassword:
    def test_password_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\tПароль = \"secret123\";\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        pwd_violations = [v for v in violations if v.rule_id == "AST-SEC003"]
        assert len(pwd_violations) >= 1


class TestAstLongProcedure:
    def test_long_procedure_detected(self, analyzer: AstAnalyzer) -> None:
        lines = ["Процедура Длинная()"]
        for i in range(101):
            lines.append(f"\tСообщить(\"{i}\");")
        lines.append("КонецПроцедуры")
        code = "\n".join(lines) + "\n"
        violations = analyzer.analyze_code(code)
        long_violations = [v for v in violations if v.rule_id == "AST-QUALITY003"]
        assert len(long_violations) >= 1


class TestAstMultipleReturn:
    def test_multiple_return_detected(self, analyzer: AstAnalyzer) -> None:
        code = "Функция Тест()\n\tВозврат 1;\n\tВозврат 2;\nКонецФункции\n"
        violations = analyzer.analyze_code(code)
        ret_violations = [v for v in violations if v.rule_id == "AST-QUALITY002"]
        assert len(ret_violations) >= 1


class TestAstNoTryCatch:
    def test_execute_without_try(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\tВыполнить(\"код\");\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        sec_violations = [v for v in violations if v.rule_id == "AST-SEC001"]
        assert len(sec_violations) >= 1

    def test_execute_with_try_ok(self, analyzer: AstAnalyzer) -> None:
        code = "Процедура Тест()\n\tПопытка\n\t\tВыполнить(\"код\");\n\tИсключение\n\tКонецПопытки;\nКонецПроцедуры\n"
        violations = analyzer.analyze_code(code)
        sec_violations = [v for v in violations if v.rule_id == "AST-SEC001"]
        assert len(sec_violations) == 0


class TestAstFileAnalysis:
    def test_analyze_file(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("Процедура Тест()\n\tВыполнить(\"код\");\nКонецПроцедуры\n", encoding="utf-8")
        violations = analyzer.analyze(bsl_file)
        assert len(violations) > 0

    def test_analyze_missing_file(self, analyzer: AstAnalyzer) -> None:
        violations = analyzer.analyze("/nonexistent/file.bsl")
        assert violations == []
