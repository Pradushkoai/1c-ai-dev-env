#!/usr/bin/env python3
"""Fix tool_definitions.py: descriptions, schemas, examples."""

content = open('src/mcpserver/tools/tool_definitions.py').read()

# 1. data_status
content = content.replace(
    'description="Статус данных проекта (persistence).",',
    'description="Статус данных проекта: список конфигураций, индексы, runtime файлы. Возвращает: configs, indices, runtime_files. Пример: data_status().",'
)
content = content.replace(
    '''            name="data_status",
            description="Статус данных проекта: список конфигураций, индексы, runtime файлы. Возвращает: configs, indices, runtime_files. Пример: data_status().",
            input_schema={
                "type": "object",
            },''',
    '''            name="data_status",
            description="Статус данных проекта: список конфигураций, индексы, runtime файлы. Возвращает: configs, indices, runtime_files. Пример: data_status().",
            input_schema={
                "properties": {},
                "type": "object",
            },'''
)

# 2. epf_factory_templates
content = content.replace(
    'description="Пути к шаблонам EpfFactory.",',
    'description="Возвращает пути к шаблонам EpfFactory для создания внешних обработок: ExternalDataProcessor, Form, Form.id, Form.elem. Пример: epf_factory_templates().",'
)
content = content.replace(
    '''            name="epf_factory_templates",
            description="Возвращает пути к шаблонам EpfFactory для создания внешних обработок: ExternalDataProcessor, Form, Form.id, Form.elem. Пример: epf_factory_templates().",
            input_schema={
                "type": "object",
            },''',
    '''            name="epf_factory_templates",
            description="Возвращает пути к шаблонам EpfFactory для создания внешних обработок: ExternalDataProcessor, Form, Form.id, Form.elem. Пример: epf_factory_templates().",
            input_schema={
                "properties": {},
                "type": "object",
            },'''
)

# 3. list_configs
content = content.replace(
    'description="Список доступных конфигураций 1С.",',
    'description="Список доступных конфигураций 1С: имена, пути, статус индексации. Возвращает массив конфигураций. Пример: list_configs().",'
)
content = content.replace(
    '''            name="list_configs",
            description="Список доступных конфигураций 1С: имена, пути, статус индексации. Возвращает массив конфигураций. Пример: list_configs().",
            input_schema={
                "type": "object",
            },''',
    '''            name="list_configs",
            description="Список доступных конфигураций 1С: имена, пути, статус индексации. Возвращает массив конфигураций. Пример: list_configs().",
            input_schema={
                "properties": {},
                "type": "object",
            },'''
)

# 4. get_knowledge — add required
old_gk = '''        _build_tool(
            name="get_knowledge",
            description="База знаний: методы 1С, паттерны, антипаттерны. Принимает query для поиска по базе знаний.",
            input_schema={
                "properties": {
                    "query": {"description": "Поисковый запрос", "type": "string"},
                    "limit": {"description": "Максимум результатов (по умолчанию 10)", "type": "integer"},
                },
                "type": "object",
            },
        ),'''
new_gk = '''        _build_tool(
            name="get_knowledge",
            description="База знаний: методы 1С, паттерны, антипаттерны. Принимает query для поиска. Возвращает: результаты с score, name, description. Пример: get_knowledge(query='найти по коду').",
            input_schema={
                "properties": {
                    "query": {"description": "Поисковый запрос", "type": "string"},
                    "limit": {"description": "Максимум результатов (по умолчанию 10)", "type": "integer"},
                },
                "required": ["query"],
                "type": "object",
            },
        ),'''
content = content.replace(old_gk, new_gk)

# 5. openspec_list
content = content.replace(
    'description="Список OpenSpec proposals.",',
    'description="Список OpenSpec proposals (управление изменениями). Возвращает массив proposals с id, title, status. Пример: openspec_list() или openspec_list(status=\'active\').",'
)

# 6. dsl_compile_* short descriptions
content = content.replace(
    'description="Компиляция JSON DSL → XML формы.",',
    'description="Компиляция JSON DSL → XML управляемой формы 1С. Создаёт Form.xml из описания элементов формы. Пример: dsl_compile_form(definition=\'{...}\', output_path=\'Form.xml\').",'
)
content = content.replace(
    'description="Компиляция JSON DSL → XML метаданных.",',
    'description="Компиляция JSON DSL → XML метаданных 1С (Catalog, Document, CommonModule и др.). Создаёт объект метаданных из JSON-описания. Пример: dsl_compile_meta(definition=\'{\\\"type\\\":\\\"Catalog\\\",\\\"name\\\":\\\"Товары\\\"}\', output_dir=\'/tmp/out\').",'
)
content = content.replace(
    'description="Компиляция JSON DSL → XML макета MXL.",',
    'description="Компиляция JSON DSL → XML табличного документа (MXL, печатная форма). Создаёт Template.xml из описания областей и параметров. Пример: dsl_compile_mxl(definition=\'{...}\', output_path=\'Template.xml\').",'
)
content = content.replace(
    'description="Компиляция JSON DSL → роли.",',
    'description="Компиляция JSON DSL → XML роли 1С (Rights.xml). Создаёт роль с правами доступа к объектам. Пример: dsl_compile_role(definition=\'{...}\', output_dir=\'Roles/\').",'
)
content = content.replace(
    'description="Компиляция JSON DSL → СКД.",',
    'description="Компиляция JSON DSL → XML схемы компоновки данных (СКД). Создаёт Template.xml с запросом, полями, отборами. Пример: dsl_compile_skd(definition=\'{...}\', output_path=\'Schema.xml\').",'
)

# 7. openspec short descriptions
content = content.replace(
    'description="Архивировать OpenSpec proposal.",',
    'description="Архивировать OpenSpec proposal (управление изменениями). Перемещает proposal в архив. Пример: openspec_archive(id=\'proposal-001\').",'
)
content = content.replace(
    'description="Обновить задачу proposal.",',
    'description="Обновить статус задачи в OpenSpec proposal. Принимает proposal_id, task_id, new_status. Пример: openspec_update_task(proposal_id=\'p1\', task_id=\'t1\', new_status=\'done\').",'
)

# 8. Add examples to remaining tools
content = content.replace(
    'description="Построить граф зависимостей метаданных 1С (networkx).",',
    'description="Построить граф зависимостей метаданных 1С (networkx). Возвращает: nodes, edges, cycles, stats. Требует предварительно построенный индекс. Пример: build_dependency_graph(config_name=\'УправлениеТорговлей\').",'
)

content = content.replace(
    'description="Трассировка поля СКД: откуда берётся значение поля.",',
    'description="Трассировка поля СКД: откуда берётся значение поля (запрос, вычисляемое поле, параметр). Пример: skd_trace(config_name=\'УТ\', template_name=\'ОсновнаяСхема\', field_name=\'Сумма\').",'
)

content = content.replace(
    'description="Создать OpenSpec proposal (управление изменениями).",',
    'description="Создать OpenSpec proposal (управление изменениями). Принимает title, description, tasks. Возвращает id созданного proposal. Пример: openspec_proposal(title=\'Добавить справочник\', description=\'Новый справочник\').",'
)

open('src/mcpserver/tools/tool_definitions.py', 'w').write(content)
print("All tool definitions fixed!")
