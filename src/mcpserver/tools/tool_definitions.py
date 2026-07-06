"""
tool_definitions.py — определения всех 45 MCP tools (types.Tool).

P2.2: вынесено из mcp_server.py для декомпозиции (SRP).
Каждое определение — types.Tool с name, description, inputSchema.

Источник истины — tests/snapshots/test_mcp_tools_snapshot/.
Любое изменение имён/описаний/схем требует --snapshot-update.
"""

from __future__ import annotations
from typing import Any

import mcp.types as types


def _build_tool(name: str, description: str, input_schema: dict[str, Any]) -> types.Tool:
    """Создать types.Tool с заданными параметрами."""
    return types.Tool(
        name=name,
        description=description,
        inputSchema=input_schema,
    )


def get_all_tool_definitions() -> list[types.Tool]:
    """Вернуть список всех 45 MCP tools (для list_tools handler)."""
    return [
        _build_tool(
            name="analyze_architecture",
            description="Анализ архитектуры конфигурации: циклические зависимости, God Object, мёртвый код, layering, regions, queries in forms. Пример: analyze_architecture(config_dir='data/configs/ut11').",
            input_schema={
                "properties": {"config_dir": {"description": "Путь к директории конфигурации", "type": "string"}},
                "required": ["config_dir"],
                "type": "object",
            },
        ),
        _build_tool(
            name="analyze_bsl",
            description="Анализ .bsl файла через BSL Language Server (187 диагностик). Возвращает: total, by_code (диагностика → кол-во), diagnostics (список). Требует установленного BSL LS (Java). Пример: analyze_bsl(file_path='/tmp/module.bsl')",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="analyze_queries",
            description="Анализ запросов 1С в BSL коде: SELECT *, LIKE %, функции в WHERE, JOIN без ON, временные таблицы без индексов. Пример: analyze_queries(file_path='module.bsl').",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="audit_security",
            description="Аудит безопасности BSL кода (15 правил SEC001-SEC015): SQL-инъекции, Выполнить(), пароли, COM, path traversal. ВЫЗЫВАЙТЕ ПОСЛЕ НАПИСАНИЯ КОДА для проверки. Пример: audit_security(file_path='module.bsl').",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу для аудита", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="build_dependency_graph",
            description="Граф зависимостей метаданных 1С: какие объекты ссылаются на какие. Возвращает: nodes, edges, cycles. Используйте для анализа архитектуры конфигурации. Пример: build_dependency_graph(config_name='УТ11').",
            input_schema={
                "properties": {"config_name": {"type": "string"}},
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="build_epf",
            description="Упаковка структуры каталога в .epf файл (внешняя обработка 1С). Принимает путь к каталогу (из generate_processing или generate_report) и создаёт .epf файл. Пример: build_epf(source_dir='generated/ВыгрузкаНоменклатуры', output_path='ВыгрузкаНоменклатуры.epf').",
            input_schema={
                "properties": {
                    "object_name": {
                        "description": "Имя объекта (если не указано — берётся из имени каталога)",
                        "type": "string",
                    },
                    "object_type": {
                        "description": "Тип объекта: DataProcessor (по умолчанию) или Report",
                        "type": "string",
                    },
                    "output_path": {"description": "Куда сохранить .epf файл", "type": "string"},
                    "source_dir": {"description": "Путь к каталогу со структурой обработки/отчёта", "type": "string"},
                },
                "required": ["source_dir", "output_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="call_graph",
            description="Граф вызовов методов: callers (кто вызывает), callees (кого вызывает), cycles (циклы), dead-code (мёртвый код). Используйте ПОСЛЕ search_1c_methods для анализа зависимостей найденного метода. Пример: call_graph(config_name='ut11', action='callers', module='ПродажиСервер', method='ОтразитьВыручку')",
            input_schema={
                "properties": {
                    "action": {
                        "default": "stats",
                        "description": "Действие: stats, callers, callees, dead-code, cycles",
                        "type": "string",
                    },
                    "config_name": {"description": "Имя конфигурации", "type": "string"},
                    "method": {"description": "Имя метода (для callers/callees)", "type": "string"},
                    "module": {"description": "Имя модуля (для callers/callees)", "type": "string"},
                },
                "required": ["config_name", "action"],
                "type": "object",
            },
        ),
        _build_tool(
            name="cfe_borrow",
            description="Заимствовать объект из конфигурации в расширение (CFE). Создаёт XML с ObjectBelonging=Adopted. Пример: cfe_borrow(object_type='Catalog', object_name='Товары', cfe_name='МоеРасширение').",
            input_schema={
                "properties": {
                    "config_path": {"type": "string"},
                    "extension_path": {"type": "string"},
                    "object_ref": {"type": "string"},
                },
                "required": ["extension_path", "config_path", "object_ref"],
                "type": "object",
            },
        ),
        _build_tool(
            name="cfe_diff",
            description="Анализ расширения CFE: что заимствовано, перехвачено. Возвращает: borrowed, patched, added. Пример: cfe_diff(config_path='data/configs/ut11', extension_path='data/cfe/МоеРасш').",
            input_schema={
                "properties": {"config_path": {"type": "string"}, "extension_path": {"type": "string"}},
                "required": ["extension_path", "config_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="cfe_patch_method",
            description="Сгенерировать BSL перехватчик (&Перед/&После/&ИзменениеИКонтроль). Создаёт BSL код патча метода. Пример: cfe_patch_method(extension_path='cfe/', interceptor_type='Before', module_path='Module.bsl', method_name='ПриОткрытии').",
            input_schema={
                "properties": {
                    "extension_path": {"type": "string"},
                    "interceptor_type": {"enum": ["Before", "After", "ModificationAndControl"], "type": "string"},
                    "method_name": {"type": "string"},
                    "module_path": {"type": "string"},
                },
                "required": ["extension_path", "module_path", "method_name", "interceptor_type"],
                "type": "object",
            },
        ),
        _build_tool(
            name="check_form_quality",
            description="Проверка качества форм: пустые формы, перегруженные, элементы без DataPath, кнопки без команд, дублирующие имена. Пример: check_form_quality(config_name='ut11').",
            input_schema={
                "properties": {"config_name": {"description": "Имя конфигурации", "type": "string"}},
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="check_skd_quality",
            description="Проверка качества СКД-схем: без параметров, без отборов, пустые запросы, перегруженные. Пример: check_skd_quality(config_name='ut11').",
            input_schema={
                "properties": {"config_name": {"description": "Имя конфигурации", "type": "string"}},
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="check_standards",
            description="Проверка .bsl на 56 правил стандартов 1С. ВЫЗЫВАЙТЕ ПОСЛЕ audit_security для полной проверки качества кода. Не требует Java. Пример: check_standards(file_path='/tmp/module.bsl')",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="check_transactions",
            description="Проверка транзакций BSL: несбалансированные, без Try/Catch, интерактив в транзакции, длинные/вложенные транзакции. Пример: check_transactions(file_path='module.bsl').",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="data_status",
            description="Статус данных проекта: что доступно (платформа, конфигурации), что нужно перестроить, доступен ли autosave пакет. Возвращает: has_platform_index, has_platform_methods, configs[], autosave_available. Пример: data_status().",
            input_schema={"properties": {}, "type": "object"},
        ),
        _build_tool(
            name="dependency_query",
            description="Запрос к графу зависимостей: what_depends_on, dependencies_of, find_cycles, и т.д. Возвращает nodes, edges, cycles. Пример: dependency_query(config_name='УТ', query_type='descendants', object_name='Справочник.Товары').",
            input_schema={
                "properties": {
                    "config_name": {"type": "string"},
                    "object_ref": {"type": "string"},
                    "query_type": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["config_name", "query_type", "object_ref"],
                "type": "object",
            },
        ),
        _build_tool(
            name="diff_configs",
            description="Сравнение версий конфигурации: добавленные/удалённые/изменённые объекты, реквизиты, формы, команды, роли, подсистемы. Пример: diff_configs(old_path='old.json', new_path='new.json').",
            input_schema={
                "properties": {
                    "new_path": {"description": "Путь к новому unified-metadata-index.json", "type": "string"},
                    "old_path": {"description": "Путь к старому unified-metadata-index.json", "type": "string"},
                },
                "required": ["old_path", "new_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="dsl_compile_form",
            description="JSON DSL → Form.xml управляемой формы 1С. Создаёт XML формы из описания элементов. Пример: dsl_compile_form(definition={...}, output_path='Form.xml').",
            input_schema={
                "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                "required": ["definition", "output_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="dsl_compile_meta",
            description="JSON DSL → XML метаданных 1С (23 типа: Catalog, Document, CommonModule и др.). Пример: dsl_compile_meta(definition={'type':'Catalog','name':'Товары'}, output_dir='/tmp/out').",
            input_schema={
                "properties": {"definition": {"type": "object"}, "output_dir": {"type": "string"}},
                "required": ["definition", "output_dir"],
                "type": "object",
            },
        ),
        _build_tool(
            name="dsl_compile_mxl",
            description="JSON DSL → MXL Template.xml (печатная форма). Создаёт табличный документ из описания. Пример: dsl_compile_mxl(definition={...}, output_path='Template.xml').",
            input_schema={
                "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                "required": ["definition", "output_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="dsl_compile_role",
            description="JSON DSL → Rights.xml роли 1С. Создаёт роль с правами доступа к объектам. Пример: dsl_compile_role(definition={...}, output_dir='Roles/').",
            input_schema={
                "properties": {"definition": {"type": "object"}, "output_dir": {"type": "string"}},
                "required": ["definition", "output_dir"],
                "type": "object",
            },
        ),
        _build_tool(
            name="dsl_compile_skd",
            description="JSON DSL → СКД Template.xml. Создаёт схему компоновки данных с запросом и полями. Пример: dsl_compile_skd(definition={...}, output_path='Schema.xml').",
            input_schema={
                "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                "required": ["definition", "output_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="epf_factory_create",
            description="Создать внешнюю обработку 1С (.epf) из BSL-кода через полный цикл: шаблоны v8unpack → подстановка name/synonym/UUID → запись BSL-модуля → проверка через BSL LS → сборка .epf → round-trip проверка. Не требует установленной 1С. Пример: epf_factory_create(name='МояОбработка', synonym='Моя обработка', bsl_code='#Область ПрограммныйИнтерфейс\\n#КонецОбласти', output_path='/tmp/МояОбработка.epf')",
            input_schema={
                "properties": {
                    "bsl_code": {"description": "BSL-код модуля формы", "type": "string"},
                    "bsl_path": {"description": "Путь к .bsl файлу (альтернатива bsl_code)", "type": "string"},
                    "form_name": {"description": "Имя формы (по умолчанию 'Форма')", "type": "string"},
                    "form_spec": {
                        "description": 'DSL-описание формы для генерации Form.elem.json. Если не задано — используется пустой шаблон (только реквизит Объект). Пример: {"props": [{"name":"ТаблицаСписка","type":"ValueTable","columns":[{"name":"Дата","type":"Date"}]}]}',
                        "type": "object",
                    },
                    "form_spec_path": {
                        "description": "Путь к JSON-файлу с DSL-описанием формы (альтернатива form_spec)",
                        "type": "string",
                    },
                    "name": {"description": "Имя обработки (латиница/кириллица, без пробелов)", "type": "string"},
                    "output_path": {"description": "Путь к выходному .epf файлу", "type": "string"},
                    "save_sources": {"description": "Сохранить v8unpack-исходники (не удалять)", "type": "boolean"},
                    "skip_bsl_validation": {"description": "Пропустить проверку BSL LS", "type": "boolean"},
                    "synonym": {"description": "Синоним (по умолчанию = name)", "type": "string"},
                },
                "required": ["name", "output_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="epf_factory_templates",
            description="Список доступных шаблонов для epf_factory_create. Возвращает пути к шаблонам ExternalDataProcessor.json, Form.json, Form.id.json, Form.elem.empty.json. Пример: epf_factory_templates().",
            input_schema={"properties": {}, "type": "object"},
        ),
        _build_tool(
            name="generate_processing",
            description="Генерация внешней обработки 1С. Создаёт структуру файлов: модуль объекта (Ext/Module.bsl), модуль формы (Forms/Форма/Ext/Form/Module.bsl), XML метаданные. Готово для упаковки в .epf. Пример: generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры').",
            input_schema={
                "properties": {
                    "author": {"description": "Автор (опционально)", "type": "string"},
                    "description": {"description": "Описание обработки (опционально)", "type": "string"},
                    "name": {"description": "Имя обработки (латиница, без пробелов)", "type": "string"},
                    "output_dir": {"description": "Куда сохранить (по умолчанию generated/<name>)", "type": "string"},
                    "synonym": {"description": "Синоним (русское название)", "type": "string"},
                },
                "required": ["name", "synonym"],
                "type": "object",
            },
        ),
        _build_tool(
            name="generate_report",
            description="Генерация отчёта на СКД (Схеме Компоновки Данных). Создаёт: модуль объекта с СКД-логикой, форму отчёта, СКД-схему (DataCompositionSchema). Пример: generate_report(name='ОтчетПоПродажам', synonym='Отчёт по продажам', data_source='Документ.РеализацияТоваровУслуг').",
            input_schema={
                "properties": {
                    "author": {"description": "Автор (опционально)", "type": "string"},
                    "data_source": {
                        "description": "Источник данных (например 'Документ.РеализацияТоваровУслуг')",
                        "type": "string",
                    },
                    "description": {"description": "Описание отчёта (опционально)", "type": "string"},
                    "main_query": {"description": "Готовый запрос 1С (если пусто — будет шаблонный)", "type": "string"},
                    "name": {"description": "Имя отчёта (латиница, без пробелов)", "type": "string"},
                    "output_dir": {"description": "Куда сохранить (по умолчанию generated/<name>)", "type": "string"},
                    "synonym": {"description": "Синоним (русское название)", "type": "string"},
                },
                "required": ["name", "synonym"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_api_reference",
            description="API-справочник конфигурации — экспортные методы общих модулей. Если module не указан — возвращает список всех модулей с кол-вом методов. Если module указан — возвращает методы конкретного модуля. Пример: get_api_reference(config_name='ut11', module='ОбщегоНазначения')",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации (ut11, priemka, и т.д.)", "type": "string"},
                    "module": {
                        "default": "",
                        "description": "Имя модуля (необязательно). Если пусто — все модули.",
                        "type": "string",
                    },
                },
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_code_metrics",
            description="Метрики кода BSL: LOC (строки кода), цикломатическая/когнитивная сложность, вложенность, дублирование кода, God Object, Long Method, Too Many Params, технический долг, health score (0-100). Пример: get_code_metrics(file_path='module.bsl').",
            input_schema={
                "properties": {"file_path": {"description": "Путь к .bsl файлу", "type": "string"}},
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_form_elements",
            description="Элементы формы конфигурации (кнопки, поля, таблицы, группы). Если form_name не указан — возвращает список всех форм. Пример: get_form_elements(config_name='obhod', form_name='Форма.ФормаАвторизации')",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации", "type": "string"},
                    "form_name": {
                        "description": "Имя формы (необязательно). Если пусто — список всех форм.",
                        "type": "string",
                    },
                },
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_form_structure",
            description="Полная структура формы: элементы (InputField, Button, Table, UsualGroup, и т.д.), их свойства (data_path, visible, enabled, read_only), события и обработчики, дерево элементов (ChildItems). Если form_name не указан — список всех форм с краткой информацией. Пример: get_form_structure(config_name='ut11', form_name='ФормаЭлемента', parent_name='Склады').",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)", "type": "string"},
                    "form_name": {"description": "Имя формы. Если не указан — список всех форм.", "type": "string"},
                    "parent_name": {
                        "description": "Имя родительского объекта (справочника, документа). Опционально для уточнения.",
                        "type": "string",
                    },
                },
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_knowledge",
            description="База знаний 1С: паттерны (создание справочника, документа, обработки, отчёта на СКД), антипаттерны, best practices. Если query не указан — список всех статей. Если item_id указан — полный текст статьи. Пример: get_knowledge(query='справочник'), get_knowledge(item_id='create_catalog').",
            input_schema={
                "properties": {
                    "category": {"description": "Категория: patterns, antipatterns, best_practices", "type": "string"},
                    "item_id": {
                        "description": "ID статьи для получения полного текста (например 'create_catalog')",
                        "type": "string",
                    },
                    "query": {
                        "description": "Поисковый запрос (например 'справочник', 'СКД', 'обработка')",
                        "type": "string",
                    },
                },
                "required": [],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_object_structure",
            description="Полная структура объекта конфигурации: ресурсы, измерения, реквизиты (с типами), табличные части. ВЫЗЫВАЙТЕ ПЕРЕД НАПИСАНИЕМ ЗАПРОСА для получения точных имён полей. Если object_name не указан — список всех объектов. Пример: get_object_structure(config_name='ut11', object_name='ВыручкаИСебестоимостьПродаж').",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)", "type": "string"},
                    "object_name": {
                        "description": "Имя объекта (справочника, документа, и т.д.). Если не указан — список всех.",
                        "type": "string",
                    },
                    "object_type": {
                        "description": "Тип объекта (Catalog, Document, InformationRegister, и т.д.) — опциональный фильтр",
                        "type": "string",
                    },
                },
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="get_skd_schema",
            description="Структура СКД-схемы (Схемы Компоновки Данных) отчёта или обработки. СКД — основной механизм отчётов в 1С 8.3. Возвращает: наборы данных (data_sets) с запросами, параметры, поля, итоги. Если report_name не указан — список всех СКД-схем в конфигурации. Пример: get_skd_schema(config_name='ut11', report_name='ABCXYZАнализНоменклатуры').",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)", "type": "string"},
                    "report_name": {
                        "description": "Имя отчёта или обработки. Если не указан — список всех СКД-схем.",
                        "type": "string",
                    },
                },
                "required": ["config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="inspect",
            description="Инспекция объектов 1С: cf (конфигурация — обзор всех объектов), meta, form, skd, mxl, role, subsystem. НАЧАЛЬНЫЙ ШАГ для понимания структуры конфигурации. Возвращает свойства и структуру. Пример: inspect(type='cf', path='data/configs/ut11').",
            input_schema={
                "properties": {
                    "config_name": {"type": "string"},
                    "mode": {"type": "string"},
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["target", "path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="list_configs",
            description="Список загруженных конфигураций 1С. ВЫЗЫВАЙТЕ ПЕРВЫМ для понимания какие данные доступны. Возвращает: name, version, status, objects_count. Пример: list_configs().",
            input_schema={"properties": {}, "type": "object"},
        ),
        _build_tool(
            name="openspec_archive",
            description="Архивировать завершённый OpenSpec change. Перемещает proposal в архив. Пример: openspec_archive(id='proposal-001').",
            input_schema={"properties": {"change_id": {"type": "string"}}, "required": ["change_id"], "type": "object"},
        ),
        _build_tool(
            name="openspec_list",
            description="Список OpenSpec changes (управление изменениями). Возвращает массив с id, title, status. Пример: openspec_list() или openspec_list(status='active').",
            input_schema={"properties": {"include_archived": {"type": "boolean"}}, "type": "object"},
        ),
        _build_tool(
            name="openspec_proposal",
            description="Создать OpenSpec proposal (Specification-Driven Development). Принимает title, description, tasks. Возвращает id. Пример: openspec_proposal(title='Добавить справочник', description='Новый справочник').",
            input_schema={
                "properties": {
                    "approach": {"type": "string"},
                    "change_id": {"type": "string"},
                    "context": {"type": "string"},
                    "tasks": {"items": {"type": "string"}, "type": "array"},
                    "title": {"type": "string"},
                },
                "required": ["change_id", "title"],
                "type": "object",
            },
        ),
        _build_tool(
            name="openspec_update_task",
            description="Обновить задачу в OpenSpec change. Принимает proposal_id, task_id, new_status. Пример: openspec_update_task(proposal_id='p1', task_id='t1', new_status='done').",
            input_schema={
                "properties": {
                    "change_id": {"type": "string"},
                    "completed": {"type": "boolean"},
                    "task_index": {"type": "integer"},
                },
                "required": ["change_id", "task_index"],
                "type": "object",
            },
        ),
        _build_tool(
            name="search_1c_methods",
            description="BM25 семантический поиск по методам платформы 1С. ПЕРВЫЙ ШАГ при работе с конфигурацией. После поиска вызовите get_object_structure для получения полей найденного объекта. Возвращает: name_ru, name_en, context, score. Пример: search_1c_methods(query='найти элемент по коду', limit=5)",
            input_schema={
                "properties": {
                    "limit": {"default": 10, "description": "Кол-во результатов (по умолчанию 10)", "type": "integer"},
                    "query": {"description": "Поисковый запрос на русском или английском", "type": "string"},
                },
                "required": ["query"],
                "type": "object",
            },
        ),
        _build_tool(
            name="search_code",
            description="BM25 поиск по коду конфигурации. Ищет по именам методов, сигнатурам, описаниям. Используйте для поиска 'как уже реализовано похожее'. После поиска вызовите get_object_structure для структуры найденного модуля. Пример: search_code(query='создать заказ', config_name='ut11', limit=5)",
            input_schema={
                "properties": {
                    "config_name": {"description": "Имя конфигурации (ut11, edo2, edo3, unp)", "type": "string"},
                    "limit": {"default": 10, "description": "Кол-во результатов (по умолчанию 10)", "type": "integer"},
                    "query": {"description": "Поисковый запрос", "type": "string"},
                },
                "required": ["query", "config_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="skd_trace",
            description="Трассировка поля СКД через всю цепочку: dataset → calculated → resource. Возвращает источник значения поля. Пример: skd_trace(config_name='УТ', template_name='ОсновнаяСхема', field_name='Сумма').",
            input_schema={
                "properties": {"field_name": {"type": "string"}, "template_path": {"type": "string"}},
                "required": ["template_path", "field_name"],
                "type": "object",
            },
        ),
        _build_tool(
            name="solve_check",
            description="Полная проверка .bsl кода: 7 анализаторов. Уровни: 'quick' (4 анализатора, без Java), 'standard' (quick + BSL LS), 'full' (standard + code_metrics + metadata_standards). Возвращает: total_errors, total_warnings, violations, verdict, analyzers_run, metrics (для full). verdict: 'ready' (0 errors), 'warnings' (0 errors, есть warnings), 'errors' (есть errors). Пример: solve_check(file_path='/tmp/module.bsl', level='standard')",
            input_schema={
                "properties": {
                    "file_path": {"description": "Путь к .bsl файлу", "type": "string"},
                    "level": {
                        "default": "standard",
                        "description": "Уровень проверки",
                        "enum": ["quick", "standard", "full"],
                        "type": "string",
                    },
                },
                "required": ["file_path"],
                "type": "object",
            },
        ),
        _build_tool(
            name="solve_context",
            description="Сбор контекста для решения задачи 1С. Собирает 7 источников: методы платформы (BM25), API-справочник, структура объектов (metadata-index), СКД-схемы (skd-index), формы (form-index), база знаний (паттерны/антипаттерны), стандарты 1С (302 проверки). Используй ПЕРВЫМ шагом при решении любой задачи. Пример: solve_context(query='создать справочник Товары', config='ut11')",
            input_schema={
                "properties": {
                    "config": {"default": "", "description": "Имя конфигурации (необязательно)", "type": "string"},
                    "limit": {"default": 5, "description": "Лимит результатов на источник", "type": "integer"},
                    "query": {"description": "Описание задачи", "type": "string"},
                },
                "required": ["query"],
                "type": "object",
            },
        ),
        _build_tool(
            name="validate_generated",
            description="Валидация сгенерированного кода: BSL-синтаксис (сбалансированность областей, процедур, циклов), XML-структура (обязательные теги, UUID), целостность файлов. Возвращает: verdict (perfect/warnings/errors), total_errors, total_warnings. Пример: validate_generated(source_dir='generated/ВыгрузкаНоменклатуры').",
            input_schema={
                "properties": {
                    "source_dir": {"description": "Путь к каталогу со структурой обработки/отчёта", "type": "string"}
                },
                "required": ["source_dir"],
                "type": "object",
            },
        ),
    ]


def get_all_descriptions() -> list[dict]:
    """Статическое описание tools (для CLI без запуска сервера).

    Возвращает: [{name, description, required_params, optional_params}]
    """
    return [
        {
            "name": "analyze_architecture",
            "description": "Анализ архитектуры: циклические зависимости, God Object, мёртвый код, layering, regions, queries in forms. Пример: analyze_architecture(config_dir='data/configs/ut11').",
            "required_params": ["config_dir"],
            "optional_params": [],
        },
        {
            "name": "analyze_bsl",
            "description": "Анализ .bsl файла через BSL Language Server (187 диагностик). Возвращает: total, by_code, diagnostics. Требует установленного BSL LS (Java).",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "analyze_queries",
            "description": "Анализ запросов 1С: SELECT *, LIKE %, функции в WHERE, JOIN без ON, временные таблицы без индексов. Пример: analyze_queries(file_path='module.bsl').",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "audit_security",
            "description": "Аудит безопасности BSL кода: SQL-инъекции, Выполнить(), хардкод паролей/токенов, COM-объекты, привилегированный режим, path traversal, небезопасная десериализация. 15 правил. Пример: audit_security(file_path='module.bsl').",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "build_dependency_graph",
            "description": "Построить граф зависимостей метаданных 1С (networkx).",
            "required_params": ["config_name"],
            "optional_params": [],
        },
        {
            "name": "build_epf",
            "description": "Упаковка структуры каталога в .epf файл (внешняя обработка 1С). Принимает путь к каталогу (из generate_processing) и создаёт .epf. Пример: build_epf(source_dir='generated/ВыгрузкаНоменклатуры', output_path='ВыгрузкаНоменклатуры.epf').",
            "required_params": ["source_dir", "output_path"],
            "optional_params": ["object_name", "object_type"],
        },
        {
            "name": "call_graph",
            "description": "Граф вызовов методов конфигурации. Кто кого вызывает, мёртвый код, циклы. Action: stats, callers, callees, dead-code, cycles. Пример: call_graph(config_name='obhod', action='callees', module='ОбменДокументы', method='ВыполнитьПолныйОбмен').",
            "required_params": ["config_name", "action"],
            "optional_params": ["module", "method"],
        },
        {
            "name": "cfe_borrow",
            "description": "Заимствовать объект из конфигурации в расширение (CFE).",
            "required_params": ["extension_path", "config_path", "object_ref"],
            "optional_params": [],
        },
        {
            "name": "cfe_diff",
            "description": "Анализ расширения CFE: что заимствовано, что перехвачено.",
            "required_params": ["extension_path", "config_path"],
            "optional_params": [],
        },
        {
            "name": "cfe_patch_method",
            "description": "Сгенерировать BSL перехватчик (&Перед/&После/&ИзменениеИКонтроль).",
            "required_params": ["extension_path", "module_path", "method_name", "interceptor_type"],
            "optional_params": [],
        },
        {
            "name": "check_form_quality",
            "description": "Проверка качества форм: пустые, перегруженные, элементы без DataPath, кнопки без команд, дубли. Пример: check_form_quality(config_name='ut11').",
            "required_params": ["config_name"],
            "optional_params": [],
        },
        {
            "name": "check_skd_quality",
            "description": "Проверка качества СКД: без параметров, без отборов, пустые запросы, перегруженные. Пример: check_skd_quality(config_name='ut11').",
            "required_params": ["config_name"],
            "optional_params": [],
        },
        {
            "name": "check_standards",
            "description": "Проверка .bsl файла на 56 правил стандартов 1С. Возвращает: список нарушений (rule_id, severity, line, message). Не требует Java — работает мгновенно.",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "check_transactions",
            "description": "Проверка транзакций BSL: несбалансированные, без Try/Catch, интерактив в транзакции, длинные/вложенные. Пример: check_transactions(file_path='module.bsl').",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "data_status",
            "description": "Статус данных проекта: что доступно (платформа, конфигурации), что нужно перестроить, доступен ли autosave пакет. Используй, если данные не находятся — возможно нужно autoload.",
            "required_params": [],
            "optional_params": [],
        },
        {
            "name": "dependency_query",
            "description": "Запрос к графу зависимостей: what_depends_on, dependencies_of, find_cycles, find_unused_objects, и т.д.",
            "required_params": ["config_name", "query_type", "object_ref"],
            "optional_params": ["target"],
        },
        {
            "name": "diff_configs",
            "description": "Сравнение версий конфигурации: добавленные/удалённые/изменённые объекты, реквизиты, формы, роли. Пример: diff_configs(old_path='old.json', new_path='new.json').",
            "required_params": ["old_path", "new_path"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_form",
            "description": "JSON DSL → Form.xml управляемой формы.",
            "required_params": ["definition", "output_path"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_meta",
            "description": "JSON DSL → XML метаданных 1С (23 типа объектов: Catalog, Document, Enum, и т.д.).",
            "required_params": ["definition", "output_dir"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_mxl",
            "description": "JSON DSL → MXL Template.xml (печатная форма).",
            "required_params": ["definition", "output_path"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_role",
            "description": "JSON DSL → Rights.xml роли 1С.",
            "required_params": ["definition", "output_dir"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_skd",
            "description": "JSON DSL → СКД Template.xml (схема компоновки данных).",
            "required_params": ["definition", "output_path"],
            "optional_params": [],
        },
        {
            "name": "epf_factory_create",
            "description": "Создать внешнюю обработку 1С (.epf) из BSL-кода через полный цикл: шаблоны v8unpack → подстановка name/synonym/UUID → запись BSL-модуля → проверка BSL LS → сборка .epf → round-trip. Не требует 1С. Пример: epf_factory_create(name='МояОбработка', bsl_code='...', output_path='/tmp/МояОбработка.epf').",
            "required_params": ["name", "output_path"],
            "optional_params": ["synonym", "bsl_code", "bsl_path", "form_name", "skip_bsl_validation", "save_sources"],
        },
        {
            "name": "epf_factory_templates",
            "description": "Список доступных шаблонов для epf_factory_create (ExternalDataProcessor.json, Form.json, Form.id.json, Form.elem.empty.json).",
            "required_params": [],
            "optional_params": [],
        },
        {
            "name": "generate_processing",
            "description": "Генерация внешней обработки 1С: модуль объекта, модуль формы, XML метаданные. Создаёт структуру файлов готовую для упаковки в .epf. Пример: generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры').",
            "required_params": ["name", "synonym"],
            "optional_params": ["description", "author", "output_dir"],
        },
        {
            "name": "generate_report",
            "description": "Генерация отчёта на СКД: модуль объекта с СКД-логикой, форма отчёта, СКД-схема (DataCompositionSchema). Пример: generate_report(name='ОтчетПоПродажам', synonym='Отчёт по продажам', data_source='Документ.РеализацияТоваровУслуг').",
            "required_params": ["name", "synonym"],
            "optional_params": ["description", "author", "output_dir", "data_source", "main_query"],
        },
        {
            "name": "get_api_reference",
            "description": "API-справочник конфигурации — экспортные методы общих модулей. Если module не указан — возвращает список всех модулей с кол-вом методов. Если module указан — возвращает методы конкретного модуля.",
            "required_params": ["config_name"],
            "optional_params": ["module"],
        },
        {
            "name": "get_code_metrics",
            "description": "Метрики кода BSL: LOC, цикломатическая/когнитивная сложность, вложенность, дублирование, God Object, Long Method, Too Many Params, техдолг, health score. Пример: get_code_metrics(file_path='module.bsl').",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "get_form_elements",
            "description": "Элементы формы конфигурации (кнопки, поля, таблицы, группы). Пример: get_form_elements(config_name='obhod', form_name='Форма.ФормаАвторизации'). Если form_name не указан — возвращает список всех форм.",
            "required_params": ["config_name"],
            "optional_params": ["form_name"],
        },
        {
            "name": "get_form_structure",
            "description": "Полная структура формы: элементы (InputField, Button, Table, и т.д.), их свойства (data_path, visible, enabled), события и обработчики, дерево элементов (ChildItems). Если form_name не указан — список всех форм. Пример: get_form_structure(config_name='ut11', form_name='ФормаЭлемента').",
            "required_params": ["config_name"],
            "optional_params": ["form_name", "parent_name"],
        },
        {
            "name": "get_knowledge",
            "description": "База знаний 1С: паттерны (создание справочника, документа, обработки, отчёта СКД), антипаттерны, best practices. Если query не указан — список всех статей. Если item_id указан — полный текст статьи. Пример: get_knowledge(query='справочник'), get_knowledge(item_id='create_catalog').",
            "required_params": [],
            "optional_params": ["query", "item_id", "category"],
        },
        {
            "name": "get_object_structure",
            "description": "Полная структура объекта конфигурации: реквизиты, табличные части, формы, команды, предопределённые значения. Если object_name не указан — возвращает список всех объектов с краткой информацией. Пример: get_object_structure(config_name='ut11', object_name='Склады').",
            "required_params": ["config_name"],
            "optional_params": ["object_name", "object_type"],
        },
        {
            "name": "get_skd_schema",
            "description": "Структура СКД-схемы (Схемы Компоновки Данных) отчёта или обработки. Наборы данных (с запросами), параметры, поля, итоги. Если report_name не указан — список всех СКД-схем. Пример: get_skd_schema(config_name='ut11', report_name='ABCXYZАнализНоменклатуры').",
            "required_params": ["config_name"],
            "optional_params": ["report_name"],
        },
        {
            "name": "inspect",
            "description": "Единый анализ объектов 1С: cf, meta, form, skd, mxl, role, subsystem, depgraph.",
            "required_params": ["target", "path"],
            "optional_params": ["mode", "name", "config_name"],
        },
        {
            "name": "list_configs",
            "description": "Список загруженных конфигураций 1С. Возвращает: name, version, status, objects_count, api_methods_count. Используй первым шагом, чтобы понять, какие данные доступны.",
            "required_params": [],
            "optional_params": [],
        },
        {
            "name": "openspec_archive",
            "description": "Архивировать завершённый OpenSpec change.",
            "required_params": ["change_id"],
            "optional_params": [],
        },
        {
            "name": "openspec_list",
            "description": "Список OpenSpec changes.",
            "required_params": [],
            "optional_params": ["include_archived"],
        },
        {
            "name": "openspec_proposal",
            "description": "Создать OpenSpec proposal (Specification-Driven Development).",
            "required_params": ["change_id", "title"],
            "optional_params": ["context", "approach", "tasks"],
        },
        {
            "name": "openspec_update_task",
            "description": "Обновить задачу в OpenSpec change (отметить завершённой/незавершённой).",
            "required_params": ["change_id", "task_index"],
            "optional_params": ["completed"],
        },
        {
            "name": "search_1c_methods",
            "description": "TF-IDF/BM25 семантический поиск по 8141 методам платформы 1С. Возвращает: name_ru, name_en, syntax, description, context. Пример: search_1c_methods(query='найти элемент по коду', limit=5)",
            "required_params": ["query"],
            "optional_params": ["limit"],
        },
        {
            "name": "search_code",
            "description": "BM25 поиск по коду конфигурации (115K+ методов). Ищет по именам методов, сигнатурам, описаниям. Пример: search_code(query='создать заказ', config_name='ut11', limit=5). Используй для поиска 'как уже реализовано похожее' в конфигурации.",
            "required_params": ["query", "config_name"],
            "optional_params": ["limit"],
        },
        {
            "name": "skd_trace",
            "description": "Трассировка поля СКД через всю цепочку: dataset → calculated → resource.",
            "required_params": ["template_path", "field_name"],
            "optional_params": [],
        },
        {
            "name": "solve_check",
            "description": "Полная проверка .bsl кода: 7 анализаторов. Уровни: 'quick' (4 анализатора, без Java), 'standard' (quick + BSL LS), 'full' (standard + code_metrics + metadata_standards). Возвращает: total_errors, total_warnings, violations, verdict, analyzers_run, metrics (для full). verdict: 'ready' / 'warnings' / 'errors'.",
            "required_params": ["file_path"],
            "optional_params": ["level"],
        },
        {
            "name": "solve_context",
            "description": "Сбор контекста для решения задачи 1С. Собирает 7 источников: методы платформы (BM25), API-справочник, структура объектов (metadata-index), СКД-схемы (skd-index), формы (form-index), база знаний (паттерны/антипаттерны), стандарты 1С (302 проверки). Используй ПЕРВЫМ шагом при решении любой задачи.",
            "required_params": ["query"],
            "optional_params": ["config", "limit"],
        },
        {
            "name": "validate_generated",
            "description": "Валидация сгенерированного кода: BSL-синтаксис (области, процедуры, циклы), XML-структура, целостность файлов. Возвращает: verdict (perfect/warnings/errors), total_errors, total_warnings. Пример: validate_generated(source_dir='generated/ВыгрузкаНоменклатуры').",
            "required_params": ["source_dir"],
            "optional_params": [],
        },
    ]
