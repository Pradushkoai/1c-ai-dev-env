"""
Модель 1С конфигурации.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Configuration:
    """1С конфигурация: UT11, Приемка, УНП, и т.д."""

    name: str
    title: str
    version: str = "unknown"
    vendor: str = ""
    path: Path | None = None
    archive: Path | None = None
    status: str = "active"  # active | archived
    objects_count: int = 0
    api_methods_count: int = 0
    added_at: str = field(default_factory=lambda: date.today().isoformat())

    # --- Свойства ---

    @property
    def common_modules_dir(self) -> Path | None:
        """Папка CommonModules если есть."""
        if self.path and (self.path / "CommonModules").exists():
            return self.path / "CommonModules"
        return None

    @property
    def has_code(self) -> bool:
        """Есть ли .bsl файлы (полная выгрузка)."""
        if not self.path:
            return False
        return any(self.path.rglob("*.bsl"))

    @property
    def configuration_xml(self) -> Path | None:
        """Путь к Configuration.xml."""
        if self.path:
            f = self.path / "Configuration.xml"
            return f if f.exists() else None
        return None

    # --- Проверки ---

    def is_active(self) -> bool:
        """Активна и папка существует."""
        return self.status == "active" and self.path is not None and self.path.exists()

    def is_archived(self) -> bool:
        return self.status == "archived"

    # --- Фабричные методы ---

    @classmethod
    def from_dict(cls, name: str, data: dict, project_root: Path) -> Configuration:
        """Создать из dict (config-registry.json)."""
        raw_path = data.get("path")
        path = (
            Path(project_root / raw_path)
            if raw_path and not raw_path.startswith("/")
            else (Path(raw_path) if raw_path else None)
        )

        raw_archive = data.get("archive")
        archive = (
            Path(project_root / raw_archive)
            if raw_archive and not raw_archive.startswith("/")
            else (Path(raw_archive) if raw_archive else None)
        )

        return cls(
            name=name,
            title=data.get("name", name),
            version=data.get("version", "unknown"),
            vendor=data.get("vendor", ""),
            path=path,
            archive=archive,
            status=data.get("status", "active"),
            objects_count=data.get("objects_count", 0),
            api_methods_count=data.get("api_methods_count", 0),
            added_at=data.get("added_at", date.today().isoformat()),
        )

    def to_dict(self) -> dict:
        """Сериализовать в dict для config-registry.json."""
        return {
            "name": self.title,
            "version": self.version,
            "vendor": self.vendor,
            "path": str(self.path) if self.path else None,
            "archive": str(self.archive) if self.archive else None,
            "status": self.status,
            "objects_count": self.objects_count,
            "api_methods_count": self.api_methods_count,
            "added_at": self.added_at,
        }

    def __repr__(self) -> str:
        return f"Configuration(name='{self.name}', version='{self.version}', status='{self.status}')"
