"""
Пакет builders — построение индексов конфигурации 1С.

Этап 2.4: build_config_index_generic.py перенесён из scripts/ в src/services/builders/config_index.py.

Использование:
    from src.services.builders.config_index import build_index
"""

from __future__ import annotations

from .config_index import build_index

__all__ = ["build_index"]
