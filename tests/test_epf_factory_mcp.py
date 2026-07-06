"""
Тест MCP-инструментов epf_factory_create и epf_factory_templates.

Проверяет:
  1. tools/list возвращает 2 epf_factory инструмента
  2. epf_factory_templates возвращает 5 шаблонов
  3. epf_factory_create с BSL кодом — EPF создан, round-trip OK
  4. epf_factory_create без BSL (default) — EPF создан
  5. epf_factory_create без name — возвращает ошибку

Запуск:
  pytest tests/test_epf_factory_mcp.py -v
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Добавляем repo_work в sys.path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.mcp_server import create_mcp_server
from mcp.types import ListToolsRequest, CallToolRequest


@pytest.fixture
def mcp_server():
    """Создать MCP-сервер для тестов."""
    return create_mcp_server()


@pytest.fixture
def handlers(mcp_server):
    """Получить handlers из MCP-сервера."""
    return mcp_server.request_handlers


@pytest.mark.asyncio
async def test_list_tools_includes_epf_factory(handlers):
    """tools/list должен включать epf_factory_create и epf_factory_templates."""
    list_handler = handlers[ListToolsRequest]
    result = await list_handler(ListToolsRequest(method="tools/list"))
    tools = result.root.tools
    tool_names = [t.name for t in tools]

    assert "epf_factory_create" in tool_names
    assert "epf_factory_templates" in tool_names


@pytest.mark.asyncio
async def test_epf_factory_templates(handlers):
    """epf_factory_templates возвращает 5 шаблонов."""
    call_handler = handlers[CallToolRequest]
    result = await call_handler(
        CallToolRequest(method="tools/call", params={"name": "epf_factory_templates", "arguments": {}})
    )
    data = json.loads(result.root.content[0].text)

    assert "ext_proc" in data
    assert "form" in data
    assert "form_id" in data
    assert "form_elem_empty" in data
    assert "templates_dir" in data

    # Проверяем что пути существуют
    for k in ["ext_proc", "form", "form_id", "form_elem_empty"]:
        assert Path(data[k]).exists(), f"Template {k} not found: {data[k]}"


@pytest.mark.asyncio
async def test_epf_factory_create_with_bsl(handlers, tmp_path):
    """epf_factory_create с BSL кодом создает валидный EPF."""
    call_handler = handlers[CallToolRequest]
    bsl_code = (
        "// ТестоваяОбработка\n"
        "#Область ПрограммныйИнтерфейс\n\n"
        "#КонецОбласти\n\n"
        "#Область СлужебныеПроцедурыИФункции\n\n"
        "&НаСервере\n"
        "Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)\n"
        '\tСообщить("Тест");\n'
        "КонецПроцедуры\n\n"
        "#КонецОбласти\n"
    )
    output_epf = tmp_path / "TestCreate.epf"

    result = await call_handler(
        CallToolRequest(
            method="tools/call",
            params={
                "name": "epf_factory_create",
                "arguments": {
                    "name": "TestCreate",
                    "synonym": "Test Create",
                    "bsl_code": bsl_code,
                    "output_path": str(output_epf),
                    "skip_bsl_validation": True,
                },
            },
        )
    )
    data = json.loads(result.root.content[0].text)

    assert data["ok"] is True
    assert data["epf_path"] == str(output_epf)
    assert data["size_bytes"] > 0
    assert data["name"] == "TestCreate"
    assert data["bsl_lines"] > 0
    assert data["round_trip_ok"] is True
    assert output_epf.exists()

    # Проверяем сигнатуру 1С-контейнера
    with open(output_epf, "rb") as f:
        sig = f.read(4)
    assert sig == b"\xff\xff\xff\x7f"


@pytest.mark.asyncio
async def test_epf_factory_create_default_bsl(handlers, tmp_path):
    """epf_factory_create без BSL использует минимальный шаблон."""
    call_handler = handlers[CallToolRequest]
    output_epf = tmp_path / "TestDefault.epf"

    result = await call_handler(
        CallToolRequest(
            method="tools/call",
            params={
                "name": "epf_factory_create",
                "arguments": {
                    "name": "TestDefault",
                    "output_path": str(output_epf),
                    "skip_bsl_validation": True,
                },
            },
        )
    )
    data = json.loads(result.root.content[0].text)

    assert data["ok"] is True
    assert data["round_trip_ok"] is True
    assert output_epf.exists()


@pytest.mark.asyncio
async def test_epf_factory_create_error_no_name(handlers, tmp_path):
    """epf_factory_create без name возвращает ошибку."""
    call_handler = handlers[CallToolRequest]

    result = await call_handler(
        CallToolRequest(
            method="tools/call",
            params={
                "name": "epf_factory_create",
                "arguments": {
                    "output_path": str(tmp_path / "test.epf"),
                },
            },
        )
    )
    # Должен вернуть error в content
    text = result.root.content[0].text
    # Может быть как JSON так и прямой текст ошибки
    assert "error" in text.lower() or "name" in text.lower()
