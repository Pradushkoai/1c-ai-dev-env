"""
Оркестратор проекта. Связывает все сервисы вместе.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models.config_registry import ConfigurationRegistry
from .services.bsl_analyzer import BSLAnalyzer
from .services.config_manager import ConfigManager
from .services.path_manager import PathManager

# Маркеры корня проекта — файлы/директории, которые однозначно указывают,
# что текущий каталог является корнем 1c-ai-dev-env.
# Порядок важен: paths.env — наиболее специфичный маркер.
_PROJECT_ROOT_MARKERS: tuple[str, ...] = (
    "paths.env",
    "pyproject.toml",
    "manifest.json",
)


class Project:
    """
    Главный объект проекта — связывает все сервисы.

    Usage:
        project = Project()
        project.config_manager.add_from_zip("ut11", Path("ut11.zip"), "УТ 11")
        project.config_manager.build("ut11")
        project.bsl_analyzer.save_baseline(Path("file.bsl"))
        result = project.bsl_analyzer.diff(Path("file.bsl"))

    Alternative — авто-обнаружение корня (для скриптов CLI/SARIF):
        project = Project.from_cwd()
    """

    def __init__(self, project_root: Path | None = None):
        self.paths = PathManager(project_root)

        self.registry = ConfigurationRegistry(
            self.paths.config_registry_path,
            self.paths.root,
        )

        self.config_manager = ConfigManager(self.registry, self.paths)

        self._bsl_analyzer: BSLAnalyzer | None = None

    @classmethod
    def from_cwd(cls, start: Path | None = None) -> Project:
        """
        Создать Project, автоматически обнаружив корень репозитория.

        Поиск выполняется восходящим обходом от ``start`` (по умолчанию —
        ``Path.cwd()``) до первого каталога, содержащего один из маркеров
        корня (paths.env, pyproject.toml, manifest.json). Это эквивалент
        тому, как git ищет ``.git`` вверх по дереву каталогов.

        Переменная окружения ``ONEC_AI_DEV_ENV_ROOT`` имеет приоритет над
        авто-обнаружением — используется в тестах и CI для явного указания
        корня без копирования файловых маркеров.

        Args:
            start: Стартовая директория для поиска. По умолчанию — cwd.

        Returns:
            Project с корректно определённым project_root.

        Raises:
            FileNotFoundError: Если ни один маркер не найден вплоть до
                корня файловой системы (fallback на cwd не выполняется,
                чтобы не маскировать ошибки конфигурации в CI).
        """
        # 1. Явное указание через env (приоритет для CI/тестов).
        env_root = os.environ.get("ONEC_AI_DEV_ENV_ROOT")
        if env_root:
            root = Path(env_root).resolve()
            if not root.is_dir():
                raise FileNotFoundError(f"ONEC_AI_DEV_ENV_ROOT points to non-existent dir: {root}")
            return cls(project_root=root)

        # 2. Восходящий поиск маркера.
        start_dir = (start or Path.cwd()).resolve()
        for candidate in [start_dir, *start_dir.parents]:
            if any((candidate / marker).exists() for marker in _PROJECT_ROOT_MARKERS):
                return cls(project_root=candidate)

        # 3. Никаких fallback — лучше упасть явно, чем молча использовать cwd
        #    и получить «пустой» SARIF-отчёт (корень проблемы в аудите P0.1).
        raise FileNotFoundError(
            f"Project root not found: none of {', '.join(_PROJECT_ROOT_MARKERS)} "
            f"exist in {start_dir} or any parent directory. "
            f"Set ONEC_AI_DEV_ENV_ROOT env var to specify root explicitly."
        )

    @property
    def bsl_analyzer(self) -> BSLAnalyzer:
        """Lazy-init BSL analyzer (нужен Java)."""
        if self._bsl_analyzer is None:
            self._bsl_analyzer = BSLAnalyzer(
                self.paths.bsl_ls_binary,
                self.paths.bsl_ls_config,
                self.paths.root,
            )
        return self._bsl_analyzer

    def validate(self) -> dict[str, bool]:
        """Проверить что все критичные пути существуют."""
        return self.paths.validate()

    def list_configs(self) -> list:
        """Список всех конфигураций."""
        return self.registry.list_all()

    def list_configs_info(self) -> list[dict[str, Any]]:
        """
        Список конфигураций с детальной информацией.
        Возвращает: [{name, version, status, objects_count, api_methods_count, has_api}]
        """
        result = []
        for config in self.registry.list_all():
            api_json = self.paths.config_api_reference_json(config.name)
            api_methods = 0
            has_api = False
            if api_json.exists():
                has_api = True
                try:
                    with open(api_json, encoding="utf-8") as f:
                        modules = json.load(f)
                    api_methods = sum(m.get("methods_count", 0) for m in modules)
                except Exception:
                    pass

            result.append(
                {
                    "name": config.name,
                    "version": config.version,
                    "status": config.status,
                    "objects_count": config.objects_count,
                    "api_methods_count": api_methods,
                    "has_api": has_api,
                }
            )
        return result

    def get_config_info(self, name: str) -> dict[str, Any] | None:
        """
        Детальная информация о конфигурации.
        Возвращает: {name, version, status, objects_count, modules: [...]}
        """
        config = self.registry.get(name)
        if config is None:
            return None

        api_json = self.paths.config_api_reference_json(name)
        modules = []
        if api_json.exists():
            try:
                with open(api_json, encoding="utf-8") as f:
                    modules = json.load(f)
            except Exception:
                pass

        return {
            "name": config.name,
            "version": config.version,
            "status": config.status,
            "objects_count": config.objects_count,
            "modules": [
                {
                    "name": m.get("name", ""),
                    "methods_count": m.get("methods_count", 0),
                }
                for m in modules
            ],
        }

    def get_api_methods(self, config_name: str, module_name: str = "") -> list[dict[str, Any]]:
        """
        Получить экспортные методы конфигурации.

        Args:
            config_name: Имя конфигурации
            module_name: Имя модуля (если пусто — все модули)

        Returns:
            Список методов: [{module, name, type, params, description, returns}]
        """
        api_json = self.paths.config_api_reference_json(config_name)
        if not api_json.exists():
            return []

        try:
            with open(api_json, encoding="utf-8") as f:
                modules = json.load(f)
        except Exception:
            return []

        result = []
        for mod in modules:
            if module_name and mod.get("name", "") != module_name:
                continue
            for method in mod.get("methods", []):
                result.append(
                    {
                        "module": mod.get("name", ""),
                        "name": method.get("name", ""),
                        "type": method.get("type", ""),
                        "params": method.get("params", []),
                        "description": method.get("description", ""),
                        "returns": method.get("returns", ""),
                        "signature": method.get("signature", ""),
                    }
                )
        return result

    def search_methods(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Поиск по методам платформы 1С (P1.1: гибридный BM25 + vector).

        Авто-выбор алгоритма:
        - Если доступен векторный поиск (fastembed + Qdrant) → гибридный (BM25 + vector)
        - v2 индекс (BM25) → гибридный поиск (BM25 + триграммы)
        - v1 индекс (TF-IDF) → классический TF-IDF (legacy)

        Args:
            query: Поисковый запрос
            limit: Кол-во результатов

        Returns:
            Список: [{score, name_ru, name_en, context, syntax, description}]
        """
        # P1.1: предпочитаем гибридный поиск (BM25 + vector) если доступен
        from .services.search_hybrid import search_hybrid_auto

        index_path = self.paths.fast_search_index
        if not index_path.exists():
            return []
        return search_hybrid_auto(index_path, query, limit)

    def __repr__(self) -> str:
        return f"Project(root={self.paths.root}, configs={len(self.registry)})"
