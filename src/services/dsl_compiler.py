"""
DSL Compiler — JSON DSL → XML для объектов 1С.

Поддерживаемые компиляторы:
1. meta_compile(definition, output_dir) — метаданные 1С (23 типа объектов)
2. form_compile(definition, output_path) — управляемая форма (Form.xml)
3. skd_compile(definition, output_path) — схема компоновки данных (СКД)

Позаимствовано из 1c-ai-development-kit (skills meta-compile, form-compile, skd-compile).
Спецификации DSL: docs/1c-xml-specs/meta-dsl-spec.md, form-dsl-spec.md, skd-dsl-spec.md

Принципы:
- Компактный JSON → валидный XML 1С
- Автогенерация синонимов из CamelCase
- Shorthand для реквизитов: 'Имя: Тип | req, index'
- Русские синонимы типов: Строка, СправочникСсылка.Xxx
"""
from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

# XML namespaces 1С
NS_MD = "http://v8.1c.ru/8.3/MDClasses"
NS_XR = "http://v8.1c.ru/8.3/xcf/extprops"
NS_V8 = "http://v8.1c.ru/8.1/data/core"
NS_XS = "http://www.w3.org/2001/XMLSchema"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_DCS = "http://v8.1c.ru/8.1/data-composition-system/schema"
NS_DCSSET = "http://v8.1c.ru/8.1/data-composition-system/settings"

# Маппинг типов объектов 1С → XML-теги и папки
TYPE_MAP: dict[str, dict] = {
    "Catalog":              {"xml_tag": "Catalog",              "dir": "Catalogs"},
    "Document":             {"xml_tag": "Document",             "dir": "Documents"},
    "Enum":                 {"xml_tag": "Enum",                 "dir": "Enums"},
    "Constant":             {"xml_tag": "Constant",             "dir": "Constants"},
    "InformationRegister":  {"xml_tag": "InformationRegister",  "dir": "InformationRegisters"},
    "AccumulationRegister": {"xml_tag": "AccumulationRegister", "dir": "AccumulationRegisters"},
    "AccountingRegister":   {"xml_tag": "AccountingRegister",   "dir": "AccountingRegisters"},
    "CalculationRegister":  {"xml_tag": "CalculationRegister",  "dir": "CalculationRegisters"},
    "ChartOfAccounts":      {"xml_tag": "ChartOfAccounts",      "dir": "ChartsOfAccounts"},
    "ChartOfCharacteristicTypes": {"xml_tag": "ChartOfCharacteristicTypes", "dir": "ChartsOfCharacteristicTypes"},
    "ChartOfCalculationTypes":    {"xml_tag": "ChartOfCalculationTypes",    "dir": "ChartsOfCalculationTypes"},
    "BusinessProcess":      {"xml_tag": "BusinessProcess",      "dir": "BusinessProcesses"},
    "Task":                 {"xml_tag": "Task",                 "dir": "Tasks"},
    "ExchangePlan":         {"xml_tag": "ExchangePlan",         "dir": "ExchangePlans"},
    "DocumentJournal":      {"xml_tag": "DocumentJournal",      "dir": "DocumentJournals"},
    "Report":               {"xml_tag": "Report",               "dir": "Reports"},
    "DataProcessor":        {"xml_tag": "DataProcessor",        "dir": "DataProcessors"},
    "CommonModule":         {"xml_tag": "CommonModule",         "dir": "CommonModules"},
    "ScheduledJob":         {"xml_tag": "ScheduledJob",         "dir": "ScheduledJobs"},
    "EventSubscription":    {"xml_tag": "EventSubscription",    "dir": "EventSubscriptions"},
    "DefinedType":          {"xml_tag": "DefinedType",          "dir": "DefinedTypes"},
    "HTTPService":          {"xml_tag": "HTTPService",          "dir": "HTTPServices"},
    "WebService":           {"xml_tag": "WebService",           "dir": "WebServices"},
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
    xml_path: Optional[Path] = None
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
    def replacer(m):
        if m.group(1) and m.group(2):
            # Russian boundary
            return m.group(1) + " " + m.group(2)
        elif m.group(3) and m.group(4):
            # English boundary
            return m.group(3) + " " + m.group(4)
        return m.group(0)

    result = re.sub(r'([а-яё])([А-ЯЁ])|([a-z])([A-Z])', replacer, name)
    if not result:
        return name
    # Первое слово с большой, остальные с маленькой
    parts = result.split(' ')
    if len(parts) == 1:
        return parts[0][0].upper() + parts[0][1:]
    return parts[0][0].upper() + parts[0][1:] + ' ' + ' '.join(p.lower() for p in parts[1:])


def _normalize_type(type_str: str) -> str:
    """Нормализовать тип данных: русские синонимы → канонические."""
    if not type_str:
        return "String"

    # Проверяем русские синонимы с параметрами (СправочникСсылка.Xxx)
    for ru, en in RU_DATA_TYPE_SYNONYMS.items():
        if type_str.startswith(ru + "."):
            return en + type_str[len(ru):]
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


def _parse_attribute(attr_def: Union[str, dict]) -> dict:
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
            type_str = en + type_str[len(ru):]
            break

    return {
        "name": name,
        "type": _normalize_type(type_str),
        "synonym": "",
        "comment": "",
        "fillChecking": "ShowError" if "req" in flags else "",
        "indexing": "Index" if "index" in flags else (
            "IndexWithAdditionalOrder" if "indexAdditional" in flags else ""
        ),
    }


def _make_type_element(parent: ET.Element, type_str: str, tag_name: str = "Type") -> None:
    """Создать элемент <Type> с правильным namespace."""
    # String(100) → xs:string + StringQualifiers
    # Number(15,2) → xs:decimal + NumberQualifiers
    # CatalogRef.Xxx → cfg:CatalogRef.Xxx
    # Boolean → xs:boolean

    # Парсим тип
    type_match = re.match(r'(\w+)(?:\((\d+)(?:,(\d+))?\))?(?:\.([^.]+))?', type_str)
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


# ============================================================================
# META COMPILE — компиляция объектов метаданных
# ============================================================================

class MetaCompiler:
    """Компилятор JSON DSL → XML для объектов метаданных 1С (23 типа)."""

    def compile(
        self,
        definition: Union[str, dict, Path],
        output_dir: Union[str, Path],
    ) -> CompileResult:
        """Скомпилировать JSON DSL → XML.

        Args:
            definition: JSON-определение объекта (dict, JSON-строка или путь к файлу)
            output_dir: каталог выгрузки конфигурации (где Catalogs/, Documents/, и т.д.)

        Returns:
            CompileResult с путями к созданным файлам
        """
        # Парсим definition
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                with open(def_path, encoding="utf-8") as f:
                    def_dict = json.load(f)
            else:
                # JSON-строка
                def_dict = json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        # Нормализуем тип объекта
        object_type = _normalize_object_type(def_dict.get("type", ""))
        if not object_type or object_type not in TYPE_MAP:
            raise ValueError(
                f"Неподдерживаемый тип объекта: {def_dict.get('type')}. "
                f"Поддерживается {len(TYPE_MAP)} типов."
            )

        object_name = def_dict.get("name", "")
        if not object_name:
            raise ValueError("Имя объекта не указано (поле 'name')")

        # Синоним (авто из CamelCase если не указан)
        synonym = def_dict.get("synonym") or _camel_to_words(object_name)

        result = CompileResult(
            object_type=object_type,
            object_name=object_name,
        )

        type_info = TYPE_MAP[object_type]
        output_dir = Path(output_dir)

        # Создаём каталог объекта
        obj_dir = output_dir / type_info["dir"] / object_name
        obj_dir.mkdir(parents=True, exist_ok=True)

        # Создаём XML объекта
        xml_path = output_dir / type_info["dir"] / f"{object_name}.xml"
        self._write_object_xml(
            xml_path, object_type, object_name, synonym, def_dict
        )
        result.xml_path = xml_path

        # Создаём модули BSL (если нужно)
        module_paths = self._create_modules(obj_dir, object_type, def_dict)
        result.module_paths = module_paths

        # Регистрируем в Configuration.xml (если есть)
        config_xml = output_dir / "Configuration.xml"
        if config_xml.exists():
            result.registered_in_config = self._register_in_config(
                config_xml, object_type, object_name
            )

        return result

    def _write_object_xml(
        self,
        xml_path: Path,
        object_type: str,
        object_name: str,
        synonym: str,
        def_dict: dict,
    ) -> None:
        """Записать XML объекта метаданных."""
        # Регистрируем namespaces
        for prefix, uri in [
            ("md", NS_MD), ("xr", NS_XR), ("v8", NS_V8),
            ("xs", NS_XS), ("xsi", NS_XSI)
        ]:
            ET.register_namespace(prefix, uri)

        type_info = TYPE_MAP[object_type]
        root = ET.Element(f"{{{NS_MD}}}{type_info['xml_tag']}")
        root.set("uuid", _gen_uuid())
        root.set("name", object_name)

        # InternalInfo (для объектов с reference)
        if object_type in ("Catalog", "Document", "Enum", "InformationRegister",
                           "AccumulationRegister", "ChartOfAccounts"):
            internal_info = ET.SubElement(root, f"{{{NS_MD}}}InternalInfo")
            if object_type in ("Catalog", "Document", "Enum"):
                # GeneratedType
                gen_type = ET.SubElement(internal_info, f"{{{NS_XR}}}GeneratedType")
                gen_type.set("name", f"Catalog.{object_name}" if object_type == "Catalog" else f"Document.{object_name}")
                gen_type.set("category", "Ref")
                type_id = ET.SubElement(gen_type, f"{{{NS_XR}}}TypeId")
                type_id.text = _gen_uuid()
                value_id = ET.SubElement(gen_type, f"{{{NS_XR}}}ValueId")
                value_id.text = _gen_uuid()

        # Properties
        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name_elem.text = object_name

        syn_elem = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
        content = ET.SubElement(item, f"{{{NS_V8}}}content")
        content.text = synonym

        # Comment
        comment = def_dict.get("comment", "")
        if comment:
            c_elem = ET.SubElement(props, f"{{{NS_XR}}}Comment")
            c_elem.text = comment

        # StandardAttributes
        self._add_standard_attributes(props, object_type)

        # Type-specific properties
        self._add_type_specific_props(props, object_type, def_dict)

        # ChildObjects
        child_objects = ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")
        self._add_child_objects(child_objects, object_type, def_dict)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    def _add_standard_attributes(self, props_elem: ET.Element, object_type: str) -> None:
        """Добавить стандартные реквизиты (Ref, Code, Description, и т.д.)."""
        std_attrs_map = {
            "Catalog": ["PredefinedDataName", "Predefined", "Ref", "DeletionMark",
                        "IsFolder", "Owner", "Parent", "Description", "Code"],
            "Document": ["Posted", "Ref", "DeletionMark", "Date", "Number"],
            "Enum": ["Order", "Ref"],
            "InformationRegister": ["Active", "LineNumber", "Recorder", "Period"],
            "AccumulationRegister": ["Active", "LineNumber", "Recorder", "Period"],
        }

        attrs = std_attrs_map.get(object_type, [])
        for attr_name in attrs:
            std_attr = ET.SubElement(props_elem, f"{{{NS_XR}}}StandardAttribute")
            std_attr.set("name", attr_name)
            ET.SubElement(std_attr, f"{{{NS_XR}}}LinkByType")
            fill_check = ET.SubElement(std_attr, f"{{{NS_XR}}}FillChecking")
            fill_check.text = "DontCheck"

    def _add_type_specific_props(
        self, props_elem: ET.Element, object_type: str, def_dict: dict
    ) -> None:
        """Добавить свойства специфичные для типа объекта."""
        if object_type == "Catalog":
            # Hierarchical, CodeLength, DescriptionLength
            hier = ET.SubElement(props_elem, f"{{{NS_XR}}}Hierarchical")
            hier.text = "false" if not def_dict.get("hierarchical") else "true"

            code_length = ET.SubElement(props_elem, f"{{{NS_XR}}}CodeLength")
            code_length.text = str(def_dict.get("codeLength", 9))

            desc_length = ET.SubElement(props_elem, f"{{{NS_XR}}}DescriptionLength")
            desc_length.text = str(def_dict.get("descriptionLength", 25))

            autonumbering = ET.SubElement(props_elem, f"{{{NS_XR}}}Autonumbering")
            autonumbering.text = "true" if def_dict.get("autonumbering", True) else "false"

        elif object_type == "Document":
            number_length = ET.SubElement(props_elem, f"{{{NS_XR}}}NumberLength")
            number_length.text = str(def_dict.get("numberLength", 11))

            check_unique = ET.SubElement(props_elem, f"{{{NS_XR}}}CheckUnique")
            check_unique.text = "true" if def_dict.get("checkUnique", True) else "false"

            posting = ET.SubElement(props_elem, f"{{{NS_XR}}}Posting")
            posting.text = def_dict.get("posting", "Allow")

            autonumbering = ET.SubElement(props_elem, f"{{{NS_XR}}}Autonumbering")
            autonumbering.text = "true" if def_dict.get("autonumbering", True) else "false"

        elif object_type == "InformationRegister":
            # Periodicity, WriteModal, etc.
            periodicity = ET.SubElement(props_elem, f"{{{NS_XR}}}Periodicity")
            periodicity.text = def_dict.get("periodicity", "Nonperiodical")

        elif object_type == "Constant":
            # Type
            type_container = ET.SubElement(props_elem, f"{{{NS_XR}}}Type")
            value_type = _normalize_type(def_dict.get("valueType", "String"))
            _make_type_element(type_container, value_type)

    def _add_child_objects(
        self, child_objects_elem: ET.Element, object_type: str, def_dict: dict
    ) -> None:
        """Добавить дочерние объекты (реквизиты, ТЧ, формы, значения enum)."""
        # Реквизиты (attributes)
        attributes = def_dict.get("attributes", [])
        for attr_def in attributes:
            attr = _parse_attribute(attr_def)
            self._write_attribute(child_objects_elem, attr, "Attribute")

        # Табличные части
        tabular_sections = def_dict.get("tabularSections", {})
        if isinstance(tabular_sections, dict):
            for ts_name, ts_attrs in tabular_sections.items():
                ts_elem = ET.SubElement(child_objects_elem, f"{{{NS_MD}}}TabularSection")
                ts_props = ET.SubElement(ts_elem, f"{{{NS_MD}}}Properties")
                name_elem = ET.SubElement(ts_props, f"{{{NS_XR}}}Name")
                name_elem.text = ts_name
                if object_type == "Catalog":
                    use = ET.SubElement(ts_props, f"{{{NS_XR}}}Use")
                    use.text = "ForItem"
                # Реквизиты ТЧ
                for attr_def in ts_attrs:
                    attr = _parse_attribute(attr_def)
                    self._write_attribute(ts_elem, attr, "Attribute")

        # Значения перечисления (для Enum)
        if object_type == "Enum":
            values = def_dict.get("values", [])
            for val_def in values:
                if isinstance(val_def, str):
                    val_name = val_def
                    val_synonym = _camel_to_words(val_name)
                else:
                    val_name = val_def.get("name", "")
                    val_synonym = val_def.get("synonym") or _camel_to_words(val_name)

                enum_val = ET.SubElement(child_objects_elem, f"{{{NS_MD}}}EnumValue")
                val_props = ET.SubElement(enum_val, f"{{{NS_MD}}}Properties")
                name_elem = ET.SubElement(val_props, f"{{{NS_XR}}}Name")
                name_elem.text = val_name
                syn_elem = ET.SubElement(val_props, f"{{{NS_XR}}}Synonym")
                item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
                content = ET.SubElement(item, f"{{{NS_V8}}}content")
                content.text = val_synonym

    def _write_attribute(
        self, parent: ET.Element, attr: dict, tag_name: str = "Attribute"
    ) -> None:
        """Записать реквизит как <Attribute>."""
        attr_elem = ET.SubElement(parent, f"{{{NS_MD}}}{tag_name}")
        attr_props = ET.SubElement(attr_elem, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(attr_props, f"{{{NS_XR}}}Name")
        name_elem.text = attr["name"]

        if attr.get("synonym"):
            syn_elem = ET.SubElement(attr_props, f"{{{NS_XR}}}Synonym")
            item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = attr["synonym"]

        # Type
        type_container = ET.SubElement(attr_props, f"{{{NS_XR}}}Type")
        _make_type_element(type_container, attr["type"])

        # FillChecking
        if attr.get("fillChecking"):
            fc = ET.SubElement(attr_props, f"{{{NS_XR}}}FillChecking")
            fc.text = attr["fillChecking"]

        # Indexing
        if attr.get("indexing"):
            idx = ET.SubElement(attr_props, f"{{{NS_XR}}}Indexing")
            idx.text = attr["indexing"]

    def _create_modules(
        self, obj_dir: Path, object_type: str, def_dict: dict
    ) -> list[Path]:
        """Создать BSL-модули объекта (ObjectModule, ManagerModule)."""
        modules: list[Path] = []

        # ObjectModule для Catalog, Document, InformationRegister, и т.д.
        types_with_object_module = {
            "Catalog", "Document", "InformationRegister", "AccumulationRegister",
            "ChartOfAccounts", "BusinessProcess", "Task", "Report", "DataProcessor",
        }
        if object_type in types_with_object_module:
            module_dir = obj_dir / "Ext"
            module_dir.mkdir(parents=True, exist_ok=True)
            module_path = module_dir / "ObjectModule.bsl"
            module_path.write_text(
                self._default_object_module(object_type, def_dict),
                encoding="utf-8"
            )
            modules.append(module_path)

        return modules

    def _default_object_module(self, object_type: str, def_dict: dict) -> str:
        """Шаблон ObjectModule.bsl с регионами."""
        return (
            f"// Объект: {object_type} {def_dict.get('name', '')}\n"
            f"// Сгенерировано DSL Compiler\n"
            f"\n"
            f"#Область ПрограммныйИнтерфейс\n"
            f"\n"
            f"// TODO: Описание API объекта\n"
            f"\n"
            f"#КонецОбласти\n"
            f"\n"
            f"#Область СлужебныйПрограммныйИнтерфейс\n"
            f"\n"
            f"// TODO: Служебные методы\n"
            f"\n"
            f"#КонецОбласти\n"
            f"\n"
            f"#Область СлужебныеПроцедурыИФункции\n"
            f"\n"
            f"// TODO: Внутренние методы\n"
            f"\n"
            f"#КонецОбласти\n"
        )

    def _register_in_config(
        self, config_xml: Path, object_type: str, object_name: str
    ) -> bool:
        """Зарегистрировать объект в ChildObjects Configuration.xml."""
        try:
            tree = ET.parse(config_xml)
            root = tree.getroot()
            type_info = TYPE_MAP.get(object_type)
            if not type_info:
                return False

            # Ищем <ChildObjects>
            child_objects = None
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "ChildObjects":
                    child_objects = elem
                    break

            if child_objects is None:
                child_objects = ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")

            # Проверяем — не зарегистрирован ли уже
            xml_tag = type_info["xml_tag"]
            for child in child_objects:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == xml_tag and child.text == object_name:
                    return True  # уже зарегистрирован

            # Добавляем
            new_elem = ET.SubElement(child_objects, f"{{{NS_MD}}}{xml_tag}")
            new_elem.text = object_name

            tree.write(config_xml, encoding="utf-8", xml_declaration=True)
            return True
        except (ET.ParseError, OSError):
            return False


# ============================================================================
# FORM COMPILE — компиляция управляемых форм
# ============================================================================

class FormCompiler:
    """Компилятор JSON DSL → Form.xml для управляемых форм 1С."""

    def compile(
        self,
        definition: Union[str, dict, Path],
        output_path: Union[str, Path],
    ) -> CompileResult:
        """Скомпилировать JSON DSL → Form.xml.

        Args:
            definition: JSON-определение формы (dict, JSON-строка или путь к файлу)
            output_path: путь к выходному Form.xml

        Returns:
            CompileResult
        """
        # Парсим definition
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                with open(def_path, encoding="utf-8") as f:
                    def_dict = json.load(f)
            else:
                def_dict = json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        form_name = def_dict.get("name", "Форма")
        result = CompileResult(
            object_type="Form",
            object_name=form_name,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Регистрируем namespaces
        for prefix, uri in [
            ("md", NS_MD), ("xr", NS_XR), ("v8", NS_V8), ("v8ui", "http://v8.1c.ru/8.1/data/ui")
        ]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_MD}}}Form")
        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")

        name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name_elem.text = form_name

        syn_elem = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
        content = ET.SubElement(item, f"{{{NS_V8}}}content")
        content.text = def_dict.get("synonym", form_name)

        # AutoTitle
        auto_title = ET.SubElement(props, f"{{{NS_XR}}}AutoTitle")
        auto_title.text = "false" if def_dict.get("customTitle") else "true"

        # Items — элементы формы
        items_container = ET.SubElement(root, f"{{{NS_MD}}}Items")
        for item_def in def_dict.get("items", []):
            self._write_form_item(items_container, item_def)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        result.xml_path = output_path

        return result

    def _write_form_item(self, parent: ET.Element, item_def: dict) -> None:
        """Записать элемент формы."""
        item_type = item_def.get("type", "Label")
        item_elem = ET.SubElement(parent, f"{{{NS_MD}}}{item_type}")

        name = item_def.get("name", "")
        if name:
            item_elem.set("name", name)

        props = ET.SubElement(item_elem, f"{{{NS_MD}}}Properties")

        if name:
            name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
            name_elem.text = name

        # Title
        title = item_def.get("title")
        if title:
            title_elem = ET.SubElement(props, f"{{{NS_XR}}}Title")
            item_v8 = ET.SubElement(title_elem, f"{{{NS_V8}}}item")
            content = ET.SubElement(item_v8, f"{{{NS_V8}}}content")
            content.text = title

        # DataPath (для InputField и других связанных с данными)
        data_path = item_def.get("dataPath")
        if data_path:
            dp_elem = ET.SubElement(props, f"{{{NS_XR}}}DataPath")
            dp_elem.text = data_path

        # Visible
        if "visible" in item_def:
            vis = ET.SubElement(props, f"{{{NS_XR}}}Visible")
            vis.text = "true" if item_def["visible"] else "false"

        # ChildItems
        for child_def in item_def.get("children", []):
            self._write_form_item(item_elem, child_def)


# ============================================================================
# SKD COMPILE — компиляция схем компоновки данных
# ============================================================================

class SkdCompiler:
    """Компилятор JSON DSL → Template.xml для СКД 1С."""

    def compile(
        self,
        definition: Union[str, dict, Path],
        output_path: Union[str, Path],
    ) -> CompileResult:
        """Скомпилировать JSON DSL → СКД Template.xml.

        Args:
            definition: JSON-определение СКД
            output_path: путь к выходному Template.xml

        Returns:
            CompileResult
        """
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                with open(def_path, encoding="utf-8") as f:
                    def_dict = json.load(f)
            else:
                def_dict = json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        result = CompileResult(
            object_type="DataCompositionSchema",
            object_name=def_dict.get("name", "ОсновнаяСхемаКомпоновкиДанных"),
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Регистрируем namespaces
        for prefix, uri in [
            ("s", NS_DCS), ("v8", NS_V8), ("xs", NS_XS), ("xsi", NS_XSI),
        ]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_DCS}}}DataCompositionSchema")

        # Data sources (auto если не указаны)
        data_sources = def_dict.get("dataSources", [])
        if not data_sources:
            data_sources = [{"name": "ИсточникДанных1", "connection": "Local"}]

        ds_container = ET.SubElement(root, f"{{{NS_DCS}}}dataSources")
        for ds_src in data_sources:
            src_elem = ET.SubElement(ds_container, f"{{{NS_DCS}}}dataSource")
            n = ET.SubElement(src_elem, f"{{{NS_DCS}}}name")
            n.text = ds_src["name"]

        # Data sets
        data_sets = def_dict.get("dataSets", [])
        ds_container = ET.SubElement(root, f"{{{NS_DCS}}}dataSets")
        for ds_def in data_sets:
            self._write_data_set(ds_container, ds_def)

        # Calculated fields
        for cf_def in def_dict.get("calculatedFields", []):
            self._write_calculated_field(root, cf_def)

        # Total fields (resources)
        for tf_def in def_dict.get("totalFields", []):
            self._write_total_field(root, tf_def)

        # Parameters
        for param_def in def_dict.get("parameters", []):
            self._write_parameter(root, param_def)

        # Записываем
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        result.xml_path = output_path

        return result

    def _write_data_set(self, parent: ET.Element, ds_def: dict) -> None:
        """Записать набор данных."""
        ds_type = ds_def.get("type", "query")
        type_map = {
            "query": "DataSetQuery",
            "objectName": "DataSetObject",
            "union": "DataSetUnion",
        }
        ds_type_xml = type_map.get(ds_type, "DataSetQuery")

        ds_elem = ET.SubElement(parent, f"{{{NS_DCS}}}dataSet")
        ds_elem.set(f"{{{NS_XSI}}}type", f"s:{ds_type_xml}")

        n = ET.SubElement(ds_elem, f"{{{NS_DCS}}}name")
        n.text = ds_def.get("name", "НаборДанных1")

        # Query (для DataSetQuery)
        if ds_type == "query" and ds_def.get("query"):
            q = ET.SubElement(ds_elem, f"{{{NS_DCS}}}query")
            q.text = ds_def["query"]

        # ObjectName (для DataSetObject)
        if ds_type == "objectName" and ds_def.get("objectName"):
            on = ET.SubElement(ds_elem, f"{{{NS_DCS}}}objectName")
            on.text = ds_def["objectName"]

        # Fields
        for field_def in ds_def.get("fields", []):
            self._write_dataset_field(ds_elem, field_def)

    def _write_dataset_field(self, parent: ET.Element, field_def: dict) -> None:
        """Записать поле набора данных."""
        f = ET.SubElement(parent, f"{{{NS_DCS}}}field")
        dp = ET.SubElement(f, f"{{{NS_DCS}}}dataPath")
        dp.text = field_def.get("path", field_def.get("name", ""))

        if field_def.get("title"):
            title = ET.SubElement(f, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = field_def["title"]

        if field_def.get("expression"):
            expr = ET.SubElement(f, f"{{{NS_DCS}}}expression")
            expr.text = field_def["expression"]

    def _write_calculated_field(self, parent: ET.Element, cf_def: dict) -> None:
        """Записать вычисляемое поле."""
        cf = ET.SubElement(parent, f"{{{NS_DCS}}}calculatedField")
        dp = ET.SubElement(cf, f"{{{NS_DCS}}}dataPath")
        dp.text = cf_def.get("path", cf_def.get("name", ""))

        if cf_def.get("expression"):
            expr = ET.SubElement(cf, f"{{{NS_DCS}}}expression")
            expr.text = cf_def["expression"]

        if cf_def.get("title"):
            title = ET.SubElement(cf, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = cf_def["title"]

    def _write_total_field(self, parent: ET.Element, tf_def: dict) -> None:
        """Записать итоговое поле (ресурс)."""
        tf = ET.SubElement(parent, f"{{{NS_DCS}}}totalField")
        dp = ET.SubElement(tf, f"{{{NS_DCS}}}dataPath")
        dp.text = tf_def.get("path", tf_def.get("name", ""))

        if tf_def.get("expression"):
            expr = ET.SubElement(tf, f"{{{NS_DCS}}}expression")
            expr.text = tf_def["expression"]

        if tf_def.get("group"):
            grp = ET.SubElement(tf, f"{{{NS_DCS}}}group")
            grp.text = tf_def["group"]

    def _write_parameter(self, parent: ET.Element, param_def: dict) -> None:
        """Записать параметр СКД."""
        p = ET.SubElement(parent, f"{{{NS_DCS}}}parameter")
        n = ET.SubElement(p, f"{{{NS_DCS}}}name")
        n.text = param_def.get("name", "")

        if param_def.get("title"):
            title = ET.SubElement(p, f"{{{NS_DCS}}}title")
            item = ET.SubElement(title, f"{{{NS_V8}}}item")
            content = ET.SubElement(item, f"{{{NS_V8}}}content")
            content.text = param_def["title"]

        # Type
        type_str = param_def.get("type", "String")
        value_type = ET.SubElement(p, f"{{{NS_DCS}}}valueType")
        type_container = ET.SubElement(value_type, f"{{{NS_V8}}}Type")
        type_container.text = f"xs:{'string' if type_str == 'String' else 'decimal' if type_str == 'Number' else 'boolean' if type_str == 'Boolean' else 'dateTime'}"


# ============================================================================
# ФАСАД — DslCompiler
# ============================================================================

class DslCompiler:
    """Единый фасад для всех компиляторов DSL."""

    def __init__(self):
        self.meta = MetaCompiler()
        self.form = FormCompiler()
        self.skd = SkdCompiler()

    def compile_meta(
        self,
        definition: Union[str, dict, Path],
        output_dir: Union[str, Path],
    ) -> CompileResult:
        """Компилировать объект метаданных (Catalog, Document, и т.д.)."""
        return self.meta.compile(definition, output_dir)

    def compile_form(
        self,
        definition: Union[str, dict, Path],
        output_path: Union[str, Path],
    ) -> CompileResult:
        """Компилировать управляемую форму."""
        return self.form.compile(definition, output_path)

    def compile_skd(
        self,
        definition: Union[str, dict, Path],
        output_path: Union[str, Path],
    ) -> CompileResult:
        """Компилировать схему компоновки данных (СКД)."""
        return self.skd.compile(definition, output_path)
