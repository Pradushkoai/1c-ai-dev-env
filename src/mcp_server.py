"""
MCP-сервер для 1C AI Development Environment.

Экспортирует 7 tools для MCP-совместимых клиентов (Cursor, Claude Desktop, VS Code, и т.д.).

Запуск: 1c-ai mcp serve
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .project import Project
from .services.logger import get_logger, configure_logging

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
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Выполняет tool и возвращает результат."""
        # Структурированный лог каждого вызова — для отладки и аудита
        log.info(
            "mcp_tool_called",
            tool=name,
            args_keys=list(arguments.keys()) if arguments else [],
        )

        if name == "list_configs":
            configs = project.list_configs_info()
            return [types.TextContent(
                type="text",
                text=json.dumps(configs, ensure_ascii=False, indent=2),
            )]

        elif name == "search_1c_methods":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            results = project.search_methods(query, limit)
            return [types.TextContent(
                type="text",
                text=json.dumps(results, ensure_ascii=False, indent=2),
            )]

        elif name == "search_code":
            query = arguments.get("query", "")
            config_name = arguments.get("config_name", "")
            limit = arguments.get("limit", 10)
            from .services.search_code import search_code
            results = search_code(config_name, query, limit, project.paths)
            return [types.TextContent(
                type="text",
                text=json.dumps(results, ensure_ascii=False, indent=2),
            )]

        elif name == "call_graph":
            config_name = arguments.get("config_name", "")
            action = arguments.get("action", "stats")
            module = arguments.get("module", "")
            method = arguments.get("method", "")
            from .services.call_graph import build_call_graph
            graph = build_call_graph(config_name, project.paths)
            if action == "stats":
                result = graph.get_stats()
            elif action == "callers":
                result = graph.get_callers(module, method)
            elif action == "callees":
                result = graph.get_callees(module, method)
            elif action == "dead-code":
                import json as _json
                api_json = project.paths.config_api_reference_json(config_name)
                export_methods = []
                if api_json.exists():
                    with open(api_json, encoding='utf-8') as f:
                        modules = _json.load(f)
                    for m in modules:
                        for meth in m.get('methods', []):
                            export_methods.append((m['name'], meth['name']))
                result = [{"module": mod, "method": meth} for mod, meth in graph.find_dead_code(export_methods)]
            elif action == "cycles":
                result = graph.find_cycles()
            else:
                result = graph.to_dict()
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]

        elif name == "get_form_elements":
            config_name = arguments.get("config_name", "")
            form_name = arguments.get("form_name", "")
            api_json = project.paths.config_api_reference_json(config_name)
            if not api_json.exists():
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"API reference not found for '{config_name}'"}, ensure_ascii=False),
                )]
            with open(api_json, encoding='utf-8') as f:
                modules = json.load(f)
            forms = [m for m in modules if m.get('type') == 'Форма']
            if not form_name:
                # Возвращаем список всех форм
                result = [{
                    "name": f['name'],
                    "methods_count": f.get('methods_count', 0),
                    "form_elements_count": f.get('form_elements_count', 0),
                    "parent_type": f.get('parent_type', ''),
                    "parent_name": f.get('parent_name', ''),
                } for f in forms]
            else:
                # Возвращаем элементы конкретной формы
                result = []
                for f in forms:
                    if f['name'] == form_name:
                        result = f.get('form_elements', [])
                        break
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]

        elif name == "get_api_reference":
            config_name = arguments.get("config_name", "")
            module = arguments.get("module", "")

            if not module:
                # Возвращаем список модулей
                info = project.get_config_info(config_name)
                if info is None:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"Конфигурация '{config_name}' не найдена"}, ensure_ascii=False),
                    )]
                return [types.TextContent(
                    type="text",
                    text=json.dumps(info, ensure_ascii=False, indent=2),
                )]
            else:
                # Возвращаем методы конкретного модуля
                methods = project.get_api_methods(config_name, module)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(methods, ensure_ascii=False, indent=2),
                )]

        elif name == "analyze_bsl":
            file_path = arguments.get("file_path", "")
            try:
                result = project.bsl_analyzer.analyze(Path(file_path))
                response = {
                    "total": result.total,
                    "by_code": result.by_code,
                    "diagnostics": result.diagnostics[:50],  # ограничиваем
                }
                return [types.TextContent(
                    type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2),
                )]
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False),
                )]

        elif name == "check_standards":
            file_path = arguments.get("file_path", "")
            try:
                import importlib.util
                scripts_dir = project.paths.scripts_dir
                if not (scripts_dir / "check_1c_standards.py").exists():
                    scripts_dir = project.paths.root / "setup" / "scripts"
                spec = importlib.util.spec_from_file_location(
                    "check_1c_standards", scripts_dir / "check_1c_standards.py"
                )
                mod = importlib.util.module_from_spec(spec)
                sys.modules["check_1c_standards"] = mod
                spec.loader.exec_module(mod)

                checker = mod.StandardsChecker()
                violations = checker.check_file(Path(file_path))
                response = [
                    {
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "line": v.line,
                        "message": v.message,
                    }
                    for v in violations
                ]
                return [types.TextContent(
                    type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2),
                )]
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False),
                )]

        elif name == "solve_context":
            query = arguments.get("query", "")
            config = arguments.get("config", "")
            limit = arguments.get("limit", 5)

            # Используем TaskProcessor — единая логика с CLI
            from .services.task_processor import TaskProcessor
            processor = TaskProcessor(project.paths)
            ctx = processor.solve(query, config_name=config, limit=limit)

            return [types.TextContent(
                type="text",
                text=json.dumps(ctx.to_dict(), ensure_ascii=False, indent=2),
            )]

        elif name == "solve_check":
            file_path = arguments.get("file_path", "")
            level = arguments.get("level", "standard")

            # Используем TaskProcessor — единая логика с CLI
            from pathlib import Path as _Path

            from .services.task_processor import TaskProcessor

            processor = TaskProcessor(project.paths)
            try:
                result = processor.check(_Path(file_path), level=level)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                )]
            except FileNotFoundError as e:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False),
                )]

        elif name == "data_status":
            # Статус данных проекта
            from .services.data_package import DataPackage
            dp = DataPackage(project.paths)
            status = dp.status()
            # Преобразуем Path и другие объекты в сериализуемый формат
            response = {
                "has_platform_index": status["has_platform_index"],
                "has_platform_methods": status["has_platform_methods"],
                "configs": status["configs"],
                "autosave_available": status["autosave_available"],
            }
            if status.get("autosave_info"):
                ai = status["autosave_info"]
                response["autosave_info"] = {
                    "size_mb": ai.get("size_mb", 0),
                    "total_files": ai.get("total_files", 0),
                    "created_at": ai.get("manifest", {}).get("created_at", "")[:19] if ai.get("manifest") else "",
                }
                response["autoload_command"] = "1c-ai data autoload"
            return [types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
            )]

        elif name == "get_object_structure":
            config_name = arguments.get("config_name", "")
            object_name = arguments.get("object_name", "")
            object_type = arguments.get("object_type", "")

            if not config_name:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

            # Ищем unified-metadata-index.json (v4.1+) или metadata-index.json (fallback)
            unified_path = project.paths.root / "derived" / "configs" / config_name / "unified-metadata-index.json"
            old_path = project.paths.root / "derived" / "configs" / config_name / "metadata-index.json"

            if unified_path.exists():
                with open(unified_path, encoding='utf-8') as f:
                    metadata = json.load(f)
                # unified format: objects is dict by type, each value is list
                all_objects = []
                for type_name, objs in metadata.get('objects', {}).items():
                    all_objects.extend(objs)

                # Также добавляем roles, subsystems, event_subscriptions, scheduled_jobs
                for section in ('roles', 'subsystems', 'event_subscriptions', 'scheduled_jobs'):
                    for obj in metadata.get(section, []):
                        all_objects.append(obj)

                stats = metadata.get('stats', {})
                config_info = metadata.get('configuration', {})
            elif old_path.exists():
                with open(old_path, encoding='utf-8') as f:
                    metadata = json.load(f)
                all_objects = metadata.get('objects', [])
                stats = metadata.get('stats', {})
                config_info = {}
            else:
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"unified-metadata-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/metadata_extractor.py data/configs/" + config_name + " derived/configs/" + config_name + "/unified-metadata-index.json",
                    }, ensure_ascii=False))]

            # Если object_name не указан — возвращаем список всех
            if not object_name:
                # Фильтр по типу если указан
                if object_type:
                    all_objects = [o for o in all_objects if o.get('type') == object_type]

                # Краткая информация
                summary = []
                for obj in all_objects:
                    children = obj.get('child_objects', {})
                    summary.append({
                        'name': obj.get('name', ''),
                        'type': obj.get('type', ''),
                        'synonym': obj.get('synonym', ''),
                        'attributes_count': len(children.get('attributes', [])),
                        'tabular_sections_count': len(children.get('tabular_sections', [])),
                        'forms_count': len(children.get('forms', [])),
                    })

                response = {
                    'config': config_name,
                    'total_objects': len(summary),
                    'stats': stats,
                    'configuration': config_info.get('properties', {}) if config_info else {},
                    'objects': summary,
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]

            # Ищем конкретный объект по имени
            found = None
            for obj in all_objects:
                if obj.get('name', '').lower() == object_name.lower():
                    if object_type and obj.get('type') != object_type:
                        continue
                    found = obj
                    break

            if not found:
                # Fuzzy search
                suggestions = [o['name'] for o in all_objects
                               if object_name.lower() in o.get('name', '').lower()][:10]
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"Object '{object_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    }, ensure_ascii=False))]

            return [types.TextContent(type="text",
                text=json.dumps(found, ensure_ascii=False, indent=2))]

        elif name == "get_skd_schema":
            config_name = arguments.get("config_name", "")
            report_name = arguments.get("report_name", "")

            if not config_name:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

            # Ищем skd-index.json для конфигурации
            skd_index_path = project.paths.root / "derived" / "configs" / config_name / "skd-index.json"
            if not skd_index_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"skd-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/skd_parser.py data/configs/" + config_name + " derived/configs/" + config_name + "/skd-index.json",
                    }, ensure_ascii=False))]

            with open(skd_index_path, encoding='utf-8') as f:
                skd_data = json.load(f)

            schemas = skd_data.get('schemas', [])

            # Если report_name не указан — возвращаем список всех СКД-схем
            if not report_name:
                summary = []
                for s in schemas:
                    summary.append({
                        'name': s.get('name', ''),
                        'parent_type': s.get('parent_type', ''),
                        'parent_name': s.get('parent_name', ''),
                        'data_sets_count': len(s.get('schema', {}).get('data_sets', [])),
                        'parameters_count': len(s.get('schema', {}).get('parameters', [])),
                        'fields_count': sum(len(ds.get('fields', [])) for ds in s.get('schema', {}).get('data_sets', [])),
                    })

                response = {
                    'config': config_name,
                    'stats': skd_data.get('stats', {}),
                    'schemas': summary,
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]

            # Ищем СКД-схему по имени отчёта
            found = None
            for s in schemas:
                if s.get('parent_name', '').lower() == report_name.lower():
                    found = s
                    break
                if s.get('name', '').lower() == report_name.lower():
                    found = s
                    break

            if not found:
                # Fuzzy search
                suggestions = list(set(
                    s.get('parent_name', '') for s in schemas
                    if report_name.lower() in s.get('parent_name', '').lower()
                ))[:10]
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"SKD schema for '{report_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    }, ensure_ascii=False))]

            return [types.TextContent(type="text",
                text=json.dumps(found, ensure_ascii=False, indent=2))]

        elif name == "get_form_structure":
            config_name = arguments.get("config_name", "")
            form_name = arguments.get("form_name", "")
            parent_name = arguments.get("parent_name", "")

            if not config_name:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

            # Ищем form-index.json для конфигурации
            form_index_path = project.paths.root / "derived" / "configs" / config_name / "form-index.json"
            if not form_index_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"form-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/form_analyzer.py data/configs/" + config_name + " derived/configs/" + config_name + "/form-index.json",
                    }, ensure_ascii=False))]

            with open(form_index_path, encoding='utf-8') as f:
                form_data = json.load(f)

            forms = form_data.get('forms', [])

            # Если form_name не указан — список всех форм
            if not form_name:
                summary = []
                for fr in forms:
                    # Фильтр по parent_name если указан
                    if parent_name and fr.get('parent_name', '').lower() != parent_name.lower():
                        continue
                    summary.append({
                        'name': fr.get('name', ''),
                        'parent_type': fr.get('parent_type', ''),
                        'parent_name': fr.get('parent_name', ''),
                        'element_count': fr.get('form', {}).get('element_count', 0),
                        'events_count': len(fr.get('form', {}).get('events', [])),
                    })

                response = {
                    'config': config_name,
                    'stats': form_data.get('stats', {}),
                    'forms': summary,
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]

            # Ищем форму по имени
            found = None
            for fr in forms:
                if fr.get('name', '').lower() == form_name.lower():
                    # Если parent_name указан — уточняем
                    if parent_name and fr.get('parent_name', '').lower() != parent_name.lower():
                        continue
                    found = fr
                    break

            if not found:
                # Fuzzy search
                suggestions = list(set(
                    f"{fr.get('parent_name', '')}.{fr.get('name', '')}"
                    for fr in forms
                    if form_name.lower() in fr.get('name', '').lower()
                ))[:10]
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"Form '{form_name}' not found in config '{config_name}'",
                        "suggestions": suggestions,
                    }, ensure_ascii=False))]

            return [types.TextContent(type="text",
                text=json.dumps(found, ensure_ascii=False, indent=2))]

        elif name in ("generate_processing", "generate_report"):
            obj_name = arguments.get("name", "")
            synonym = arguments.get("synonym", "")
            description = arguments.get("description", "")
            author = arguments.get("author", "")
            output_dir = arguments.get("output_dir", "")

            if not obj_name or not synonym:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "name and synonym are required"}, ensure_ascii=False))]

            # По умолчанию — generated/<name>
            if not output_dir:
                output_dir = str(project.paths.root / "generated" / obj_name)

            # Загружаем code_generator
            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            cg_path = scripts_dir / "code_generator.py"
            if not cg_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "code_generator.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("code_generator", cg_path)
            cg_mod = importlib.util.module_from_spec(spec)
            sys.modules["code_generator"] = cg_mod
            spec.loader.exec_module(cg_mod)

            if name == "generate_processing":
                result = cg_mod.generate_processing(obj_name, synonym, output_dir, description, author)
            else:  # generate_report
                data_source = arguments.get("data_source", "")
                main_query = arguments.get("main_query", "")
                result = cg_mod.generate_report(obj_name, synonym, output_dir, description, author, data_source, main_query)

            response = {
                "status": "success",
                "object_type": result["stats"]["object_type"],
                "name": obj_name,
                "synonym": synonym,
                "uuid": result["stats"].get("uuid", ""),
                "output_dir": output_dir,
                "total_files": result["stats"]["total_files"],
                "bsl_files": result["stats"]["bsl_files"],
                "xml_files": result["stats"]["xml_files"],
                "files": [{"path": f["path"].replace(str(project.paths.root) + "/", ""),
                            "type": f["type"], "size": f["size"]} for f in result["files"]],
            }
            return [types.TextContent(type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2))]

        elif name == "build_epf":
            source_dir = arguments.get("source_dir", "")
            output_path = arguments.get("output_path", "")
            object_name = arguments.get("object_name")
            object_type = arguments.get("object_type", "DataProcessor")

            if not source_dir or not output_path:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "source_dir and output_path are required"}, ensure_ascii=False))]

            # Преобразуем относительные пути
            if not os.path.isabs(source_dir):
                source_dir = str(project.paths.root / source_dir)
            if not os.path.isabs(output_path):
                output_path = str(project.paths.root / output_path)

            if not os.path.exists(source_dir):
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"source_dir not found: {source_dir}"}, ensure_ascii=False))]

            # Загружаем epf_builder
            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            eb_path = scripts_dir / "epf_builder.py"
            if not eb_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "epf_builder.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("epf_builder", eb_path)
            eb_mod = importlib.util.module_from_spec(spec)
            sys.modules["epf_builder"] = eb_mod
            spec.loader.exec_module(eb_mod)

            try:
                result = eb_mod.build_epf(source_dir, output_path, object_name, object_type)
                response = {
                    "status": "success",
                    "file_path": result["file_path"],
                    "size": result["size"],
                    "object_name": result["object_name"],
                    "object_type": result["object_type"],
                    "uuid": result["uuid"],
                    "files_included": result["files_included"],
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"Build failed: {str(e)}"}, ensure_ascii=False))]

        elif name == "validate_generated":
            source_dir = arguments.get("source_dir", "")

            if not source_dir:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "source_dir is required"}, ensure_ascii=False))]

            # Преобразуем относительный путь
            if not os.path.isabs(source_dir):
                source_dir = str(project.paths.root / source_dir)

            if not os.path.exists(source_dir):
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"source_dir not found: {source_dir}"}, ensure_ascii=False))]

            # Загружаем code_validator
            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            cv_path = scripts_dir / "code_validator.py"
            if not cv_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "code_validator.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("code_validator", cv_path)
            cv_mod = importlib.util.module_from_spec(spec)
            sys.modules["code_validator"] = cv_mod
            spec.loader.exec_module(cv_mod)

            try:
                result = cv_mod.validate_generated(source_dir)
                response = {
                    "source_dir": result["source_dir"],
                    "verdict": result["verdict"],
                    "total_errors": result["total_errors"],
                    "total_warnings": result["total_warnings"],
                    "structure": result["structure"],
                    "bsl_validation": result.get("bsl_validation", []),
                    "xml_validation": result.get("xml_validation", []),
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"Validation failed: {str(e)}"}, ensure_ascii=False))]

        elif name == "get_knowledge":
            query = arguments.get("query", "")
            item_id = arguments.get("item_id", "")
            category = arguments.get("category", "")

            try:
                from .services.knowledge_base import KnowledgeBase
                kb = KnowledgeBase()

                # Если item_id указан — возвращаем полный текст
                if item_id:
                    item = kb.get_item(item_id)
                    if item:
                        return [types.TextContent(type="text",
                            text=json.dumps(item, ensure_ascii=False, indent=2))]
                    else:
                        return [types.TextContent(type="text",
                            text=json.dumps({"error": f"Item not found: {item_id}"}, ensure_ascii=False))]

                # Если query указан — поиск
                if query:
                    results = kb.search(query, category=category if category else None, limit=20)
                    response = {
                        "query": query,
                        "category": category or "all",
                        "total_results": len(results),
                        "results": results,
                    }
                    return [types.TextContent(type="text",
                        text=json.dumps(response, ensure_ascii=False, indent=2))]

                # Если ничего не указано — список всех
                items = kb.list_all()
                response = {
                    "stats": kb.get_stats(),
                    "items": items,
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]

            except Exception as e:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"Knowledge base error: {str(e)}"}, ensure_ascii=False))]

        elif name == "audit_security":
            file_path = arguments.get("file_path", "")

            if not file_path:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "file_path is required"}, ensure_ascii=False))]

            if not os.path.isabs(file_path):
                file_path = str(project.paths.root / file_path)

            if not os.path.exists(file_path):
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False))]

            # Загружаем security_auditor
            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            sa_path = scripts_dir / "security_auditor.py"
            if not sa_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "security_auditor.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("security_auditor", sa_path)
            sa_mod = importlib.util.module_from_spec(spec)
            sys.modules["security_auditor"] = sa_mod
            spec.loader.exec_module(sa_mod)

            try:
                auditor = sa_mod.SecurityAuditor()
                violations = auditor.audit_file(Path(file_path))
                stats = auditor.get_stats(violations)

                response = {
                    "file_path": file_path,
                    "total_violations": stats["total_violations"],
                    "by_severity": stats["by_severity"],
                    "critical_count": stats["critical_count"],
                    "high_count": stats["high_count"],
                    "medium_count": stats["medium_count"],
                    "low_count": stats["low_count"],
                    "violations": [
                        {
                            "rule_id": v.rule_id,
                            "severity": v.severity,
                            "line": v.line,
                            "message": v.message,
                            "recommendation": v.recommendation,
                        }
                        for v in violations
                    ],
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"Audit failed: {str(e)}"}, ensure_ascii=False))]

        elif name == "get_code_metrics":
            file_path = arguments.get("file_path", "")

            if not file_path:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "file_path is required"}, ensure_ascii=False))]

            if not os.path.isabs(file_path):
                file_path = str(project.paths.root / file_path)

            if not os.path.exists(file_path):
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False))]

            # Загружаем code_metrics
            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            cm_path = scripts_dir / "code_metrics.py"
            if not cm_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({"error": "code_metrics.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("code_metrics", cm_path)
            cm_mod = importlib.util.module_from_spec(spec)
            sys.modules["code_metrics"] = cm_mod
            spec.loader.exec_module(cm_mod)

            try:
                analyzer = cm_mod.CodeMetricsAnalyzer()
                metrics = analyzer.analyze_file(Path(file_path))

                response = {
                    "file_path": file_path,
                    "total_lines": metrics.total_lines,
                    "code_lines": metrics.code_lines,
                    "comment_lines": metrics.comment_lines,
                    "blank_lines": metrics.blank_lines,
                    "procedures_count": metrics.procedures_count,
                    "functions_count": metrics.functions_count,
                    "export_count": metrics.export_count,
                    "total_cyclomatic": metrics.total_cyclomatic,
                    "avg_cyclomatic": round(metrics.avg_cyclomatic, 2),
                    "max_cyclomatic": metrics.max_cyclomatic,
                    "total_cognitive": metrics.total_cognitive,
                    "max_cognitive": metrics.max_cognitive,
                    "max_nesting": metrics.max_nesting,
                    "duplicate_blocks": metrics.duplicate_blocks,
                    "duplicate_lines": metrics.duplicate_lines,
                    "is_god_object": metrics.is_god_object,
                    "long_methods_count": len(metrics.long_methods),
                    "too_many_params_count": len(metrics.too_many_params),
                    "technical_debt_minutes": metrics.technical_debt_minutes,
                    "health_score": round(metrics.health_score, 1),
                    "issues": metrics.issues,
                    "methods": [
                        {
                            "name": m.name,
                            "type": m.method_type,
                            "loc": m.loc,
                            "lloc": m.lloc,
                            "cyclomatic": m.cyclomatic_complexity,
                            "cognitive": m.cognitive_complexity,
                            "nesting": m.max_nesting_depth,
                            "params": m.param_count,
                            "export": m.is_export,
                        }
                        for m in metrics.methods[:20]  # первые 20 методов
                    ],
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text",
                    text=json.dumps({"error": f"Metrics failed: {str(e)}"}, ensure_ascii=False))]

        elif name in ("check_transactions", "analyze_queries"):
            file_path = arguments.get("file_path", "")
            if not file_path:
                return [types.TextContent(type="text", text=json.dumps({"error": "file_path required"}, ensure_ascii=False))]
            if not os.path.isabs(file_path):
                file_path = str(project.paths.root / file_path)
            if not os.path.exists(file_path):
                return [types.TextContent(type="text", text=json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False))]

            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            script_name = "transaction_checker" if name == "check_transactions" else "query_analyzer"
            script_path = scripts_dir / f"{script_name}.py"
            if not script_path.exists():
                return [types.TextContent(type="text", text=json.dumps({"error": f"{script_name}.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location(script_name, script_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[script_name] = mod
            spec.loader.exec_module(mod)

            try:
                if name == "check_transactions":
                    checker = mod.TransactionChecker()
                    violations = checker.check_file(Path(file_path))
                    stats = checker.get_stats(violations)
                    response = {
                        "file_path": file_path,
                        "total_violations": stats["total"],
                        "by_severity": stats["by_severity"],
                        "violations": [{"rule_id": v.rule_id, "severity": v.severity, "line": v.line, "message": v.message, "recommendation": v.recommendation} for v in violations],
                    }
                else:  # analyze_queries
                    analyzer = mod.QueryAnalyzer()
                    issues = analyzer.analyze_file(Path(file_path))
                    stats = analyzer.get_stats(issues)
                    response = {
                        "file_path": file_path,
                        "total_issues": stats["total"],
                        "by_severity": stats["by_severity"],
                        "issues": [{"rule_id": i.rule_id, "severity": i.severity, "line": i.line, "message": i.message, "recommendation": i.recommendation} for i in issues],
                    }
                return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Analysis failed: {str(e)}"}, ensure_ascii=False))]

        elif name == "analyze_architecture":
            config_dir = arguments.get("config_dir", "")
            if not config_dir:
                return [types.TextContent(type="text", text=json.dumps({"error": "config_dir required"}, ensure_ascii=False))]
            if not os.path.isabs(config_dir):
                config_dir = str(project.paths.root / config_dir)
            if not os.path.exists(config_dir):
                return [types.TextContent(type="text", text=json.dumps({"error": f"Directory not found: {config_dir}"}, ensure_ascii=False))]

            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            script_path = scripts_dir / "architecture_analyzer.py"
            if not script_path.exists():
                return [types.TextContent(type="text", text=json.dumps({"error": "architecture_analyzer.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("architecture_analyzer", script_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["architecture_analyzer"] = mod
            spec.loader.exec_module(mod)

            try:
                analyzer = mod.ArchitectureAnalyzer()
                issues, modules = analyzer.analyze_config(Path(config_dir))
                stats = analyzer.get_stats(issues)
                response = {
                    "config_dir": config_dir,
                    "total_modules": len(modules),
                    "total_issues": stats["total_issues"],
                    "by_severity": stats["by_severity"],
                    "by_rule": stats["by_rule"],
                    "issues": [{"rule_id": i.rule_id, "severity": i.severity, "module": i.module, "line": i.line, "message": i.message} for i in issues[:50]],
                }
                return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Analysis failed: {str(e)}"}, ensure_ascii=False))]

        elif name in ("check_form_quality", "check_skd_quality"):
            config_name = arguments.get("config_name", "")
            if not config_name:
                return [types.TextContent(type="text", text=json.dumps({"error": "config_name required"}, ensure_ascii=False))]

            import importlib.util
            scripts_dir = project.paths.root / "scripts"

            if name == "check_form_quality":
                index_path = project.paths.root / "derived" / "configs" / config_name / "form-index.json"
                script_name = "form_quality_checker"
                checker_class = "FormQualityChecker"
            else:  # check_skd_quality
                index_path = project.paths.root / "derived" / "configs" / config_name / "skd-index.json"
                script_name = "skd_quality_checker"
                checker_class = "SKDQualityChecker"

            if not index_path.exists():
                return [types.TextContent(type="text", text=json.dumps({"error": f"Index not found: {index_path}"}, ensure_ascii=False))]

            script_path = scripts_dir / f"{script_name}.py"
            if not script_path.exists():
                return [types.TextContent(type="text", text=json.dumps({"error": f"{script_name}.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location(script_name, script_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[script_name] = mod
            spec.loader.exec_module(mod)

            try:
                checker = getattr(mod, checker_class)()
                issues = checker.check_form_index(index_path) if name == "check_form_quality" else checker.check_skd_index(index_path)
                stats = checker.get_stats(issues)
                response = {
                    "config_name": config_name,
                    "total_issues": stats["total"],
                    "by_severity": stats["by_severity"],
                    "by_rule": stats["by_rule"],
                    "issues": [{"rule_id": i.rule_id, "severity": i.severity, "form_name": getattr(i, 'form_name', getattr(i, 'schema_name', '')), "message": i.message} for i in issues[:50]],
                }
                return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Check failed: {str(e)}"}, ensure_ascii=False))]

        elif name == "diff_configs":
            old_path = arguments.get("old_path", "")
            new_path = arguments.get("new_path", "")
            if not old_path or not new_path:
                return [types.TextContent(type="text", text=json.dumps({"error": "old_path and new_path required"}, ensure_ascii=False))]
            if not os.path.isabs(old_path):
                old_path = str(project.paths.root / old_path)
            if not os.path.isabs(new_path):
                new_path = str(project.paths.root / new_path)
            if not os.path.exists(old_path):
                return [types.TextContent(type="text", text=json.dumps({"error": f"Old index not found: {old_path}"}, ensure_ascii=False))]
            if not os.path.exists(new_path):
                return [types.TextContent(type="text", text=json.dumps({"error": f"New index not found: {new_path}"}, ensure_ascii=False))]

            import importlib.util
            scripts_dir = project.paths.root / "scripts"
            script_path = scripts_dir / "diff_analyzer.py"
            if not script_path.exists():
                return [types.TextContent(type="text", text=json.dumps({"error": "diff_analyzer.py not found"}, ensure_ascii=False))]

            spec = importlib.util.spec_from_file_location("diff_analyzer", script_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["diff_analyzer"] = mod
            spec.loader.exec_module(mod)

            try:
                analyzer = mod.DiffAnalyzer()
                diff = analyzer.compare(Path(old_path), Path(new_path))
                response = {
                    "summary": diff.summary,
                    "added_objects": [{"type": c.object_type, "name": c.object_name} for c in diff.added_objects[:50]],
                    "removed_objects": [{"type": c.object_type, "name": c.object_name} for c in diff.removed_objects[:50]],
                    "modified_objects": [{"type": c.object_type, "name": c.object_name, "details": c.details} for c in diff.modified_objects[:50]],
                    "added_roles": diff.added_roles,
                    "removed_roles": diff.removed_roles,
                    "added_subsystems": diff.added_subsystems,
                    "removed_subsystems": diff.removed_subsystems,
                    "added_event_subscriptions": diff.added_event_subscriptions,
                    "removed_event_subscriptions": diff.removed_event_subscriptions,
                    "added_scheduled_jobs": diff.added_scheduled_jobs,
                    "removed_scheduled_jobs": diff.removed_scheduled_jobs,
                }
                return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Diff failed: {str(e)}"}, ensure_ascii=False))]

        # Неизвестный tool
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False),
        )]

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
