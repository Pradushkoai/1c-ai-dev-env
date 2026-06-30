#!/usr/bin/env python3
"""Performance / benchmark тесты для критических операций."""
import os
import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

UT11_DIR = Path('/home/z/my-project/repo_work/data/configs/ut11')
UT11_DERIVED = Path('/home/z/my-project/repo_work/derived/configs/ut11')


# ============================================================================
# BENCHMARK: XML parsing
# ============================================================================

class TestBenchmarkXMLParsing:
    """Бенчмарки парсинга XML метаданных."""

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='xml-parse')
    def test_benchmark_parse_catalog(self, benchmark):
        """Парсинг одного Catalog.xml."""
        from metadata_extractor import UniversalObjectParser
        parser = UniversalObjectParser()

        # Берём первый попавшийся Catalog
        cat_dir = UT11_DIR / 'Catalogs'
        xml_files = list(cat_dir.glob('*.xml'))
        if not xml_files:
            pytest.skip('No catalog XML files')
        xml_file = xml_files[0]

        benchmark(parser.parse, xml_file)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='xml-parse')
    def test_benchmark_parse_configuration(self, benchmark):
        """Парсинг Configuration.xml."""
        from metadata_extractor import ConfigParser
        parser = ConfigParser()
        config_xml = UT11_DIR / 'Configuration.xml'
        if not config_xml.exists():
            pytest.skip('Configuration.xml not found')

        benchmark(parser.parse_configuration, config_xml)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='xml-parse-bulk')
    def test_benchmark_parse_100_catalogs(self, benchmark):
        """Парсинг 100 Catalog.xml файлов."""
        from metadata_extractor import UniversalObjectParser
        parser = UniversalObjectParser()

        cat_dir = UT11_DIR / 'Catalogs'
        xml_files = sorted(cat_dir.glob('*.xml'))[:100]
        if len(xml_files) < 10:
            pytest.skip('Not enough catalog files')

        def parse_100():
            for f in xml_files:
                parser.parse(f)

        benchmark(parse_100)


# ============================================================================
# BENCHMARK: BSL analysis
# ============================================================================

class TestBenchmarkBSLAnalysis:
    """Бенчмарки анализа BSL кода."""

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='bsl-analyze')
    def test_benchmark_security_audit(self, benchmark):
        """Аудит безопасности одного BSL файла."""
        from security_auditor import SecurityAuditor
        auditor = SecurityAuditor()

        # Берём первый BSL из CommonModules
        cm_dir = UT11_DIR / 'CommonModules'
        bsl_files = list(cm_dir.rglob('Module.bsl'))
        if not bsl_files:
            pytest.skip('No BSL files')
        bsl_file = bsl_files[0]

        benchmark(auditor.audit_file, bsl_file)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='bsl-analyze')
    def test_benchmark_code_metrics(self, benchmark):
        """Метрики кода одного BSL файла."""
        from code_metrics import CodeMetricsAnalyzer
        analyzer = CodeMetricsAnalyzer()

        cm_dir = UT11_DIR / 'CommonModules'
        bsl_files = list(cm_dir.rglob('Module.bsl'))
        if not bsl_files:
            pytest.skip('No BSL files')
        bsl_file = bsl_files[0]

        benchmark(analyzer.analyze_file, bsl_file)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='bsl-analyze')
    def test_benchmark_transaction_check(self, benchmark):
        """Проверка транзакций BSL файла."""
        from transaction_checker import TransactionChecker
        checker = TransactionChecker()

        cm_dir = UT11_DIR / 'CommonModules'
        bsl_files = list(cm_dir.rglob('Module.bsl'))
        if not bsl_files:
            pytest.skip('No BSL files')
        bsl_file = bsl_files[0]

        benchmark(checker.check_file, bsl_file)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='bsl-analyze')
    def test_benchmark_query_analyzer(self, benchmark):
        """Анализ запросов BSL файла."""
        from query_analyzer import QueryAnalyzer
        analyzer = QueryAnalyzer()

        cm_dir = UT11_DIR / 'CommonModules'
        bsl_files = list(cm_dir.rglob('Module.bsl'))
        if not bsl_files:
            pytest.skip('No BSL files')
        bsl_file = bsl_files[0]

        benchmark(analyzer.analyze_file, bsl_file)

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    @pytest.mark.benchmark(group='bsl-analyze-bulk')
    def test_benchmark_audit_100_files(self, benchmark):
        """Аудит безопасности 100 BSL файлов."""
        from security_auditor import SecurityAuditor
        auditor = SecurityAuditor()

        cm_dir = UT11_DIR / 'CommonModules'
        bsl_files = list(cm_dir.rglob('Module.bsl'))[:100]
        if len(bsl_files) < 10:
            pytest.skip('Not enough BSL files')

        def audit_100():
            for f in bsl_files:
                auditor.audit_file(f)

        benchmark(audit_100)


# ============================================================================
# BENCHMARK: Search
# ============================================================================

class TestBenchmarkSearch:
    """Бенчмарки поиска."""

    @pytest.mark.skipif(not UT11_DERIVED.exists(), reason='UT11 derived not available')
    @pytest.mark.benchmark(group='search')
    def test_benchmark_search_code(self, benchmark):
        """Загрузка и подсчёт методов из api-reference.json."""
        api_ref = UT11_DERIVED / 'api-reference.json'
        if not api_ref.exists():
            pytest.skip('api-reference.json not found')

        def load_and_count():
            with open(api_ref, encoding='utf-8') as f:
                modules = json.load(f)
            return len(modules)

        result = benchmark(load_and_count)
        assert result > 0


# ============================================================================
# BENCHMARK: Index loading
# ============================================================================

class TestBenchmarkIndexLoading:
    """Бенчмарки загрузки индексов."""

    @pytest.mark.skipif(not UT11_DERIVED.exists(), reason='UT11 derived not available')
    @pytest.mark.benchmark(group='index-load')
    def test_benchmark_load_unified_metadata(self, benchmark):
        """Загрузка unified-metadata-index.json (203 МБ)."""
        index_path = UT11_DERIVED / 'unified-metadata-index.json'
        if not index_path.exists():
            pytest.skip('unified-metadata-index.json not found')

        def load_index():
            with open(index_path, encoding='utf-8') as f:
                return json.load(f)

        result = benchmark(load_index)
        assert 'objects' in result

    @pytest.mark.skipif(not UT11_DERIVED.exists(), reason='UT11 derived not available')
    @pytest.mark.benchmark(group='index-load')
    def test_benchmark_load_api_reference(self, benchmark):
        """Загрузка api-reference.json (84 МБ)."""
        index_path = UT11_DERIVED / 'api-reference.json'
        if not index_path.exists():
            pytest.skip('api-reference.json not found')

        def load_index():
            with open(index_path, encoding='utf-8') as f:
                return json.load(f)

        result = benchmark(load_index)
        assert len(result) > 0

    @pytest.mark.skipif(not UT11_DERIVED.exists(), reason='UT11 derived not available')
    @pytest.mark.benchmark(group='index-load')
    def test_benchmark_load_form_index(self, benchmark):
        """Загрузка form-index.json (37 МБ)."""
        index_path = UT11_DERIVED / 'form-index.json'
        if not index_path.exists():
            pytest.skip('form-index.json not found')

        def load_index():
            with open(index_path, encoding='utf-8') as f:
                return json.load(f)

        result = benchmark(load_index)
        assert 'forms' in result
