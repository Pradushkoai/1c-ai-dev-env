#!/usr/bin/env python3
"""
Патч для build_api_reference.py — добавляет индексацию модулей форм.

Добавляет обработку:
1. CommonForms/<Имя>/Ext/Form/Module.bsl — общие формы
2. <ТипОбъекта>/<Имя>/Forms/<ИмяФормы>/Ext/Form/Module.bsl — формы объектов
3. <ТипОбъекта>/<Имя>/Ext/Form/Module.bsl — формы обработки (если есть)

Формы добавляются в api-reference.json с type='Форма' и category='Формы'.
"""
import re
import os
import json
from pathlib import Path

# Папки типов объектов, где могут быть формы
OBJECT_TYPES_WITH_FORMS = [
    'Documents', 'Catalogs', 'DataProcessors', 'Reports',
    'InformationRegisters', 'AccumulationRegisters', 'ChartsOfAccounts',
    'ChartsOfCharacteristicTypes', 'BusinessProcesses', 'Tasks',
    'ExchangePlans', 'FilterCriteria',
]


def find_form_modules(config_dir):
    """Находит все модули форм в конфигурации.
    
    Возвращает список: [{name, bsl_path, xml_path, parent_type, parent_name, form_name}]
    """
    forms = []
    config_dir = Path(config_dir)

    # 1. CommonForms/<Имя>/Ext/Form/Module.bsl
    common_forms_dir = config_dir / 'CommonForms'
    if common_forms_dir.exists():
        for item in sorted(common_forms_dir.iterdir()):
            if not item.is_dir():
                continue
            bsl_path = item / 'Ext' / 'Form' / 'Module.bsl'
            xml_path = item / 'Ext' / 'Form.xml'
            meta_xml = common_forms_dir / f'{item.name}.xml'
            if bsl_path.exists():
                forms.append({
                    'name': f'Форма.{item.name}',
                    'bsl_path': str(bsl_path),
                    'xml_path': str(xml_path if xml_path.exists() else meta_xml if meta_xml.exists() else ''),
                    'parent_type': 'CommonForm',
                    'parent_name': item.name,
                    'form_name': item.name,
                })

    # 2. Forms внутри объектов
    for obj_type in OBJECT_TYPES_WITH_FORMS:
        obj_dir = config_dir / obj_type
        if not obj_dir.exists():
            continue
        for obj_item in sorted(obj_dir.iterdir()):
            if not obj_item.is_dir():
                continue
            # <Тип>/<ИмяОбъекта>/Forms/<ИмяФормы>/Ext/Form/Module.bsl
            forms_dir = obj_item / 'Forms'
            if forms_dir.exists():
                for form_item in sorted(forms_dir.iterdir()):
                    if not form_item.is_dir():
                        continue
                    bsl_path = form_item / 'Ext' / 'Form' / 'Module.bsl'
                    xml_path = form_item / 'Ext' / 'Form.xml'
                    if bsl_path.exists():
                        forms.append({
                            'name': f'{obj_item.name}.{form_item.name}',
                            'bsl_path': str(bsl_path),
                            'xml_path': str(xml_path if xml_path.exists() else ''),
                            'parent_type': obj_type,
                            'parent_name': obj_item.name,
                            'form_name': form_item.name,
                        })
            # <Тип>/<ИмяОбъекта>/Ext/Form/Module.bsl (форма обработки)
            direct_form_bsl = obj_item / 'Ext' / 'Form' / 'Module.bsl'
            if direct_form_bsl.exists():
                # Проверим что не дубль с Forms/
                already = any(f['parent_name'] == obj_item.name and f['form_name'] == obj_item.name 
                             for f in forms)
                if not already:
                    forms.append({
                        'name': f'{obj_item.name}.Форма',
                        'bsl_path': str(direct_form_bsl),
                        'xml_path': str(obj_item / 'Ext' / 'Form.xml'),
                        'parent_type': obj_type,
                        'parent_name': obj_item.name,
                        'form_name': 'Форма',
                    })

    return forms


def parse_form_xml(xml_path):
    """Парсит XML формы — извлекает элементы формы (кнопки, поля, группы).
    
    Возвращает: {elements: [{name, type, title, data_path}]}
    """
    if not xml_path or not os.path.exists(xml_path):
        return {'elements': []}

    import xml.etree.ElementTree as ET

    def strip_ns(tag):
        return tag.split('}')[1] if '}' in tag else tag

    elements = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Ищем все элементы формы
        for elem in root.iter():
            tag = strip_ns(elem.tag)
            name = elem.get('name', '')
            if not name:
                continue

            if tag in ('InputField', 'LabelField', 'Button', 'UsualGroup',
                       'Pages', 'Page', 'Table', 'CheckBox', 'RadioButton',
                       'ProgressBar', 'Picture', 'Calendar', 'Chart',
                       'SpreadSheetDocument', 'TextDocument', 'HTMLDocument',
                       'CommandBar', 'ContextMenu', 'AutoCommandBar',
                       'ExtendedTooltip', 'SearchStringAddition',
                       'ViewStatusAddition', 'SearchControlAddition'):
                # Получаем title
                title = ''
                title_elem = None
                for child in elem:
                    if strip_ns(child.tag) == 'Title':
                        title = child.text or ''
                        break

                # Получаем DataPath
                data_path = ''
                for child in elem:
                    if strip_ns(child.tag) == 'DataPath':
                        data_path = child.text or ''
                        break

                # Получаем CommandName (для кнопок)
                command_name = ''
                for child in elem:
                    if strip_ns(child.tag) == 'CommandName':
                        command_name = child.text or ''
                        break

                elements.append({
                    'name': name,
                    'type': tag,
                    'title': title,
                    'data_path': data_path,
                    'command': command_name,
                })
    except Exception:
        pass

    return {'elements': elements}


# ============================================================================
# Интеграция в build_api_reference
# ============================================================================

def add_forms_to_api_reference(config_dir, modules_list, parse_bsl_func):
    """Добавляет модули форм в список modules_list.
    
    Args:
        config_dir: Путь к директории конфигурации
        modules_list: Существующий список модулей (изменяется in-place)
        parse_bsl_func: Функция парсинга BSL (parse_module_bsl из build_api_reference)
    
    Returns:
        Кол-во добавленных форм
    """
    forms = find_form_modules(config_dir)
    added = 0

    for form in forms:
        bsl_path = form['bsl_path']
        if not os.path.exists(bsl_path):
            continue

        # Парсим BSL модуль формы
        methods = parse_bsl_func(bsl_path)

        # Парсим XML формы (элементы)
        form_info = parse_form_xml(form['xml_path'])

        modules_list.append({
            'name': form['name'],
            'synonym': form['form_name'],
            'comment': f'Форма: {form["parent_type"]}.{form["parent_name"]}',
            'type': 'Форма',
            'category': 'Формы',
            'properties': {
                'global': False,
                'server': False,
                'client_managed': True,
                'server_call': False,
                'privileged': False,
                'external_connection': False,
            },
            'methods': methods,
            'methods_count': len(methods),
            'form_elements': form_info['elements'],
            'form_elements_count': len(form_info['elements']),
            'parent_type': form['parent_type'],
            'parent_name': form['parent_name'],
        })
        added += 1

    return added


if __name__ == '__main__':
    # Тестовый запуск
    import sys
    if len(sys.argv) < 2:
        print("Использование: python3 form_indexer.py <config_dir>")
        sys.exit(1)

    config_dir = sys.argv[1]
    forms = find_form_modules(config_dir)
    print(f"Найдено форм с модулями: {len(forms)}")
    for f in forms:
        print(f"  {f['name']} ({f['parent_type']}.{f['parent_name']})")
        print(f"    BSL: {f['bsl_path']}")
        print(f"    XML: {f['xml_path']}")

        # Парсим элементы формы
        form_info = parse_form_xml(f['xml_path'])
        if form_info['elements']:
            print(f"    Элементов формы: {len(form_info['elements'])}")
            for elem in form_info['elements'][:5]:
                print(f"      {elem['type']}: {elem['name']} — {elem.get('title','')[:40]}")
        print()
