"""
_common.py — Общие константы, модели и утилиты для DSL компиляторов.

Содержит:
- XML namespaces 1С (NS_MD, NS_XR, NS_V8, NS_XS, NS_XSI, NS_DCS, NS_DCSSET)
- TYPE_MAP — маппинг типов объектов 1С → XML-теги и папки
- RU_TYPE_SYNONYMS — русские синонимы типов объектов
- RU_DATA_TYPE_SYNONYMS — русские синонимы типов данных
- CompileResult — dataclass результата компиляции
- _gen_uuid, _camel_to_words, _normalize_type, _normalize_object_type,
  _parse_attribute, _make_type_element — утилиты
"""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

NS_MD = "http://v8.1c.ru/8.3/MDClasses"
NS_XR = "http://v8.1c.ru/8.3/xcf/extprops"
NS_V8 = "http://v8.1c.ru/8.1/data/core"
NS_XS = "http://www.w3.org/2001/XMLSchema"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_DCS = "http://v8.1c.ru/8.1/data-composition-system/schema"
NS_DCSSET = "http://v8.1c.ru/8.1/data-composition-system/settings"
# P2.3: NS_SSD, NS_SSDX для MxlCompiler (spreadsheet document)
NS_SSD = "http://v8.1c.ru/8.1/data/spreadsheet"
NS_SSDX = "http://v8.1c.ru/8.1/data/spreadsheet/auxiliary"
# P2.3: NS_RIGHTS для RoleCompiler
NS_RIGHTS = "http://v8.1c.ru/8.1/data/rights"

# Маппинг типов объектов 1С → XML-теги и папки.
# P3.17: вынесен в src/services/object_types.py — единый источник для DSL и CFE.
# Здесь оставлен re-export для обратной совместимости с существующими импортами.
# DSL поддерживает подмножество типов из полного TYPE_MAP.
# Импортируем только поддерживаемые, чтобы не вводить в заблуждение.
from src.services.object_types import DSL_SUPPORTED_TYPES
from src.services.object_types import TYPE_MAP as _UNIFIED_TYPE_MAP

TYPE_MAP: dict[str, dict] = {
    k: v for k, v in _UNIFIED_TYPE_MAP.items() if k in DSL_SUPPORTED_TYPES
}

# Русские синонимы типов
RU_TYPE_SYNONYMS: dict[str, str] = {
    "Справочник": "Catalog",
    "Документ": "Document",
    "Перечисление": "Enum",
    "Константа": "Constant",
    "РегистрСведений": "InformationRegister",
    "РегистрНакопления": "AccumulationRegister",
    "РегистрБухгалтерии": "AccountingRegister",
    "РегистрРасчёта": "CalculationRegister",
    "РегистрРасчета": "CalculationRegister",
    "ПланСчетов": "ChartOfAccounts",
    "ПланВидовХарактеристик": "ChartOfCharacteristicTypes",
    "ПланВидовРасчёта": "ChartOfCalculationTypes",
    "ПланВидовРасчета": "ChartOfCalculationTypes",
    "БизнесПроцесс": "BusinessProcess",
    "Задача": "Task",
    "ПланОбмена": "ExchangePlan",
    "ЖурналДокументов": "DocumentJournal",
    "Отчёт": "Report",
    "Отчет": "Report",
    "Обработка": "DataProcessor",
    "ОбщийМодуль": "CommonModule",
    "РегламентноеЗадание": "ScheduledJob",
    "ПодпискаНаСобытие": "EventSubscription",
    "ОпределяемыйТип": "DefinedType",
    "HTTPСервис": "HTTPService",
    "ВебСервис": "WebService",
}

# Русские синонимы типов данных
RU_DATA_TYPE_SYNONYMS: dict[str, str] = {
    "Строка": "String",
    "Число": "Number",
    "Булево": "Boolean",
    "Дата": "Date",
    "ДатаВремя": "DateTime",
    "СправочникСсылка": "CatalogRef",
    "ДокументСсылка": "DocumentRef",
    "ПеречислениеСсылка": "EnumRef",
    "ПланСчетовСсылка": "ChartOfAccountsRef",
    "ПланВидовХарактеристикСсылка": "ChartOfCharacteristicTypesRef",
    "ПланВидовРасчётаСсылка": "ChartOfCalculationTypesRef",
    "ПланВидовРасчетаСсылка": "ChartOfCalculationTypesRef",
    "ПланОбменаСсылка": "ExchangePlanRef",
    "БизнесПроцессСсылка": "BusinessProcessRef",
    "ЗадачаСсылка": "TaskRef",
    "ОпределяемыйТип": "DefinedType",
}


# ============================================================================
# МОДЕЛИ
# ============================================================================


@dataclass
class CompileResult:
    """Результат компиляции DSL → XML."""

    object_type: str
    object_name: str
    xml_path: Path | None = None
    module_paths: list[Path] = field(default_factory=list)
    registered_in_config: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ============================================================================
# УТИЛИТЫ
# ============================================================================


def _gen_uuid() -> str:
    """Сгенерировать UUID в формате 1С."""
    return str(uuid.uuid4())


def _camel_to_words(name: str) -> str:
    """Разбить CamelCase на слова для автогенерации синонима.

    АвансовыйОтчет → Авансовый отчет
    ОсновнаяВалюта → Основная валюта
    НДС20 → НДС20
    IncomingDocument → Incoming document
    """
    if not name:
        return name

    # Граница на переходе [а-яё][А-ЯЁ] и [a-z][A-Z]
    def replacer(m: re.Match[str]) -> str:
        if m.group(1) and m.group(2):
            # Russian boundary
            return m.group(1) + " " + m.group(2)
        elif m.group(3) and m.group(4):
            # English boundary
            return m.group(3) + " " + m.group(4)
        return m.group(0)

    result = re.sub(r"([а-яё])([А-ЯЁ])|([a-z])([A-Z])", replacer, name)
    if not result:
        return name
    # Первое слово с большой, остальные с маленькой
    parts = result.split(" ")
    if len(parts) == 1:
        return parts[0][0].upper() + parts[0][1:]
    return parts[0][0].upper() + parts[0][1:] + " " + " ".join(p.lower() for p in parts[1:])


def _normalize_type(type_str: str) -> str:
    """Нормализовать тип данных: русские синонимы → канонические."""
    if not type_str:
        return "String"

    # Проверяем русские синонимы с параметрами (СправочникСсылка.Xxx)
    for ru, en in RU_DATA_TYPE_SYNONYMS.items():
        if type_str.startswith(ru + "."):
            return en + type_str[len(ru) :]
        if type_str.lower() == ru.lower():
            return en

    return type_str


def _normalize_object_type(type_str: str) -> str:
    """Нормализовать тип объекта: русские синонимы → английские."""
    if not type_str:
        return ""
    if type_str in TYPE_MAP:
        return type_str
    if type_str in RU_TYPE_SYNONYMS:
        return RU_TYPE_SYNONYMS[type_str]
    # Case-insensitive поиск
    for ru, en in RU_TYPE_SYNONYMS.items():
        if type_str.lower() == ru.lower():
            return en
    return type_str


def _sanitize_bsl_string(value: str) -> str:
    """SEC-3: Санитация строковых значений для вставки в BSL/XML.

    Удаляет символы, которые могут привести к инъекции:
    - Двойные кавычки экранируются (для BSL строковых литералов)
    - Угловые скобки экранируются (для XML)
    """
    if not isinstance(value, str):
        return str(value)
    # BSL: " → "" (экранирование внутри строкового литерала)
    # XML: < → &lt; > → &gt; & → &amp;
    return value.replace('"', '""')


def _parse_attribute(attr_def: str | dict) -> dict:
    """Разбор определения реквизита (строка или объект).

    Форматы:
        'Имя'                                    → String без квалификаторов
        'Имя: Тип'                               → с типом
        'Имя: Тип | req, index'                  → с флагами
        {"name": "Имя", "type": "String(100)", "synonym": "..."}
    """
    if isinstance(attr_def, dict):
        return {
            "name": attr_def.get("name", ""),
            "type": _normalize_type(attr_def.get("type", "String")),
            "synonym": attr_def.get("synonym", ""),
            "comment": attr_def.get("comment", ""),
            "fillChecking": attr_def.get("fillChecking", ""),
            "indexing": attr_def.get("indexing", ""),
        }

    if not isinstance(attr_def, str):
        raise ValueError(f"Неверный формат реквизита: {attr_def}")

    # Строковая форма: "Имя: Тип | req, index"
    flags: list[str] = []
    if "|" in attr_def:
        attr_def, flags_str = attr_def.split("|", 1)
        flags = [f.strip() for f in flags_str.split(",")]

    name = attr_def.strip()
    type_str = "String"

    if ":" in name:
        name, type_str = name.split(":", 1)
        name = name.strip()
        type_str = type_str.strip()

    # Нормализуем русские синонимы типов С УЧЕТОМ скобок
    # Число(10,3) → Number(10,3), Строка(100) → String(100)
    for ru, en in RU_DATA_TYPE_SYNONYMS.items():
        if type_str.startswith(ru):
            # Заменяем только префикс (оставляем параметры в скобках)
            type_str = en + type_str[len(ru) :]
            break

    return {
        "name": name,
        "type": _normalize_type(type_str),
        "synonym": "",
        "comment": "",
        "fillChecking": "ShowError" if "req" in flags else "",
        "indexing": "Index" if "index" in flags else ("IndexWithAdditionalOrder" if "indexAdditional" in flags else ""),
    }


def _make_type_element(parent: ET.Element, type_str: str, tag_name: str = "Type") -> None:
    """Создать элемент <Type> с правильным namespace."""
    # String(100) → xs:string + StringQualifiers
    # Number(15,2) → xs:decimal + NumberQualifiers
    # CatalogRef.Xxx → cfg:CatalogRef.Xxx
    # Boolean → xs:boolean

    # Парсим тип
    type_match = re.match(r"(\w+)(?:\((\d+)(?:,(\d+))?\))?(?:\.([^.]+))?", type_str)
    if not type_match:
        return

    base_type = type_match.group(1)
    length = type_match.group(2)
    precision = type_match.group(3)
    ref_name = type_match.group(4)

    if base_type == "String":
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:string"
        if length:
            qualifiers = ET.SubElement(parent, f"{{{NS_XR}}}StringQualifiers")
            length_elem = ET.SubElement(qualifiers, f"{{{NS_XR}}}Length")
            length_elem.text = length
    elif base_type == "Number":
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:decimal"
        qualifiers = ET.SubElement(parent, f"{{{NS_XR}}}NumberQualifiers")
        length_elem = ET.SubElement(qualifiers, f"{{{NS_XR}}}Length")
        length_elem.text = length or "10"
        if precision:
            prec_elem = ET.SubElement(qualifiers, f"{{{NS_XR}}}Precision")
            prec_elem.text = precision
            scale_elem = ET.SubElement(qualifiers, f"{{{NS_XR}}}Scale")
            scale_elem.text = precision
    elif base_type == "Boolean":
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:boolean"
    elif base_type == "Date":
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:dateTime"
        qualifiers = ET.SubElement(parent, f"{{{NS_XR}}}DateQualifiers")
        df = ET.SubElement(qualifiers, f"{{{NS_XR}}}DateFractions")
        df.text = "Date"
    elif base_type == "DateTime":
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:dateTime"
        qualifiers = ET.SubElement(parent, f"{{{NS_XR}}}DateQualifiers")
        df = ET.SubElement(qualifiers, f"{{{NS_XR}}}DateFractions")
        df.text = "DateTime"
    elif base_type.endswith("Ref") and ref_name:
        # CatalogRef.Xxx → cfg:CatalogRef.Xxx
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = f"cfg:{base_type}.{ref_name}"
    elif base_type == "DefinedType" and ref_name:
        type_elem = ET.SubElement(parent, f"{{{NS_V8}}}TypeSet")
        type_elem.text = f"cfg:DefinedType.{ref_name}"
    else:
        # Fallback — строка
        type_elem = ET.SubElement(parent, f"{{{NS_XS}}}{tag_name}")
        type_elem.text = "xs:string"
