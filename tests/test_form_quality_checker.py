#!/usr/bin/env python3
"""Тесты для form_quality_checker.py."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from form_quality_checker import FormQualityChecker, FormQualityIssue


@pytest.fixture
def checker():
    return FormQualityChecker()


class TestEmptyForm:
    def test_empty_form_detected(self, checker):
        form = {"name": "TestForm", "parent_name": "Test", "form": {"element_count": 0, "items": []}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ001" for i in issues)

    def test_non_empty_form_ok(self, checker):
        form = {
            "name": "TestForm",
            "parent_name": "Test",
            "form": {
                "element_count": 1,
                "items": [{"type": "InputField", "name": "Поле1", "data_path": "Объект.Реквизит1"}],
            },
        }
        issues = checker.check_form(form)
        assert not any(i.rule_id == "FQ001" for i in issues)


class TestOverloadedForm:
    def test_overloaded_form_detected(self, checker):
        items = [{"type": "InputField", "name": f"Поле{i}", "data_path": f"Объект.Реквизит{i}"} for i in range(101)]
        form = {"name": "BigForm", "parent_name": "Test", "form": {"element_count": 101, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ002" for i in issues)

    def test_normal_form_ok(self, checker):
        items = [{"type": "InputField", "name": f"Поле{i}", "data_path": f"Объект.Реквизит{i}"} for i in range(10)]
        form = {"name": "NormalForm", "parent_name": "Test", "form": {"element_count": 10, "items": items}}
        issues = checker.check_form(form)
        assert not any(i.rule_id == "FQ002" for i in issues)


class TestNoDataPath:
    def test_no_datapath_detected(self, checker):
        items = [{"type": "InputField", "name": f"Поле{i}", "data_path": ""} for i in range(6)]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 6, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ003" for i in issues)


class TestButtonNoCommand:
    def test_button_no_command_detected(self, checker):
        items = [{"type": "Button", "name": "Кнопка1", "command_name": ""}]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 1, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ004" for i in issues)

    def test_button_with_command_ok(self, checker):
        items = [{"type": "Button", "name": "Кнопка1", "command_name": "Выполнить"}]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 1, "items": items}}
        issues = checker.check_form(form)
        assert not any(i.rule_id == "FQ004" for i in issues)


class TestTooManyButtons:
    def test_too_many_buttons_detected(self, checker):
        items = [{"type": "Button", "name": f"Кнопка{i}", "command_name": f"Cmd{i}"} for i in range(11)]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 11, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ005" for i in issues)


class TestHiddenElements:
    def test_hidden_elements_detected(self, checker):
        items = [
            {"type": "InputField", "name": f"Поле{i}", "data_path": f"Объект.Поле{i}", "visible": False}
            for i in range(4)
        ]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 4, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ006" for i in issues)


class TestDuplicateNames:
    def test_duplicate_names_detected(self, checker):
        items = [
            {"type": "InputField", "name": "Поле1", "data_path": "Объект.А"},
            {"type": "InputField", "name": "Поле1", "data_path": "Объект.Б"},
        ]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 2, "items": items}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ008" for i in issues)


class TestNoEvents:
    def test_no_events_detected(self, checker):
        items = [{"type": "InputField", "name": f"Поле{i}", "data_path": f"Объект.А{i}"} for i in range(6)]
        form = {"name": "Form", "parent_name": "Test", "form": {"element_count": 6, "items": items, "events": []}}
        issues = checker.check_form(form)
        assert any(i.rule_id == "FQ009" for i in issues)


class TestStats:
    def test_empty(self, checker):
        stats = checker.get_stats([])
        assert stats["total"] == 0

    def test_mixed(self, checker):
        issues = [
            FormQualityIssue("FQ001", "LOW", "Form1", "Test", "msg"),
            FormQualityIssue("FQ002", "HIGH", "Form2", "Test", "msg"),
        ]
        stats = checker.get_stats(issues)
        assert stats["total"] == 2


class TestIntegrationRealData:
    FORM_INDEX = Path("/home/z/my-project/repo_work/derived/configs/ut11/form-index.json")

    @pytest.mark.skipif(not FORM_INDEX.exists(), reason="UT11 form-index not available")
    def test_check_ut11_forms(self, checker):
        issues = checker.check_form_index(self.FORM_INDEX)
        stats = checker.get_stats(issues)
        print(f"\n  Проблем: {stats['total']}")
        print(f"  by severity: {stats['by_severity']}")
        assert isinstance(issues, list)
