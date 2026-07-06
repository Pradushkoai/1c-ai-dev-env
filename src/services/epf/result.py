"""
EpfFactoryResult — результат работы EpfFactory.create_epf.

Этап 2.2: вынесено из src/services/epf_factory.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class EpfFactoryResult:
    """Результат работы EpfFactory.create_epf."""

    ok: bool = False
    error: str = ""
    epf_path: Path | None = None
    size_bytes: int = 0
    name: str = ""
    synonym: str = ""
    proc_uuid: str = ""
    form_uuid: str = ""
    bsl_lines: int = 0
    bsl_warnings: int = 0
    bsl_errors: int = 0
    bsl_validation_ok: bool = False
    round_trip_ok: bool = False
    work_dir: Path | None = None  # если save_sources=True
    native_mode: bool = False  # T5.1b: True если создано через NativeEpfWriter
