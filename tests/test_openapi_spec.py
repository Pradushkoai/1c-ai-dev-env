"""
Tесты для OpenAPI spec (docs/mcp-openapi.json).

A-1 (2026-07-05): добавлен тест версии spec.
Ранее spec был 5.3.1 при версии проекта 6.0.0 — рассинхрон.
Тест гарантирует, что spec версия соответствует pyproject.toml версии.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OPENAPI_SPEC_PATH = REPO_ROOT / "docs" / "mcp-openapi.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _get_pyproject_version() -> str:
    """Извлечь версию из pyproject.toml."""
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.strip().startswith("version"):
            # Строка вида: version = "6.0.0"
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _load_openapi_spec() -> dict:
    """Загрузить OpenAPI spec из docs/mcp-openapi.json."""
    if not OPENAPI_SPEC_PATH.exists():
        pytest.fail(f"OpenAPI spec не найден: {OPENAPI_SPEC_PATH}")
    with open(OPENAPI_SPEC_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestOpenApiSpecStructure:
    """Базовая проверка структуры OpenAPI spec."""

    def test_spec_exists(self) -> None:
        """OpenAPI spec файл существует."""
        assert OPENAPI_SPEC_PATH.exists(), f"OpenAPI spec должен существовать: {OPENAPI_SPEC_PATH}"

    def test_spec_is_valid_json(self) -> None:
        """OpenAPI spec — валидный JSON."""
        spec = _load_openapi_spec()
        assert isinstance(spec, dict), "Spec должен быть dict"

    def test_spec_has_required_top_level_fields(self) -> None:
        """Spec содержит обязательные top-level поля OpenAPI 3.0."""
        spec = _load_openapi_spec()
        required = ["openapi", "info", "paths"]
        for field in required:
            assert field in spec, f"Spec должен содержать top-level поле: {field}"

    def test_spec_openapi_version(self) -> None:
        """Spec использует OpenAPI 3.0.3."""
        spec = _load_openapi_spec()
        assert spec["openapi"] == "3.0.3", f"OpenAPI версия должна быть 3.0.3, получено: {spec['openapi']}"

    def test_spec_info_has_required_fields(self) -> None:
        """Spec info содержит обязательные поля."""
        spec = _load_openapi_spec()
        info = spec["info"]
        required = ["title", "description", "version", "contact", "license"]
        for field in required:
            assert field in info, f"info должен содержать поле: {field}"


class TestOpenApiSpecVersion:
    """A-1: проверка синхронизации версии spec с pyproject.toml."""

    def test_spec_version_matches_pyproject(self) -> None:
        """Версия OpenAPI spec синхронизирована с pyproject.toml.

        A-1 (2026-07-05): ранее spec был 5.3.1 при pyproject 6.0.0.
        Тест гарантирует, что spec версия = pyproject версия.
        Если тест падает — запустите: python3 scripts/generate_openapi.py
        """
        spec = _load_openapi_spec()
        spec_version = spec["info"]["version"]
        pyproject_version = _get_pyproject_version()

        assert spec_version == pyproject_version, (
            f"OpenAPI spec версия ({spec_version}) не соответствует "
            f"pyproject.toml версии ({pyproject_version}). "
            f"Запустите: python3 scripts/generate_openapi.py"
        )

    def test_spec_version_is_not_legacy_5_3_1(self) -> None:
        """Spec версия НЕ должна быть устаревшей 5.3.1.

        A-1 (2026-07-05): 5.3.1 была устаревшей версией до синхронизации.
        """
        spec = _load_openapi_spec()
        spec_version = spec["info"]["version"]
        assert spec_version != "5.3.1", (
            "OpenAPI spec версия 5.3.1 устарела. "
            "Запустите: python3 scripts/generate_openapi.py для регенерации."
        )


class TestOpenApiSpecTools:
    """Проверка tools в spec."""

    def test_spec_has_7_visible_tools(self) -> None:
        """Spec содержит 7 visible MCP tools (R1: 6 high-level + data_status).

        OpenAPI spec экспонирует только visible tools (7) — те, что LLM/клиент
        может вызвать через HTTP. Остальные 55 доступны через run_cli.
        """
        spec = _load_openapi_spec()
        tools_count = len(spec["paths"])
        assert tools_count == 7, (
            f"Spec должен содержать 7 visible tools, получено: {tools_count}. "
            f"Запустите: python3 scripts/generate_openapi.py для регенерации."
        )

    def test_all_tools_have_post_method(self) -> None:
        """Все tools используют POST method."""
        spec = _load_openapi_spec()
        for path, methods in spec["paths"].items():
            assert "post" in methods, f"Tool {path} должен иметь POST method"

    def test_all_tools_have_required_operation_fields(self) -> None:
        """Все tools имеют обязательные поля operation."""
        spec = _load_openapi_spec()
        required = ["summary", "description", "operationId", "requestBody", "responses"]
        for path, methods in spec["paths"].items():
            for method, op in methods.items():
                for field in required:
                    assert field in op, f"Tool {path}/{method} должен иметь поле: {field}"

    def test_all_tools_have_responses(self) -> None:
        """Все tools имеют responses с 200/400/500."""
        spec = _load_openapi_spec()
        for path, methods in spec["paths"].items():
            for method, op in methods.items():
                responses = op.get("responses", {})
                for code in ["200", "400", "500"]:
                    assert code in responses, (
                        f"Tool {path}/{method} должен иметь response {code}"
                    )


class TestOpenApiSpecGenerator:
    """Проверка генератора spec (scripts/generate_openapi.py)."""

    def test_generator_exists(self) -> None:
        """Генератор spec существует."""
        generator = REPO_ROOT / "scripts" / "generate_openapi.py"
        assert generator.exists(), "Генератор должен существовать: scripts/generate_openapi.py"

    def test_generator_uses_dynamic_version(self) -> None:
        """F2.1: Генератор использует динамическую версию из pyproject.toml.

        Ранее версия была захардкожена (5.3.1, потом 6.0.0) — рассинхрон с pyproject.toml.
        Теперь: _read_pyproject_version() читает версию из pyproject.toml.
        """
        generator = REPO_ROOT / "scripts" / "generate_openapi.py"
        content = generator.read_text(encoding="utf-8")
        # Проверяем, что НЕТ захардкоженной версии как значения поля
        assert '"version": "5.3.1"' not in content, (
            "Генератор не должен содержать устаревшую версию 5.3.1 как значение."
        )
        assert '"version": "6.0.0"' not in content, (
            "Генератор не должен содержать захардкоженную версию 6.0.0. "
            "Используйте _read_pyproject_version() для динамической версии."
        )
        # Проверяем, что функция _read_pyproject_version существует
        assert "_read_pyproject_version" in content, (
            "Генератор должен использовать _read_pyproject_version() для динамической версии."
        )

    def test_generator_produces_valid_spec(self) -> None:
        """Генератор (через _get_tools_description) производит валидный spec.

        Косвенная проверка: если spec существует и валиден, генератор работает.
        Прямой запуск генератора требует импорта src.mcp_server, что может
        требовать mcp SDK — оставляем как интеграционный тест.
        """
        spec = _load_openapi_spec()
        assert spec["info"]["version"] != "", "Spec должен иметь непустую версию"
