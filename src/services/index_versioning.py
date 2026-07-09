"""
D2.3 (2026-07-05): Версионирование индексов.

Каждый индекс (unified-metadata-index.json, api-reference.json, и т.д.)
должен иметь поле schema_version. При изменении схемы — миграция через
IndexMigration chain (аналог DB migrations).

Использование:
    from src.services.index_versioning import CURRENT_SCHEMA_VERSION, check_schema_version, migrate_index

    # Проверить версию индекса
    version = check_schema_version(index_path)
    if version < CURRENT_SCHEMA_VERSION:
        migrate_index(index_path, from_version=version, to_version=CURRENT_SCHEMA_VERSION)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# D2.3: Текущая версия схемы индексов
# v1: исходная (до D2.3)
# v2: D2.3 — добавлено schema_version поле
CURRENT_SCHEMA_VERSION = 2


def check_schema_version(index_path: Path | str) -> int:
    """
    D2.3: Проверить версию схемы индекса.

    Args:
        index_path: Путь к JSON индексу.

    Returns:
        Версия схемы (int). 1 если поле отсутствует (legacy).
    """
    index_path = Path(index_path)
    if not index_path.exists():
        return 0

    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("schema_version", 1)
    except (json.JSONDecodeError, OSError):
        return 0


def needs_migration(index_path: Path | str) -> bool:
    """
    D2.3: Проверить, нужна ли миграция индекса.

    Args:
        index_path: Путь к JSON индексу.

    Returns:
        True если версия < CURRENT_SCHEMA_VERSION.
    """
    version = check_schema_version(index_path)
    return version < CURRENT_SCHEMA_VERSION


def migrate_index(index_path: Path | str) -> bool:
    """
    D2.3: Мигрировать индекс до текущей версии схемы.

    Миграции:
    - v1 → v2: добавить schema_version=2 поле

    Args:
        index_path: Путь к JSON индексу.

    Returns:
        True если миграция успешна, False если ошибка.
    """
    index_path = Path(index_path)
    if not index_path.exists():
        return False

    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("index_migration_failed: %s", e)
        return False

    current_version = data.get("schema_version", 1)

    if current_version >= CURRENT_SCHEMA_VERSION:
        return True  # Уже актуально

    # v1 → v2: добавить schema_version
    if current_version < 2:
        data["schema_version"] = 2
        logger.info("index_migrated: v1 → v2, path=%s", index_path)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True


def add_schema_version_if_missing(index_path: Path | str) -> None:
    """
    D2.3: Добавить schema_version в индекс если отсутствует.

    Используется после построения индекса — гарантирует, что
    новый индекс имеет актуальную версию схемы.
    """
    index_path = Path(index_path)
    if not index_path.exists():
        return

    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    if "schema_version" not in data:
        data["schema_version"] = CURRENT_SCHEMA_VERSION
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
