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
            "description": "TF-IDF семантический поиск по 8141 методам платформы 1С. Возвращает: name_ru, name_en, syntax, description, context. Пример: search_1c_methods(query='найти элемент по коду', limit=5)",
            "required_params": ["query"],
            "optional_params": ["limit"],
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
            "description": "Сбор контекста для решения задачи 1С. Собирает: TF-IDF поиск методов платформы, API-справочник конфигурации, стандарты 1С. Используй ПЕРВЫМ шагом при решении любой задачи.",
            "required_params": ["query"],
            "optional_params": ["config"],
        },
        {
            "name": "solve_check",
            "description": "Полная проверка .bsl кода: BSL LS (187) + 56 правил стандартов. Возвращает: total_errors, total_warnings, violations, verdict. verdict: 'ready' / 'warnings' / 'errors'.",
            "required_params": ["file_path"],
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
                    "TF-IDF семантический поиск по 8141 методам платформы 1С. "
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
