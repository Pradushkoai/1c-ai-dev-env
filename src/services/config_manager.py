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

    def build(self, name: str) -> dict:
        """Построить ВСЕ индексы для конфигурации. Возвращает отчёт.

        Запускает 4 парсера:
        1. metadata_extractor.py → unified-metadata-index.json
        2. build_api_reference.py → api-reference.json + api-reference.md
        3. skd_parser.py → skd-index.json
        4. form_analyzer.py → form-index.json
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            raise ValueError(f"Конфигурация '{name}' не активна")

        report = {
            "name": name,
            "metadata": False,
            "api": False,
            "skd": False,
            "forms": False,
        }

        derived_dir = self._paths.config_derived_dir(name)
        derived_dir.mkdir(parents=True, exist_ok=True)

        config_dir = config.path
        scripts_dir = self._paths.scripts_dir

        # 1. Unified metadata index (metadata_extractor.py)
        try:
            self._run_script(
                scripts_dir / "metadata_extractor.py",
                [str(config_dir), str(derived_dir / "unified-metadata-index.json")],
            )
            report["metadata"] = True
        except Exception as e:
            print(f"  ⚠️ metadata_extractor: {e}")

        # 2. API reference (build_api_reference.py)
        if config.common_modules_dir:
            api_md = self._paths.config_api_reference_md(name)
            api_json = self._paths.config_api_reference_json(name)
            try:
                self._build_api_reference(config, api_md, api_json)
                report["api"] = True
            except Exception as e:
                print(f"  ⚠️ build_api_reference: {e}")

        # 3. SKD index (skd_parser.py)
        try:
            self._run_script(
                scripts_dir / "skd_parser.py",
                [str(config_dir), str(derived_dir / "skd-index.json")],
            )
            report["skd"] = True
        except Exception as e:
            print(f"  ⚠️ skd_parser: {e}")

        # 4. Form index (form_analyzer.py)
        try:
            self._run_script(
                scripts_dir / "form_analyzer.py",
                [str(config_dir), str(derived_dir / "form-index.json")],
            )
            report["forms"] = True
        except Exception as e:
            print(f"  ⚠️ form_analyzer: {e}")

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
