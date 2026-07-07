"""
src/core/analyzers/ — Анализаторы: BSL AST, security, standards.

Phase 2 of refactoring: core layer for code analyzers.

Backward compat: реэкспортирует из src.services.analyzers для нового пути.
"""

from __future__ import annotations

# Re-export анализаторов
from src.services.bsl_tree_sitter import (
    BslSymbol,
    BslTreeSitterParser,
    extract_symbols,
    extract_symbols_from_file,
    is_available,
)
from src.services.analyzers.ast_analyzer import AstAnalyzer, AstViolation
from src.services.analyzers.query_analyzer import QueryAnalyzer, QueryIssue
from src.services.analyzers.query_parser import (
    ParsedBatch,
    ParsedQuery,
    QueryField,
    QueryParser,
    QueryTable,
)
from src.services.analyzers.query_validator_static import (
    StaticQueryValidator,
    ValidationIssue,
    ValidationResult,
)
from src.services.analyzers.security_auditor import SecurityAuditor
from src.services.analyzers.transaction_checker import TransactionChecker

__all__ = [
    "AstAnalyzer",
    "AstViolation",
    "BslSymbol",
    "BslTreeSitterParser",
    "ParsedBatch",
    "ParsedQuery",
    "QueryAnalyzer",
    "QueryField",
    "QueryIssue",
    "QueryParser",
    "QueryTable",
    "SecurityAuditor",
    "StaticQueryValidator",
    "TransactionChecker",
    "ValidationIssue",
    "ValidationResult",
    "extract_symbols",
    "extract_symbols_from_file",
    "is_available",
]
