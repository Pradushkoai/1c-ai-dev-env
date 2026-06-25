"""
Оркестратор проекта. Связывает все сервисы вместе.
"""
from __future__ import annotations

from pathlib import Path

from .models.config_registry import ConfigurationRegistry
from .services.path_manager import PathManager
from .services.config_manager import ConfigManager
from .services.bsl_analyzer import BSLAnalyzer


class Project:
    """
    Главный объект проекта — связывает все сервисы.

    Usage:
        project = Project()
        project.config_manager.add_from_zip("ut11", Path("ut11.zip"), "УТ 11")
        project.config_manager.build("ut11")
        project.bsl_analyzer.save_baseline(Path("file.bsl"))
        result = project.bsl_analyzer.diff(Path("file.bsl"))
    """

    def __init__(self, project_root: Path | None = None):
        self.paths = PathManager(project_root)

        self.registry = ConfigurationRegistry(
            self.paths.config_registry_path,
            self.paths.root,
        )

        self.config_manager = ConfigManager(self.registry, self.paths)

        self._bsl_analyzer: BSLAnalyzer | None = None

    @property
    def bsl_analyzer(self) -> BSLAnalyzer:
        """Lazy-init BSL analyzer (нужен Java)."""
        if self._bsl_analyzer is None:
            self._bsl_analyzer = BSLAnalyzer(
                self.paths.bsl_ls_binary,
                self.paths.bsl_ls_config,
            )
        return self._bsl_analyzer

    def validate(self) -> dict[str, bool]:
        """Проверить что все критичные пути существуют."""
        return self.paths.validate()

    def list_configs(self) -> list:
        """Список всех конфигураций."""
        return self.registry.list_all()

    def __repr__(self) -> str:
        return f"Project(root={self.paths.root}, configs={len(self.registry)})"
