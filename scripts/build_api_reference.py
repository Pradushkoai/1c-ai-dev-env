#!/usr/bin/env python3
"""
Универсальный парсер API общих модулей 1С (УТ11, УНП, БП, ERP, и др.).

Извлекает из каждого общего модуля:
- Имя модуля, синоним, комментарий
- Свойства: Server, Client, ServerCall, Global, Privileged, ExternalConnection
- Все экспортные процедуры и функции
- Документацию к каждому методу (из комментариев перед методом)
- Параметры методов (из секции "Параметры:")
- Возвращаемое значение (из секции "Возвращаемое значение:")

Создает indexes/<config>-api-reference.md для любой конфигурации.
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Универсальные параметры через argparse
import argparse
parser = argparse.ArgumentParser(description='Парсер API 1С')
parser.add_argument('--config', required=True)
parser.add_argument('--config-dir', required=True)
parser.add_argument('--output-md', default=None)
parser.add_argument('--output-json', default=None)
parser.add_argument('--title', default='')
_args = parser.parse_args()

CONFIG_DIR = os.path.join(_args.config_dir, 'CommonModules')
OUTPUT_INDEX = _args.output_md or f'indexes/{_args.config}-api-reference.md'
OUTPUT_JSON = _args.output_json or f'indexes/{_args.config}-api-reference.json'
CONFIG_TITLE = _args.title or _args.config


def strip_ns(tag):
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def get_child(elem, tag):
    if elem is None:
        return None
    for child in elem:
        if strip_ns(child.tag) == tag:
            return child
    return None


def get_text(elem, tag, default=''):
    child = get_child(elem, tag)
    if child is not None:
        return child.text or ''
    return default


def get_synonym_text(parent, tag='Synonym'):
    elem = get_child(parent, tag)
    if elem is None:
        return ''
    if elem.text and elem.text.strip():
        return elem.text.strip()
    for item in elem:
        if strip_ns(item.tag) == 'item':
            content = get_text(item, 'content')
            if content:
                return content
    return ''


def parse_module_xml(xml_path):
    """Парсит .xml файл общего модуля, извлекает свойства."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        mdo = None
        for child in root:
            if strip_ns(child.tag) == 'CommonModule':
                mdo = child
                break
        if mdo is None:
            return None
        
        props = get_child(mdo, 'Properties')
        if props is None:
            return None
        
        result = {
            'name': get_text(props, 'Name'),
            'synonym': get_synonym_text(props, 'Synonym'),
            'comment': get_text(props, 'Comment'),
            'global': get_text(props, 'Global'),
            'server': get_text(props, 'Server'),
            'client_managed': get_text(props, 'ClientManagedApplication'),
            'client_ordinary': get_text(props, 'ClientOrdinaryApplication'),
            'server_call': get_text(props, 'ServerCall'),
            'privileged': get_text(props, 'Privileged'),
            'external_connection': get_text(props, 'ExternalConnection'),
            'return_values_reuse': get_text(props, 'ReturnValuesReuse'),
        }
        return result
    except Exception as e:
        return None


def parse_module_bsl(bsl_path):
    """
    Парсит .bsl файл общего модуля, извлекает экспортные методы
    с документацией и параметрами.
    """
    try:
        with open(bsl_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception:
        return []
    
    methods = []
    
    # Регулярка для поиска экспортных процедур и функций
    # Захватываем предшествующий комментарий (// строки)
    pattern = re.compile(
        r'((?://[^\n]*\n)*)'  # комментарии перед методом
        r'(Процедура|Функция)\s+'
        r'([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*'  # имя метода
        r'\(([^)]*)\)\s*'  # параметры
        r'(Экспорт)?',  # ключевое слово Экспорт
        re.MULTILINE
    )
    
    for match in pattern.finditer(content):
        comment_block = match.group(1)
        method_type = match.group(2)  # Процедура или Функция
        method_name = match.group(3)
        params_str = match.group(4).strip()
        is_export = match.group(5) is not None
        
        if not is_export:
            continue
        
        # Парсим комментарий
        doc = parse_comment_block(comment_block)
        
        # Парсим параметры из сигнатуры
        signature_params = parse_signature_params(params_str)
        
        # Объединяем: параметры из сигнатуры + документация
        params = []
        for sp in signature_params:
            doc_param = None
            for dp in doc.get('params', []):
                if dp['name'].lower() == sp['name'].lower():
                    doc_param = dp
                    break
            
            params.append({
                'name': sp['name'],
                'type': doc_param['type'] if doc_param else sp.get('type', ''),
                'description': doc_param['description'] if doc_param else '',
                'optional': sp.get('optional', False),
                'default_value': sp.get('default_value', ''),
            })
        
        # Добавляем документированные параметры, которых нет в сигнатуре (например, Структура с полями)
        for dp in doc.get('params', []):
            if not any(p['name'].lower() == dp['name'].lower() for p in params):
                params.append({
                    'name': dp['name'],
                    'type': dp['type'],
                    'description': dp['description'],
                    'optional': False,
                    'default_value': '',
                })
        
        method = {
            'name': method_name,
            'type': method_type,  # Процедура or Функция
            'params': params,
            'description': doc.get('description', ''),
            'returns': doc.get('returns', ''),
            'example': doc.get('example', ''),
            'signature': f'{method_type} {method_name}({params_str}) Экспорт',
        }
        methods.append(method)
    
    return methods


def parse_comment_block(comment_block):
    """
    Парсит блок комментариев перед методом.
    Извлекает: описание, параметры, возвращаемое значение, пример.
    """
    if not comment_block:
        return {}
    
    # Убираем // из каждой строки
    lines = []
    for line in comment_block.split('\n'):
        stripped = line.strip()
        if stripped.startswith('//'):
            lines.append(stripped[2:].strip())
        elif stripped:
            lines.append(stripped)
    
    text = '\n'.join(lines)
    
    result = {
        'description': '',
        'params': [],
        'returns': '',
        'example': '',
    }
    
    # Извлекаем описание (всё до секции "Параметры:" или "Возвращаемое значение:")
    desc_lines = []
    in_params = False
    in_returns = False
    in_example = False
    
    current_param = None
    
    for line in lines:
        lower = line.lower()
        
        # Секции
        if lower.startswith('параметры:') or lower == 'параметры':
            in_params = True
            in_returns = False
            in_example = False
            current_param = None
            continue
        elif lower.startswith('возвращаемое значение:'):
            in_params = False
            in_returns = True
            in_example = False
            current_param = None
            continue
        elif lower.startswith('пример:') or lower.startswith('пример'):
            in_params = False
            in_returns = False
            in_example = True
            current_param = None
            continue
        
        if in_params:
            # Строка параметра: "Имя - Тип - описание" или "Имя - Тип -"
            # Также может быть "Имя - Тип"
            param_match = re.match(
                r'^([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*[-–—]\s*(.+)',
                line
            )
            if param_match:
                # Сохраняем предыдущий параметр
                if current_param:
                    result['params'].append(current_param)
                
                param_name = param_match.group(1)
                rest = param_match.group(2).strip()
                
                # Тип - описание (разделитель " - ")
                type_desc = re.split(r'\s*[-–—]\s*', rest, maxsplit=1)
                param_type = type_desc[0].strip()
                param_desc = type_desc[1].strip() if len(type_desc) > 1 else ''
                
                current_param = {
                    'name': param_name,
                    'type': param_type,
                    'description': param_desc,
                }
            elif current_param:
                # Продолжение описания параметра
                current_param['description'] += ' ' + line.strip()
        elif in_returns:
            if line.strip():
                result['returns'] += ' ' + line.strip() if result['returns'] else line.strip()
        elif in_example:
            if line.strip():
                result['example'] += '\n' + line
        else:
            # Описание метода
            if line.strip():
                desc_lines.append(line.strip())
    
    # Сохраняем последний параметр
    if current_param:
        result['params'].append(current_param)
    
    result['description'] = ' '.join(desc_lines).strip()
    result['returns'] = result['returns'].strip()
    result['example'] = result['example'].strip()
    
    return result


def parse_signature_params(params_str):
    """
    Парсит строку параметров из сигнатуры метода.
    Например: "ДополнительныеСвойства, Движения, Отказ"
    или: "Номенклатура, БазовыеВНачале = Ложь, СкладскаяГруппа = Неопределено"
    """
    if not params_str.strip():
        return []
    
    params = []
    # Разделяем по запятым (но не внутри скобок)
    parts = re.split(r',\s*(?![^()]*\))', params_str)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Имя = ЗначениеПоУмолчанию
        if '=' in part:
            name, default = part.split('=', 1)
            params.append({
                'name': name.strip(),
                'optional': True,
                'default_value': default.strip(),
            })
        else:
            params.append({
                'name': part,
                'optional': False,
                'default_value': '',
            })
    
    return params


def classify_module(name, props):
    """
    Классифицирует модуль по его свойствам.
    Возвращает: Server, Client, ServerCall, Global, Privileged, ClientServer, и т.д.
    """
    is_server = props.get('server', 'false').lower() == 'true'
    is_client = props.get('client_managed', 'false').lower() == 'true'
    is_server_call = props.get('server_call', 'false').lower() == 'true'
    is_global = props.get('global', 'false').lower() == 'true'
    is_privileged = props.get('privileged', 'false').lower() == 'true'
    is_ext = props.get('external_connection', 'false').lower() == 'true'
    
    if is_global:
        return 'Глобальный'
    elif is_privileged:
        return 'Привилегированный'
    elif is_server_call:
        return 'Серверный (ВызовСервера)'
    elif is_server and is_client:
        return 'Клиент-серверный'
    elif is_server:
        return 'Серверный'
    elif is_client:
        return 'Клиентский'
    else:
        return 'Прочий'


def categorize_module_by_name(name):
    """
    Категоризует модуль по имени (для группировки в справочнике).
    """
    name_lower = name.lower()
    
    # Подсистемы УТ11
    if any(x in name_lower for x in ['продаж', 'заказ', 'реализ', 'взаиморасчет', 'клиент']):
        return 'Продажи'
    elif any(x in name_lower for x in ['закуп', 'поставщик']):
        return 'Закупки'
    elif any(x in name_lower for x in ['склад', 'товар', 'ячейк', 'помещ', 'адресн']):
        return 'Склад'
    elif any(x in name_lower for x in ['цен', 'наценк', 'скидк']):
        return 'Ценообразование'
    elif any(x in name_lower for x in ['финанс', 'казнач', 'плат', 'банк', 'касс', 'денежн']):
        return 'Финансы'
    elif any(x in name_lower for x in ['партнер', 'контрагент']):
        return 'Партнёры'
    elif any(x in name_lower for x in ['номенклатур', 'характеристик', 'серия']):
        return 'Номенклатура'
    elif any(x in name_lower for x in ['обмен', 'синхрон', 'формат', 'xdto']):
        return 'Обмен данными'
    elif any(x in name_lower for x in ['интеграц', 'егас', 'гисм', 'эдо', 'марк']):
        return 'Интеграции'
    elif any(x in name_lower for x in ['отчет', 'скд', 'вариант']):
        return 'Отчёты'
    elif any(x in name_lower for x in ['форм', 'элемент', 'управляем']):
        return 'Формы'
    elif any(x in name_lower for x in ['печа', 'макет', 'табличн']):
        return 'Печать'
    elif any(x in name_lower for x in ['бсп', 'стандарт', 'общегоназнач', 'подключ', 'обновл']):
        return 'БСП / Стандартные подсистемы'
    elif any(x in name_lower for x in ['бонус', 'лояльн', 'маркет', 'crm']):
        return 'CRM и маркетинг'
    elif any(x in name_lower for x in ['партион', 'счетфактур', 'ндс', 'усн', 'налог']):
        return 'Партионный учёт и налоги'
    elif any(x in name_lower for x in ['мобил', 'тсд', 'терминал', 'сбор']):
        return 'Мобильные и ТСД'
    elif any(x in name_lower for x in ['фасовк', 'взвеш', 'упаков', 'ед']):
        return 'Фасовка и единицы'
    elif any(x in name_lower for x in ['доставк', 'перевоз', 'маршрут']):
        return 'Доставка'
    elif any(x in name_lower for x in ['бухгалт', 'провод']):
        return 'Бухгалтерия'
    elif any(x in name_lower for x in ['пользоват', 'роль', 'прав', 'rls']):
        return 'Права и пользователи'
    elif any(x in name_lower for x in ['регламент', 'фонов', 'задан']):
        return 'Регламентные задания'
    elif 'переопределяемый' in name_lower:
        return 'Переопределяемые'
    elif 'внутренний' in name_lower:
        return 'Внутренние (НЕ использовать)'
    else:
        return 'Прочее'


def main():
    print(f'Парсинг общих модулей ({CONFIG_TITLE}) из {CONFIG_DIR}...')
    
    modules = []
    total_methods = 0
    
    module_dirs = sorted([d for d in os.listdir(CONFIG_DIR)
                         if os.path.isdir(os.path.join(CONFIG_DIR, d))])
    
    print(f'Найдено модулей: {len(module_dirs)}')
    
    for i, module_name in enumerate(module_dirs, 1):
        if i % 100 == 0:
            print(f'  Прогресс: {i}/{len(module_dirs)}')
        
        module_dir = os.path.join(CONFIG_DIR, module_name)
        xml_path = os.path.join(CONFIG_DIR, module_name + '.xml')
        bsl_path = os.path.join(module_dir, 'Ext', 'Module.bsl')
        
        # Парсим .xml
        props = None
        if os.path.exists(xml_path):
            props = parse_module_xml(xml_path)
        
        if props is None:
            props = {
                'name': module_name,
                'synonym': '',
                'comment': '',
                'server': 'false',
                'client_managed': 'false',
                'server_call': 'false',
                'global': 'false',
                'privileged': 'false',
                'external_connection': 'false',
            }
        
        # Парсим .bsl
        methods = []
        if os.path.exists(bsl_path):
            methods = parse_module_bsl(bsl_path)
        
        total_methods += len(methods)
        
        # Классификация
        module_type = classify_module(module_name, props)
        category = categorize_module_by_name(module_name)
        
        modules.append({
            'name': module_name,
            'synonym': props.get('synonym', ''),
            'comment': props.get('comment', ''),
            'type': module_type,
            'category': category,
            'properties': {
                'global': props.get('global', 'false') == 'true',
                'server': props.get('server', 'false') == 'true',
                'client_managed': props.get('client_managed', 'false') == 'true',
                'server_call': props.get('server_call', 'false') == 'true',
                'privileged': props.get('privileged', 'false') == 'true',
                'external_connection': props.get('external_connection', 'false') == 'true',
            },
            'methods': methods,
            'methods_count': len(methods),
        })
    
    print(f'\n=== Готово ===')
    print(f'Модулей: {len(modules)}')
    print(f'Всего экспортных методов: {total_methods}')
    
    # Сохраняем JSON
    print(f'\nСохраняю JSON в {OUTPUT_JSON}...')
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(modules, f, ensure_ascii=False, indent=2)
    print(f'  Размер: {os.path.getsize(OUTPUT_JSON) // 1024} КБ')
    
    # Генерируем Markdown
    print(f'\nГенерирую Markdown в {OUTPUT_INDEX}...')
    generate_markdown(modules, total_methods)
    print(f'  Размер: {os.path.getsize(OUTPUT_INDEX) // 1024} КБ')


def generate_markdown(modules, total_methods):
    """Генерирует Markdown-справочник API."""
    
    lines = []
    lines.append(f'# Справочник API: {CONFIG_TITLE}')
    lines.append('')
    lines.append(f'> Сгенерировано: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'> Источник: общие модули конфигурации "{CONFIG_TITLE}"')
    lines.append(f'> Модулей: **{len(modules)}**, экспортных методов: **{total_methods}**')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 1. Статистика
    lines.append('## 1. Статистика')
    lines.append('')
    
    # По типам модулей
    by_type = defaultdict(int)
    for m in modules:
        by_type[m['type']] += 1
    lines.append('### По типу модулей')
    lines.append('')
    lines.append('| Тип | Кол-во |')
    lines.append('|-----|--------|')
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f'| {t} | {c} |')
    lines.append('')
    
    # По категориям
    by_category = defaultdict(int)
    by_category_methods = defaultdict(int)
    for m in modules:
        by_category[m['category']] += 1
        by_category_methods[m['category']] += m['methods_count']
    lines.append('### По категориям (подсистемам)')
    lines.append('')
    lines.append('| Категория | Модулей | Методов |')
    lines.append('|-----------|---------|---------|')
    for cat, c in sorted(by_category.items(), key=lambda x: -x[1]):
        lines.append(f'| {cat} | {c} | {by_category_methods[cat]} |')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 2. Топ-20 модулей по количеству методов
    lines.append('## 2. Топ-20 модулей по API')
    lines.append('')
    lines.append('| Модуль | Синоним | Тип | Категория | Методов |')
    lines.append('|--------|---------|-----|-----------|---------|')
    top_modules = sorted(modules, key=lambda x: -x['methods_count'])[:20]
    for m in top_modules:
        syn = m['synonym'][:40].replace('|', '\\|') if m['synonym'] else '—'
        lines.append(f'| `{m["name"]}` | {syn} | {m["type"]} | {m["category"]} | {m["methods_count"]} |')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 3. Детальный справочник по категориям
    lines.append('## 3. Справочник по категориям')
    lines.append('')
    
    # Пропускаем "Внутренние" — они не для использования
    skip_categories = {'Внутренние (НЕ использовать)'}
    
    for category in sorted(by_category.keys()):
        if category in skip_categories:
            continue
        
        cat_modules = [m for m in modules if m['category'] == category]
        cat_methods_count = sum(m['methods_count'] for m in cat_modules)
        
        lines.append(f'### {category} ({len(cat_modules)} модулей, {cat_methods_count} методов)')
        lines.append('')
        
        for m in sorted(cat_modules, key=lambda x: -x['methods_count']):
            if m['methods_count'] == 0:
                continue
            
            # Заголовок модуля
            syn = f' — {m["synonym"]}' if m['synonym'] else ''
            lines.append(f'#### `{m["name"]}`{syn}')
            lines.append('')
            lines.append(f'**Тип:** {m["type"]}')
            if m['comment']:
                lines.append(f'**Комментарий:** {m["comment"]}')
            lines.append(f'**Экспортных методов:** {m["methods_count"]}')
            lines.append('')
            
            # Методы
            if m['methods']:
                for method in m['methods']:
                    method_type_icon = '🔧' if method['type'] == 'Функция' else '⚙️'
                    lines.append(f'**{method_type_icon} {method["name"]}** ({method["type"]})')
                    lines.append('')
                    lines.append(f'```bsl')
                    lines.append(method['signature'])
                    lines.append(f'```')
                    lines.append('')
                    
                    if method['description']:
                        lines.append(f'*{method["description"]}*')
                        lines.append('')
                    
                    if method['params']:
                        lines.append(f'**Параметры:**')
                        lines.append('')
                        for p in method['params']:
                            optional = ' (необязательный)' if p.get('optional') else ''
                            default = f', по умолчанию: `{p.get("default_value", "")}`' if p.get('default_value') else ''
                            type_str = f' `{p["type"]}`' if p.get('type') else ''
                            lines.append(f'- `{p["name"]}`{type_str}{optional}{default} — {p.get("description", "—")}')
                        lines.append('')
                    
                    if method['returns']:
                        lines.append(f'**Возвращаемое значение:**')
                        lines.append(f'{method["returns"]}')
                        lines.append('')
                    
                    if method['example']:
                        lines.append(f'**Пример:**')
                        lines.append(f'```bsl')
                        lines.append(method['example'])
                        lines.append(f'```')
                        lines.append('')
        
        lines.append('---')
        lines.append('')
    
    # 4. Внутренние модули (предупреждение)
    lines.append('## 4. Внутренние модули (НЕ использовать напрямую)')
    lines.append('')
    lines.append('⚠️ Эти модули не являются публичным API. Их методы могут измениться без предупреждения.')
    lines.append('')
    internal_modules = [m for m in modules if m['category'] == 'Внутренние (НЕ использовать)']
    lines.append(f'Всего: {len(internal_modules)} модулей')
    lines.append('')
    lines.append('| Модуль | Методов |')
    lines.append('|--------|---------|')
    for m in sorted(internal_modules, key=lambda x: -x['methods_count']):
        lines.append(f'| `{m["name"]}` | {m["methods_count"]} |')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 5. Как пользоваться
    lines.append('## 5. Как пользоваться справочником')
    lines.append('')
    lines.append('### Поиск метода по имени')
    lines.append('```bash')
    lines.append('# Найти все методы, содержащие "Цена" в имени')
    lines.append('grep -B 2 -A 10 "Цена" indexes/<config>-api-reference.md')
    lines.append('')
    lines.append('# Найти метод по имени модуля')
    lines.append('grep -A 5 "СкладыСервер" indexes/<config>-api-reference.md')
    lines.append('```')
    lines.append('')
    lines.append('### Программный поиск через JSON')
    lines.append('```python')
    lines.append('import json')
    lines.append('with open("indexes/<config>-api-reference.json") as f:')
    lines.append('    modules = json.load(f)')
    lines.append('')
    lines.append('# Найти все функции в модуле СкладыСервер')
    lines.append('for m in modules:')
    lines.append('    if m["name"] == "СкладыСервер":')
    lines.append('        for method in m["methods"]:')
    lines.append('            if method["type"] == "Функция":')
    lines.append('                print(f"{method[\'name\']}({\', \'.join(p[\'name\'] for p in method[\'params\'])})")')
    lines.append('```')
    lines.append('')
    lines.append('### Правила использования API')
    lines.append('')
    lines.append('1. **Используй только публичные модули** — без суффикса "Внутренний"')
    lines.append('2. **Серверные методы** (`Server=true`) вызывай только `&НаСервере`')
    lines.append('3. **Клиент-серверные** можно вызывать и на клиенте, и на сервере')
    lines.append('4. **Глобальные** модули доступны без указания имени (например, `Сообщить()` вместо `ОбщегоНазначения.Сообщить()`)')
    lines.append('5. **Привилегированные** игнорируют RLS — осторожно с правами доступа')
    lines.append('6. **ServerCall** (`ВызовСервера`) — серверные методы, которые можно вызывать с клиента через `ОбщийМодуль.ИмяМетода()`')
    
    with open(OUTPUT_INDEX, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


import json  # нужен для json.dump в generate_markdown


if __name__ == '__main__':
    main()
