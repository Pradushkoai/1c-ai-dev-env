#!/usr/bin/env python3
"""Step 2: Add workflow hints to tool descriptions."""

content = open('src/mcpserver/tools/tool_definitions.py').read()

# Exact replacements based on actual file content
replacements = [
    # search_1c_methods
    ('description="TF-IDF/BM25 семантический поиск по 8141 методам платформы 1С. Возвращает: name_ru, name_en, syntax, description, context. Пример: search_1c_methods(query=\'найти элемент по коду\', limit=5)"',
     'description="BM25 семантический поиск по методам платформы 1С. ПЕРВЫЙ ШАГ при работе с конфигурацией. После поиска вызовите get_object_structure для получения полей найденного объекта. Возвращает: name_ru, name_en, context, score. Пример: search_1c_methods(query=\'найти элемент по коду\', limit=5)"'),

    # get_object_structure
    ('description="Полная структура объекта конфигурации: реквизиты (с типами данных), табличные части (с реквизитами), формы, команды, предопределённые значения. Если object_name не указан — возвращает список всех объектов с краткой информацией. Пример: get_object_structure(config_name=\'ut11\', object_name=\'Склады\'). Возвращает: name, uuid, synonym, attributes[{name, types, synonym}], tabular_sections[{name, attributes}], forms, commands."',
     'description="Полная структура объекта конфигурации: ресурсы, измерения, реквизиты (с типами), табличные части. ВЫЗЫВАЙТЕ ПЕРЕД НАПИСАНИЕМ ЗАПРОСА для получения точных имён полей. Если object_name не указан — список всех объектов. Пример: get_object_structure(config_name=\'ut11\', object_name=\'ВыручкаИСебестоимостьПродаж\')."'),

    # inspect
    ('description="Единый анализ объектов 1С: cf, meta, form, skd, mxl, role, subsystem, depgraph. Возвращает свойства и структуру объекта. Пример: inspect(type=\'cf\', path=\'data/configs/ut11\')."',
     'description="Инспекция объектов 1С: cf (конфигурация — обзор всех объектов), meta, form, skd, mxl, role, subsystem. НАЧАЛЬНЫЙ ШАГ для понимания структуры конфигурации. Возвращает свойства и структуру. Пример: inspect(type=\'cf\', path=\'data/configs/ut11\')."'),

    # list_configs
    ('description="Список загруженных конфигураций 1С. Возвращает: name, version, status, objects_count, api_methods_count. Используй первым шагом. Пример: list_configs()."',
     'description="Список загруженных конфигураций 1С. ВЫЗЫВАЙТЕ ПЕРВЫМ для понимания какие данные доступны. Возвращает: name, version, status, objects_count. Пример: list_configs()."'),

    # search_code
    ('description="BM25 поиск по коду конфигурации (115K+ методов). Ищет по именам методов, сигнатурам, описаниям. Используй для поиска \'как уже реализовано похожее\' в конфигурации. Пример: search_code(query=\'создать заказ\', config_name=\'ut11\', limit=5)"',
     'description="BM25 поиск по коду конфигурации. Ищет по именам методов, сигнатурам, описаниям. Используйте для поиска \'как уже реализовано похожее\'. После поиска вызовите get_object_structure для структуры найденного модуля. Пример: search_code(query=\'создать заказ\', config_name=\'ut11\', limit=5)"'),

    # call_graph
    ('description="Граф вызовов методов конфигурации. Кто кого вызывает, мёртвый код, циклические зависимости. Action: stats (статистика), callers (кто вызывает), callees (кого вызывает), dead-code (мёртвый код), cycles (циклы). Пример: call_graph(config_name=\'obhod\', action=\'callees\', module=\'ОбменДокументы\', method=\'ВыполнитьПолныйОбмен\')"',
     'description="Граф вызовов методов: callers (кто вызывает), callees (кого вызывает), cycles (циклы), dead-code (мёртвый код). Используйте ПОСЛЕ search_1c_methods для анализа зависимостей найденного метода. Пример: call_graph(config_name=\'ut11\', action=\'callers\', module=\'ПродажиСервер\', method=\'ОтразитьВыручку\')"'),

    # check_standards
    ('description="Проверка .bsl файла на 56 правил стандартов 1С. Возвращает: список нарушений (rule_id, severity, line, message). Не требует Java — работает мгновенно. Пример: check_standards(file_path=\'/tmp/module.bsl\')"',
     'description="Проверка .bsl на 56 правил стандартов 1С. ВЫЗЫВАЙТЕ ПОСЛЕ audit_security для полной проверки качества кода. Не требует Java. Пример: check_standards(file_path=\'/tmp/module.bsl\')"'),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1
    else:
        print(f'NOT FOUND: {old[:70]}...')

open('src/mcpserver/tools/tool_definitions.py', 'w').write(content)
print(f'Fixed {count}/{len(replacements)} descriptions')
