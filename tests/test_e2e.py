#!/usr/bin/env python3
"""E2E тест: полный цикл от генерации обработки до валидации и упаковки .epf."""

import shutil
import tempfile
from pathlib import Path

import pytest

# Этап 1.2 завершён: все генераторы и анализаторы перенесены в src.services.
# sys.path.insert больше не нужен.
from src.services.analyzers.architecture_analyzer import ArchitectureAnalyzer
from src.services.analyzers.check_1c_standards import StandardsChecker
from src.services.analyzers.code_metrics import CodeMetricsAnalyzer
from src.services.analyzers.query_analyzer import QueryAnalyzer
from src.services.analyzers.security_auditor import SecurityAuditor
from src.services.analyzers.transaction_checker import TransactionChecker
from src.services.code_generator import generate_processing, generate_report
from src.services.code_validator import validate_generated
from src.services.epf_builder import build_epf


class TestE2EProcessingGeneration:
    """E2E: генерация обработки → валидация → упаковка .epf."""

    def test_full_cycle_processing(self):
        """Полный цикл: generate → validate → build_epf."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Generate
            result = generate_processing(
                name="ТестоваяОбработка",
                synonym="Тестовая обработка",
                output_dir=str(tmpdir / "processing"),
            )
            assert result["stats"]["total_files"] >= 5
            assert result["stats"]["bsl_files"] >= 2
            assert result["stats"]["xml_files"] >= 1

            # Step 2: Validate
            validation = validate_generated(str(tmpdir / "processing"))
            assert validation["verdict"] in ("perfect", "warnings")
            assert validation["total_errors"] == 0

            # Step 3: Build .epf
            epf_path = tmpdir / "ТестоваяОбработка.epf"
            epf_result = build_epf(
                source_dir=str(tmpdir / "processing"),
                output_path=str(epf_path),
            )
            assert epf_path.exists()
            assert epf_result["size"] > 0
            assert epf_result["object_name"] == "ТестоваяОбработка"

    def test_full_cycle_report(self):
        """Полный цикл: generate report → validate → build_epf."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Generate
            result = generate_report(
                name="ТестовыйОтчет",
                synonym="Тестовый отчёт",
                output_dir=str(tmpdir / "report"),
                data_source="Документ.РеализацияТоваровУслуг",
            )
            assert result["stats"]["total_files"] >= 7
            assert result["stats"]["has_skd_schema"] is True

            # Step 2: Validate
            validation = validate_generated(str(tmpdir / "report"))
            assert validation["verdict"] in ("perfect", "warnings")
            assert validation["total_errors"] == 0

            # Step 3: Build .epf
            epf_path = tmpdir / "ТестовыйОтчет.erf"
            epf_result = build_epf(
                source_dir=str(tmpdir / "report"),
                output_path=str(epf_path),
                object_type="Report",
            )
            assert epf_path.exists()
            assert epf_result["size"] > 0


class TestE2ESecurityAudit:
    """E2E: аудит безопасности сгенерированного кода."""

    def test_generated_code_is_safe(self):
        """Сгенерированный код не должен содержать критических уязвимостей."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Generate
            generate_processing(
                name="БезопаснаяОбработка",
                synonym="Безопасная обработка",
                output_dir=str(tmpdir),
            )

            # Audit
            auditor = SecurityAuditor()
            bsl_file = tmpdir / "Ext" / "Module.bsl"
            violations = auditor.audit_file(bsl_file)

            critical = [v for v in violations if v.severity == "CRITICAL"]
            assert len(critical) == 0, f"Сгенерированный код содержит CRITICAL уязвимости: {critical}"


class TestE2ECodeMetrics:
    """E2E: метрики сгенерированного кода."""

    def test_generated_code_has_good_health(self):
        """Сгенерированный код должен иметь health score >= 80."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Generate
            generate_processing(
                name="КачественнаяОбработка",
                synonym="Качественная обработка",
                output_dir=str(tmpdir),
            )

            # Metrics
            analyzer = CodeMetricsAnalyzer()
            bsl_file = tmpdir / "Ext" / "Module.bsl"
            metrics = analyzer.analyze_file(bsl_file)

            assert metrics.health_score >= 80, f"Health score {metrics.health_score} < 80"
            assert not metrics.is_god_object
            assert len(metrics.long_methods) == 0


class TestE2ETransactionCheck:
    """E2E: проверка транзакций сгенерированного кода."""

    def test_generated_code_has_no_tx_violations(self):
        """Сгенерированный код не должен иметь нарушений транзакций."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Generate
            generate_processing(
                name="ТранзакционнаяОбработка",
                synonym="Транзакционная обработка",
                output_dir=str(tmpdir),
            )

            # Check
            checker = TransactionChecker()
            bsl_file = tmpdir / "Ext" / "Module.bsl"
            violations = checker.check_file(bsl_file)

            critical = [v for v in violations if v.severity in ("CRITICAL", "HIGH")]
            assert len(critical) == 0, f"Сгенерированный код содержит нарушения транзакций: {critical}"


class TestE2EQueryAnalysis:
    """E2E: анализ запросов в сгенерированном коде."""

    def test_generated_report_has_clean_queries(self):
        """Сгенерированный отчёт не должен иметь проблем с запросами СКД."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Generate report with SKD
            generate_report(
                name="ЧистыйОтчет",
                synonym="Чистый отчёт",
                output_dir=str(tmpdir),
                data_source="Справочник.Номенклатура",
            )

            # Check BSL module for query issues
            analyzer = QueryAnalyzer()
            bsl_file = tmpdir / "Ext" / "Module.bsl"
            if bsl_file.exists():
                issues = analyzer.analyze_file(bsl_file)
                critical = [i for i in issues if i.severity in ("CRITICAL", "HIGH")]
                assert len(critical) == 0, f"Сгенерированный код содержит проблемы запросов: {critical}"


class TestE2EFullSolveCheck:
    """E2E: полный solve_check на сгенерированном коде (quick level)."""

    def test_solve_check_quick_on_generated(self):
        """solve_check --level quick на сгенерированном коде — verdict perfect или warnings."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Generate
            generate_processing(
                name="ПолнаяПроверка",
                synonym="Полная проверка",
                output_dir=str(tmpdir),
            )

            bsl_file = tmpdir / "Ext" / "Module.bsl"
            total_errors = 0

            # 1. check_1c_standards
            checker = StandardsChecker()
            violations = checker.check_file(bsl_file)
            total_errors += sum(1 for v in violations if v.severity == "error")

            # 2. security_auditor
            auditor = SecurityAuditor()
            sec_violations = auditor.audit_file(bsl_file)
            total_errors += sum(1 for v in sec_violations if v.severity in ("CRITICAL", "HIGH"))

            # 3. transaction_checker
            tx_checker = TransactionChecker()
            tx_violations = tx_checker.check_file(bsl_file)
            total_errors += sum(1 for v in tx_violations if v.severity in ("CRITICAL", "HIGH"))

            # 4. query_analyzer
            qa_analyzer = QueryAnalyzer()
            qa_issues = qa_analyzer.analyze_file(bsl_file)
            total_errors += sum(1 for i in qa_issues if i.severity in ("CRITICAL", "HIGH"))

            assert total_errors == 0, f"Сгенерированный код прошёл solve_check с {total_errors} errors"
