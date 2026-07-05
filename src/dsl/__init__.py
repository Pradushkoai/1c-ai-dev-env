"""
DSL Compiler — JSON DSL → XML для объектов 1С.

Единый фасад DslCompiler и 5 компиляторов:
- MetaCompiler — метаданные 1С (23 типа объектов)
- FormCompiler — управляемые формы (Form.xml)
- SkdCompiler — схемы компоновки данных (СКД)
- MxlCompiler — MXL-макеты (печатные формы)
- RoleCompiler — роли 1С (Rights.xml)

P2.3: разбит из src/services/dsl_compiler.py на пакет src/dsl/.
Обратная совместимость: `from src.services.dsl_compiler import DslCompiler` работает.
"""

from ._common import (
    NS_DCS,
    NS_DCSSET,
    NS_MD,
    NS_RIGHTS,
    NS_SSD,
    NS_SSDX,
    NS_V8,
    NS_XR,
    NS_XS,
    NS_XSI,
    RU_DATA_TYPE_SYNONYMS,
    RU_TYPE_SYNONYMS,
    TYPE_MAP,
    CompileResult,
    _camel_to_words,
    _gen_uuid,
    _make_type_element,
    _normalize_object_type,
    _normalize_type,
    _parse_attribute,
)
from .facade import DslCompiler
from .form import FormCompiler
from .meta import MetaCompiler
from .mxl import MxlCompiler
from .role import RoleCompiler
from .skd import SkdCompiler

__all__ = [
    "CompileResult",
    "DslCompiler",
    "FormCompiler",
    "MetaCompiler",
    "MxlCompiler",
    "RoleCompiler",
    "SkdCompiler",
    "TYPE_MAP",
    "RU_TYPE_SYNONYMS",
    "RU_DATA_TYPE_SYNONYMS",
    "NS_MD",
    "NS_XR",
    "NS_V8",
    "NS_XS",
    "NS_XSI",
    "NS_DCS",
    "NS_DCSSET",
    "NS_SSD",
    "NS_SSDX",
    "NS_RIGHTS",
    "_camel_to_words",
    "_gen_uuid",
    "_make_type_element",
    "_normalize_object_type",
    "_normalize_type",
    "_parse_attribute",
]
