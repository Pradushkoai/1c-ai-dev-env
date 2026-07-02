"""
Реестр конфигураций 1С.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .configuration import Configuration


class ConfigurationRegistry:
    """Управление реестром конфигураций в config-registry.json."""

    def __init__(self, registry_path: Path, project_root: Path):
        self._path = registry_path
        self._project_root = project_root
        self._configs: dict[str, Configuration] = {}
        self._load()

    # --- Загрузка / сохранение ---

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            for name, cfg_data in data.get("configs", {}).items():
                self._configs[name] = Configuration.from_dict(name, cfg_data, self._project_root)

    def _save(self) -> None:
        data = {
            "version": "2.0",
            "configs": {name: cfg.to_dict() for name, cfg in self._configs.items()},
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- CRUD ---

    def add(self, config: Configuration) -> None:
        """Добавить или обновить конфигурацию."""
        self._configs[config.name] = config
        self._save()

    def remove(self, name: str) -> bool:
        """Удалить конфигурацию по имени."""
        if name in self._configs:
            del self._configs[name]
            self._save()
            return True
        return False

    def get(self, name: str) -> Configuration | None:
        return self._configs.get(name)

    def list_all(self) -> list[Configuration]:
        return list(self._configs.values())

    def list_active(self) -> list[Configuration]:
        return [c for c in self._configs.values() if c.is_active()]

    def list_archived(self) -> list[Configuration]:
        return [c for c in self._configs.values() if c.is_archived()]

    def __contains__(self, name: str) -> bool:
        return name in self._configs

    def __iter__(self) -> Iterator[Configuration]:
        return iter(self._configs.values())

    def __len__(self) -> int:
        return len(self._configs)
