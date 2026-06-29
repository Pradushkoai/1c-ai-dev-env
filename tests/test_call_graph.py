"""
Тесты для графа вызовов методов (call_graph.py).
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.services.call_graph import (
    CallGraph, CallEdge, build_call_graph,
    _get_module_name_from_path, _strip_comments, _find_current_procedure,
)


@pytest.fixture
def mock_paths(tmp_path):
    """Mock PathManager с реальной файловой структурой."""
    paths = MagicMock()
    paths.root = tmp_path

    # Создаём структуру конфигурации
    config_dir = tmp_path / "configs" / "test_cfg"
    config_dir.mkdir(parents=True)

    # CommonModules/МодульА/Ext/Module.bsl
    mod_a_dir = config_dir / "CommonModules" / "МодульА" / "Ext"
    mod_a_dir.mkdir(parents=True)
    (mod_a_dir / "Module.bsl").write_text(
        "Процедура МетодА() Экспорт\n"
        "\tМодульБ.МетодБ();\n"
        "\tЛокальныйМетод();\n"
        "КонецПроцедуры\n"
        "\n"
        "Процедура ЛокальныйМетод() Экспорт\n"
        "\tМодульБ.ДругойМетод();\n"
        "КонецПроцедуры\n",
        encoding='utf-8'
    )

    # CommonModules/МодульБ/Ext/Module.bsl
    mod_b_dir = config_dir / "CommonModules" / "МодульБ" / "Ext"
    mod_b_dir.mkdir(parents=True)
    (mod_b_dir / "Module.bsl").write_text(
        "Процедура МетодБ() Экспорт\n"
        "\t// Ничего не вызывает\n"
        "КонецПроцедуры\n"
        "\n"
        "Процедура ДругойМетод() Экспорт\n"
        "КонецПроцедуры\n",
        encoding='utf-8'
    )

    # api-reference.json
    derived_dir = tmp_path / "derived" / "configs" / "test_cfg"
    derived_dir.mkdir(parents=True)
    api_data = [
        {"name": "МодульА", "methods": [
            {"name": "МетодА"},
            {"name": "ЛокальныйМетод"},
        ]},
        {"name": "МодульБ", "methods": [
            {"name": "МетодБ"},
            {"name": "ДругойМетод"},
        ]},
    ]
    (derived_dir / "api-reference.json").write_text(
        json.dumps(api_data, ensure_ascii=False), encoding='utf-8'
    )

    paths.config_path.return_value = config_dir
    paths.config_api_reference_json.return_value = derived_dir / "api-reference.json"

    return paths


# ============ CallEdge / CallGraph ============

class TestCallGraph:
    def test_empty_graph(self):
        g = CallGraph(config_name="test")
        assert g.get_stats()["total_edges"] == 0
        assert g.get_callers("A", "B") == []
        assert g.get_callees("A", "B") == []

    def test_add_edges_and_query(self):
        g = CallGraph(config_name="test")
        g.edges.append(CallEdge("ModA", "FuncA", "ModB", "FuncB", 10, "file.bsl"))
        g.edges.append(CallEdge("ModC", "FuncC", "ModB", "FuncB", 20, "file2.bsl"))
        g._reindex()

        callers = g.get_callers("ModB", "FuncB")
        assert len(callers) == 2

        callees = g.get_callees("ModA", "FuncA")
        assert len(callees) == 1
        assert callees[0]["method"] == "FuncB"

    def test_find_dead_code(self):
        g = CallGraph(config_name="test")
        g.edges.append(CallEdge("ModA", "FuncA", "ModB", "FuncB", 1, "f.bsl"))
        g._reindex()

        export_methods = [("ModA", "FuncA"), ("ModB", "FuncB"), ("ModC", "FuncC")]
        dead = g.find_dead_code(export_methods)
        # ModC.FuncC — никто не вызывает
        assert ("ModC", "FuncC") in dead
        assert ("ModB", "FuncB") not in dead  # вызывается из ModA.FuncA
        assert ("ModA", "FuncA") in dead  # никто не вызывает ModA.FuncA

    def test_find_cycles(self):
        g = CallGraph(config_name="test")
        # A → B → A (цикл)
        g.edges.append(CallEdge("ModA", "FuncA", "ModB", "FuncB", 1, "f.bsl"))
        g.edges.append(CallEdge("ModB", "FuncB", "ModA", "FuncA", 2, "f2.bsl"))
        g._reindex()

        cycles = g.find_cycles()
        assert len(cycles) > 0

    def test_no_cycles(self):
        g = CallGraph(config_name="test")
        g.edges.append(CallEdge("ModA", "FuncA", "ModB", "FuncB", 1, "f.bsl"))
        g._reindex()

        cycles = g.find_cycles()
        assert len(cycles) == 0

    def test_to_dict(self):
        g = CallGraph(config_name="test")
        g.edges.append(CallEdge("ModA", "FuncA", "ModB", "FuncB", 10, "file.bsl"))
        g._reindex()

        d = g.to_dict()
        assert d["config_name"] == "test"
        assert d["stats"]["total_edges"] == 1
        assert len(d["edges"]) == 1


# ============ Helper functions ============

class TestHelpers:
    def test_get_module_name_common_module(self, tmp_path):
        configs_dir = tmp_path / "configs"
        bsl_path = configs_dir / "CommonModules" / "ОбменДокументы" / "Ext" / "Module.bsl"
        bsl_path.parent.mkdir(parents=True)
        bsl_path.touch()
        assert _get_module_name_from_path(bsl_path, configs_dir) == "ОбменДокументы"

    def test_get_module_name_managed_app(self, tmp_path):
        configs_dir = tmp_path / "configs"
        bsl_path = configs_dir / "Ext" / "ManagedApplicationModule.bsl"
        bsl_path.parent.mkdir(parents=True)
        bsl_path.touch()
        assert _get_module_name_from_path(bsl_path, configs_dir) == "ManagedApplicationModule"

    def test_get_module_name_common_form(self, tmp_path):
        configs_dir = tmp_path / "configs"
        bsl_path = configs_dir / "CommonForms" / "ФормаАвторизации" / "Ext" / "Form" / "Module.bsl"
        bsl_path.parent.mkdir(parents=True)
        bsl_path.touch()
        assert _get_module_name_from_path(bsl_path, configs_dir) == "ФормаАвторизации"

    def test_strip_comments(self):
        assert _strip_comments("Код(); // комментарий") == "Код(); "
        assert _strip_comments("// только комментарий") == ""
        assert _strip_comments('Стр = "// не комментарий"') == 'Стр = "// не комментарий"'

    def test_find_current_procedure(self):
        lines = [
            "Процедура МояПроцедура()",
            "\tПерем = 1;",
            "\tВызов();",
            "КонецПроцедуры",
        ]
        assert _find_current_procedure(lines, 2) == "МояПроцедура"
        assert _find_current_procedure(lines, 0) == "МояПроцедура"

    def test_find_current_function(self):
        lines = [
            "Функция МояФункция()",
            "\tВозврат 1;",
        ]
        assert _find_current_procedure(lines, 1) == "МояФункция"


# ============ build_call_graph ============

class TestBuildCallGraph:
    def test_build_simple_graph(self, mock_paths):
        graph = build_call_graph("test_cfg", mock_paths)

        # Должны найти вызовы:
        # МодульА.МетодА → МодульБ.МетодБ
        # МодульА.МетодА → ЛокальныйМетод (локальный)
        # МодульА.ЛокальныйМетод → МодульБ.ДругойМетод
        assert graph.get_stats()["total_edges"] >= 2

        # Проверяем callees
        callees = graph.get_callees("МодульА", "МетодА")
        callee_names = [c["method"] for c in callees]
        assert "МетодБ" in callee_names

    def test_dead_code_detection(self, mock_paths):
        graph = build_call_graph("test_cfg", mock_paths)
        export = [("МодульА", "МетодА"), ("МодульА", "ЛокальныйМетод"),
                  ("МодульБ", "МетодБ"), ("МодульБ", "ДругойМетод")]
        dead = graph.find_dead_code(export)
        # МетодБ и ДругойМетод вызываются → не мёртвый
        dead_names = [(m, me) for m, me in dead]
        assert ("МодульБ", "МетодБ") not in dead_names
        assert ("МодульБ", "ДругойМетод") not in dead_names

    def test_callers_query(self, mock_paths):
        graph = build_call_graph("test_cfg", mock_paths)
        callers = graph.get_callers("МодульБ", "МетодБ")
        assert len(callers) >= 1
        assert callers[0]["module"] == "МодульА"
        assert callers[0]["method"] == "МетодА"

    def test_no_cycles_in_simple_graph(self, mock_paths):
        graph = build_call_graph("test_cfg", mock_paths)
        cycles = graph.find_cycles()
        assert len(cycles) == 0

    def test_empty_config(self, tmp_path):
        paths = MagicMock()
        paths.root = tmp_path
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir(parents=True)
        paths.config_path.return_value = empty_dir
        paths.config_api_reference_json.return_value = tmp_path / "nonexistent.json"

        graph = build_call_graph("empty", paths)
        assert graph.get_stats()["total_edges"] == 0
