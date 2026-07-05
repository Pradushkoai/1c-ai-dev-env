"""facade.py — DslCompiler — единый фасад для 5 компиляторов."""

from __future__ import annotations

from pathlib import Path

from ._common import CompileResult
from .form import FormCompiler
from .meta import MetaCompiler
from .mxl import MxlCompiler
from .role import RoleCompiler
from .skd import SkdCompiler


class DslCompiler:
    """Единый фасад для всех 5 компиляторов DSL.

    1. MetaCompiler — метаданные 1С (23 типа объектов)
    2. FormCompiler — управляемые формы (Form.xml)
    3. SkdCompiler — схемы компоновки данных (СКД)
    4. MxlCompiler — табличные документы (MXL, печатные формы)
    5. RoleCompiler — роли 1С (Rights.xml)
    """

    def __init__(self) -> None:
        self.meta = MetaCompiler()
        self.form = FormCompiler()
        self.skd = SkdCompiler()
        self.mxl = MxlCompiler()
        self.role = RoleCompiler()

    def compile_meta(self, definition: str | dict | Path, output_dir: str | Path) -> CompileResult:
        """Компилировать объект метаданных (Catalog, Document, и т.д.)."""
        return self.meta.compile(definition, output_dir)

    def compile_form(self, definition: str | dict | Path, output_path: str | Path) -> CompileResult:
        """Компилировать управляемую форму."""
        return self.form.compile(definition, output_path)

    def compile_skd(self, definition: str | dict | Path, output_path: str | Path) -> CompileResult:
        """Компилировать схему компоновки данных (СКД)."""
        return self.skd.compile(definition, output_path)

    def compile_mxl(self, definition: str | dict | Path, output_path: str | Path) -> CompileResult:
        """Компилировать табличный документ (MXL, печатная форма)."""
        return self.mxl.compile(definition, output_path)

    def compile_role(self, definition: str | dict | Path, output_dir: str | Path) -> CompileResult:
        """Компилировать роль 1С (Rights.xml + метаданные)."""
        return self.role.compile(definition, output_dir)
