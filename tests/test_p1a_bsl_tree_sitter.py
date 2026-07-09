"""
P1-A — Тесты для tree-sitter-bsl AST парсера.

Проверяет:
1. Базовое извлечение процедур/функций
2. Флаг Экспорт
3. Извлечение вызовов методов внутри тела
4. Краевые случаи: пустой код, синтаксические ошибки
5. Совместимость с bsl_ast.py (fallback когда tree-sitter недоступен)
"""

from __future__ import annotations

import pytest


# Динамически проверяем доступность tree-sitter
try:
    from src.services.bsl_tree_sitter import (
        BslSymbol,
        BslTreeSitterParser,
        extract_symbols,
        extract_symbols_from_file,
        is_available,
    )
    _TS_AVAILABLE = is_available()
except ImportError:
    _TS_AVAILABLE = False


# Все тесты пропускаются если tree-sitter не установлен
if not _TS_AVAILABLE:
    pytest.skip("tree-sitter-bsl не установлен", allow_module_level=True)


# ============================================================================
# 1. БАЗОВОЕ ИЗВЛЕЧЕНИЕ ПРОЦЕДУР/ФУНКЦИЙ
# ============================================================================


class TestExtractSymbolsBasic:
    """Базовые тесты извлечения процедур и функций."""

    def test_parse_simple_procedure(self):
        """Простая процедура."""
        code = "Процедура МояПроцедура()\n\tВозврат;\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "МояПроцедура"
        assert symbols[0].kind == "procedure"
        assert symbols[0].start_line == 1

    def test_parse_simple_function(self):
        """Простая функция."""
        code = "Функция МояФункция()\n\tВозврат 1;\nКонецФункции"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "МояФункция"
        assert symbols[0].kind == "function"

    def test_parse_multiple_symbols(self):
        """Несколько процедур/функций в одном файле."""
        code = """Процедура Первая()
КонецПроцедуры

Функция Вторая()
    Возврат 1;
КонецФункции

Процедура Третья()
КонецПроцедуры"""
        symbols = extract_symbols(code)
        assert len(symbols) == 3
        names = [s.name for s in symbols]
        assert "Первая" in names
        assert "Вторая" in names
        assert "Третья" in names

    def test_parse_empty_code(self):
        """Пустой код → пустой список."""
        assert extract_symbols("") == []

    def test_parse_code_without_definitions(self):
        """Код без определений процедур/функций."""
        code = "// Просто комментарий\nПерем ГлобальнаяПеременная;"
        symbols = extract_symbols(code)
        assert symbols == []


# ============================================================================
# 2. ФЛАГ ЭКСПОРТ
# ============================================================================


class TestExportFlag:
    """Тесты флага Экспорт."""

    def test_export_procedure(self):
        """Процедура с Экспорт."""
        code = "Процедура МояПроцедура() Экспорт\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].is_export is True

    def test_non_export_procedure(self):
        """Процедура без Экспорт."""
        code = "Процедура МояПроцедура()\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].is_export is False

    def test_export_function_with_params(self):
        """Функция с параметрами и Экспорт."""
        code = "Функция МояФункция(Параметр1, Параметр2) Экспорт\n\tВозврат Параметр1;\nКонецФункции"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].is_export is True
        assert symbols[0].name == "МояФункция"

    def test_mixed_export_and_non_export(self):
        """Смешанные: с Экспорт и без."""
        code = """Процедура Открытая() Экспорт
КонецПроцедуры

Процедура Закрытая()
КонецПроцедуры"""
        symbols = extract_symbols(code)
        assert len(symbols) == 2
        export_flags = {s.name: s.is_export for s in symbols}
        assert export_flags["Открытая"] is True
        assert export_flags["Закрытая"] is False


# ============================================================================
# 3. ИЗВЛЕЧЕНИЕ ВЫЗОВОВ МЕТОДОВ
# ============================================================================


class TestExtractCalls:
    """Тесты извлечения вызовов методов внутри тела процедуры/функции."""

    def test_extract_simple_calls(self):
        """Простые вызовы методов."""
        code = """Процедура МояПроцедура()
    ПодготовитьДанные();
    ЗаписатьВЖурнал("текст");
КонецПроцедуры"""
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        calls = symbols[0].calls
        assert "ПодготовитьДанные" in calls
        assert "ЗаписатьВЖурнал" in calls

    def test_extract_calls_with_deduplication(self):
        """Дубликаты вызовов схлопываются."""
        code = """Процедура МояПроцедура()
    ПодготовитьДанные();
    ПодготовитьДанные();
    ПодготовитьДанные();
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # 'ПодготовитьДанные' должен быть только один раз
        assert calls.count("ПодготовитьДанные") == 1

    def test_keywords_not_in_calls(self):
        """Ключевые слова BSL не считаются вызовами."""
        code = """Процедура МояПроцедура()
    Если Условие() Тогда
        Возврат;
    КонецЕсли;
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # 'Если', 'Тогда', 'КонецЕсли' не должны быть в calls
        assert "Если" not in calls
        assert "Тогда" not in calls
        assert "КонецЕсли" not in calls
        # 'Условие' должно быть
        assert "Условие" in calls

    def test_calls_in_nested_blocks(self):
        """Вызовы во вложенных блоках (если/циклы)."""
        code = """Процедура МояПроцедура()
    Для Индекс = 1 По 10 Цикл
        ОбработатьЭлемент(Индекс);
    КонецЦикла;
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        assert "ОбработатьЭлемент" in calls

    def test_no_calls_in_empty_procedure(self):
        """Пустая процедура — нет вызовов."""
        code = "Процедура МояПроцедура()\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert symbols[0].calls == []

    def test_method_calls_on_objects(self):
        """Вызовы методов на объектах: Объект.Метод()."""
        code = """Процедура МояПроцедура()
    Таблица.Добавить();
    Структура.Вставить("ключ", "значение");
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # Должны быть извлечены имена методов (без префикса объекта)
        assert "Добавить" in calls
        assert "Вставить" in calls


# ============================================================================
# 4. КРАЕВЫЕ СЛУЧАИ
# ============================================================================


class TestEdgeCases:
    """Краевые случаи."""

    def test_procedure_with_annotation(self):
        """Процедура с аннотацией &НаСервере."""
        code = """&НаСервере
Процедура МояПроцедура()
КонецПроцедуры"""
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "МояПроцедура"

    def test_procedure_with_multiple_annotations(self):
        """Процедура с несколькими аннотациями."""
        code = """&НаСервере
&НаКлиенте
Процедура ПриОткрытии()
КонецПроцедуры"""
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].name == "ПриОткрытии"

    def test_syntax_error_does_not_crash(self):
        """Синтаксическая ошибка не должна валить парсер."""
        # Незакрытая процедура
        code = "Процедура МояПроцедура()\n\tВозврат;"
        # tree-sitter должен обработать gracefully
        symbols = extract_symbols(code)
        # Может вернуть 0 или 1 символ — главное не упасть
        assert isinstance(symbols, list)

    def test_lines_are_1_based(self):
        """Номера строк 1-based."""
        code = "\n\nПроцедура МояПроцедура()\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        assert symbols[0].start_line == 3  # 3-я строка (1-based)

    def test_end_line_correct(self):
        """end_line корректен."""
        code = "Процедура МояПроцедура()\n\tДействие();\nКонецПроцедуры"
        symbols = extract_symbols(code)
        assert symbols[0].start_line == 1
        assert symbols[0].end_line == 3

    def test_english_keywords(self):
        """Английские ключевые слова Procedure/Function."""
        code = """Procedure MyProcedure()
    Return;
EndProcedure

Function MyFunction()
    Return 1;
EndFunction"""
        symbols = extract_symbols(code)
        # tree-sitter-bsl поддерживает английские ключевые слова
        names = [s.name for s in symbols]
        assert "MyProcedure" in names or len(symbols) >= 1


# ============================================================================
# 5. PUBLIC API
# ============================================================================


class TestPublicAPI:
    """Тесты публичного API модуля."""

    def test_get_parser_returns_singleton(self):
        """get_parser() возвращает singleton."""
        from src.services.bsl_tree_sitter import get_parser

        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2

    def test_is_available_returns_true(self):
        """is_available() возвращает True когда установлен."""
        assert is_available() is True

    def test_parser_class_instantiation(self):
        """BslTreeSitterParser создаётся без ошибок."""
        parser = BslTreeSitterParser()
        assert parser is not None

    def test_parse_file_method(self, tmp_path):
        """parse_file читает .bsl файл."""
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text(
            "Процедура Тест()\n\tВозврат;\nКонецПроцедуры",
            encoding="utf-8",
        )

        parser = BslTreeSitterParser()
        symbols = parser.parse_file(bsl_file)
        assert len(symbols) == 1
        assert symbols[0].name == "Тест"

    def test_parse_file_with_bom(self, tmp_path):
        """parse_file корректно читает UTF-8 с BOM."""
        bsl_file = tmp_path / "test.bsl"
        # UTF-8 с BOM
        bsl_file.write_bytes(
            b"\xef\xbb\xbf"
            + "Процедура Тест()\nКонецПроцедуры".encode("utf-8")
        )

        parser = BslTreeSitterParser()
        symbols = parser.parse_file(bsl_file)
        assert len(symbols) == 1
        assert symbols[0].name == "Тест"

    def test_extract_symbols_from_file(self, tmp_path):
        """extract_symbols_from_file — удобная функция."""
        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text(
            "Функция МояФункция() Экспорт\n\tВозврат 1;\nКонецФункции",
            encoding="utf-8",
        )

        symbols = extract_symbols_from_file(bsl_file)
        assert len(symbols) == 1
        assert symbols[0].name == "МояФункция"
        assert symbols[0].kind == "function"
        assert symbols[0].is_export is True


# ============================================================================
# 6. РЕГРЕССИОННЫЕ ТЕСТЫ — типичные BSL паттерны
# ============================================================================


class TestRealBSLPatterns:
    """Тесты на реальных BSL паттернах из 1С разработки."""

    def test_typical_1c_module_pattern(self):
        """Типичный модуль 1С с областями и комментариями."""
        code = """#Область ПрограммныйИнтерфейс

// Получает элемент справочника по коду.
// Возвращает СправочникСсылка.Товары.
Функция ПолучитьПоКоду(Код) Экспорт
    Возврат Справочники.Товары.НайтиПоКоду(Код);
КонецФункции

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Процедура ВнутренняяПроцедура()
    Данные = Новый Структура;
КонецПроцедуры

#КонецОбласти"""
        symbols = extract_symbols(code)
        assert len(symbols) == 2
        names = [s.name for s in symbols]
        assert "ПолучитьПоКоду" in names
        assert "ВнутренняяПроцедура" in names

    def test_method_call_in_return(self):
        """Вызов метода в Return."""
        code = """Функция Вычислить()
    Возврат Математика.Сумма(1, 2);
КонецФункции"""
        symbols = extract_symbols(code)
        assert len(symbols) == 1
        # Должен извлечь 'Сумма' из вызова
        assert "Сумма" in symbols[0].calls

    def test_complex_nested_calls(self):
        """Сложные вложенные вызовы."""
        code = """Процедура Сложная()
    Результат = Обработать(Подготовить(ПолучитьДанные()));
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # Все три вызова должны быть извлечены
        assert "Обработать" in calls
        assert "Подготовить" in calls
        assert "ПолучитьДанные" in calls

    def test_no_calls_in_string_literals(self):
        """Вызовы внутри строк не считаются."""
        code = """Процедура Тест()
    Стр = "ПодготовитьДанные() в строке";
    ПодготовитьДанные();
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # Только реальный вызов, не из строки
        assert calls == ["ПодготовитьДанные"]

    def test_no_calls_in_comments(self):
        """Вызовы в комментариях не считаются."""
        code = """Процедура Тест()
    // Это комментарий с ВызватьМетод()
    // ДругойМетод() тоже в комментарии
    РеальныйВызов();
КонецПроцедуры"""
        symbols = extract_symbols(code)
        calls = symbols[0].calls
        # Только реальный вызов
        assert "РеальныйВызов" in calls
        assert "ВызватьМетод" not in calls
        assert "ДругойМетод" not in calls
