#!/usr/bin/env python3
"""Тесты для architecture_analyzer.py."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from architecture_analyzer import ArchitectureAnalyzer, ArchitectureIssue, ModuleInfo


@pytest.fixture
def analyzer():
    return ArchitectureAnalyzer()


class TestGodObjects:
    def test_god_object_by_loc(self, analyzer):
        code = "А = 1;\n" * 1100
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            issues = analyzer.analyze_file(Path(f.name), 'BigModule')
            os.unlink(f.name)
        assert any(i.rule_id == 'ARCH004' for i in issues)

    def test_small_module_ok(self, analyzer):
        code = "А = 1;\nБ = 2;\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            issues = analyzer.analyze_file(Path(f.name), 'SmallModule')
            os.unlink(f.name)
        assert not any(i.rule_id == 'ARCH004' for i in issues)


class TestMissingRegions:
    def test_no_regions_detected(self, analyzer):
        code = "А = 1;\n" * 30
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            issues = analyzer.analyze_file(Path(f.name), 'NoRegions')
            os.unlink(f.name)
        assert any(i.rule_id == 'ARCH007' for i in issues)

    def test_with_regions_ok(self, analyzer):
        code = "#Область ПрограммныйИнтерфейс\nА = 1;\n#КонецОбласти\n" * 10
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            issues = analyzer.analyze_file(Path(f.name), 'WithRegions')
            os.unlink(f.name)
        assert not any(i.rule_id == 'ARCH007' for i in issues)


class TestQueriesInForms:
    def test_query_without_na_server(self, analyzer):
        code = """&НаКлиенте
Процедура Тест()
    Запрос = Новый Запрос;
КонецПроцедуры
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            # analyze_file не проверяет формы, нужен analyze_config
            # Но проверим через прямой вызов _check_queries_in_forms
            from architecture_analyzer import ModuleInfo
            mi = ModuleInfo(name='TestForm', file_path=f.name, module_type='FormModule')
            issues = analyzer._check_queries_in_forms([mi])
            os.unlink(f.name)
        assert any(i.rule_id == 'ARCH009' for i in issues)

    def test_query_with_na_server_ok(self, analyzer):
        code = """&НаСервере
Процедура ТестНаСервере()
    Запрос = Новый Запрос;
КонецПроцедуры
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            from architecture_analyzer import ModuleInfo
            mi = ModuleInfo(name='TestForm', file_path=f.name, module_type='FormModule')
            issues = analyzer._check_queries_in_forms([mi])
            os.unlink(f.name)
        assert not any(i.rule_id == 'ARCH009' for i in issues)


class TestParseModule:
    def test_export_methods_detected(self, analyzer):
        code = """Процедура Экспортная() Экспорт
КонецПроцедуры
Функция НеЭкспортная()
    Возврат 1;
КонецФункции
Процедура ЕщёЭкспортная(А, Б) Экспорт
КонецПроцедуры
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            mi = analyzer._parse_module(Path(f.name), 'TestModule', 'CommonModule')
            os.unlink(f.name)
        assert len(mi.export_methods) == 2
        assert 'Экспортная' in mi.export_methods
        assert 'ЕщёЭкспортная' in mi.export_methods

    def test_dependencies_detected(self, analyzer):
        code = """Процедура Тест()
    Результат = ОбщегоНазначения.ВыполнитьЧто();
    ДругойМодуль.СделатьЧтото();
КонецПроцедуры
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bsl', delete=False, encoding='utf-8') as f:
            f.write(code)
            f.flush()
            mi = analyzer._parse_module(Path(f.name), 'TestModule', 'CommonModule')
            os.unlink(f.name)
        assert 'ОбщегоНазначения' in mi.dependencies
        assert 'ДругойМодуль' in mi.dependencies


class TestStats:
    def test_empty_issues(self, analyzer):
        stats = analyzer.get_stats([])
        assert stats['total_issues'] == 0

    def test_mixed_issues(self, analyzer):
        issues = [
            ArchitectureIssue('ARCH001', 'HIGH', 'Module1', 0, 'Test'),
            ArchitectureIssue('ARCH004', 'HIGH', 'Module2', 0, 'Test'),
            ArchitectureIssue('ARCH007', 'MEDIUM', 'Module3', 0, 'Test'),
        ]
        stats = analyzer.get_stats(issues)
        assert stats['total_issues'] == 3
        assert stats['by_severity']['HIGH'] == 2


class TestIntegrationRealData:
    UT11_DIR = Path('/home/z/my-project/repo_work/data/configs/ut11')

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_analyze_ut11(self, analyzer):
        issues, modules = analyzer.analyze_config(self.UT11_DIR)
        stats = analyzer.get_stats(issues)
        print(f"\n  Модулей: {len(modules)}")
        print(f"  Проблем: {stats['total_issues']}")
        print(f"  by severity: {stats['by_severity']}")
        assert isinstance(issues, list)
        assert isinstance(modules, list)
        assert len(modules) > 0
