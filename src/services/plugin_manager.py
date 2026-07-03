"""
S2: Plugin System — plugin interface через Python entry_points.

Позволяет сторонним разработчикам добавлять custom BSL analyzers
без изменения ядра проекта.

Использование (для разработчика плагина):
    1. Создать Python пакет с классом, реализующим AnalyserProtocol
    2. Зарегистрировать через entry_points в pyproject.toml
    3. pip install — плагин автоматически подхватывается

Использование (для пользователя):
    1c-ai plugin list  # список установленных плагинов
    1c-ai plugin enable <name>
    1c-ai plugin disable <name>
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Entry point group для регистрации плагинов
PLUGIN_ENTRY_POINT_GROUP = "1c_ai.analyzers"


@runtime_checkable
class AnalyserProtocol(Protocol):
    """Protocol для BSL analyzer плагинов.

    Любой класс, реализующий этот interface, может быть зарегистрирован
    как плагин через entry_points.

    Пример:
        class MyCustomAnalyzer:
            def get_name(self) -> str:
                return "my_custom"

            def get_rules(self) -> list[str]:
                return ["RULE001", "RULE002"]

            def check_file(self, file_path: Path) -> list[dict]:
                # Проверка BSL файла
                return [{"rule_id": "RULE001", "severity": "warning", ...}]
    """

    def get_name(self) -> str:
        """Уникальное имя analyzer."""
        ...

    def get_rules(self) -> list[str]:
        """Список rule IDs, которые проверяет analyzer."""
        ...

    def check_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Проверить BSL файл.

        Args:
            file_path: Путь к .bsl файлу.

        Returns:
            Список violations: [{rule_id, severity, line, message, file}].
        """
        ...


@dataclass
class PluginInfo:
    """Информация об установленном плагине."""

    name: str
    version: str
    entry_point: str
    enabled: bool = True
    analyzer_name: str = ""
    rules_count: int = 0


class PluginManager:
    """Менеджер плагинов для 1c-ai-dev-env (S2).

    Обнаруживает, загружает и управляет плагинами через Python entry_points.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, AnalyserProtocol] = {}
        self._disabled: set[str] = set()

    def discover_plugins(self) -> list[PluginInfo]:
        """Обнаружить установленные плагины через entry_points.

        Returns:
            Список PluginInfo для каждого найденного плагина.
        """
        plugins: list[PluginInfo] = []

        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
            for ep in eps:
                try:
                    analyzer = ep.load()
                    info = PluginInfo(
                        name=ep.name,
                        version=getattr(analyzer, "__version__", "unknown"),
                        entry_point=str(ep),
                        enabled=ep.name not in self._disabled,
                        analyzer_name=analyzer().get_name() if callable(analyzer) else "",
                        rules_count=len(analyzer().get_rules()) if callable(analyzer) else 0,
                    )
                    plugins.append(info)

                    if ep.name not in self._disabled:
                        self._plugins[ep.name] = analyzer()
                except Exception as e:
                    logger.warning("Failed to load plugin %s: %s", ep.name, e)
                    plugins.append(
                        PluginInfo(
                            name=ep.name,
                            version="error",
                            entry_point=str(ep),
                            enabled=False,
                        )
                    )
        except Exception as e:
            logger.debug("No plugins found or entry_points error: %s", e)

        return plugins

    def get_plugin(self, name: str) -> AnalyserProtocol | None:
        """Получить загруженный плагин по имени.

        Args:
            name: Имя плагина (entry_point name).

        Returns:
            AnalyserProtocol instance или None если не найден/отключён.
        """
        return self._plugins.get(name)

    def get_all_plugins(self) -> dict[str, AnalyserProtocol]:
        """Получить все загруженные и включённые плагины.

        Returns:
            dict[name, AnalyserProtocol].
        """
        return dict(self._plugins)

    def enable_plugin(self, name: str) -> bool:
        """Включить плагин.

        Args:
            name: Имя плагина.

        Returns:
            True если плагин был найден и включён.
        """
        if name in self._disabled:
            self._disabled.remove(name)
            # Перезагружаем плагины
            self._plugins.clear()
            self.discover_plugins()
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Отключить плагин.

        Args:
            name: Имя плагина.

        Returns:
            True если плагин был найден и отключён.
        """
        if name in self._plugins:
            self._disabled.add(name)
            del self._plugins[name]
            return True
        return False

    def is_enabled(self, name: str) -> bool:
        """Проверить, включён ли плагин.

        Args:
            name: Имя плагина.

        Returns:
            True если плагин включён.
        """
        return name in self._plugins

    def run_all_analyzers(self, file_path: Path) -> dict[str, list[dict[str, Any]]]:
        """Запустить все включённые плагины на файл.

        Args:
            file_path: Путь к .bsl файлу.

        Returns:
            dict[plugin_name, list[violations]].
        """
        results: dict[str, list[dict[str, Any]]] = {}
        for name, analyzer in self._plugins.items():
            try:
                violations = analyzer.check_file(file_path)
                results[name] = violations
            except Exception as e:
                logger.warning("Plugin %s failed on %s: %s", name, file_path, e)
                results[name] = [{"error": str(e)}]
        return results
