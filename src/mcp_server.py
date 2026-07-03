"""
MCP-сервер для 1C AI Development Environment.

Экспортирует 7 tools для MCP-совместимых клиентов (Cursor, Claude Desktop, VS Code, и т.д.).

Запуск: 1c-ai mcp serve
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .project import Project
from .services.logger import configure_logging, get_logger

# MCP-сервер пишет логи в stderr (stdout занят под MCP-протокол)
# JSON-формат включается через LOG_FORMAT=json
configure_logging()
log = get_logger("src.mcp_server")


def _get_tools_description() -> list[dict]:
    """
    Статическое описание tools (для CLI без запуска сервера).

    Возвращает: [{name, description, required_params, optional_params}]
    """
    return [
        {
            "name": "list_configs",
            "description": "Список загруженных конфигураций 1С. Возвращает: name, version, status, objects_count, api_methods_count. Используй первым шагом, чтобы понять, какие данные доступны.",
            "required_params": [],
            "optional_params": [],
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
            "name": "call_graph",
            "description": "Граф вызовов методов конфигурации. Кто кого вызывает, мёртвый код, циклы. Action: stats, callers, callees, dead-code, cycles. Пример: call_graph(config_name='obhod', action='callees', module='ОбменДокументы', method='ВыполнитьПолныйОбмен').",
            "required_params": ["config_name", "action"],
            "optional_params": ["module", "method"],
        },
        {
            "name": "get_form_elements",
            "description": "Элементы формы конфигурации (кнопки, поля, таблицы, группы). Пример: get_form_elements(config_name='obhod', form_name='Форма.ФормаАвторизации'). Если form_name не указан — возвращает список всех форм.",
            "required_params": ["config_name"],
            "optional_params": ["form_name"],
        },
        {
            "name": "get_api_reference",
            "description": "API-справочник конфигурации — экспортные методы общих модулей. Если module не указан — возвращает список всех модулей с кол-вом методов. Если module указан — возвращает методы конкретного модуля.",
            "required_params": ["config_name"],
            "optional_params": ["module"],
        },
        {
            "name": "analyze_bsl",
            "description": "Анализ .bsl файла через BSL Language Server (187 диагностик). Возвращает: total, by_code, diagnostics. Требует установленного BSL LS (Java).",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "check_standards",
            "description": "Проверка .bsl файла на 56 правил стандартов 1С. Возвращает: список нарушений (rule_id, severity, line, message). Не требует Java — работает мгновенно.",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "solve_context",
            "description": "Сбор контекста для решения задачи 1С. Собирает 7 источников: методы платформы (BM25), API-справочник, структура объектов (metadata-index), СКД-схемы (skd-index), формы (form-index), база знаний (паттерны/антипаттерны), стандарты 1С (302 проверки). Используй ПЕРВЫМ шагом при решении любой задачи.",
            "required_params": ["query"],
            "optional_params": ["config", "limit"],
        },
        {
            "name": "solve_check",
            "description": "Полная проверка .bsl кода: 7 анализаторов. Уровни: 'quick' (4 анализатора, без Java), 'standard' (quick + BSL LS), 'full' (standard + code_metrics + metadata_standards). Возвращает: total_errors, total_warnings, violations, verdict, analyzers_run, metrics (для full). verdict: 'ready' / 'warnings' / 'errors'.",
            "required_params": ["file_path"],
            "optional_params": ["level"],
        },
        {
            "name": "data_status",
            "description": "Статус данных проекта: что доступно (платформа, конфигурации), что нужно перестроить, доступен ли autosave пакет. Используй, если данные не находятся — возможно нужно autoload.",
            "required_params": [],
            "optional_params": [],
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
            "name": "get_form_structure",
            "description": "Полная структура формы: элементы (InputField, Button, Table, и т.д.), их свойства (data_path, visible, enabled), события и обработчики, дерево элементов (ChildItems). Если form_name не указан — список всех форм. Пример: get_form_structure(config_name='ut11', form_name='ФормаЭлемента').",
            "required_params": ["config_name"],
            "optional_params": ["form_name", "parent_name"],
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
            "name": "build_epf",
            "description": "Упаковка структуры каталога в .epf файл (внешняя обработка 1С). Принимает путь к каталогу (из generate_processing) и создаёт .epf. Пример: build_epf(source_dir='generated/ВыгрузкаНоменклатуры', output_path='ВыгрузкаНоменклатуры.epf').",
            "required_params": ["source_dir", "output_path"],
            "optional_params": ["object_name", "object_type"],
        },
        {
            "name": "validate_generated",
            "description": "Валидация сгенерированного кода: BSL-синтаксис (области, процедуры, циклы), XML-структура, целостность файлов. Возвращает: verdict (perfect/warnings/errors), total_errors, total_warnings. Пример: validate_generated(source_dir='generated/ВыгрузкаНоменклатуры').",
            "required_params": ["source_dir"],
            "optional_params": [],
        },
        {
            "name": "get_knowledge",
            "description": "База знаний 1С: паттерны (создание справочника, документа, обработки, отчёта СКД), антипаттерны, best practices. Если query не указан — список всех статей. Если item_id указан — полный текст статьи. Пример: get_knowledge(query='справочник'), get_knowledge(item_id='create_catalog').",
            "required_params": [],
            "optional_params": ["query", "item_id", "category"],
        },
        {
            "name": "audit_security",
            "description": "Аудит безопасности BSL кода: SQL-инъекции, Выполнить(), хардкод паролей/токенов, COM-объекты, привилегированный режим, path traversal, небезопасная десериализация. 15 правил. Пример: audit_security(file_path='module.bsl').",
            "required_params": ["file_path"],
            "optional_params": [],
        },
        {
            "name": "get_code_metrics",
            "description": "Метрики кода BSL: LOC, цикломатическая/когнитивная сложность, вложенность, дублирование, God Object, Long Method, Too Many Params, техдолг, health score. Пример: get_code_metrics(file_path='module.bsl').",
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
            "name": "analyze_architecture",
            "description": "Анализ архитектуры: циклические зависимости, God Object, мёртвый код, layering, regions, queries in forms. Пример: analyze_architecture(config_dir='data/configs/ut11').",
            "required_params": ["config_dir"],
            "optional_params": [],
        },
        {
            "name": "analyze_queries",
            "description": "Анализ запросов 1С: SELECT *, LIKE %, функции в WHERE, JOIN без ON, временные таблицы без индексов. Пример: analyze_queries(file_path='module.bsl').",
            "required_params": ["file_path"],
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
            "name": "diff_configs",
            "description": "Сравнение версий конфигурации: добавленные/удалённые/изменённые объекты, реквизиты, формы, роли. Пример: diff_configs(old_path='old.json', new_path='new.json').",
            "required_params": ["old_path", "new_path"],
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
        # P1.2: 16 tools, отсутствовавших в статическом описании (синхронизация с list_tools handler)
        {
            "name": "dsl_compile_meta",
            "description": "JSON DSL → XML метаданных 1С (23 типа объектов: Catalog, Document, Enum, и т.д.).",
            "required_params": ["definition", "output_dir"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_form",
            "description": "JSON DSL → Form.xml управляемой формы.",
            "required_params": ["definition", "output_path"],
            "optional_params": [],
        },
        {
            "name": "dsl_compile_skd",
            "description": "JSON DSL → СКД Template.xml (схема компоновки данных).",
            "required_params": ["definition", "output_path"],
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
            "name": "cfe_borrow",
            "description": "Заимствовать объект из конфигурации в расширение (CFE).",
            "required_params": ["extension_path", "config_path", "object_ref"],
            "optional_params": [],
        },
        {
            "name": "cfe_patch_method",
            "description": "Сгенерировать BSL перехватчик (&Перед/&После/&ИзменениеИКонтроль).",
            "required_params": ["extension_path", "module_path", "method_name", "interceptor_type"],
            "optional_params": [],
        },
        {
            "name": "cfe_diff",
            "description": "Анализ расширения CFE: что заимствовано, что перехвачено.",
            "required_params": ["extension_path", "config_path"],
            "optional_params": [],
        },
        {
            "name": "skd_trace",
            "description": "Трассировка поля СКД через всю цепочку: dataset → calculated → resource.",
            "required_params": ["template_path", "field_name"],
            "optional_params": [],
        },
        {
            "name": "build_dependency_graph",
            "description": "Построить граф зависимостей метаданных 1С (networkx).",
            "required_params": ["config_name"],
            "optional_params": [],
        },
        {
            "name": "dependency_query",
            "description": "Запрос к графу зависимостей: what_depends_on, dependencies_of, find_cycles, find_unused_objects, и т.д.",
            "required_params": ["config_name", "query_type", "object_ref"],
            "optional_params": ["target"],
        },
        {
            "name": "inspect",
            "description": "Единый анализ объектов 1С: cf, meta, form, skd, mxl, role, subsystem, depgraph.",
            "required_params": ["target", "path"],
            "optional_params": ["mode", "name", "config_name"],
        },
        {
            "name": "openspec_proposal",
            "description": "Создать OpenSpec proposal (Specification-Driven Development).",
            "required_params": ["change_id", "title"],
            "optional_params": ["context", "approach", "tasks"],
        },
        {
            "name": "openspec_list",
            "description": "Список OpenSpec changes.",
            "required_params": [],
            "optional_params": ["include_archived"],
        },
        {
            "name": "openspec_update_task",
            "description": "Обновить задачу в OpenSpec change (отметить завершённой/незавершённой).",
            "required_params": ["change_id", "task_index"],
            "optional_params": ["completed"],
        },
        {
            "name": "openspec_archive",
            "description": "Архивировать завершённый OpenSpec change.",
            "required_params": ["change_id"],
            "optional_params": [],
        },
    ]


def create_mcp_server() -> Server:
    """Создать MCP-сервер с tools для 1C AI Development Environment."""
    server = Server("1c-ai-dev-env")
    project = Project()

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Возвращает список всех доступных tools."""
        return [
            types.Tool(
                name="list_configs",
                description=(
                    "Список загруженных конфигураций 1С. "
                    "Возвращает: name, version, status, objects_count, api_methods_count. "
                    "Используй первым шагом, чтобы понять, какие данные доступны."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="search_1c_methods",
                description=(
                    "TF-IDF/BM25 семантический поиск по 8141 методам платформы 1С. "
                    "Возвращает: name_ru, name_en, syntax, description, context. "
                    "Пример: search_1c_methods(query='найти элемент по коду', limit=5)"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос на русском или английском",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Кол-во результатов (по умолчанию 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="search_code",
                description=(
                    "BM25 поиск по коду конфигурации (115K+ методов). "
                    "Ищет по именам методов, сигнатурам, описаниям. "
                    "Используй для поиска 'как уже реализовано похожее' в конфигурации. "
                    "Пример: search_code(query='создать заказ', config_name='ut11', limit=5)"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос",
                        },
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации (ut11, edo2, edo3, unp)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Кол-во результатов (по умолчанию 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query", "config_name"],
                },
            ),
            types.Tool(
                name="call_graph",
                description=(
                    "Граф вызовов методов конфигурации. "
                    "Кто кого вызывает, мёртвый код, циклические зависимости. "
                    "Action: stats (статистика), callers (кто вызывает), "
                    "callees (кого вызывает), dead-code (мёртвый код), cycles (циклы). "
                    "Пример: call_graph(config_name='obhod', action='callees', "
                    "module='ОбменДокументы', method='ВыполнитьПолныйОбмен')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации",
                        },
                        "action": {
                            "type": "string",
                            "description": "Действие: stats, callers, callees, dead-code, cycles",
                            "default": "stats",
                        },
                        "module": {
                            "type": "string",
                            "description": "Имя модуля (для callers/callees)",
                        },
                        "method": {
                            "type": "string",
                            "description": "Имя метода (для callers/callees)",
                        },
                    },
                    "required": ["config_name", "action"],
                },
            ),
            types.Tool(
                name="get_form_elements",
                description=(
                    "Элементы формы конфигурации (кнопки, поля, таблицы, группы). "
                    "Если form_name не указан — возвращает список всех форм. "
                    "Пример: get_form_elements(config_name='obhod', form_name='Форма.ФормаАвторизации')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации",
                        },
                        "form_name": {
                            "type": "string",
                            "description": "Имя формы (необязательно). Если пусто — список всех форм.",
                        },
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="get_api_reference",
                description=(
                    "API-справочник конфигурации — экспортные методы общих модулей. "
                    "Если module не указан — возвращает список всех модулей с кол-вом методов. "
                    "Если module указан — возвращает методы конкретного модуля. "
                    "Пример: get_api_reference(config_name='ut11', module='ОбщегоНазначения')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации (ut11, priemka, и т.д.)",
                        },
                        "module": {
                            "type": "string",
                            "description": "Имя модуля (необязательно). Если пусто — все модули.",
                            "default": "",
                        },
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="analyze_bsl",
                description=(
                    "Анализ .bsl файла через BSL Language Server (187 диагностик). "
                    "Возвращает: total, by_code (диагностика → кол-во), diagnostics (список). "
                    "Требует установленного BSL LS (Java). "
                    "Пример: analyze_bsl(file_path='/tmp/module.bsl')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Путь к .bsl файлу",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="check_standards",
                description=(
                    "Проверка .bsl файла на 56 правил стандартов 1С. "
                    "Возвращает: список нарушений (rule_id, severity, line, message). "
                    "Не требует Java — работает мгновенно. "
                    "Пример: check_standards(file_path='/tmp/module.bsl')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Путь к .bsl файлу",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="solve_context",
                description=(
                    "Сбор контекста для решения задачи 1С. "
                    "Собирает 7 источников: методы платформы (BM25), API-справочник, "
                    "структура объектов (metadata-index), СКД-схемы (skd-index), "
                    "формы (form-index), база знаний (паттерны/антипаттерны), "
                    "стандарты 1С (302 проверки). "
                    "Используй ПЕРВЫМ шагом при решении любой задачи. "
                    "Пример: solve_context(query='создать справочник Товары', config='ut11')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Описание задачи",
                        },
                        "config": {
                            "type": "string",
                            "description": "Имя конфигурации (необязательно)",
                            "default": "",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Лимит результатов на источник",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="solve_check",
                description=(
                    "Полная проверка .bsl кода: 7 анализаторов. "
                    "Уровни: 'quick' (4 анализатора, без Java), "
                    "'standard' (quick + BSL LS), "
                    "'full' (standard + code_metrics + metadata_standards). "
                    "Возвращает: total_errors, total_warnings, violations, verdict, "
                    "analyzers_run, metrics (для full). "
                    "verdict: 'ready' (0 errors), 'warnings' (0 errors, есть warnings), "
                    "'errors' (есть errors). "
                    "Пример: solve_check(file_path='/tmp/module.bsl', level='standard')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Путь к .bsl файлу",
                        },
                        "level": {
                            "type": "string",
                            "enum": ["quick", "standard", "full"],
                            "default": "standard",
                            "description": "Уровень проверки",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="data_status",
                description=(
                    "Статус данных проекта: что доступно (платформа, конфигурации), "
                    "что нужно перестроить, доступен ли autosave пакет. "
                    "Используй, если данные не находятся — возможно нужно autoload через CLI. "
                    "Возвращает: has_platform_index, has_platform_methods, configs[], autosave_available."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="get_object_structure",
                description=(
                    "Полная структура объекта конфигурации: реквизиты (с типами данных), "
                    "табличные части (с реквизитами), формы, команды, предопределённые значения. "
                    "Если object_name не указан — возвращает список всех объектов с краткой информацией. "
                    "Пример: get_object_structure(config_name='ut11', object_name='Склады'). "
                    "Возвращает: name, uuid, synonym, attributes[{name, types, synonym}], "
                    "tabular_sections[{name, attributes}], forms, commands."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Имя объекта (справочника, документа, и т.д.). Если не указан — список всех.",
                        },
                        "object_type": {
                            "type": "string",
                            "description": "Тип объекта (Catalog, Document, InformationRegister, и т.д.) — опциональный фильтр",
                        },
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="get_skd_schema",
                description=(
                    "Структура СКД-схемы (Схемы Компоновки Данных) отчёта или обработки. "
                    "СКД — основной механизм отчётов в 1С 8.3. "
                    "Возвращает: наборы данных (data_sets) с запросами, параметры, поля, итоги. "
                    "Если report_name не указан — список всех СКД-схем в конфигурации. "
                    "Пример: get_skd_schema(config_name='ut11', report_name='ABCXYZАнализНоменклатуры')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)",
                        },
                        "report_name": {
                            "type": "string",
                            "description": "Имя отчёта или обработки. Если не указан — список всех СКД-схем.",
                        },
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="get_form_structure",
                description=(
                    "Полная структура формы: элементы (InputField, Button, Table, UsualGroup, и т.д.), "
                    "их свойства (data_path, visible, enabled, read_only), события и обработчики, "
                    "дерево элементов (ChildItems). "
                    "Если form_name не указан — список всех форм с краткой информацией. "
                    "Пример: get_form_structure(config_name='ut11', form_name='ФормаЭлемента', parent_name='Склады')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {
                            "type": "string",
                            "description": "Имя конфигурации (ut11, edo2, edo3, unp, obhod)",
                        },
                        "form_name": {
                            "type": "string",
                            "description": "Имя формы. Если не указан — список всех форм.",
                        },
                        "parent_name": {
                            "type": "string",
                            "description": "Имя родительского объекта (справочника, документа). Опционально для уточнения.",
                        },
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="generate_processing",
                description=(
                    "Генерация внешней обработки 1С. Создаёт структуру файлов: "
                    "модуль объекта (Ext/Module.bsl), модуль формы (Forms/Форма/Ext/Form/Module.bsl), "
                    "XML метаданные. Готово для упаковки в .epf. "
                    "Пример: generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Имя обработки (латиница, без пробелов)",
                        },
                        "synonym": {
                            "type": "string",
                            "description": "Синоним (русское название)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Описание обработки (опционально)",
                        },
                        "author": {
                            "type": "string",
                            "description": "Автор (опционально)",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Куда сохранить (по умолчанию generated/<name>)",
                        },
                    },
                    "required": ["name", "synonym"],
                },
            ),
            types.Tool(
                name="generate_report",
                description=(
                    "Генерация отчёта на СКД (Схеме Компоновки Данных). Создаёт: "
                    "модуль объекта с СКД-логикой, форму отчёта, СКД-схему (DataCompositionSchema). "
                    "Пример: generate_report(name='ОтчетПоПродажам', synonym='Отчёт по продажам', "
                    "data_source='Документ.РеализацияТоваровУслуг')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Имя отчёта (латиница, без пробелов)",
                        },
                        "synonym": {
                            "type": "string",
                            "description": "Синоним (русское название)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Описание отчёта (опционально)",
                        },
                        "author": {
                            "type": "string",
                            "description": "Автор (опционально)",
                        },
                        "data_source": {
                            "type": "string",
                            "description": "Источник данных (например 'Документ.РеализацияТоваровУслуг')",
                        },
                        "main_query": {
                            "type": "string",
                            "description": "Готовый запрос 1С (если пусто — будет шаблонный)",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Куда сохранить (по умолчанию generated/<name>)",
                        },
                    },
                    "required": ["name", "synonym"],
                },
            ),
            types.Tool(
                name="build_epf",
                description=(
                    "Упаковка структуры каталога в .epf файл (внешняя обработка 1С). "
                    "Принимает путь к каталогу (из generate_processing или generate_report) "
                    "и создаёт .epf файл. "
                    "Пример: build_epf(source_dir='generated/ВыгрузкаНоменклатуры', "
                    "output_path='ВыгрузкаНоменклатуры.epf')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_dir": {
                            "type": "string",
                            "description": "Путь к каталогу со структурой обработки/отчёта",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Куда сохранить .epf файл",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Имя объекта (если не указано — берётся из имени каталога)",
                        },
                        "object_type": {
                            "type": "string",
                            "description": "Тип объекта: DataProcessor (по умолчанию) или Report",
                        },
                    },
                    "required": ["source_dir", "output_path"],
                },
            ),
            types.Tool(
                name="validate_generated",
                description=(
                    "Валидация сгенерированного кода: BSL-синтаксис (сбалансированность "
                    "областей, процедур, циклов), XML-структура (обязательные теги, UUID), "
                    "целостность файлов. "
                    "Возвращает: verdict (perfect/warnings/errors), total_errors, total_warnings. "
                    "Пример: validate_generated(source_dir='generated/ВыгрузкаНоменклатуры')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_dir": {
                            "type": "string",
                            "description": "Путь к каталогу со структурой обработки/отчёта",
                        },
                    },
                    "required": ["source_dir"],
                },
            ),
            types.Tool(
                name="get_knowledge",
                description=(
                    "База знаний 1С: паттерны (создание справочника, документа, обработки, "
                    "отчёта на СКД), антипаттерны, best practices. "
                    "Если query не указан — список всех статей. "
                    "Если item_id указан — полный текст статьи. "
                    "Пример: get_knowledge(query='справочник'), "
                    "get_knowledge(item_id='create_catalog')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос (например 'справочник', 'СКД', 'обработка')",
                        },
                        "item_id": {
                            "type": "string",
                            "description": "ID статьи для получения полного текста (например 'create_catalog')",
                        },
                        "category": {
                            "type": "string",
                            "description": "Категория: patterns, antipatterns, best_practices",
                        },
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="audit_security",
                description=(
                    "Аудит безопасности BSL кода: SQL-инъекции, Выполнить(), "
                    "хардкод паролей/токенов, COM-объекты, привилегированный режим, "
                    "path traversal, небезопасная десериализация. 15 правил. "
                    "Пример: audit_security(file_path='module.bsl')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Путь к .bsl файлу для аудита",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="get_code_metrics",
                description=(
                    "Метрики кода BSL: LOC (строки кода), цикломатическая/когнитивная сложность, "
                    "вложенность, дублирование кода, God Object, Long Method, Too Many Params, "
                    "технический долг, health score (0-100). "
                    "Пример: get_code_metrics(file_path='module.bsl')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Путь к .bsl файлу",
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="check_transactions",
                description=(
                    "Проверка транзакций BSL: несбалансированные, без Try/Catch, "
                    "интерактив в транзакции, длинные/вложенные транзакции. "
                    "Пример: check_transactions(file_path='module.bsl')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Путь к .bsl файлу"},
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="analyze_architecture",
                description=(
                    "Анализ архитектуры конфигурации: циклические зависимости, God Object, "
                    "мёртвый код, layering, regions, queries in forms. "
                    "Пример: analyze_architecture(config_dir='data/configs/ut11')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_dir": {"type": "string", "description": "Путь к директории конфигурации"},
                    },
                    "required": ["config_dir"],
                },
            ),
            types.Tool(
                name="analyze_queries",
                description=(
                    "Анализ запросов 1С в BSL коде: SELECT *, LIKE %, функции в WHERE, "
                    "JOIN без ON, временные таблицы без индексов. "
                    "Пример: analyze_queries(file_path='module.bsl')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Путь к .bsl файлу"},
                    },
                    "required": ["file_path"],
                },
            ),
            types.Tool(
                name="check_form_quality",
                description=(
                    "Проверка качества форм: пустые формы, перегруженные, элементы без DataPath, "
                    "кнопки без команд, дублирующие имена. "
                    "Пример: check_form_quality(config_name='ut11')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {"type": "string", "description": "Имя конфигурации"},
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="check_skd_quality",
                description=(
                    "Проверка качества СКД-схем: без параметров, без отборов, пустые запросы, "
                    "перегруженные. "
                    "Пример: check_skd_quality(config_name='ut11')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {"type": "string", "description": "Имя конфигурации"},
                    },
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="diff_configs",
                description=(
                    "Сравнение версий конфигурации: добавленные/удалённые/изменённые объекты, "
                    "реквизиты, формы, команды, роли, подсистемы. "
                    "Пример: diff_configs(old_path='old.json', new_path='new.json')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_path": {"type": "string", "description": "Путь к старому unified-metadata-index.json"},
                        "new_path": {"type": "string", "description": "Путь к новому unified-metadata-index.json"},
                    },
                    "required": ["old_path", "new_path"],
                },
            ),
            types.Tool(
                name="dsl_compile_meta",
                description="JSON DSL → XML метаданных 1С (23 типа объектов).",
                inputSchema={
                    "type": "object",
                    "properties": {"definition": {"type": "object"}, "output_dir": {"type": "string"}},
                    "required": ["definition", "output_dir"],
                },
            ),
            types.Tool(
                name="dsl_compile_form",
                description="JSON DSL → Form.xml управляемой формы.",
                inputSchema={
                    "type": "object",
                    "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                    "required": ["definition", "output_path"],
                },
            ),
            types.Tool(
                name="dsl_compile_skd",
                description="JSON DSL → СКД Template.xml.",
                inputSchema={
                    "type": "object",
                    "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                    "required": ["definition", "output_path"],
                },
            ),
            types.Tool(
                name="dsl_compile_mxl",
                description="JSON DSL → MXL Template.xml (печатная форма).",
                inputSchema={
                    "type": "object",
                    "properties": {"definition": {"type": "object"}, "output_path": {"type": "string"}},
                    "required": ["definition", "output_path"],
                },
            ),
            types.Tool(
                name="dsl_compile_role",
                description="JSON DSL → Rights.xml роли 1С.",
                inputSchema={
                    "type": "object",
                    "properties": {"definition": {"type": "object"}, "output_dir": {"type": "string"}},
                    "required": ["definition", "output_dir"],
                },
            ),
            types.Tool(
                name="cfe_borrow",
                description="Заимствовать объект из конфигурации в расширение (CFE).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "extension_path": {"type": "string"},
                        "config_path": {"type": "string"},
                        "object_ref": {"type": "string"},
                    },
                    "required": ["extension_path", "config_path", "object_ref"],
                },
            ),
            types.Tool(
                name="cfe_patch_method",
                description="Сгенерировать BSL перехватчик (&Перед/&После/&ИзменениеИКонтроль).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "extension_path": {"type": "string"},
                        "module_path": {"type": "string"},
                        "method_name": {"type": "string"},
                        "interceptor_type": {"type": "string", "enum": ["Before", "After", "ModificationAndControl"]},
                    },
                    "required": ["extension_path", "module_path", "method_name", "interceptor_type"],
                },
            ),
            types.Tool(
                name="cfe_diff",
                description="Анализ расширения CFE: что заимствовано, перехвачено.",
                inputSchema={
                    "type": "object",
                    "properties": {"extension_path": {"type": "string"}, "config_path": {"type": "string"}},
                    "required": ["extension_path", "config_path"],
                },
            ),
            types.Tool(
                name="skd_trace",
                description="Трассировка поля СКД через всю цепочку: dataset → calculated → resource.",
                inputSchema={
                    "type": "object",
                    "properties": {"template_path": {"type": "string"}, "field_name": {"type": "string"}},
                    "required": ["template_path", "field_name"],
                },
            ),
            types.Tool(
                name="build_dependency_graph",
                description="Построить граф зависимостей метаданных 1С (networkx).",
                inputSchema={
                    "type": "object",
                    "properties": {"config_name": {"type": "string"}},
                    "required": ["config_name"],
                },
            ),
            types.Tool(
                name="dependency_query",
                description="Запрос к графу зависимостей: what_depends_on, dependencies_of, find_cycles, и т.д.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "config_name": {"type": "string"},
                        "query_type": {"type": "string"},
                        "object_ref": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "required": ["config_name", "query_type", "object_ref"],
                },
            ),
            types.Tool(
                name="inspect",
                description="Единый анализ объектов 1С: cf, meta, form, skd, mxl, role, subsystem, depgraph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "path": {"type": "string"},
                        "mode": {"type": "string"},
                        "name": {"type": "string"},
                        "config_name": {"type": "string"},
                    },
                    "required": ["target", "path"],
                },
            ),
            types.Tool(
                name="openspec_proposal",
                description="Создать OpenSpec proposal (Specification-Driven Development).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "change_id": {"type": "string"},
                        "title": {"type": "string"},
                        "context": {"type": "string"},
                        "approach": {"type": "string"},
                        "tasks": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["change_id", "title"],
                },
            ),
            types.Tool(
                name="openspec_list",
                description="Список OpenSpec changes.",
                inputSchema={"type": "object", "properties": {"include_archived": {"type": "boolean"}}},
            ),
            types.Tool(
                name="openspec_update_task",
                description="Обновить задачу в OpenSpec change.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "change_id": {"type": "string"},
                        "task_index": {"type": "integer"},
                        "completed": {"type": "boolean"},
                    },
                    "required": ["change_id", "task_index"],
                },
            ),
            types.Tool(
                name="openspec_archive",
                description="Архивировать завершённый OpenSpec change.",
                inputSchema={
                    "type": "object",
                    "properties": {"change_id": {"type": "string"}},
                    "required": ["change_id"],
                },
            ),
            types.Tool(
                name="epf_factory_create",
                description=(
                    "Создать внешнюю обработку 1С (.epf) из BSL-кода через полный цикл: "
                    "шаблоны v8unpack → подстановка name/synonym/UUID → запись BSL-модуля → "
                    "проверка через BSL LS → сборка .epf → round-trip проверка. "
                    "Не требует установленной 1С. "
                    "Пример: epf_factory_create(name='МояОбработка', synonym='Моя обработка', "
                    "bsl_code='#Область ПрограммныйИнтерфейс\\n#КонецОбласти', "
                    "output_path='/tmp/МояОбработка.epf')"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Имя обработки (латиница/кириллица, без пробелов)"},
                        "synonym": {"type": "string", "description": "Синоним (по умолчанию = name)"},
                        "bsl_code": {"type": "string", "description": "BSL-код модуля формы"},
                        "bsl_path": {"type": "string", "description": "Путь к .bsl файлу (альтернатива bsl_code)"},
                        "output_path": {"type": "string", "description": "Путь к выходному .epf файлу"},
                        "form_name": {"type": "string", "description": "Имя формы (по умолчанию 'Форма')"},
                        "form_spec": {
                            "type": "object",
                            "description": (
                                "DSL-описание формы для генерации Form.elem.json. "
                                "Если не задано — используется пустой шаблон (только реквизит Объект). "
                                'Пример: {"props": [{"name":"ТаблицаСписка",'
                                '"type":"ValueTable","columns":[{"name":"Дата","type":"Date"}]}]}'
                            ),
                        },
                        "form_spec_path": {
                            "type": "string",
                            "description": "Путь к JSON-файлу с DSL-описанием формы (альтернатива form_spec)",
                        },
                        "skip_bsl_validation": {"type": "boolean", "description": "Пропустить проверку BSL LS"},
                        "save_sources": {"type": "boolean", "description": "Сохранить v8unpack-исходники (не удалять)"},
                    },
                    "required": ["name", "output_path"],
                },
            ),
            types.Tool(
                name="epf_factory_templates",
                description=(
                    "Список доступных шаблонов для epf_factory_create. "
                    "Возвращает пути к шаблонам ExternalDataProcessor.json, Form.json, "
                    "Form.id.json, Form.elem.empty.json."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Выполняет tool и возвращает результат."""
        # Структурированный лог каждого вызова — для отладки и аудита
        with contextlib.suppress(Exception):
            log.info(f"mcp_tool_called: {name} args={list(arguments.keys()) if arguments else []}")

        # P2.2: dict-dispatch для handlers группы 1 (config/search/metadata)
        from .mcpserver.handlers import CONFIG_SEARCH_HANDLERS

        handler = CONFIG_SEARCH_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для handlers группы 3a (BSL анализаторы)
        from .mcpserver.handlers import ANALYZER_HANDLERS

        handler = ANALYZER_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для handlers группы 2 (dsl/cfe/skd/depgraph)
        from .mcpserver.handlers import DSL_CFE_HANDLERS

        handler = DSL_CFE_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для handlers группы 4 (openspec)
        from .mcpserver.handlers import MISC_HANDLERS

        handler = MISC_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для handlers группы 5 (inspect/data)
        from .mcpserver.handlers import INSPECT_DATA_HANDLERS

        handler = INSPECT_DATA_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для handlers группы 6 (structure)
        from .mcpserver.handlers import STRUCTURE_HANDLERS

        handler = STRUCTURE_HANDLERS.get(name)
        if handler is not None:
            return await handler(project, arguments)

        # P2.2: dict-dispatch для оставшихся handlers (группы 6-8)
        from .mcpserver.handlers import GENERATE_HANDLERS, QUALITY_HANDLERS, STRUCTURE_HANDLERS

        for handlers_dict in (STRUCTURE_HANDLERS, GENERATE_HANDLERS, QUALITY_HANDLERS):
            handler = handlers_dict.get(name)
            if handler is not None:
                return await handler(project, arguments)

        # Неизвестный tool
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False),
            )
        ]

    return server


async def run_mcp_server() -> None:
    """Точка входа MCP-сервера."""
    server = create_mcp_server()
    init_options = server.create_initialization_options()
    async with stdio_server() as (read, write):
        await server.run(read, write, init_options)


def run_mcp_server_sync() -> None:
    """Синхронная точка входа (для console_scripts в pyproject.toml)."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    run_mcp_server_sync()
