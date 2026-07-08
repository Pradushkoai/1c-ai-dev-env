#!/usr/bin/env python3
"""Тесты для DataExchangeChecker — проверка обмена данными по v8std.ru / ITS.

Покрытие:
- DX001: ПередЗаписью без проверки ОбменДанными.Загрузка (#std773)
- DX002: ПриЗаписи без проверки ОбменДанными.Загрузка (#std773)
- DX003: ПередУдалением без проверки ОбменДанными.Загрузка (#std773)
- DX004: Обращение через точку в логике регистрации (#std701)
- DX005: Регистрация вне ПередЗаписью/ПередУдалением (#std701)
- DX006: Подписка на событие без проверки ОбменДанными.Загрузка (#std773)
- DX007: Захардкоженный путь файла обмена (#std542)
- DX008: AdditionalInfo в EnterpriseData (#std771)
- DX009: ЗначениеИзСтрокиВнутр для обмена
- DX010: Бизнес-логика без Возврат при ОбменДанными.Загрузка (#std773)
"""

import pytest

from src.services.analyzers.data_exchange_checker import (
    DataExchangeChecker,
    DataExchangeIssue,
)


@pytest.fixture
def checker():
    return DataExchangeChecker()


class TestDX001PeredZapisiyu:
    """DX001: ПередЗаписью без проверки ОбменДанными.Загрузка."""

    def test_no_exchange_check_detected(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если Не ЗначениеЗаполнено(Реквизит1) Тогда
        Отказ = Истина;
    КонецЕсли;
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX001" for v in violations)

    def test_with_exchange_check_ok(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    Если Не ЗначениеЗаполнено(Реквизит1) Тогда
        Отказ = Истина;
    КонецЕсли;
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert not any(v.rule_id == "DX001" for v in violations)

    def test_recommendation_links_std773(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Отказ = Истина;
КонецПроцедуры"""
        violations = checker.check_code(code)
        dx001 = [v for v in violations if v.rule_id == "DX001"]
        assert dx001
        assert "std773" in dx001[0].recommendation


class TestDX002PriZapisi:
    """DX002: ПриЗаписи без проверки ОбменДанными.Загрузка."""

    def test_no_exchange_check_detected(self, checker):
        code = """Процедура ПриЗаписи(Отказ)
    Движения.Остатки.Записать();
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX002" for v in violations)


class TestDX003PeredUdaleniem:
    """DX003: ПередУдалением без проверки ОбменДанными.Загрузка."""

    def test_no_exchange_check_detected(self, checker):
        code = """Процедура ПередУдалением(Отказ)
    // регистрация удаления
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX003" for v in violations)


class TestDX004DotAccessInRegistration:
    """DX004: Обращение через точку в логике регистрации (#std701)."""

    def test_dot_access_in_registration_detected(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, ЭтотОбъект.Контрагент.Организация);
КонецПроцедуры"""
        violations = checker.check_code(code)
        # DX001 не должно быть (есть проверка), но DX004 — да
        assert any(v.rule_id == "DX004" for v in violations)

    def test_no_dot_access_ok(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert not any(v.rule_id == "DX004" for v in violations)

    def test_recommendation_links_std701(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, ЭтотОбъект.Контрагент.Договор.Организация);
КонецПроцедуры"""
        violations = checker.check_code(code)
        dx004 = [v for v in violations if v.rule_id == "DX004"]
        assert dx004
        assert "std701" in dx004[0].recommendation


class TestDX005RegistrationOutsideHandler:
    """DX005: Регистрация вне ПередЗаписью/ПередУдалением."""

    def test_registration_in_other_procedure_detected(self, checker):
        code = """Процедура МояОбработка()
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX005" for v in violations)

    def test_registration_in_pered_zapisiyu_ok(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert not any(v.rule_id == "DX005" for v in violations)

    def test_registration_in_exchange_module_ok(self, checker):
        """Процедуры со словом 'Обмен' в имени — исключение."""
        code = """Процедура ОбработатьОбменДанными()
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        assert not any(v.rule_id == "DX005" for v in violations)


class TestDX007HardcodedPath:
    """DX007: Захардкоженный путь файла обмена (#std542)."""

    def test_hardcoded_windows_path_detected(self, checker):
        code = 'ЗаписьXML.ОткрытьФайл("C:\\\\temp\\\\exchange.xml");'
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX007" for v in violations)

    def test_temp_file_ok(self, checker):
        code = 'ИмяФайла = ПолучитьИмяВременногоФайла("xml");\nЗаписьXML.ОткрытьФайл(ИмяФайла);'
        violations = checker.check_code(code)
        # DX007 только на hardcoded path, здесь — переменная
        assert not any(v.rule_id == "DX007" for v in violations)


class TestDX008AdditionalInfo:
    """DX008: AdditionalInfo в EnterpriseData (#std771)."""

    def test_additional_info_in_exchange_detected(self, checker):
        code = (
            'ОбменДанными.ДополнительныеСвойства.Вставить("AdditionalInfo", Значение);'
        )
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX008" for v in violations)


class TestDX009InternalSerialization:
    """DX009: ЗначениеИзСтрокиВнутр для обмена."""

    def test_internal_serialization_in_exchange_detected(self, checker):
        code = (
            'Узел = ПланыОбмена.Узлы.НайтиПоКоду("ЦБ");\n'
            'Данные = ЗначениеИзСтрокиВнутр(Строка);'
        )
        violations = checker.check_code(code)
        assert any(v.rule_id == "DX009" for v in violations)

    def test_internal_serialization_no_exchange_context_ok(self, checker):
        """Без контекста обмена — не нарушение."""
        code = 'Данные = ЗначениеИзСтрокиВнутр(Строка);'
        violations = checker.check_code(code)
        assert not any(v.rule_id == "DX009" for v in violations)


class TestRulesRegistration:
    """Проверка регистрации правил."""

    def test_all_rules_registered(self, checker):
        for rid in ("DX001", "DX002", "DX003", "DX004", "DX005",
                    "DX006", "DX007", "DX008", "DX009", "DX010"):
            assert rid in checker.rules, f"Rule {rid} not registered"

    def test_dx001_severity_high(self, checker):
        assert checker.rules["DX001"].severity == "HIGH"

    def test_dx004_severity_high(self, checker):
        assert checker.rules["DX004"].severity == "HIGH"


class TestComplexScenarios:
    """Сложные сценарии."""

    def test_full_module_with_multiple_issues(self, checker):
        """Модуль с несколькими нарушениями."""
        code = """Процедура ПередЗаписью(Отказ)
    // Нет проверки ОбменДанными.Загрузка
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, ЭтотОбъект.Контрагент.Организация);
КонецПроцедуры

Процедура МояОбработка()
    // Регистрация вне обработчика
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        # Должно быть:
        # - DX001 (ПередЗаписью без проверки)
        # - DX004 (разыменование в регистрации)
        # - DX005 (регистрация вне обработчика)
        rule_ids = {v.rule_id for v in violations}
        assert "DX001" in rule_ids
        assert "DX004" in rule_ids
        assert "DX005" in rule_ids

    def test_clean_module_no_violations(self, checker):
        """Чистый модуль — без нарушений."""
        code = """Процедура ПередЗаписью(Отказ)
    Если ОбменДанными.Загрузка Тогда
        Возврат;
    КонецЕсли;
    ПланыОбмена.ЗарегистрироватьИзменения(Узел, Ссылка);
КонецПроцедуры"""
        violations = checker.check_code(code)
        # Не должно быть DX001, DX004, DX005
        for rid in ("DX001", "DX004", "DX005"):
            assert not any(v.rule_id == rid for v in violations), \
                f"Unexpected violation {rid}"


class TestStatsAndPath:
    """Тест get_stats и check_path."""

    def test_get_stats(self, checker):
        code = """Процедура ПередЗаписью(Отказ)
    Отказ = Истина;
КонецПроцедуры"""
        violations = checker.check_code(code)
        stats = checker.get_stats(violations)
        assert "total_violations" in stats
        assert "by_severity" in stats
        assert "by_rule" in stats
        assert stats["total_violations"] >= 1

    def test_check_path_returns_list(self, checker, tmp_path):
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("Процедура ПередЗаписью(Отказ)\nОтказ = Истина;\nКонецПроцедуры")
        violations = checker.check_file(bsl_file)
        assert isinstance(violations, list)
