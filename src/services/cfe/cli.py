"""
CLI helpers для CFE операций (без PathManager).

Этап 2.5: вынесено из src/services/cfe_manager.py.
"""

from __future__ import annotations

from pathlib import Path

from .result import BorrowResult, CfeDiffResult, PatchMethodResult


def borrow_object_cli(
    extension_path: str,
    config_path: str,
    object_ref: str,
) -> BorrowResult:
    """CLI wrapper для borrow_object."""
    from ..cfe_manager import CfeManager

    manager = CfeManager()
    return manager.borrow_object(Path(extension_path), Path(config_path), object_ref)


def patch_method_cli(
    extension_path: str,
    module_path: str,
    method_name: str,
    interceptor_type: str,
    context: str = "НаСервере",
    is_function: bool = False,
) -> PatchMethodResult:
    """CLI wrapper для patch_method."""
    from ..cfe_manager import CfeManager

    manager = CfeManager()
    return manager.patch_method(
        Path(extension_path),
        module_path,
        method_name,
        interceptor_type,
        context,
        is_function,
    )


def diff_cli(extension_path: str, config_path: str) -> CfeDiffResult:
    """CLI wrapper для diff."""
    from ..cfe_manager import CfeManager

    manager = CfeManager()
    return manager.diff(Path(extension_path), Path(config_path))
