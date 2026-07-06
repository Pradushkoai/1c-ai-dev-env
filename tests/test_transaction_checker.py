#!/usr/bin/env python3
"""Тесты для src.services.analyzers.transaction_checker."""

from pathlib import Path

import pytest

from src.services.analyzers.transaction_checker import TransactionChecker, TransactionViolation


@pytest.fixture
def checker():
    return TransactionChecker()


class TestUnbalancedTransactions:
    def test_begin_without_commit(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\n"
        v = checker.check_code(code)
        assert any(x.rule_id == "TX001" for x in v)

    def test_balanced_transaction(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX001" for x in v)

    def test_rollback_counts_as_close(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\nОтменитьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX001" for x in v)


class TestNoTryCatch:
    def test_transaction_without_try(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert any(x.rule_id == "TX002" for x in v)

    def test_transaction_with_try(self, checker):
        code = "Попытка\nНачатьТранзакцию();\nА = 1;\nЗафиксироватьТранзакцию();\nИсключение\nОтменитьТранзакцию();\nКонецПопытки;\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX002" for x in v)


class TestInteractiveInTransaction:
    def test_soobshit_in_transaction(self, checker):
        code = 'НачатьТранзакцию();\nСообщить("Тест");\nЗафиксироватьТранзакцию();\n'
        v = checker.check_code(code)
        assert any(x.rule_id == "TX003" for x in v)

    def test_no_interactive_outside_transaction(self, checker):
        code = 'Сообщить("Тест");\n'
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX003" for x in v)

    def test_open_form_in_transaction(self, checker):
        code = 'НачатьТранзакцию();\nОткрытьФорму("Справочник.Тест");\nЗафиксироватьТранзакцию();\n'
        v = checker.check_code(code)
        assert any(x.rule_id == "TX003" for x in v)


class TestLongTransactions:
    def test_long_transaction_detected(self, checker):
        code = "НачатьТранзакцию();\n" + "А = 1;\n" * 110 + "ЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert any(x.rule_id == "TX004" for x in v)

    def test_short_transaction_ok(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\nБ = 2;\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX004" for x in v)


class TestNestedTransactions:
    def test_nested_transaction_detected(self, checker):
        code = "НачатьТранзакцию();\nНачатьТранзакцию();\nЗафиксироватьТранзакцию();\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert any(x.rule_id == "TX005" for x in v)

    def test_no_nested_ok(self, checker):
        code = "НачатьТранзакцию();\nА = 1;\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX005" for x in v)


class TestDBWriteWithoutTransaction:
    def test_multiple_writes_without_transaction(self, checker):
        code = "Объект1.Записать();\nОбъект2.Записать();\nОбъект3.Записать();\n"
        v = checker.check_code(code)
        assert any(x.rule_id == "TX006" for x in v)

    def test_single_write_ok(self, checker):
        code = "Объект.Записать();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX006" for x in v)

    def test_writes_in_transaction_ok(self, checker):
        code = "НачатьТранзакцию();\nОбъект1.Записать();\nОбъект2.Записать();\nОбъект3.Записать();\nЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX006" for x in v)


class TestComments:
    def test_comments_ignored(self, checker):
        code = "// НачатьТранзакцию();\n// ЗафиксироватьТранзакцию();\n"
        v = checker.check_code(code)
        assert not any(x.rule_id == "TX001" for x in v)


class TestStats:
    def test_empty_violations(self, checker):
        stats = checker.get_stats([])
        assert stats["total"] == 0

    def test_mixed_violations(self, checker):
        violations = [
            TransactionViolation("TX001", "CRITICAL", 1, "Test message"),
            TransactionViolation("TX003", "MEDIUM", 2, "Test message 2"),
        ]
        stats = checker.get_stats(violations)
        assert stats["total"] == 2
        assert "CRITICAL" in stats["by_severity"]


class TestIntegrationRealData:
    UT11_DIR = Path("/home/z/my-project/repo_work/data/configs/ut11")

    @pytest.mark.skipif(not UT11_DIR.exists(), reason="UT11 data not available")
    def test_check_ut11(self, checker):
        cm_dir = self.UT11_DIR / "CommonModules"
        if not cm_dir.exists():
            pytest.skip("CommonModules not found")
        violations = checker.check_path(cm_dir)
        stats = checker.get_stats(violations)
        print(f"\n  Найдено нарушений: {stats['total']}")
        assert isinstance(violations, list)
