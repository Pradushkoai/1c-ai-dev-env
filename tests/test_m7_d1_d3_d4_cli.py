"""
M7 (2026-07-06): Тесты для CLI unified (D-1, D-3, D-4).
"""

from __future__ import annotations

import json

import pytest

from src.cli.unified import (
    CliResponse,
    CommandHelp,
    ExitCode,
    format_json_output,
    get_all_commands,
    get_command_help,
    get_exit_code,
    print_help,
    print_json_output,
)


# ============================================================================
# D-4: Exit codes tests
# ============================================================================


class TestExitCodes:
    def test_success_is_zero(self) -> None:
        assert ExitCode.SUCCESS == 0

    def test_general_error_is_one(self) -> None:
        assert ExitCode.GENERAL_ERROR == 1

    def test_usage_error_is_two(self) -> None:
        assert ExitCode.USAGE_ERROR == 2

    def test_get_exit_code_success(self) -> None:
        assert get_exit_code(success=True) == 0

    def test_get_exit_code_failure_general(self) -> None:
        assert get_exit_code(success=False) == 1

    def test_get_exit_code_not_found(self) -> None:
        assert get_exit_code(success=False, error_type="not_found") == 127

    def test_get_exit_code_validation(self) -> None:
        assert get_exit_code(success=False, error_type="validation") == 128

    def test_get_exit_code_timeout(self) -> None:
        assert get_exit_code(success=False, error_type="timeout") == 124

    def test_get_exit_code_dependency(self) -> None:
        assert get_exit_code(success=False, error_type="dependency") == 129

    def test_get_exit_code_config(self) -> None:
        assert get_exit_code(success=False, error_type="config") == 78

    def test_get_exit_code_unknown_type_defaults_to_general(self) -> None:
        assert get_exit_code(success=False, error_type="unknown") == 1


# ============================================================================
# D-3: JSON output tests
# ============================================================================


class TestCliResponse:
    def test_defaults(self) -> None:
        r = CliResponse(success=True)
        assert r.success is True
        assert r.data == {}
        assert r.error == ""
        assert r.warnings == []

    def test_to_json(self) -> None:
        r = CliResponse(success=True, data={"key": "value"})
        js = r.to_json()
        data = json.loads(js)
        assert data["success"] is True
        assert data["data"]["key"] == "value"

    def test_to_dict(self) -> None:
        r = CliResponse(success=False, error="test error", error_type="validation")
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "test error"
        assert d["error_type"] == "validation"


class TestFormatJsonOutput:
    def test_success_output(self) -> None:
        js = format_json_output(success=True, data={"result": "ok"})
        data = json.loads(js)
        assert data["success"] is True
        assert data["data"]["result"] == "ok"

    def test_error_output(self) -> None:
        js = format_json_output(success=False, error="Not found", error_type="not_found")
        data = json.loads(js)
        assert data["success"] is False
        assert data["error"] == "Not found"
        assert data["error_type"] == "not_found"

    def test_with_warnings(self) -> None:
        js = format_json_output(success=True, warnings=["warning1", "warning2"])
        data = json.loads(js)
        assert data["warnings"] == ["warning1", "warning2"]

    def test_with_metadata(self) -> None:
        js = format_json_output(success=True, metadata={"duration": 1.5, "count": 10})
        data = json.loads(js)
        assert data["metadata"]["duration"] == 1.5

    def test_empty_data_default(self) -> None:
        js = format_json_output(success=True)
        data = json.loads(js)
        assert data["data"] == {}


class TestPrintJsonOutput:
    def test_prints_and_returns_exit_code(self, capsys) -> None:
        rc = print_json_output(success=True, data={"x": 1})
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True

    def test_prints_error_and_returns_error_code(self, capsys) -> None:
        rc = print_json_output(success=False, error="fail", error_type="validation")
        assert rc == 128  # VALIDATION_ERROR
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is False


# ============================================================================
# D-1: Help system tests
# ============================================================================


class TestHelpSystem:
    def test_print_general_help(self, capsys) -> None:
        rc = print_help(None)
        assert rc == 0
        captured = capsys.readouterr()
        assert "1c-ai-dev-env" in captured.out
        assert "Commands:" in captured.out

    def test_print_command_help(self, capsys) -> None:
        rc = print_help("config")
        assert rc == 0
        captured = capsys.readouterr()
        assert "config" in captured.out
        assert "Управление конфигурациями" in captured.out

    def test_print_help_unknown_command(self, capsys) -> None:
        rc = print_help("unknown")
        assert rc == 2  # USAGE_ERROR
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    def test_get_all_commands(self) -> None:
        commands = get_all_commands()
        assert "config" in commands
        assert "bsl" in commands
        assert "search" in commands
        assert len(commands) >= 8

    def test_get_command_help_existing(self) -> None:
        help_obj = get_command_help("search")
        assert help_obj is not None
        assert help_obj.name == "search"
        assert help_obj.description

    def test_get_command_help_nonexistent(self) -> None:
        assert get_command_help("nonexistent") is None

    def test_all_commands_have_description(self) -> None:
        for cmd in get_all_commands():
            help_obj = get_command_help(cmd)
            assert help_obj is not None
            assert help_obj.description
            assert help_obj.usage

    def test_all_commands_have_examples(self) -> None:
        for cmd in get_all_commands():
            help_obj = get_command_help(cmd)
            assert help_obj is not None
            assert len(help_obj.examples) > 0


# ============================================================================
# CommandHelp dataclass tests
# ============================================================================


class TestCommandHelp:
    def test_creation(self) -> None:
        ch = CommandHelp(
            name="test",
            description="Test command",
            usage="test [options]",
        )
        assert ch.name == "test"
        assert ch.examples == []
        assert ch.arguments == []

    def test_with_examples(self) -> None:
        ch = CommandHelp(
            name="test",
            description="Test",
            usage="test",
            examples=["test --foo", "test --bar"],
        )
        assert len(ch.examples) == 2
