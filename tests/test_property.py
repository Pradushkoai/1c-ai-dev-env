"""
Property-based тесты через hypothesis.

Тестируют ИНВАРИАНТЫ — свойства которые должны выполняться
для ЛЮБЫХ входных данных, не только для конкретных примеров.

Запуск:
    pytest tests/test_property.py -v
    pytest tests/test_property.py -v --hypothesis-show-statistics

Hypothesis автоматически генерирует сотни входных данных
и пытается найти контрпример.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck

from src.models.task import (
    TaskContext,
    CheckResult,
    Violation,
    CodeMetric,
    PlatformMethodHit,
    ModuleApiHit,
    MetadataObjectHit,
    SkdSchemaHit,
    FormHit,
    KnowledgeArticleHit,
)
from src.models.configuration import Configuration
from src.services.sarif_reporter import SarifReporter, SEVERITY_TO_LEVEL


# ─────────────────────────────────────────────
# Стратегии генерации
# ─────────────────────────────────────────────

# Безопасные строки (без управляющих символов)
safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd', 'Pc', 'Pd', 'Ps', 'Pe', 'Sm'),
        max_codepoint=0x04FF,  # латиница + кириллица + цифры + знаки
    ),
    max_size=50,
)

# Severity из допустимого множества
severities = st.sampled_from([
    "error", "critical", "high", "warning", "medium",
    "low", "info", "information", "hint",
])

# Rule IDs в kebab-case
rule_ids = st.from_regex(r'[a-z][a-z0-9-]*[a-z0-9]', fullmatch=True)

# Source names (анализаторы)
sources = st.sampled_from([
    "bsl_ls", "check_1c_standards", "security_auditor",
    "transaction_checker", "query_analyzer", "code_metrics",
    "check_metadata_standards",
])


@st.composite
def violations(draw) -> Violation:
    """Генератор Violation."""
    return Violation(
        source=draw(sources),
        rule_id=draw(rule_ids),
        severity=draw(severities),
        line=draw(st.integers(min_value=0, max_value=10000)),
        message=draw(safe_text),
        file=draw(safe_text),
    )


@st.composite
def check_results(draw) -> CheckResult:
    """Генератор CheckResult."""
    n_violations = draw(st.integers(min_value=0, max_value=20))
    return CheckResult(
        file=draw(safe_text),
        level=draw(st.sampled_from(["quick", "standard", "full"])),
        violations=[draw(violations()) for _ in range(n_violations)],
        bsl_ls_available=draw(st.booleans()),
        analyzers_run=[draw(sources) for _ in range(draw(st.integers(0, 5)))],
    )


@st.composite
def code_metrics(draw) -> CodeMetric:
    """Генератор CodeMetric."""
    return CodeMetric(
        loc=draw(st.integers(min_value=0, max_value=100000)),
        lloc=draw(st.integers(min_value=0, max_value=100000)),
        cyclomatic_complexity=draw(st.floats(min_value=0, max_value=1000)),
        cognitive_complexity=draw(st.floats(min_value=0, max_value=10000)),
        max_nesting=draw(st.integers(min_value=0, max_value=20)),
        methods_count=draw(st.integers(min_value=0, max_value=500)),
        is_god_object=draw(st.booleans()),
        health_score=draw(st.floats(min_value=0, max_value=100)),
    )


# ─────────────────────────────────────────────
# ИНВАРИАНТ 1: Roundtrip сериализации Configuration
# ─────────────────────────────────────────────

@given(
    name=safe_text,
    title=safe_text,
    version=safe_text,
    vendor=safe_text,
    objects_count=st.integers(min_value=0, max_value=100000),
    api_methods_count=st.integers(min_value=0, max_value=100000),
)
def test_configuration_roundtrip(name, title, version, vendor, objects_count, api_methods_count):
    """Configuration.to_dict() → from_dict() должно дать эквивалентный объект."""
    assume(name and title)  # не пустые
    cfg = Configuration(
        name=name,
        title=title,
        version=version,
        vendor=vendor,
        objects_count=objects_count,
        api_methods_count=api_methods_count,
        status="active",
    )
    d = cfg.to_dict()
    restored = Configuration.from_dict(name, d, project_root=Path("."))

    assert restored.name == cfg.name
    assert restored.title == cfg.title
    assert restored.version == cfg.version
    assert restored.vendor == cfg.vendor
    assert restored.objects_count == cfg.objects_count
    assert restored.api_methods_count == cfg.api_methods_count
    assert restored.status == cfg.status


# ─────────────────────────────────────────────
# ИНВАРИАНТ 2: CheckResult.verdict консистентен
# ─────────────────────────────────────────────

@given(result=check_results())
def test_check_result_verdict_consistent(result: CheckResult):
    """verdict всегда согласован с total_errors/total_warnings."""
    verdict = result.verdict
    if result.total_errors == 0 and result.total_warnings == 0:
        assert verdict == "ready"
    elif result.total_errors == 0:
        assert verdict == "warnings"
    else:
        assert verdict == "errors"


@given(result=check_results())
def test_check_result_to_dict_roundtrip(result: CheckResult):
    """to_dict() должен быть JSON-сериализуемым."""
    d = result.to_dict()
    # Не должно выбросить
    json_str = json.dumps(d, ensure_ascii=False)
    # И должно парситься обратно
    restored = json.loads(json_str)
    assert restored["total_errors"] == result.total_errors
    assert restored["total_warnings"] == result.total_warnings
    assert restored["verdict"] == result.verdict


@given(result=check_results())
def test_check_result_errors_count_matches(result: CheckResult):
    """total_errors == количество violations с error/critical/high."""
    expected = sum(
        1 for v in result.violations
        if v.severity.lower() in ("error", "critical", "high")
    )
    assert result.total_errors == expected


# ─────────────────────────────────────────────
# ИНВАРИАНТ 3: SARIF severity mapping
# ─────────────────────────────────────────────

@given(severity=severities)
def test_sarif_severity_always_mapped(severity: str):
    """Любая severity должна быть отображена в один из 4 SARIF levels."""
    v = Violation(
        source="test",
        rule_id="R1",
        severity=severity,
        line=1,
        message="test",
        file="test.bsl",
    )
    result = CheckResult(file="test.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    level = sarif["runs"][0]["results"][0]["level"]
    assert level in ("error", "warning", "note", "none")


@given(severity=severities)
def test_sarif_critical_and_high_are_errors(severity: str):
    """critical и high всегда мапятся в error (SARIF не имеет critical)."""
    assume(severity in ("critical", "high", "error"))
    v = Violation(source="test", rule_id="R1", severity=severity, line=1, message="m", file="t.bsl")
    result = CheckResult(file="t.bsl", violations=[v])
    sarif = SarifReporter().convert(result)
    assert sarif["runs"][0]["results"][0]["level"] == "error"


@given(result=check_results())
def test_sarif_results_count_matches_violations(result: CheckResult):
    """Количество SARIF results >= количество violations (метрики могут добавить)."""
    sarif = SarifReporter().convert(result)
    sarif_count = len(sarif["runs"][0]["results"])
    violations_count = len(result.violations)
    # SARIF results может быть больше если есть метрики (METRICS_SUMMARY)
    assert sarif_count >= violations_count


# ─────────────────────────────────────────────
# ИНВАРИАНТ 4: SARIF structure always valid
# ─────────────────────────────────────────────

@given(result=check_results())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
def test_sarif_always_valid_json(result: CheckResult):
    """SARIF output всегда валидный JSON."""
    sarif = SarifReporter().convert(result)
    json_str = json.dumps(sarif, ensure_ascii=False)
    restored = json.loads(json_str)
    assert restored["version"] == "2.1.0"
    assert "runs" in restored
    assert len(restored["runs"]) == 1


@given(result=check_results())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
def test_sarif_location_startline_always_positive(result: CheckResult):
    """startLine всегда >= 1 (SARIF не принимает 0)."""
    if not result.violations:
        return
    sarif = SarifReporter().convert(result)
    for r in sarif["runs"][0]["results"]:
        loc = r["locations"][0]["physicalLocation"]
        if "region" in loc:
            assert loc["region"]["startLine"] >= 1


# ─────────────────────────────────────────────
# ИНВАРИАНТ 5: TaskContext.total_hits
# ─────────────────────────────────────────────

@given(
    n_platform=st.integers(0, 10),
    n_api=st.integers(0, 10),
    n_meta=st.integers(0, 10),
    n_skd=st.integers(0, 10),
    n_forms=st.integers(0, 10),
    n_kb=st.integers(0, 10),
)
def test_task_context_total_hits(n_platform, n_api, n_meta, n_skd, n_forms, n_kb):
    """total_hits == сумма длин всех списков находок."""
    ctx = TaskContext(query="test")
    ctx.platform_methods = [PlatformMethodHit() for _ in range(n_platform)]
    ctx.api_modules = [ModuleApiHit() for _ in range(n_api)]
    ctx.metadata_objects = [MetadataObjectHit() for _ in range(n_meta)]
    ctx.skd_schemas = [SkdSchemaHit() for _ in range(n_skd)]
    ctx.forms = [FormHit() for _ in range(n_forms)]
    ctx.knowledge_articles = [KnowledgeArticleHit() for _ in range(n_kb)]

    expected = n_platform + n_api + n_meta + n_skd + n_forms + n_kb
    assert ctx.total_hits == expected


# ─────────────────────────────────────────────
# ИНВАРИАНТ 6: TaskContext.to_dict() roundtrip
# ─────────────────────────────────────────────

@given(
    query=safe_text,
    config_name=safe_text,
    n_platform=st.integers(0, 5),
)
def test_task_context_to_dict_json_serializable(query, config_name, n_platform):
    """to_dict() всегда JSON-сериализуем."""
    assume(query)  # не пустой
    ctx = TaskContext(query=query, config_name=config_name)
    ctx.platform_methods = [
        PlatformMethodHit(
            name_ru=f"Метод{i}",
            name_en=f"Method{i}",
            score=float(i) * 0.1,
        )
        for i in range(n_platform)
    ]
    d = ctx.to_dict()
    json_str = json.dumps(d, ensure_ascii=False)
    restored = json.loads(json_str)
    assert restored["query"] == query
    assert restored["config"] == config_name
    assert len(restored["platform_methods"]) == n_platform


# ─────────────────────────────────────────────
# ИНВАРИАНТ 7: CodeMetric.health_score в диапазоне
# ─────────────────────────────────────────────

@given(metrics=code_metrics())
def test_code_metric_health_score_range(metrics: CodeMetric):
    """health_score всегда в [0, 100]."""
    assert 0 <= metrics.health_score <= 100


@given(metrics=code_metrics())
def test_code_metric_to_dict_json_serializable(metrics: CodeMetric):
    """CodeMetric.__dict__ должен быть JSON-сериализуем."""
    json.dumps(metrics.__dict__, ensure_ascii=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
