"""
Кастомные исключения проекта 1C AI Development Environment.

Иерархия:
    ProjectError (базовое)
    ├── ConfigError (ошибки конфигураций)
    │   ├── ConfigAlreadyExistsError
    │   ├── ConfigNotFoundError
    │   └── ConfigNotActiveError
    ├── ArchiveError (ошибки архивации)
    │   ├── ArchiveNotFoundError
    │   └── ArchiveCorruptedError
    ├── BSLAnalysisError (ошибки анализа BSL)
    │   ├── BSLBinaryNotFoundError
    │   └── BSLAnalysisTimeoutError
    └── IndexError (ошибки индексации)
        └── IndexBuildError
"""

from __future__ import annotations


class ProjectError(Exception):
    """Базовое исключение проекта."""


# === Конфигурации ===


class ConfigError(ProjectError):
    """Базовая ошибка конфигурации."""


class ConfigAlreadyExistsError(ConfigError):
    """Конфигурация с таким именем уже существует."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Конфигурация '{name}' уже существует")


class ConfigNotFoundError(ConfigError):
    """Конфигурация не найдена."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Конфигурация '{name}' не найдена")


class ConfigNotActiveError(ConfigError):
    """Конфигурация не активна."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Конфигурация '{name}' не активна")


# === Архивация ===


class ArchiveError(ProjectError):
    """Базовая ошибка архивации."""


class ArchiveNotFoundError(ArchiveError):
    """Архив не найден."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Архив для '{name}' не найден")


class ArchiveCorruptedError(ArchiveError):
    """Архив повреждён."""

    def __init__(self, path: str, detail: str = ""):
        self.path = path
        super().__init__(f"Архив повреждён: {path} ({detail})" if detail else f"Архив повреждён: {path}")


# === BSL анализ ===


class BSLAnalysisError(ProjectError):
    """Базовая ошибка анализа BSL."""


class BSLBinaryNotFoundError(BSLAnalysisError):
    """BSL LS binary не найден."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"BSL Language Server не найден: {path}. Запустите: bash install.sh")


class BSLAnalysisTimeoutError(BSLAnalysisError):
    """Превышен таймаут анализа BSL."""

    def __init__(self, timeout: int):
        self.timeout = timeout
        super().__init__(f"Превышен таймаут BSL LS: {timeout} сек")


# === Индексация ===


class IndexBuildError(ProjectError):
    """Ошибка построения индекса."""

    def __init__(self, config_name: str, detail: str = ""):
        self.config_name = config_name
        super().__init__(f"Ошибка построения индекса для '{config_name}'" + (f": {detail}" if detail else ""))
