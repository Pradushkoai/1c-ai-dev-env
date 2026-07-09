#!/usr/bin/env python3
"""Тесты для усиленных правил SecurityAuditor (SEC016-SEC020).

Усиление по стандартам v8std.ru / ITS:
- SEC016: HTTPСоединение/WSПрокси без таймаута (#std748)
- SEC017: Выполнить/Вычислить без УстановитьБезопасныйРежим (#std770)
- SEC018: КомандаСистемы с опасными символами (#std774)
- SEC019: COM Word/Excel без DisableAutoMacros (#std775)
- SEC020: Внешняя обработка без БСП (#std669)
"""

import pytest

from src.services.analyzers.security_auditor import SecurityAuditor, SecurityViolation


@pytest.fixture
def auditor():
    return SecurityAuditor()


class TestSEC016ExternalNoTimeout:
    """SEC016: HTTPСоединение/WSПрокси без таймаута (#std748)."""

    def test_http_no_timeout_detected(self, auditor):
        code = 'Соединение = Новый HTTPСоединение("api.example.com");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC016" for v in violations)

    def test_http_with_timeout_ok(self, auditor):
        # Однострочный вызов с числовым аргументом таймаута
        code = 'Соединение = Новый HTTPСоединение("api.example.com", 443, , , , 30);'
        violations = auditor.audit_code(code)
        # Должно быть 0 нарушений SEC016
        sec016 = [v for v in violations if v.rule_id == "SEC016"]
        assert not sec016, f"Expected no SEC016, got: {sec016}"

    def test_ftp_no_timeout_detected(self, auditor):
        code = 'Соединение = Новый FTPСоединение("ftp.example.com");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC016" for v in violations)

    def test_recommendation_links_std748(self, auditor):
        code = 'Соединение = Новый HTTPСоединение("api.example.com");'
        violations = auditor.audit_code(code)
        sec016 = [v for v in violations if v.rule_id == "SEC016"]
        assert sec016
        assert "std748" in sec016[0].recommendation


class TestSEC017ExecNoSafeMode:
    """SEC017: Выполнить/Вычислить без УстановитьБезопасныйРежим (#std770)."""

    def test_execute_dynamic_no_safe_mode_detected(self, auditor):
        code = (
            "Алгоритм = \"Сообщить(\"\"test\"\");\";\n"
            "Выполнить(Алгоритм);\n"
        )
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC017" for v in violations)

    def test_execute_with_safe_mode_ok(self, auditor):
        code = (
            "Алгоритм = \"Сообщить(\"\"test\"\");\";\n"
            "УстановитьБезопасныйРежим(Истина);\n"
            "Выполнить(Алгоритм);\n"
        )
        violations = auditor.audit_code(code)
        sec017 = [v for v in violations if v.rule_id == "SEC017"]
        assert not sec017, f"Expected no SEC017, got: {sec017}"

    def test_static_execute_literal_ok(self, auditor):
        """Статичный строковый литерал в Выполнить — не требует safe mode.

        В BSL кавычки внутри строк удваиваются, поэтому простая строка
        без вложенных кавычек распознаётся как статичный литерал.
        """
        code = 'Выполнить("Сообщить(1);");'
        violations = auditor.audit_code(code)
        sec017 = [v for v in violations if v.rule_id == "SEC017"]
        assert not sec017

    def test_recommendation_links_std770(self, auditor):
        code = (
            "Алгоритм = ПолучитьАлгоритм();\n"
            "Выполнить(Алгоритм);\n"
        )
        violations = auditor.audit_code(code)
        sec017 = [v for v in violations if v.rule_id == "SEC017"]
        assert sec017
        assert "std770" in sec017[0].recommendation


class TestSEC018CmdInjection:
    """SEC018: КомандаСистемы/ЗапуститьПриложение с опасными символами (#std774)."""

    def test_semicolon_in_command_detected(self, auditor):
        code = 'КомандаСистемы("dir; rm -rf /");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC018" for v in violations)

    def test_pipe_in_command_detected(self, auditor):
        code = 'ЗапуститьПриложение("cmd || echo hacked");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC018" for v in violations)

    def test_dollar_in_command_detected(self, auditor):
        code = 'ЗапуститьПриложение("echo $HOME");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC018" for v in violations)

    def test_clean_command_no_violation(self, auditor):
        """Команда без опасных символов — нет нарушения SEC018."""
        code = 'ЗапуститьПриложение("notepad.exe");'
        violations = auditor.audit_code(code)
        sec018 = [v for v in violations if v.rule_id == "SEC018"]
        assert not sec018


class TestSEC019COMNoMacroDisable:
    """SEC019: COM Word/Excel без DisableAutoMacros (#std775)."""

    def test_word_without_disable_automacros_detected(self, auditor):
        code = (
            'ОбъектWord = Новый COMОбъект("Word.Application");\n'
            'Документ = ОбъектWord.Documents.Open(ИмяФайла);\n'
        )
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC019" for v in violations)

    def test_word_with_disable_automacros_ok(self, auditor):
        code = (
            'ОбъектWord = Новый COMОбъект("Word.Application");\n'
            'ОбъектWord.WordBasic.DisableAutoMacros(1);\n'
            'Документ = ОбъектWord.Documents.Open(ИмяФайла);\n'
        )
        violations = auditor.audit_code(code)
        sec019 = [v for v in violations if v.rule_id == "SEC019"]
        assert not sec019

    def test_excel_without_automation_security_detected(self, auditor):
        code = (
            'ОбъектExcel = Новый COMОбъект("Excel.Application");\n'
            'Документ = ОбъектExcel.Workbooks.Open(Файл);\n'
        )
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC019" for v in violations)

    def test_excel_with_automation_security_ok(self, auditor):
        code = (
            'ОбъектExcel = Новый COMОбъект("Excel.Application");\n'
            'ОбъектExcel.AutomationSecurity = 3;\n'
            'Документ = ОбъектExcel.Workbooks.Open(Файл);\n'
        )
        violations = auditor.audit_code(code)
        sec019 = [v for v in violations if v.rule_id == "SEC019"]
        assert not sec019


class TestSEC020ExternalCodeLoad:
    """SEC020: Внешняя обработка без БСП (#std669)."""

    def test_direct_external_processing_load_detected(self, auditor):
        code = (
            'Обработка = ВнешниеОбработки.Создать("C:\\temp\\bad.epf");'
        )
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC020" for v in violations)

    def test_bsp_managed_load_ok(self, auditor):
        """Если используется ДополнительныеОтчетыИОбработки — это БСП, нарушение не требуется."""
        code = (
            'ДополнительныеОтчетыИОбработки.Подключить(Ссылка);\n'
            'Обработка = ВнешниеОбработки.Создать(Путь);'
        )
        violations = auditor.audit_code(code)
        sec020 = [v for v in violations if v.rule_id == "SEC020"]
        assert not sec020

    def test_recommendation_links_std669(self, auditor):
        code = 'Обработка = ВнешниеОбработки.Создать("bad.epf");'
        violations = auditor.audit_code(code)
        sec020 = [v for v in violations if v.rule_id == "SEC020"]
        assert sec020
        assert "std669" in sec020[0].recommendation


class TestRulesRegistration:
    """Проверка, что новые правила зарегистрированы."""

    def test_all_new_rules_in_registry(self, auditor):
        for rid in ("SEC016", "SEC017", "SEC018", "SEC019", "SEC020"):
            assert rid in auditor.rules, f"Rule {rid} not in registry"

    def test_sec016_severity_high(self, auditor):
        assert auditor.rules["SEC016"].severity == "HIGH"

    def test_sec017_severity_critical(self, auditor):
        assert auditor.rules["SEC017"].severity == "CRITICAL"

    def test_sec018_severity_critical(self, auditor):
        assert auditor.rules["SEC018"].severity == "CRITICAL"
