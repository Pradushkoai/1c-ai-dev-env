"""
Тесты для DependencyGraph — граф зависимостей метаданных 1С.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.dependency_graph import (
    DependencyGraph, DependencyEdge, DependencyGraphResult, RELATION_TYPES,
)


@pytest.fixture
def setup(tmp_path):
    """Project root + PathManager + DependencyGraph."""
    for d in ["data/configs", "derived/configs", "runtime"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    from src.services.path_manager import PathManager
    pm = PathManager(project_root=tmp_path)
    return pm, tmp_path


def _write_metadata(tmp_path: Path, config_name: str, metadata: dict) -> None:
    """Записать unified-metadata-index.json для теста."""
    index_path = (
        tmp_path / "derived" / "configs" / config_name
        / "unified-metadata-index.json"
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────

class TestBuildGraph:
    """Тесты построения графа."""

    def test_build_empty_metadata(self, setup):
        """Пустой metadata → пустой граф."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {"objects": {}})

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        assert result.config_name == "test"
        assert len(result.nodes) == 0
        assert len(result.edges) == 0

    def test_build_missing_index_returns_warning(self, setup):
        """Нет unified-metadata-index.json → warning."""
        pm, tmp = setup
        dg = DependencyGraph()
        result = dg.build_from_metadata_index("missing", pm)

        assert len(result.warnings) >= 1
        assert any("не найден" in w for w in result.warnings)

    def test_build_with_attribute_ref(self, setup):
        """Реквизит ссылочного типа → ребро зависимости."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [{
                    "name": "Контрагенты",
                    "child_objects": {"attributes": [], "tabular_sections": []},
                }],
                "Document": [{
                    "name": "ЗаказКлиента",
                    "child_objects": {
                        "attributes": [
                            {"name": "Контрагент", "type": "CatalogRef.Контрагенты"},
                        ],
                        "tabular_sections": [],
                    },
                }],
            },
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        assert len(result.edges) >= 1
        # Document.ЗаказКлиента → Catalog.Контрагенты
        edge = next(
            e for e in result.edges
            if e.source == "Document.ЗаказКлиента"
            and e.target == "Catalog.Контрагенты"
        )
        assert edge.relation == "uses_attribute"
        assert "Контрагент" in edge.detail

    def test_build_with_tabular_section_ref(self, setup):
        """ТЧ со ссылочным типом → ребро."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [{
                    "name": "Товары",
                    "child_objects": {"attributes": [], "tabular_sections": []},
                }],
                "Document": [{
                    "name": "Поступление",
                    "child_objects": {
                        "attributes": [],
                        "tabular_sections": [{
                            "name": "Товары",
                            "attributes": [
                                {"name": "Номенклатура", "type": "CatalogRef.Товары"},
                            ],
                        }],
                    },
                }],
            },
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        edge = next(
            e for e in result.edges
            if e.source == "Document.Поступление"
            and e.target == "Catalog.Товары"
        )
        assert "ТЧ Товары" in edge.detail

    def test_build_with_register_recorder(self, setup):
        """Регистратор регистра → ребро (через RegisterRecords в документе)."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Documents": [{
                    "name": "Поступление",
                    "child_objects": {"attributes": [], "tabular_sections": []},
                    "properties": {"RegisterRecords": ["AccumulationRegister.ТоварыНаСкладах"]},
                }],
                "AccumulationRegisters": [{
                    "name": "ТоварыНаСкладах",
                }],
            },
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        edge = next(
            e for e in result.edges
            if e.source == "Document.Поступление"
            and e.target == "AccumulationRegister.ТоварыНаСкладах"
        )
        assert edge.relation == "registered_by"

    def test_build_with_subsystem(self, setup):
        """Объект в подсистеме → ребро."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [{
                    "name": "Товары",
                    "child_objects": {"attributes": [], "tabular_sections": []},
                }],
            },
            "subsystems": [{
                "name": "Склад",
                "content": ["Catalog.Товары"],
            }],
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        edge = next(
            e for e in result.edges
            if e.source == "Catalog.Товары"
            and e.target == "Subsystem.Склад"
        )
        assert edge.relation == "in_subsystem"

    def test_build_with_event_subscription(self, setup):
        """Подписка на событие → ребро к обработчику."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {},
            "event_subscriptions": [{
                "name": "ПриЗаписиТовара",
                "handler": "РаботаСТоварами.ПриЗаписиТовара",
            }],
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        edge = next(
            e for e in result.edges
            if e.source == "EventSubscription.ПриЗаписиТовара"
            and e.target == "CommonModule.РаботаСТоварами"
        )
        assert edge.relation == "event_handler"

    def test_self_reference_ignored(self, setup):
        """Ссылка объекта на себя не создаёт ребро."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [{
                    "name": "Иерархия",
                    "child_objects": {
                        "attributes": [
                            {"name": "Родитель", "type": "CatalogRef.Иерархия"},
                        ],
                        "tabular_sections": [],
                    },
                }],
            },
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        # Не должно быть ребра Catalog.Иерархия → Catalog.Иерархия
        self_refs = [e for e in result.edges if e.source == e.target]
        assert len(self_refs) == 0

    def test_multiple_ref_types_in_one_attribute(self, setup):
        """Составной тип с несколькими ссылками."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [
                    {"name": "Контрагенты", "child_objects": {"attributes": [], "tabular_sections": []}},
                    {"name": "Поставщики", "child_objects": {"attributes": [], "tabular_sections": []}},
                ],
                "Document": [{
                    "name": "Док",
                    "child_objects": {
                        "attributes": [
                            {"name": "Контрагент", "type": "CatalogRef.Контрагенты, CatalogRef.Поставщики"},
                        ],
                        "tabular_sections": [],
                    },
                }],
            },
        })

        dg = DependencyGraph()
        result = dg.build_from_metadata_index("test", pm)

        targets = {e.target for e in result.edges if e.source == "Document.Док"}
        assert "Catalog.Контрагенты" in targets
        assert "Catalog.Поставщики" in targets


# ─────────────────────────────────────────────

class TestQueries:
    """Тесты запросов к графу."""

    @pytest.fixture
    def graph_with_data(self, setup):
        """Граф с тестовыми данными."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [
                    {"name": "Контрагенты", "child_objects": {"attributes": [], "tabular_sections": []}},
                    {"name": "Товары", "child_objects": {"attributes": [], "tabular_sections": []}},
                ],
                "Document": [
                    {
                        "name": "ЗаказКлиента",
                        "child_objects": {
                            "attributes": [
                                {"name": "Контрагент", "type": "CatalogRef.Контрагенты"},
                                {"name": "Товар", "type": "CatalogRef.Товары"},
                            ],
                            "tabular_sections": [],
                        },
                    },
                    {
                        "name": "Реализация",
                        "child_objects": {
                            "attributes": [
                                {"name": "Контрагент", "type": "CatalogRef.Контрагенты"},
                            ],
                            "tabular_sections": [],
                        },
                    },
                ],
            },
        })

        dg = DependencyGraph()
        dg.build_from_metadata_index("test", pm)
        return dg

    def test_what_depends_on(self, graph_with_data):
        """what_depends_on возвращает зависимые объекты."""
        result = graph_with_data.what_depends_on("Catalog.Контрагенты")

        sources = {r["source"] for r in result}
        assert "Document.ЗаказКлиента" in sources
        assert "Document.Реализация" in sources

    def test_what_depends_on_empty(self, graph_with_data):
        """what_depends_on на несуществующий объект → пусто."""
        result = graph_with_data.what_depends_on("Catalog.Несуществующий")
        assert result == []

    def test_dependencies_of(self, graph_with_data):
        """dependencies_of возвращает зависимости объекта."""
        result = graph_with_data.dependencies_of("Document.ЗаказКлиента")

        targets = {r["target"] for r in result}
        assert "Catalog.Контрагенты" in targets
        assert "Catalog.Товары" in targets

    def test_find_unused_objects(self, graph_with_data):
        """find_unused_objects — объекты на которые никто не ссылается."""
        result = graph_with_data.find_unused_objects()

        # Document.ЗаказКлиента и Document.Реализация никто не использует
        # (на них нет ссылок)
        assert "Document.ЗаказКлиента" in result
        assert "Document.Реализация" in result
        # Catalog.Контрагенты используется → не должен быть в unused
        assert "Catalog.Контрагенты" not in result

    def test_find_root_objects(self, graph_with_data):
        """find_root_objects — на которые ссылаются, но сами ни на кого."""
        result = graph_with_data.find_root_objects()

        # Catalog.Контрагенты и Catalog.Товары — на них ссылаются, сами ни на кого
        assert "Catalog.Контрагенты" in result
        assert "Catalog.Товары" in result

    def test_transitive_dependencies(self, graph_with_data):
        """transitive_dependencies — все транзитивные зависимости."""
        # Document.ЗаказКлиента → Catalog.Контрагенты, Catalog.Товары
        result = graph_with_data.transitive_dependencies("Document.ЗаказКлиента")

        assert "Catalog.Контрагенты" in result
        assert "Catalog.Товары" in result

    def test_transitive_dependents(self, graph_with_data):
        """transitive_dependents — кто зависит от target."""
        result = graph_with_data.transitive_dependents("Catalog.Контрагенты")

        assert "Document.ЗаказКлиента" in result
        assert "Document.Реализация" in result

    def test_shortest_path(self, graph_with_data):
        """shortest_path между объектами."""
        # Document.ЗаказКлиента → Catalog.Контрагенты (прямая связь)
        path = graph_with_data.shortest_path("Document.ЗаказКлиента", "Catalog.Контрагенты")
        assert path is not None
        assert path[0] == "Document.ЗаказКлиента"
        assert path[-1] == "Catalog.Контрагенты"

    def test_shortest_path_no_path(self, graph_with_data):
        """shortest_path без пути → None."""
        # Catalog.Контрагенты не зависит от Catalog.Товары
        path = graph_with_data.shortest_path("Catalog.Контрагенты", "Catalog.Товары")
        assert path is None

    def test_get_stats(self, graph_with_data):
        """get_stats возвращает статистику."""
        stats = graph_with_data.get_stats()

        assert "nodes" in stats
        assert "edges" in stats
        assert "cycles" in stats
        assert "unused_objects" in stats
        assert "density" in stats
        assert "is_dag" in stats
        assert stats["nodes"] > 0
        assert stats["edges"] > 0
        # Граф без циклов (DAG)
        assert stats["is_dag"] is True

    def test_find_cycles_empty(self, graph_with_data):
        """find_cycles — нет циклов в простом графе."""
        cycles = graph_with_data.find_cycles()
        assert cycles == []

    def test_find_cycles_with_cycle(self, setup):
        """Циклическая зависимость находится."""
        pm, tmp = setup
        _write_metadata(tmp, "test", {
            "objects": {
                "Catalog": [
                    {
                        "name": "A",
                        "child_objects": {
                            "attributes": [{"name": "B", "type": "CatalogRef.B"}],
                            "tabular_sections": [],
                        },
                    },
                    {
                        "name": "B",
                        "child_objects": {
                            "attributes": [{"name": "A", "type": "CatalogRef.A"}],
                            "tabular_sections": [],
                        },
                    },
                ],
            },
        })

        dg = DependencyGraph()
        dg.build_from_metadata_index("test", pm)

        cycles = dg.find_cycles()
        assert len(cycles) >= 1


# ─────────────────────────────────────────────

class TestSerialization:
    """Тесты сериализации."""

    def test_to_dict_has_keys(self):
        """to_dict возвращает корректную структуру."""
        # Создаём минимальный граф
        dg = DependencyGraph()
        dg._graph.add_edge("A", "B", relation="test", detail="d")
        dg._edges.append(DependencyEdge("A", "B", "test", "d"))

        d = dg.to_dict()
        assert "config_name" in d
        assert "nodes" in d
        assert "edges" in d
        assert "stats" in d


# ─────────────────────────────────────────────

class TestExtractRefs:
    """Тесты утилиты _extract_refs."""

    def test_catalog_ref(self):
        refs = DependencyGraph._extract_refs("CatalogRef.Контрагенты")
        assert refs == [("Catalog", "Контрагенты")]

    def test_document_ref(self):
        refs = DependencyGraph._extract_refs("DocumentRef.Заказ")
        assert refs == [("Document", "Заказ")]

    def test_multiple_refs(self):
        refs = DependencyGraph._extract_refs("CatalogRef.А, CatalogRef.Б")
        assert ("Catalog", "А") in refs
        assert ("Catalog", "Б") in refs

    def test_cfg_prefix_stripped(self):
        refs = DependencyGraph._extract_refs("cfg:CatalogRef.Контрагенты")
        assert refs == [("Catalog", "Контрагенты")]

    def test_no_ref(self):
        refs = DependencyGraph._extract_refs("String(100)")
        assert refs == []

    def test_empty(self):
        refs = DependencyGraph._extract_refs("")
        assert refs == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
