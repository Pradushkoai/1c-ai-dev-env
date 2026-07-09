"""
Тесты для TaskProcessor — единого пайплайна решения задач.

Все внешние зависимости (BSL LS, скрипты) замоканы.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.task import CheckResult, TaskContext, Violation
from src.services.path_manager import PathManager
from src.services.task_processor import TaskProcessor

# Модули, которые тесты кладут в sys.modules — нужно чистить между прогонами
_ANALYZER_MODULES = (
    "check_1c_standards",
    "security_auditor",
    "transaction_checker",
    "query_analyzer",
    "code_metrics",
    "check_metadata_standards",
)


@pytest.fixture(autouse=True)
def _clean_sys_modules():
    """Очистить sys.modules от замоканных analyzer-модулей после каждого теста."""
    saved = {name: sys.modules.get(name) for name in _ANALYZER_MODULES}
    yield
    for name in _ANALYZER_MODULES:
        if saved[name] is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved[name]


@pytest.fixture
def setup(tmp_path):
    """PathManager + минимальная структура."""
    for d in ["data/configs", "data/archives", "derived/configs", "runtime"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    pm = PathManager(project_root=tmp_path)
    return pm, tmp_path


# ─────────────────────────────────────────────
# SOLVE: сбор контекста
# ─────────────────────────────────────────────


def test_solve_no_config_no_indexes(setup):
    """solve() без config и без индексов → TaskContext с missing_sources."""
    pm, tmp = setup
    processor = TaskProcessor(pm)

    ctx = processor.solve("создать справочник", config_name="", limit=5)

    assert isinstance(ctx, TaskContext)
    assert ctx.query == "создать справочник"
    assert ctx.config_name == ""
    # Хотя бы один missing source (platform_methods)
    assert len(ctx.missing_sources) >= 1
    assert any("platform_methods" in m for m in ctx.missing_sources)
    # Стандарты всегда есть
    assert "total_checks" in ctx.standards_summary
    # T12: dynamic counts — 187+62+18+20+6+10+10 = 313 проверок
    assert ctx.standards_summary["total_checks"] == 313


def test_solve_with_config_but_no_indexes(setup):
    """solve() с config, но без индексов → все 4 источника в missing_sources."""
    pm, tmp = setup
    # Создаём конфигурацию в реестре — но без индексов
    cfg_dir = tmp / "data" / "configs" / "ut11"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name="ut11", limit=5)

    assert ctx.config_name == "ut11"
    # Все 4 источника должны быть в missing
    missing_str = " ".join(ctx.missing_sources)
    assert "api_reference" in missing_str
    assert "metadata" in missing_str
    assert "skd" in missing_str
    assert "forms" in missing_str


def test_solve_finds_api_modules(setup):
    """solve() находит релевантные модули в api-reference.json."""
    pm, tmp = setup
    config_name = "ut11"

    # Создаём api-reference.json с двумя модулями
    api_json = pm.config_api_reference_json(config_name)
    api_json.parent.mkdir(parents=True, exist_ok=True)
    api_json.write_text(
        json.dumps(
            [
                {
                    "name": "ТоварыМодуль",
                    "methods_count": 5,
                    "methods": [
                        {"name": "НайтиТовар", "params": []},
                        {"name": "ДобавитьТовар", "params": []},
                    ],
                },
                {
                    "name": "ЗаказыМодуль",
                    "methods_count": 3,
                    "methods": [],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name=config_name, limit=5)

    assert len(ctx.api_modules) == 1
    assert ctx.api_modules[0].name == "ТоварыМодуль"
    assert ctx.api_modules[0].methods_count == 5


def test_solve_finds_metadata_objects(setup):
    """solve() находит объекты в unified-metadata-index.json."""
    pm, tmp = setup
    config_name = "ut11"

    unified_path = tmp / "derived" / "configs" / config_name / "unified-metadata-index.json"
    unified_path.parent.mkdir(parents=True, exist_ok=True)
    unified_path.write_text(
        json.dumps(
            {
                "objects": {
                    "Catalogs": [
                        {
                            "type": "Catalog",
                            "name": "Товары",
                            "synonym": "Номенклатура",
                            "child_objects": {
                                "attributes": [{"name": "Артикул"}],
                                "tabular_sections": [{"name": "Характеристики"}],
                                "forms": [{"name": "ФормаСписка"}],
                            },
                        },
                        {
                            "type": "Catalog",
                            "name": "Контрагенты",
                            "synonym": "Покупатели",
                            "child_objects": {},
                        },
                    ]
                },
                "subsystems": [],
                "event_subscriptions": [],
                "scheduled_jobs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name=config_name, limit=5)

    assert len(ctx.metadata_objects) == 1
    obj = ctx.metadata_objects[0]
    assert obj.name == "Товары"
    assert obj.attributes_count == 1
    assert obj.tabular_sections_count == 1
    assert obj.forms_count == 1


def test_solve_finds_skd_schemas(setup):
    """solve() находит СКД-схемы."""
    pm, tmp = setup
    config_name = "ut11"
    skd_path = tmp / "derived" / "configs" / config_name / "skd-index.json"
    skd_path.parent.mkdir(parents=True, exist_ok=True)
    skd_path.write_text(
        json.dumps(
            {
                "schemas": [
                    {
                        "parent_type": "Report",
                        "parent_name": "ОтчётПоТовары",
                        "name": "ОсновнаяСхема",
                        "schema": {
                            "data_sets": [{"name": "ds1"}],
                            "parameters": [{"name": "p1"}],
                        },
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name=config_name, limit=5)

    assert len(ctx.skd_schemas) == 1
    assert ctx.skd_schemas[0].parent_name == "ОтчётПоТовары"
    assert ctx.skd_schemas[0].data_sets_count == 1
    assert ctx.skd_schemas[0].parameters_count == 1


def test_solve_finds_forms(setup):
    """solve() находит формы."""
    pm, tmp = setup
    config_name = "ut11"
    form_path = tmp / "derived" / "configs" / config_name / "form-index.json"
    form_path.parent.mkdir(parents=True, exist_ok=True)
    form_path.write_text(
        json.dumps(
            {
                "forms": [
                    {
                        "parent_type": "Catalog",
                        "parent_name": "Товары",
                        "name": "ФормаСписка",
                        "form": {"element_count": 42},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name=config_name, limit=5)

    assert len(ctx.forms) == 1
    assert ctx.forms[0].name == "ФормаСписка"
    assert ctx.forms[0].element_count == 42


def test_solve_to_dict_serializable(setup):
    """to_dict() возвращает JSON-сериализуемый dict."""
    pm, tmp = setup
    processor = TaskProcessor(pm)
    ctx = processor.solve("тест", config_name="", limit=5)

    d = ctx.to_dict()
    # Должно быть сериализуемо
    json.dumps(d, ensure_ascii=False)

    assert d["query"] == "тест"
    assert "standards_summary" in d
    assert "missing_sources" in d


def test_solve_total_hits(setup):
    """total_hits правильно считает количество находок."""
    pm, tmp = setup
    config_name = "ut11"

    api_json = pm.config_api_reference_json(config_name)
    api_json.parent.mkdir(parents=True, exist_ok=True)
    api_json.write_text(
        json.dumps(
            [
                {"name": "ТоварыМодуль", "methods_count": 1, "methods": []},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    processor = TaskProcessor(pm)
    ctx = processor.solve("товары", config_name=config_name, limit=5)

    assert ctx.total_hits >= 1


# ─────────────────────────────────────────────
# CHECK: запуск анализаторов
# ─────────────────────────────────────────────


def test_check_file_not_found(setup):
    """check() на несуществующий файл → FileNotFoundError."""
    pm, tmp = setup
    processor = TaskProcessor(pm)

    with pytest.raises(FileNotFoundError):
        processor.check(tmp / "missing.bsl", level="quick")


def _make_fake_violations_module(module_name: str, attr_name: str, violations: list):
    """Создать фейковый модуль-анализатор и положить его в sys.modules."""
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

    mod.FakeViolation = FakeViolation
    setattr(mod, attr_name, FakeChecker)
    sys.modules[module_name] = mod
    return mod


def test_check_quick_level_runs_4_analyzers(setup):
    """check(level='quick') запускает 4 анализатора (без BSL LS)."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    # Мокаем все 4 analyzer-модуля
    sample_v = [type("V", (), {"rule_id": "R1", "severity": "error", "line": 1, "message": "test", "file": ""})()]
    _make_fake_violations_module("check_1c_standards", "StandardsChecker", sample_v)
    _make_fake_violations_module("security_auditor", "SecurityAuditor", sample_v)
    _make_fake_violations_module("transaction_checker", "TransactionChecker", sample_v)
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", sample_v)

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="quick")

    assert isinstance(result, CheckResult)
    assert result.level == "quick"
    assert "check_1c_standards" in result.analyzers_run
    assert "security_auditor" in result.analyzers_run
    assert "transaction_checker" in result.analyzers_run
    assert "query_analyzer" in result.analyzers_run
    # BSL LS не запускается на quick
    assert "bsl_ls" not in result.analyzers_run
    assert result.bsl_ls_available is False
    # 4 violation-а (по одному от каждого analyzer)
    assert len(result.violations) == 4
    assert result.total_errors == 4


def test_check_to_dict_roundtrip(setup):
    """to_dict() возвращает JSON-сериализуемый dict."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    sample_v = [type("V", (), {"rule_id": "R1", "severity": "warning", "line": 1, "message": "w", "file": ""})()]
    _make_fake_violations_module("check_1c_standards", "StandardsChecker", sample_v)
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="quick")

    d = result.to_dict()
    json.dumps(d, ensure_ascii=False)  # не должно выбросить

    assert d["level"] == "quick"
    assert d["verdict"] == "warnings"  # 1 warning, 0 errors
    assert d["total_warnings"] == 1
    assert d["total_errors"] == 0


def test_check_verdict_ready(setup):
    """verdict='ready' когда нет нарушений."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="quick")

    assert result.verdict == "ready"
    assert result.total_errors == 0
    assert result.total_warnings == 0


def test_check_verdict_errors(setup):
    """verdict='errors' когда есть error."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуру", encoding="utf-8")

    sample_v = [
        type("V", (), {"rule_id": "R1", "severity": "error", "line": 1, "message": "e", "file": ""})(),
        type("V", (), {"rule_id": "R2", "severity": "warning", "line": 2, "message": "w", "file": ""})(),
    ]
    _make_fake_violations_module("check_1c_standards", "StandardsChecker", sample_v)
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="quick")

    assert result.verdict == "errors"
    assert result.total_errors == 1
    assert result.total_warnings == 1


def test_check_violation_source_tracking(setup):
    """violations правильно атрибутируются по source."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    _make_fake_violations_module(
        "check_1c_standards",
        "StandardsChecker",
        [type("V", (), {"rule_id": "STD1", "severity": "error", "line": 1, "message": "m", "file": ""})()],
    )
    _make_fake_violations_module(
        "security_auditor",
        "SecurityAuditor",
        [type("V", (), {"rule_id": "SEC1", "severity": "critical", "line": 2, "message": "m", "file": ""})()],
    )
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="quick")

    sources = {v.source for v in result.violations}
    assert "check_1c_standards" in sources
    assert "security_auditor" in sources


# ─────────────────────────────────────────────
# CHECK: standard / full levels (BSL LS, code_metrics, metadata_standards)
# ─────────────────────────────────────────────


def test_check_standard_level_bsl_ls_not_available(setup):
    """check(level='standard') без BSL LS → bsl_ls_available=False, 4 анализатора."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    sample_v = [type("V", (), {"rule_id": "R1", "severity": "warning", "line": 1, "message": "test", "file": ""})()]
    _make_fake_violations_module("check_1c_standards", "StandardsChecker", sample_v)
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    processor = TaskProcessor(pm)
    # BSL LS binary не существует → bsl_ls_available=False
    result = processor.check(bsl_file, level="standard")

    assert result.level == "standard"
    assert result.bsl_ls_available is False
    assert "bsl_ls" not in result.analyzers_run
    # 4 базовых анализатора запущены
    assert "check_1c_standards" in result.analyzers_run


def test_check_standard_level_bsl_ls_available(setup):
    """check(level='standard') с BSL LS → bsl_ls_available=True, violations от BSL LS."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    # Создаём фейковый BSL LS binary
    bsl_ls_bin = tmp / "bsl-ls"
    bsl_ls_bin.write_text("#!/bin/bash\necho ok", encoding="utf-8")
    bsl_ls_bin.chmod(0o755)
    # Патчим property bsl_ls_binary
    with patch.object(type(pm), "bsl_ls_binary", new_callable=lambda: property(lambda self: bsl_ls_bin)):
        _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
        _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
        _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
        _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

        processor = TaskProcessor(pm)

        # Мокаем BSLAnalyzer.analyze чтобы вернуть диагностики
        fake_diag = {"code": "BSL001", "severity": "warning", "line": 5, "message": "diag"}
        fake_result = type("R", (), {"diagnostics": [fake_diag]})()

        with patch("src.services.bsl_analyzer.BSLAnalyzer") as MockBSL:
            MockBSL.return_value.analyze.return_value = fake_result
            result = processor.check(bsl_file, level="standard")

    assert result.bsl_ls_available is True
    assert "bsl_ls" in result.analyzers_run
    # Должна быть violation от BSL LS
    bsl_violations = [v for v in result.violations if v.source == "bsl_ls"]
    assert len(bsl_violations) == 1
    assert bsl_violations[0].rule_id == "BSL001"


def test_check_standard_level_bsl_ls_exception(setup):
    """check(level='standard') с BSL LS exception → graceful, 4 анализатора."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    bsl_ls_bin = tmp / "bsl-ls"
    bsl_ls_bin.write_text("#!/bin/bash\necho ok", encoding="utf-8")
    bsl_ls_bin.chmod(0o755)

    with patch.object(type(pm), "bsl_ls_binary", new_callable=lambda: property(lambda self: bsl_ls_bin)):
        _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
        _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
        _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
        _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

        processor = TaskProcessor(pm)

        # BSLAnalyzer выбрасывает исключение
        with patch("src.services.bsl_analyzer.BSLAnalyzer") as MockBSL:
            MockBSL.return_value.analyze.side_effect = RuntimeError("Java failed")
            result = processor.check(bsl_file, level="standard")

    assert result.bsl_ls_available is True
    # bsl_ls не в analyzers_run (упал), но не завалил весь check
    assert "bsl_ls" not in result.analyzers_run
    # Базовые 4 анализатора запущены
    assert "check_1c_standards" in result.analyzers_run


def _make_fake_metrics_module():
    """Создать фейковый code_metrics модуль."""
    mod = types.ModuleType("code_metrics")

    class FakeMethod:
        def __init__(self, name, lloc, line_start):
            self.name = name
            self.lloc = lloc
            self.line_start = line_start

    class FakeMetrics:
        def __init__(self):
            self.loc = 200
            self.lloc = 150
            self.cyclomatic_complexity = 25.0
            self.cognitive_complexity = 30.0
            self.max_nesting = 5
            self.methods = [FakeMethod("m1", 10, 1), FakeMethod("m2", 80, 50)]
            self.is_god_object = True
            self.long_methods = [FakeMethod("LongMethod", 80, 50)]
            self.health_score = 40.0

    class CodeMetricsAnalyzer:
        def analyze_file(self, path):
            return FakeMetrics()

    mod.CodeMetricsAnalyzer = CodeMetricsAnalyzer
    sys.modules["code_metrics"] = mod
    return mod


def _make_fake_metadata_standards_module():
    """Создать фейковый check_metadata_standards модуль."""
    mod = types.ModuleType("check_metadata_standards")

    class FakeViolation:
        def __init__(self, rule_id, severity, line, message, file=""):
            self.rule_id = rule_id
            self.severity = severity
            self.line = line
            self.message = message
            self.file = file

    class MetadataStandardsChecker:
        def check_path(self, path):
            return [FakeViolation("META001", "warning", 10, "metadata issue", str(path))]

    mod.FakeViolation = FakeViolation
    mod.MetadataStandardsChecker = MetadataStandardsChecker
    sys.modules["check_metadata_standards"] = mod
    return mod


def test_check_full_level_runs_code_metrics(setup):
    """check(level='full') запускает code_metrics с God Object и Long Method."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])
    _make_fake_metrics_module()

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="full")

    assert result.level == "full"
    assert "code_metrics" in result.analyzers_run
    assert result.metrics is not None
    assert result.metrics.loc == 200
    assert result.metrics.is_god_object is True
    assert len(result.metrics.long_methods) == 1

    # God Object violation
    god_violations = [v for v in result.violations if v.rule_id == "GOD_OBJECT"]
    assert len(god_violations) == 1
    assert god_violations[0].severity == "error"

    # Long Method violation
    long_violations = [v for v in result.violations if v.rule_id == "LONG_METHOD"]
    assert len(long_violations) == 1
    assert long_violations[0].severity == "warning"


def test_check_full_level_runs_metadata_standards(setup):
    """check(level='full') запускает check_metadata_standards."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])
    _make_fake_metrics_module()
    _make_fake_metadata_standards_module()

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="full")

    assert "check_metadata_standards" in result.analyzers_run
    meta_violations = [v for v in result.violations if v.source == "check_metadata_standards"]
    assert len(meta_violations) == 1
    assert meta_violations[0].rule_id == "META001"


def test_check_full_level_code_metrics_exception(setup):
    """check(level='full') с code_metrics exception → graceful."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    _make_fake_violations_module("check_1c_standards", "StandardsChecker", [])
    _make_fake_violations_module("security_auditor", "SecurityAuditor", [])
    _make_fake_violations_module("transaction_checker", "TransactionChecker", [])
    _make_fake_violations_module("query_analyzer", "QueryAnalyzer", [])

    # Фейковый code_metrics с исключением
    mod = types.ModuleType("code_metrics")

    class CodeMetricsAnalyzer:
        def analyze_file(self, path):
            raise RuntimeError("metrics failed")

    mod.CodeMetricsAnalyzer = CodeMetricsAnalyzer
    sys.modules["code_metrics"] = mod

    processor = TaskProcessor(pm)
    result = processor.check(bsl_file, level="full")

    # code_metrics не в analyzers_run (упал)
    assert "code_metrics" not in result.analyzers_run
    # Но check не завалился
    assert "check_1c_standards" in result.analyzers_run


# ─────────────────────────────────────────────
# CHECK via analyzers (новый OCP API)
# ─────────────────────────────────────────────


def test_check_via_analyzers_file_not_found(setup):
    """check_via_analyzers() на несуществующий файл → FileNotFoundError."""
    pm, tmp = setup
    processor = TaskProcessor(pm)
    with pytest.raises(FileNotFoundError):
        processor.check_via_analyzers(tmp / "missing.bsl", level="quick")


def test_check_via_analyzers_returns_check_result(setup):
    """check_via_analyzers() возвращает CheckResult."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    processor = TaskProcessor(pm)
    result = processor.check_via_analyzers(bsl_file, level="quick")

    assert isinstance(result, CheckResult)
    assert result.level == "quick"
    assert result.file == str(bsl_file)


def test_check_via_analyzers_populates_violations(setup):
    """check_via_analyzers() заполняет violations и analyzers_run."""
    pm, tmp = setup
    bsl_file = tmp / "test.bsl"
    bsl_file.write_text("Процедура Тест() Экспорт\nКонецПроцедуры", encoding="utf-8")

    processor = TaskProcessor(pm)
    result = processor.check_via_analyzers(bsl_file, level="quick")

    # analyzers_run должен быть заполнен (хотя бы один analyzer)
    assert len(result.analyzers_run) > 0
    # violations — список (может быть пустым если код чистый)
    assert isinstance(result.violations, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
