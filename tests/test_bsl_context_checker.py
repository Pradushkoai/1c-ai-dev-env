#!/usr/bin/env python3
"""Тесты для BslContextChecker — проверка доступности методов.

Поток 5: Тесты на основе реальных ошибок пользователя.

Покрытие:
  - CTX001: Метод недоступен в контексте (ERROR)
  - CTX002: Метод устарел (WARNING)
  - detect_context(): автоопределение контекста
  - _find_global_context_props(): Метаданные, ПараметрыСеанса
  - Type inference: Соединение.Получить → HTTPСоединение.Получить
"""

import pytest

from src.services.analyzers.bsl_context_checker import BslContextChecker


@pytest.fixture
def checker():
    """Создаёт checker. Если индекс недоступен — тесты пропускаются."""
    c = BslContextChecker()
    if c._get_index() is None:
        pytest.skip("Platform methods index not built. Run: python3 scripts/build_platform_methods_index.py")
    return c


class TestCTX001ServerMethodsOnClient:
    """CTX001: Серверные методы на клиенте → ERROR."""

    def test_zapis_zhurnala_on_client(self, checker):
        """ЗаписьЖурналаРегистрации недоступна на тонком клиенте."""
        code = """
&НаКлиенте
Процедура Тест()
    ЗаписьЖурналаРегистрации("ТСД.Ошибка", УровеньЖурналаРегистрации.Ошибка);
КонецПроцедуры
"""
        violations = checker.check_code(code)
        ctx001 = [v for v in violations if v.rule_id == "CTX001"]
        assert len(ctx001) > 0
        assert any("ЗаписьЖурналаРегистрации" in v.message for v in ctx001)
        assert all(v.severity == "error" for v in ctx001)

    def test_zapis_zhurnala_on_server_ok(self, checker):
        """ЗаписьЖурналаРегистрации на сервере → нет нарушений."""
        code = """
&НаСервере
Процедура Тест()
    ЗаписьЖурналаРегистрации("ТСД.Ошибка", УровеньЖурналаРегистрации.Ошибка);
КонецПроцедуры
"""
        violations = checker.check_code(code)
        ctx001 = [v for v in violations if v.rule_id == "CTX001" and "ЗаписьЖурналаРегистрации" in v.method_name]
        assert len(ctx001) == 0

    def test_metadata_on_client(self, checker):
        """Метаданные недоступны на тонком клиенте."""
        code = """
&НаКлиенте
Процедура Тест()
    Если Метаданные.Справочники.Найти("ПрофилиТСД") <> Неопределено Тогда
        Возврат;
    КонецЕсли;
КонецПроцедуры
"""
        violations = checker.check_code(code)
        ctx001 = [v for v in violations if v.rule_id == "CTX001"]
        assert len(ctx001) > 0
        # Должно найти либо Метаданные, либо Справочники
        assert any("Метаданные" in v.message or "Справочники" in v.message for v in ctx001)


class TestDetectContext:
    """Автоопределение целевого контекста по коду."""

    def test_detect_client(self, checker):
        """&НаКлиенте → thin_client."""
        code = "&НаКлиенте\nПроцедура Тест()\nКонецПроцедуры"
        ctx = checker.detect_context(code)
        assert "thin_client" in ctx

    def test_detect_server(self, checker):
        """&НаСервере → server."""
        code = "&НаСервере\nПроцедура Тест()\nКонецПроцедуры"
        ctx = checker.detect_context(code)
        assert "server" in ctx

    def test_detect_async(self, checker):
        """Асинх Функция → клиентский контекст."""
        code = "Асинх Функция МояФункция() Экспорт\nКонецФункции"
        ctx = checker.detect_context(code)
        assert "thin_client" in ctx


class TestGlobalContextProps:
    """Проверка глобальных свойств контекста."""

    def test_find_metadata(self, checker):
        """_find_global_context_props находит Метаданные."""
        code = "Если Метаданные.Справочники.Найти(\"Тест\") Тогда КонецЕсли;"
        props = checker._find_global_context_props(code)
        assert any(p[0] == "Метаданные" for p in props)

    def test_find_constants(self, checker):
        """_find_global_context_props находит Константы."""
        code = "Значение = Константы.ИмяКонстанты.Получить();"
        props = checker._find_global_context_props(code)
        assert any(p[0] == "Константы" for p in props)


class TestTypeInference:
    """Type inference через bsl_tree_sitter."""

    def test_http_connection_type_inference(self):
        """Соединение = Новый HTTPСоединение → type=HTTPСоединение."""
        from src.services.bsl_tree_sitter import infer_variable_types

        code = 'Соединение = Новый HTTPСоединение("api.example.com", 443);'
        var_types = infer_variable_types(code)
        assert var_types.get("Соединение") == "HTTPСоединение"

    def test_query_type_inference(self):
        """Запрос = Новый Запрос → type=Запрос."""
        from src.services.bsl_tree_sitter import infer_variable_types

        code = 'Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");'
        var_types = infer_variable_types(code)
        assert var_types.get("Запрос") == "Запрос"

    def test_extract_calls_with_types(self):
        """extract_calls_with_types находит вызов с resolved_type."""
        from src.services.bsl_tree_sitter import extract_calls_with_types

        code = '''
Соединение = Новый HTTPСоединение("api.example.com", 443);
Ответ = Соединение.Получить(Запрос);
'''
        calls = extract_calls_with_types(code)
        # Должен найти Соединение.Получить с resolved_type=HTTPСоединение
        http_calls = [c for c in calls if c.name == "Получить" and c.object_var == "Соединение"]
        assert len(http_calls) > 0
        assert http_calls[0].resolved_type == "HTTPСоединение"
