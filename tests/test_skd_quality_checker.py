#!/usr/bin/env python3
"""Тесты для skd_quality_checker.py."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from skd_quality_checker import SKDIssue, SKDQualityChecker


@pytest.fixture
def checker():
    return SKDQualityChecker()


class TestNoParameters:
    def test_no_params_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {"data_sets": [{"query": "ВЫБРАТЬ * ИЗ Таблица"}], "parameters": []},
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD001" for i in issues)

    def test_with_params_ok(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "Test",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Таблица"}],
                "parameters": [{"name": "Период", "types": ["xs:dateTime"]}],
            },
        }
        issues = checker.check_schema(schema)
        assert not any(i.rule_id == "SKD001" for i in issues)


class TestNoFilters:
    def test_no_filters_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {"data_sets": [], "parameters": [{"name": "P", "types": ["xs:string"]}], "filters": []},
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD003" for i in issues)


class TestNoTotalFields:
    def test_no_totals_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {
                "data_sets": [{"fields": [{"data_path": "Сумма"}], "query": "ВЫБРАТЬ Сумма"}],
                "total_fields": [],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD004" for i in issues)


class TestOverloadedSKD:
    def test_too_many_fields_detected(self, checker):
        fields = [{"data_path": f"Поле{i}"} for i in range(51)]
        schema = {
            "name": "Big",
            "parent_name": "",
            "schema": {
                "data_sets": [{"fields": fields}],
                "parameters": [{"name": "P", "types": ["xs:string"]}],
                "total_fields": [{"data_path": "Сумма"}],
                "filters": [{"name": "F"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD005" for i in issues)


class TestQueryNoWhere:
    def test_query_no_where_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Документ.Реализация", "fields": []}],
                "parameters": [{"name": "P", "types": ["xs:string"]}],
                "total_fields": [{"data_path": "S"}],
                "filters": [{"name": "F"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD006" for i in issues)


class TestParamNoType:
    def test_param_no_type_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {
                "data_sets": [{"query": "ВЫБРАТЬ * ИЗ Таблица ГДЕ Код = &Код"}],
                "parameters": [{"name": "Код", "types": []}],
                "total_fields": [{"data_path": "S"}],
                "filters": [{"name": "F"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD007" for i in issues)


class TestEmptyQuery:
    def test_empty_query_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {
                "data_sets": [{"query": "", "fields": []}],
                "parameters": [{"name": "P", "types": ["xs:string"]}],
                "total_fields": [{"data_path": "S"}],
                "filters": [{"name": "F"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD009" for i in issues)


class TestNoDataSource:
    def test_no_data_source_detected(self, checker):
        schema = {
            "name": "Test",
            "parent_name": "",
            "schema": {
                "data_sources": [],
                "data_sets": [],
                "parameters": [{"name": "P", "types": ["xs:string"]}],
                "total_fields": [{"data_path": "S"}],
                "filters": [{"name": "F"}],
            },
        }
        issues = checker.check_schema(schema)
        assert any(i.rule_id == "SKD010" for i in issues)


class TestStats:
    def test_empty(self, checker):
        stats = checker.get_stats([])
        assert stats["total"] == 0


class TestIntegrationRealData:
    SKD_INDEX = Path("/home/z/my-project/repo_work/derived/configs/ut11/skd-index.json")

    @pytest.mark.skipif(not SKD_INDEX.exists(), reason="UT11 skd-index not available")
    def test_check_ut11_skd(self, checker):
        issues = checker.check_skd_index(self.SKD_INDEX)
        stats = checker.get_stats(issues)
        print(f"\n  Проблем: {stats['total']}")
        print(f"  by severity: {stats['by_severity']}")
        assert isinstance(issues, list)
