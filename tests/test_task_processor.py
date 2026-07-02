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
    assert ctx.standards_summary["total_checks"] == 302


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
