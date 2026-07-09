"""
query_validator_static.py — Статический валидатор запросов 1С без живой базы.

P1.5 (Шаг 2): валидирует запрос 1С по метаданным из unified-metadata-index.json.
Не требует подключения к 1С:Предприятие — работает офлайн.

Проверяет:
1. Существование таблиц и полей
2. Доступность виртуальных таблиц по типу регистра
   (Остатки только для AccumulationRegister.Balance)
3. Типы в агрегатных функциях
   (СУММА(поле) — поле должно быть числом)
4. Совместимость JOIN (типы полей в условии ПО)
5. Корректность алиасов (поля вида Алиас.Имя ссылаются на существующую таблицу)
6. Параметры запроса (&Параметр) — не проверяем наличие, но фиксируем

Не проверяет (требуют живой базы):
- Предопределённые элементы (Справочник.Товары.Услуга)
- Динамические типы через DefinedType (если DefinedType не в индексе)
- Выполнение запроса и его производительность
- Семантику бизнес-логики

Лицензия: MIT.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.services.analyzers.query_parser import (
    ParsedBatch,
    ParsedQuery,
    QueryField,
    QueryParser,
    QueryTable,
)
from src.services.metadata.standard_attributes import (
    get_standard_attributes,
    get_virtual_tables,
    is_virtual_table_name,
)
from src.services.metadata.type_resolver import (
    ResolvedType,
    is_type_compatible_with_numeric,
    parse_type_string,
    resolve_defined_type,
    resolve_types,
)


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class ValidationIssue:
    """Одна проблема, найденная валидатором."""

    rule_id: str
    severity: str  # 'error' | 'warning' | 'info'
    message: str
    line: int = 0
    context: str = ""  # Имя таблицы/поля, к которому относится
    recommendation: str = ""


@dataclass
class ValidationResult:
    """Результат валидации запроса."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    total_errors: int = 0
    total_warnings: int = 0
    parsed_queries: int = 0
    parsed_tables: int = 0
    parsed_fields: int = 0
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "parsed_queries": self.parsed_queries,
            "parsed_tables": self.parsed_tables,
            "parsed_fields": self.parsed_fields,
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "severity": i.severity,
                    "message": i.message,
                    "line": i.line,
                    "context": i.context,
                    "recommendation": i.recommendation,
                }
                for i in self.issues
            ],
        }


# ============================================================================
# ВАЛИДАТОР
# ============================================================================


class StaticQueryValidator:
    """Статический валидатор запросов 1С по метаданным."""

    def __init__(self, metadata_index: dict[str, Any]):
        """Инициализация валидатора с индексом метаданных.

        Args:
            metadata_index: Содержимое unified-metadata-index.json
        """
        self.metadata = metadata_index
        self.parser = QueryParser()

        # Строим быстрый индекс объектов по полному имени
        # 'РегистрНакопления.ВыручкаСебестоимость' → объект
        self._objects_by_full_name: dict[str, dict[str, Any]] = {}
        self._objects_by_name: dict[str, dict[str, Any]] = {}
        self._defined_types: dict[str, list[str]] = {}

        self._build_indexes()

    @classmethod
    def from_config_dir(cls, config_dir: Path | str) -> "StaticQueryValidator | None":
        """Создаёт валидатор из директории конфигурации.

        Загружает derived/configs/<name>/unified-metadata-index.json.

        Args:
            config_dir: Путь к распакованной конфигурации 1С

        Returns:
            StaticQueryValidator или None, если индекс не найден.
        """
        config_dir = Path(config_dir)
        # Возможные расположения индекса
        candidates = [
            config_dir / "unified-metadata-index.json",
            config_dir / "derived" / "configs" / config_dir.name / "unified-metadata-index.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                with open(candidate, encoding="utf-8") as f:
                    return cls(json.load(f))
        return None

    @classmethod
    def from_metadata_file(cls, metadata_path: Path | str) -> "StaticQueryValidator":
        """Создаёт валидатор из файла unified-metadata-index.json."""
        with open(metadata_path, encoding="utf-8") as f:
            return cls(json.load(f))

    def _build_indexes(self) -> None:
        """Строит внутренние индексы для быстрого поиска."""
        # Объекты по типу
        objects_by_type: dict[str, list[dict[str, Any]]] = self.metadata.get("objects", {})

        # Mapping для русского → английского типа
        type_ru_to_en = {
            "Catalogs": "Catalog",
            "Documents": "Document",
            "DocumentJournals": "DocumentJournal",
            "Enums": "Enum",
            "InformationRegisters": "InformationRegister",
            "AccumulationRegisters": "AccumulationRegister",
            "AccountingRegisters": "AccountingRegister",
            "CalculationRegisters": "CalculationRegister",
            "ChartsOfAccounts": "ChartOfAccounts",
            "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
            "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
            "ExchangePlans": "ExchangePlan",
            "BusinessProcesses": "BusinessProcess",
            "Tasks": "Task",
            "Constants": "Constant",
            "DataProcessors": "DataProcessor",
            "Reports": "Report",
        }

        for type_plural, objs in objects_by_type.items():
            obj_type = type_ru_to_en.get(type_plural, type_plural)
            for obj in objs:
                obj_dict = dict(obj)
                obj_dict["type"] = obj_type
                full_name = f"{type_ru_to_en.get(type_plural, type_plural)}.{obj_dict.get('name', '')}"
                # Для поиска используем и русское, и английское имя типа
                self._objects_by_full_name[full_name] = obj_dict
                # Также русское имя
                ru_type_map = {v: k for k, v in type_ru_to_en.items()}
                ru_plural = ru_type_map.get(obj_type)
                if ru_plural:
                    ru_full_name = self._en_to_ru_type(obj_type) + "." + obj_dict.get("name", "")
                    self._objects_by_full_name[ru_full_name] = obj_dict
                self._objects_by_name[obj_dict.get("name", "")] = obj_dict

        # DefinedTypes для раскрытия
        defined_types_list = objects_by_type.get("DefinedTypes", [])
        for dt in defined_types_list:
            name = dt.get("name", "")
            types = []
            # У DefinedType могут быть типы в child_objects.attributes или в properties
            children = dt.get("child_objects", {})
            for attr in children.get("attributes", []):
                types.extend(attr.get("types", []))
            if not types:
                # Пробуем из properties
                props = dt.get("properties", {})
                type_str = props.get("Type", "")
                if type_str:
                    types.append(type_str)
            if name and types:
                self._defined_types[name] = types

    def _en_to_ru_type(self, en_type: str) -> str:
        """Преобразует английский тип в русский."""
        mapping = {
            "Catalog": "Справочник",
            "Document": "Документ",
            "DocumentJournal": "ЖурналДокументов",
            "Enum": "Перечисление",
            "InformationRegister": "РегистрСведений",
            "AccumulationRegister": "РегистрНакопления",
            "AccountingRegister": "РегистрБухгалтерии",
            "CalculationRegister": "РегистрРасчета",
            "ChartOfAccounts": "ПланСчетов",
            "ChartOfCharacteristicTypes": "ПланВидовХарактеристик",
            "ChartOfCalculationTypes": "ПланВидовРасчета",
            "ExchangePlan": "ПланОбмена",
            "BusinessProcess": "БизнесПроцесс",
            "Task": "Задача",
            "Constant": "Константа",
            "DataProcessor": "Обработка",
            "Report": "Отчет",
        }
        return mapping.get(en_type, en_type)

    def validate(self, query_text: str) -> ValidationResult:
        """Валидирует текст запроса 1С.

        Args:
            query_text: Текст запроса 1С (один или несколько SELECT)

        Returns:
            ValidationResult с найденными проблемами.
        """
        if not query_text or not query_text.strip():
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(
                    rule_id="EMPTY_QUERY",
                    severity="error",
                    message="Пустой запрос",
                    recommendation="Укажите текст запроса для проверки",
                )],
                total_errors=1,
            )

        # Парсим запрос
        try:
            batch = self.parser.parse(query_text)
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(
                    rule_id="PARSE_ERROR",
                    severity="error",
                    message=f"Ошибка парсинга запроса: {e}",
                    recommendation="Проверьте синтаксис запроса",
                )],
                total_errors=1,
                raw_text=query_text,
            )

        result = ValidationResult(
            valid=True,
            parsed_queries=len(batch.queries),
            raw_text=query_text,
        )

        # Таблицы и поля для статистики
        all_tables: list[QueryTable] = []
        all_fields: list[QueryField] = []

        # Валидируем каждый запрос в пакете
        for i, query in enumerate(batch.queries):
            self._validate_query(query, batch, i, result)
            all_tables.extend(query.tables)
            all_fields.extend(query.select_fields)
            all_fields.extend(query.where_fields)
            all_fields.extend(query.group_by_fields)
            all_fields.extend(query.order_by_fields)

        result.parsed_tables = len(all_tables)
        result.parsed_fields = len(all_fields)

        # Подсчитываем ошибки
        result.total_errors = sum(1 for i in result.issues if i.severity == "error")
        result.total_warnings = sum(1 for i in result.issues if i.severity == "warning")
        result.valid = result.total_errors == 0

        return result

    def _validate_query(
        self,
        query: ParsedQuery,
        batch: ParsedBatch,
        query_index: int,
        result: ValidationResult,
    ) -> None:
        """Валидирует один SELECT-запрос."""
        # 1. Проверяем существование таблиц и их структуру
        table_resolved: dict[str, dict[str, Any]] = {}  # алиас → объект метаданных
        for table in query.tables:
            obj = self._resolve_table(table, batch, result, query_index)
            if obj:
                alias = table.alias or table.object_name
                table_resolved[alias] = obj
                # Также сохраняем по full_name и по object_name
                table_resolved[table.object_name] = obj

        # 2. Проверяем виртуальные таблицы
        for table in query.tables:
            if table.virtual_table:
                self._check_virtual_table(table, result, query_index)

        # 3. Проверяем поля SELECT
        for field in query.select_fields:
            self._check_field(field, table_resolved, batch, result, query_index)

        # 4. Проверяем поля WHERE
        for field in query.where_fields:
            self._check_field(field, table_resolved, batch, result, query_index)

        # 5. Проверяем поля GROUP BY
        for field in query.group_by_fields:
            self._check_field(field, table_resolved, batch, result, query_index)

        # 6. Проверяем поля ORDER BY
        for field in query.order_by_fields:
            self._check_field(field, table_resolved, batch, result, query_index)

        # 7. Проверяем агрегатные функции
        for field in query.select_fields:
            if field.aggregate:
                self._check_aggregate(field, table_resolved, batch, result, query_index)

    def _resolve_table(
        self,
        table: QueryTable,
        batch: ParsedBatch,
        result: ValidationResult,
        query_index: int,
    ) -> dict[str, Any] | None:
        """Находит объект метаданных для таблицы запроса."""
        # 1. Проверяем, не временная ли это таблица
        temp_def = batch.get_temp_table_definition(table.full_name)
        if temp_def or self._is_temp_table(table.full_name, batch):
            # Временная таблица — не проверяем поля, она определена в пакете
            return {
                "type": "TempTable",
                "name": table.full_name,
                "child_objects": {
                    "attributes": [],
                    "dimensions": [],
                    "resources": [],
                    "attributes_only": [],
                    "standard_attributes": [],
                },
                "properties": {},
                "_is_temp": True,
            }

        # 2. Ищем в индексе по полному имени
        obj = self._objects_by_full_name.get(table.full_name)
        if obj:
            return obj

        # 3. Ищем по имени объекта (без типа)
        if table.object_name:
            obj = self._objects_by_name.get(table.object_name)
            if obj:
                # Проверяем совпадение типа
                if table.object_type and obj.get("type") and obj["type"].lower() != table.object_type.lower():
                    # Тип не совпадает — возможно, указан неверный
                    ru_obj_type = self._en_to_ru_type(obj.get("type", ""))
                    if table.object_type.lower() != ru_obj_type.lower():
                        result.issues.append(ValidationIssue(
                            rule_id="TABLE_TYPE_MISMATCH",
                            severity="error",
                            message=f"Тип объекта '{table.object_type}' не соответствует фактическому типу '{obj.get('type')}' / '{ru_obj_type}' для объекта '{table.object_name}'",
                            context=table.full_name,
                            recommendation=f"Используйте '{obj.get('type')}.{table.object_name}' или '{ru_obj_type}.{table.object_name}'",
                        ))
                        return None
                return obj

        # 4. Таблица не найдена
        result.issues.append(ValidationIssue(
            rule_id="TABLE_NOT_FOUND",
            severity="error",
            message=f"Таблица '{table.full_name}' не найдена в метаданных конфигурации",
            context=table.full_name,
            recommendation="Проверьте корректность имени таблицы и типа объекта",
        ))
        return None

    def _is_temp_table(self, name: str, batch: ParsedBatch) -> bool:
        """Проверяет, является ли имя временной таблицей пакета."""
        for q in batch.queries:
            if q.into_temp_table == name:
                return True
        return False

    def _check_virtual_table(
        self,
        table: QueryTable,
        result: ValidationResult,
        query_index: int,
    ) -> None:
        """Проверяет доступность виртуальной таблицы для типа регистра."""
        # Находим объект
        obj = self._objects_by_name.get(table.object_name)
        if not obj:
            return  # Уже сообщили об ошибке в _resolve_table

        obj_type = obj.get("type", "")
        properties = obj.get("properties", {})

        # Получаем доступные виртуальные таблицы
        available = get_virtual_tables(obj_type, properties)

        # Если для этого типа нет виртуальных таблиц вообще
        if not available:
            result.issues.append(ValidationIssue(
                rule_id="VIRTUAL_TABLE_NOT_AVAILABLE",
                severity="error",
                message=f"Виртуальные таблицы недоступны для типа '{obj_type}' (объект '{table.object_name}')",
                context=table.full_name,
                recommendation=f"Тип '{obj_type}' не поддерживает виртуальные таблицы",
            ))
            return

        # Приводим имя виртуальной таблицы к нормализованному виду
        vtable_name = is_virtual_table_name(table.virtual_table)
        if not vtable_name:
            result.issues.append(ValidationIssue(
                rule_id="UNKNOWN_VIRTUAL_TABLE",
                severity="error",
                message=f"Неизвестная виртуальная таблица '{table.virtual_table}'",
                context=table.full_name,
                recommendation=f"Доступные: {', '.join(available)}",
            ))
            return

        if vtable_name not in available:
            result.issues.append(ValidationIssue(
                rule_id="VIRTUAL_TABLE_NOT_AVAILABLE",
                severity="error",
                message=f"Виртуальная таблица '{vtable_name}' недоступна для регистра '{table.object_name}' (тип {obj_type})",
                context=table.full_name,
                recommendation=f"Доступные виртуальные таблицы: {', '.join(available)}",
            ))

    def _check_field(
        self,
        field: QueryField,
        table_resolved: dict[str, dict[str, Any]],
        batch: ParsedBatch,
        result: ValidationResult,
        query_index: int,
    ) -> None:
        """Проверяет существование поля в метаданных."""
        if not field.raw or field.raw == "*":
            return

        # Если поле содержит пробел или операторы — это выражение, пропускаем
        # (проверка выражений не входит в P1.5)
        if " " in field.raw or any(op in field.raw for op in [" + ", " - ", " * ", " / ", "+", "-"]):
            # Но только если это похоже на выражение (есть ссылка на поле)
            return

        # Если поле без точки — это может быть алиас поля, константа или параметр
        if "." not in field.raw:
            return  # Не можем проверить без алиаса таблицы

        # Разбираем Алиас.ИмяПоля (или Алиас.Имя.Имя для обращений к реквизитам ссылок)
        parts = field.raw.split(".")
        if len(parts) < 2:
            return

        table_alias = parts[0]
        field_chain = parts[1:]

        # Находим таблицу по алиасу
        table_obj = table_resolved.get(table_alias)
        if not table_obj:
            # Возможно, это ссылка на тип объекта (Справочник.Имя.Реквизит)
            # — это не валидная конструкция в SELECT, должно быть через алиас
            if table_alias in self._objects_by_name:
                result.issues.append(ValidationIssue(
                    rule_id="FIELD_WITHOUT_ALIAS",
                    severity="warning",
                    message=f"Поле '{field.raw}' использует имя объекта вместо алиаса таблицы",
                    context=field.raw,
                    recommendation=f"Используйте алиас таблицы: 'АЛИАС.{field_chain[0]}'",
                ))
            else:
                result.issues.append(ValidationIssue(
                    rule_id="UNKNOWN_TABLE_ALIAS",
                    severity="error",
                    message=f"Неизвестный алиас таблицы '{table_alias}' в поле '{field.raw}'",
                    context=field.raw,
                    recommendation="Убедитесь, что таблица объявлена в FROM/JOIN с этим алиасом",
                ))
            return

        if table_obj.get("_is_temp"):
            return  # Временная таблица — не проверяем

        # Ищем поле в объекте
        # Поддерживаем chain: Алиас.Номенклатура.Наименование
        # — Номенклатура это реквизит-ссылка, Наименование — реквизит справочника
        current_obj = table_obj
        for i, field_name in enumerate(field_chain):
            found_attr = self._find_attribute_in_object(current_obj, field_name)
            if not found_attr:
                result.issues.append(ValidationIssue(
                    rule_id="FIELD_NOT_FOUND",
                    severity="error",
                    message=f"Поле '{field_name}' не найдено в объекте '{current_obj.get('name', '')}'",
                    context=field.raw,
                    recommendation=self._suggest_field_alternatives(current_obj, field_name),
                ))
                return

            # Если это последняя часть chain — всё ок
            if i == len(field_chain) - 1:
                break

            # Если есть продолжение chain — нужно раскрыть тип текущего поля
            resolved_type_dict = found_attr.get("resolved_type", {})
            if resolved_type_dict.get("kind") == "ref":
                ref_name = resolved_type_dict.get("ref_name", "")
                ref_obj = self._objects_by_name.get(ref_name)
                if ref_obj:
                    current_obj = ref_obj
                else:
                    # Не можем раскрыть — пропускаем проверку следующих частей
                    break
            else:
                # Не ссылочный тип — chain не имеет смысла
                result.issues.append(ValidationIssue(
                    rule_id="FIELD_CHAIN_INVALID",
                    severity="warning",
                    message=f"Поле '{field_name}' в '{field.raw}' не ссылочное — обращение к его свойствам недопустимо",
                    context=field.raw,
                    recommendation="Уберите цепочку после нессылочного поля",
                ))
                return

    def _find_attribute_in_object(
        self, obj: dict[str, Any], field_name: str
    ) -> dict[str, Any] | None:
        """Ищет атрибут в объекте метаданных по имени."""
        children = obj.get("child_objects", {})

        # P1.5: для индексов, сгенерированных старым парсером, добавляем стандартные
        # реквизиты на лету (если их нет в объекте).
        self._ensure_standard_attributes(obj)

        # Поиск по всем типам атрибутов
        for key in (
            "dimensions",
            "resources",
            "attributes_only",
            "standard_attributes",
            "attributes",  # fallback на общий список
        ):
            attrs = children.get(key, [])
            for attr in attrs:
                if attr.get("name", "").lower() == field_name.lower():
                    return attr

        # Поиск в табличных частях (для обращения ИмяТЧ.ИмяРеквизита)
        # — это отдельный случай, пока не поддерживаем

        # Поиск в enum_values (для перечислений)
        for enum_value in children.get("enum_values", []):
            if enum_value.get("name", "").lower() == field_name.lower():
                return enum_value

        return None

    def _ensure_standard_attributes(self, obj: dict[str, Any]) -> None:
        """P1.5: добавляет стандартные реквизиты в объект, если их ещё нет.

        Это нужно для индексов, сгенерированных ДО доработки парсера.
        Новые индексы уже содержат standard_attributes после парсинга.
        """
        # Проверяем флаг — что уже обработали
        if obj.get("_std_attrs_ensured"):
            return

        children = obj.get("child_objects", {})
        obj_type = obj.get("type", "")
        properties = obj.get("properties", {})

        if not obj_type:
            obj["_std_attrs_ensured"] = True
            return

        # Получаем стандартные реквизиты для типа
        try:
            std_attrs = get_standard_attributes(obj_type, properties)
        except Exception:
            std_attrs = []

        if not std_attrs:
            obj["_std_attrs_ensured"] = True
            return

        # Добавляем в общий список attributes (если их там ещё нет)
        existing_names = {a.get("name") for a in children.get("attributes", [])}
        for attr in std_attrs:
            if attr.get("name") not in existing_names:
                children.setdefault("attributes", []).append(attr)

        # Также в standard_attributes (если пусто)
        if not children.get("standard_attributes"):
            children["standard_attributes"] = list(std_attrs)

        obj["_std_attrs_ensured"] = True

    def _suggest_field_alternatives(
        self, obj: dict[str, Any], field_name: str
    ) -> str:
        """Предлагает похожие имена полей."""
        children = obj.get("child_objects", {})
        all_names: list[str] = []
        for key in (
            "dimensions",
            "resources",
            "attributes_only",
            "standard_attributes",
            "attributes",
        ):
            for attr in children.get(key, []):
                name = attr.get("name", "")
                if name:
                    all_names.append(name)

        # Простой fuzzy match — находим поля, содержащие подстроку
        field_lower = field_name.lower()
        similar = [n for n in all_names if field_lower in n.lower() or n.lower() in field_lower]

        if similar:
            return f"Возможно, вы имели в виду: {', '.join(similar[:5])}. Доступные поля: {', '.join(all_names[:10])}..."
        return f"Доступные поля: {', '.join(all_names[:15])}{'...' if len(all_names) > 15 else ''}"

    def _check_aggregate(
        self,
        field: QueryField,
        table_resolved: dict[str, dict[str, Any]],
        batch: ParsedBatch,
        result: ValidationResult,
        query_index: int,
    ) -> None:
        """Проверяет корректность агрегатной функции."""
        if not field.aggregate_arg or field.aggregate_arg == "*":
            return

        # СУММА и СРЕДНЕЕ — аргумент должен быть числом
        if field.aggregate in ("SUM", "AVG"):
            field_type = self._resolve_field_type(field.aggregate_arg, table_resolved)
            if field_type and not is_type_compatible_with_numeric(field_type, self._defined_types):
                result.issues.append(ValidationIssue(
                    rule_id="AGGREGATE_TYPE_MISMATCH",
                    severity="error",
                    message=f"Агрегатная функция {field.aggregate} ожидает числовой аргумент, но поле '{field.aggregate_arg}' имеет тип '{field_type.description}'",
                    context=field.raw,
                    recommendation="Используйте числовое поле или приведите тип",
                ))

    def _resolve_field_type(
        self, field_ref: str, table_resolved: dict[str, dict[str, Any]]
    ) -> ResolvedType | None:
        """Определяет тип поля по ссылке Алиас.Имя."""
        if "." not in field_ref:
            return None

        parts = field_ref.split(".")
        table_alias = parts[0]
        field_chain = parts[1:]

        table_obj = table_resolved.get(table_alias)
        if not table_obj:
            return None

        current_obj = table_obj
        for i, field_name in enumerate(field_chain):
            attr = self._find_attribute_in_object(current_obj, field_name)
            if not attr:
                return None

            if i == len(field_chain) - 1:
                # Последняя часть chain — возвращаем её тип
                resolved_type_dict = attr.get("resolved_type")
                if resolved_type_dict:
                    return self._dict_to_resolved_type(resolved_type_dict)
                # Fallback: парсим types напрямую
                types = attr.get("types", [])
                if types:
                    return resolve_types(types)
                return None

            # Раскрываем chain
            resolved_type_dict = attr.get("resolved_type", {})
            if resolved_type_dict.get("kind") == "ref":
                ref_name = resolved_type_dict.get("ref_name", "")
                ref_obj = self._objects_by_name.get(ref_name)
                if ref_obj:
                    current_obj = ref_obj
                else:
                    return None
            else:
                return None

        return None

    def _dict_to_resolved_type(self, d: dict[str, Any]) -> ResolvedType:
        """Преобразует dict обратно в ResolvedType."""
        rt = ResolvedType(
            kind=d.get("kind", "unknown"),
            description=d.get("description", ""),
        )
        if rt.kind == "ref":
            rt.ref_kind = d.get("ref_kind", "")
            rt.ref_name = d.get("ref_name", "")
        elif rt.kind == "primitive":
            rt.primitive = d.get("primitive", "")
            rt.string_length = d.get("string_length", 0)
            rt.precision = d.get("precision", 0)
            rt.scale = d.get("scale", 0)
        elif rt.kind == "composite":
            rt.variants = [self._dict_to_resolved_type(v) for v in d.get("variants", [])]
        return rt
