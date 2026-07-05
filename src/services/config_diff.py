"""
D2.6 (2026-07-05): Configuration diff engine — структурный diff метаданных.

Сравнивает две версии конфигурации (два unified-metadata-index.json)
и показывает: что добавлено, удалено, изменено.

Использование:
    from src.services.config_diff import ConfigDiff

    differ = ConfigDiff()
    result = differ.diff(old_index_path, new_index_path)
    print(result.summary())
    for change in result.changes:
        print(change)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DiffChange:
    """Одно изменение между двумя версиями конфигурации."""

    change_type: str  # "added" | "removed" | "modified"
    object_type: str  # "Catalog", "Document", etc.
    object_name: str
    old_uuid: str = ""
    new_uuid: str = ""
    details: str = ""

    def __str__(self) -> str:
        symbol = {"added": "+", "removed": "-", "modified": "~"}[self.change_type]
        return f"  {symbol} {self.object_type}.{self.object_name} — {self.change_type}{f': {self.details}' if self.details else ''}"


@dataclass
class DiffResult:
    """Результат сравнения двух конфигураций."""

    old_version: str = ""
    new_version: str = ""
    changes: list[DiffChange] = field(default_factory=list)
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0

    def summary(self) -> str:
        """Краткая сводка изменений."""
        return (
            f"=== Config Diff ===\n"
            f"  Added: {self.added_count}\n"
            f"  Removed: {self.removed_count}\n"
            f"  Modified: {self.modified_count}\n"
            f"  Unchanged: {self.unchanged_count}\n"
            f"  Total changes: {len(self.changes)}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict."""
        return {
            "old_version": self.old_version,
            "new_version": self.new_version,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "modified_count": self.modified_count,
            "unchanged_count": self.unchanged_count,
            "changes": [
                {
                    "change_type": c.change_type,
                    "object_type": c.object_type,
                    "object_name": c.object_name,
                    "old_uuid": c.old_uuid,
                    "new_uuid": c.new_uuid,
                    "details": c.details,
                }
                for c in self.changes
            ],
        }


class ConfigDiff:
    """
    D2.6: Configuration diff engine.

    Сравнивает два unified-metadata-index.json файла и находит:
    - Добавленные объекты (added)
    - Удалённые объекты (removed)
    - Изменённые объекты (modified) — по UUID или имени
    """

    def diff(
        self,
        old_index_path: Path | str,
        new_index_path: Path | str,
    ) -> DiffResult:
        """
        Сравнить две версии конфигурации.

        Args:
            old_index_path: Путь к старому unified-metadata-index.json.
            new_index_path: Путь к новому unified-metadata-index.json.

        Returns:
            DiffResult с списком изменений.
        """
        old_data = self._load_index(old_index_path)
        new_data = self._load_index(new_index_path)

        old_objects = self._index_by_key(old_data)
        new_objects = self._index_by_key(new_data)

        result = DiffResult(
            old_version=old_data.get("version", ""),
            new_version=new_data.get("version", ""),
        )

        old_keys = set(old_objects.keys())
        new_keys = set(new_objects.keys())

        # Added: есть в new, нет в old
        for key in sorted(new_keys - old_keys):
            obj = new_objects[key]
            result.changes.append(DiffChange(
                change_type="added",
                object_type=obj.get("type", ""),
                object_name=obj.get("name", ""),
                new_uuid=obj.get("uuid", ""),
            ))
            result.added_count += 1

        # Removed: есть в old, нет в new
        for key in sorted(old_keys - new_keys):
            obj = old_objects[key]
            result.changes.append(DiffChange(
                change_type="removed",
                object_type=obj.get("type", ""),
                object_name=obj.get("name", ""),
                old_uuid=obj.get("uuid", ""),
            ))
            result.removed_count += 1

        # Modified: есть в обоих, но UUID отличается
        for key in sorted(old_keys & new_keys):
            old_obj = old_objects[key]
            new_obj = new_objects[key]
            old_uuid = old_obj.get("uuid", "")
            new_uuid = new_obj.get("uuid", "")
            if old_uuid != new_uuid:
                result.changes.append(DiffChange(
                    change_type="modified",
                    object_type=old_obj.get("type", ""),
                    object_name=old_obj.get("name", ""),
                    old_uuid=old_uuid,
                    new_uuid=new_uuid,
                    details="UUID changed",
                ))
                result.modified_count += 1
            else:
                result.unchanged_count += 1

        return result

    @staticmethod
    def _load_index(path: Path | str) -> dict[str, Any]:
        """Загрузить unified-metadata-index.json."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Index file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _index_by_key(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Индексировать объекты по ключу (type.name).

        Использует type.name как ключ для matching переименованных объектов.
        """
        result: dict[str, dict[str, Any]] = {}
        objects = data.get("objects", [])
        if isinstance(objects, list):
            for obj in objects:
                key = f"{obj.get('type', '')}.{obj.get('name', '')}"
                result[key] = obj
        return result
