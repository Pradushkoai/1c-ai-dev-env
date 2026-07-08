"""
Тесты для P2.12: ABC Analyzer protocol в TaskProcessor.

До фикса: TaskProcessor.check() содержал 7 if-блоков — добавление нового
analyzer'а требовало модификации check() (нарушение OCP).

После фикса: введён Analyzer Protocol с методом check_file().
TaskProcessor.check_via_analyzers() использует список analyzer'ов.
Новые analyzer'ы добавляются через регистрацию, без модификации метода.

Существующий check() сохранён для обратной совместимости.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.analyzers import (
    Analyzer,
    AnalyzerViolation,
    CodeMetricsAdapter,
    MetadataStandardsAdapter,
    QueryAnalyzerAdapter,
    SecurityAuditorAdapter,
    StandardsCheckerAdapter,
    TransactionCheckerAdapter,
    _level_allows,
    get_default_analyzers,
    get_registered_analyzers,
    register_analyzer,
    run_analyzers,
)
from src.services.path_manager import PathManager


# ============================================================================
# Helpers
# ============================================================================


def _make_fake_violations_module(module_name: str, attr_name: str, violations: list):
    """Создать фейковый модуль-анализатор."""
    mod = types.ModuleType(module_name)

    class FakeViolation:
        def __init__(self, rule_id, severity, line, message, file=""):
            self.rule_id = rule_id
            self.severity = severity
            self.line = line
            self.message = message
            self.file = file

    class FakeChecker:
        def check_file(self, path):
            return violations

        def audit_file(self, path):
            return violations

        def analyze_file(self, path):
            return violations

        def check_path(self, path):
            return violations

    mod.FakeViolation = FakeViolation
    setattr(mod, attr_name, FakeChecker)
    sys.modules[module_name] = mod
    return mod


@pytest.fixture
def fake_analyzer_modules():
    """Загружает фейковые модули для всех 6 analyzer'ов."""
    sample_v = [
        type(
            "V",
            (),
            {
                "rule_id": "TEST_R1",
                "severity": "error",
                "line": 1,
                "message": "test violation",
                "file": "",
            },
        )()
    ]
    _make_fake_violations_module("check_1c_standards", "StandardsChecker", sample_v)
    _make_fake_violations_module("security_auditor", "SecurityAuditor", sample_v)
    _make_fake_violations_module("transaction_checker", "TransactionChecker", sample_v)
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", sample_v)
    _make_fake_violations_module("code_metrics", "CodeMetricsAnalyzer", sample_v)
    _make_fake_violations_module("check_metadata_standards", "MetadataStandardsChecker", sample_v)
    yield
    # Cleanup
    for name in (
        "check_1c_standards",
        "security_auditor",
        "transaction_checker",
        "query_analyzer",
        "code_metrics",
        "check_metadata_standards",
    ):
        sys.modules.pop(name, None)


# ============================================================================
# Тесты — Protocol
# ============================================================================


class TestAnalyzerProtocol:
    """Analyzer Protocol — структура и контракты."""

    def test_analyzer_is_protocol(self) -> None:
        """Analyzer должен быть runtime_checkable Protocol."""
        assert hasattr(Analyzer, "_is_protocol")
        # runtime_checkable decorator добавляет __instancecheck__
        assert hasattr(Analyzer, "__instancecheck__")

    def test_analyzer_violation_has_source_field(self) -> None:
        """AnalyzerViolation должен иметь поле source."""
        v = AnalyzerViolation(rule_id="R1", severity="error", line=1, message="test")
        assert v.source == ""  # default
        v.source = "security_auditor"
        assert v.source == "security_auditor"


# ============================================================================
# Тесты — level hierarchy
# ============================================================================


class TestLevelAllows:
    """_level_allows проверяет, должен ли analyzer запуститься на данном level."""

    def test_quick_analyzer_runs_on_all_levels(self) -> None:
        """min_level='quick' → запускается на quick/standard/full."""
        assert _level_allows("quick", "quick") is True
        assert _level_allows("standard", "quick") is True
        assert _level_allows("full", "quick") is True

    def test_standard_analyzer_skips_quick(self) -> None:
        """min_level='standard' → НЕ запускается на quick."""
        assert _level_allows("quick", "standard") is False
        assert _level_allows("standard", "standard") is True
        assert _level_allows("full", "standard") is True

    def test_full_analyzer_only_on_full(self) -> None:
        """min_level='full' → запускается только на full."""
        assert _level_allows("quick", "full") is False
        assert _level_allows("standard", "full") is False
        assert _level_allows("full", "full") is True


# ============================================================================
# Тесты — adapters
# ============================================================================


class TestAdapters:
    """Каждый adapter должен корректно загружать analyzer и вызывать метод."""

    def test_standards_checker_adapter(self, fake_analyzer_modules) -> None:
        """StandardsCheckerAdapter загружает check_1c_standards.StandardsChecker."""
        pm = PathManager()
        adapter = StandardsCheckerAdapter(pm)
        assert adapter.source == "check_1c_standards"
        assert adapter.min_level == "quick"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1
        assert violations[0].rule_id == "TEST_R1"

    def test_security_auditor_adapter(self, fake_analyzer_modules) -> None:
        """SecurityAuditorAdapter загружает security_auditor.SecurityAuditor."""
        pm = PathManager()
        adapter = SecurityAuditorAdapter(pm)
        assert adapter.source == "security_auditor"
        assert adapter.min_level == "quick"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1

    def test_transaction_checker_adapter(self, fake_analyzer_modules) -> None:
        pm = PathManager()
        adapter = TransactionCheckerAdapter(pm)
        assert adapter.source == "transaction_checker"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1

    def test_query_analyzer_adapter(self, fake_analyzer_modules) -> None:
        pm = PathManager()
        adapter = QueryAnalyzerAdapter(pm)
        assert adapter.source == "query_analyzer"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1

    def test_code_metrics_adapter(self, fake_analyzer_modules) -> None:
        pm = PathManager()
        adapter = CodeMetricsAdapter(pm)
        assert adapter.source == "code_metrics"
        assert adapter.min_level == "full"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1

    def test_metadata_standards_adapter(self, fake_analyzer_modules) -> None:
        pm = PathManager()
        adapter = MetadataStandardsAdapter(pm)
        assert adapter.source == "check_metadata_standards"
        assert adapter.min_level == "full"

        violations = adapter.check_file(Path("/fake.bsl"))
        assert len(violations) == 1


# ============================================================================
# Тесты — registry
# ============================================================================


class TestRegistry:
    """get_default_analyzers возвращает 7 analyzer'ов (B6: +bsl_context_checker)."""

    def test_returns_6_analyzers(self) -> None:
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        assert len(analyzers) == 7  # B6: +bsl_context_checker

    def test_analyzer_names_unique(self) -> None:
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        names = [a.source for a in analyzers]
        assert len(names) == len(set(names)), "Analyzer names must be unique"

    def test_quick_analyzers_first(self) -> None:
        """quick-level analyzer'ы идут раньше full-level."""
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        # Первые 4 — quick, 5-й — standard (bsl_context_checker), последние 2 — full
        for a in analyzers[:4]:
            assert a.min_level == "quick"
        # 5-й — standard (bsl_context_checker, B6)
        assert analyzers[4].min_level == "standard"
        # Последние 2 — full
        for a in analyzers[5:]:
            assert a.min_level == "full"


# ============================================================================
# Тесты — run_analyzers
# ============================================================================


class TestRunAnalyzers:
    """run_analyzers — оркестрация запуска analyzer'ов."""

    def test_quick_level_runs_only_quick_analyzers(self, fake_analyzer_modules) -> None:
        """level='quick' запускает только 4 quick analyzer'а (не full)."""
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        violations, analyzers_run = run_analyzers(analyzers, Path("/fake.bsl"), level="quick")
        assert set(analyzers_run) == {
            "check_1c_standards",
            "security_auditor",
            "transaction_checker",
            "query_analyzer",
        }
        assert "code_metrics" not in analyzers_run
        assert "check_metadata_standards" not in analyzers_run
        # 4 analyzer'а × 1 violation = 4 violations
        assert len(violations) == 4

    def test_full_level_runs_all_6_analyzers(self, fake_analyzer_modules) -> None:
        """level='full' запускает все 7 analyzer'ов (B6: +bsl_context_checker).

        bsl_context_checker запускается, но может не найти нарушений
        на фейковом файле (нет BSL-кода для анализа). Поэтому
        проверяем только количество запущенных analyzer'ов.
        """
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        violations, analyzers_run = run_analyzers(analyzers, Path("/fake.bsl"), level="full")
        assert len(analyzers_run) == 7  # B6: +bsl_context_checker
        # bsl_context_checker может не найти нарушений на фейковом файле
        assert len(violations) >= 6  # минимум 6 (без bsl_context_checker)

    def test_violations_have_source_set(self, fake_analyzer_modules) -> None:
        """Каждое нарушение должно иметь заполненное поле source."""
        pm = PathManager()
        analyzers = get_default_analyzers(pm)
        violations, _ = run_analyzers(analyzers, Path("/fake.bsl"), level="quick")
        for v in violations:
            assert v.source, f"Violation {v.rule_id} has empty source"
            assert v.source in {
                "check_1c_standards",
                "security_auditor",
                "transaction_checker",
                "query_analyzer",
            }

    def test_analyzer_exception_doesnt_crash_run(self) -> None:
        """Если analyzer падает, run_analyzers продолжает с другими."""

        # Создаём analyzer, который падает
        class CrashingAnalyzer:
            source = "crashing"
            min_level = "quick"

            def check_file(self, file_path: Path) -> list:
                raise RuntimeError("boom")

        # И нормальный analyzer
        class GoodAnalyzer:
            source = "good"
            min_level = "quick"

            def check_file(self, file_path: Path) -> list:
                return [
                    AnalyzerViolation(
                        rule_id="OK",
                        severity="info",
                        line=1,
                        message="ok",
                    )
                ]

        violations, analyzers_run = run_analyzers(
            [CrashingAnalyzer(), GoodAnalyzer()], Path("/fake.bsl"), level="quick"
        )
        # Crashing analyzer не должен быть в analyzers_run
        assert "crashing" not in analyzers_run
        # Good analyzer должен отработать
        assert "good" in analyzers_run
        assert len(violations) == 1
        assert violations[0].source == "good"


# ============================================================================
# Тесты — TaskProcessor.check_via_analyzers
# ============================================================================


class TestCheckViaAnalyzers:
    """Новый API TaskProcessor.check_via_analyzers()."""

    def test_method_exists(self) -> None:
        from src.services.task_processor import TaskProcessor

        pm = PathManager()
        tp = TaskProcessor(pm)
        assert hasattr(tp, "check_via_analyzers")
        assert callable(tp.check_via_analyzers)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """check_via_analyzers на несуществующий файл → FileNotFoundError."""
        from src.services.task_processor import TaskProcessor

        pm = PathManager()
        tp = TaskProcessor(pm)
        with pytest.raises(FileNotFoundError):
            tp.check_via_analyzers(tmp_path / "missing.bsl", level="quick")

    def test_returns_check_result(self, fake_analyzer_modules, tmp_path: Path) -> None:
        """Должен вернуть CheckResult с violations и analyzers_run."""
        from src.services.task_processor import CheckResult, TaskProcessor

        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

        pm = PathManager()
        tp = TaskProcessor(pm)
        result = tp.check_via_analyzers(bsl_file, level="quick")

        assert isinstance(result, CheckResult)
        assert result.level == "quick"
        # 4 quick analyzer'а должны быть запущены
        assert "check_1c_standards" in result.analyzers_run
        assert "security_auditor" in result.analyzers_run
        assert "transaction_checker" in result.analyzers_run
        assert "query_analyzer" in result.analyzers_run
        # full-level НЕ запускаются
        assert "code_metrics" not in result.analyzers_run
        assert "check_metadata_standards" not in result.analyzers_run
        # 4 violations (по 1 от каждого analyzer)
        assert len(result.violations) == 4
        # Каждое нарушение должно иметь source
        for v in result.violations:
            assert v.source, "Violation must have source set"


# ============================================================================
# Тесты — OCP: регистрация custom analyzer
# ============================================================================


class TestCustomAnalyzerRegistration:
    """Custom analyzer'ы можно регистрировать без модификации TaskProcessor."""

    def test_register_analyzer(self) -> None:
        """register_analyzer добавляет analyzer в реестр."""

        class MyCustomAnalyzer:
            source = "my_custom"
            min_level = "quick"

            def check_file(self, file_path: Path) -> list:
                return []

        # Очистка перед тестом
        registry = get_registered_analyzers()
        if "my_custom" in registry:
            del registry["my_custom"]

        register_analyzer("my_custom", MyCustomAnalyzer)
        assert "my_custom" in get_registered_analyzers()

    def test_register_duplicate_raises(self) -> None:
        """Повторная регистрация того же имени → ValueError."""

        class A1:
            source = "dup"
            min_level = "quick"

            def check_file(self, p):
                return []

        class A2:
            source = "dup"
            min_level = "quick"

            def check_file(self, p):
                return []

        # Очистка
        registry = get_registered_analyzers()
        if "dup" in registry:
            del registry["dup"]

        register_analyzer("dup", A1)
        with pytest.raises(ValueError, match="already registered"):
            register_analyzer("dup", A2)
