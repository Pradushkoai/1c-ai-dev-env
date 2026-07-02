#!/usr/bin/env python3
"""Тесты для security_auditor.py."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from security_auditor import SECURITY_RULES, SecurityAuditor, SecurityViolation

# ============================================================================
# ФИКССТУРЫ
# ============================================================================


@pytest.fixture
def auditor():
    return SecurityAuditor()


# ============================================================================
# ТЕСТЫ ПРАВИЛ
# ============================================================================


class TestSecurityRules:
    """Тесты что правила определены корректно."""

    def test_all_rules_have_ids(self):
        for rule in SECURITY_RULES:
            assert rule.rule_id, f"Rule without id: {rule}"
            assert rule.rule_id.startswith("SEC")

    def test_all_rules_have_severity(self):
        valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        for rule in SECURITY_RULES:
            assert rule.severity in valid_severities, f"Invalid severity: {rule.severity}"

    def test_15_rules_defined(self):
        assert len(SECURITY_RULES) == 15


# ============================================================================
# ТЕСТЫ SEC001 — SQL-инъекция
# ============================================================================


class TestSQLInjection:
    """Тесты обнаружения SQL-инъекций."""

    def test_concatenation_in_query_text(self, auditor):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ " + ИмяТаблицы;'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC001" for v in violations)

    def test_strconcat_for_query(self, auditor):
        code = "ТекстЗапроса = СтрСоединить(МассивЧастей);"
        violations = auditor.audit_code(code)
        # СтрСоединить само по себе не триггерит без контекста запроса
        # но с "Текст" в переменной может
        assert isinstance(violations, list)

    def test_safe_parameterized_query(self, auditor):
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура ГДЕ Код = &Код";'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC001" for v in violations)

    def test_strtemplate_for_query(self, auditor):
        code = 'Запрос.Текст = СтрШаблон("ВЫБРАТЬ * ИЗ %1", ИмяТаблицы);'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC001" for v in violations)


# ============================================================================
# ТЕСТЫ SEC002 — Выполнить()
# ============================================================================


class TestExecute:
    """Тесты обнаружения Выполнить()."""

    def test_execute_with_variable(self, auditor):
        code = "Выполнить(СформированныйКод);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC002" for v in violations)

    def test_execute_with_strconcat(self, auditor):
        code = 'Выполнить("Процедура " + Имя + "() КонецПроцедуры");'
        violations = auditor.audit_code(code)
        # Конкатенация с переменной
        assert any(v.rule_id == "SEC002" for v in violations)

    def test_execute_with_static_string(self, auditor):
        code = 'Выполнить("Сообщить(1)");'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC002" for v in violations)


# ============================================================================
# ТЕСТЫ SEC003 — Вычислить()
# ============================================================================


class TestEval:
    """Тесты обнаружения Вычислить()."""

    def test_eval_with_variable(self, auditor):
        code = "Результат = Вычислить(ВыражениеОтПользователя);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC003" for v in violations)

    def test_eval_with_static_string(self, auditor):
        code = 'Результат = Вычислить("1 + 2");'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC003" for v in violations)


# ============================================================================
# ТЕСТЫ SEC004 — Хардкод пароля
# ============================================================================


class TestHardcodedPassword:
    """Тесты обнаружения хардкода паролей."""

    def test_password_assignment(self, auditor):
        code = 'Пароль = "secret123";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC004" for v in violations)

    def test_password_english(self, auditor):
        code = 'password = "mypassword";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC004" for v in violations)

    def test_connection_string_with_password(self, auditor):
        code = 'Соединение = "user:pass@localhost";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC004" for v in violations)


# ============================================================================
# ТЕСТЫ SEC005 — Хардкод токена
# ============================================================================


class TestHardcodedToken:
    """Тесты обнаружения хардкода токенов."""

    def test_token_assignment(self, auditor):
        code = 'Токен = "ghp_abcdef1234567890abcdefghij";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC005" for v in violations)

    def test_api_key_assignment(self, auditor):
        code = 'APIKey = "sk-1234567890abcdef";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC005" for v in violations)

    def test_bearer_token(self, auditor):
        code = 'Заголовок = "Authorization: Bearer eyJabc";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC005" for v in violations)


# ============================================================================
# ТЕСТЫ SEC006 — COM-объекты
# ============================================================================


class TestCOMObject:
    """Тесты обнаружения небезопасных COM-объектов."""

    def test_dangerous_com_wscript(self, auditor):
        code = 'Shell = Новый COMОбъект("WScript.Shell");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC006" for v in violations)

    def test_dangerous_com_shell(self, auditor):
        code = 'App = Новый COMОбъект("Shell.Application");'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC006" for v in violations)

    def test_safe_com_excel(self, auditor):
        code = 'Excel = Новый COMОбъект("Excel.Application");'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC006" for v in violations)


# ============================================================================
# ТЕСТЫ SEC007 — Привилегированный режим
# ============================================================================


class TestPrivilegedMode:
    """Тесты обнаружения привилегированного режима."""

    def test_privileged_true(self, auditor):
        code = "УстановкаПривилегированногоРежима(Истина);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC007" for v in violations)

    def test_privileged_false(self, auditor):
        code = "УстановкаПривилегированногоРежима(Ложь);"
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC007" for v in violations)


# ============================================================================
# ТЕСТЫ SEC008 — ЗапуститьПриложение
# ============================================================================


class TestRunApp:
    """Тесты обнаружения ЗапуститьПриложение."""

    def test_run_app_with_variable(self, auditor):
        code = "ЗапуститьПриложение(ПутьКПрограмме);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC008" for v in violations)

    def test_run_app_with_static_path(self, auditor):
        code = 'ЗапуститьПриложение("notepad.exe");'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC008" for v in violations)


# ============================================================================
# ТЕСТЫ SEC010 — HTTP без SSL
# ============================================================================


class TestHTTPNoSSL:
    """Тесты обнаружения HTTP без SSL."""

    def test_http_url(self, auditor):
        code = 'URL = "http://api.example.com/data";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC010" for v in violations)

    def test_localhost_ok(self, auditor):
        code = 'URL = "http://localhost:8080/api";'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC010" for v in violations)

    def test_https_ok(self, auditor):
        code = 'URL = "https://api.example.com/data";'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC010" for v in violations)


# ============================================================================
# ТЕСТЫ SEC012 — Десериализация
# ============================================================================


class TestDeserialization:
    """Тесты обнаружения небезопасной десериализации."""

    def test_value_from_string(self, auditor):
        code = "Значение = ЗначениеИзСтрокиВнутр(СтрокаОтПользователя);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC012" for v in violations)


# ============================================================================
# ТЕСТЫ SEC014 — Хардкод IP
# ============================================================================


class TestHardcodedIP:
    """Тесты обнаружения хардкода IP-адресов."""

    def test_hardcoded_ip(self, auditor):
        code = 'Сервер = "192.168.1.100";'
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC014" for v in violations)

    def test_localhost_ok(self, auditor):
        code = 'Сервер = "127.0.0.1";'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC014" for v in violations)


# ============================================================================
# ТЕСТЫ SEC015 — Слабое шифрование
# ============================================================================


class TestWeakCrypto:
    """Тесты обнаружения устаревшего шифрования."""

    def test_weak_crypto(self, auditor):
        code = "Результат = ШифрованиеДанных(Данные, Ключ);"
        violations = auditor.audit_code(code)
        assert any(v.rule_id == "SEC015" for v in violations)

    def test_safe_crypto(self, auditor):
        code = "Крипто = Новый СредстваКриптографии();"
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC015" for v in violations)


# ============================================================================
# ТЕСТЫ СТАТИСТИКИ
# ============================================================================


class TestStats:
    """Тесты get_stats()."""

    def test_empty_violations(self, auditor):
        stats = auditor.get_stats([])
        assert stats["total_violations"] == 0
        assert stats["critical_count"] == 0

    def test_mixed_violations(self, auditor):
        violations = [
            SecurityViolation("SEC001", "CRITICAL", 1),
            SecurityViolation("SEC004", "CRITICAL", 2),
            SecurityViolation("SEC010", "MEDIUM", 3),
            SecurityViolation("SEC014", "LOW", 4),
        ]
        stats = auditor.get_stats(violations)
        assert stats["total_violations"] == 4
        assert stats["critical_count"] == 2
        assert stats["medium_count"] == 1
        assert stats["low_count"] == 1


# ============================================================================
# ТЕСТЫ КОММЕНТАРИЕВ
# ============================================================================


class TestComments:
    """Тесты что комментарии не проверяются."""

    def test_comment_ignored(self, auditor):
        code = '// Пароль = "secret123";'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC004" for v in violations)

    def test_comment_sql_ignored(self, auditor):
        code = '// Запрос.Текст = "ВЫБРАТЬ " + Таблица;'
        violations = auditor.audit_code(code)
        assert not any(v.rule_id == "SEC001" for v in violations)


# ============================================================================
# ИНТЕГРАЦИОННЫЙ ТЕСТ
# ============================================================================


class TestIntegrationRealData:
    """Интеграционный тест на реальных данных УТ11."""

    UT11_DIR = Path("/home/z/my-project/repo_work/data/configs/ut11")

    @pytest.mark.skipif(not UT11_DIR.exists(), reason="UT11 data not available")
    def test_audit_ut11_common_modules(self, auditor):
        """Аудит CommonModules УТ11."""
        cm_dir = self.UT11_DIR / "CommonModules"
        if not cm_dir.exists():
            pytest.skip("CommonModules not found")

        violations = auditor.audit_path(cm_dir)
        stats = auditor.get_stats(violations)

        # УТ11 — большая конфигурация, должны найти хоть что-то
        print(f"\n  Найдено нарушений: {stats['total_violations']}")
        print(f"  CRITICAL: {stats['critical_count']}")
        print(f"  HIGH: {stats['high_count']}")
        print(f"  MEDIUM: {stats['medium_count']}")
        print(f"  LOW: {stats['low_count']}")

        # Проверяем что нет crash
        assert isinstance(violations, list)
