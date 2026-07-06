"""
M7 (2026-07-06): Тесты для MCP improvements (I6.2, A-7, A-8, I6.8).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from src.cli_tools.mcp_improvements import (
    MIN_MCP_SDK_VERSION,
    MCP_SDK_VERSIONS,
    RECOMMENDED_MCP_SDK_VERSION,
    AsyncToolDef,
    GITHUB_ACTION_TEMPLATE,
    ToolVersion,
    check_sdk_compatibility,
    get_all_tool_versions,
    get_async_tool_wrapper,
    get_deprecated_tools,
    get_github_action_template,
    get_recommended_sdk_version,
    get_sdk_compatibility_info,
    get_tool_version,
    is_sdk_version_supported,
    is_tool_deprecated,
    run_tool_async,
    save_github_action,
)


# ============================================================================
# I6.2: Tool versioning tests
# ============================================================================


class TestToolVersioning:
    def test_tool_version_dataclass(self) -> None:
        v = ToolVersion("test", "1.0.0", "6.0.0")
        assert v.tool_name == "test"
        assert v.version == "1.0.0"
        assert v.deprecated_in == ""

    def test_get_tool_version_existing(self) -> None:
        v = get_tool_version("search_1c_methods")
        assert v is not None
        assert v.tool_name == "search_1c_methods"

    def test_get_tool_version_nonexistent(self) -> None:
        assert get_tool_version("nonexistent") is None

    def test_is_tool_deprecated_false(self) -> None:
        assert is_tool_deprecated("search_1c_methods") is False

    def test_is_tool_deprecated_true(self) -> None:
        # create_epf deprecated in 6.3.0
        assert is_tool_deprecated("create_epf") is True

    def test_get_all_tool_versions(self) -> None:
        versions = get_all_tool_versions()
        assert len(versions) >= 10
        assert "search_1c_methods" in versions

    def test_get_deprecated_tools(self) -> None:
        deprecated = get_deprecated_tools()
        assert len(deprecated) >= 1
        names = [d.tool_name for d in deprecated]
        assert "create_epf" in names

    def test_deprecated_tool_has_successor(self) -> None:
        v = get_tool_version("create_epf")
        assert v is not None
        assert v.successor == "create_epf_native"


# ============================================================================
# A-7: MCP SDK compatibility tests
# ============================================================================


class TestMcpSdkCompatibility:
    def test_sdk_versions_defined(self) -> None:
        assert len(MCP_SDK_VERSIONS) >= 4
        assert "1.0" in MCP_SDK_VERSIONS
        assert "1.3" in MCP_SDK_VERSIONS

    def test_recommended_version(self) -> None:
        assert RECOMMENDED_MCP_SDK_VERSION == "1.3"

    def test_min_version(self) -> None:
        assert MIN_MCP_SDK_VERSION == "1.0"

    def test_is_sdk_version_supported_true(self) -> None:
        assert is_sdk_version_supported("1.0") is True
        assert is_sdk_version_supported("1.3") is True

    def test_is_sdk_version_supported_false(self) -> None:
        assert is_sdk_version_supported("0.9") is False
        assert is_sdk_version_supported("2.0") is False

    def test_get_recommended_sdk_version(self) -> None:
        assert get_recommended_sdk_version() == "1.3"

    def test_get_sdk_compatibility_info_existing(self) -> None:
        info = get_sdk_compatibility_info("1.3")
        assert info is not None
        assert "features" in info

    def test_get_sdk_compatibility_info_nonexistent(self) -> None:
        assert get_sdk_compatibility_info("0.5") is None

    def test_check_sdk_compatibility_supported(self) -> None:
        result = check_sdk_compatibility("1.3")
        assert result["supported"] is True
        assert result["recommended"] is True

    def test_check_sdk_compatibility_unsupported(self) -> None:
        result = check_sdk_compatibility("0.5")
        assert result["supported"] is False
        assert "not supported" in result["recommendation"]

    def test_check_sdk_compatibility_old_version(self) -> None:
        result = check_sdk_compatibility("1.0")
        assert result["supported"] is True
        assert result["recommended"] is False
        assert "upgrading" in result["recommendation"]


# ============================================================================
# A-8: Async tool definitions tests
# ============================================================================


class TestAsyncToolDef:
    def test_creation(self) -> None:
        td = AsyncToolDef(name="test", description="Test tool")
        assert td.name == "test"
        assert td.is_async is True
        assert td.timeout_seconds == 30

    def test_with_custom_timeout(self) -> None:
        td = AsyncToolDef(name="test", description="Test", timeout_seconds=60)
        assert td.timeout_seconds == 60


class TestAsyncWrapper:
    def test_wraps_sync_function(self) -> None:
        def sync_func(x: int) -> int:
            return x * 2

        async_func = get_async_tool_wrapper(sync_func)
        assert asyncio.iscoroutinefunction(async_func)

    def test_async_wrapper_returns_result(self) -> None:
        def sync_func(x: int) -> int:
            return x + 1

        async_func = get_async_tool_wrapper(sync_func)
        result = asyncio.run(async_func(5))
        assert result == 6

    def test_async_wrapper_timeout(self) -> None:
        def slow_func() -> str:
            time.sleep(2)
            return "done"

        async_func = get_async_tool_wrapper(slow_func, timeout_seconds=1)
        result = asyncio.run(async_func())
        assert isinstance(result, dict)
        assert "timeout" in result["error_type"]

    def test_async_wrapper_handles_exception(self) -> None:
        def failing_func() -> None:
            raise ValueError("test error")

        async_func = get_async_tool_wrapper(failing_func)
        result = asyncio.run(async_func())
        assert isinstance(result, dict)
        assert result["error_type"] == "execution_error"
        assert "test error" in result["error"]

    def test_run_tool_async(self) -> None:
        def sync_func(x: int) -> int:
            return x * 3

        result = run_tool_async(sync_func, 5)
        assert result == 15

    def test_run_tool_async_with_timeout(self) -> None:
        def slow_func() -> str:
            time.sleep(2)
            return "done"

        result = run_tool_async(slow_func, timeout_seconds=1)
        assert isinstance(result, dict)
        assert result["error_type"] == "timeout"


# ============================================================================
# I6.8: GitHub Action tests
# ============================================================================


class TestGitHubAction:
    def test_template_exists(self) -> None:
        assert GITHUB_ACTION_TEMPLATE
        assert "1c-ai-dev-env" in GITHUB_ACTION_TEMPLATE

    def test_get_github_action_template(self) -> None:
        template = get_github_action_template()
        assert "name:" in template
        assert "description:" in template
        assert "inputs:" in template

    def test_template_has_command_input(self) -> None:
        template = get_github_action_template()
        assert "command:" in template
        assert "required: true" in template

    def test_template_has_docker_image(self) -> None:
        template = get_github_action_template()
        assert "docker://" in template
        assert "1c-ai-dev-env" in template

    def test_save_github_action(self, tmp_path: Path) -> None:
        output = tmp_path / "action.yml"
        result = save_github_action(output)
        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "1c-ai-dev-env" in content

    def test_save_github_action_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / ".github" / "actions" / "1c-ai" / "action.yml"
        save_github_action(output)
        assert output.exists()

    def test_template_has_example_usage(self) -> None:
        template = get_github_action_template()
        assert "Example usage" in template
        assert "uses:" in template


# ============================================================================
# Integration tests
# ============================================================================


class TestIntegration:
    def test_all_features_work_together(self) -> None:
        """Все 4 фичи работают вместе."""
        # I6.2: versioning
        assert get_tool_version("search_1c_methods") is not None

        # A-7: SDK
        assert check_sdk_compatibility("1.3")["supported"] is True

        # A-8: async
        async_func = get_async_tool_wrapper(lambda x: x + 1)
        result = asyncio.run(async_func(10))
        assert result == 11

        # I6.8: action
        template = get_github_action_template()
        assert "1c-ai-dev-env" in template
