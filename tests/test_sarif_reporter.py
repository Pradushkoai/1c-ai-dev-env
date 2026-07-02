"""
Тесты для SarifReporter — конвертация CheckResult в SARIF 2.1.0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.task import CheckResult, CodeMetric, Violation
from src.services.sarif_reporter import SEVERITY_TO_LEVEL, SarifReporter


@pytest.fixture
def simple_result() -> CheckResult:
    """CheckResult с 3 violations от 2 разных анализаторов."""
    return CheckResult(
        file="/path/to/module.bsl",
        level="standard",
        violations=[
            Violation(
                source="check_1c_standards",
                rule_id="no-yo-in-code",
                severity="warning",
                line=42,
                message="Найдена буква 'ё' в коде",
                file="/path/to/module.bsl",
            ),
            Violation(
                source="check_1c_standards",
                rule_id="line-too-long",
                severity="warning",
                line=100,
                message="Строка длиннее 120 символов",
                file="/path/to/module.bsl",
            ),
            Violation(
                source="security_auditor",
                rule_id="SQL_INJECTION",
                severity="critical",
                line=15,
                message="Возможна SQL-инъекция: конкатенация строки в запросе",
                file="/path/to/module.bsl",
            ),
        ],
        analyzers_run=["check_1c_standards", "security_auditor"],
    )


@pytest.fixture
def empty_result() -> CheckResult:
    """CheckResult без violations."""
    return CheckResult(
        file="/path/to/clean.bsl",
        level="quick",
        violations=[],
        analyzers_run=["check_1c_standards"],
    )


@pytest.fixture
def result_with_metrics() -> CheckResult:
    """CheckResult с метриками (level=full)."""
    r = CheckResult(
        file="/path/to/complex.bsl",
        level="full",
        violations=[
            Violation(
                source="code_metrics",
                rule_id="GOD_OBJECT",
                severity="error",
                line=0,
                message="God Object: 800 строк, 45 методов",
                file="/path/to/complex.bsl",
            ),
        ],
        analyzers_run=["code_metrics", "check_1c_standards"],
    )
    r.metrics = CodeMetric(
        loc=800,
        lloc=650,
        cyclomatic_complexity=145.0,
        cognitive_complexity=320.0,
        max_nesting=8,
        methods_count=45,
        is_god_object=True,
        long_methods=[{"name": "BigMethod", "lloc": 120, "line_start": 50}],
        health_score=35.0,
    )
    return r


# ─────────────────────────────────────────────
# Структура SARIF
# ─────────────────────────────────────────────


def test_sarif_version_and_schema():
    """SARIF имеет корректную версию и schema."""
    reporter = SarifReporter()
    result = CheckResult(file="test.bsl", violations=[])
    sarif = reporter.convert(result)

    assert sarif["version"] == "2.1.0"
    assert "sarif-schema-2.1.0.json" in sarif["$schema"]
    assert "runs" in sarif
    assert len(sarif["runs"]) == 1


def test_sarif_has_run_structure(simple_result):
    """SARIF run содержит tool и results."""
    sarif = SarifReporter().convert(simple_result)

    run = sarif["runs"][0]
    assert "tool" in run
    assert "results" in run
    assert "invocations" in run


def test_sarif_results_count_matches_violations(simple_result):
    """Количество results = количество violations."""
    sarif = SarifReporter().convert(simple_result)
    assert len(sarif["runs"][0]["results"]) == 3


def test_sarif_empty_results(empty_result):
    """Нет violations → пустой results массив."""
    sarif = SarifReporter().convert(empty_result)
    assert sarif["runs"][0]["results"] == []


# ─────────────────────────────────────────────
# Severity mapping
# ─────────────────────────────────────────────


def test_sarif_severity_error_mapped_to_error():
    """severity=error → level=error."""
    v = Violation(source="x", rule_id="R1", severity="error", line=1, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def test_sarif_severity_critical_mapped_to_error():
    """severity=critical → level=error (SARIF не имеет critical)."""
    v = Violation(source="x", rule_id="R1", severity="critical", line=1, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def test_sarif_severity_warning_mapped_to_warning():
    """severity=warning → level=warning."""
    v = Violation(source="x", rule_id="R1", severity="warning", line=1, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    assert sarif["runs"][0]["results"][0]["level"] == "warning"


def test_sarif_severity_info_mapped_to_note():
    """severity=info → level=note."""
    v = Violation(source="x", rule_id="R1", severity="info", line=1, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    assert sarif["runs"][0]["results"][0]["level"] == "note"


# ─────────────────────────────────────────────
# Locations (для GitHub аннотаций на строках)
# ─────────────────────────────────────────────


def test_sarif_location_has_line(simple_result):
    """Каждый result имеет location с startLine."""
    sarif = SarifReporter().convert(simple_result)
    for r in sarif["runs"][0]["results"]:
        loc = r["locations"][0]["physicalLocation"]
        assert "region" in loc
        assert "startLine" in loc["region"]
        assert loc["region"]["startLine"] >= 1


def test_sarif_location_has_artifact_uri(simple_result):
    """Каждый result имеет artifactLocation.uri."""
    sarif = SarifReporter().convert(simple_result)
    for r in sarif["runs"][0]["results"]:
        loc = r["locations"][0]["physicalLocation"]
        assert "artifactLocation" in loc
        assert "uri" in loc["artifactLocation"]
        assert loc["artifactLocation"]["uri"]


def test_sarif_line_zero_becomes_one():
    """line=0 → startLine=1 (SARIF не принимает 0)."""
    v = Violation(source="x", rule_id="R1", severity="error", line=0, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    loc = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert loc["region"]["startLine"] == 1


# ─────────────────────────────────────────────
# Tools / Rules metadata
# ─────────────────────────────────────────────


def test_sarif_tools_count_matches_sources(simple_result):
    """В SARIF 2.1.0 один driver с объединёнными rules из всех sources.

    Проверяем, что rules содержат правила из обоих sources.
    """
    sarif = SarifReporter().convert(simple_result)
    # simple_result имеет 2 sources: check_1c_standards + security_auditor
    tool = sarif["runs"][0]["tool"]
    # SARIF 2.1.0: один driver с объединёнными rules
    driver = tool["driver"]
    # rules должны содержать правила из обоих sources
    rule_ids = [r["id"] for r in driver["rules"]]
    # Должны быть правила из check_1c_standards (no-yo-in-code, line-too-long)
    assert "no-yo-in-code" in rule_ids
    # И из security_auditor (rule_id = SQL_INJECTION в simple_result fixture)
    assert "SQL_INJECTION" in rule_ids


def test_sarif_rules_unique_per_tool(simple_result):
    """rules внутри driver уникальны (no duplicates)."""
    sarif = SarifReporter().convert(simple_result)
    tool = sarif["runs"][0]["tool"]
    driver = tool["driver"]

    rule_ids = [r["id"] for r in driver["rules"]]
    assert len(rule_ids) == len(set(rule_ids))  # нет дублей
    assert "no-yo-in-code" in rule_ids
    assert "line-too-long" in rule_ids


def test_sarif_tool_has_driver_metadata():
    """tool.driver содержит name, version, informationUri."""
    v = Violation(source="security_auditor", rule_id="R1", severity="error", line=1, message="m")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)

    tool = sarif["runs"][0]["tool"]
    driver = tool["driver"]
    assert "name" in driver
    assert "version" in driver
    assert "informationUri" in driver


# ─────────────────────────────────────────────
# Метрики как info-level results
# ─────────────────────────────────────────────


def test_sarif_metrics_added_as_info(result_with_metrics):
    """Метрики добавляются как info-level result."""
    sarif = SarifReporter().convert(result_with_metrics)
    results = sarif["runs"][0]["results"]

    # Должен быть result с ruleId=METRICS_SUMMARY
    metric_results = [r for r in results if r["ruleId"] == "METRICS_SUMMARY"]
    assert len(metric_results) == 1
    assert metric_results[0]["level"] == "note"
    # В message должны быть метрики
    msg = metric_results[0]["message"]["text"]
    assert "LOC=800" in msg
    assert "Health=35.0" in msg


# ─────────────────────────────────────────────
# Запись в файл
# ─────────────────────────────────────────────


def test_sarif_write_to_file(simple_result, tmp_path):
    """write() создаёт валидный JSON файл."""
    out = tmp_path / "report.sarif"
    SarifReporter().write(simple_result, out)

    assert out.exists()
    # Должен быть валидный JSON
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "2.1.0"
    assert len(data["runs"][0]["results"]) == 3


def test_sarif_write_returns_path(simple_result, tmp_path):
    """write() возвращает путь к созданному файлу."""
    out = tmp_path / "report.sarif"
    result = SarifReporter().write(simple_result, out)
    assert result == out


# ─────────────────────────────────────────────
# Multiple CheckResult (для PR с несколькими файлами)
# ─────────────────────────────────────────────


def test_sarif_convert_multiple():
    """convert_multiple() объединяет violations из нескольких результатов."""
    r1 = CheckResult(
        file="a.bsl",
        violations=[
            Violation(source="x", rule_id="R1", severity="error", line=1, message="m1", file="a.bsl"),
        ],
    )
    r2 = CheckResult(
        file="b.bsl",
        violations=[
            Violation(source="x", rule_id="R2", severity="warning", line=2, message="m2", file="b.bsl"),
        ],
    )

    sarif = SarifReporter().convert_multiple([r1, r2])

    results = sarif["runs"][0]["results"]
    assert len(results) == 2
    files = {r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in results}
    assert files == {"a.bsl", "b.bsl"}


# ─────────────────────────────────────────────
# JSON сериализуемость
# ─────────────────────────────────────────────


def test_sarif_json_serializable(simple_result):
    """SARIF output должен быть JSON-сериализуемым."""
    sarif = SarifReporter().convert(simple_result)
    # Не должно выбросить
    json_str = json.dumps(sarif, ensure_ascii=False)
    # И должно парситься обратно
    json.loads(json_str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
