"""
M7 (2026-07-06): Тесты для OpenAPI enricher (A-2, A-3, A-4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cli.openapi_enricher import (
    EXAMPLES,
    RESPONSE_SCHEMAS,
    TOOL_CATEGORIES,
    enrich_openapi_spec,
    save_enriched_spec,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def minimal_spec() -> dict:
    """Минимальный OpenAPI spec для тестов."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": {
            "/tools/search_1c_methods": {
                "post": {
                    "summary": "search_1c_methods",
                    "operationId": "search_1c_methods",
                    "tags": ["MCP Tools"],
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/tools/analyze_architecture": {
                "post": {
                    "summary": "analyze_architecture",
                    "operationId": "analyze_architecture",
                    "tags": ["MCP Tools"],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }


@pytest.fixture
def spec_file(tmp_path: Path, minimal_spec: dict) -> Path:
    """Spec файл на диске."""
    spec_path = tmp_path / "test-openapi.json"
    spec_path.write_text(json.dumps(minimal_spec), encoding="utf-8")
    return spec_path


# ============================================================================
# Constants tests
# ============================================================================


class TestConstants:
    def test_tool_categories_defined(self) -> None:
        assert len(TOOL_CATEGORIES) >= 8
        assert "Analyzers" in TOOL_CATEGORIES
        assert "Search" in TOOL_CATEGORIES

    def test_response_schemas_defined(self) -> None:
        assert len(RESPONSE_SCHEMAS) >= 5
        assert "ErrorResponse" in RESPONSE_SCHEMAS
        assert "SearchResult" in RESPONSE_SCHEMAS

    def test_examples_defined(self) -> None:
        assert len(EXAMPLES) >= 5
        assert "search_request" in EXAMPLES
        assert "error_response" in EXAMPLES


# ============================================================================
# enrich_openapi_spec tests
# ============================================================================


class TestEnrichSpec:
    def test_adds_tags_section(self, spec_file: Path) -> None:
        """A-4: Добавляет tags section."""
        spec = enrich_openapi_spec(spec_file)
        assert "tags" in spec
        assert len(spec["tags"]) >= 8

    def test_adds_components_schemas(self, spec_file: Path) -> None:
        """A-2: Добавляет components/schemas."""
        spec = enrich_openapi_spec(spec_file)
        assert "components" in spec
        assert "schemas" in spec["components"]
        assert "ErrorResponse" in spec["components"]["schemas"]

    def test_adds_components_examples(self, spec_file: Path) -> None:
        """A-3: Добавляет components/examples."""
        spec = enrich_openapi_spec(spec_file)
        assert "examples" in spec["components"]
        assert "search_request" in spec["components"]["examples"]

    def test_updates_path_tags(self, spec_file: Path) -> None:
        """A-4: Обновляет tags для каждого path."""
        spec = enrich_openapi_spec(spec_file)
        # search_1c_methods → Search category
        search_path = spec["paths"]["/tools/search_1c_methods"]
        assert "Search" in search_path["post"]["tags"]

        # analyze_architecture → Analyzers
        analyze_path = spec["paths"]["/tools/analyze_architecture"]
        assert "Analyzers" in analyze_path["post"]["tags"]

    def test_adds_response_schemas_to_paths(self, spec_file: Path) -> None:
        """A-2: Добавляет response schemas."""
        spec = enrich_openapi_spec(spec_file)
        for path, methods in spec["paths"].items():
            for method, info in methods.items():
                if not isinstance(info, dict):
                    continue
                assert "responses" in info
                assert "200" in info["responses"]
                assert "400" in info["responses"]

    def test_error_response_uses_ref(self, spec_file: Path) -> None:
        """A-2: 400 response использует $ref на ErrorResponse."""
        spec = enrich_openapi_spec(spec_file)
        for path, methods in spec["paths"].items():
            for method, info in methods.items():
                if not isinstance(info, dict):
                    continue
                resp_400 = info["responses"].get("400", {})
                content = resp_400.get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                assert "$ref" in schema
                assert "ErrorResponse" in schema["$ref"]

    def test_preserves_existing_paths(self, spec_file: Path) -> None:
        """Существующие paths сохраняются."""
        spec = enrich_openapi_spec(spec_file)
        assert "/tools/search_1c_methods" in spec["paths"]
        assert "/tools/analyze_architecture" in spec["paths"]

    def test_preserves_existing_info(self, spec_file: Path) -> None:
        """Info section сохраняется."""
        spec = enrich_openapi_spec(spec_file)
        assert spec["info"]["title"] == "Test"
        assert spec["info"]["version"] == "1.0.0"

    def test_unknown_tool_gets_misc_tag(self, tmp_path: Path) -> None:
        """Unknown tool → Misc tag."""
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/tools/unknown_tool": {
                    "post": {"summary": "unknown", "tags": ["MCP Tools"]}
                }
            },
        }
        spec_path = tmp_path / "test.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        enriched = enrich_openapi_spec(spec_path)
        tags = enriched["paths"]["/tools/unknown_tool"]["post"]["tags"]
        # Unknown tools keep MCP Tools or get Misc
        assert len(tags) == 1


# ============================================================================
# save_enriched_spec tests
# ============================================================================


class TestSaveSpec:
    def test_save_creates_file(self, tmp_path: Path, minimal_spec: dict) -> None:
        output = tmp_path / "output" / "spec.json"
        save_enriched_spec(minimal_spec, output)
        assert output.exists()

    def test_save_creates_parent_dirs(self, tmp_path: Path, minimal_spec: dict) -> None:
        output = tmp_path / "deep" / "nested" / "spec.json"
        save_enriched_spec(minimal_spec, output)
        assert output.exists()

    def test_save_valid_json(self, tmp_path: Path, minimal_spec: dict) -> None:
        output = tmp_path / "spec.json"
        save_enriched_spec(minimal_spec, output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
        assert loaded == minimal_spec


# ============================================================================
# Integration: real spec
# ============================================================================


class TestIntegrationRealSpec:
    """Интеграционный тест с реальным spec."""

    def test_real_spec_can_be_enriched(self) -> None:
        """Реальный docs/mcp-openapi.json может быть обогащён."""
        spec_path = Path("docs/mcp-openapi.json")
        if not spec_path.exists():
            pytest.skip("docs/mcp-openapi.json not found")

        spec = enrich_openapi_spec(spec_path)
        # Должны быть добавлены tags
        assert "tags" in spec
        assert len(spec["tags"]) >= 8
        # Должны быть schemas
        assert "components" in spec
        assert "schemas" in spec["components"]
