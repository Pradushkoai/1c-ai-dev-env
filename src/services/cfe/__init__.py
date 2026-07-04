"""
Пакет cfe — работа с расширениями конфигураций 1С (CFE).

Этап 2.5: декомпозиция cfe_manager.py.
- result.py: BorrowResult, PatchMethodResult, CfeDiffResult dataclasses
- cli.py: CLI helpers (без PathManager)
- CfeManager класс остаётся в src/services/cfe_manager.py (facade)

Использование:
    from src.services.cfe import BorrowResult, CfeDiffResult, PatchMethodResult
    from src.services.cfe.cli import borrow_object_cli, patch_method_cli, diff_cli
"""

from __future__ import annotations

from .result import BorrowResult, CfeDiffResult, PatchMethodResult

__all__ = ["BorrowResult", "CfeDiffResult", "PatchMethodResult"]
