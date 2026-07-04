"""
Общие модели и хелперы для standards.* модулей.

Этап 2.1: вынесено из src/services/analyzers/check_1c_standards.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


# ============================================================================
# МОДЕЛИ
# ============================================================================


# ============================================================================
# МОДЕЛИ
# ============================================================================


@dataclass
class Violation:
    """Одно нарушение стандарта 1С."""

    file: str
    line: int
    col: int
    rule_id: str
    severity: str  # error | warning
    message: str

    def format_text(self) -> str:
        """Текстовый формат (как ESLint)."""
        return f"  {self.severity.upper():7} {self.rule_id:20} {self.file}:{self.line}:{self.col}  {self.message}"


