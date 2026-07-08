"""
DataPackage — persistence для данных проекта.

Решает проблему: диск /home/z/my-project пересоздаётся между сессиями,
data/ и derived/ теряются. DataPackage позволяет упаковать всё в один ZIP
и восстановить при следующем запуске.

Структура пакета:
    data-package/
    ├── manifest.json          — метаданные, версии, состав
    ├── runtime/
    │   └── config-registry.json
    ├── derived/
    │   ├── configs/
    │   │   └── <name>/
    │   │       ├── api-reference.json
    │   │       ├── api-reference.md
    │   │       └── index.md
    │   └── platform/
    │       ├── fast-search-index.json
    │       └── syntax-helper-index.json
    └── data/ (опционально, --include-raw)
        ├── configs/<name>/   — распакованные конфигурации
        └── hbk/              — синтакс-помощник

Usage:
    DataPackage(paths).save(Path('backup.zip'))
    DataPackage(paths).load(Path('backup.zip'))
"""

from __future__ import annotations

import contextlib
import json
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .path_manager import PathManager


@dataclass
class PackageManifest:
    """Метаданные пакета данных."""

    version: str = "1.0"
    created_at: str = ""
    project_root: str = ""
    include_raw: bool = False
    include_derived: bool = True
    configs: list[dict] = field(default_factory=list)  # [{name, version, status, objects_count}]
    files_count: int = 0
    size_bytes: int = 0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "project_root": self.project_root,
            "include_raw": self.include_raw,
            "include_derived": self.include_derived,
            "configs": self.configs,
            "files_count": self.files_count,
            "size_bytes": self.size_bytes,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageManifest:
        return cls(
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
            project_root=data.get("project_root", ""),
            include_raw=data.get("include_raw", False),
            include_derived=data.get("include_derived", True),
            configs=data.get("configs", []),
            files_count=data.get("files_count", 0),
            size_bytes=data.get("size_bytes", 0),
            description=data.get("description", ""),
        )


class DataPackage:
    """
    Сохранение и восстановление данных проекта в один ZIP.
    """

    def __init__(self, paths: PathManager):
        self._paths = paths

    # ---- Сохранение ----

    def save(
        self,
        output_path: Path,
        include_raw: bool = False,
        include_derived: bool = True,
        description: str = "",
    ) -> Path:
        """
        Сохранить данные проекта в ZIP.

        Args:
            output_path: Куда сохранить ZIP
            include_raw: Включить data/ (распакованные конфиги, hbk) — большой объём
            include_derived: Включить derived/ (индексы) — маленький, рекомендуем
            description: Описание пакета

        Returns: Путь к созданному ZIP
        """
        if not include_raw and not include_derived:
            raise ValueError("Хотя бы одно из include_raw/include_derived должно быть True")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Манифест
        manifest = PackageManifest(
            created_at=datetime.now().isoformat(),
            project_root=str(self._paths.root),
            include_raw=include_raw,
            include_derived=include_derived,
            description=description,
        )

        # Информация о конфигурациях
        registry_path = self._paths.config_registry_path
        if registry_path.exists():
            with open(registry_path, encoding="utf-8") as f:
                registry = json.load(f)
            for name, cfg in registry.get("configs", {}).items():
                manifest.configs.append(
                    {
                        "name": name,
                        "version": cfg.get("version", ""),
                        "status": cfg.get("status", ""),
                        "objects_count": cfg.get("objects_count", 0),
                    }
                )

        files_count = 0
        size_bytes = 0

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # 1. runtime/config-registry.json (всегда)
            if registry_path.exists():
                zf.write(registry_path, "data-package/runtime/config-registry.json")
                files_count += 1

            # 2. derived/ (если включён)
            if include_derived and self._paths.derived_dir.exists():
                for root, _dirs, files in os.walk(self._paths.derived_dir):
                    for fname in files:
                        full = Path(root) / fname
                        rel = full.relative_to(self._paths.root)
                        arcname = f"data-package/{rel}"
                        zf.write(full, arcname)
                        files_count += 1
                        size_bytes += full.stat().st_size

            # 3. data/ (если включён) — большие файлы
            if include_raw and self._paths.data_dir.exists():
                for root, _dirs, files in os.walk(self._paths.data_dir):
                    for fname in files:
                        full = Path(root) / fname
                        rel = full.relative_to(self._paths.root)
                        arcname = f"data-package/{rel}"
                        zf.write(full, arcname)
                        files_count += 1
                        size_bytes += full.stat().st_size

            # 4. Манифест
            manifest.files_count = files_count
            manifest.size_bytes = size_bytes
            zf.writestr(
                "data-package/manifest.json",
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            )

        return output_path

    # ---- Загрузка ----

    def load(self, input_path: Path) -> dict[str, Any]:
        """
        Восстановить данные из ZIP.

        Args: input_path: Путь к ZIP
        Returns: Статистика {files_restored, configs_loaded, derived_restored, raw_restored}
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Пакет не найден: {input_path}")

        stats: dict[str, Any] = {
            "files_restored": 0,
            "configs_loaded": 0,
            "derived_restored": 0,
            "raw_restored": 0,
            "manifest": None,
        }

        with zipfile.ZipFile(input_path, "r") as zf:
            # Читаем манифест первым
            try:
                with zf.open("data-package/manifest.json") as f:
                    manifest_data = json.loads(f.read().decode("utf-8"))
                stats["manifest"] = PackageManifest.from_dict(manifest_data)
            except KeyError:
                # Нет манифеста — старый формат
                pass

            # Распаковываем всё
            for info in zf.infolist():
                if info.filename.endswith("/"):
                    continue
                if info.filename == "data-package/manifest.json":
                    continue

                # Вычисляем относительный путь внутри data-package/
                if not info.filename.startswith("data-package/"):
                    continue
                rel_path = info.filename[len("data-package/") :]

                # Куда распаковать
                target = self._paths.root / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())

                stats["files_restored"] += 1

                # Категоризация
                if rel_path.startswith("derived/"):
                    stats["derived_restored"] += 1
                elif rel_path.startswith("data/"):
                    stats["raw_restored"] += 1
                elif rel_path.startswith("runtime/config-registry.json"):
                    stats["configs_loaded"] += 1

        return stats

    # ---- Информация о пакете ----

    def info(self, input_path: Path) -> dict[str, Any]:
        """
        Прочитать информацию о пакете без распаковки.

        Returns: {manifest, file_list (первые 50), total_files}
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Пакет не найден: {input_path}")

        result: dict[str, Any] = {
            "manifest": None,
            "total_files": 0,
            "file_list_sample": [],
            "size_mb": input_path.stat().st_size / 1024 / 1024,
        }

        with zipfile.ZipFile(input_path, "r") as zf:
            result["total_files"] = len(zf.namelist())

            # Список файлов (первые 50)
            for name in zf.namelist()[:50]:
                result["file_list_sample"].append(name)

            # Манифест
            try:
                with zf.open("data-package/manifest.json") as f:
                    manifest_data = json.loads(f.read().decode("utf-8"))
                result["manifest"] = PackageManifest.from_dict(manifest_data).to_dict()
            except KeyError:
                pass

        return result

    # ---- Стандартное место для autosave/autoload ----

    @property
    def default_package_path(self) -> Path:
        """Стандартное место для пакета данных (персистентное)."""
        # download/ — пользовательская директория, персистентная
        return self._paths.root / "download" / "1c-ai-data-package.zip"

    def autosave(self, include_raw: bool = False, include_derived: bool = True, description: str = "") -> Path:
        """Сохранить в стандартное место."""
        return self.save(
            self.default_package_path,
            include_raw=include_raw,
            include_derived=include_derived,
            description=description or "Autosave",
        )

    def autoload(self) -> dict[str, Any] | None:
        """
        Автоматически восстановить из стандартного места, если пакет существует.

        Returns: Статистика загрузки или None если пакет не найден
        """
        if not self.default_package_path.exists():
            return None
        return self.load(self.default_package_path)

    def has_autosave(self) -> bool:
        """Есть ли сохранённый пакет в стандартном месте?"""
        return self.default_package_path.exists()

    # ---- Статус данных ----

    def status(self) -> dict[str, Any]:
        """
        Текущий статус данных: что доступно, что нужно перестроить.

        Returns: {
            has_platform_index: bool,
            has_platform_methods: bool,
            has_platform_methods_db: bool,  # B9 FIX: SQLite индекс платформы
            platform_version: str,          # B5: версия платформы
            configs: [{name, has_derived, has_raw}],
            autosave_available: bool,
            autosave_info: dict[str, Any] | None,
        }
        """
        # B9 FIX: проверяем новый SQLite индекс платформы
        # вместо несуществующего syntax_helper_index_json
        import os

        platform_version = os.environ.get("1C_AI_PLATFORM_VERSION", "8.3.20")
        platform_db_path = self._paths.derived_platform_dir / "versions" / platform_version / "platform-methods.db"

        status: dict[str, Any] = {
            "has_platform_index": self._paths.fast_search_index.exists(),
            "has_platform_methods": platform_db_path.exists(),  # B9 FIX
            "has_platform_methods_db": platform_db_path.exists(),  # B9 FIX: новый SQLite
            "platform_version": platform_version,
            "platform_db_path": str(platform_db_path),
            "configs": [],
            "autosave_available": self.has_autosave(),
            "autosave_info": None,
        }

        # Конфигурации
        registry_path = self._paths.config_registry_path
        if registry_path.exists():
            with open(registry_path, encoding="utf-8") as f:
                registry = json.load(f)
            for name, cfg in registry.get("configs", {}).items():
                derived_dir = self._paths.config_derived_dir(name)
                api_json = self._paths.config_api_reference_json(name)
                raw_dir = self._paths.config_path(name)

                status["configs"].append(
                    {
                        "name": name,
                        "version": cfg.get("version", ""),
                        "status": cfg.get("status", ""),
                        "has_derived": derived_dir.exists(),
                        "has_api": api_json.exists(),
                        "has_raw": raw_dir.exists() if cfg.get("path") else False,
                    }
                )

        # Информация об autosave
        if status["autosave_available"]:
            with contextlib.suppress(Exception):
                status["autosave_info"] = self.info(self.default_package_path)

        return status
