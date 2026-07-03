"""
config_builder.py — построение индексов конфигураций 1С.

P2.11: выделен из ConfigManager (746 строк, God Object) для соблюдения SRP.
ConfigBuilder отвечает только за:
  - build(name) — построение всех 4 индексов для конфигурации
  - build_all() — построение индексов для всех активных конфигураций

Не делает: CRUD (это ConfigManager), валидации (это ConfigValidator).
Использует ConfigValidator для pre-flight проверок.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config_validator import ConfigValidator

if TYPE_CHECKING:
    from ..models.config_registry import ConfigurationRegistry
    from ..models.configuration import Configuration
    from .path_manager import PathManager

# Используем structlog если доступен, иначе fallback на logging
try:
    from .logger import get_logger

    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


# ============================================================================
# ConfigBuilder
# ============================================================================


class ConfigBuilder:
    """
    Построение индексов конфигураций 1С.

    Ответственность (SRP):
    - build(name): построение 4 индексов (metadata/api/skd/forms)
    - build_all():批量 построение для всех активных конфигураций

    Не делает: CRUD (это ConfigManager), валидации (это ConfigValidator).
    Использует ConfigValidator для pre-flight проверок.

    Запускаемые парсеры:
    1. metadata_extractor.py → unified-metadata-index.json
    2. build_api_reference.py → api-reference.json + api-reference.md
    3. skd_parser.py → skd-index.json
    4. form_analyzer.py → form-index.json

    Usage:
        builder = ConfigBuilder(registry, paths)
        report = builder.build("ut11")
        if not report["metadata"]:
            print(f"metadata build failed")
    """

    def __init__(
        self,
        registry: ConfigurationRegistry,
        paths: PathManager,
    ) -> None:
        self._registry = registry
        self._paths = paths
        self._validator = ConfigValidator(registry, paths)

    def build(
        self,
        name: str,
        force: bool = False,
        skip_if_fresh: bool = True,
    ) -> dict:
        """
        Построить ВСЕ индексы для конфигурации. Возвращает отчёт.

        Args:
            name: имя конфигурации
            force: если True — пересобрать даже если индексы свежие
            skip_if_fresh: если True (default) — пропустить индексы которые свежие
                          (только когда force=False)

        Returns:
            dict с ключами: name, metadata, api, skd, forms, skipped

        Raises:
            ValueError: если конфигурация не активна или исходники невалидны.
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            raise ValueError(f"Конфигурация '{name}' не активна")

        # Валидация исходников перед индексацией
        validation = self._validator.validate_sources(name)
        if not validation.is_valid:
            raise ValueError(f"Исходники конфигурации '{name}' невалидны: " + "; ".join(validation.errors))

        # Проверка актуальности (если не force)
        skipped: list[str] = []
        if not force and skip_if_fresh:
            freshness = self._validator.check_freshness(name)
            if freshness.all_fresh:
                return {
                    "name": name,
                    "metadata": True,
                    "api": True,
                    "skd": True,
                    "forms": True,
                    "skipped": ["all"],
                    "reason": "all indexes fresh",
                }

        report: dict = {
            "name": name,
            "metadata": False,
            "api": False,
            "skd": False,
            "forms": False,
            "skipped": skipped,
        }

        derived_dir = self._paths.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)

        config_dir = config.path
        scripts_dir = self._paths.scripts_dir

        # Определяем какие индексы нужно перестроить
        freshness_map: dict[str, bool] = {}
        if not force and skip_if_fresh:
            freshness = self._validator.check_freshness(name)
            for idx in freshness.indexes:
                freshness_map[idx.name] = idx.is_stale or not idx.exists
        else:
            freshness_map = {"metadata": True, "api": True, "skd": True, "forms": True}

        # 1. metadata_extractor
        if freshness_map.get("metadata", True):
            try:
                self._run_script(
                    scripts_dir / "metadata_extractor.py",
                    [str(config_dir), str(derived_dir / "unified-metadata-index.json")],
                )
                report["metadata"] = True
            except Exception as e:
                logger.warning(
                    "parser_failed",
                    parser="metadata_extractor",
                    config=name,
                    error=str(e),
                )
        else:
            report["metadata"] = True
            skipped.append("metadata")

        # 2. API reference (build_api_reference.py)
        if config.common_modules_dir:
            if freshness_map.get("api", True):
                api_md = self._paths.config_api_reference_md(name)
                api_json = self._paths.config_api_reference_json(name)
                try:
                    self._build_api_reference(config, api_md, api_json)
                    report["api"] = True
                except Exception as e:
                    logger.warning(
                        "parser_failed",
                        parser="build_api_reference",
                        config=name,
                        error=str(e),
                    )
            else:
                report["api"] = True
                skipped.append("api")
        else:
            report["api"] = False
            report.setdefault("skipped_reasons", {})["api"] = "no CommonModules dir"

        # 3. SKD index (skd_parser.py)
        if freshness_map.get("skd", True):
            try:
                self._run_script(
                    scripts_dir / "skd_parser.py",
                    [str(config_dir), str(derived_dir / "skd-index.json")],
                )
                report["skd"] = True
            except Exception as e:
                logger.warning(
                    "parser_failed",
                    parser="skd_parser",
                    config=name,
                    error=str(e),
                )
        else:
            report["skd"] = True
            skipped.append("skd")

        # 4. Form index (form_analyzer.py)
        if freshness_map.get("forms", True):
            try:
                self._run_script(
                    scripts_dir / "form_analyzer.py",
                    [str(config_dir), str(derived_dir / "form-index.json")],
                )
                report["forms"] = True
            except Exception as e:
                logger.warning(
                    "parser_failed",
                    parser="form_analyzer",
                    config=name,
                    error=str(e),
                )
        else:
            report["forms"] = True
            skipped.append("forms")

        report["skipped"] = skipped

        # Обновить реестр
        config.objects_count = self._count_objects(config.path)
        self._registry.add(config)

        return report

    def build_all(self, force: bool = False) -> list[dict]:
        """Индексы для всех активных конфигураций."""
        results = []
        for config in self._registry.list_active():
            results.append(self.build(config.name, force=force))
        return results

    # ─── Private helpers ───

    def _run_script(self, script_path: Path, args: list[str]) -> None:
        """Запускает Python скрипт с аргументами."""
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{script_path.name} failed: {result.stderr[-500:]}")

    def _build_api_reference(
        self,
        config: Configuration,
        output_md: Path,
        output_json: Path,
    ) -> None:
        """Запустить build_api_reference.py."""
        script = self._paths.scripts_dir / "build_api_reference.py"
        if not script.exists():
            script = self._paths.root / "setup" / "scripts" / "build_api_reference.py"
        subprocess.run(
            [
                "python3",
                str(script),
                "--config",
                config.name,
                "--config-dir",
                str(config.path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--title",
                config.title,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _count_objects(config_dir: Path) -> int:
        """Посчитать количество объектов метаданных в директории конфигурации."""
        type_dirs = [
            "Catalogs",
            "Documents",
            "Enums",
            "Constants",
            "CommonModules",
            "InformationRegisters",
            "AccumulationRegisters",
            "Reports",
            "DataProcessors",
            "CommonForms",
            "CommonTemplates",
            "CommonCommands",
            "CommonPictures",
            "Roles",
            "Subsystems",
            "EventSubscriptions",
            "ScheduledJobs",
            "DefinedTypes",
            "FunctionalOptions",
            "ExchangePlans",
            "ChartsOfCharacteristicTypes",
            "HTTPServices",
            "WebServices",
            "XDTOPackages",
            "FilterCriteria",
            "SessionParameters",
            "CommandGroups",
            "SettingsStorages",
            "BusinessProcesses",
            "Tasks",
            "DocumentJournals",
            "DocumentNumerators",
            "Sequences",
            "FunctionalOptionsParameters",
            "CommonAttributes",
            "WSReferences",
        ]
        count = 0
        for type_dir in type_dirs:
            d = config_dir / type_dir
            if d.is_dir():
                count += sum(1 for item in d.iterdir() if item.is_dir())
        return count
