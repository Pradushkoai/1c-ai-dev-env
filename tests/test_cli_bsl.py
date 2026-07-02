"""
Тесты для src/cli_commands/bsl.py — BSL анализ и валидация.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli_commands.bsl import cmd_bsl_analyze, cmd_bsl_baseline, cmd_bsl_diff, cmd_validate


def _make_args(**kwargs):
    """Создать mock argparse.Namespace."""
    return argparse.Namespace(**kwargs)


def _make_project_mock():
    """Создать mock Project с bsl_analyzer."""
    project = MagicMock()
    return project


# ─── cmd_bsl_analyze ───


class TestCmdBslAnalyze:
    def test_successful_analysis(self, capsys):
        """Успешный анализ BSL — выводит total и top codes."""
        project = _make_project_mock()
        result = MagicMock()
        result.total = 5
        result.by_code = {"STD001": 3, "STD002": 2}
        project.bsl_analyzer.analyze.return_value = result

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_analyze(project, args)

        captured = capsys.readouterr()
        assert "Всего: 5" in captured.out
        assert "STD001" in captured.out
        assert "STD002" in captured.out

    def test_file_not_found_error(self, capsys):
        """FileNotFoundError — BSL LS не установлен."""
        project = _make_project_mock()
        project.bsl_analyzer.analyze.side_effect = FileNotFoundError("bsl-language-server not found")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_analyze(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "BSL Language Server" in captured.out

    def test_general_exception(self, capsys):
        """Общая ошибка — выводит сообщение."""
        project = _make_project_mock()
        project.bsl_analyzer.analyze.side_effect = RuntimeError("unexpected error")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_analyze(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "unexpected error" in captured.out

    def test_empty_by_code(self, capsys):
        """Пустой by_code — только total."""
        project = _make_project_mock()
        result = MagicMock()
        result.total = 0
        result.by_code = {}
        project.bsl_analyzer.analyze.return_value = result

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_analyze(project, args)

        captured = capsys.readouterr()
        assert "Всего: 0" in captured.out


# ─── cmd_bsl_baseline ───


class TestCmdBslBaseline:
    def test_successful_baseline(self, capsys):
        """Успешное сохранение baseline."""
        project = _make_project_mock()
        result = MagicMock()
        result.total = 42
        project.bsl_analyzer.save_baseline.return_value = result

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_baseline(project, args)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "42" in captured.out

    def test_file_not_found_error(self, capsys):
        """FileNotFoundError — BSL LS не установлен."""
        project = _make_project_mock()
        project.bsl_analyzer.save_baseline.side_effect = FileNotFoundError("not found")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_baseline(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out

    def test_general_exception(self, capsys):
        """Общая ошибка."""
        project = _make_project_mock()
        project.bsl_analyzer.save_baseline.side_effect = RuntimeError("fail")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_baseline(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "fail" in captured.out


# ─── cmd_bsl_diff ───


class TestCmdBslDiff:
    def test_successful_diff_with_new_and_fixed(self, capsys):
        """Успешный diff — есть новые и исправленные."""
        project = _make_project_mock()
        diff = MagicMock()
        diff.new = [
            {"code": "STD001", "line": 10, "message": "error 1"},
            {"code": "STD002", "line": 20, "message": "error 2"},
        ]
        diff.fixed = [{"key": "OLD001"}]
        project.bsl_analyzer.diff.return_value = diff

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_diff(project, args)

        captured = capsys.readouterr()
        assert "НОВЫЕ (2)" in captured.out
        assert "STD001" in captured.out
        assert "STD002" in captured.out
        assert "ИСПРАВЛЕННЫЕ (1)" in captured.out
        assert "OLD001" in captured.out

    def test_successful_diff_empty(self, capsys):
        """Diff без новых и исправленных."""
        project = _make_project_mock()
        diff = MagicMock()
        diff.new = []
        diff.fixed = []
        project.bsl_analyzer.diff.return_value = diff

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_diff(project, args)

        captured = capsys.readouterr()
        assert "НОВЫЕ (0)" in captured.out
        assert "ИСПРАВЛЕННЫЕ (0)" in captured.out

    def test_file_not_found_error(self, capsys):
        """FileNotFoundError — BSL LS не установлен."""
        project = _make_project_mock()
        project.bsl_analyzer.diff.side_effect = FileNotFoundError("not found")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_diff(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "BSL Language Server" in captured.out

    def test_general_exception(self, capsys):
        """Общая ошибка."""
        project = _make_project_mock()
        project.bsl_analyzer.diff.side_effect = RuntimeError("fail")

        args = _make_args(path="/tmp/test.bsl")
        cmd_bsl_diff(project, args)

        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "fail" in captured.out


# ─── cmd_validate ───


class TestCmdValidate:
    def test_all_checks_pass(self, capsys):
        """Все проверки прошли — exit 0."""
        project = _make_project_mock()
        project.validate.return_value = {"python": True, "bsl_ls": True, "paths": True}

        args = _make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(project, args)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "✅" in captured.out

    def test_some_checks_fail(self, capsys):
        """Некоторые проверки провалились — exit 1."""
        project = _make_project_mock()
        project.validate.return_value = {"python": True, "bsl_ls": False, "paths": True}

        args = _make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(project, args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "❌" in captured.out
        assert "bsl_ls" in captured.out

    def test_all_checks_fail(self, capsys):
        """Все проверки провалились — exit 1."""
        project = _make_project_mock()
        project.validate.return_value = {"python": False, "bsl_ls": False}

        args = _make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(project, args)

        assert exc_info.value.code == 1

    def test_empty_checks(self, capsys):
        """Пустые проверки — exit 0 (all_ok=True by default)."""
        project = _make_project_mock()
        project.validate.return_value = {}

        args = _make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(project, args)

        assert exc_info.value.code == 0
