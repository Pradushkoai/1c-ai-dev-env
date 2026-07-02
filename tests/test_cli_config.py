"""
Тесты для src/cli_commands/config.py — управление конфигурациями.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.cli_commands.config import (
    _print_build_report,
    cmd_config_add,
    cmd_config_build,
    cmd_config_build_all,
    cmd_config_list,
)


def _make_args(**kwargs):
    return argparse.Namespace(**kwargs)


def _make_project():
    project = MagicMock()
    return project


def _make_config(name="ut11", version="11.5", status="active", objects_count=500, path=None, archive=None):
    c = MagicMock()
    c.name = name
    c.version = version
    c.status = status
    c.objects_count = objects_count
    c.path = path
    c.archive = archive
    return c


# ─── _print_build_report ───


class TestPrintBuildReport:
    def test_all_indexes_fresh_skip(self, capsys):
        _print_build_report({"name": "ut11", "skipped": ["all"]})
        captured = capsys.readouterr()
        assert "ut11" in captured.out
        assert "свежие" in captured.out

    def test_all_indexes_built(self, capsys):
        report = {
            "name": "ut11",
            "skipped": [],
            "metadata": True,
            "api": True,
            "skd": True,
            "forms": True,
        }
        _print_build_report(report)
        captured = capsys.readouterr()
        assert "ut11" in captured.out
        assert "metadata=✅" in captured.out
        assert "api=✅" in captured.out

    def test_some_indexes_failed(self, capsys):
        report = {
            "name": "ut11",
            "skipped": [],
            "metadata": True,
            "api": False,
            "skd": True,
            "forms": False,
        }
        _print_build_report(report)
        captured = capsys.readouterr()
        assert "api=❌" in captured.out
        assert "forms=❌" in captured.out

    def test_skipped_some(self, capsys):
        report = {
            "name": "ut11",
            "skipped": ["skd"],
            "metadata": True,
            "api": True,
            "skd": True,
            "forms": True,
        }
        _print_build_report(report)
        captured = capsys.readouterr()
        assert "Пропущено" in captured.out
        assert "skd" in captured.out


# ─── cmd_config_list ───


class TestCmdConfigList:
    def test_no_configs(self, capsys):
        project = _make_project()
        project.list_configs.return_value = []
        cmd_config_list(project, _make_args())
        captured = capsys.readouterr()
        assert "Нет конфигураций" in captured.out

    def test_with_configs(self, capsys):
        project = _make_project()
        project.list_configs.return_value = [
            _make_config(name="ut11", version="11.5", objects_count=500, path=Path("/data/ut11")),
            _make_config(name="edo2", version="2.0", objects_count=200, archive=Path("/data/edo2.zip")),
        ]
        cmd_config_list(project, _make_args())
        captured = capsys.readouterr()
        assert "ut11" in captured.out
        assert "edo2" in captured.out
        assert "11.5" in captured.out

    def test_config_with_no_path(self, capsys):
        project = _make_project()
        project.list_configs.return_value = [_make_config(name="test", path=None, archive=None)]
        cmd_config_list(project, _make_args())
        captured = capsys.readouterr()
        assert "test" in captured.out
        assert "—" in captured.out


# ─── cmd_config_add ───


class TestCmdConfigAdd:
    def test_add_from_zip_with_build(self, capsys):
        project = _make_project()
        config = _make_config(name="ut11", version="11.5", objects_count=500)
        project.config_manager.add_from_zip.return_value = config
        project.config_manager.build.return_value = {"name": "ut11", "skipped": ["all"]}

        args = _make_args(name="ut11", zip="ut11.zip", cf=None, title="УТ 11", skip_build=False)
        cmd_config_add(project, args)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "ut11" in captured.out
        assert "Индексация" in captured.out
        project.config_manager.add_from_zip.assert_called_once()

    def test_add_from_zip_skip_build(self, capsys):
        project = _make_project()
        config = _make_config(name="ut11", version="11.5", objects_count=500)
        project.config_manager.add_from_zip.return_value = config

        args = _make_args(name="ut11", zip="ut11.zip", cf=None, title="УТ 11", skip_build=True)
        cmd_config_add(project, args)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "Индексация" not in captured.out
        project.config_manager.build.assert_not_called()

    def test_add_from_cf(self, capsys):
        project = _make_project()
        config = _make_config(name="test", version="1.0", objects_count=10)
        project.config_manager.add_from_cf.return_value = config
        project.config_manager.build.return_value = {"name": "test", "skipped": ["all"]}

        args = _make_args(name="test", zip=None, cf="test.cf", title="Test", skip_build=True)
        cmd_config_add(project, args)

        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "test" in captured.out
        project.config_manager.add_from_cf.assert_called_once()


# ─── cmd_config_build ───


class TestCmdConfigBuild:
    def test_build_force(self, capsys):
        project = _make_project()
        project.config_manager.build.return_value = {
            "name": "ut11",
            "skipped": [],
            "metadata": True,
            "api": True,
            "skd": True,
            "forms": True,
        }

        args = _make_args(name="ut11", force=True, check_freshness=False, validate=False)
        cmd_config_build(project, args)

        captured = capsys.readouterr()
        assert "ut11" in captured.out
        project.config_manager.build.assert_called_once_with("ut11", force=True)

    def test_check_freshness_all_fresh(self, capsys):
        project = _make_project()
        report = MagicMock()
        report.config_name = "ut11"
        report.all_fresh = True
        report.source_mtime = None
        report.missing_indexes = []
        report.stale_indexes = []
        report.indexes = []
        project.config_manager.check_freshness.return_value = report

        args = _make_args(name="ut11", force=False, check_freshness=True, validate=False)
        cmd_config_build(project, args)

        captured = capsys.readouterr()
        assert "ut11" in captured.out
        assert "да" in captured.out

    def test_check_freshness_stale(self, capsys):
        project = _make_project()
        report = MagicMock()
        report.config_name = "ut11"
        report.all_fresh = False
        report.source_mtime = 1234567890
        report.missing_indexes = ["skd"]
        report.stale_indexes = ["metadata"]
        report.indexes = []
        project.config_manager.check_freshness.return_value = report

        args = _make_args(name="ut11", force=False, check_freshness=True, validate=False)
        cmd_config_build(project, args)

        captured = capsys.readouterr()
        assert "нет" in captured.out
        assert "skd" in captured.out
        assert "metadata" in captured.out

    def test_validate_valid(self, capsys):
        project = _make_project()
        result = MagicMock()
        result.is_valid = True
        result.has_configuration_xml = True
        result.has_metadata_dirs = True
        result.has_bsl_files = True
        result.found_type_dirs = ["Catalogs", "Documents"]
        result.errors = []
        result.warnings = []
        project.config_manager.validate_sources.return_value = result

        args = _make_args(name="ut11", force=False, check_freshness=False, validate=True)
        cmd_config_build(project, args)

        captured = capsys.readouterr()
        assert "да" in captured.out
        assert "Catalogs" in captured.out

    def test_validate_invalid(self, capsys):
        project = _make_project()
        result = MagicMock()
        result.is_valid = False
        result.has_configuration_xml = False
        result.has_metadata_dirs = True
        result.has_bsl_files = False
        result.found_type_dirs = []
        result.errors = ["Configuration.xml not found"]
        result.warnings = []
        project.config_manager.validate_sources.return_value = result

        args = _make_args(name="ut11", force=False, check_freshness=False, validate=True)
        cmd_config_build(project, args)

        captured = capsys.readouterr()
        assert "нет" in captured.out
        assert "Configuration.xml not found" in captured.out


# ─── cmd_config_build_all ───


class TestCmdConfigBuildAll:
    def test_build_all(self, capsys):
        project = _make_project()
        project.config_manager.build_all.return_value = [
            {"name": "ut11", "skipped": ["all"]},
            {"name": "edo2", "skipped": [], "metadata": True, "api": True, "skd": False, "forms": True},
        ]

        args = _make_args(force=False)
        cmd_config_build_all(project, args)

        captured = capsys.readouterr()
        assert "ut11" in captured.out
        assert "edo2" in captured.out

    def test_build_all_empty(self, capsys):
        project = _make_project()
        project.config_manager.build_all.return_value = []

        args = _make_args(force=False)
        cmd_config_build_all(project, args)

        captured = capsys.readouterr()
        # Nothing printed — empty list
        assert captured.out == ""
