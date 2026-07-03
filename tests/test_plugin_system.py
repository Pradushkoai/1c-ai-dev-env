"""
S2: Тесты для Plugin System.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.plugin_manager import (
    AnalyserProtocol,
    PluginInfo,
    PluginManager,
    PLUGIN_ENTRY_POINT_GROUP,
)


# ============================================================================
# Тесты — AnalyserProtocol
# ============================================================================


class TestAnalyserProtocol:
    """Проверка AnalyserProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """AnalyserProtocol — runtime_checkable."""

        # Создаём класс, реализующий protocol
        class MyAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return ["R1"]

            def check_file(self, file_path: Path) -> list[dict]:
                return []

        analyzer = MyAnalyzer()
        assert isinstance(analyzer, AnalyserProtocol)

    def test_protocol_not_satisfied_without_methods(self) -> None:
        """Класс без методов не удовлетворяет protocol."""

        class NotAnAnalyzer:
            pass

        analyzer = NotAnAnalyzer()
        assert not isinstance(analyzer, AnalyserProtocol)


# ============================================================================
# Тесты — PluginManager
# ============================================================================


class TestPluginManager:
    """Проверка PluginManager."""

    def test_init(self) -> None:
        """PluginManager инициализируется."""
        pm = PluginManager()
        assert pm is not None
        assert pm.get_all_plugins() == {}

    def test_discover_no_plugins(self) -> None:
        """discover_plugins без установленных плагинов → пустой список."""
        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[]):
            plugins = pm.discover_plugins()
        assert plugins == []

    def test_discover_with_mock_plugin(self) -> None:
        """discover_plugins находит mock плагин."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        class MockAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return ["R1", "R2"]

            def check_file(self, file_path: Path) -> list[dict]:
                return [{"rule_id": "R1", "severity": "warning"}]

        mock_ep.load.return_value = MockAnalyzer

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = pm.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].name == "test_plugin"
        assert plugins[0].analyzer_name == "test"
        assert plugins[0].rules_count == 2

    def test_get_plugin(self) -> None:
        """get_plugin возвращает загруженный плагин."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        class MockAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return []

            def check_file(self, file_path: Path) -> list[dict]:
                return []

        mock_ep.load.return_value = MockAnalyzer

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            pm.discover_plugins()

        plugin = pm.get_plugin("test_plugin")
        assert plugin is not None
        assert plugin.get_name() == "test"

    def test_get_plugin_not_found(self) -> None:
        """get_plugin для несуществующего плагина → None."""
        pm = PluginManager()
        assert pm.get_plugin("nonexistent") is None

    def test_disable_plugin(self) -> None:
        """disable_plugin отключает плагин."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        class MockAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return []

            def check_file(self, file_path: Path) -> list[dict]:
                return []

        mock_ep.load.return_value = MockAnalyzer

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            pm.discover_plugins()

        assert pm.is_enabled("test_plugin") is True
        assert pm.disable_plugin("test_plugin") is True
        assert pm.is_enabled("test_plugin") is False
        assert pm.get_plugin("test_plugin") is None

    def test_disable_nonexistent_plugin(self) -> None:
        """disable_plugin для несуществующего → False."""
        pm = PluginManager()
        assert pm.disable_plugin("nonexistent") is False

    def test_enable_plugin(self) -> None:
        """enable_plugin включает ранее отключённый плагин."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        class MockAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return []

            def check_file(self, file_path: Path) -> list[dict]:
                return []

        mock_ep.load.return_value = MockAnalyzer

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            pm.discover_plugins()
            pm.disable_plugin("test_plugin")
            assert pm.enable_plugin("test_plugin") is True
            assert pm.is_enabled("test_plugin") is True

    def test_run_all_analyzers(self, tmp_path: Path) -> None:
        """run_all_analyzers запускает все плагины."""
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        class MockAnalyzer:
            def get_name(self) -> str:
                return "test"

            def get_rules(self) -> list[str]:
                return ["R1"]

            def check_file(self, file_path: Path) -> list[dict]:
                return [{"rule_id": "R1", "severity": "warning", "line": 1}]

        mock_ep.load.return_value = MockAnalyzer

        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("// test", encoding="utf-8")

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            pm.discover_plugins()

        results = pm.run_all_analyzers(bsl_file)
        assert "test_plugin" in results
        assert len(results["test_plugin"]) == 1
        assert results["test_plugin"][0]["rule_id"] == "R1"

    def test_run_all_analyzers_handles_errors(self, tmp_path: Path) -> None:
        """run_all_analyzers не падает при ошибке плагина."""
        mock_ep = MagicMock()
        mock_ep.name = "failing_plugin"

        class FailingAnalyzer:
            def get_name(self) -> str:
                return "failing"

            def get_rules(self) -> list[str]:
                return []

            def check_file(self, file_path: Path) -> list[dict]:
                raise RuntimeError("plugin error")

        mock_ep.load.return_value = FailingAnalyzer

        bsl_file = tmp_path / "test.bsl"
        bsl_file.write_text("// test", encoding="utf-8")

        pm = PluginManager()
        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            pm.discover_plugins()

        results = pm.run_all_analyzers(bsl_file)
        assert "failing_plugin" in results
        assert "error" in results["failing_plugin"][0]


# ============================================================================
# Тесты — константы
# ============================================================================


class TestPluginConstants:
    """Проверка констант."""

    def test_entry_point_group(self) -> None:
        """PLUGIN_ENTRY_POINT_GROUP = '1c_ai.analyzers'."""
        assert PLUGIN_ENTRY_POINT_GROUP == "1c_ai.analyzers"
