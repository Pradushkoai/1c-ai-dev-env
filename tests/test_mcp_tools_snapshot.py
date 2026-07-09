"""
P1.6: Snapshot тесты для MCP tools.

Проверяет стабильность контракта 54 MCP tools через pytest-snapshot.
Любое изменение в:
- количестве tools
- именах tools
- описаниях tools
- inputSchema tools

приведёт к падению теста. Для обновления snapshot (при намеренном изменении):
    pytest tests/test_mcp_tools_snapshot.py --snapshot-update

Контракт MCP tools критичен: LLM-агенты (Cursor, Claude) зависят от
стабильности имён и параметров tools. Любое breaking change должно быть
осознанным и задокументированным.
"""

from __future__ import annotations

import json

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tool_definitions() -> list[dict]:
    """Получить определения всех 54 MCP tools для snapshot тестов."""
    from src.mcpserver.tools.tool_definitions import get_all_tool_definitions

    tools = get_all_tool_definitions()
    # Преобразуем types.Tool в dict для JSON-сериализации
    result: list[dict] = []
    for t in tools:
        result.append(
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
        )
    # Сортируем по имени для стабильности snapshot
    result.sort(key=lambda x: x["name"])
    return result


@pytest.fixture
def static_descriptions() -> list[dict]:
    """Получить статические описания всех MCP tools."""
    from src.mcpserver.tools import get_all_descriptions

    tools = get_all_descriptions()
    # Сортируем по имени для стабильности
    return sorted(tools, key=lambda x: x["name"])


# ============================================================================
# Snapshot тесты — types.Tool определения
# ============================================================================


class TestToolDefinitionsSnapshot:
    """Snapshot тесты для types.Tool определений (list_tools handler).

    Проверяет, что определения tools (name, description, inputSchema)
    не меняются без явного обновления snapshot.
    """

    def test_tool_names_snapshot(self, snapshot, tool_definitions: list[dict]) -> None:
        """Snapshot имён всех 54 tools (отсортированных)."""
        names = [t["name"] for t in tool_definitions]
        snapshot.assert_match(
            json.dumps(names, ensure_ascii=False, indent=2),
            "tool_names.json",
        )

    def test_tool_count_snapshot(self, snapshot, tool_definitions: list[dict]) -> None:
        """Snapshot количества tools (54)."""
        count = len(tool_definitions)
        snapshot.assert_match(f"Total MCP tools: {count}\n", "tool_count.txt")

    def test_tool_descriptions_snapshot(self, snapshot, tool_definitions: list[dict]) -> None:
        """Snapshot описаний всех tools (name → description)."""
        descriptions = {t["name"]: t["description"] for t in tool_definitions}
        snapshot.assert_match(
            json.dumps(descriptions, ensure_ascii=False, indent=2),
            "tool_descriptions.json",
        )

    def test_tool_input_schemas_snapshot(self, snapshot, tool_definitions: list[dict]) -> None:
        """Snapshot inputSchema всех tools."""
        schemas = {t["name"]: t["inputSchema"] for t in tool_definitions}
        snapshot.assert_match(
            json.dumps(schemas, ensure_ascii=False, indent=2, sort_keys=True),
            "tool_input_schemas.json",
        )


# ============================================================================
# Snapshot тесты — статические описания
# ============================================================================


class TestStaticDescriptionsSnapshot:
    """Snapshot тесты для _get_tools_description() (статические описания).

    Проверяет, что статические описания (name, description, required_params,
    optional_params) не меняются без явного обновления snapshot.
    """

    def test_static_descriptions_snapshot(self, snapshot, static_descriptions: list[dict]) -> None:
        """Snapshot всех статических описаний tools."""
        snapshot.assert_match(
            json.dumps(static_descriptions, ensure_ascii=False, indent=2),
            "static_descriptions.json",
        )

    def test_static_descriptions_names_snapshot(self, snapshot, static_descriptions: list[dict]) -> None:
        """Snapshot имён из статических описаний."""
        names = [t["name"] for t in static_descriptions]
        snapshot.assert_match(
            json.dumps(names, ensure_ascii=False, indent=2),
            "static_descriptions_names.json",
        )

    def test_static_descriptions_required_params_snapshot(self, snapshot, static_descriptions: list[dict]) -> None:
        """Snapshot required_params для каждого tool."""
        params = {t["name"]: t["required_params"] for t in static_descriptions}
        snapshot.assert_match(
            json.dumps(params, ensure_ascii=False, indent=2, sort_keys=True),
            "static_descriptions_required_params.json",
        )


# ============================================================================
# Контрактные тесты — синхронизация между static и handler
# ============================================================================


class TestToolContractSync:
    """Контрактные тесты: статические описания и handler определения синхронизированы.

    Эти тесты НЕ snapshot — они проверяют инвариант: набор tools в
    _get_tools_description() и get_all_tool_definitions() должен совпадать.
    """

    def test_same_tool_names_in_static_and_handler(
        self, tool_definitions: list[dict], static_descriptions: list[dict]
    ) -> None:
        """Имена tools в static descriptions и handler definitions совпадают."""
        handler_names = {t["name"] for t in tool_definitions}
        static_names = {t["name"] for t in static_descriptions}
        assert handler_names == static_names, (
            f"Mismatch between static descriptions and handler definitions:\n"
            f"In handler only: {handler_names - static_names}\n"
            f"In static only: {static_names - handler_names}"
        )

    def test_descriptions_not_empty(self, tool_definitions: list[dict]) -> None:
        """Все tools имеют непустое описание."""
        for tool in tool_definitions:
            assert tool["description"], f"Tool '{tool['name']}' has empty description"
            assert len(tool["description"]) > 10, (
                f"Tool '{tool['name']}' has too short description: '{tool['description']}'"
            )

    def test_input_schema_has_type_object(self, tool_definitions: list[dict]) -> None:
        """Все inputSchema имеют type='object'."""
        for tool in tool_definitions:
            schema = tool["inputSchema"]
            assert schema.get("type") == "object", (
                f"Tool '{tool['name']}' inputSchema must have type='object', got: {schema.get('type')}"
            )

    def test_input_schema_has_properties(self, tool_definitions: list[dict]) -> None:
        """Все inputSchema имеют properties (даже пустые)."""
        for tool in tool_definitions:
            schema = tool["inputSchema"]
            assert "properties" in schema, f"Tool '{tool['name']}' inputSchema missing 'properties' key"
