"""
dsl_compiler.py — Тонкая обёртка для обратной совместимости.

P2.3: реальная реализация перенесена в src/dsl/ пакет.
Этот файл сохраняет `from src.services.dsl_compiler import DslCompiler` работающим.

Для нового кода используйте: `from src.dsl import DslCompiler`
"""

# noqa: F401 — все импорты реэкспортируются для обратной совместимости
from src.dsl import (  # noqa: F401
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
    DslCompiler,
    FormCompiler,
    MetaCompiler,
    MxlCompiler,
    RoleCompiler,
    SkdCompiler,
    _camel_to_words,
    _gen_uuid,
    _make_type_element,
    _normalize_object_type,
    _normalize_type,
    _parse_attribute,
)

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
