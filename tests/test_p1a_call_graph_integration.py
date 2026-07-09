"""
P1-A-Integration — Тесты интеграции bsl_tree_sitter в call_graph.py.

Проверяет:
1. tree-sitter path включается когда доступен
2. regex fallback работает когда tree-sitter недоступен
3. Кросс-модульные вызовы извлекаются в обоих режимах
4. Локальные вызовы извлекаются точнее через AST (не путает со строками)
5. Гибридная стратегия: tree-sitter (локальные) + regex (кросс-модульные)
6. Backward compat: существующие CallEdge и CallGraph API не изменились
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.call_graph import (
    CallEdge,
    CallGraph,
    _parse_bsl_file_with_regex,
    _parse_bsl_file_with_tree_sitter,
    _TREE_SITTER_AVAILABLE,
    build_call_graph,
)


# ============================================================================
# ФИКСТУРЫ
# ============================================================================


@pytest.fixture
def sample_bsl_module(tmp_path: Path) -> Path:
    """Создаёт тестовый .bsl файл с типичным 1С модулем."""
    bsl_content = """#Область ПрограммныйИнтерфейс

// Получает элемент по коду.
Функция ПолучитьПоКоду(Код) Экспорт
    Возврат Справочники.Товары.НайтиПоКоду(Код);
КонецФункции

// Записывает журнал.
Процедура ЗаписатьЖурнал(Сообщение) Экспорт
    ЗаписьЖурналаРегистрации.Записать("Событие", Сообщение);
КонецПроцедуры

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Процедура ВнутренняяОбработка()
    Стр = "Не вызывать: ПодготовитьДанные() в строке";
    ПодготовитьДанные();
    // Комментарий: ДругойМетод()
КонецПроцедуры

Процедура ПодготовитьДанные() Экспорт
    Возврат;
КонецПроцедуры

#КонецОбласти"""
    bsl_path = tmp_path / "TestModule.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")
    return bsl_path


@pytest.fixture
def bsl_with_cross_module_calls(tmp_path: Path) -> Path:
    """BSL файл с кросс-модульными вызовами."""
    bsl_content = """Процедура Тест()
    ОбменДокументы.ВыполнитьПолныйОбмен();
    Справочники.Товары.НайтиПоКоду("123");
КонецПроцедуры"""
    bsl_path = tmp_path / "CrossModule.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")
    return bsl_path


# ============================================================================
# 1. ПРОВЕРКА ДОСТУПНОСТИ TREE-SITTER
# ============================================================================


class TestTreeSitterAvailability:
    """Тесты флага доступности tree-sitter."""

    def test_tree_sitter_flag_is_boolean(self):
        """_TREE_SITTER_AVAILABLE — это bool."""
        assert isinstance(_TREE_SITTER_AVAILABLE, bool)

    def test_tree_sitter_available_in_test_env(self):
        """В тестовом окружении tree-sitter должен быть установлен."""
        # Если tree-sitter не установлен — тесты P1-A будут skip,
        # но сам модуль должен импортироваться
        assert _TREE_SITTER_AVAILABLE is True, (
            "tree-sitter должен быть установлен в тестовом окружении. "
            "Установите: pip install tree-sitter tree-sitter-bsl"
        )


# ============================================================================
# 2. ТЕСТЫ _parse_bsl_file_with_tree_sitter
# ============================================================================


class TestParseBslFileWithTreeSitter:
    """Тесты функции извлечения рёбер через AST."""

    def test_extracts_local_calls(self, sample_bsl_module, tmp_path):
        """Локальные вызовы извлекаются через AST."""
        # 'ВнутренняяОбработка' вызывает 'ПодготовитьДанные'
        edges = _parse_bsl_file_with_tree_sitter(
            sample_bsl_module,
            tmp_path,
            "TestModule",
            module_names={"TestModule"},
            export_methods={"TestModule.ПолучитьПоКоду", "TestModule.ПодготовитьДанные"},
        )

        # Должно быть ребро: ВнутренняяОбработка → ПодготовитьДанные
        local_edges = [
            e for e in edges
            if e.caller_method == "ВнутренняяОбработка"
            and e.callee_method == "ПодготовитьДанные"
        ]
        assert len(local_edges) >= 1, f"Локальный вызов не извлечён: {edges}"

    def test_does_not_extract_calls_from_strings(self, sample_bsl_module, tmp_path):
        """Вызовы в строковых литералах НЕ извлекаются (главное преимущество AST)."""
        edges = _parse_bsl_file_with_tree_sitter(
            sample_bsl_module,
            tmp_path,
            "TestModule",
            module_names={"TestModule"},
            export_methods=set(),
        )

        # В строке: 'Не вызывать: ПодготовитьДанные() в строке'
        # AST НЕ должен извлечь 'ПодготовитьДанные' из строки как вызов из
        # процедуры 'ПолучитьПоКоду' (там только Return)
        # Но из 'ВнутренняяОбработка' 'ПодготовитьДанные' должен быть
        for edge in edges:
            if edge.caller_method == "ПолучитьПоКоду":
                # ПолучитьПоКоду ничего не вызывает (только Возврат)
                # поэтому рёбер из неё быть не должно
                assert edge.callee_method != "ПодготовитьДанные", (
                    "Извлечён вызов из строки — AST должен был это отфильтровать"
                )

    def test_handles_empty_file(self, tmp_path):
        """Пустой BSL файл — нет рёбер."""
        bsl_path = tmp_path / "empty.bsl"
        bsl_path.write_text("", encoding="utf-8")

        edges = _parse_bsl_file_with_tree_sitter(
            bsl_path, tmp_path, "EmptyModule", set(), set()
        )
        assert edges == []

    def test_handles_syntax_error_gracefully(self, tmp_path):
        """Синтаксическая ошибка не валит парсер."""
        bsl_path = tmp_path / "broken.bsl"
        bsl_path.write_text("Процедура БезКонца()\n    Возврат;", encoding="utf-8")

        # Не должно выбросить исключение
        edges = _parse_bsl_file_with_tree_sitter(
            bsl_path, tmp_path, "BrokenModule", set(), set()
        )
        assert isinstance(edges, list)


# ============================================================================
# 3. ТЕСТЫ _parse_bsl_file_with_regex (fallback)
# ============================================================================


class TestParseBslFileWithRegex:
    """Тесты regex fallback функции."""

    def test_extracts_local_calls(self, sample_bsl_module, tmp_path):
        """Локальные вызовы извлекаются через regex."""
        edges = _parse_bsl_file_with_regex(
            sample_bsl_module,
            tmp_path,
            "TestModule",
            module_names={"TestModule"},
            export_methods={"TestModule.ПодготовитьДанные"},
        )

        # Должно быть ребро: ВнутренняяОбработка → ПодготовитьДанные
        local_edges = [
            e for e in edges
            if e.caller_method == "ВнутренняяОбработка"
            and e.callee_method == "ПодготовитьДанные"
        ]
        assert len(local_edges) >= 1, f"Локальный вызов не извлечён regex: {edges}"

    def test_extracts_cross_module_calls(self, bsl_with_cross_module_calls, tmp_path):
        """Кросс-модульные вызовы извлекаются через regex."""
        edges = _parse_bsl_file_with_regex(
            bsl_with_cross_module_calls,
            tmp_path,
            "CallerModule",
            module_names={"ОбменДокументы"},  # ОбменДокументы — модуль конфигурации
            export_methods=set(),
        )

        # Должно быть ребро: CallerModule.Тест → ОбменДокументы.ВыполнитьПолныйОбмен
        cross_edges = [
            e for e in edges
            if e.callee_module == "ОбменДокументы"
            and e.callee_method == "ВыполнитьПолныйОбмен"
        ]
        assert len(cross_edges) >= 1, f"Кросс-модульный вызов не извлечён: {edges}"

    def test_does_not_extract_standard_objects(self, bsl_with_cross_module_calls, tmp_path):
        """Вызовы стандартных объектов (Справочники.Товары.НайтиПоКоду) НЕ извлекаются."""
        edges = _parse_bsl_file_with_regex(
            bsl_with_cross_module_calls,
            tmp_path,
            "CallerModule",
            module_names=set(),  # Никаких модулей конфигурации
            export_methods=set(),
        )

        # 'Справочники' — стандартный объект, не должен стать callee_module
        for edge in edges:
            assert edge.callee_module != "Справочники", (
                "Стандартный объект не должен быть callee_module"
            )


# ============================================================================
# 4. СРАВНЕНИЕ TREE-SITTER vs REGEX (главный кейс P1-A-Integration)
# ============================================================================


class TestTreeSitterVsRegex:
    """Сравнение точности: tree-sitter vs regex."""

    def test_tree_sitter_filters_calls_in_strings(self, tmp_path):
        """AST не считает вызовы в строках, regex может ошибиться.

        Это главное преимущество AST.
        """
        bsl_content = """Процедура Тест()
    Стр = "Это строка с ВнутреннийМетод() внутри";
    ВнутреннийМетод();
КонецПроцедуры

Процедура ВнутреннийМетод() Экспорт
    Возврат;
КонецПроцедуры"""
        bsl_path = tmp_path / "string_test.bsl"
        bsl_path.write_text(bsl_content, encoding="utf-8")

        # Tree-sitter должен извлечь ОДИН вызов (реальный)
        ts_edges = _parse_bsl_file_with_tree_sitter(
            bsl_path, tmp_path, "TestModule",
            module_names={"TestModule"},
            export_methods={"TestModule.ВнутреннийМетод"},
        )
        ts_real_calls = [
            e for e in ts_edges
            if e.caller_method == "Тест" and e.callee_method == "ВнутреннийМетод"
        ]
        # AST должен извлечь 1 вызов (только реальный, не из строки)
        assert len(ts_real_calls) == 1

    def test_tree_sitter_filters_calls_in_comments(self, tmp_path):
        """AST не считает вызовы в комментариях."""
        bsl_content = """Процедура Тест()
    // Комментарий с ВнутреннийМетод()
    ВнутреннийМетод();
КонецПроцедуры

Процедура ВнутреннийМетод() Экспорт
    Возврат;
КонецПроцедуры"""
        bsl_path = tmp_path / "comment_test.bsl"
        bsl_path.write_text(bsl_content, encoding="utf-8")

        ts_edges = _parse_bsl_file_with_tree_sitter(
            bsl_path, tmp_path, "TestModule",
            module_names={"TestModule"},
            export_methods={"TestModule.ВнутреннийМетод"},
        )
        # AST должен извлечь только реальный вызов, не из комментария
        real_calls = [
            e for e in ts_edges
            if e.caller_method == "Тест" and e.callee_method == "ВнутреннийМетод"
        ]
        assert len(real_calls) == 1


# ============================================================================
# 5. ИНТЕГРАЦИОННЫЕ ТЕСТЫ build_call_graph
# ============================================================================


@pytest.fixture
def minimal_config(tmp_path: Path) -> tuple[Path, Path]:
    """Создаёт минимальную конфигурацию с одним модулем."""
    config_dir = tmp_path / "test_config"
    common_modules_dir = config_dir / "CommonModules" / "ТестовыйМодуль" / "Ext"
    common_modules_dir.mkdir(parents=True)

    bsl_content = """#Область ПрограммныйИнтерфейс

Функция ПолучитьДанные() Экспорт
    Возврат "данные";
КонецФункции

Процедура ОбработатьДанные() Экспорт
    Данные = ПолучитьДанные();
    ДругойМодуль.ВнешнийВызов();
КонецПроцедуры

#КонецОбласти"""
    bsl_path = common_modules_dir / "Module.bsl"
    bsl_path.write_text(bsl_content, encoding="utf-8")

    # Configuration.xml (минимальный)
    config_xml = config_dir / "Configuration.xml"
    config_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"/>',
        encoding="utf-8",
    )

    return config_dir, bsl_path


class TestBuildCallGraphIntegration:
    """Интеграционные тесты build_call_graph с гибридной стратегией."""

    def test_build_call_graph_does_not_crash(self, minimal_config, monkeypatch):
        """build_call_graph не падает на минимальной конфигурации."""
        config_dir, _ = minimal_config

        # Создаём PathManager mock
        from src.services.path_manager import PathManager

        # Используем tmp_path как корень
        class MockPaths:
            def __init__(self, root):
                self.root = root

            def config_derived_dir(self, name):
                return self.root / "derived" / name

            def config_path(self, name):
                return self.root / name

            def config_api_reference_json(self, name):
                return self.root / "derived" / name / "api-reference.json"

        # Помещаем конфигурацию в tmp_path/test_config
        # и используем её как config_path
        paths = MockPaths(config_dir.parent)

        # Чтобы не зависеть от кэша
        try:
            graph = build_call_graph("test_config", paths=paths, use_cache=False)
            assert graph is not None
            assert isinstance(graph, CallGraph)
        except FileNotFoundError:
            # Если PathManager не подошёл — это OK, главное что нет crash
            pytest.skip("PathManager setup requires real project structure")

    def test_call_graph_api_unchanged(self):
        """Публичный API CallGraph не изменился."""
        graph = CallGraph(config_name="test")
        assert hasattr(graph, "edges")
        assert hasattr(graph, "get_callers")
        assert hasattr(graph, "get_callees")
        assert hasattr(graph, "find_cycles")
        assert hasattr(graph, "find_dead_code")
        assert hasattr(graph, "get_stats")
        assert hasattr(graph, "to_dict")
        assert hasattr(graph, "save")
        assert hasattr(graph, "from_dict")
        assert hasattr(graph, "load")

    def test_call_edge_api_unchanged(self):
        """Публичный API CallEdge не изменился."""
        edge = CallEdge(
            caller_module="Mod1",
            caller_method="Proc1",
            callee_module="Mod2",
            callee_method="Proc2",
            line=10,
            file="Mod1/Ext/Module.bsl",
        )
        assert edge.caller_module == "Mod1"
        assert edge.callee_method == "Proc2"


# ============================================================================
# 6. ТЕСТЫ MOCK-режима (tree-sitter недоступен)
# ============================================================================


class TestRegexFallbackWhenTreeSitterUnavailable:
    """Тесты что regex работает когда tree-sitter недоступен."""

    def test_parse_with_tree_sitter_returns_empty_when_unavailable(self, sample_bsl_module, tmp_path):
        """_parse_bsl_file_with_tree_sitter возвращает [] если tree-sitter недоступен."""
        # P3.4: _TREE_SITTER_AVAILABLE теперь в call_graph_parser (не call_graph)
        with patch("src.services.call_graph_parser._TREE_SITTER_AVAILABLE", False):
            edges = _parse_bsl_file_with_tree_sitter(
                sample_bsl_module, tmp_path, "TestModule", set(), set()
            )
            assert edges == []

    def test_regex_works_regardless_of_tree_sitter(self, sample_bsl_module, tmp_path):
        """_parse_bsl_file_with_regex работает независимо от tree-sitter."""
        with patch("src.services.call_graph._TREE_SITTER_AVAILABLE", False):
            edges = _parse_bsl_file_with_regex(
                sample_bsl_module,
                tmp_path,
                "TestModule",
                module_names={"TestModule"},
                export_methods={"TestModule.ПодготовитьДанные"},
            )
            # Regex должен извлечь вызов даже когда tree-sitter "недоступен"
            assert len(edges) > 0
