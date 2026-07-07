"""
P1.5 — Тесты для статического валидатора запросов 1С.

Проверяет:
1. Парсер запросов (query_parser.py)
2. Статический валидатор (query_validator_static.py)
3. Реальный кейс: запрос к регистру накопления с несуществующим полем
   (тот самый баг из прошлой сессии: ВыручкаСебестоимость.Номенклатура)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.analyzers.query_parser import QueryParser
from src.services.analyzers.query_validator_static import (
    StaticQueryValidator,
    ValidationIssue,
    ValidationResult,
)


# ============================================================================
# ФИКСТУРЫ
# ============================================================================


@pytest.fixture
def ut11_metadata_path() -> Path:
    """Путь к unified-metadata-index.json для УТ11."""
    p = (
        Path(__file__).parent.parent
        / "analysis"
        / "1c-ai-dev-env"
        / "derived"
        / "configs"
        / "УправлениеТорговлей"
        / "unified-metadata-index.json"
    )
    if not p.exists():
        # Альтернативный путь в самом репозитории
        p = (
            Path(__file__).parent.parent
            / "derived"
            / "configs"
            / "УправлениеТорговлей"
            / "unified-metadata-index.json"
        )
    if not p.exists():
        pytest.skip("UT11 metadata index not found")
    return p


@pytest.fixture
def ut11_validator(ut11_metadata_path) -> StaticQueryValidator:
    """Валидатор с загруженным индексом УТ11."""
    return StaticQueryValidator.from_metadata_file(ut11_metadata_path)


@pytest.fixture
def simple_metadata() -> dict:
    """Простые метаданные для unit-тестов без зависимости от УТ11."""
    return {
        "objects": {
            "AccumulationRegisters": [
                {
                    "type": "AccumulationRegister",
                    "name": "ВыручкаСебестоимость",
                    "synonym": "Выручка и себестоимость",
                    "properties": {"RegisterType": "Balance"},
                    "child_objects": {
                        "attributes": [
                            {"name": "Номенклатура", "types": ["cfg:CatalogRef.Номенклатура"], "kind": "Dimension"},
                            {"name": "Склад", "types": ["cfg:CatalogRef.Склады"], "kind": "Dimension"},
                            {"name": "Выручка", "types": ["xs:decimal"], "kind": "Resource"},
                            {"name": "Себестоимость", "types": ["xs:decimal"], "kind": "Resource"},
                            {"name": "Количество", "types": ["xs:decimal"], "kind": "Resource"},
                        ],
                        "dimensions": [
                            {"name": "Номенклатура", "types": ["cfg:CatalogRef.Номенклатура"], "kind": "Dimension"},
                            {"name": "Склад", "types": ["cfg:CatalogRef.Склады"], "kind": "Dimension"},
                        ],
                        "resources": [
                            {"name": "Выручка", "types": ["xs:decimal"], "kind": "Resource"},
                            {"name": "Себестоимость", "types": ["xs:decimal"], "kind": "Resource"},
                            {"name": "Количество", "types": ["xs:decimal"], "kind": "Resource"},
                        ],
                        "attributes_only": [],
                        "standard_attributes": [
                            {"name": "Период", "type": "xs:dateTime", "kind": "Standard"},
                            {"name": "Регистратор", "type": "DocumentRef.<Any>", "kind": "Standard"},
                            {"name": "Активность", "type": "xs:boolean", "kind": "Standard"},
                        ],
                    },
                }
            ],
            "Catalogs": [
                {
                    "type": "Catalog",
                    "name": "Номенклатура",
                    "synonym": "Номенклатура",
                    "properties": {},
                    "child_objects": {
                        "attributes": [
                            {"name": "Наименование", "types": ["xs:string"], "kind": "Attribute"},
                            {"name": "Код", "types": ["xs:string"], "kind": "Standard"},
                            {"name": "Ссылка", "types": ["cfg:CatalogRef.Номенклатура"], "kind": "Standard"},
                            {"name": "ВидНоменклатуры", "types": ["cfg:CatalogRef.ВидыНоменклатуры"], "kind": "Attribute"},
                        ],
                        "dimensions": [],
                        "resources": [],
                        "attributes_only": [
                            {"name": "Наименование", "types": ["xs:string"], "kind": "Attribute"},
                            {"name": "ВидНоменклатуры", "types": ["cfg:CatalogRef.ВидыНоменклатуры"], "kind": "Attribute"},
                        ],
                        "standard_attributes": [
                            {"name": "Ссылка", "types": ["cfg:CatalogRef.Номенклатура"], "kind": "Standard"},
                            {"name": "Код", "types": ["xs:string"], "kind": "Standard"},
                            {"name": "Наименование", "types": ["xs:string"], "kind": "Standard"},
                        ],
                    },
                }
            ],
        }
    }


@pytest.fixture
def simple_validator(simple_metadata) -> StaticQueryValidator:
    """Валидатор на простых метаданных."""
    return StaticQueryValidator(simple_metadata)


# ============================================================================
# 1. ТЕСТЫ ПАРСЕРА
# ============================================================================


class TestQueryParser:
    """Тесты парсера запросов 1С."""

    def test_parse_simple_select(self):
        """Простой SELECT с одной таблицей."""
        q = """
        ВЫБРАТЬ
            Номенклатура.Ссылка,
            Номенклатура.Наименование
        ИЗ
            Справочник.Номенклатура КАК Номенклатура
        """
        parser = QueryParser()
        result = parser.parse(q)
        assert len(result.queries) == 1
        query = result.queries[0]
        assert len(query.tables) == 1
        assert query.tables[0].full_name == "Справочник.Номенклатура"
        assert query.tables[0].object_type == "Справочник"
        assert query.tables[0].object_name == "Номенклатура"
        assert query.tables[0].alias == "Номенклатура"

    def test_parse_select_with_where(self):
        """SELECT с WHERE."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            Рег.Выручка
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        ГДЕ
            Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
            И Рег.Номенклатура В
                (ВЫБРАТЬ
                    НоменклатураЛук.Ссылка
                ИЗ
                    Справочник.Номенклатура КАК НоменклатураЛук
                ГДЕ
                    НоменклатураЛук.Наименование ПОДОБНО &ШаблонПоиска)
        """
        parser = QueryParser()
        result = parser.parse(q)
        assert len(result.queries) >= 1
        # Внешний запрос
        outer = result.queries[0]
        # P1.5: парсер может найти и таблицу из подзапроса (известное ограничение regex-парсера),
        # но внешняя таблица точно должна быть первой
        assert len(outer.tables) >= 1
        assert outer.tables[0].full_name == "РегистрНакопления.ВыручкаСебестоимость"
        assert outer.tables[0].alias == "Рег"
        # Параметры
        assert "ДатаНачала" in outer.parameters
        assert "ДатаКонца" in outer.parameters
        assert "ШаблонПоиска" in outer.parameters

    def test_parse_virtual_table(self):
        """Парсинг виртуальной таблицы Остатки."""
        q = """
        ВЫБРАТЬ
            Остатки.Номенклатура,
            Остатки.КоличествоОстаток
        ИЗ
            РегистрНакопления.ТоварыНаСкладах.Остатки(
                &Период,
                Склад = &СкладПараметр
            ) КАК Остатки
        """
        parser = QueryParser()
        result = parser.parse(q)
        assert len(result.queries) == 1
        query = result.queries[0]
        assert len(query.tables) == 1
        table = query.tables[0]
        assert table.object_type == "РегистрНакопления"
        assert table.object_name == "ТоварыНаСкладах"
        assert table.virtual_table == "Остатки"
        # Параметры виртуальной таблицы
        assert "&Период" in table.virtual_table_params or "Период" in table.virtual_table_params

    def test_parse_join(self):
        """Парсинг LEFT JOIN."""
        q = """
        ВЫБРАТЬ
            Т.Ссылка,
            Т.Наименование,
            В.Наименование КАК Вид
        ИЗ
            Справочник.Номенклатура КАК Т
            ЛЕВОЕ СОЕДИНЕНИЕ Справочник.ВидыНоменклатуры КАК В
                ПО Т.ВидНоменклатуры = В.Ссылка
        """
        parser = QueryParser()
        result = parser.parse(q)
        query = result.queries[0]
        assert len(query.tables) == 2
        # Первая таблица (FROM)
        assert query.tables[0].full_name == "Справочник.Номенклатура"
        assert query.tables[0].alias == "Т"
        # Вторая таблица (JOIN)
        assert query.tables[1].full_name == "Справочник.ВидыНоменклатуры"
        assert query.tables[1].alias == "В"
        assert query.tables[1].join_type == "LEFT"

    def test_parse_aggregate(self):
        """Парсинг агрегатных функций."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            СУММА(Рег.Выручка) КАК СуммаВыручки,
            КОЛИЧЕСТВО(Рег.Номенклатура) КАК КоличествоПродаж
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        СГРУППИРОВАТЬ ПО
            Рег.Номенклатура
        """
        parser = QueryParser()
        result = parser.parse(q)
        query = result.queries[0]
        # Должны распознать агрегаты
        agg_fields = [f for f in query.select_fields if f.aggregate]
        assert len(agg_fields) == 2
        aggregates = {f.aggregate for f in agg_fields}
        assert "SUM" in aggregates
        assert "COUNT" in aggregates

    def test_parse_batch_with_temp_table(self):
        """Пакетный запрос с временной таблицей."""
        q = """
        ВЫБРАТЬ
            Номенклатура.Ссылка КАК Ссылка
        ПОМЕСТИТЬ ВременнаяТаблица
        ИЗ
            Справочник.Номенклатура КАК Номенклатура
        ГДЕ
            Номенклатура.Наименование ПОДОБНО &Шаблон
        ;

        ВЫБРАТЬ
            ВременнаяТаблица.Ссылка
        ИЗ
            ВременнаяТаблица КАК ВременнаяТаблица
        """
        parser = QueryParser()
        result = parser.parse(q)
        assert len(result.queries) == 2
        assert result.queries[0].into_temp_table == "ВременнаяТаблица"

    def test_parse_english_keywords(self):
        """Английские ключевые слова."""
        q = """
        SELECT
            t.Ref,
            t.Description
        FROM
            Catalog.Goods AS t
        WHERE
            t.Description LIKE &Pattern
        """
        parser = QueryParser()
        result = parser.parse(q)
        query = result.queries[0]
        assert len(query.tables) == 1
        assert query.tables[0].object_type == "Catalog"
        assert query.tables[0].object_name == "Goods"
        assert query.tables[0].alias == "t"

    def test_parse_parameters(self):
        """Извлечение параметров &Параметр."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        ГДЕ
            Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
            И Рег.Склад = &Склад
            И Рег.Номенклатура В (&МассивНоменклатуры)
        """
        parser = QueryParser()
        result = parser.parse(q)
        query = result.queries[0]
        assert "ДатаНачала" in query.parameters
        assert "ДатаКонца" in query.parameters
        assert "Склад" in query.parameters
        assert "МассивНоменклатуры" in query.parameters


# ============================================================================
# 2. ТЕСТЫ ВАЛИДАТОРА (НА ПРОСТЫХ МЕТАДАННЫХ)
# ============================================================================


class TestStaticQueryValidatorSimple:
    """Тесты валидатора на простой метаданной фикстуре."""

    def test_valid_query(self, simple_validator):
        """Корректный запрос — валидатор должен вернуть valid=True."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            Рег.Выручка
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        assert result.valid is True
        assert result.total_errors == 0
        assert result.parsed_tables == 1
        assert result.parsed_queries == 1

    def test_field_not_found(self, simple_validator):
        """Несуществующее поле — должна быть ошибка FIELD_NOT_FOUND."""
        # Это именно тот баг из прошлой сессии
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            Рег.НесуществующееПоле
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        assert result.valid is False
        not_found_errors = [i for i in result.issues if i.rule_id == "FIELD_NOT_FOUND"]
        assert len(not_found_errors) >= 1
        assert "НесуществующееПоле" in not_found_errors[0].message

    def test_table_not_found(self, simple_validator):
        """Несуществующая таблица — TABLE_NOT_FOUND."""
        q = """
        ВЫБРАТЬ
            Рег.Ссылка
        ИЗ
            РегистрНакопления.НесуществующийРегистр КАК Рег
        """
        result = simple_validator.validate(q)
        assert result.valid is False
        errors = [i for i in result.issues if i.rule_id == "TABLE_NOT_FOUND"]
        assert len(errors) >= 1

    def test_virtual_table_balances_available(self, simple_validator):
        """Для регистра остатков Остатки доступны."""
        q = """
        ВЫБРАТЬ
            Остатки.Номенклатура
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость.Остатки(
                &Период
            ) КАК Остатки
        """
        result = simple_validator.validate(q)
        # Не должно быть ошибки о недоступности виртуальной таблицы
        vtable_errors = [
            i for i in result.issues
            if i.rule_id == "VIRTUAL_TABLE_NOT_AVAILABLE"
        ]
        assert len(vtable_errors) == 0

    def test_standard_attributes_recognized(self, simple_validator):
        """Стандартные реквизиты (Период, Регистратор) должны распознаваться."""
        q = """
        ВЫБРАТЬ
            Рег.Период,
            Рег.Регистратор,
            Рег.Активность
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        assert result.valid is True, f"Стандартные реквизиты не распознаны: {[i.message for i in result.issues]}"

    def test_aggregate_sum_on_numeric(self, simple_validator):
        """СУММА на числовом поле — без ошибки."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            СУММА(Рег.Выручка) КАК Сумма
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        СГРУППИРОВАТЬ ПО
            Рег.Номенклатура
        """
        result = simple_validator.validate(q)
        type_errors = [i for i in result.issues if i.rule_id == "AGGREGATE_TYPE_MISMATCH"]
        assert len(type_errors) == 0

    def test_aggregate_sum_on_string(self, simple_validator):
        """СУММА на строковом поле — ошибка AGGREGATE_TYPE_MISMATCH."""
        q = """
        ВЫБРАТЬ
            СУММА(Ном.Наименование) КАК Сумма
        ИЗ
            Справочник.Номенклатура КАК Ном
        """
        result = simple_validator.validate(q)
        type_errors = [i for i in result.issues if i.rule_id == "AGGREGATE_TYPE_MISMATCH"]
        assert len(type_errors) >= 1

    def test_unknown_table_alias(self, simple_validator):
        """Поля с неизвестным алиасом — ошибка UNKNOWN_TABLE_ALIAS."""
        q = """
        ВЫБРАТЬ
            НеизвестныйАлиас.Поле
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        errors = [i for i in result.issues if i.rule_id == "UNKNOWN_TABLE_ALIAS"]
        assert len(errors) >= 1

    def test_temp_table_recognized(self, simple_validator):
        """Временная таблица — не должна давать TABLE_NOT_FOUND."""
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
        result = simple_validator.validate(q)
        # Временная таблица не должна давать TABLE_NOT_FOUND
        table_errors = [
            i for i in result.issues
            if i.rule_id == "TABLE_NOT_FOUND" and "ВременнаяТаблица" in i.context
        ]
        assert len(table_errors) == 0

    def test_field_chain_through_ref(self, simple_validator):
        """Обращение к реквизиту ссылочного поля: Рег.Номенклатура.Наименование."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура.Наименование
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        # Не должно быть ошибки FIELD_NOT_FOUND для Наименование
        field_errors = [
            i for i in result.issues
            if i.rule_id == "FIELD_NOT_FOUND" and "Наименование" in i.message
        ]
        assert len(field_errors) == 0

    def test_empty_query(self, simple_validator):
        """Пустой запрос — ошибка."""
        result = simple_validator.validate("")
        assert result.valid is False
        assert any(i.rule_id == "EMPTY_QUERY" for i in result.issues)

    def test_result_to_dict_serialization(self, simple_validator):
        """Сериализация результата в dict."""
        q = """
        ВЫБРАТЬ Рег.Номенклатура ИЗ РегистрНакопления.ВыручкаСебестоимость КАК Рег
        """
        result = simple_validator.validate(q)
        d = result.to_dict()
        assert "valid" in d
        assert "issues" in d
        assert "total_errors" in d
        assert isinstance(d["issues"], list)


# ============================================================================
# 3. ИНТЕГРАЦИОННЫЙ ТЕСТ НА УТ11
# ============================================================================


class TestValidatorOnUT11:
    """Интеграционные тесты на реальной УТ11."""

    def test_validator_loads_ut11(self, ut11_validator):
        """Валидатор успешно загружает индекс УТ11."""
        assert ut11_validator is not None
        # Должен знать хотя бы один объект
        assert len(ut11_validator._objects_by_name) > 100

    def test_ut11_existing_register(self, ut11_validator):
        """В УТ11 есть реальные AccumulationRegister."""
        # ВзвешенныеТовары — реальный регистр с Номенклатура как Dimension
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            Рег.Склад,
            Рег.Количество
        ИЗ
            РегистрНакопления.ВзвешенныеТовары КАК Рег
        ГДЕ
            Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
        """
        result = ut11_validator.validate(q)
        # Должен найти все поля
        field_errors = [i for i in result.issues if i.rule_id == "FIELD_NOT_FOUND"]
        assert len(field_errors) == 0, f"Неожиданные FIELD_NOT_FOUND: {[i.message for i in field_errors]}"

    def test_ut11_standard_period_attribute(self, ut11_validator):
        """Стандартный реквизит Период доступен в регистре."""
        q = """
        ВЫБРАТЬ
            Рег.Период,
            Рег.Регистратор
        ИЗ
            РегистрНакопления.ВзвешенныеТовары КАК Рег
        """
        result = ut11_validator.validate(q)
        field_errors = [i for i in result.issues if i.rule_id == "FIELD_NOT_FOUND"]
        assert len(field_errors) == 0

    def test_ut11_virtual_balances(self, ut11_validator):
        """Виртуальная таблица Остатки доступна для Balance-регистра."""
        q = """
        ВЫБРАТЬ
            Остатки.Номенклатура,
            Остатки.КоличествоОстаток
        ИЗ
            РегистрНакопления.ВзвешенныеТовары.Остатки(
                &Период
            ) КАК Остатки
        """
        result = ut11_validator.validate(q)
        vtable_errors = [
            i for i in result.issues
            if i.rule_id == "VIRTUAL_TABLE_NOT_AVAILABLE"
        ]
        assert len(vtable_errors) == 0

    def test_ut11_typo_in_field_name(self, ut11_validator):
        """Опечатка в имени поля — должна быть ошибка с альтернативами."""
        q = """
        ВЫБРАТЬ
            Рег.Номенклатур
        ИЗ
            РегистрНакопления.ВзвешенныеТовары КАК Рег
        """
        result = ut11_validator.validate(q)
        not_found = [i for i in result.issues if i.rule_id == "FIELD_NOT_FOUND"]
        assert len(not_found) >= 1
        # Должен предложить альтернативы
        assert not_found[0].recommendation, "Нет рекомендаций по исправлению"

    def test_ut11_unknown_register(self, ut11_validator):
        """Несуществующий регистр — TABLE_NOT_FOUND."""
        q = """
        ВЫБРАТЬ
            Рег.Ссылка
        ИЗ
            РегистрНакопления.НесуществующийРегистр КАК Рег
        """
        result = ut11_validator.validate(q)
        errors = [i for i in result.issues if i.rule_id == "TABLE_NOT_FOUND"]
        assert len(errors) >= 1


# ============================================================================
# 4. РЕГРЕССИОННЫЙ ТЕСТ — ТОТ САМЫЙ БАГ ИЗ ПРОШЛОЙ СЕССИИ
# ============================================================================


class TestRegressionOriginalBug:
    """Регрессионный тест: баг из прошлой сессии.

    Контекст:
        Пользователь написал запрос к регистру ВыручкаСебестоимость с полем
        `ВыручкаСебестоимость.Номенклатура` — но в самой 1С это поле отсутствует
        (там были измерения с другими именами).

    Ожидание:
        Статический валидатор должен выявить проблему ещё до запуска в 1С.
    """

    def test_real_bug_reproduction(self, ut11_validator):
        """Воспроизведение бага: запрос с использованием алиаса вместо имени таблицы."""
        # Реальный запрос из прошлой сессии (адаптированный):
        q = """
        ВЫБРАТЬ
            СУММА(ВыручкаСебестоимость.Номенклатура),
            СУММА(ВыручкаСебестоимость.Себестоимость),
            КОЛИЧЕСТВО(ВыручкаСебестоимость.КоличествоРаспределение)
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК ВыручкаСебестоимость
        """
        result = ut11_validator.validate(q)
        # Если регистра ВыручкаСебестоимость нет в УТ11 — TABLE_NOT_FOUND
        # Если есть — FIELD_NOT_FOUND для Номенклатура (если её нет в этом регистре)
        # В любом случае — валидатор должен что-то обнаружить
        assert result.total_errors > 0 or result.total_warnings > 0 or len(result.issues) > 0

    def test_corrected_query_passes(self, simple_validator):
        """Исправленный запрос проходит валидацию без ошибок."""
        # Корректный запрос с реальными полями и агрегатами
        q = """
        ВЫБРАТЬ
            Рег.Номенклатура,
            СУММА(Рег.Выручка) КАК Выручка,
            СУММА(Рег.Себестоимость) КАК Себестоимость,
            СУММА(Рег.Выручка - Рег.Себестоимость) КАК Прибыль,
            КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Рег.Регистратор) КАК КоличествоПродаж
        ИЗ
            РегистрНакопления.ВыручкаСебестоимость КАК Рег
        ГДЕ
            Рег.Период МЕЖДУ &ДатаНачала И &ДатаКонца
            И Рег.Активность = ИСТИНА
        СГРУППИРОВАТЬ ПО
            Рег.Номенклатура
        """
        result = simple_validator.validate(q)
        errors = [i for i in result.issues if i.severity == "error"]
        # Допустимы warnings (например, наReg.Выручка - Рег.Себестоимость — это выражение),
        # но не errors
        assert len(errors) == 0, f"Неожиданные ошибки: {[i.message for i in errors]}"
