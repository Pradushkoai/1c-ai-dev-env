"""
type_resolver.py — Ресолвинг типов полей 1С в структурированное представление.

P1.5 (Шаг 1): преобразует строки типов из XML метаданных 1С вида
`cfg:CatalogRef.Номенклатура` или `cfg:DefinedType.Товары` в структурированные
объекты, понятные статическому валидатору запросов.

Формат типов 1С в XML:
- cfg:CatalogRef.<Name>          — ссылка на справочник
- cfg:DocumentRef.<Name>         — ссылка на документ
- cfg:EnumRef.<Name>             — ссылка на перечисление
- cfg:ChartOfCharacteristicTypesRef.<Name>
- cfg:ChartOfAccountsRef.<Name>
- cfg:ChartOfCalculationTypesRef.<Name>
- cfg:BusinessProcessRef.<Name>
- cfg:TaskRef.<Name>
- cfg:ExchangePlanRef.<Name>
- cfg:DefinedType.<Name>         — определённый тип (нужно раскрытие)
- xs:string                      — строка
- xs:decimal                     — число
- xs:boolean                     — булево
- xs:dateTime                    — дата/время
- xs:date                        — дата
- xs:time                        — время
- xs:hexBinary                   — двоичные данные
- Null                           — NULL

Составные типы: несколько <Type>...</Type> элементов в одном <Type> —
означает, что поле может содержать значение любого из перечисленных типов.

Лицензия: MIT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ============================================================================
# DATA CLASS
# ============================================================================


@dataclass
class ResolvedType:
    """Ресолвнутый тип поля 1С."""

    kind: str  # 'ref' | 'primitive' | 'defined_type' | 'composite' | 'unknown'
    # Для ref:
    ref_kind: str = ""  # 'Catalog' | 'Document' | 'Enum' | 'ChartOfCharacteristicTypes' | ...
    ref_name: str = ""  # Имя объекта (например, 'Номенклатура')
    # Для primitive:
    primitive: str = ""  # 'string' | 'decimal' | 'boolean' | 'dateTime' | ...
    string_length: int = 0  # Для string
    precision: int = 0  # Для decimal (общая длина)
    scale: int = 0  # Для decimal (знаков после запятой)
    # Для composite:
    variants: list["ResolvedType"] = field(default_factory=list)
    # Человекочитаемое описание
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict."""
        d: dict[str, Any] = {"kind": self.kind, "description": self.description}
        if self.kind == "ref":
            d["ref_kind"] = self.ref_kind
            d["ref_name"] = self.ref_name
        elif self.kind == "primitive":
            d["primitive"] = self.primitive
            if self.string_length:
                d["string_length"] = self.string_length
            if self.precision:
                d["precision"] = self.precision
                d["scale"] = self.scale
        elif self.kind == "composite":
            d["variants"] = [v.to_dict() for v in self.variants]
        return d

    def is_numeric(self) -> bool:
        """Числовый ли тип."""
        if self.kind == "primitive":
            return self.primitive == "decimal"
        if self.kind == "composite":
            return any(v.is_numeric() for v in self.variants)
        return False

    def is_string(self) -> bool:
        """Строковый ли тип."""
        if self.kind == "primitive":
            return self.primitive == "string"
        if self.kind == "composite":
            return any(v.is_string() for v in self.variants)
        return False

    def is_boolean(self) -> bool:
        """Булев ли тип."""
        if self.kind == "primitive":
            return self.primitive == "boolean"
        if self.kind == "composite":
            return any(v.is_boolean() for v in self.variants)
        return False

    def is_date(self) -> bool:
        """Дата/время ли тип."""
        if self.kind == "primitive":
            return self.primitive in ("dateTime", "date", "time")
        if self.kind == "composite":
            return any(v.is_date() for v in self.variants)
        return False

    def is_ref(self) -> bool:
        """Ссылочный ли тип."""
        return self.kind == "ref"

    def is_composite(self) -> bool:
        """Составной ли тип."""
        return self.kind == "composite"


# ============================================================================
# ПАРСИНГ ТИПОВ
# ============================================================================

# Соответствие типов 1С → ref_kind
REF_TYPE_MAP: dict[str, str] = {
    "CatalogRef": "Catalog",
    "DocumentRef": "Document",
    "EnumRef": "Enum",
    "ChartOfCharacteristicTypesRef": "ChartOfCharacteristicTypes",
    "ChartOfAccountsRef": "ChartOfAccounts",
    "ChartOfCalculationTypesRef": "ChartOfCalculationTypes",
    "BusinessProcessRef": "BusinessProcess",
    "TaskRef": "Task",
    "ExchangePlanRef": "ExchangePlan",
}

# Примитивные типы
PRIMITIVE_MAP: dict[str, str] = {
    "xs:string": "string",
    "xs:decimal": "decimal",
    "xs:boolean": "boolean",
    "xs:dateTime": "dateTime",
    "xs:date": "date",
    "xs:time": "time",
    "xs:hexBinary": "hexBinary",
    "xs:integer": "decimal",  # integer — частный случай decimal
    "xs:int": "decimal",
    "xs:long": "decimal",
    "xs:double": "decimal",
    "xs:float": "decimal",
    "Null": "null",
}

# Зарезервированные слова 1С, которые используются в специальных типах
SPECIAL_TYPES: dict[str, str] = {
    "Null": "null",
    "Строка": "string",
    "Число": "decimal",
    "Булево": "boolean",
    "Дата": "dateTime",
}


def parse_type_string(type_str: str) -> ResolvedType:
    """Парсит строку типа 1С из XML метаданных.

    Args:
        type_str: Строка типа (например, 'cfg:CatalogRef.Номенклатура' или 'xs:string')

    Returns:
        ResolvedType с распознанной структурой.
    """
    type_str = type_str.strip()

    # Примитивные типы
    if type_str in PRIMITIVE_MAP:
        return ResolvedType(
            kind="primitive",
            primitive=PRIMITIVE_MAP[type_str],
            description=_describe_primitive(PRIMITIVE_MAP[type_str]),
        )

    # Специальные (русские имена)
    if type_str in SPECIAL_TYPES:
        return ResolvedType(
            kind="primitive",
            primitive=SPECIAL_TYPES[type_str],
            description=_describe_primitive(SPECIAL_TYPES[type_str]),
        )

    # Ссылочные типы: cfg:CatalogRef.<Name>
    for cfg_prefix, ref_kind in REF_TYPE_MAP.items():
        # Поддержка как 'cfg:CatalogRef.Имя' так и просто 'CatalogRef.Имя'
        patterns = [
            rf"^{cfg_prefix}\.([^.\s]+)$",
            rf"^cfg:{cfg_prefix}\.([^.\s]+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, type_str)
            if match:
                ref_name = match.group(1)
                return ResolvedType(
                    kind="ref",
                    ref_kind=ref_kind,
                    ref_name=ref_name,
                    description=f"{ref_kind}Ref.{ref_name}",
                )

    # DefinedType: cfg:DefinedType.<Name>
    match = re.match(r"^(?:cfg:)?DefinedType\.([^.\s]+)$", type_str)
    if match:
        return ResolvedType(
            kind="defined_type",
            ref_name=match.group(1),
            description=f"DefinedType.{match.group(1)}",
        )

    # Неизвестный тип
    return ResolvedType(
        kind="unknown",
        description=type_str,
    )


def resolve_types(type_strings: list[str]) -> ResolvedType:
    """Разрешает список типов 1С (для составных полей).

    Args:
        type_strings: Список строк типов (из <Type><Type>cfg:...<Type>xs:decimal</Type></Type>)

    Returns:
        ResolvedType. Если список пустой — unknown.
        Если один элемент — соответствующий тип.
        Если несколько — composite с вариантами.
    """
    if not type_strings:
        return ResolvedType(kind="unknown", description="не задан")

    resolved_variants = [parse_type_string(ts) for ts in type_strings]

    if len(resolved_variants) == 1:
        return resolved_variants[0]

    # Составной тип
    descriptions = ", ".join(v.description for v in resolved_variants)
    return ResolvedType(
        kind="composite",
        variants=resolved_variants,
        description=descriptions,
    )


def _describe_primitive(primitive: str) -> str:
    """Человекочитаемое описание примитивного типа."""
    descriptions = {
        "string": "Строка",
        "decimal": "Число",
        "boolean": "Булево",
        "dateTime": "Дата/Время",
        "date": "Дата",
        "time": "Время",
        "hexBinary": "Двоичные данные",
        "null": "Null",
    }
    return descriptions.get(primitive, primitive)


# ============================================================================
# ПОЛУЧЕНИЕ ИЗ METADATA INDEX
# ============================================================================


def resolve_field_types_from_metadata(field_types: list[str]) -> ResolvedType:
    """Удобная обёртка для вызова из metadata_index.

    Args:
        field_types: Список типов из unified-metadata-index.json
                     (атрибут .types: ['cfg:CatalogRef.Номенклатура', 'xs:decimal'])

    Returns:
        ResolvedType — распознанный тип поля.
    """
    return resolve_types(field_types)


def resolve_defined_type(
    defined_type_name: str, defined_types_index: dict[str, list[str]]
) -> ResolvedType:
    """Раскрывает DefinedType через индекс всех DefinedType в конфигурации.

    Args:
        defined_type_name: Имя DefinedType (например, 'Товары')
        defined_types_index: {name: [type_strings]} — словарь из metadata_index

    Returns:
        ResolvedType — раскрытый тип. Если не найден — DefinedType без раскрытия.
    """
    type_strings = defined_types_index.get(defined_type_name)
    if not type_strings:
        return ResolvedType(
            kind="defined_type",
            ref_name=defined_type_name,
            description=f"DefinedType.{defined_type_name} (не раскрыт — нет в индексе)",
        )
    return resolve_types(type_strings)


def is_type_compatible_with_numeric(resolved: ResolvedType, defined_types_index: dict | None = None) -> bool:
    """Проверяет, совместим ли тип с числовым контекстом (СУММА, СРЕДНЕЕ)."""
    if resolved.is_numeric():
        return True
    if resolved.kind == "defined_type" and defined_types_index:
        expanded = resolve_defined_type(resolved.ref_name, defined_types_index)
        return is_type_compatible_with_numeric(expanded, defined_types_index)
    if resolved.is_composite():
        # Для составного хотя бы один вариант должен быть числовым
        return any(is_type_compatible_with_numeric(v, defined_types_index) for v in resolved.variants)
    return False


def is_type_compatible_with_string(resolved: ResolvedType, defined_types_index: dict | None = None) -> bool:
    """Проверяет, совместим ли тип со строковым контекстом (ПОДОБНО, Строка)."""
    if resolved.is_string() or resolved.is_date() or resolved.is_boolean():
        return True
    if resolved.is_ref():
        return True  # Ссылки могут быть приведены к строке (представление)
    if resolved.kind == "defined_type" and defined_types_index:
        expanded = resolve_defined_type(resolved.ref_name, defined_types_index)
        return is_type_compatible_with_string(expanded, defined_types_index)
    if resolved.is_composite():
        return any(is_type_compatible_with_string(v, defined_types_index) for v in resolved.variants)
    return False
