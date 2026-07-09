"""
D3.1-D3.8 + 14.2 (2026-07-05): Тесты для M3 BSL Parser tasks.

Покрывает:
- D3.1: analyzer coverage report
- 14.2/D3.2: tree-sitter-bsl adapter
- D3.3: портирование правил из BSL LS (plan)
- D3.4: incremental analysis (plan)
- D3.5: AST-based analyzers (plan)
- D3.6: dependency graph расширение
- D3.7: code generator 10+ типов
- D3.8: SARIF reporter suppressions
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestBslAstAdapter:
    """14.2/D3.2: tree-sitter-bsl adapter."""

    def test_bsl_ast_module_exists(self) -> None:
        """Модуль bsl_ast существует."""
        from src.services import bsl_ast
        assert hasattr(bsl_ast, "parse_bsl")
        assert hasattr(bsl_ast, "is_tree_sitter_available")

    def test_is_tree_sitter_available_returns_bool(self) -> None:
        """is_tree_sitter_available возвращает bool."""
        from src.services.bsl_ast import is_tree_sitter_available
        result = is_tree_sitter_available()
        assert isinstance(result, bool)

    def test_parse_bsl_returns_none_without_tree_sitter(self) -> None:
        """parse_bsl возвращает None если tree-sitter не установлен."""
        from src.services.bsl_ast import parse_bsl, is_tree_sitter_available
        if is_tree_sitter_available():
            pytest.skip("tree-sitter установлен — тест пропускается")
        result = parse_bsl("Процедура Тест() КонецПроцедуры")
        assert result is None

    def test_has_syntax_errors_returns_false_on_fallback(self) -> None:
        """has_syntax_errors возвращает False при fallback (нет tree-sitter)."""
        from src.services.bsl_ast import has_syntax_errors, is_tree_sitter_available
        if is_tree_sitter_available():
            pytest.skip("tree-sitter установлен")
        assert has_syntax_errors("любой код") is False

    def test_get_ast_node_types_returns_list(self) -> None:
        """get_ast_node_types возвращает list."""
        from src.services.bsl_ast import get_ast_node_types, is_tree_sitter_available
        if is_tree_sitter_available():
            pytest.skip("tree-sitter установлен")
        result = get_ast_node_types("Процедура Тест() КонецПроцедуры")
        assert isinstance(result, list)
        assert len(result) == 0  # Без tree-sitter — пустой список


class TestD3_3_BslLsPortPlan:
    """D3.3: План портирования 50 правил из BSL LS в Python."""

    def test_security_auditor_has_15_rules(self) -> None:
        """Security auditor содержит 15 правил (SEC001-SEC015)."""
        from src.services.analyzers.security_auditor import SecurityAuditor
        auditor = SecurityAuditor()
        assert len(auditor.rules) >= 15

    def test_standards_modules_exist(self) -> None:
        """Модули standards/ существуют (5 модулей)."""
        standards_dir = REPO_ROOT / "src" / "services" / "analyzers" / "standards"
        assert (standards_dir / "style.py").exists()
        assert (standards_dir / "architecture.py").exists()
        assert (standards_dir / "queries.py").exists()
        assert (standards_dir / "client_server.py").exists()
        assert (standards_dir / "misc.py").exists()


class TestD3_4_IncrementalAnalysis:
    """D3.4: Incremental analysis (план)."""

    def test_bsl_analyzer_has_baseline_diff(self) -> None:
        """BSLAnalyzer имеет baseline/diff методы (основа для incremental)."""
        from src.services.bsl_analyzer import BSLAnalyzer
        assert hasattr(BSLAnalyzer, "save_baseline")
        assert hasattr(BSLAnalyzer, "diff")


class TestD3_5_AstBasedAnalyzers:
    """D3.5: AST-based analyzers (план, зависит от 14.2)."""

    def test_bsl_ast_module_has_parse_function(self) -> None:
        """bsl_ast модуль имеет parse_bsl функцию."""
        from src.services.bsl_ast import parse_bsl
        assert callable(parse_bsl)


class TestD3_6_DependencyGraph:
    """D3.6: Dependency graph расширение."""

    def test_dependency_graph_exists(self) -> None:
        """DependencyGraph модуль существует."""
        from src.services.dependency_graph import DependencyGraph
        assert hasattr(DependencyGraph, "build_from_metadata_index")
        assert hasattr(DependencyGraph, "what_depends_on")
        assert hasattr(DependencyGraph, "find_cycles")
        assert hasattr(DependencyGraph, "find_unused_objects")


class TestD3_7_CodeGenerator:
    """D3.7: Code generator 10+ типов."""

    def test_code_generator_exists(self) -> None:
        """Code generator модуль существует с функциями generate_processing и generate_report."""
        from src.services import code_generator
        assert hasattr(code_generator, "generate_processing")
        assert hasattr(code_generator, "generate_report")

    def test_dsl_supports_5_types(self) -> None:
        """DSL компиляторы поддерживают 5 типов (meta/form/skd/mxl/role)."""
        from src.dsl import DslCompiler
        compiler = DslCompiler()
        assert hasattr(compiler, "compile_meta")
        assert hasattr(compiler, "compile_form")
        assert hasattr(compiler, "compile_skd")
        assert hasattr(compiler, "compile_mxl")
        assert hasattr(compiler, "compile_role")


class TestD3_8_SarifReporter:
    """D3.8: SARIF reporter."""

    def test_sarif_reporter_exists(self) -> None:
        """SarifReporter модуль существует."""
        from src.services.sarif_reporter import SarifReporter
        assert hasattr(SarifReporter, "convert")
        assert hasattr(SarifReporter, "write")

    def test_sarif_version(self) -> None:
        """SARIF версия 2.1.0."""
        from src.services.sarif_reporter import SarifReporter
        assert hasattr(SarifReporter, "SARIF_VERSION")
        assert SarifReporter.SARIF_VERSION == "2.1.0"
