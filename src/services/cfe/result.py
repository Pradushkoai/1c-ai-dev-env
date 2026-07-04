from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BorrowResult:
    """Результат операции borrow_object."""

    object_ref: str
    object_type: str
    object_name: str
    xml_created: list[Path] = field(default_factory=list)
    registered_in_config: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class PatchMethodResult:
    """Результат операции patch_method."""

    module_path: str  # Catalog.Контрагенты.ObjectModule
    method_name: str
    interceptor_type: str  # Before | After | ModificationAndControl
    bsl_file: Path | None = None
    bsl_content: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class CfeDiffResult:
    """Результат операции diff — что перенесено в основную конфигурацию."""

    extension_path: Path
    config_path: Path
    borrowed_objects: list[dict[str, Any]] = field(default_factory=list)
    patch_methods: list[dict[str, Any]] = field(default_factory=list)
    not_in_config: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
