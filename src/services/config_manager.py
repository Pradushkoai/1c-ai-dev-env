"""
Менеджер конфигураций: добавление, архивация, индексация.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.configuration import Configuration
from ..models.config_registry import ConfigurationRegistry
from .path_manager import PathManager

logger = logging.getLogger(__name__)


# --- Директории 1С, которые считаются валидными метаданными ---

REQUIRED_TYPE_DIRS: tuple[str, ...] = (
    "Catalogs", "Documents", "Enums", "Constants", "CommonModules",
    "InformationRegisters", "AccumulationRegisters", "Reports",
    "DataProcessors", "CommonForms", "CommonTemplates", "CommonCommands",
    "CommonPictures", "Roles", "Subsystems", "EventSubscriptions",
    "ScheduledJobs", "DefinedTypes", "FunctionalOptions",
    "ExchangePlans", "ChartsOfCharacteristicTypes", "HTTPServices",
    "WebServices", "XDTOPackages", "FilterCriteria", "SessionParameters",
    "CommandGroups", "SettingsStorages", "BusinessProcesses", "Tasks",
    "DocumentJournals", "DocumentNumerators", "Sequences",
    "FunctionalOptionsParameters", "CommonAttributes", "WSReferences",
)

# Минимум одна из этих директорий должна быть, чтобы считать выгрузку валидной
MIN_REQUIRED_DIRS: tuple[str, ...] = ("CommonModules", "Catalogs", "Documents", "Subsystems")


@dataclass
class SourceValidation:
    """Результат валидации исходников конфигурации."""
    is_valid: bool
    has_configuration_xml: bool = False
    has_metadata_dirs: bool = False
    has_bsl_files: bool = False
    found_type_dirs: list[str] = field(default_factory=list)
    missing_critical: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IndexStatus:
    """Статус одного индекса конфигурации."""
    name: str            # metadata | api | skd | forms
    path: Optional[Path]
    exists: bool
    mtime: Optional[float]      # время модификации индекса (epoch)
    size_bytes: int = 0
    is_stale: bool = False      # True если source новее индекса
    stale_reason: str = ""      # объяснение почему stale


@dataclass
class IndexFreshnessReport:
    """Полный отчёт об актуальности всех индексов конфигурации."""
    config_name: str
    source_mtime: Optional[float]      # самый свежий .xml/.bsl в исходниках
    indexes: list[IndexStatus] = field(default_factory=list)
    all_fresh: bool = True
    missing_indexes: list[str] = field(default_factory=list)
    stale_indexes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "config": self.config_name,
            "source_mtime": self.source_mtime,
            "all_fresh": self.all_fresh,
            "missing": self.missing_indexes,
            "stale": self.stale_indexes,
            "indexes": [
                {
                    "name": i.name,
                    "exists": i.exists,
                    "is_stale": i.is_stale,
                    "stale_reason": i.stale_reason,
                    "size_bytes": i.size_bytes,
                }
                for i in self.indexes
            ],
        }


class ConfigManager:
    """Управление конфигурациями 1С: add, activate, archive, build, list."""

    def __init__(self, registry: ConfigurationRegistry, paths: PathManager):
        self._registry = registry
        self._paths = paths

    # --- Добавление ---

    def add_from_zip(self, name: str, zip_path: Path, title: str = "") -> Configuration:
        """Распаковать ZIP и зарегистрировать конфигурацию."""
        if name in self._registry:
            raise ValueError(f"Конфигурация '{name}' уже существует")
        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP не найден: {zip_path}")

        config_dir = self._paths.config_path(name)
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Проверим целостность перед распаковкой
                bad = zf.testzip()
                if bad is not None:
                    raise zipfile.BadZipFile(f"Повреждён файл внутри архива: {bad}")
                zf.extractall(config_dir)
        except zipfile.BadZipFile as e:
            shutil.rmtree(config_dir, ignore_errors=True)
            raise ValueError(f"ZIP повреждён или не является архивом: {zip_path} ({e})") from e

        config = self._create_config(name, title or name, config_dir)
        self._registry.add(config)
        return config

    def register_existing(self, name: str, path: Path, title: str = "") -> Configuration:
        """Зарегистрировать существующую папку."""
        if name in self._registry:
            raise ValueError(f"Конфигурация '{name}' уже существует")

        config = self._create_config(name, title or name, path)
        self._registry.add(config)
        return config

    def add_from_cf(self, name: str, cf_path: Path, title: str = "") -> Configuration:
        """
        Распаковать .cf/.cfe/.epf файл и зарегистрировать конфигурацию.

        Использует scripts/cf_extractor.py — наш собственный парсер
        формата контейнера 1С (без зависимости от внешнего v8unpack).
        После распаковки конвертирует структуру v8unpack в формат,
        совместимый с build_api_reference (через cf_to_xml_adapter).
        """
        if name in self._registry:
            raise ValueError(f"Конфигурация '{name}' уже существует")
        if not cf_path.exists():
            raise FileNotFoundError(f".cf файл не найден: {cf_path}")

        # Импортируем cf_extractor из scripts/
        import importlib.util
        import sys

        scripts_dir = self._paths.scripts_dir
        if not (scripts_dir / "cf_extractor.py").exists():
            scripts_dir = self._paths.root / "setup" / "scripts"
        if not (scripts_dir / "cf_extractor.py").exists():
            raise FileNotFoundError("scripts/cf_extractor.py не найден")

        # Загружаем cf_extractor
        spec = importlib.util.spec_from_file_location("cf_extractor", scripts_dir / "cf_extractor.py")
        cf_mod = importlib.util.module_from_spec(spec)
        sys.modules["cf_extractor"] = cf_mod
        spec.loader.exec_module(cf_mod)

        # Загружаем improved_cf_adapter (предпочтительно) или cf_to_xml_adapter (fallback)
        adapter_path = scripts_dir / "improved_cf_adapter.py"
        if not adapter_path.exists():
            adapter_path = scripts_dir / "cf_to_xml_adapter.py"
        if adapter_path.exists():
            adapter_modname = adapter_path.stem
            spec2 = importlib.util.spec_from_file_location(adapter_modname, adapter_path)
            adapter_mod = importlib.util.module_from_spec(spec2)
            sys.modules[adapter_modname] = adapter_mod
            spec2.loader.exec_module(adapter_mod)
        else:
            adapter_mod = None

        config_dir = self._paths.config_path(name)
        config_dir.mkdir(parents=True, exist_ok=True)

        # Создаём временную папку для распаковки
        raw_dir = config_dir / '_cf_raw'
        raw_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Шаг 1: Распаковка .cf
            cf_mod.extract_cf(cf_path, raw_dir)

            # Шаг 2: Конвертация в формат build_api_reference
            if adapter_mod:
                # Конвертируем CommonModules в CommonModules/ папку
                adapter_mod.convert_cf_to_xml_format(raw_dir, config_dir)

            # Удаляем временную папку (экономим место)
            shutil.rmtree(raw_dir, ignore_errors=True)

        except Exception as e:
            shutil.rmtree(config_dir, ignore_errors=True)
            raise ValueError(f"Ошибка распаковки .cf: {e}") from e

        config = self._create_config(name, title or name, config_dir)
        self._registry.add(config)
        return config

    # --- Архивация ---

    def archive(self, name: str) -> None:
        """Запаковать в ZIP и удалить распакованную папку."""
        config = self._registry.get(name)
        if not config or not config.path or not config.path.exists():
            raise ValueError(f"Конфигурация '{name}' не активна")

        self._paths.archives_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self._paths.archives_dir / f"{name}_full.zip"
        shutil.make_archive(str(archive_path.with_suffix("")), "zip", str(config.path))
        shutil.rmtree(config.path)

        config.path = None
        config.archive = archive_path
        config.status = "archived"
        self._registry.add(config)

    def activate(self, name: str) -> Configuration:
        """Распаковать из архива."""
        config = self._registry.get(name)
        if not config or not config.archive or not config.archive.exists():
            raise ValueError(f"Архив для '{name}' не найден")

        config_dir = self._paths.config_path(name)
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(config.archive, "r") as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise zipfile.BadZipFile(f"Повреждён файл: {bad}")
                zf.extractall(config_dir)
        except zipfile.BadZipFile as e:
            shutil.rmtree(config_dir, ignore_errors=True)
            raise ValueError(f"Архив повреждён: {config.archive} ({e})") from e

        config.path = config_dir
        config.status = "active"
        self._registry.add(config)
        return config

    # --- Индексация ---

    def validate_sources(self, name: str) -> SourceValidation:
        """Проверить что исходники конфигурации валидны для индексации.

        Проверяет:
        - Configuration.xml (обязателен для полной XML выгрузки)
        - Хотя бы одну из MIN_REQUIRED_DIRS директорий
        - Наличие .bsl файлов (предупреждение если нет)
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            return SourceValidation(
                is_valid=False,
                errors=[f"Конфигурация '{name}' не активна"],
            )

        result = SourceValidation(is_valid=True)
        config_dir = config.path

        # 1. Configuration.xml
        cfg_xml = config_dir / "Configuration.xml"
        result.has_configuration_xml = cfg_xml.exists()
        if not result.has_configuration_xml:
            result.errors.append("Configuration.xml не найден — это не полная XML выгрузка")
            result.is_valid = False

        # 2. Метаданные-директории
        for type_dir in REQUIRED_TYPE_DIRS:
            d = config_dir / type_dir
            if d.is_dir() and any(d.iterdir()):
                result.found_type_dirs.append(type_dir)

        # Хотя бы одна критическая директория
        has_critical = any(d in result.found_type_dirs for d in MIN_REQUIRED_DIRS)
        result.has_metadata_dirs = has_critical
        if not has_critical:
            result.missing_critical = list(MIN_REQUIRED_DIRS)
            result.errors.append(
                "Ни одна из критических директорий не найдена: "
                + ", ".join(MIN_REQUIRED_DIRS)
            )
            result.is_valid = False

        # 3. .bsl файлы (предупреждение)
        try:
            bsl_count = sum(1 for _ in config_dir.rglob("*.bsl"))
            result.has_bsl_files = bsl_count > 0
            if not result.has_bsl_files:
                result.warnings.append(
                    ".bsl файлы не найдены — api-reference будет пустым. "
                    "Возможно это .cf распаковка без адаптации."
                )
        except (OSError, PermissionError) as e:
            result.warnings.append(f"Не удалось проверить .bsl файлы: {e}")

        return result

    def check_freshness(self, name: str) -> IndexFreshnessReport:
        """Проверить актуальность индексов конфигурации.

        Для каждого из 4 индексов (metadata/api/skd/forms):
        - существует ли файл?
        - новее ли source чем index? (по mtime)
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            return IndexFreshnessReport(
                config_name=name,
                source_mtime=None,
                all_fresh=False,
                missing_indexes=["metadata", "api", "skd", "forms"],
            )

        # Самый свежий файл исходников
        source_mtime = self._latest_source_mtime(config.path)

        derived_dir = self._paths.config_derived_dir(name)
        index_files = {
            "metadata": derived_dir / "unified-metadata-index.json",
            "api": self._paths.config_api_reference_json(name),
            "skd": derived_dir / "skd-index.json",
            "forms": derived_dir / "form-index.json",
        }

        report = IndexFreshnessReport(
            config_name=name,
            source_mtime=source_mtime,
        )

        for idx_name, idx_path in index_files.items():
            status = IndexStatus(name=idx_name, path=idx_path, exists=False, mtime=None)

            if idx_path and idx_path.exists():
                status.exists = True
                status.mtime = idx_path.stat().st_mtime
                status.size_bytes = idx_path.stat().st_size

                # Сравнение: если source новее индекса — устарел
                if source_mtime is not None and source_mtime > status.mtime:
                    status.is_stale = True
                    delta = int(source_mtime - status.mtime)
                    status.stale_reason = (
                        f"исходники новее на {delta} сек "
                        f"(source={time.ctime(source_mtime)}, index={time.ctime(status.mtime)})"
                    )
                    report.stale_indexes.append(idx_name)
                    report.all_fresh = False
            else:
                status.is_stale = True
                status.stale_reason = "индекс отсутствует"
                report.missing_indexes.append(idx_name)
                report.all_fresh = False

            report.indexes.append(status)

        return report

    @staticmethod
    def _latest_source_mtime(config_dir: Path) -> Optional[float]:
        """Найти самый свежий mtime среди .xml и .bsl файлов исходников."""
        latest: Optional[float] = None
        try:
            for pattern in ("*.xml", "*.bsl"):
                for f in config_dir.rglob(pattern):
                    if f.is_file():
                        try:
                            m = f.stat().st_mtime
                            if latest is None or m > latest:
                                latest = m
                        except (OSError, PermissionError):
                            continue
        except (OSError, PermissionError):
            pass
        return latest

    def build(self, name: str, force: bool = False, skip_if_fresh: bool = True) -> dict:
        """Построить ВСЕ индексы для конфигурации. Возвращает отчёт.

        Запускает 4 парсера:
        1. metadata_extractor.py → unified-metadata-index.json
        2. build_api_reference.py → api-reference.json + api-reference.md
        3. skd_parser.py → skd-index.json
        4. form_analyzer.py → form-index.json

        Args:
            name: имя конфигурации
            force: если True — пересобрать даже если индексы свежие
            skip_if_fresh: если True (default) — пропустить индексы которые свежие
                          (только когда force=False)
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            raise ValueError(f"Конфигурация '{name}' не активна")

        # Валидация исходников перед индексацией
        validation = self.validate_sources(name)
        if not validation.is_valid:
            raise ValueError(
                f"Исходники конфигурации '{name}' невалидны: "
                + "; ".join(validation.errors)
            )

        # Проверка актуальности (если не force)
        skipped: list[str] = []
        if not force and skip_if_fresh:
            freshness = self.check_freshness(name)
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

        report = {
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

        # Список парсеров: (ключ отчёта, путь к скрипту, индекс-файл, аргументы)
        parsers: list[tuple[str, Path, Path, list[str]]] = [
            (
                "metadata",
                scripts_dir / "metadata_extractor.py",
                derived_dir / "unified-metadata-index.json",
                [str(config_dir), str(derived_dir / "unified-metadata-index.json")],
            ),
            (
                "skd",
                scripts_dir / "skd_parser.py",
                derived_dir / "skd-index.json",
                [str(config_dir), str(derived_dir / "skd-index.json")],
            ),
            (
                "forms",
                scripts_dir / "form_analyzer.py",
                derived_dir / "form-index.json",
                [str(config_dir), str(derived_dir / "form-index.json")],
            ),
        ]

        # Определяем какие индексы нужно перестроить
        freshness_map: dict[str, bool] = {}  # name → нужно перестроить
        if not force and skip_if_fresh:
            freshness = self.check_freshness(name)
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
                print(f"  ⚠️ metadata_extractor: {e}")
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
                    print(f"  ⚠️ build_api_reference: {e}")
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
                print(f"  ⚠️ skd_parser: {e}")
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
                print(f"  ⚠️ form_analyzer: {e}")
        else:
            report["forms"] = True
            skipped.append("forms")

        report["skipped"] = skipped

        # Обновить реестр
        config.objects_count = self._count_objects(config.path)
        self._registry.add(config)

        return report

    def _run_script(self, script_path: Path, args: list[str]) -> None:
        """Запускает Python скрипт с аргументами."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{script_path.name} failed: {result.stderr[-500:]}")

    def build_all(self, force: bool = False) -> list[dict]:
        """Индексы для всех активных конфигураций."""
        results = []
        for config in self._registry.list_active():
            results.append(self.build(config.name, force=force))
        return results

    # --- Удаление ---

    def remove(self, name: str) -> bool:
        return self._registry.remove(name)

    # --- Внутренние методы ---

    def _create_config(self, name: str, title: str, path: Path) -> Configuration:
        version, vendor = self._read_config_props(path / "Configuration.xml")
        objects_count = self._count_objects(path)
        return Configuration(
            name=name,
            title=title,
            version=version,
            vendor=vendor,
            path=path,
            status="active",
            objects_count=objects_count,
        )

    @staticmethod
    def _read_config_props(xml_path: Path) -> tuple[str, str]:
        if not xml_path.exists():
            return ("unknown", "")

        def _strip_ns(tag: str) -> str:
            return tag.split("}")[1] if "}" in tag else tag

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            cfg = next((c for c in root if _strip_ns(c.tag) == "Configuration"), None)
            if cfg is None:
                return ("unknown", "")
            props = next((c for c in cfg if _strip_ns(c.tag) == "Properties"), None)
            if props is None:
                return ("unknown", "")
            version = ""
            vendor = ""
            for child in props:
                tag = _strip_ns(child.tag)
                if tag == "Version":
                    version = child.text or ""
                elif tag == "Vendor":
                    vendor = child.text or ""
            return (version, vendor)
        except ET.ParseError as e:
            logger.warning("Не удалось распарсить %s: %s", xml_path, e)
            return ("unknown", "")
        except (OSError, PermissionError) as e:
            logger.warning("Нет доступа к %s: %s", xml_path, e)
            return ("unknown", "")

    @staticmethod
    def _count_objects(config_dir: Path) -> int:
        type_dirs = [
            "Catalogs", "Documents", "Enums", "Constants", "CommonModules",
            "InformationRegisters", "AccumulationRegisters", "Reports",
            "DataProcessors", "CommonForms", "CommonTemplates", "CommonCommands",
            "CommonPictures", "Roles", "Subsystems", "EventSubscriptions",
            "ScheduledJobs", "DefinedTypes", "FunctionalOptions",
            "ExchangePlans", "ChartsOfCharacteristicTypes", "HTTPServices",
            "WebServices", "XDTOPackages", "FilterCriteria", "SessionParameters",
            "CommandGroups", "SettingsStorages", "BusinessProcesses", "Tasks",
            "DocumentJournals", "DocumentNumerators", "Sequences",
            "FunctionalOptionsParameters", "CommonAttributes", "WSReferences",
        ]
        count = 0
        for type_dir in type_dirs:
            d = config_dir / type_dir
            if d.is_dir():
                count += sum(1 for item in d.iterdir() if item.is_dir())
        return count

    def _build_metadata_index(self, config: Configuration, output: Path) -> None:
        """Запустить build_config_index_generic.py."""
        script = self._paths.scripts_dir / "build_config_index_generic.py"
        if not script.exists():
            script = self._paths.root / "setup" / "scripts" / "build_config_index_generic.py"
        subprocess.run(
            ["python3", str(script), str(config.path), str(output), config.title],
            check=True, capture_output=True, text=True,
        )

    def _build_api_reference(self, config: Configuration, output_md: Path, output_json: Path) -> None:
        """Запустить build_api_reference.py."""
        script = self._paths.scripts_dir / "build_api_reference.py"
        if not script.exists():
            script = self._paths.root / "setup" / "scripts" / "build_api_reference.py"
        subprocess.run(
            ["python3", str(script),
             "--config", config.name,
             "--config-dir", str(config.path),
             "--output-md", str(output_md),
             "--output-json", str(output_json),
             "--title", config.title],
            check=True, capture_output=True, text=True,
        )
