#!/usr/bin/env python3
"""
skd_parser.py — Парсер СКД-схем (Схем Компоновки Данных) 1С.

СКД — это XML-формат 1С для декларативного описания отчётов.
Namespace: http://v8.1c.ru/8.1/data-composition-system/schema

Извлекает из СКД-схемы:
- Источники данных (dataSources)
- Наборы данных (dataSets): запросы, объединения
- Поля наборов данных (fields)
- Параметры (parameters) с типами и значениями
- Отборы/фильтры (filters)
- Группировки (groupings)
- Итоговые поля (totalFields)
- Условное оформление (conditionalAppearance)

Где искать СКД-схемы:
1. Reports/<Имя>/Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml
2. CommonTemplates/<Имя>/Ext/Template.xml (если тип = DataCompositionSchema)
3. DataProcessors/<Имя>/Templates/<Имя>/Ext/Template.xml

Создаёт skd-index.json для каждой конфигурации.
"""
from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


# ============================================================================
# УТИЛИТЫ (такие же как в metadata_parser.py)
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
    """Извлекает локализованную строку из <v8:item><v8:content>Текст</v8:content></v8:item>."""
    if elem is None:
        return ''
    for item in elem:
        if strip_ns(item.tag) == 'item':
            content = get_text(item, 'content')
            if content:
                return content
    return ''


# ============================================================================
# ПАРСЕРЫ ЭЛЕМЕНТОВ СКД
# ============================================================================

def parse_data_source(elem) -> dict:
    """Парсит <dataSource> — источник данных."""
    return {
        'name': get_text(elem, 'name'),
        'type': get_text(elem, 'dataSourceType'),  # Local, Remote
        'connection_string': get_text(elem, 'connectionString'),
    }


def parse_data_set_field(elem) -> dict:
    """Парсит <field> — поле набора данных."""
    return {
        'data_path': get_text(elem, 'dataPath'),
        'field': get_text(elem, 'field'),
        'title': get_local_string(get_child(elem, 'title')),
        'role': get_text(elem, 'role'),
    }


def parse_data_set(elem) -> dict:
    """Парсит <dataSet> — набор данных."""
    xsi_type = ''
    for attr_name, attr_val in elem.attrib.items():
        if 'type' in attr_name.lower():
            xsi_type = attr_val
            break

    result = {
        'name': get_text(elem, 'name'),
        'type': xsi_type,  # DataSetQuery, DataSetUnion, DataSetObject
        'data_source': get_text(elem, 'dataSource'),
        'fields': [],
        'query': '',
        'main_table': '',
    }

    # Поля
    for field_elem in get_children(elem, 'field'):
        result['fields'].append(parse_data_set_field(field_elem))

    # Запрос (для DataSetQuery)
    query = get_text(elem, 'query')
    if query:
        result['query'] = query.strip()
        # Извлекаем основную таблицу из запроса
        # Простой парсер: ищем "ИЗ Документ.Имя" или "ИЗ Справочник.Имя"
        import re
        m = re.search(r'\bИЗ\s+(Документ|Справочник|РегистрСведений|РегистрНакопления|РегистрБухгалтерии|РегистрРасчета)\.([^\s,\n]+)', query, re.IGNORECASE)
        if m:
            result['main_table'] = f'{m.group(1)}.{m.group(2)}'

    return result


def parse_parameter(elem) -> dict:
    """Парсит <parameter> — параметр СКД."""
    result = {
        'name': get_text(elem, 'name'),
        'title': get_local_string(get_child(elem, 'title')),
        'types': [],
        'use_restriction': get_text(elem, 'useRestriction') == 'true',
        'available_values': get_text(elem, 'availableValues'),
        'value': '',
        'expression': get_text(elem, 'expression'),
    }

    # Тип значения
    value_type = get_child(elem, 'valueType')
    if value_type is not None:
        for child in value_type:
            if strip_ns(child.tag) == 'Type':
                result['types'].append(child.text or '')

    # Значение по умолчанию
    value_elem = get_child(elem, 'value')
    if value_elem is not None and value_elem.text:
        result['value'] = value_elem.text

    return result


def parse_total_field(elem) -> dict:
    """Парсит <totalField> — итоговое поле."""
    return {
        'data_path': get_text(elem, 'dataPath'),
        'expression': get_text(elem, 'expression'),
    }


def parse_filter(elem) -> dict:
    """Парсит <filter> — отбор."""
    return {
        'name': get_text(elem, 'name'),
        'data_path': get_text(elem, 'dataPath'),
        'filter_usage': get_text(elem, 'filterUsage'),
    }


def parse_grouping(elem) -> dict:
    """Парсит группировку из <settings>."""
    return {
        'name': get_text(elem, 'name'),
        'data_path': get_text(elem, 'dataPath'),
    }


# ============================================================================
# ГЛАВНЫЙ ПАРСЕР СКД-СХЕМЫ
# ============================================================================

def parse_skd_schema(xml_path: Path) -> dict:
    """Парсит СКД-схему из XML файла.

    Args:
        xml_path: Путь к Template.xml (СКД-схема)

    Returns:
        dict: {data_sources, data_sets, parameters, total_fields, ...}
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return {'error': f'Parse error: {e}'}

    # Проверяем что это СКД-схема
    if 'data-composition-system/schema' not in (root.tag if '}' in root.tag else ''):
        return {'error': 'Not a DataCompositionSchema'}

    result = {
        'file': str(xml_path),
        'data_sources': [],
        'data_sets': [],
        'parameters': [],
        'total_fields': [],
        'filters': [],
    }

    # Источники данных
    for ds in get_children(root, 'dataSource'):
        result['data_sources'].append(parse_data_source(ds))

    # Наборы данных
    for dset in get_children(root, 'dataSet'):
        result['data_sets'].append(parse_data_set(dset))

    # Параметры
    for param in get_children(root, 'parameter'):
        result['parameters'].append(parse_parameter(param))

    # Итоговые поля
    for tf in get_children(root, 'totalField'):
        result['total_fields'].append(parse_total_field(tf))

    # Отборы
    for flt in get_children(root, 'filter'):
        result['filters'].append(parse_filter(flt))

    # Вычисляемые поля
    calculated_fields = []
    for cf in get_children(root, 'calculatedField'):
        calculated_fields.append({
            'name': get_text(cf, 'name'),
            'data_path': get_text(cf, 'dataPath'),
            'expression': get_text(cf, 'expression'),
        })
    result['calculated_fields'] = calculated_fields

    return result


# ============================================================================
# ПОИСК СКД-СХЕМ В КОНФИГУРАЦИИ
# ============================================================================

def find_skd_schemas(config_dir: Path) -> list[dict]:
    """Находит все СКД-схемы в конфигурации.

    Ищет в:
    - Reports/<Имя>/Templates/*/Ext/Template.xml
    - CommonTemplates/<Имя>/Ext/Template.xml
    - DataProcessors/<Имя>/Templates/*/Ext/Template.xml

    Returns:
        [{name, file, parent_type, parent_name, schema}, ...]
    """
    config_dir = Path(config_dir)
    schemas = []

    # 1. СКД в отчётах
    reports_dir = config_dir / 'Reports'
    if reports_dir.exists():
        for report_dir in sorted(reports_dir.iterdir()):
            if not report_dir.is_dir():
                continue
            report_name = report_dir.name
            templates_dir = report_dir / 'Templates'
            if not templates_dir.exists():
                continue
            for tmpl_dir in sorted(templates_dir.iterdir()):
                if not tmpl_dir.is_dir():
                    continue
                template_xml = tmpl_dir / 'Ext' / 'Template.xml'
                if template_xml.exists():
                    schema = parse_skd_schema(template_xml)
                    if 'error' not in schema:
                        schemas.append({
                            'name': tmpl_dir.name,
                            'parent_type': 'Report',
                            'parent_name': report_name,
                            'file': str(template_xml),
                            'schema': schema,
                        })

    # 2. СКД в общих макетах
    common_templates_dir = config_dir / 'CommonTemplates'
    if common_templates_dir.exists():
        for tmpl_dir in sorted(common_templates_dir.iterdir()):
            if not tmpl_dir.is_dir():
                continue
            template_xml = tmpl_dir / 'Ext' / 'Template.xml'
            if template_xml.exists():
                schema = parse_skd_schema(template_xml)
                if 'error' not in schema:
                    schemas.append({
                        'name': tmpl_dir.name,
                        'parent_type': 'CommonTemplate',
                        'parent_name': '',
                        'file': str(template_xml),
                        'schema': schema,
                    })

    # 3. СКД в обработках
    dp_dir = config_dir / 'DataProcessors'
    if dp_dir.exists():
        for dp_item in sorted(dp_dir.iterdir()):
            if not dp_item.is_dir():
                continue
            dp_name = dp_item.name
            templates_dir = dp_item / 'Templates'
            if not templates_dir.exists():
                continue
            for tmpl_dir in sorted(templates_dir.iterdir()):
                if not tmpl_dir.is_dir():
                    continue
                template_xml = tmpl_dir / 'Ext' / 'Template.xml'
                if template_xml.exists():
                    schema = parse_skd_schema(template_xml)
                    if 'error' not in schema:
                        schemas.append({
                            'name': tmpl_dir.name,
                            'parent_type': 'DataProcessor',
                            'parent_name': dp_name,
                            'file': str(template_xml),
                            'schema': schema,
                        })

    return schemas


def build_skd_index(config_dir: Path | str, output_path: Path | str) -> dict:
    """Строит индекс всех СКД-схем в конфигурации.

    Args:
        config_dir: Путь к директории конфигурации
        output_path: Куда сохранить skd-index.json

    Returns:
        Статистика
    """
    config_dir = Path(config_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Поиск СКД-схем в: {config_dir}")
    schemas = find_skd_schemas(config_dir)

    print(f"\n✅ Найдено СКД-схем: {len(schemas)}")

    # Статистика
    stats = {
        'total_schemas': len(schemas),
        'by_parent_type': {},
        'total_data_sets': 0,
        'total_parameters': 0,
        'total_fields': 0,
        'reports_with_skd': set(),
    }

    for s in schemas:
        parent_type = s['parent_type']
        stats['by_parent_type'][parent_type] = stats['by_parent_type'].get(parent_type, 0) + 1
        schema = s['schema']
        stats['total_data_sets'] += len(schema.get('data_sets', []))
        stats['total_parameters'] += len(schema.get('parameters', []))
        for dset in schema.get('data_sets', []):
            stats['total_fields'] += len(dset.get('fields', []))
        if parent_type == 'Report':
            stats['reports_with_skd'].add(s['parent_name'])

    stats['reports_with_skd'] = len(stats['reports_with_skd'])

    print(f"   По типам:")
    for pt, count in stats['by_parent_type'].items():
        print(f"     {pt}: {count}")
    print(f"   Наборов данных: {stats['total_data_sets']}")
    print(f"   Параметров: {stats['total_parameters']}")
    print(f"   Полей: {stats['total_fields']}")
    print(f"   Отчётов с СКД: {stats['reports_with_skd']}")

    # Сохраняем
    result = {
        'stats': stats,
        'schemas': schemas,
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
        print("Использование: python3 skd_parser.py <config_dir> [output_path]")
        print()
        print("Пример:")
        print("  python3 skd_parser.py data/configs/ut11 derived/configs/ut11/skd-index.json")
        sys.exit(1)

    config_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'skd-index.json'

    build_skd_index(config_dir, output)


if __name__ == '__main__':
    main()
