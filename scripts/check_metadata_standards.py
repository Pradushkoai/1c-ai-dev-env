#!/usr/bin/env python3
"""
check_metadata_standards.py — Проверка метаданных конфигурации 1С.

В отличие от check_1c_standards.py (который проверяет .bsl файлы),
этот скрипт проверяет XML метаданные конфигурации:
- Синонимы объектов (должны быть заполнены)
- Комментарии общих модулей
- Имена объектов (без пробелов, осмысленные)
- Свойства Configuration.xml (Vendor, Version, CompatibilityMode)
- Формы справочников (должны быть DefaultListForm, DefaultObjectForm)
- Уникальность кодов (CheckUnique)
- NamePrefix конфигурации

Основано на:
- ITS standard 01: Создание и изменение объектов метаданных
- ITS standard 04: Соглашения при написании кода
- ITS standard 16: Требования к конфигурациям

Использование:
    python3 check_metadata_standards.py <config_dir>

Пример:
    python3 check_metadata_standards.py data/configs/priemka
"""
from __future__ import annotations

import os
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class MetadataViolation:
    """Одно нарушение стандарта в метаданных."""
    file: str
    object_type: str
    object_name: str
    rule_id: str
    severity: str
    message: str

    def format_text(self) -> str:
        return (
            f"  {self.severity.upper():7} {self.rule_id:30} "
            f"{self.object_type}.{self.object_name}  {self.message}"
        )


def _strip_ns(tag: str) -> str:
    """Убирает namespace из тега."""
    return tag.split("}")[1] if "}" in tag else tag


def _get_child(elem, tag: str):
    """Находит дочерний элемент по имени тега (без namespace)."""
    if elem is None:
        return None
    for child in elem:
        if _strip_ns(child.tag) == tag:
            return child
    return None


def _get_text(elem, tag: str, default: str = "") -> str:
    """Возвращает текст дочернего элемента."""
    child = _get_child(elem, tag)
    if child is not None:
        return (child.text or "").strip()
    return default


def _get_synonym(elem) -> str:
    """Извлекает синоним из элемента Properties."""
    syn = _get_child(elem, "Synonym")
    if syn is None:
        return ""
    # Пустой тег <Synonym/> → ""
    content = _get_child(syn, "content")
    if content is not None:
        return (content.text or "").strip()
    # v8:item структура
    for item in syn:
        if _strip_ns(item.tag) == "item":
            c = _get_child(item, "content")
            if c is not None:
                return (c.text or "").strip()
    return ""


def _parse_object_xml(xml_path: Path) -> tuple[str, str, ET.Element | None]:
    """
    Парсит XML файл метаданных.
    Возвращает (object_type, object_name, properties_element).
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return ("", "", None)
    except Exception:
        return ("", "", None)

    # Ищем элемент метаданных (Catalog, Document, CommonModule, и т.д.)
    for child in root:
        tag = _strip_ns(child.tag)
        # Пропускаем внутренние элементы
        if tag in ("InternalInfo", "ChildObjects"):
            continue
        # Это элемент объекта метаданных
        if tag not in ("Properties", "Form", "Template", "Command"):
            props = _get_child(child, "Properties")
            name = _get_text(props, "Name") if props is not None else ""
            return (tag, name, props)

    return ("", "", None)


def check_metadata(config_dir: Path) -> list[MetadataViolation]:
    """
    Проверяет метаданные конфигурации.

    Args:
        config_dir: Путь к папке конфигурации (с Configuration.xml)

    Returns:
        Список нарушений
    """
    violations = []

    # 1. Проверка Configuration.xml
    config_xml = config_dir / "Configuration.xml"
    if config_xml.exists():
        violations.extend(_check_configuration(config_xml))

    # 2. Проверка всех объектов метаданных
    type_dirs = {
        "Catalogs": "Catalog",
        "Documents": "Document",
        "CommonModules": "CommonModule",
        "InformationRegisters": "InformationRegister",
        "AccumulationRegisters": "AccumulationRegister",
        "Reports": "Report",
        "DataProcessors": "DataProcessor",
        "Constants": "Constant",
        "Enums": "Enum",
        "CommonForms": "CommonForm",
        "CommonCommands": "CommonCommand",
        "Subsystems": "Subsystem",
        "ExchangePlans": "ExchangePlan",
    }

    for dir_name, obj_type in type_dirs.items():
        type_dir = config_dir / dir_name
        if not type_dir.exists():
            continue
        for xml_file in sorted(type_dir.glob("*.xml")):
            violations.extend(_check_object(xml_file, obj_type))

    return violations


def _check_configuration(config_path: Path) -> list[MetadataViolation]:
    """Проверка Configuration.xml."""
    violations = []
    _, _, props = _parse_object_xml(config_path)
    if props is None:
        return violations

    obj_name = _get_text(props, "Name", "Конфигурация")

    # Vendor должен быть заполнен (STD 16)
    vendor = _get_text(props, "Vendor")
    if not vendor:
        violations.append(MetadataViolation(
            file=str(config_path), object_type="Configuration",
            object_name=obj_name,
            rule_id="empty-vendor",
            severity="warning",
            message="Vendor не указан — заполните свойство (STD 16)",
        ))

    # Version должна быть заполнена (STD 16)
    version = _get_text(props, "Version")
    if not version:
        violations.append(MetadataViolation(
            file=str(config_path), object_type="Configuration",
            object_name=obj_name,
            rule_id="empty-version",
            severity="warning",
            message="Version не указана — заполните свойство (STD 16)",
        ))

    # NamePrefix должен быть заполнен (STD 01)
    name_prefix = _get_text(props, "NamePrefix")
    if not name_prefix:
        violations.append(MetadataViolation(
            file=str(config_path), object_type="Configuration",
            object_name=obj_name,
            rule_id="empty-name-prefix",
            severity="warning",
            message="NamePrefix не указан — нужен префикс для избежания конфликтов (STD 01)",
        ))

    # CompatibilityMode должен быть указан (STD 01)
    compat = _get_text(props, "CompatibilityMode")
    if not compat:
        violations.append(MetadataViolation(
            file=str(config_path), object_type="Configuration",
            object_name=obj_name,
            rule_id="empty-compatibility-mode",
            severity="warning",
            message="CompatibilityMode не указан — укажите версию совместимости (STD 01)",
        ))

    # ScriptVariant должен быть Russian (STD 04)
    script = _get_text(props, "ScriptVariant")
    if script and script != "Russian":
        violations.append(MetadataViolation(
            file=str(config_path), object_type="Configuration",
            object_name=obj_name,
            rule_id="non-russian-script",
            severity="warning",
            message=f"ScriptVariant={script} — рекомендуется Russian (STD 04)",
        ))

    return violations


def _check_object(xml_path: Path, obj_type: str) -> list[MetadataViolation]:
    """Проверка объекта метаданных."""
    violations = []
    parsed_type, obj_name, props = _parse_object_xml(xml_path)
    if props is None or not obj_name:
        return violations

    # Используем распарсенный тип если он определён
    actual_type = parsed_type or obj_type

    # 1. Синоним должен быть заполнен (STD 01)
    synonym = _get_synonym(props)
    if not synonym:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type=actual_type,
            object_name=obj_name,
            rule_id="empty-synonym",
            severity="warning",
            message=f"Синоним не заполнен — добавьте пользовательское название (STD 01)",
        ))

    # 2. Имя не должно содержать пробелы (STD 01)
    if " " in obj_name:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type=actual_type,
            object_name=obj_name,
            rule_id="name-with-spaces",
            severity="error",
            message="Имя содержит пробелы — недопустимо (STD 01)",
        ))

    # 3. Имя не должно начинаться с цифры (STD 01)
    if obj_name and obj_name[0].isdigit():
        violations.append(MetadataViolation(
            file=str(xml_path), object_type=actual_type,
            object_name=obj_name,
            rule_id="name-starts-with-digit",
            severity="error",
            message="Имя начинается с цифры — недопустимо (STD 01)",
        ))

    # 4. Специфичные проверки для Catalog
    if actual_type == "Catalog":
        violations.extend(_check_catalog(xml_path, obj_name, props))

    # 5. Специфичные проверки для CommonModule
    if actual_type == "CommonModule":
        violations.extend(_check_common_module(xml_path, obj_name, props))

    # 6. Специфичные проверки для Document
    if actual_type == "Document":
        violations.extend(_check_document(xml_path, obj_name, props))

    # 7. Специфичные проверки для InformationRegister
    if actual_type == "InformationRegister":
        violations.extend(_check_info_register(xml_path, obj_name, props))

    return violations


def _check_catalog(xml_path: Path, name: str, props: ET.Element) -> list[MetadataViolation]:
    """Проверки для справочников."""
    violations = []

    # CheckUnique должен быть true если есть код (STD 01)
    code_length = _get_text(props, "CodeLength", "0")
    check_unique = _get_text(props, "CheckUnique", "false")
    if int(code_length) > 0 and check_unique.lower() != "true":
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="Catalog",
            object_name=name,
            rule_id="catalog-no-check-unique",
            severity="warning",
            message="CheckUnique=false при наличии кода — должна быть проверка уникальности (STD 01)",
        ))

    # Должна быть DefaultListForm (STD 01)
    default_list_form = _get_text(props, "DefaultListForm")
    if not default_list_form:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="Catalog",
            object_name=name,
            rule_id="catalog-no-list-form",
            severity="warning",
            message="DefaultListForm не указана — добавьте форму списка (STD 01)",
        ))

    # Должна быть DefaultObjectForm (STD 01)
    default_obj_form = _get_text(props, "DefaultObjectForm")
    if not default_obj_form:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="Catalog",
            object_name=name,
            rule_id="catalog-no-object-form",
            severity="warning",
            message="DefaultObjectForm не указана — добавьте форму элемента (STD 01)",
        ))

    return violations


def _check_common_module(xml_path: Path, name: str, props: ET.Element) -> list[MetadataViolation]:
    """Проверки для общих модулей."""
    violations = []

    # Comment должен быть заполнен (STD 04)
    comment = _get_text(props, "Comment")
    if not comment:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="CommonModule",
            object_name=name,
            rule_id="module-no-comment",
            severity="warning",
            message="Comment не заполнен — добавьте описание назначения модуля (STD 04)",
        ))

    # Синоним должен быть заполнен (STD 01)
    synonym = _get_synonym(props)
    if not synonym:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="CommonModule",
            object_name=name,
            rule_id="module-no-synonym",
            severity="warning",
            message="Синоним не заполнен — добавьте пользовательское название (STD 01)",
        ))

    # Проверка суффиксов имени (STD 04)
    # Серверные модули должны иметь суффикс ...Сервер
    # Клиентские — ...Клиент
    # ВызовСервера — ...ВызовСервера
    server = _get_text(props, "Server", "false").lower() == "true"
    server_call = _get_text(props, "ServerCall", "false").lower() == "true"
    client_managed = _get_text(props, "ClientManagedApplication", "false").lower() == "true"

    if server and not server_call and not client_managed:
        # Только серверный модуль — должен иметь суффикс Сервер
        if not name.endswith("Сервер") and not name.endswith("Server"):
            violations.append(MetadataViolation(
                file=str(xml_path), object_type="CommonModule",
                object_name=name,
                rule_id="module-server-no-suffix",
                severity="warning",
                message="Серверный модуль без суффикса 'Сервер' — добавьте для ясности (STD 04)",
            ))

    if client_managed and not server:
        # Клиентский модуль — должен иметь суффикс Клиент
        if not name.endswith("Клиент") and not name.endswith("Client"):
            violations.append(MetadataViolation(
                file=str(xml_path), object_type="CommonModule",
                object_name=name,
                rule_id="module-client-no-suffix",
                severity="warning",
                message="Клиентский модуль без суффикса 'Клиент' — добавьте для ясности (STD 04)",
            ))

    if server_call:
        # Модуль с ServerCall — должен иметь суффикс ВызовСервера
        if not name.endswith("ВызовСервера") and not name.endswith("ServerCall"):
            violations.append(MetadataViolation(
                file=str(xml_path), object_type="CommonModule",
                object_name=name,
                rule_id="module-servercall-no-suffix",
                severity="warning",
                message="Модуль с ServerCall без суффикса 'ВызовСервера' — добавьте (STD 04)",
            ))

    return violations


def _check_document(xml_path: Path, name: str, props: ET.Element) -> list[MetadataViolation]:
    """Проверки для документов."""
    violations = []

    # Должна быть DefaultListForm
    default_list_form = _get_text(props, "DefaultListForm")
    if not default_list_form:
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="Document",
            object_name=name,
            rule_id="document-no-list-form",
            severity="warning",
            message="DefaultListForm не указана — добавьте форму списка (STD 01)",
        ))

    # Номер должен быть уникальным
    num_length = _get_text(props, "NumberLength", "0")
    check_unique = _get_text(props, "CheckUnique", "true")
    if int(num_length) > 0 and check_unique.lower() != "true":
        violations.append(MetadataViolation(
            file=str(xml_path), object_type="Document",
            object_name=name,
            rule_id="document-no-check-unique",
            severity="warning",
            message="CheckUnique=false при наличии номера — должна быть проверка (STD 01)",
        ))

    return violations


def _check_info_register(xml_path: Path, name: str, props: ET.Element) -> list[MetadataViolation]:
    """Проверки для регистров сведений."""
    violations = []

    # Записи должны иметь периодичность если это не с независимым режимом
    # Проверка наличия Dimensions для регистров с периодичностью
    periodicity = _get_text(props, "Periodicity", "")
    if periodicity and periodicity != "Nonperiodic":
        # Для периодических регистров рекомендуется иметь измерения
        pass  # Слишком сложно для автоматической проверки

    return violations


def format_violations(violations: list[MetadataViolation], output_format: str = "text") -> str:
    """Форматировать вывод."""
    if output_format == "json":
        return json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2)

    if not violations:
        return "✅ Нарушений в метаданных не найдено."

    from collections import defaultdict
    by_type = defaultdict(list)
    for v in violations:
        by_type[v.object_type].append(v)

    lines = []
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    lines.append(f"Найдено: {errors} errors, {warnings} warnings в {len(by_type)} типах объектов")
    lines.append("")

    for obj_type in sorted(by_type.keys()):
        lines.append(f"📋 {obj_type} ({len(by_type[obj_type])} нарушений)")
        for v in by_type[obj_type]:
            lines.append(v.format_text())
        lines.append("")

    return "\n".join(lines)


def main():
    import json
    if len(sys.argv) < 2:
        print("Использование: python3 check_metadata_standards.py <config_dir>")
        print()
        print("Пример:")
        print("  python3 check_metadata_standards.py data/configs/priemka")
        sys.exit(1)

    config_dir = Path(sys.argv[1])
    if not config_dir.exists():
        print(f"❌ Папка не найдена: {config_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Проверка метаданных: {config_dir}")
    print()

    violations = check_metadata(config_dir)
    print(format_violations(violations))

    has_errors = any(v.severity == "error" for v in violations)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
