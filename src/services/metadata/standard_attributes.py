"""
standard_attributes.py — Платформенные стандартные реквизиты объектов 1С.

P1.5 (Шаг 1): эти реквизиты есть у всех объектов соответствующего типа, но они
НЕ описаны в XML метаданных явно — их добавляет платформа 1С при выполнении
запроса. Без них статический валидатор запросов будет выдавать false positives
на конструкциях вида `РегистрНакопления.XXX.Регистратор` или `Справочник.YYY.Ссылка`.

Источники:
- Документация 1С:Предприятие 8.3, раздел «Стандартные реквизиты»
- ИТС, стандарт «Разработка безопасных запросов»

Лицензия: MIT (содержимое — открытые знания о платформе 1С).
"""

from __future__ import annotations

from typing import Any

# ============================================================================
# СТАНДАРТНЫЕ РЕКВИЗИТЫ ПО ТИПУ ОБЪЕКТА
# ============================================================================

# Каждый стандартный реквизит: name, type (строкой как в 1С), synonym, kind
# kind: "Standard" — отдельная категория, не Attribute/Dimension/Resource

STANDARD_ATTRIBUTES: dict[str, list[dict[str, str]]] = {
    "Catalog": [
        {"name": "Ссылка", "type": "CatalogRef.<ThisCatalog>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Код", "type": "xs:string", "synonym": "Код", "kind": "Standard"},
        {"name": "Наименование", "type": "xs:string", "synonym": "Наименование", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Владелец", "type": "<OwnerRef>", "synonym": "Владелец", "kind": "Standard"},
        {"name": "Родитель", "type": "CatalogRef.<ThisCatalog>", "synonym": "Родитель", "kind": "Standard"},
        {"name": "Предопределенный", "type": "xs:boolean", "synonym": "Предопределенный", "kind": "Standard"},
    ],
    "Document": [
        {"name": "Ссылка", "type": "DocumentRef.<ThisDocument>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Номер", "type": "xs:string", "synonym": "Номер", "kind": "Standard"},
        {"name": "Дата", "type": "xs:dateTime", "synonym": "Дата", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Проведен", "type": "xs:boolean", "synonym": "Проведен", "kind": "Standard"},
    ],
    "DocumentJournal": [
        {"name": "Ссылка", "type": "DocumentRef.<Any>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Дата", "type": "xs:dateTime", "synonym": "Дата", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Проведен", "type": "xs:boolean", "synonym": "Проведен", "kind": "Standard"},
    ],
    "Enum": [
        {"name": "Ссылка", "type": "EnumRef.<ThisEnum>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Порядок", "type": "xs:decimal", "synonym": "Порядок", "kind": "Standard"},
        {"name": "Имя", "type": "xs:string", "synonym": "Имя", "kind": "Standard"},
        {"name": "Значение", "type": "xs:string", "synonym": "Значение", "kind": "Standard"},
    ],
    "ChartOfCharacteristicTypes": [
        {"name": "Ссылка", "type": "ChartOfCharacteristicTypesRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Код", "type": "xs:string", "synonym": "Код", "kind": "Standard"},
        {"name": "Наименование", "type": "xs:string", "synonym": "Наименование", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Владелец", "type": "<OwnerRef>", "synonym": "Владелец", "kind": "Standard"},
        {"name": "Родитель", "type": "ChartOfCharacteristicTypesRef.<This>", "synonym": "Родитель", "kind": "Standard"},
        {"name": "ТипЗначения", "type": "DefinedType.<Type>", "synonym": "Тип значения", "kind": "Standard"},
    ],
    "ChartOfAccounts": [
        {"name": "Ссылка", "type": "ChartOfAccountsRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Код", "type": "xs:string", "synonym": "Код счета", "kind": "Standard"},
        {"name": "Наименование", "type": "xs:string", "synonym": "Наименование", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Родитель", "type": "ChartOfAccountsRef.<This>", "synonym": "Родитель", "kind": "Standard"},
        {"name": "Вид", "type": "xs:string", "synonym": "Вид", "kind": "Standard"},
        {"name": "Забалансовый", "type": "xs:boolean", "synonym": "Забалансовый", "kind": "Standard"},
        {"name": "Количественный", "type": "xs:boolean", "synonym": "Количественный", "kind": "Standard"},
        {"name": "Валютный", "type": "xs:boolean", "synonym": "Валютный", "kind": "Standard"},
        {"name": "ТипСуммы", "type": "xs:string", "synonym": "Тип суммы", "kind": "Standard"},
    ],
    "ChartOfCalculationTypes": [
        {"name": "Ссылка", "type": "ChartOfCalculationTypesRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Код", "type": "xs:string", "synonym": "Код", "kind": "Standard"},
        {"name": "Наименование", "type": "xs:string", "synonym": "Наименование", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Периодичность", "type": "xs:string", "synonym": "Периодичность", "kind": "Standard"},
        {"name": "Базовый", "type": "xs:boolean", "synonym": "Базовый", "kind": "Standard"},
    ],
    "InformationRegister": [
        # Периодический (когда Periodicity != Nonperiodical)
        {"name": "Период", "type": "xs:dateTime", "synonym": "Период", "kind": "Standard", "conditional": "periodic"},
        # Подчинённый регистратору (когда RecordingType == SubordinateToRecorder)
        {"name": "Регистратор", "type": "DocumentRef.<Any>", "synonym": "Регистратор", "kind": "Standard", "conditional": "subordinate"},
        {"name": "НомерСтроки", "type": "xs:decimal", "synonym": "Номер строки", "kind": "Standard", "conditional": "subordinate"},
        # Активность — только для подчинённых регистратору
        {"name": "Активность", "type": "xs:boolean", "synonym": "Активность", "kind": "Standard", "conditional": "subordinate"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
    ],
    "AccumulationRegister": [
        {"name": "Период", "type": "xs:dateTime", "synonym": "Период", "kind": "Standard"},
        {"name": "Регистратор", "type": "DocumentRef.<Any>", "synonym": "Регистратор", "kind": "Standard"},
        {"name": "НомерСтроки", "type": "xs:decimal", "synonym": "Номер строки", "kind": "Standard"},
        {"name": "Активность", "type": "xs:boolean", "synonym": "Активность", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        # Специфичные для Balance / Turnovers / Other
        {"name": "ВидДвижения", "type": "xs:string", "synonym": "Вид движения", "kind": "Standard", "conditional": "balance"},
    ],
    "AccountingRegister": [
        {"name": "Период", "type": "xs:dateTime", "synonym": "Период", "kind": "Standard"},
        {"name": "Регистратор", "type": "DocumentRef.<Any>", "synonym": "Регистратор", "kind": "Standard"},
        {"name": "НомерСтроки", "type": "xs:decimal", "synonym": "Номер строки", "kind": "Standard"},
        {"name": "Активность", "type": "xs:boolean", "synonym": "Активность", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Счет", "type": "ChartOfAccountsRef.<Any>", "synonym": "Счет", "kind": "Standard"},
        {"name": "СчетДт", "type": "ChartOfAccountsRef.<Any>", "synonym": "Счет Дт", "kind": "Standard"},
        {"name": "СчетКт", "type": "ChartOfAccountsRef.<Any>", "synonym": "Счет Кт", "kind": "Standard"},
        {"name": "ВалютаДт", "type": "CatalogRef.<Валюты>", "synonym": "Валюта Дт", "kind": "Standard", "conditional": "currency"},
        {"name": "ВалютаКт", "type": "CatalogRef.<Валюты>", "synonym": "Валюта Кт", "kind": "Standard", "conditional": "currency"},
    ],
    "CalculationRegister": [
        {"name": "ПериодРегистрации", "type": "xs:dateTime", "synonym": "Период регистрации", "kind": "Standard"},
        {"name": "ПериодДействияНачало", "type": "xs:dateTime", "synonym": "Период действия начало", "kind": "Standard"},
        {"name": "ПериодДействияКонец", "type": "xs:dateTime", "synonym": "Период действия конец", "kind": "Standard"},
        {"name": "Регистратор", "type": "DocumentRef.<Any>", "synonym": "Регистратор", "kind": "Standard"},
        {"name": "НомерСтроки", "type": "xs:decimal", "synonym": "Номер строки", "kind": "Standard"},
        {"name": "Активность", "type": "xs:boolean", "synonym": "Активность", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "ВидРасчета", "type": "ChartOfCalculationTypesRef.<Any>", "synonym": "Вид расчета", "kind": "Standard"},
        {"name": "Счет", "type": "ChartOfAccountsRef.<Any>", "synonym": "Счет", "kind": "Standard"},
        {"name": "Отработано", "type": "xs:boolean", "synonym": "Отработано", "kind": "Standard"},
    ],
    "BusinessProcess": [
        {"name": "Ссылка", "type": "BusinessProcessRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Номер", "type": "xs:string", "synonym": "Номер", "kind": "Standard"},
        {"name": "Дата", "type": "xs:dateTime", "synonym": "Дата", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Проведен", "type": "xs:boolean", "synonym": "Проведен", "kind": "Standard"},
        {"name": "Начат", "type": "xs:boolean", "synonym": "Начат", "kind": "Standard"},
        {"name": "Завершен", "type": "xs:boolean", "synonym": "Завершен", "kind": "Standard"},
    ],
    "Task": [
        {"name": "Ссылка", "type": "TaskRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Номер", "type": "xs:string", "synonym": "Номер", "kind": "Standard"},
        {"name": "Дата", "type": "xs:dateTime", "synonym": "Дата", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Выполнена", "type": "xs:boolean", "synonym": "Выполнена", "kind": "Standard"},
        {"name": "БизнесПроцесс", "type": "BusinessProcessRef.<Any>", "synonym": "Бизнес-процесс", "kind": "Standard"},
        {"name": "ТочкаМаршрута", "type": "xs:string", "synonym": "Точка маршрута", "kind": "Standard"},
    ],
    "ExchangePlan": [
        {"name": "Ссылка", "type": "ExchangePlanRef.<This>", "synonym": "Ссылка", "kind": "Standard"},
        {"name": "Код", "type": "xs:string", "synonym": "Код", "kind": "Standard"},
        {"name": "Наименование", "type": "xs:string", "synonym": "Наименование", "kind": "Standard"},
        {"name": "ПометкаУдаления", "type": "xs:boolean", "synonym": "Пометка удаления", "kind": "Standard"},
        {"name": "Получен", "type": "xs:boolean", "synonym": "Получен", "kind": "Standard"},
        {"name": "Загружено", "type": "xs:dateTime", "synonym": "Загружено", "kind": "Standard"},
        {"name": "Выгружено", "type": "xs:dateTime", "synonym": "Выгружено", "kind": "Standard"},
        {"name": "НачалоВыгрузки", "type": "xs:dateTime", "synonym": "Начало выгрузки", "kind": "Standard"},
        {"name": "КонецВыгрузки", "type": "xs:dateTime", "synonym": "Конец выгрузки", "kind": "Standard"},
    ],
    "Constant": [
        # У константы нет ссылки/кода, но есть значение и период для периодических
        {"name": "Значение", "type": "<DefinedByProperty>", "synonym": "Значение", "kind": "Standard"},
        {"name": "Период", "type": "xs:dateTime", "synonym": "Период", "kind": "Standard", "conditional": "periodic"},
    ],
}

# ============================================================================
# ВИРТУАЛЬНЫЕ ТАБЛИЦЫ ПО ТИПУ РЕГИСТРА
# ============================================================================

# Доступность виртуальных таблиц зависит от типа регистра и его подтипа
VIRTUAL_TABLES: dict[str, dict[str, list[str]]] = {
    "AccumulationRegister": {
        # RegisterType: Balance / Turnovers / Other
        "Balance": ["Остатки", "Обороты", "ОстаткиИОбороты", "ДвиженияССубконто"],
        "Turnovers": ["Обороты", "ДвиженияССубконто"],
        "Other": ["ДвиженияССубконто"],
    },
    "InformationRegister": {
        # Periodicity: Nonperiodical / RecorderPeriod / DailyPeriod / MonthlyPeriod / QuarterlyPeriod / YearlyPeriod
        "_any_periodic": ["СрезПоследних"],
        "_any_subordinate": ["Движения", "ДвиженияССубконто"],
    },
    "AccountingRegister": {
        "_any": ["Движения", "Остатки", "Обороты", "ОстаткиИОбороты", "ДвиженияССубконто"],
    },
    "CalculationRegister": {
        "_any": ["Движения", "БазаНачисления", "ГрафаПерерасчета", "Перерасчеты"],
    },
}

# Алиасы виртуальных таблиц на английском (для запросов с английскими ключевыми словами)
VIRTUAL_TABLES_EN: dict[str, str] = {
    "Balances": "Остатки",
    "Turnovers": "Обороты",
    "BalancesAndTurnovers": "ОстаткиИОбороты",
    "ExtDimensions": "ДопРеквизиты",
    "SliceLast": "СрезПоследних",
    "RecordKey": "КлючЗаписи",
    "BaseCalculation": "БазаНачисления",
    "Recalculations": "Перерасчеты",
    "Actual": "Действительные",
}


def get_standard_attributes(obj_type: str, properties: dict | None = None) -> list[dict[str, str]]:
    """Возвращает список стандартных реквизитов для типа объекта.

    Args:
        obj_type: Тип объекта (Catalog, Document, AccumulationRegister, ...)
        properties: Свойства объекта (для условных реквизитов — periodic, subordinate, balance)

    Returns:
        Список реквизитов: [{name, type, synonym, kind}]
    """
    result: list[dict[str, str]] = []
    base_list = STANDARD_ATTRIBUTES.get(obj_type, [])
    for attr in base_list:
        conditional = attr.get("conditional")
        if conditional and properties:
            # Проверяем условие
            if not _check_conditional(conditional, obj_type, properties):
                continue
        result.append({k: v for k, v in attr.items() if k != "conditional"})
    return result


def _check_conditional(conditional: str, obj_type: str, properties: dict) -> bool:
    """Проверяет условие для условного стандартного реквизита."""
    if conditional == "periodic":
        if obj_type == "InformationRegister":
            periodicity = properties.get("Periodicity", "")
            return periodicity and periodicity != "Nonperiodical"
        if obj_type == "Constant":
            # У константы нет Periodicity в XML, используется для периодических через API
            return False
        return False
    if conditional == "subordinate":
        if obj_type == "InformationRegister":
            recording = properties.get("RecordingType", "")
            return recording == "SubordinateToRecorder"
        return False
    if conditional == "balance":
        if obj_type == "AccumulationRegister":
            return properties.get("RegisterType", "") == "Balance"
        return False
    if conditional == "currency":
        # Бухгалтерский регистр с включёнными валютами
        if obj_type == "AccountingRegister":
            return properties.get("UseCurrency", "false") == "true"
        return False
    return True


def get_virtual_tables(obj_type: str, properties: dict | None = None) -> list[str]:
    """Возвращает список доступных виртуальных таблиц для типа регистра.

    Args:
        obj_type: Тип регистра (AccumulationRegister, InformationRegister, ...)
        properties: Свойства (RegisterType, Periodicity, RecordingType)

    Returns:
        Список имён виртуальных таблиц (русских): ['Остатки', 'Обороты', ...]
    """
    spec = VIRTUAL_TABLES.get(obj_type)
    if not spec:
        return []

    result: list[str] = []
    if obj_type == "AccumulationRegister":
        register_type = properties.get("RegisterType", "Other") if properties else "Other"
        result = spec.get(register_type, spec.get("Other", []))[:]
    elif obj_type == "InformationRegister":
        # СрезПоследних доступен для периодических
        if properties:
            periodicity = properties.get("Periodicity", "Nonperiodical")
            if periodicity and periodicity != "Nonperiodical":
                result.extend(spec.get("_any_periodic", []))
            recording = properties.get("RecordingType", "")
            if recording == "SubordinateToRecorder":
                result.extend(spec.get("_any_subordinate", []))
    else:
        # AccountingRegister, CalculationRegister
        result = spec.get("_any", [])[:]

    return result


def is_virtual_table_name(name: str) -> str | None:
    """Проверяет, является ли имя виртуальной таблицей 1С.

    Returns:
        Русское имя виртуальной таблицы, если распознано, иначе None.
    """
    # Прямое совпадение
    known = {
        "Остатки", "Обороты", "ОстаткиИОбороты", "СрезПоследних",
        "Движения", "ДвиженияССубконто", "ДопРеквизиты", "КлючЗаписи",
        "БазаНачисления", "ГрафаПерерасчета", "Перерасчеты", "Действительные",
    }
    if name in known:
        return name
    # Английский алиас
    return VIRTUAL_TABLES_EN.get(name)


# ============================================================================
# СТАНДАРТНЫЕ ТАБЛИЧНЫЕ ЧАСТИ
# ============================================================================

# У некоторых объектов есть стандартные табличные части, добавляемые платформой
STANDARD_TABULAR_SECTIONS: dict[str, list[dict[str, str]]] = {
    "AccountingRegister": [
        {"name": "Субконто", "synonym": "Субконто"},
    ],
    "ChartOfAccounts": [
        {"name": "Субконто", "synonym": "Виды субконто"},
    ],
}


def get_standard_tabular_sections(obj_type: str) -> list[dict[str, str]]:
    """Возвращает список стандартных табличных частей для типа объекта."""
    return STANDARD_TABULAR_SECTIONS.get(obj_type, [])[:]
