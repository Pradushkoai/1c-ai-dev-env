"""
Tесты для OpenAPI spec validation (A-5).

Локальная Python-валидация, заменяющая spectral для окружений без Node.js.
Дублирует правила из .spectral.yaml — если spectral найдёт ошибку,
этот тест тоже должен её найти.

A-5 (2026-07-05): добавлен для CI blocking проверки spec.
Запускается в CI (openapi-validation.yml) и локально через pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OPENAPI_SPEC_PATH = REPO_ROOT / "docs" / "mcp-openapi.json"


def _load_spec() -> dict:
    """Загрузить OpenAPI spec."""
    if not OPENAPI_SPEC_PATH.exists():
        pytest.fail(f"OpenAPI spec не найден: {OPENAPI_SPEC_PATH}")
    with open(OPENAPI_SPEC_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate_spec(spec: dict) -> tuple[list[str], list[str]]:
    """Валидация spec. Возвращает (errors, warnings).

    Дублирует правила из .spectral.yaml:
    - info-contact (error)
    - info-description (warn)
    - info-license (warn)
    - operation-operationId (error)
    - operation-summary (warn)
    - operation-description (warn)
    - operation-responses (error)
    - version-not-legacy (error)
    - mcp-tools-post-only (error)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. info.contact (error)
    if not spec.get("info", {}).get("contact"):
        errors.append("info.contact missing")

    # 2. info.description (warn)
    if not spec.get("info", {}).get("description"):
        warnings.append("info.description missing")

    # 3. info.license (warn)
    if not spec.get("info", {}).get("license"):
        warnings.append("info.license missing")

    # 4. info.version (not legacy 5.3.1, error)
    version = spec.get("info", {}).get("version", "")
    if version == "5.3.1":
        errors.append("info.version is legacy 5.3.1 (must be 6.0.0+)")
    elif not version:
        errors.append("info.version missing")

    # 5-6. Все paths имеют operationId, summary, description, responses, POST only
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            # operationId (error)
            if not op.get("operationId"):
                errors.append(f"{path}/{method}: operationId missing")
            # summary (warn)
            if not op.get("summary"):
                warnings.append(f"{path}/{method}: summary missing")
            # description (warn)
            if not op.get("description"):
                warnings.append(f"{path}/{method}: description missing")
            # responses (error)
            if not op.get("responses"):
                errors.append(f"{path}/{method}: responses missing")
            # POST only (error)
            if method != "post":
                errors.append(f"{path}/{method}: MCP tools must use POST only (got {method})")

    return errors, warnings


class TestOpenApiValidation:
    """A-5: локальная Python-валидация spec (заменяет spectral без Node.js)."""

    def test_spec_has_no_validation_errors(self) -> None:
        """Spec проходит валидацию без ошибок (errors=0).

        Это blocking проверка — если есть errors, CI должен упасть.
        Соответствует spectral ruleset: error severity.
        """
        spec = _load_spec()
        errors, _ = _validate_spec(spec)
        assert len(errors) == 0, (
            f"OpenAPI spec validation errors ({len(errors)}):\n"
            + "\n".join(f"  ❌ {e}" for e in errors)
        )

    def test_spec_warnings_count(self) -> None:
        """Spec имеет 0 warnings (не blocking, но желательно).

        Warnings не блокируют CI, но указывают на улучшения.
        Тест информативный — показывает количество warnings.
        """
        spec = _load_spec()
        _, warnings = _validate_spec(spec)
        # Non-blocking: просто показываем warnings
        if warnings:
            print(f"\n⚠️  OpenAPI spec warnings ({len(warnings)}):")
            for w in warnings[:10]:
                print(f"  ⚠️  {w}")
        # Не assert — warnings не blocking

    def test_spectral_ruleset_exists(self) -> None:
        """Spectral ruleset (.spectral.yaml) существует для CI валидации."""
        ruleset = REPO_ROOT / ".spectral.yaml"
        assert ruleset.exists(), (
            "Spectral ruleset должен существовать: .spectral.yaml. "
            "См. A-5 (2026-07-05): OpenAPI validation в CI через spectral."
        )

    def test_ci_workflow_exists(self) -> None:
        """CI workflow для OpenAPI validation существует."""
        workflow = REPO_ROOT / ".github" / "workflows" / "openapi-validation.yml"
        assert workflow.exists(), (
            "CI workflow должен существовать: .github/workflows/openapi-validation.yml. "
            "См. A-5 (2026-07-05): OpenAPI validation в CI."
        )

    def test_ci_workflow_uses_spectral_action(self) -> None:
        """CI workflow использует stoplightio/spectral-action."""
        workflow = REPO_ROOT / ".github" / "workflows" / "openapi-validation.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "stoplightio/spectral-action" in content, (
            "CI workflow должен использовать stoplightio/spectral-action для валидации"
        )

    def test_ci_workflow_checks_version_sync(self) -> None:
        """CI workflow проверяет синхронизацию версии spec с pyproject.toml (A-1)."""
        workflow = REPO_ROOT / ".github" / "workflows" / "openapi-validation.yml"
        content = workflow.read_text(encoding="utf-8")
        # Проверяем, что есть step с проверкой версии
        assert "spec version matches pyproject" in content or "SPEC_VER" in content, (
            "CI workflow должен проверять синхронизацию версии spec с pyproject.toml (A-1)"
        )


class TestSpectralRulesetContent:
    """Проверка содержимого .spectral.yaml — правила соответствуют требованиям."""

    def test_ruleset_extends_oas(self) -> None:
        """Ruleset наследует spectral:oas (стандартные OpenAPI правила)."""
        ruleset = REPO_ROOT / ".spectral.yaml"
        content = ruleset.read_text(encoding="utf-8")
        assert "spectral:oas" in content, (
            "Ruleset должен наследовать spectral:oas для стандартных OpenAPI правил"
        )

    def test_ruleset_has_required_rules(self) -> None:
        """Ruleset содержит обязательные правила (error severity)."""
        ruleset = REPO_ROOT / ".spectral.yaml"
        content = ruleset.read_text(encoding="utf-8")
        required_rules = [
            "info-contact",
            "operation-operationId",
            "operation-responses",
            "version-not-legacy",
            "mcp-tools-post-only",
        ]
        for rule in required_rules:
            assert rule in content, f"Ruleset должен содержать правило: {rule}"

    def test_ruleset_has_warn_rules(self) -> None:
        """Ruleset содержит предупреждающие правила (warn severity)."""
        ruleset = REPO_ROOT / ".spectral.yaml"
        content = ruleset.read_text(encoding="utf-8")
        warn_rules = [
            "info-description",
            "info-license",
            "operation-summary",
            "operation-description",
        ]
        for rule in warn_rules:
            assert rule in content, f"Ruleset должен содержать правило: {rule}"
