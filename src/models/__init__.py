"""Модели данных проекта."""

from .config_registry import ConfigurationRegistry as ConfigurationRegistry
from .configuration import Configuration as Configuration

__all__ = ["ConfigurationRegistry", "Configuration"]
