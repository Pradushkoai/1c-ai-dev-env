"""
Тесты для SKD trace mode — трассировка поля через всю цепочку.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Добавляем scripts/ в path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from skd_parser import trace_field


SKD_NS = "http://v8.1c.ru/8.1/data-composition-system/schema"
V8_NS = "http://v8.1c.ru/8.1/data/core"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _make_skd_schema(tmp_path: Path, datasets=None, calculated=None, totals=None) -> Path:
    """Создать тестовую СКД-схему (Template.xml)."""
    # Регистрируем namespace
    import xml.etree.ElementTree as ET
    ET.register_namespace('s', SKD_NS)
    ET.register_namespace('v8', V8_NS)

    root = ET.Element(f'{{{SKD_NS}}}DataCompositionSchema')

    # Data sources
    ds_src = ET.SubElement(root, f'{{{SKD_NS}}}dataSources')
    src = ET.SubElement(ds_src, f'{{{SKD_NS}}}dataSource')
    n = ET.SubElement(src, f'{{{SKD_NS}}}name')
    n.text = 'ИсточникДанных1'

    # Data sets
    if datasets:
        ds_container = ET.SubElement(root, f'{{{SKD_NS}}}dataSets')
        for ds_def in datasets:
            ds = ET.SubElement(ds_container, f'{{{SKD_NS}}}dataSet')
            ds.set(f'{{{XSI_NS}}}type', f's:DataSet{ds_def.get("type", "Query")}')
            n = ET.SubElement(ds, f'{{{SKD_NS}}}name')
            n.text = ds_def['name']
            # Fields
            for fld in ds_def.get('fields', []):
                f = ET.SubElement(ds, f'{{{SKD_NS}}}field')
                dp = ET.SubElement(f, f'{{{SKD_NS}}}dataPath')
                dp.text = fld['path']
                if fld.get('title'):
                    title = ET.SubElement(f, f'{{{SKD_NS}}}title')
                    item = ET.SubElement(title, f'{{{V8_NS}}}item')
                    content = ET.SubElement(item, f'{{{V8_NS}}}content')
                    content.text = fld['title']

    # Calculated fields
    if calculated:
        for cf_def in calculated:
            cf = ET.SubElement(root, f'{{{SKD_NS}}}calculatedField')
            dp = ET.SubElement(cf, f'{{{SKD_NS}}}dataPath')
            dp.text = cf_def['path']
            expr = ET.SubElement(cf, f'{{{SKD_NS}}}expression')
            expr.text = cf_def['expression']
            if cf_def.get('title'):
                title = ET.SubElement(cf, f'{{{SKD_NS}}}title')
                item = ET.SubElement(title, f'{{{V8_NS}}}item')
                content = ET.SubElement(item, f'{{{V8_NS}}}content')
                content.text = cf_def['title']

    # Total fields (resources)
    if totals:
        for tf_def in totals:
            tf = ET.SubElement(root, f'{{{SKD_NS}}}totalField')
            dp = ET.SubElement(tf, f'{{{SKD_NS}}}dataPath')
            dp.text = tf_def['path']
            expr = ET.SubElement(tf, f'{{{SKD_NS}}}expression')
            expr.text = tf_def.get('expression', '')
            if tf_def.get('group'):
                grp = ET.SubElement(tf, f'{{{SKD_NS}}}group')
                grp.text = tf_def['group']

    # Сохраняем
    out = tmp_path / 'Template.xml'
    tree = ET.ElementTree(root)
    tree.write(out, encoding='utf-8', xml_declaration=True)
    return out


# ─────────────────────────────────────────────

def test_trace_field_not_found_file(tmp_path):
    """trace_field на несуществующий файл → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        trace_field(tmp_path / 'missing.xml', 'SomeField')


def test_trace_field_dataset_origin(tmp_path):
    """trace_field находит происхождение поля из dataset."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Продажи',
            'type': 'Query',
            'fields': [
                {'path': 'Сумма', 'title': 'Сумма продажи'},
                {'path': 'Контрагент'},
            ],
        }],
    )
    result = trace_field(schema, 'Сумма')

    assert result['target_field'] == 'Сумма'
    assert result['title'] == 'Сумма продажи'
    assert len(result['dataset_origin']) >= 1
    assert 'Продажи' in ' '.join(result['dataset_origin'])
    assert 'calculated' not in result or result['calculated'] is None


def test_trace_field_by_title(tmp_path):
    """trace_field по title (синониму) находит поле."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Данные',
            'fields': [
                {'path': 'КоличествоОборот', 'title': 'Количество оборот'},
            ],
        }],
    )
    # Ищем по title
    result = trace_field(schema, 'Количество оборот')
    assert result['target_field'] == 'КоличествоОборот'


def test_trace_field_substring_title(tmp_path):
    """trace_field по substring в title находит поле."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Данные',
            'fields': [
                {'path': 'СуммаПродаж', 'title': 'Сумма продаж за период'},
            ],
        }],
    )
    # Ищем по подстроке
    result = trace_field(schema, 'продаж')
    assert result['target_field'] == 'СуммаПродаж'


def test_trace_field_calculated(tmp_path):
    """trace_field находит выражение вычисляемого поля."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Данные',
            'fields': [{'path': 'Цена'}, {'path': 'Количество'}],
        }],
        calculated=[
            {'path': 'Сумма', 'expression': 'Цена * Количество', 'title': 'Сумма'},
        ],
    )
    result = trace_field(schema, 'Сумма')

    assert result['target_field'] == 'Сумма'
    assert result['calculated'] is not None
    assert 'Цена * Количество' in result['calculated']['expression']


def test_trace_field_resource(tmp_path):
    """trace_field находит итоговое поле (resource)."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Данные',
            'fields': [{'path': 'Сумма'}],
        }],
        totals=[
            {'path': 'Сумма', 'expression': 'СУММА(Сумма)', 'group': 'Контрагент'},
        ],
    )
    result = trace_field(schema, 'Сумма')

    assert result['target_field'] == 'Сумма'
    assert len(result['resources']) == 1
    assert 'СУММА' in result['resources'][0]['expression']
    assert result['resources'][0]['group'] == 'Контрагент'


def test_trace_field_full_chain(tmp_path):
    """Полная цепочка: dataset → calculated → resource для одного поля."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Продажи',
            'fields': [{'path': 'Сумма', 'title': 'Сумма'}],
        }],
        calculated=[
            {'path': 'СуммаНДС', 'expression': 'Сумма * 1.2', 'title': 'Сумма с НДС'},
        ],
        totals=[
            {'path': 'Сумма', 'expression': 'СУММА(Сумма)', 'group': 'Контрагент'},
            {'path': 'СуммаНДС', 'expression': 'СУММА(СуммаНДС)', 'group': 'Контрагент'},
        ],
    )

    # Трассируем Сумма — должна быть dataset + 1 resource
    r1 = trace_field(schema, 'Сумма')
    assert r1['dataset_origin']
    assert len(r1['resources']) == 1
    assert 'СУММА(Сумма)' in r1['resources'][0]['expression']

    # Трассируем СуммаНДС — должна быть calculated + 1 resource
    r2 = trace_field(schema, 'СуммаНДС')
    assert r2['calculated'] is not None
    assert 'Сумма * 1.2' in r2['calculated']['expression']
    assert len(r2['resources']) == 1
    assert 'СУММА(СуммаНДС)' in r2['resources'][0]['expression']


def test_trace_field_not_found_returns_error(tmp_path):
    """trace_field на несуществующее поле возвращает error."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Данные',
            'fields': [{'path': 'Сумма'}],
        }],
    )
    result = trace_field(schema, 'НесуществующеееПоле')
    assert 'error' in result
    assert result['target_field'] is None
    # Должен вернуть список доступных полей
    assert 'available_fields' in result
    assert 'Сумма' in result['available_fields']


def test_trace_field_trace_text_format(tmp_path):
    """trace_text содержит читаемую трассировку."""
    schema = _make_skd_schema(
        tmp_path,
        datasets=[{
            'name': 'Продажи',
            'fields': [{'path': 'Сумма', 'title': 'Сумма'}],
        }],
        totals=[
            {'path': 'Сумма', 'expression': 'СУММА(Сумма)', 'group': 'Контрагент'},
        ],
    )
    result = trace_field(schema, 'Сумма')
    text = result['trace_text']
    assert 'Trace: Сумма' in text
    assert 'Dataset:' in text
    assert 'Resources' in text
    assert 'СУММА(Сумма)' in text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
