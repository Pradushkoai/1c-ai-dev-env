"""
Менеджер конфигураций: добавление, архивация, индексация.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..models.configuration import Configuration
from ..models.config_registry import ConfigurationRegistry
from .path_manager import PathManager

logger = logging.getLogger(__name__)


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

    def build(self, name: str) -> dict:
        """Построить все индексы для конфигурации. Возвращает отчёт."""
        config = self._registry.get(name)
        if not config or not config.is_active():
            raise ValueError(f"Конфигурация '{name}' не активна")

        report = {"name": name, "index": False, "api": False}

        derived_dir = self._paths.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)

        # 1. Индекс метаданных
        index_path = self._paths.config_index_path(name)
        self._build_metadata_index(config, index_path)
        report["index"] = True

        # 2. API справочник
        if config.common_modules_dir:
            api_md = self._paths.config_api_reference_md(name)
            api_json = self._paths.config_api_reference_json(name)
            self._build_api_reference(config, api_md, api_json)
            report["api"] = True

        # Обновить реестр
        config.objects_count = self._count_objects(config.path)
        self._registry.add(config)

        return report

    def build_all(self) -> list[dict]:
        """Индексы для всех активных конфигураций."""
        results = []
        for config in self._registry.list_active():
            results.append(self.build(config.name))
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
