"""
Smoke-тесты для критических путей 1c-ai-dev-env.

Этап 5.3: выделить smoke-тесты для быстрой обратной связи на каждый PR.
Запуск: pytest -m smoke — только smoke-тесты (< 30 сек).

Критические пути (10-15 тестов):
1. Config: list, add (mock), build (mock)
2. Search: BM25 search с pre-built индексом
3. BSL analysis: solve check quick на тестовом файле
4. DSL: compile meta (минимальный JSON → XML)
5. EPF: factory create (mock v8unpack)
6. MCP: list_tools возвращает 45 tools
7. Diff: compare_data на двух простых индексах
8. Standards: check_1c_standards на тестовом .bsl
9. Security: audit_file на тестовом .bsl
10. PathManager: пути корректно определяются
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Маркер smoke
# ============================================================================
pytestmark = pytest.mark.smoke


# ============================================================================
# 1. Config: list
# ============================================================================


class TestSmokeConfig:
    """Smoke: Config операции."""

    def test_config_registry_imports(self):
        """ConfigurationRegistry импортируется и имеет правильный API."""
        from src.models.config_registry import ConfigurationRegistry

        assert hasattr(ConfigurationRegistry, "list_all")
        assert hasattr(ConfigurationRegistry, "list_active")
        assert hasattr(ConfigurationRegistry, "add")


# ============================================================================
# 2. Search: BM25
# ============================================================================


class TestSmokeSearch:
    """Smoke: Search операции."""

    def test_search_bm25_import(self):
        """search_bm25 модуль импортируется."""
        from src.services.search_bm25 import search_auto, detect_index_version

        assert callable(search_auto)
        assert callable(detect_index_version)


# ============================================================================
# 3. BSL analysis: standards
# ============================================================================


class TestSmokeBSLAnalysis:
    """Smoke: BSL анализ."""

    def test_check_standards_on_test_file(self, tmp_path):
        """check_1c_standards работает на тестовом .bsl файле."""
        from src.services.analyzers.check_1c_standards import StandardsChecker

        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text(
            "#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            encoding="utf-8",
        )

        checker = StandardsChecker()
        violations = checker.check_file(bsl_file)
        assert isinstance(violations, list)

    def test_security_auditor_on_test_file(self, tmp_path):
        """security_auditor работает на тестовом .bsl файле."""
        from src.services.analyzers.security_auditor import SecurityAuditor

        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text(
            "Процедура Тест()\nКонецПроцедуры\n",
            encoding="utf-8",
        )

        auditor = SecurityAuditor()
        violations = auditor.audit_file(bsl_file)
        assert isinstance(violations, list)


# ============================================================================
# 4. DSL: compile meta
# ============================================================================


class TestSmokeDSL:
    """Smoke: DSL компиляторы."""

    def test_dsl_meta_compiles(self, tmp_path):
        """MetaCompiler компилирует минимальный JSON в XML."""
        from src.dsl.meta import MetaCompiler

        spec = {
            "type": "Catalog",
            "name": "ТестовыйСправочник",
            "synonym": "Тестовый справочник",
        }
        compiler = MetaCompiler()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        result = compiler.compile(spec, output_dir)
        assert result.object_type == "Catalog"
        assert result.object_name == "ТестовыйСправочник"
        assert result.xml_path.exists()


# ============================================================================
# 5. EPF: factory
# ============================================================================


class TestSmokeEPF:
    """Smoke: EPF factory."""

    def test_epf_factory_list_templates(self):
        """EpfFactory.list_templates возвращает dict."""
        from src.services.epf_factory import EpfFactory

        templates = EpfFactory.list_templates()
        assert isinstance(templates, dict)
        assert "ext_proc" in templates
        assert "form" in templates


# ============================================================================
# 6. MCP: list_tools
# ============================================================================


class TestSmokeMCP:
    """Smoke: MCP server."""

    def test_mcp_tools_count(self):
        """MCP tools definitions содержат ожидаемое количество tools."""
        from src.mcpserver.tools.tool_definitions import get_all_tool_definitions

        tools = get_all_tool_definitions()
        assert len(tools) == 45  # 45 MCP tools


# ============================================================================
# 7. Diff: compare_data
# ============================================================================


class TestSmokeDiff:
    """Smoke: Diff analyzer."""

    def test_diff_compare_data(self):
        """DiffAnalyzer.compare_data на двух простых индексах."""
        from src.services.diff import DiffAnalyzer

        old = {
            "objects": {"Catalogs": [{"name": "Кат1", "synonym": "Старый"}]},
            "roles": [],
            "subsystems": [],
            "event_subscriptions": [],
            "scheduled_jobs": [],
        }
        new = {
            "objects": {
                "Catalogs": [
                    {"name": "Кат1", "synonym": "Новый"},
                    {"name": "Кат2", "synonym": "Новый"},
                ]
            },
            "roles": [],
            "subsystems": [],
            "event_subscriptions": [],
            "scheduled_jobs": [],
        }

        analyzer = DiffAnalyzer()
        diff = analyzer.compare_data(old, new)
        assert len(diff.added_objects) == 1  # Кат2
        assert len(diff.modified_objects) == 1  # Кат1 (synonym changed)
        assert diff.summary["total_added"] == 1
        assert diff.summary["total_modified"] == 1


# ============================================================================
# 8. PathManager
# ============================================================================


class TestSmokePathManager:
    """Smoke: PathManager."""

    def test_path_manager_root(self):
        """PathManager определяет корень проекта."""
        from src.services.path_manager import PathManager

        pm = PathManager()
        assert pm.root.exists()
        assert (pm.root / "src").exists()


# ============================================================================
# 9. CFE: result dataclasses
# ============================================================================


class TestSmokeCFE:
    """Smoke: CFE result dataclasses."""

    def test_borrow_result_creation(self):
        """BorrowResult создаётся с правильными полями."""
        from src.services.cfe.result import BorrowResult

        result = BorrowResult(
            object_ref="Catalog.Тест",
            object_type="Catalog",
            object_name="Тест",
        )
        assert result.object_ref == "Catalog.Тест"
        assert result.xml_created == []
        assert result.registered_in_config is False


# ============================================================================
# 10. Standards: ALL_RULES count
# ============================================================================


class TestSmokeStandards:
    """Smoke: Standards package."""

    def test_all_rules_count(self):
        """ALL_RULES содержит 56 правил."""
        from src.services.analyzers.standards import ALL_RULES

        assert len(ALL_RULES) == 56
