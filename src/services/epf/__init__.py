"""
Пакет epf — утилиты для создания внешних обработок 1С (.epf).

Этап 2.2: декомпозиция god-файла epf_factory.py (713 LOC) на 4 модуля:
- result: EpfFactoryResult dataclass
- json_patcher: patch_ext_proc_json, patch_form_id_json, replace_in_tree
- bsl_validator: validate_bsl
- round_trip: verify_round_trip

EpfFactory (facade) остаётся в src/services/epf_factory.py.
"""

from __future__ import annotations

from .bsl_validator import validate_bsl
from .json_patcher import patch_ext_proc_json, patch_form_id_json, replace_in_tree
from .result import EpfFactoryResult
from .round_trip import verify_round_trip

__all__ = [
    "EpfFactoryResult",
    "validate_bsl",
    "patch_ext_proc_json",
    "patch_form_id_json",
    "replace_in_tree",
    "verify_round_trip",
]
