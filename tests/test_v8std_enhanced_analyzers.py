#!/usr/bin/env python3
"""Тесты для усиленных правил analyzer'ов по стандартам v8std.ru / ITS.

KB-EXP-3: проверка новых правил
- TransactionChecker: TX007-TX011 (#std632, #std490, #std792, #std496, #std661)
- check_1c_standards: no-pereyti, no-metadata-name-compare, no-export-variables,
  no-long-structure-constructor, no-string-concat-in-loop, no-tekuschaya-data
- form_quality_checker: FQ010-FQ014 (#std711, #std765, #std744, #std400, #std418)
- architecture_analyzer: ARCH011-ARCH015 (#std544, #std647, #std456, #std640, #std723)
"""

import pytest
from pathlib import Path

from src.services.analyzers.transaction_checker import TransactionChecker
from src.services.analyzers.check_1c_standards import StandardsChecker
from src.services.analyzers.form_quality_checker import FormQualityChecker
from src.services.analyzers.architecture_analyzer import ArchitectureAnalyzer


# ============================================================================
# TransactionChecker: TX007-TX011
# ============================================================================


class TestTX007ConstantInTransaction:
    """TX007: Запись константы в обработчике (#std632)."""

    def test_constant_in_procedure_detected(self, tmp_path):
        code = """Процедура ОбработкаПроведения(Отказ, РежимПроведения)
    Константы.Счетчик.Установить(1);
КонецПроцедуры"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "TX007" for v in violations)

    def test_no_constant_ok(self, tmp_path):
        code = """Процедура ОбработкаПроведения(Отказ, РежимПроведения)
    Движения.Записать();
КонецПроцедуры"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert not any(v.rule_id == "TX007" for v in violations)


class TestTX008NoObjectLock:
    """TX008: Изменение объекта без объектной блокировки (#std490)."""

    def test_no_lock_before_write_detected(self, tmp_path):
        code = """Объект = Ссылка.ПолучитьОбъект();
Объект.Наименование = "Новое имя";
Объект.Записать();"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "TX008" for v in violations)

    def test_with_lock_ok(self, tmp_path):
        code = """Объект = Ссылка.ПолучитьОбъект();
Объект.Заблокировать();
Объект.Наименование = "Новое имя";
Объект.Записать();"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert not any(v.rule_id == "TX008" for v in violations)


class TestTX009RecordInLoop:
    """TX009: Запись набора в цикле (#std792)."""

    def test_record_in_loop_detected(self, tmp_path):
        code = """Для Каждого Стр Из Таблицы Цикл
    НаборЗаписей.Запись = Стр;
    НаборЗаписей.Записать();
КонецЦикла;"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "TX009" for v in violations)


class TestTX010FullAttributeLoad:
    """TX010: ПолучитьОбъект для чтения реквизита (#std496)."""

    def test_get_object_for_read_detected(self, tmp_path):
        code = """Объект = Ссылка.ПолучитьОбъект();
Код = Объект.Код;"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "TX010" for v in violations)


class TestTX011NoDataLock:
    """TX011: Чтение остатков без ДЛЯ ИЗМЕНЕНИЯ (#std661)."""

    def test_no_lock_in_transaction_detected(self, tmp_path):
        code = """НачатьТранзакцию();
Попытка
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ РегистрНакопления.Товары.Остатки()";
    Результат = Запрос.Выполнить();
    ЗафиксироватьТранзакцию();
Исключение
    ОтменитьТранзакцию();
КонецПопытки;"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = TransactionChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "TX011" for v in violations)


# ============================================================================
# check_1c_standards: новые правила
# ============================================================================


class TestStd547NoPereyti:
    """no-pereyti: Оператор Перейти (#std547)."""

    def test_pereyti_detected(self, tmp_path):
        code = "Если Ошибка Тогда\n    Перейти ~ОбработкаОшибки;\nКонецЕсли;"
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-pereyti" for v in violations)


class TestStd442NoMetadataNameCompare:
    """no-metadata-name-compare: Сравнение через Метаданные().Имя (#std442)."""

    def test_metadata_name_compare_detected(self, tmp_path):
        code = 'Если Ссылка.Метаданные().Имя = "Поступление" Тогда\nКонецЕсли;'
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-metadata-name-compare" for v in violations)


class TestStd639NoExportVariables:
    """no-export-variables: Экспортная переменная модуля (#std639)."""

    def test_export_var_detected(self, tmp_path):
        code = "Перем ГлобальныйСчетчик Экспорт;"
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-export-variables" for v in violations)


class TestStd643NoTekuschayaData:
    """no-tekuschaya-data: ТекущаяДата вместо ТекущаяДатаСеанса (#std643)."""

    def test_tek_data_detected(self, tmp_path):
        code = "Дата = ТекущаяДата();"
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-tekuschaya-data" for v in violations)


class TestStd693NoLongStructureConstructor:
    """no-long-structure-constructor: Длинный конструктор структуры (#std693)."""

    def test_long_ctor_detected(self, tmp_path):
        code = (
            'Параметры = Новый Структура("Поле1, Поле2, Поле3, Поле4, Поле5, Поле6, '
            'Поле7, Поле8, Поле9, Поле10, Поле11", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11);'
        )
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-long-structure-constructor" for v in violations)


class TestStd782NoStringConcatInLoop:
    """no-string-concat-in-loop: Конкатенация в цикле (#std782)."""

    def test_concat_in_loop_detected(self, tmp_path):
        code = """Для Инд = 1 По 100 Цикл
    Текст = Текст + "строка" + Символы.ПС;
КонецЦикла;"""
        bsl = tmp_path / "test.bsl"
        bsl.write_text(code, encoding="utf-8")

        checker = StandardsChecker()
        violations = checker.check_file(bsl)
        assert any(v.rule_id == "no-string-concat-in-loop" for v in violations)


# ============================================================================
# form_quality_checker: FQ010-FQ014
# ============================================================================


class TestFQ010TooManyCommandPanelItems:
    """FQ010: Слишком много элементов в командной панели (#std711)."""

    def test_too_many_cmd_items_detected(self):
        checker = FormQualityChecker()
        # 16 элементов типа CommandPanel
        items = [
            {"type": "CommandPanel", "name": f"cmd{i}"}
            for i in range(16)
        ]
        form_data = {
            "name": "TestForm",
            "parent_name": "Test",
            "form": {"items": items, "attributes": []},
        }
        issues = checker.check_form(form_data)
        assert any(i.rule_id == "FQ010" for i in issues)


class TestFQ011MissingTitle:
    """FQ011: Элементы без заголовка у таблиц/групп (#std765)."""

    def test_table_without_title_detected(self):
        checker = FormQualityChecker()
        items = [
            {"type": "Table", "name": "Товары"},  # без title
        ]
        form_data = {
            "name": "TestForm",
            "parent_name": "Test",
            "form": {"items": items, "attributes": []},
        }
        issues = checker.check_form(form_data)
        assert any(i.rule_id == "FQ011" for i in issues)

    def test_table_with_title_ok(self):
        checker = FormQualityChecker()
        items = [
            {"type": "Table", "name": "Товары", "title": "Товары"},
        ]
        form_data = {
            "name": "TestForm",
            "parent_name": "Test",
            "form": {"items": items, "attributes": []},
        }
        issues = checker.check_form(form_data)
        assert not any(i.rule_id == "FQ011" for i in issues)


class TestFQ012TooManyAttributes:
    """FQ012: Слишком много реквизитов формы (#std744)."""

    def test_too_many_attrs_detected(self):
        checker = FormQualityChecker()
        attrs = [{"name": f"attr{i}"} for i in range(51)]
        form_data = {
            "name": "TestForm",
            "parent_name": "Test",
            "form": {"items": [], "attributes": attrs},
        }
        issues = checker.check_form(form_data)
        assert any(i.rule_id == "FQ012" for i in issues)


# ============================================================================
# architecture_analyzer: ARCH011-ARCH015
# ============================================================================


class TestARCH011ExportInCommandModule:
    """ARCH011: Экспорт в модуле команды (#std544)."""

    def test_export_in_command_module_detected(self, tmp_path):
        # Создаём файл в каталоге Commands
        cmd_dir = tmp_path / "Commands"
        cmd_dir.mkdir()
        bsl = cmd_dir / "MyCommand.bsl"
        bsl.write_text(
            "Процедура ОбработкаКоманды(ПараметрКоманды) Экспорт\nКонецПроцедуры",
            encoding="utf-8",
        )

        analyzer = ArchitectureAnalyzer()
        issues = analyzer.analyze_file(bsl, "MyCommand")
        assert any(i.rule_id == "ARCH011" for i in issues)


class TestARCH013LongFunction:
    """ARCH013: Длинная функция (#std456)."""

    def test_long_function_detected(self, tmp_path):
        lines = ["Процедура ДлиннаяФункция()"] + ["    // код"] * 110 + ["КонецПроцедуры"]
        bsl = tmp_path / "test.bsl"
        bsl.write_text("\n".join(lines), encoding="utf-8")

        analyzer = ArchitectureAnalyzer()
        issues = analyzer.analyze_file(bsl, "test")
        assert any(i.rule_id == "ARCH013" for i in issues)


class TestARCH014TooManyParams:
    """ARCH014: Слишком много параметров (#std640)."""

    def test_too_many_params_detected(self, tmp_path):
        params = ", ".join([f"Параметр{i}" for i in range(8)])
        bsl = tmp_path / "test.bsl"
        bsl.write_text(
            f"Процедура МояПроцедура({params})\nКонецПроцедуры",
            encoding="utf-8",
        )

        analyzer = ArchitectureAnalyzer()
        issues = analyzer.analyze_file(bsl, "test")
        assert any(i.rule_id == "ARCH014" for i in issues)


class TestARCH015COMNoPlatformCheck:
    """ARCH015: COM без проверки платформы (#std723)."""

    def test_com_no_check_detected(self, tmp_path):
        bsl = tmp_path / "test.bsl"
        bsl.write_text(
            'Объект = Новый COMОбъект("Excel.Application");',
            encoding="utf-8",
        )

        analyzer = ArchitectureAnalyzer()
        issues = analyzer.analyze_file(bsl, "test")
        assert any(i.rule_id == "ARCH015" for i in issues)

    def test_com_with_check_ok(self, tmp_path):
        bsl = tmp_path / "test.bsl"
        bsl.write_text(
            'Информация = Новый СистемнаяИнформация;\n'
            'Если Информация.ТипПлатформы = ТипПлатформы.Windows_x86 Тогда\n'
            '    Объект = Новый COMОбъект("Excel.Application");\n'
            'КонецЕсли;',
            encoding="utf-8",
        )

        analyzer = ArchitectureAnalyzer()
        issues = analyzer.analyze_file(bsl, "test")
        assert not any(i.rule_id == "ARCH015" for i in issues)
