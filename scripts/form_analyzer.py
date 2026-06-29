#!/usr/bin/env python3
"""
form_analyzer.py — Полный парсер форм 1С из XML выгрузки Конфигуратора.

Извлекает из Form.xml:
- Все элементы формы (InputField, Button, Table, UsualGroup, и т.д.)
- Свойства элементов (name, id, title, data_path, visible, enabled)
- События и обработчики (Events/Event)
- Команды (CommandName, AutoCommandBar)
- Группировку (ChildItems — дерево элементов)
- Контекстные меню (ContextMenu)
- Расширенные подсказки (ExtendedTooltip)

Создаёт form-index.json для каждой конфигурации.
"""
from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def strip_ns(tag: str) -> str:
    return tag.split('}')[1] if '}' in tag else tag


def get_child(elem, tag: str):
    if elem is None:
        return None
    for child in elem:
        if strip_ns(child.tag) == tag:
            return child
    return None


def get_children(elem, tag: str):
    if elem is None:
        return []
    return [child for child in elem if strip_ns(child.tag) == tag]


def get_text(elem, tag: str, default: str = '') -> str:
    child = get_child(elem, tag)
    if child is not None:
        return child.text or ''
    return default


def get_local_string(elem) -> str:
    """Извлекает локализованную строку."""
    if elem is None:
        return ''
    for item in elem:
        if strip_ns(item.tag) == 'item':
            content = get_text(item, 'content')
            if content:
                return content
    return ''


# ============================================================================
# ТИПЫ ЭЛЕМЕНТОВ ФОРМЫ
# ============================================================================

# Все типы элементов формы 1С
FORM_ELEMENT_TYPES = {
    'InputField', 'LabelField', 'Button', 'UsualGroup',
    'Pages', 'Page', 'Table', 'CheckBox', 'RadioButton',
    'ProgressBar', 'Picture', 'Calendar', 'Chart',
    'SpreadSheetDocument', 'TextDocument', 'HTMLDocument',
    'CommandBar', 'ContextMenu', 'AutoCommandBar',
    'ExtendedTooltip', 'SearchStringAddition',
    'ViewStatusAddition', 'SearchControlAddition',
    'Label', 'GroupBox', 'Popup', 'CommandGroup',
    'Field', 'Column', 'Format', 'ToolTip', 'Title',
}

# Основные типы (для краткой статистики)
MAIN_ELEMENT_TYPES = {
    'InputField', 'LabelField', 'Button', 'UsualGroup',
    'Pages', 'Page', 'Table', 'CheckBox', 'RadioButton',
    'ProgressBar', 'Picture', 'Calendar', 'Chart',
    'SpreadSheetDocument', 'TextDocument', 'HTMLDocument',
    'CommandBar', 'AutoCommandBar',
}


# ============================================================================
# ПАРСЕР ЭЛЕМЕНТА ФОРМЫ
# ============================================================================

def parse_form_element(elem) -> dict:
    """Парсит один элемент формы (рекурсивно с ChildItems).

    Args:
        elem: XML элемент (InputField, Button, Table, и т.д.)

    Returns:
        dict: {type, name, id, title, data_path, events, children, ...}
    """
    tag = strip_ns(elem.tag)
    name = elem.get('name', '')
    elem_id = elem.get('id', '')

    result = {
        'type': tag,
        'name': name,
        'id': elem_id,
        'title': '',
        'data_path': '',
        'visible': True,
        'enabled': True,
        'read_only': False,
        'command_name': '',
        'events': [],
        'children': [],
    }

    # Title
    title_elem = get_child(elem, 'Title')
    if title_elem is not None:
        result['title'] = get_local_string(title_elem)

    # DataPath
    result['data_path'] = get_text(elem, 'DataPath')

    # Visible / Enabled / ReadOnly
    visible = get_text(elem, 'Visible')
    if visible == 'false':
        result['visible'] = False
    enabled = get_text(elem, 'Enabled')
    if enabled == 'false':
        result['enabled'] = False
    read_only = get_text(elem, 'ReadOnly')
    if read_only == 'true':
        result['read_only'] = True

    # CommandName (для кнопок)
    result['command_name'] = get_text(elem, 'CommandName')

    # Events
    events_elem = get_child(elem, 'Events')
    if events_elem is not None:
        for event in events_elem:
            if strip_ns(event.tag) == 'Event':
                event_name = event.get('name', '')
                handler = event.text or ''
                result['events'].append({
                    'event': event_name,
                    'handler': handler,
                })

    # ChildItems — рекурсивно
    child_items = get_child(elem, 'ChildItems')
    if child_items is not None:
        for child in child_items:
            child_tag = strip_ns(child.tag)
            if child_tag in MAIN_ELEMENT_TYPES or child_tag in FORM_ELEMENT_TYPES:
                result['children'].append(parse_form_element(child))

    return result


# ============================================================================
# ПАРСЕР ФОРМЫ
# ============================================================================

def parse_form(xml_path: Path) -> dict:
    """Парсит Form.xml — форму 1С.

    Args:
        xml_path: Путь к Form.xml

    Returns:
        dict: {window_opening_mode, auto_command_bar, items[], events[]}
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return {'error': f'Parse error: {e}'}

    # Проверяем что это форма
    if strip_ns(root.tag) != 'Form':
        return {'error': 'Not a Form'}

    result = {
        'file': str(xml_path),
        'window_opening_mode': get_text(root, 'WindowOpeningMode'),
        'items': [],
        'events': [],
        'element_count': 0,
    }

    # События формы (на уровне формы)
    events_elem = get_child(root, 'Events')
    if events_elem is not None:
        for event in events_elem:
            if strip_ns(event.tag) == 'Event':
                result['events'].append({
                    'event': event.get('name', ''),
                    'handler': event.text or '',
                })

    # AutoCommandBar на уровне формы
    auto_cmd = get_child(root, 'AutoCommandBar')
    if auto_cmd is not None:
        result['auto_command_bar'] = auto_cmd.get('name', '')

    # ChildItems — основные элементы формы
    child_items = get_child(root, 'ChildItems')
    if child_items is not None:
        for child in child_items:
            child_tag = strip_ns(child.tag)
            if child_tag in MAIN_ELEMENT_TYPES or child_tag in FORM_ELEMENT_TYPES:
                result['items'].append(parse_form_element(child))

    # Считаем все элементы (рекурсивно)
    def count_elements(items):
        count = len(items)
        for item in items:
            count += count_elements(item.get('children', []))
        return count

    result['element_count'] = count_elements(result['items'])

    return result


# ============================================================================
# ПОИСК ФОРМ В КОНФИГУРАЦИИ
# ============================================================================

def find_all_forms(config_dir: Path) -> list[dict]:
    """Находит все формы в конфигурации.

    Ищет:
    - CommonForms/<Имя>/Ext/Form.xml
    - <ТипОбъекта>/<Имя>/Forms/<ИмяФормы>/Ext/Form.xml
    - <ТипОбъекта>/<Имя>/Ext/Form/Form.xml (для обработок без папки Forms)

    Returns:
        [{name, parent_type, parent_name, file, form}, ...]
    """
    config_dir = Path(config_dir)
    forms = []

    # Типы объектов, у которых могут быть формы
    object_types = [
        'Catalogs', 'Documents', 'DataProcessors', 'Reports',
        'InformationRegisters', 'AccumulationRegisters',
        'ChartsOfAccounts', 'ChartsOfCharacteristicTypes',
        'BusinessProcesses', 'Tasks', 'ExchangePlans',
        'Enums', 'FilterCriteria', 'Constants',
        'CalculationRegisters', 'AccountingRegisters',
        'DocumentJournals',
    ]

    # 1. CommonForms
    common_forms_dir = config_dir / 'CommonForms'
    if common_forms_dir.exists():
        for form_dir in sorted(common_forms_dir.iterdir()):
            if not form_dir.is_dir():
                continue
            form_xml = form_dir / 'Ext' / 'Form.xml'
            if form_xml.exists():
                form_data = parse_form(form_xml)
                if 'error' not in form_data:
                    forms.append({
                        'name': form_dir.name,
                        'parent_type': 'CommonForm',
                        'parent_name': '',
                        'file': str(form_xml),
                        'form': form_data,
                    })

    # 2. Формы объектов
    for obj_type in object_types:
        type_dir = config_dir / obj_type
        if not type_dir.exists():
            continue
        for obj_dir in sorted(type_dir.iterdir()):
            if not obj_dir.is_dir():
                continue
            obj_name = obj_dir.name

            # Forms/<ИмяФормы>/Ext/Form.xml
            forms_dir = obj_dir / 'Forms'
            if forms_dir.exists():
                for form_dir in sorted(forms_dir.iterdir()):
                    if not form_dir.is_dir():
                        continue
                    form_xml = form_dir / 'Ext' / 'Form.xml'
                    if form_xml.exists():
                        form_data = parse_form(form_xml)
                        if 'error' not in form_data:
                            forms.append({
                                'name': form_dir.name,
                                'parent_type': obj_type,
                                'parent_name': obj_name,
                                'file': str(form_xml),
                                'form': form_data,
                            })

            # Ext/Form/Form.xml (форма без папки Forms)
            direct_form = obj_dir / 'Ext' / 'Form' / 'Form.xml'
            if direct_form.exists():
                form_data = parse_form(direct_form)
                if 'error' not in form_data:
                    forms.append({
                        'name': 'Форма',
                        'parent_type': obj_type,
                        'parent_name': obj_name,
                        'file': str(direct_form),
                        'form': form_data,
                    })

    return forms


def build_form_index(config_dir: Path | str, output_path: Path | str) -> dict:
    """Строит индекс всех форм в конфигурации.

    Args:
        config_dir: Путь к директории конфигурации
        output_path: Куда сохранить form-index.json

    Returns:
        Статистика
    """
    config_dir = Path(config_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Поиск форм в: {config_dir}")
    forms = find_all_forms(config_dir)

    print(f"\n✅ Найдено форм: {len(forms)}")

    # Статистика
    stats = {
        'total_forms': len(forms),
        'by_parent_type': {},
        'total_elements': 0,
        'total_events': 0,
        'element_types': {},
    }

    for f in forms:
        parent_type = f['parent_type']
        stats['by_parent_type'][parent_type] = stats['by_parent_type'].get(parent_type, 0) + 1
        form = f['form']
        stats['total_elements'] += form.get('element_count', 0)
        stats['total_events'] += len(form.get('events', []))

        # Подсчёт типов элементов
        def count_element_types(items):
            for item in items:
                t = item.get('type', '')
                stats['element_types'][t] = stats['element_types'].get(t, 0) + 1
                count_element_types(item.get('children', []))

        count_element_types(form.get('items', []))

    print(f"   По типам родителей:")
    for pt, count in sorted(stats['by_parent_type'].items()):
        print(f"     {pt}: {count}")
    print(f"   Всего элементов: {stats['total_elements']}")
    print(f"   Всего событий: {stats['total_events']}")
    print(f"   Типы элементов:")
    for et, count in sorted(stats['element_types'].items(), key=lambda x: -x[1])[:10]:
        print(f"     {et}: {count}")

    # Сохраняем
    result = {
        'stats': stats,
        'forms': forms,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в: {output_path} ({output_path.stat().st_size // 1024} КБ)")

    return stats


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 form_analyzer.py <config_dir> [output_path]")
        print()
        print("Пример:")
        print("  python3 form_analyzer.py data/configs/ut11 derived/configs/ut11/form-index.json")
        sys.exit(1)

    config_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'form-index.json'

    build_form_index(config_dir, output)


if __name__ == '__main__':
    main()
