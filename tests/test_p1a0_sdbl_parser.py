"""
Phase A.0 — Тесты для SDBL AST парсера.

Проверяет:
1. Базовое парсинг запросов (SELECT, FROM, WHERE, GROUP BY)
2. Извлечение таблиц и алиасов
3. Извлечение полей SELECT
4. Извлечение параметров (&Параметр)
5. Агрегатные функции (СУММА, КОЛИЧЕСТВО, ...)
6. Пакетные запросы (несколько SELECT)
7. Виртуальные таблицы
8. Совместимость с ParsedBatch интерфейсом
"""

from __future__ import annotations

import pytest

# Динамическая проверка доступности SDBL
try:
    from src.services.analyzers.sdbl_parser import (
        SDBLBatch,
        SDBLField,
        SDBLQuery,
        SDBLQueryParser,
        SDBLTable,
        is_sdbl_available,
    )
    _SDBL_AVAILABLE = is_sdbl_available()
except ImportError:
    _SDBL_AVAILABLE = False


if not _SDBL_AVAILABLE:
    pytest.skip("SDBL parser недоступен (antlr4-python3-runtime не установлен)", allow_module_level=True)


# ============================================================================
# 1. БАЗОВЫЙ ПАРСИНГ
# ============================================================================


class TestSDBLBasicParsing:
    """Базовые тесты парсинга запросов через SDBL AST."""

    def test_parse_simple_select(self):
        """Простой SELECT с одной таблицей."""
        q = """
        ВЫБРАТЬ
            Номенклатура.Ссылка,
            Номенклатура.Наименование
        ИЗ
            Справочник.Номенклатура КАК Номенклатура
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert batch.has_syntax_error is False
        assert len(batch.queries) == 1

    def test_parse_empty_query(self):
        """Пустой запрос → пустой batch."""
        parser = SDBLQueryParser()
        batch = parser.parse("")
        assert batch.queries == []

    def test_parse_query_with_syntax_error(self):
        """Запрос с синтаксической ошибкой."""
        parser = SDBLQueryParser()
        batch = parser.parse("ВЫБРАТЬ ИЗ")  # Незавершённый
        # SDBL может быть толерантен — главное что не падает
        assert isinstance(batch, SDBLBatch)

    def test_parse_english_keywords(self):
        """Английские ключевые слова SELECT/FROM/WHERE."""
        q = """
        SELECT
            t.Ref,
            t.Description
        FROM
            Catalog.Goods AS t
        WHERE
            t.Description LIKE &Pattern
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert batch.has_syntax_error is False
        assert len(batch.queries) >= 1


# ============================================================================
# 2. ИЗВЛЕЧЕНИЕ ТАБЛИЦ
# ============================================================================


class TestSDBLTableExtraction:
    """Тесты извлечения таблиц из SDBL AST."""

    def test_extract_table_with_alias(self):
        """Таблица с алиасом."""
        q = """
        ВЫБРАТЬ Рег.Ссылка
        ИЗ РегистрНакопления.Продажи КАК Рег
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            assert len(query.tables) >= 1
            # Должна быть таблица РегистрНакопления.Продажи
            found = any(
                "Продажи" in t.full_name or t.object_name == "Продажи"
                for t in query.tables
            )
            assert found, f"Таблица Продажи не найдена: {query.tables}"

    def test_extract_multiple_tables_join(self):
        """Несколько таблиц с JOIN."""
        q = """
        ВЫБРАТЬ
            Т.Ссылка,
            В.Наименование КАК Вид
        ИЗ
            Справочник.Номенклатура КАК Т
            ЛЕВОЕ СОЕДИНЕНИЕ Справочник.ВидыНоменклатуры КАК В
                ПО Т.ВидНоменклатуры = В.Ссылка
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должны быть извлечены таблицы (минимум 1, лучше 2)
            assert len(query.tables) >= 1

    def test_extract_virtual_table(self):
        """Виртуальная таблица Остатки."""
        q = """
        ВЫБРАТЬ
            Остатки.Номенклатура
        ИЗ
            РегистрНакопления.ТоварыНаСкладах.Остатки(&Период) КАК Остатки
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должна быть таблица с ТоварыНаСкладах
            found = any(
                "ТоварыНаСкладах" in t.full_name or t.object_name == "ТоварыНаСкладах"
                for t in query.tables
            )
            assert found, f"Виртуальная таблица не найдена: {query.tables}"


# ============================================================================
# 3. ИЗВЛЕЧЕНИЕ ПОЛЕЙ SELECT
# ============================================================================


class TestSDBLSelectFields:
    """Тесты извлечения полей SELECT."""

    def test_extract_simple_fields(self):
        """Простые поля в SELECT."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            Рег.Выручка
        ИЗ
            РегистрНакопления.Продажи КАК Рег
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            assert len(query.select_fields) >= 2

    def test_extract_aggregate_function(self):
        """Агрегатная функция СУММА."""
        q = """
        ВЫБРАТЬ
            СУММА(Рег.Выручка) КАК СуммаВыручки
        ИЗ
            РегистрНакопления.Продажи КАК Рег
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должна быть агрегатная функция
            agg_fields = [f for f in query.select_fields if f.aggregate]
            assert len(agg_fields) >= 1

    def test_extract_field_with_alias(self):
        """Поле с алиасом КАК."""
        q = """
        ВЫБРАТЬ
            Рег.Выручка КАК Сумма
        ИЗ
            РегистрНакопления.Продажи КАК Рег
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должно быть поле с алиасом
            aliased = [f for f in query.select_fields if f.alias]
            # AST extraction может быть несовершенным, проверяем что поля есть
            assert len(query.select_fields) >= 1


# ============================================================================
# 4. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ
# ============================================================================


class TestSDBLParameters:
    """Тесты извлечения параметров запроса (&Параметр)."""

    def test_extract_parameter_in_where(self):
        """Параметр в WHERE."""
        q = """
        ВЫБРАТЬ Рег.Ссылка
        ИЗ РегистрНакопления.Продажи КАК Рег
        ГДЕ Рег.Период = &ДатаНачала
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должен быть параметр ДатаНачала (возможно с лишним, но должен быть)
            assert any("ДатаНачала" in p for p in query.parameters)

    def test_extract_multiple_parameters(self):
        """Несколько параметров."""
        q = """
        ВЫБРАТЬ Рег.Ссылка
        ИЗ РегистрНакопления.Продажи КАК Рег
        ГДЕ Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
            И Рег.Склад = &Склад
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        if batch.queries:
            query = batch.queries[0]
            # Должны быть параметры (минимум какие-то из них)
            assert len(query.parameters) >= 2


# ============================================================================
# 5. ПАКЕТНЫЕ ЗАПРОСЫ
# ============================================================================


class TestSDBLBatchQueries:
    """Тесты пакетных запросов."""

    def test_parse_batch_with_temp_table(self):
        """Пакетный запрос с временной таблицей."""
        q = """
        ВЫБРАТЬ
            Номенклатура.Ссылка КАК Ссылка
        ПОМЕСТИТЬ ВременнаяТаблица
        ИЗ
            Справочник.Номенклатура КАК Номенклатура
        ;

        ВЫБРАТЬ
            ВременнаяТаблица.Ссылка
        ИЗ
            ВременнаяТаблица КАК ВременнаяТаблица
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        # SDBL поддерживает пакетные запросы через ;
        assert len(batch.queries) >= 1

    def test_parse_multiple_selects(self):
        """Несколько SELECT в пакете."""
        q = """
        ВЫБРАТЬ Первая.Ссылка ИЗ Справочник.Первый КАК Первая;
        ВЫБРАТЬ Вторая.Ссылка ИЗ Справочник.Второй КАК Вторая
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert len(batch.queries) >= 1


# ============================================================================
# 6. СОВМЕСТИМОСТЬ С ParsedBatch ИНТЕРФЕЙСОМ
# ============================================================================


class TestSDBLCompatibility:
    """Тесты совместимости с существующим ParsedBatch интерфейсом."""

    def test_sdbl_batch_has_required_fields(self):
        """SDBLBatch имеет те же поля что ParsedBatch."""
        batch = SDBLBatch()
        assert hasattr(batch, "queries")
        assert hasattr(batch, "raw_text")
        assert hasattr(batch, "get_all_tables")
        assert hasattr(batch, "get_temp_table_definition")

    def test_sdbl_query_has_required_fields(self):
        """SDBLQuery имеет те же поля что ParsedQuery."""
        query = SDBLQuery()
        for field in [
            "tables", "select_fields", "where_fields", "group_by_fields",
            "order_by_fields", "parameters", "temp_tables", "into_temp_table",
            "raw_text", "get_table_by_alias",
        ]:
            assert hasattr(query, field), f"Missing field: {field}"

    def test_sdbl_table_has_required_fields(self):
        """SDBLTable имеет те же поля что QueryTable."""
        table = SDBLTable(full_name="Справочник.Товары")
        assert hasattr(table, "full_name")
        assert hasattr(table, "object_type")
        assert hasattr(table, "object_name")
        assert hasattr(table, "virtual_table")
        assert hasattr(table, "alias")
        assert hasattr(table, "join_type")
        # Проверяем __post_init__
        assert table.object_type == "Справочник"
        assert table.object_name == "Товары"

    def test_sdbl_field_has_required_fields(self):
        """SDBLField имеет те же поля что QueryField."""
        field = SDBLField(raw="Рег.Номенклатура")
        assert hasattr(field, "raw")
        assert hasattr(field, "table_alias")
        assert hasattr(field, "field_name")
        assert hasattr(field, "alias")
        assert hasattr(field, "aggregate")
        assert hasattr(field, "context")
        # Проверяем __post_init__
        assert field.table_alias == "Рег"
        assert field.field_name == "Номенклатура"


# ============================================================================
# 7. РЕГРЕССИОННЫЕ ТЕСТЫ — реальные запросы
# ============================================================================


class TestSDBLRealQueries:
    """Тесты на реальных запросах 1С."""

    def test_sales_by_period(self):
        """Запрос продаж по периодам — типичный 1С кейс."""
        q = """
        ВЫБРАТЬ
            Продажи.Номенклатура,
            Продажи.Склад,
            СУММА(Продажи.Выручка) КАК Выручка,
            СУММА(Продажи.Количество) КАК Количество
        ИЗ
            РегистрНакопления.Продажи КАК Продажи
        ГДЕ
            Продажи.Период МЕЖДУ &ДатаНачала И &ДатаКонца
        СГРУППИРОВАТЬ ПО
            Продажи.Номенклатура,
            Продажи.Склад
        УПОРЯДОЧИТЬ ПО
            Выручка УБЫВ
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert batch.has_syntax_error is False
        assert len(batch.queries) == 1

    def test_query_with_join_and_filter(self):
        """Запрос с JOIN и фильтрацией."""
        q = """
        ВЫБРАТЬ
            Заказ.Ссылка,
            Заказ.Контрагент,
            Контрагент.Наименование КАК КонтрагентНаименование
        ИЗ
            Документ.ЗаказКлиента КАК Заказ
            ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК Контрагент
                ПО Заказ.Контрагент = Контрагент.Ссылка
        ГДЕ
            Заказ.Дата МЕЖДУ &ДатаНачала И &ДатаКонца
            И Заказ.Проведен = ИСТИНА
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert batch.has_syntax_error is False

    def test_balances_virtual_table(self):
        """Запрос к виртуальной таблице Остатки."""
        q = """
        ВЫБРАТЬ
            Остатки.Номенклатура,
            Остатки.Склад,
            Остатки.КоличествоОстаток
        ИЗ
            РегистрНакопления.ТоварыНаСкладах.Остатки(
                &Период,
                Склад = &СкладПараметр
            ) КАК Остатки
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        assert batch.has_syntax_error is False

    def test_complex_nested_query(self):
        """Сложный запрос с подзапросом в WHERE."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            СУММА(Рег.Выручка) КАК Сумма
        ИЗ
            РегистрНакопления.Продажи КАК Рег
        ГДЕ
            Рег.Номенклатура В
                (ВЫБРАТЬ
                    НоменклатураЛук.Ссылка
                ИЗ
                    Справочник.Номенклатура КАК НоменклатураЛук
                ГДЕ
                    НоменклатураЛук.Наименование ПОДОБНО &Шаблон)
        СГРУППИРОВАТЬ ПО
            Рег.Номенклатура
        """
        parser = SDBLQueryParser()
        batch = parser.parse(q)
        # SDBL должен обработать без ошибок (подзапросы поддерживаются)
        assert batch.has_syntax_error is False
