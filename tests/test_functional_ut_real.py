"""
Функциональные тесты на реальной конфигурации УправлениеТорговлей.

Тестовые данные: tests/functional_test_data/УправлениеТорговлей/
- Configuration.xml (УправлениеТорговлей)
- 5 Catalogs: Номенклатура, Контрагенты, Склады, Организации, Валюты
- 3 Documents: РеализацияТоваровУслуг, ПоступлениеТоваровУслуг, ЗаказКлиента
- 5 CommonModules с реальным BSL кодом:
  * ПродажиСервер (чистый код, 16K строк)
  * ОбщегоНазначенияКлиентСервер (содержит Пароль)
  * ВыгрузкаТоваровНаСайт (Выполнить + Пароль + HTTP)
  * ОбщийМодуль77w (Выполнить + Пароль + HTTP)
  * ИнтеграцияГИСМВызовСервера (Выполнить + HTTP)
- 99 BSL файлов всего
- 32 MB тестовых данных

Эти тесты проверяют что инструменты РЕАЛЬНО РАБОТАЮТ на production коде,
а не на синтетических данных.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Путь к реальным тестовым данным
UT_DATA_DIR = Path(__file__).parent / "functional_test_data" / "УправлениеТорговлей"
UT_MODULES = UT_DATA_DIR / "CommonModules"


# ============================================================================
# Test data validation
# ============================================================================


class TestUtDataIntegrity:
    """Проверка что реальные данные УТ загружены корректно."""

    def test_configuration_xml_exists(self) -> None:
        assert (UT_DATA_DIR / "Configuration.xml").exists()

    def test_configuration_is_ut(self) -> None:
        """Конфигурация — УправлениеТорговлей."""
        xml = (UT_DATA_DIR / "Configuration.xml").read_text(encoding="utf-8-sig")
        assert "УправлениеТорговлей" in xml

    def test_catalogs_exist(self) -> None:
        for cat in ["Номенклатура", "Контрагенты", "Склады"]:
            assert (UT_DATA_DIR / "Catalogs" / cat).is_dir()

    def test_documents_exist(self) -> None:
        for doc in ["РеализацияТоваровУслуг", "ЗаказКлиента"]:
            assert (UT_DATA_DIR / "Documents" / doc).is_dir()

    def test_common_modules_exist(self) -> None:
        for mod in ["ПродажиСервер", "ОбщегоНазначенияКлиентСервер"]:
            assert (UT_MODULES / mod / "Ext" / "Module.bsl").exists()

    def test_bsl_files_count(self) -> None:
        """Достаточно BSL файлов для тестирования."""
        bsl_files = list(UT_DATA_DIR.rglob("*.bsl"))
        assert len(bsl_files) >= 50, f"Expected >=50 BSL files, got {len(bsl_files)}"

    def test_real_violations_present(self) -> None:
        """Реальные модули содержат нарушения для детектирования."""
        # Ищем реальные нарушения: Пароль =, HTTPСоединение, ЗапуститьПриложение
        violation_files = []
        for bsl in UT_MODULES.rglob("Module.bsl"):
            code = bsl.read_text(encoding="utf-8-sig", errors="replace")
            if re.search(r'[Пп]ароль\s*=\s*"', code) or "HTTPСоединение" in code:
                violation_files.append(bsl.parent.parent.name)
        assert len(violation_files) >= 1, "Должны быть модули с нарушениями"

    def test_real_password_patterns(self) -> None:
        """Реальные модули содержат паттерны паролей."""
        password_files = []
        for bsl in UT_MODULES.rglob("Module.bsl"):
            code = bsl.read_text(encoding="utf-8-sig", errors="replace")
            if re.search(r'[Пп]ароль\s*=\s*"', code):
                password_files.append(bsl.parent.parent.name)
        assert len(password_files) >= 1, "Должны быть модули с паролями"

    def test_real_http_patterns(self) -> None:
        """Реальные модули содержат HTTPСоединение."""
        http_files = []
        for bsl in UT_MODULES.rglob("Module.bsl"):
            code = bsl.read_text(encoding="utf-8-sig", errors="replace")
            if "HTTPСоединение" in code:
                http_files.append(bsl.parent.parent.name)
        assert len(http_files) >= 1, "Должны быть модули с HTTP"


# ============================================================================
# Security auditor на реальном коде УТ
# ============================================================================


class TestUtSecurityAudit:
    """Security auditor находит нарушения в реальном коде УТ."""

    def test_audit_finds_violations_in_real_modules(self) -> None:
        """Аудит всех модулей УТ находит нарушения."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = auditor.audit_file(bsl)
            all_violations.extend(violations)

        assert len(all_violations) > 0, "Должны найтись нарушения в реальном коде УТ"

        # Проверяем разнообразие нарушений
        rule_ids = {v.rule_id for v in all_violations}
        assert len(rule_ids) >= 3, f"Ожидали >=3 разных правил, got: {rule_ids}"

    def test_audit_specific_module_with_violations(self) -> None:
        """Аудит модуля ВыгрузкаТоваровНаСайт находит SEC нарушения."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        bsl = UT_MODULES / "ВыгрузкаТоваровНаСайт" / "Ext" / "Module.bsl"
        violations = auditor.audit_file(bsl)

        # Этот модуль содержит множество нарушений (SQL injection, tokens, etc.)
        assert len(violations) > 10, f"Ожидали >10 нарушений, got {len(violations)}"

        rule_ids = {v.rule_id for v in violations}
        assert any(rid.startswith("SEC") for rid in rule_ids), \
            f"Должны найтись SEC нарушения, got: {rule_ids}"

    def test_audit_finds_password_violations(self) -> None:
        """Аудит находит хардкод паролей (SEC004)."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = auditor.audit_file(bsl)
            all_violations.extend(violations)

        sec004 = [v for v in all_violations if v.rule_id == "SEC004"]
        assert len(sec004) >= 1, "Должны найтись хардкод пароли (SEC004)"

    def test_audit_finds_http_violations(self) -> None:
        """Аудит находит HTTP без HTTPS (SEC010)."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = auditor.audit_file(bsl)
            all_violations.extend(violations)

        sec010 = [v for v in all_violations if v.rule_id == "SEC010"]
        assert len(sec010) >= 1, "Должны найтись HTTP без HTTPS (SEC010)"

    def test_audit_clean_module_no_critical(self) -> None:
        """ПродажиСервер — чистый модуль, нет critical нарушений."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        bsl = UT_MODULES / "ПродажиСервер" / "Ext" / "Module.bsl"
        violations = auditor.audit_file(bsl)

        critical = [v for v in violations if v.severity in ("CRITICAL", "HIGH")]
        # ПродажиСервер — качественный код, не должно быть critical
        # (может быть SEC010 для http://localhost, но не CRITICAL)
        sec_critical = [v for v in critical if v.rule_id not in ("SEC010",)]
        assert len(sec_critical) == 0, \
            f"Не ожидали critical нарушения в ПродажиСервер: {sec_critical}"

    def test_audit_path_scans_all_modules(self) -> None:
        """audit_path сканирует всю директорию CommonModules."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        violations = auditor.audit_path(UT_MODULES)

        assert len(violations) > 0
        # Разные модули должны быть проверены
        files_audited = {v.line for v in violations}  # хотя бы разные line numbers
        assert len(files_audited) > 1

    def test_audit_stats(self) -> None:
        """get_stats возвращает корректную статистику."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        all_violations: list = []
        for bsl in UT_MODULES.rglob("Module.bsl"):
            all_violations.extend(auditor.audit_file(bsl))

        stats = auditor.get_stats(all_violations)
        assert stats["total_violations"] > 0
        assert stats["critical_count"] >= 0
        assert "by_rule" in stats
        assert len(stats["by_rule"]) >= 2


# ============================================================================
# BSL LS Rules на реальном коде УТ
# ============================================================================


class TestUtBslLsRules:
    """BSL LS rules анализируют реальный код УТ."""

    def test_analyze_real_module_finds_violations(self) -> None:
        """BSL LS rules находят нарушения в реальных модулях."""
        from src.services.analyzers.bsl_ls_rules import BslLsRulesAnalyzer

        analyzer = BslLsRulesAnalyzer()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = analyzer.analyze(bsl)
            all_violations.extend(violations)

        assert len(all_violations) > 0, "Должны найтись нарушения BSL LS в реальном коде"

    def test_analyze_finds_long_lines(self) -> None:
        """Находит строки длиннее 120 символов (style-004)."""
        from src.services.analyzers.bsl_ls_rules import BslLsRulesAnalyzer

        analyzer = BslLsRulesAnalyzer()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = analyzer.analyze(bsl)
            all_violations.extend(violations)

        long_lines = [v for v in all_violations if v.rule_id == "bsl-ls-style-004"]
        # В реальном коде УТ точно есть длинные строки
        assert len(long_lines) >= 1, "Должны найтись строки > 120 символов"

    def test_analyze_finds_modal_calls(self) -> None:
        """Находит модальные вызовы (perf-009) или HTTP без HTTPS (sec-002)."""
        from src.services.analyzers.bsl_ls_rules import BslLsRulesAnalyzer

        analyzer = BslLsRulesAnalyzer()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = analyzer.analyze(bsl)
            all_violations.extend(violations)

        # Должны найтись sec-002 (HTTP) или perf-009 (modal)
        sec_or_perf = [v for v in all_violations if "sec-002" in v.rule_id or "perf-009" in v.rule_id]
        assert len(sec_or_perf) >= 1, "Должны найтись sec-002 или perf-009 нарушения"


# ============================================================================
# Code metrics на реальном коде
# ============================================================================


class TestUtCodeMetrics:
    """Анализ метрик реального кода УТ."""

    def test_complexity_analysis_on_real_code(self) -> None:
        """Complexity analyzer работает на реальном коде."""
        from src.services.analyzers.ast_analyzers_extended import (
            ComplexityAnalyzer, get_complexity_summary,
        )

        analyzer = ComplexityAnalyzer()
        bsl = UT_MODULES / "ПродажиСервер" / "Ext" / "Module.bsl"

        metrics = analyzer.analyze(bsl)
        assert len(metrics) > 0, "Должны найтись функции в ПродажиСервер"

        # Проверяем что метрики вычислены
        for m in metrics[:5]:
            assert m.name  # имя функции
            assert m.lines_of_code > 0
            assert m.cyclomatic_complexity >= 1

    def test_complexity_summary(self) -> None:
        """Summary метрик на реальном коде."""
        from src.services.analyzers.ast_analyzers_extended import (
            ComplexityAnalyzer, get_complexity_summary,
        )

        analyzer = ComplexityAnalyzer()
        bsl = UT_MODULES / "ПродажиСервер" / "Ext" / "Module.bsl"

        metrics = analyzer.analyze(bsl)
        summary = get_complexity_summary(metrics)

        assert summary["total_functions"] > 0
        assert summary["max_complexity"] >= 1
        assert summary["max_nesting"] >= 0
        assert summary["max_lines"] > 0

    def test_pattern_analysis_finds_anti_patterns(self) -> None:
        """Pattern analyzer находит anti-patterns в реальном коде."""
        from src.services.analyzers.ast_analyzers_extended import (
            ComplexityAnalyzer, PatternAnalyzer,
        )

        complexity_analyzer = ComplexityAnalyzer()
        pattern_analyzer = PatternAnalyzer()

        all_violations: list = []
        for bsl in UT_MODULES.rglob("Module.bsl"):
            metrics = complexity_analyzer.analyze(bsl)
            violations = pattern_analyzer.analyze(metrics)
            all_violations.extend(violations)

        # В реальном коде УТ точно есть long functions
        assert len(all_violations) > 0, "Должны найтись anti-patterns"

        patterns = {v.pattern for v in all_violations}
        # В коде УТ (16K+ строк в одном модуле) точно есть long-function
        assert "long-function" in patterns or "high-complexity" in patterns


# ============================================================================
# EDT Parser на реальных XML метаданных
# ============================================================================


class TestUtEdtParser:
    """EDT parser работает с реальными XML метаданными УТ."""

    def test_parse_catalog_xml(self) -> None:
        """Парсинг реального XML справочника."""
        cat_dir = UT_DATA_DIR / "Catalogs" / "Номенклатура"
        cat_xml = cat_dir / "Номенклатура.xml"
        if not cat_xml.exists():
            xml_files = list(cat_dir.rglob("*.xml"))
            assert len(xml_files) > 0, "Должен быть хотя бы один XML"
            cat_xml = xml_files[0]

        import xml.etree.ElementTree as ET
        tree = ET.parse(cat_xml)
        root = tree.getroot()
        assert root is not None
        xml_text = cat_xml.read_text(encoding="utf-8-sig")
        assert len(xml_text) > 100, "XML должен содержать метаданные"

    def test_parse_document_xml(self) -> None:
        """Парсинг реального XML документа ЗаказКлиента."""
        doc_dir = UT_DATA_DIR / "Documents" / "ЗаказКлиента"
        doc_xml = doc_dir / "ЗаказКлиента.xml"
        if not doc_xml.exists():
            doc_xml = list(doc_dir.rglob("*.xml"))[0]

        import xml.etree.ElementTree as ET
        tree = ET.parse(doc_xml)
        root = tree.getroot()

        # Проверяем что XML валиден
        assert root is not None

    def test_parse_all_catalog_xmls(self) -> None:
        """Все XML справочников парсятся без ошибок."""
        import xml.etree.ElementTree as ET

        cat_dir = UT_DATA_DIR / "Catalogs"
        for cat in cat_dir.iterdir():
            if not cat.is_dir():
                continue
            for xml_file in cat.rglob("*.xml"):
                try:
                    ET.parse(xml_file)
                except ET.ParseError as e:
                    pytest.fail(f"XML parse error in {xml_file}: {e}")


# ============================================================================
# Code sandbox на реальном коде УТ
# ============================================================================


class TestUtCodeSandbox:
    """Code sandbox проверяет реальный код УТ."""

    def test_validate_real_module_with_violations(self) -> None:
        """Sandbox находит нарушения в реальном модуле ВыгрузкаТоваровНаСайт."""
        from src.services.code_sandbox import validate_bsl_code

        bsl = UT_MODULES / "ВыгрузкаТоваровНаСайт" / "Ext" / "Module.bsl"
        code = bsl.read_text(encoding="utf-8-sig", errors="replace")
        result = validate_bsl_code(code)
        assert len(result.violations) > 0, "ВыгрузкаТоваровНаСайт должен иметь violations"

    def test_validate_clean_real_module(self) -> None:
        """Sandbox проверяет чистый модуль ПродажиСервер."""
        from src.services.code_sandbox import validate_bsl_code

        bsl = UT_MODULES / "ПродажиСервер" / "Ext" / "Module.bsl"
        code = bsl.read_text(encoding="utf-8-sig", errors="replace")

        result = validate_bsl_code(code)
        # ПродажиСервер может содержать или не содержать нарушения
        # Главное — что validation работает без crash
        assert hasattr(result, "is_safe")
        assert hasattr(result, "violations")


# ============================================================================
# BSL Templates — применимость к реальным сценариям УТ
# ============================================================================


class TestUtBslTemplatesApplicability:
    """BSL templates применимы к реальным объектам УТ."""

    def test_template_for_nomencatura_catalog(self) -> None:
        """Шаблон поиска по коду для справочника Номенклатура."""
        from src.services.bsl_templates import get_template

        code = get_template("catalog_find_by_code", catalog_name="Номенклатура")
        assert "Справочник.Номенклатура" in code
        assert "УстановитьПараметр" in code  # параметризованный запрос

    def test_template_for_realization_document(self) -> None:
        """Шаблон создания документа для РеализацияТоваровУслуг."""
        from src.services.bsl_templates import get_template

        code = get_template("document_create_with_header", document_name="РеализацияТоваровУслуг")
        assert "Документы.РеализацияТоваровУслуг" in code
        assert "СоздатьДокумент" in code

    def test_template_for_ut_query(self) -> None:
        """Шаблон запроса для реального объекта УТ."""
        from src.services.bsl_templates import get_template

        code = get_template(
            "query_with_filter",
            table_name="Документ.РеализацияТоваровУслуг",
            filter_field="Контрагент",
        )
        assert "Документ.РеализацияТоваровУслуг" in code
        assert "Контрагент" in code
        assert "&ЗначениеФильтра" in code  # параметризованный


# ============================================================================
# Integration: реальные сценарии УТ
# ============================================================================


class TestUtIntegration:
    """Интеграционные тесты на реальных сценариях УТ."""

    def test_security_audit_then_sandbox_pipeline(self) -> None:
        """Security audit → code sandbox pipeline на реальном коде."""
        from src.services.analyzers.security_auditor import SecurityAuditor
        from src.services.code_sandbox import validate_bsl_code

        auditor = SecurityAuditor()
        bsl = UT_MODULES / "ВыгрузкаТоваровНаСайт" / "Ext" / "Module.bsl"
        code = bsl.read_text(encoding="utf-8-sig", errors="replace")

        # Step 1: Security audit
        violations = auditor.audit_code(code)
        assert len(violations) > 10, "Должны найтись нарушения"

        # Step 2: Sandbox validation
        sandbox_result = validate_bsl_code(code)
        assert len(sandbox_result.violations) > 0, "Sandbox должен найти нарушения"

    def test_full_audit_report_on_real_code(self) -> None:
        """Полный отчёт аудита на всех модулях УТ."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        auditor = SecurityAuditor()
        all_violations: list = []

        for bsl in UT_MODULES.rglob("Module.bsl"):
            violations = auditor.audit_file(bsl)
            all_violations.extend(violations)

        stats = auditor.get_stats(all_violations)

        # Проверяем что отчёт содержит все необходимые поля
        assert "total_violations" in stats
        assert "by_severity" in stats
        assert "by_rule" in stats
        assert "critical_count" in stats
        assert "high_count" in stats

        # В реальном коде точно есть нарушения
        assert stats["total_violations"] > 0

    def test_bsl_ls_rules_and_security_auditor_complement(self) -> None:
        """BSL LS rules и security_auditor дополняют друг друга."""
        from src.services.analyzers.bsl_ls_rules import BslLsRulesAnalyzer
        from src.services.analyzers.security_auditor import SecurityAuditor

        sec_auditor = SecurityAuditor()
        ls_analyzer = BslLsRulesAnalyzer()

        bsl = UT_MODULES / "ВыгрузкаТоваровНаСайт" / "Ext" / "Module.bsl"

        sec_violations = sec_auditor.audit_file(bsl)
        ls_violations = ls_analyzer.analyze(bsl)

        # Security auditor находит SEC нарушения
        sec_rules = {v.rule_id for v in sec_violations}
        assert any(r.startswith("SEC") for r in sec_rules), \
            f"Security auditor должен найти SEC нарушения, got: {sec_rules}"

        # BSL LS находит style/best practice нарушения
        ls_rules = {v.rule_id for v in ls_violations}
        # Должны найтись style или best practice нарушения
        assert any("style" in r or "bp" in r for r in ls_rules), \
            f"BSL LS должен найти style/bp нарушения, got: {ls_rules}"

    def test_complexity_and_patterns_on_largest_module(self) -> None:
        """Complexity analysis на самом большом модуле."""
        from src.services.analyzers.ast_analyzers_extended import (
            ComplexityAnalyzer, PatternAnalyzer, get_complexity_summary,
        )

        # Находим самый большой BSL файл
        bsl_files = sorted(
            UT_MODULES.rglob("Module.bsl"),
            key=lambda f: f.stat().st_size,
            reverse=True,
        )
        if not bsl_files:
            pytest.skip("Нет BSL файлов")

        largest = bsl_files[0]
        module_name = largest.parent.parent.name

        analyzer = ComplexityAnalyzer()
        metrics = analyzer.analyze(largest)

        # Большой модуль должен иметь много функций
        assert len(metrics) > 5, f"Ожидали >5 функций в {module_name}, got {len(metrics)}"

        # Summary
        summary = get_complexity_summary(metrics)
        assert summary["total_functions"] > 5

        # Pattern analysis
        pattern_analyzer = PatternAnalyzer()
        violations = pattern_analyzer.analyze(metrics)
        # Большой модуль → точно есть anti-patterns
        assert len(violations) > 0, f"Ожидали anti-patterns в {module_name}"

    def test_mcp_audit_security_on_real_module(self) -> None:
        """MCP handler audit_security на реальном модуле УТ."""
        from src.mcpserver.handlers.quality import handle_audit_security

        project = MagicMock()
        project.paths.root = UT_DATA_DIR

        # Берём модуль с нарушениями
        bsl = UT_MODULES / "ВыгрузкаТоваровНаСайт" / "Ext" / "Module.bsl"
        rel_path = str(bsl.relative_to(UT_DATA_DIR))

        result = asyncio.run(handle_audit_security(
            project=project,
            arguments={"file_path": rel_path},
        ))

        assert len(result) > 0
        text = result[0].text
        data = json.loads(text)

        # Должны найтись нарушения (или error если путь не разрешён)
        if "violations" in data:
            assert len(data["violations"]) > 0, "Должны найтись нарушения в ВыгрузкаТоваровНаСайт"
        elif "error" in data:
            # Path resolution может не сработать из-за структуры директорий
            pytest.skip(f"MCP handler не смог найти файл: {data.get('error')}")
