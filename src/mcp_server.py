"""
MCP-сервер для 1C AI Development Environment.

Экспортирует 7 tools для MCP-совместимых клиентов (Cursor, Claude Desktop, VS Code, и т.д.).

Запуск: 1c-ai mcp serve
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from .project import Project


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
            "description": "Сбор контекста для решения задачи 1С. Собирает: TF-IDF/BM25 поиск методов платформы, API-справочник конфигурации, стандарты 1С. Используй ПЕРВЫМ шагом при решении любой задачи.",
            "required_params": ["query"],
            "optional_params": ["config"],
        },
        {
            "name": "solve_check",
            "description": "Полная проверка .bsl кода: BSL LS (187) + 56 правил стандартов. Возвращает: total_errors, total_warnings, violations, verdict. verdict: 'ready' / 'warnings' / 'errors'.",
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
                    "Собирает: TF-IDF поиск методов платформы, API-справочник конфигурации, "
                    "стандарты 1С (ключевые правила), антипаттерны (CRITICAL). "
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
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="solve_check",
                description=(
                    "Полная проверка .bsl кода: BSL LS (187) + 56 правил стандартов. "
                    "Возвращает: total_errors, total_warnings, violations, verdict. "
                    "verdict: 'ready' (0 errors), 'warnings' (0 errors, есть warnings), "
                    "'errors' (есть errors). "
                    "Пример: solve_check(file_path='/tmp/module.bsl')"
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
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Выполняет tool и возвращает результат."""

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
                    with open(api_json, 'r', encoding='utf-8') as f:
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
            with open(api_json, 'r', encoding='utf-8') as f:
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

            # Собираем контекст
            context = {
                "query": query,
                "platform_methods": [],
                "config_info": None,
                "standards_summary": {},
            }

            # 1. Поиск методов платформы
            results = project.search_methods(query, limit=5)
            context["platform_methods"] = results

            # 2. API конфигурации
            if config:
                info = project.get_config_info(config)
                if info:
                    context["config_info"] = {
                        "name": info["name"],
                        "version": info["version"],
                        "objects_count": info["objects_count"],
                        "modules_count": len(info["modules"]),
                    }

            # 3. Стандарты
            context["standards_summary"] = {
                "bsl_ls_diagnostics": 187,
                "check_1c_standards_rules": 56,
                "check_metadata_rules": 18,
                "total_checks": 261,
            }

            return [types.TextContent(
                type="text",
                text=json.dumps(context, ensure_ascii=False, indent=2),
            )]

        elif name == "solve_check":
            file_path = arguments.get("file_path", "")
            total_errors = 0
            total_warnings = 0
            violations_list = []

            # 1. BSL LS
            if project.paths.bsl_ls_binary.exists():
                try:
                    result = project.bsl_analyzer.analyze(Path(file_path))
                    bsl_errors = sum(1 for d in result.diagnostics
                                     if d.get("severity", "").lower() == "error")
                    bsl_warnings = sum(1 for d in result.diagnostics
                                       if d.get("severity", "").lower() in ("warning", "information", "hint"))
                    total_errors += bsl_errors
                    total_warnings += bsl_warnings
                    violations_list.append({
                        "source": "bsl_ls",
                        "total": result.total,
                        "errors": bsl_errors,
                        "warnings": bsl_warnings,
                    })
                except Exception as e:
                    violations_list.append({"source": "bsl_ls", "error": str(e)})
            else:
                violations_list.append({"source": "bsl_ls", "error": "BSL LS не установлен"})

            # 2. check_1c_standards
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
                std_errors = sum(1 for v in violations if v.severity == "error")
                std_warnings = sum(1 for v in violations if v.severity == "warning")
                total_errors += std_errors
                total_warnings += std_warnings
                violations_list.append({
                    "source": "check_1c_standards",
                    "errors": std_errors,
                    "warnings": std_warnings,
                    "violations": [
                        {"rule_id": v.rule_id, "severity": v.severity,
                         "line": v.line, "message": v.message}
                        for v in violations[:20]
                    ],
                })
            except Exception as e:
                violations_list.append({"source": "check_1c_standards", "error": str(e)})

            # Вердикт
            if total_errors == 0 and total_warnings == 0:
                verdict = "ready"
            elif total_errors == 0:
                verdict = "warnings"
            else:
                verdict = "errors"

            response = {
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "verdict": verdict,
                "details": violations_list,
            }
            return [types.TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, indent=2),
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

            # Ищем metadata-index.json для конфигурации
            metadata_index_path = project.paths.root / "derived" / "configs" / config_name / "metadata-index.json"
            if not metadata_index_path.exists():
                return [types.TextContent(type="text",
                    text=json.dumps({
                        "error": f"metadata-index.json not found for config '{config_name}'",
                        "hint": "Run: python3 scripts/metadata_parser.py data/configs/" + config_name + " derived/configs/" + config_name + "/metadata-index.json",
                    }, ensure_ascii=False))]

            with open(metadata_index_path, encoding='utf-8') as f:
                metadata = json.load(f)

            objects = metadata.get('objects', [])

            # Если object_name не указан — возвращаем список всех
            if not object_name:
                # Фильтр по типу если указан
                if object_type:
                    objects = [o for o in objects if o.get('type') == object_type]

                # Краткая информация
                summary = []
                for obj in objects:
                    summary.append({
                        'name': obj.get('name', ''),
                        'type': obj.get('type', ''),
                        'synonym': obj.get('synonym', ''),
                        'attributes_count': len(obj.get('attributes', [])),
                        'tabular_sections_count': len(obj.get('tabular_sections', [])),
                        'forms_count': len(obj.get('forms', [])),
                    })

                response = {
                    'config': config_name,
                    'total_objects': len(summary),
                    'stats': metadata.get('stats', {}),
                    'objects': summary,
                }
                return [types.TextContent(type="text",
                    text=json.dumps(response, ensure_ascii=False, indent=2))]

            # Ищем конкретный объект по имени
            found = None
            for obj in objects:
                if obj.get('name', '').lower() == object_name.lower():
                    if object_type and obj.get('type') != object_type:
                        continue
                    found = obj
                    break

            if not found:
                # Fuzzy search
                suggestions = [o['name'] for o in objects
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
