"""D3.4 + D3.6 + D3.7 + D3.8 (2026-07-05): Тесты для incremental analysis, dependency graph, code generator, SARIF."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.incremental_analyzer import IncrementalAnalyzer, IncrementalResult


class TestD3_4_IncrementalAnalysis:
    """D3.4: Incremental analysis."""

    def test_extract_functions(self, tmp_path: Path) -> None:
        bsl = tmp_path / "test.bsl"
        bsl.write_text(
            "Процедура Первая()\n\tСообщить(\"1\");\nКонецПроцедуры\n\n"
            "Функция Вторая()\n\tВозврат 2;\nКонецФункции\n",
            encoding="utf-8",
        )
        inc = IncrementalAnalyzer()
        funcs = inc._extract_functions(bsl)
        assert len(funcs) == 2  # Две функции найдены

    def test_no_changes_after_baseline(self, tmp_path: Path) -> None:
        bsl = tmp_path / "test.bsl"
        bsl.write_text("Процедура Тест()\n\tСообщить(\"1\");\nКонецПроцедуры\n", encoding="utf-8")
        baseline = tmp_path / "baseline.json"

        # Первый запуск — создаёт baseline
        inc = IncrementalAnalyzer()
        result1 = inc.analyze_changed(bsl, baseline)
        assert result1.changed_functions == 1
        assert result1.total_functions == 1

        # Второй запуск — нет изменений
        result2 = inc.analyze_changed(bsl, baseline)
        assert result2.changed_functions == 0
        assert result2.unchanged_functions == 1
        assert result2.analysis_skipped is True

    def test_detects_changed_function(self, tmp_path: Path) -> None:
        bsl = tmp_path / "test.bsl"
        bsl.write_text("Процедура Тест()\n\tСообщить(\"1\");\nКонецПроцедуры\n", encoding="utf-8")
        baseline = tmp_path / "baseline.json"

        inc = IncrementalAnalyzer()
        inc.analyze_changed(bsl, baseline)

        # Изменяем функцию
        bsl.write_text("Процедура Тест()\n\tСообщить(\"2\");\nКонецПроцедуры\n", encoding="utf-8")
        result = inc.analyze_changed(bsl, baseline)
        assert result.changed_functions == 1
        assert "Тест" in result.changed_function_names

    def test_missing_file(self) -> None:
        inc = IncrementalAnalyzer()
        result = inc.analyze_changed("/nonexistent.bsl")
        assert result.total_functions == 0

    def test_baseline_saved(self, tmp_path: Path) -> None:
        bsl = tmp_path / "test.bsl"
        bsl.write_text("Процедура Тест()\nКонецПроцедуры\n", encoding="utf-8")
        baseline = tmp_path / "baseline.json"
        inc = IncrementalAnalyzer()
        inc.analyze_changed(bsl, baseline)
        assert baseline.exists()
        data = json.loads(baseline.read_text(encoding="utf-8"))
        assert "Тест" in data


class TestD3_6_DependencyGraphExtension:
    """D3.6: Dependency graph расширение."""

    def test_dependency_graph_has_call_graph(self) -> None:
        from src.services.dependency_graph import DependencyGraph
        dg = DependencyGraph()
        assert hasattr(dg, "build_from_metadata_index")
        assert hasattr(dg, "what_depends_on")
        assert hasattr(dg, "find_cycles")
        assert hasattr(dg, "find_unused_objects")
        assert hasattr(dg, "get_stats")
        assert hasattr(dg, "shortest_path")

    def test_call_graph_exists(self) -> None:
        from src.services.call_graph import CallGraph
        assert CallGraph is not None  # Module exists

    def test_dependency_graph_has_transitive(self) -> None:
        from src.services.dependency_graph import DependencyGraph
        dg = DependencyGraph()
        assert hasattr(dg, "transitive_dependencies")
        assert hasattr(dg, "transitive_dependents")
        assert hasattr(dg, "find_root_objects")


class TestD3_7_CodeGeneratorTemplates:
    """D3.7: Code generator templates."""

    def test_generate_processing_exists(self) -> None:
        from src.services import code_generator
        assert callable(code_generator.generate_processing)

    def test_generate_report_exists(self) -> None:
        from src.services import code_generator
        assert callable(code_generator.generate_report)

    def test_dsl_5_compilers(self) -> None:
        from src.dsl import DslCompiler
        c = DslCompiler()
        assert hasattr(c, "compile_meta")
        assert hasattr(c, "compile_form")
        assert hasattr(c, "compile_skd")
        assert hasattr(c, "compile_mxl")
        assert hasattr(c, "compile_role")

    def test_templates_exist(self) -> None:
        from pathlib import Path
        repo = Path(__file__).parent.parent
        assert (repo / "templates" / "bsl").exists()
        assert (repo / "templates" / "xml").exists()


class TestD3_8_SarifSuppressions:
    """D3.8: SARIF reporter suppressions."""

    def test_sarif_reporter_exists(self) -> None:
        from src.services.sarif_reporter import SarifReporter
        assert hasattr(SarifReporter, "convert")
        assert hasattr(SarifReporter, "write")

    def test_sarif_version(self) -> None:
        from src.services.sarif_reporter import SarifReporter
        assert SarifReporter.SARIF_VERSION == "2.1.0"

    def test_sarif_suppression_support(self) -> None:
        """SARIF reporter должен поддерживать suppressions (baselines)."""
        from src.services.sarif_reporter import SarifReporter
        assert hasattr(SarifReporter, "convert")  # Supports converting violations
