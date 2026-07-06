"""
M7 (2026-07-06): CLI improvements — D-1, D-3, D-4.

D-1: Унификация help — единый формат help для всех команд
D-3: Consistent JSON output — стандартизированный JSON output
D-4: CLI exit codes — стандартизированные exit codes

Использование:
    from src.cli.unified import format_json_output, get_exit_code, print_help

    # D-3: JSON output
    print(format_json_output(success=True, data={"key": "value"}))

    # D-4: Exit codes
    sys.exit(get_exit_code(success=True))

    # D-1: Help
    print_help(command_name="config")
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


# ============================================================================
# D-4: Standard exit codes
# ============================================================================


class ExitCode:
    """Стандартные exit codes для CLI.

    Based on sysexits.h:
    - 0: SUCCESS
    - 1: GENERAL_ERROR
    - 2: USAGE_ERROR (argparse default)
    - 64-78: sysexits.h codes
    """

    SUCCESS = 0
    GENERAL_ERROR = 1
    USAGE_ERROR = 2  # argparse default for invalid args

    # sysexits.h
    DATA_ERROR = 65
    NO_INPUT = 66
    NO_USER = 67
    NO_HOST = 68
    SERVICE_UNAVAILABLE = 69
    SOFTWARE_ERROR = 70
    OS_ERROR = 71
    OS_FILE_ERROR = 72
    CANT_CREATE = 73
    IO_ERROR = 74
    TEMP_FAIL = 75
    PROTOCOL = 76
    NO_PERMISSION = 77
    CONFIG_ERROR = 78

    # Custom codes (128+ to avoid sysexits.h)
    NOT_FOUND = 127
    TIMEOUT = 124
    VALIDATION_ERROR = 128
    DEPENDENCY_MISSING = 129


def get_exit_code(success: bool, error_type: str = "") -> int:
    """Получить exit code по результату операции.

    Args:
        success: True если операция успешна.
        error_type: Тип ошибки (для не-success case).

    Returns:
        Exit code integer.
    """
    if success:
        return ExitCode.SUCCESS

    error_map = {
        "general": ExitCode.GENERAL_ERROR,
        "usage": ExitCode.USAGE_ERROR,
        "data": ExitCode.DATA_ERROR,
        "not_found": ExitCode.NOT_FOUND,
        "no_input": ExitCode.NO_INPUT,
        "timeout": ExitCode.TIMEOUT,
        "validation": ExitCode.VALIDATION_ERROR,
        "dependency": ExitCode.DEPENDENCY_MISSING,
        "config": ExitCode.CONFIG_ERROR,
        "io": ExitCode.IO_ERROR,
        "permission": ExitCode.NO_PERMISSION,
    }
    return error_map.get(error_type, ExitCode.GENERAL_ERROR)


# ============================================================================
# D-3: Consistent JSON output
# ============================================================================


@dataclass
class CliResponse:
    """Стандартизированный response для CLI команд.

    Все CLI команды возвращают этот формат при --json флаге.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    error_type: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        """Сериализация в JSON."""
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict."""
        return asdict(self)


def format_json_output(
    success: bool,
    data: dict[str, Any] | None = None,
    error: str = "",
    error_type: str = "",
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """D-3: Форматировать JSON output для CLI."""
    response = CliResponse(
        success=success,
        data=data or {},
        error=error,
        error_type=error_type,
        warnings=warnings or [],
        metadata=metadata or {},
    )
    return response.to_json()


def print_json_output(
    success: bool,
    data: dict[str, Any] | None = None,
    error: str = "",
    error_type: str = "",
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    """D-3 + D-4: Напечатать JSON output и вернуть exit code."""
    print(format_json_output(
        success=success,
        data=data,
        error=error,
        error_type=error_type,
        warnings=warnings,
        metadata=metadata,
    ))
    return get_exit_code(success, error_type)


# ============================================================================
# D-1: Unified help system
# ============================================================================


@dataclass
class CommandHelp:
    """Help для одной команды."""

    name: str
    description: str
    usage: str
    examples: list[str] = field(default_factory=list)
    arguments: list[dict[str, str]] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


_COMMANDS_HELP: dict[str, CommandHelp] = {
    "config": CommandHelp(
        name="config",
        description="Управление конфигурациями 1С",
        usage="1c-ai config <subcommand> [options]",
        examples=[
            "1c-ai config list",
            "1c-ai config add --name ut11 --zip ut11.zip --title 'УТ 11'",
            "1c-ai config build --name ut11",
            "1c-ai config build-all",
        ],
        arguments=[
            {"name": "list", "description": "Список конфигураций"},
            {"name": "add", "description": "Добавить конфигурацию"},
            {"name": "build", "description": "Построить индекс"},
            {"name": "build-all", "description": "Построить все индексы"},
        ],
    ),
    "bsl": CommandHelp(
        name="bsl",
        description="Анализ BSL кода",
        usage="1c-ai bsl <subcommand> [options]",
        examples=[
            "1c-ai bsl analyze <path>",
            "1c-ai bsl baseline <path>",
            "1c-ai bsl diff <path>",
        ],
        arguments=[
            {"name": "analyze", "description": "Анализ кода"},
            {"name": "baseline", "description": "Создать baseline"},
            {"name": "diff", "description": "Сравнить с baseline"},
        ],
    ),
    "search": CommandHelp(
        name="search",
        description="Поиск по методам 1С",
        usage="1c-ai search <query> [options]",
        examples=[
            "1c-ai search 'найти по коду'",
            "1c-ai search --limit 20 'запрос'",
            "1c-ai search --json 'запрос'",
        ],
        arguments=[
            {"name": "query", "description": "Поисковый запрос"},
            {"name": "--limit", "description": "Максимум результатов (default: 10)"},
            {"name": "--json", "description": "JSON output"},
        ],
    ),
    "standards": CommandHelp(
        name="standards",
        description="Проверка кода на стандарты 1С",
        usage="1c-ai standards <path> [options]",
        examples=[
            "1c-ai standards module.bsl",
            "1c-ai standards --level standard module.bsl",
        ],
    ),
    "validate": CommandHelp(
        name="validate",
        description="Валидация проекта",
        usage="1c-ai validate",
        examples=["1c-ai validate"],
    ),
    "inspect": CommandHelp(
        name="inspect",
        description="Инспекция объектов 1С",
        usage="1c-ai inspect <type> <path>",
        examples=[
            "1c-ai inspect cf <path>",
            "1c-ai inspect form <path>",
            "1c-ai inspect meta <path>",
        ],
    ),
    "epf": CommandHelp(
        name="epf",
        description="Создание внешних обработок (.epf)",
        usage="1c-ai epf <subcommand> [options]",
        examples=[
            "1c-ai epf create --name MyProc --output my.epf",
            "1c-ai epf create --native --name X --output x.epf",
        ],
    ),
    "cfe": CommandHelp(
        name="cfe",
        description="Управление CFE расширениями",
        usage="1c-ai cfe <subcommand> [options]",
        examples=[
            "1c-ai cfe borrow --type Catalog --name Товары",
            "1c-ai cfe patch --module Module.bsl --method Method",
        ],
    ),
    "dsl": CommandHelp(
        name="dsl",
        description="Компиляция DSL в XML",
        usage="1c-ai dsl <subcommand> [options]",
        examples=[
            "1c-ai dsl compile --type Catalog --input def.json --output out/",
            "1c-ai dsl round-trip --input def.json",
        ],
    ),
}


def print_help(command_name: str | None = None) -> int:
    """D-1: Напечатать help для команды."""
    if command_name is None:
        print("1c-ai-dev-env — Среда разработки 1С с ИИ-ассистентом\n")
        print("Usage: 1c-ai <command> [subcommand] [options]\n")
        print("Commands:")
        for cmd in sorted(_COMMANDS_HELP.keys()):
            help_obj = _COMMANDS_HELP[cmd]
            print(f"  {cmd:15} {help_obj.description}")
        print("\nUse '1c-ai help <command>' for command-specific help.")
        print("Use '1c-ai --version' for version info.")
        return ExitCode.SUCCESS

    if command_name not in _COMMANDS_HELP:
        print(f"Unknown command: {command_name}")
        print(f"Available commands: {', '.join(sorted(_COMMANDS_HELP.keys()))}")
        return ExitCode.USAGE_ERROR

    help_obj = _COMMANDS_HELP[command_name]
    print(f"{help_obj.name} — {help_obj.description}\n")
    print(f"Usage: {help_obj.usage}\n")

    if help_obj.examples:
        print("Examples:")
        for ex in help_obj.examples:
            print(f"  {ex}")
        print()

    if help_obj.arguments:
        print("Arguments:")
        for arg in help_obj.arguments:
            print(f"  {arg['name']:15} {arg['description']}")
        print()

    if help_obj.see_also:
        print(f"See also: {', '.join(help_obj.see_also)}")

    return ExitCode.SUCCESS


def get_all_commands() -> list[str]:
    """Список всех доступных команд."""
    return sorted(_COMMANDS_HELP.keys())


def get_command_help(command_name: str) -> CommandHelp | None:
    """Получить help для команды."""
    return _COMMANDS_HELP.get(command_name)
