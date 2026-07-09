"""
M7 (2026-07-06): MCP improvements — I6.2, A-7, A-8, I6.8.

I6.2: MCP tools versioning — версионирование MCP tools
A-7: MCP SDK compatibility — совместимость с MCP SDK
A-8: Async tool definitions — асинхронные tool definitions
I6.8: GitHub Action — GitHub Action для 1c-ai-dev-env

Использование:
    from src.cli.mcp_improvements import (
        get_tool_version, is_tool_deprecated, get_async_tool_wrapper,
        MCP_SDK_VERSIONS, GITHUB_ACTION_TEMPLATE,
    )
"""

from __future__ import annotations

import asyncio
import functools
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


# ============================================================================
# I6.2: MCP tools versioning
# ============================================================================


@dataclass
class ToolVersion:
    """Версия MCP tool."""

    tool_name: str
    version: str  # semver: "1.0.0"
    introduced_in: str = "6.0.0"  # версия проекта
    deprecated_in: str = ""  # пусто = не deprecated
    removed_in: str = ""  # пусто = не removed
    successor: str = ""  # замена если deprecated
    deprecation_reason: str = ""


# Registry версий tools
_TOOL_VERSIONS: dict[str, ToolVersion] = {
    "search_1c_methods": ToolVersion("search_1c_methods", "1.0.0", "6.0.0"),
    "search_code": ToolVersion("search_code", "1.0.0", "6.0.0"),
    "search_hybrid": ToolVersion("search_hybrid", "1.1.0", "6.1.0"),
    "analyze_architecture": ToolVersion("analyze_architecture", "1.0.0", "6.0.0"),
    "audit_security": ToolVersion("audit_security", "1.2.0", "6.2.0"),
    "check_transactions": ToolVersion("check_transactions", "1.0.0", "6.0.0"),
    "create_epf": ToolVersion("create_epf", "2.0.0", "6.0.0",
                               deprecated_in="6.3.0",
                               successor="create_epf_native",
                               deprecation_reason="Use create_epf_native for v8unpack-free creation"),
    "create_epf_native": ToolVersion("create_epf_native", "1.0.0", "6.3.0"),
    "compile_dsl": ToolVersion("compile_dsl", "1.0.0", "6.3.0"),
    "round_trip_dsl": ToolVersion("round_trip_dsl", "1.0.0", "6.3.0"),
}


def get_tool_version(tool_name: str) -> ToolVersion | None:
    """Получить версию tool."""
    return _TOOL_VERSIONS.get(tool_name)


def is_tool_deprecated(tool_name: str) -> bool:
    """Проверить, deprecated ли tool."""
    version = _TOOL_VERSIONS.get(tool_name)
    return version is not None and bool(version.deprecated_in)


def get_all_tool_versions() -> dict[str, ToolVersion]:
    """Все версии tools."""
    return dict(_TOOL_VERSIONS)


def get_deprecated_tools() -> list[ToolVersion]:
    """Список deprecated tools."""
    return [v for v in _TOOL_VERSIONS.values() if v.deprecated_in]


# ============================================================================
# A-7: MCP SDK compatibility
# ============================================================================

# Поддерживаемые версии MCP SDK
MCP_SDK_VERSIONS: dict[str, dict[str, Any]] = {
    "1.0": {
        "release_date": "2024-12-01",
        "features": ["basic_tools", "stdio_transport"],
        "deprecated": False,
    },
    "1.1": {
        "release_date": "2025-01-15",
        "features": ["basic_tools", "stdio_transport", "resources"],
        "deprecated": False,
    },
    "1.2": {
        "release_date": "2025-03-01",
        "features": ["basic_tools", "stdio_transport", "resources", "prompts"],
        "deprecated": False,
    },
    "1.3": {
        "release_date": "2025-06-01",
        "features": ["basic_tools", "stdio_transport", "resources", "prompts",
                     "sampling", "logging"],
        "deprecated": False,
        "current": True,
    },
}

# Минимальная поддерживаемая версия
MIN_MCP_SDK_VERSION = "1.0"
# Рекомендуемая версия
RECOMMENDED_MCP_SDK_VERSION = "1.3"


def is_sdk_version_supported(version: str) -> bool:
    """Проверить, поддерживается ли версия MCP SDK."""
    return version in MCP_SDK_VERSIONS


def get_recommended_sdk_version() -> str:
    """Рекомендуемая версия MCP SDK."""
    return RECOMMENDED_MCP_SDK_VERSION


def get_sdk_compatibility_info(version: str) -> dict[str, Any] | None:
    """Информация о совместимости для версии SDK."""
    return MCP_SDK_VERSIONS.get(version)


def check_sdk_compatibility(version: str) -> dict[str, Any]:
    """Полная проверка совместимости SDK.

    Returns:
        {supported, recommended, deprecated, features, recommendation}
    """
    info = MCP_SDK_VERSIONS.get(version)
    if info is None:
        return {
            "supported": False,
            "recommendation": f"Version {version} not supported. Use {RECOMMENDED_MCP_SDK_VERSION}",
        }

    return {
        "supported": True,
        "version": version,
        "recommended": version == RECOMMENDED_MCP_SDK_VERSION,
        "deprecated": info.get("deprecated", False),
        "features": info.get("features", []),
        "recommendation": "OK" if version == RECOMMENDED_MCP_SDK_VERSION
                         else f"Consider upgrading to {RECOMMENDED_MCP_SDK_VERSION}",
    }


# ============================================================================
# A-8: Async tool definitions
# ============================================================================


@dataclass
class AsyncToolDef:
    """Definition асинхронного MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    is_async: bool = True
    timeout_seconds: int = 30
    streaming: bool = False


def get_async_tool_wrapper(
    func: Callable[..., Any],
    *,
    timeout_seconds: int = 30,
) -> Callable[..., Any]:
    """A-8: Обёртка для асинхронного вызова tool.

    Превращает sync функцию в async с timeout.

    Args:
        func: Sync функция для обёртки.
        timeout_seconds: Timeout в секундах.

    Returns:
        Async функция.
    """
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            # Run sync function in thread pool with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                timeout=timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            return {"error": f"Tool timeout after {timeout_seconds}s",
                    "error_type": "timeout"}
        except Exception as e:
            return {"error": str(e), "error_type": "execution_error"}

    return async_wrapper


def run_tool_async(
    func: Callable[..., Any],
    *args: Any,
    timeout_seconds: int = 30,
    **kwargs: Any,
) -> Any:
    """Запустить sync tool асинхронно (sync wrapper для async).

    Args:
        func: Sync функция.
        *args: Позиционные аргументы.
        timeout_seconds: Timeout.
        **kwargs: Keyword аргументы.

    Returns:
        Результат или error dict.
    """
    async def _run() -> Any:
        wrapper = get_async_tool_wrapper(func, timeout_seconds=timeout_seconds)
        return await wrapper(*args, **kwargs)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — create task
            task = loop.create_task(_run())
            return loop.run_until_complete(task)
        else:
            return loop.run_until_complete(_run())
    except RuntimeError:
        # No event loop — create new one
        return asyncio.run(_run())


# ============================================================================
# I6.8: GitHub Action
# ============================================================================

GITHUB_ACTION_TEMPLATE = """\
# GitHub Action for 1c-ai-dev-env
# I6.8 (2026-07-06): Action для использования 1c-ai-dev-env в CI/CD

name: '1c-ai-dev-env'
description: 'Run 1c-ai-dev-env tools in your GitHub Actions workflow'
branding:
  icon: 'code'
  color: 'blue'

inputs:
  command:
    description: '1c-ai command to run (e.g., search, bsl analyze, standards)'
    required: true
  args:
    description: 'Arguments for the command'
    required: false
    default: ''
  config:
    description: 'Path to 1C configuration'
    required: false
    default: ''

runs:
  using: 'docker'
  image: 'docker://ghcr.io/pradushkoai/1c-ai-dev-env:latest'
  entrypoint: '1c-ai'
  args:
    - ${{{{ inputs.command }}}}
    - ${{{{ inputs.args }}}}

# Example usage in workflow:
# - uses: Pradushkoai/1c-ai-dev-env-action@v1
#   with:
#     command: 'search'
#     args: '--json "найти по коду"'
"""


def get_github_action_template() -> str:
    """I6.8: Получить template для GitHub Action."""
    return GITHUB_ACTION_TEMPLATE


def save_github_action(output_path: str | Path) -> Path:
    """Сохранить GitHub Action template.

    Args:
        output_path: Путь для action.yml.

    Returns:
        Path к созданному файлу.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(get_github_action_template(), encoding="utf-8")
    return output_path


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для MCP improvements."""
    import sys

    print("MCP Improvements (I6.2, A-7, A-8, I6.8)")
    print("=" * 50)

    # I6.2: Tool versions
    print("\nI6.2: Tool Versions")
    print(f"  Total tools: {len(_TOOL_VERSIONS)}")
    deprecated = get_deprecated_tools()
    print(f"  Deprecated: {len(deprecated)}")
    for d in deprecated:
        print(f"    - {d.tool_name} (deprecated in {d.deprecated_in}, use {d.successor})")

    # A-7: SDK compatibility
    print("\nA-7: MCP SDK Compatibility")
    print(f"  Supported versions: {', '.join(MCP_SDK_VERSIONS.keys())}")
    print(f"  Recommended: {RECOMMENDED_MCP_SDK_VERSION}")

    # A-8: Async tools
    print("\nA-8: Async Tool Support")
    print("  get_async_tool_wrapper(): wrap sync → async with timeout")
    print("  run_tool_async(): run sync tool asynchronously")

    # I6.8: GitHub Action
    print("\nI6.8: GitHub Action")
    print("  Use save_github_action(path) to create action.yml")

    return 0


if __name__ == "__main__":
    sys.exit(main())
