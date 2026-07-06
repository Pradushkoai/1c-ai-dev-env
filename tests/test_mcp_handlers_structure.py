"""
Тесты для src/mcpserver/handlers/structure.py — get_object_structure, get_skd_schema, get_form_structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mcpserver.handlers.structure import (
    handle_get_form_structure,
    handle_get_object_structure,
    handle_get_skd_schema,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = Path("/repo")
    return project


# ─── handle_get_object_structure ───


class TestHandleGetObjectStructure:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_get_object_structure(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unified_index_not_found(self, tmp_path):
        project = _make_project()
        project.paths.root = tmp_path
        data = _parse(await handle_get_object_structure(project, {"config_name": "ut11"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_all_objects(self, tmp_path):
        project = _make_project()
        # Create unified-metadata-index.json
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        unified_path = derived_dir / "unified-metadata-index.json"
        unified_path.write_text(
            json.dumps(
                {
                    "objects": {
                        "Catalog": [
                            {
                                "name": "Склады",
                                "type": "Catalog",
                                "synonym": "Склады",
                                "child_objects": {"attributes": [], "tabular_sections": [], "forms": []},
                            }
                        ],
                        "Document": [
                            {
                                "name": "Заказ",
                                "type": "Document",
                                "synonym": "Заказ",
                                "child_objects": {
                                    "attributes": [{"name": "Клиент"}],
                                    "tabular_sections": [],
                                    "forms": [],
                                },
                            }
                        ],
                    },
                    "stats": {"total": 2},
                    "configuration": {"properties": {"name": "УТ 11"}},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_object_structure(project, {"config_name": "ut11"}))
        assert data["total_objects"] == 2
        assert data["config"] == "ut11"

    @pytest.mark.asyncio
    async def test_filter_by_type(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        unified_path = derived_dir / "unified-metadata-index.json"
        unified_path.write_text(
            json.dumps(
                {
                    "objects": {
                        "Catalog": [{"name": "Склады", "type": "Catalog", "child_objects": {}}],
                        "Document": [{"name": "Заказ", "type": "Document", "child_objects": {}}],
                    },
                    "stats": {},
                    "configuration": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_object_structure(project, {"config_name": "ut11", "object_type": "Catalog"}))
        assert data["total_objects"] == 1
        assert data["objects"][0]["name"] == "Склады"

    @pytest.mark.asyncio
    async def test_specific_object_found(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        unified_path = derived_dir / "unified-metadata-index.json"
        unified_path.write_text(
            json.dumps(
                {
                    "objects": {
                        "Catalog": [{"name": "Склады", "type": "Catalog", "attributes": ["код"]}],
                    },
                    "stats": {},
                    "configuration": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_object_structure(project, {"config_name": "ut11", "object_name": "Склады"}))
        assert data["name"] == "Склады"

    @pytest.mark.asyncio
    async def test_object_not_found_with_suggestions(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        unified_path = derived_dir / "unified-metadata-index.json"
        unified_path.write_text(
            json.dumps(
                {
                    "objects": {
                        "Catalog": [
                            {"name": "Склады", "type": "Catalog"},
                            {"name": "СкладыОсновной", "type": "Catalog"},
                        ],
                    },
                    "stats": {},
                    "configuration": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(
            await handle_get_object_structure(project, {"config_name": "ut11", "object_name": "несуществующий"})
        )
        assert "error" in data
        assert "suggestions" in data


# ─── handle_get_skd_schema ───


class TestHandleGetSkdSchema:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_get_skd_schema(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_skd_index_not_found(self, tmp_path):
        project = _make_project()
        project.paths.root = tmp_path
        data = _parse(await handle_get_skd_schema(project, {"config_name": "ut11"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_all_schemas(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        skd_path = derived_dir / "skd-index.json"
        skd_path.write_text(
            json.dumps(
                {
                    "schemas": [
                        {
                            "name": "Схема1",
                            "parent_type": "Report",
                            "parent_name": "Отчет1",
                            "schema": {"data_sets": [], "parameters": []},
                        },
                        {
                            "name": "Схема2",
                            "parent_type": "DataProcessor",
                            "parent_name": "Обработка1",
                            "schema": {"data_sets": [{"fields": []}], "parameters": []},
                        },
                    ],
                    "stats": {"total": 2},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_skd_schema(project, {"config_name": "ut11"}))
        assert len(data["schemas"]) == 2
        assert data["schemas"][0]["name"] == "Схема1"

    @pytest.mark.asyncio
    async def test_specific_schema_found(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        skd_path = derived_dir / "skd-index.json"
        skd_path.write_text(
            json.dumps(
                {
                    "schemas": [
                        {"name": "Схема1", "parent_name": "Отчет1", "schema": {"data_sets": []}},
                    ],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_skd_schema(project, {"config_name": "ut11", "report_name": "Отчет1"}))
        assert data["parent_name"] == "Отчет1"

    @pytest.mark.asyncio
    async def test_schema_not_found_with_suggestions(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        skd_path = derived_dir / "skd-index.json"
        skd_path.write_text(
            json.dumps(
                {
                    "schemas": [{"name": "Схема1", "parent_name": "Отчет1"}],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_skd_schema(project, {"config_name": "ut11", "report_name": "несуществующий"}))
        assert "error" in data


# ─── handle_get_form_structure ───


class TestHandleGetFormStructure:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_get_form_structure(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_form_index_not_found(self, tmp_path):
        project = _make_project()
        project.paths.root = tmp_path
        data = _parse(await handle_get_form_structure(project, {"config_name": "ut11"}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_all_forms(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        form_path = derived_dir / "form-index.json"
        form_path.write_text(
            json.dumps(
                {
                    "forms": [
                        {
                            "name": "ФормаСписка",
                            "parent_type": "Catalog",
                            "parent_name": "Склады",
                            "form": {"element_count": 10, "events": []},
                        },
                        {
                            "name": "ФормаЭлемента",
                            "parent_type": "Catalog",
                            "parent_name": "Склады",
                            "form": {"element_count": 20, "events": ["ПриОткрытии"]},
                        },
                    ],
                    "stats": {"total": 2},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_form_structure(project, {"config_name": "ut11"}))
        assert len(data["forms"]) == 2

    @pytest.mark.asyncio
    async def test_filter_by_parent_name(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        form_path = derived_dir / "form-index.json"
        form_path.write_text(
            json.dumps(
                {
                    "forms": [
                        {"name": "Форма1", "parent_name": "Склады", "form": {"element_count": 5, "events": []}},
                        {"name": "Форма2", "parent_name": "Заказы", "form": {"element_count": 3, "events": []}},
                    ],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_form_structure(project, {"config_name": "ut11", "parent_name": "Склады"}))
        assert len(data["forms"]) == 1
        assert data["forms"][0]["name"] == "Форма1"

    @pytest.mark.asyncio
    async def test_specific_form_found(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        form_path = derived_dir / "form-index.json"
        form_path.write_text(
            json.dumps(
                {
                    "forms": [
                        {"name": "ФормаСписка", "parent_name": "Склады", "form": {"element_count": 10}},
                    ],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_form_structure(project, {"config_name": "ut11", "form_name": "ФормаСписка"}))
        assert data["name"] == "ФормаСписка"

    @pytest.mark.asyncio
    async def test_form_not_found_with_suggestions(self, tmp_path):
        project = _make_project()
        derived_dir = tmp_path / "derived" / "configs" / "ut11"
        derived_dir.mkdir(parents=True)
        form_path = derived_dir / "form-index.json"
        form_path.write_text(
            json.dumps(
                {
                    "forms": [{"name": "ФормаСписка", "parent_name": "Склады"}],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
        project.paths.root = tmp_path

        data = _parse(await handle_get_form_structure(project, {"config_name": "ut11", "form_name": "несуществующая"}))
        assert "error" in data
