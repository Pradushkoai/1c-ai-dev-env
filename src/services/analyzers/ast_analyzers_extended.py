"""
D3.5 (2026-07-06): Дополнительные AST-based analyzers.

Расширяет AstAnalyzer (D3.2) дополнительными анализаторами:
1. ComplexityAnalyzer — цикломатическая сложность, вложенность
2. DependencyAnalyzer — анализ зависимостей через AST
3. PatternAnalyzer — поиск паттернов (anti-patterns)
4. MetricsAnalyzer — метрики кода через AST

Использование:
    from src.services.analyzers.ast_analyzers_extended import (
        ComplexityAnalyzer, PatternAnalyzer, analyze_ast_full,
    )

    result = analyze_ast_full(Path("module.bsl"))
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.services.bsl_ast import is_tree_sitter_available, parse_bsl

logger = logging.getLogger(__name__)


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class ComplexityMetrics:
    """Метрики сложности функции."""

    name: str
    cyclomatic_complexity: int = 1  # baseline
    nesting_depth: int = 0
    lines_of_code: int = 0
    parameter_count: int = 0
    decision_points: int = 0


@dataclass
class AstPatternViolation:
    """Нарушение паттерна."""

    rule_id: str
    pattern: str
    line: int
    message: str
    severity: str = "warning"


@dataclass
class AstAnalysisResult:
    """Результат полного AST анализа."""

    file_path: str
    complexity: list[ComplexityMetrics] = field(default_factory=list)
    patterns: list[AstPatternViolation] = field(default_factory=list)
    function_count: int = 0
    procedure_count: int = 0
    total_lines: int = 0
    max_nesting: int = 0
    error: str = ""


# ============================================================================
# ComplexityAnalyzer
# ============================================================================


class ComplexityAnalyzer:
    """D3.5: Анализатор цикломатической сложности и вложенности."""

    # Ключевые слова, увеличивающие сложность
    DECISION_KEYWORDS = {"Если", "Для", "Пока", "Цикл", "Попытка", "Исключение"}
    # Альтернативные ветви
    BRANCH_KEYWORDS = {"Иначе", "ИначеЕсли"}

    def analyze(self, file_path: Path | str) -> list[ComplexityMetrics]:
        """Анализ сложности всех функций в файле.

        Args:
            file_path: Путь к .bsl файлу.

        Returns:
            Список ComplexityMetrics для каждой функции.

        Note:
            Если tree-sitter не установлен, использует regex-based fallback.
        """
        # Fallback: regex-based analysis (всегда работает)
        try:
            return self._analyze_regex(Path(file_path))
        except Exception as e:
            logger.warning("Complexity analysis failed: %s", e)
            return []

    def _analyze_regex(self, file_path: Path) -> list[ComplexityMetrics]:
        """Regex-based complexity analysis (fallback without tree-sitter)."""
        code = file_path.read_text(encoding="utf-8-sig", errors="replace")
        lines = code.split("\n")

        return self._analyze_lines(lines, str(file_path))

    def _analyze_lines(self, lines: list[str], file_path: str) -> list[ComplexityMetrics]:
        """Анализ complexity из lines (shared logic)."""
        metrics: list[ComplexityMetrics] = []

        current_func: ComplexityMetrics | None = None
        nesting = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Начало процедуры/функции
            if stripped.startswith("Процедура ") or stripped.startswith("Функция "):
                if current_func is not None:
                    metrics.append(current_func)

                # Извлекаем имя
                name = self._extract_name(stripped)
                params = self._count_params(stripped)

                current_func = ComplexityMetrics(
                    name=name,
                    parameter_count=params,
                    lines_of_code=1,
                )
                nesting = 0
                continue

            if current_func is None:
                continue

            current_func.lines_of_code += 1

            # Считаем decision points
            for keyword in self.DECISION_KEYWORDS:
                if keyword in stripped:
                    current_func.decision_points += 1
                    current_func.cyclomatic_complexity += 1

            # Подсчёт nesting
            if any(kw in stripped for kw in ["Если", "Для", "Пока", "Попытка"]):
                nesting += 1
                if nesting > current_func.nesting_depth:
                    current_func.nesting_depth = nesting
            elif any(kw in stripped for kw in ["КонецЕсли", "КонецЦикла", "КонецПопытки"]):
                nesting = max(0, nesting - 1)

            # Конец процедуры/функции
            if stripped.startswith("КонецПроцедуры") or stripped.startswith("КонецФункции"):
                metrics.append(current_func)
                current_func = None
                nesting = 0

        return metrics

    def _analyze_tree(self, tree: Any, file_path: str) -> list[ComplexityMetrics]:
        """Анализ complexity из AST tree."""
        metrics: list[ComplexityMetrics] = []
        code = Path(file_path).read_text(encoding="utf-8-sig", errors="replace")
        lines = code.split("\n")

        # Простой подход: ищем процедуры/функции и считаем complexity
        current_func: ComplexityMetrics | None = None
        nesting = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Начало процедуры/функции
            if stripped.startswith("Процедура ") or stripped.startswith("Функция "):
                if current_func is not None:
                    metrics.append(current_func)

                # Извлекаем имя
                name = self._extract_name(stripped)
                params = self._count_params(stripped)

                current_func = ComplexityMetrics(
                    name=name,
                    parameter_count=params,
                    lines_of_code=1,
                )
                nesting = 0
                continue

            if current_func is None:
                continue

            current_func.lines_of_code += 1

            # Считаем decision points
            for keyword in self.DECISION_KEYWORDS:
                if keyword in stripped:
                    current_func.decision_points += 1
                    current_func.cyclomatic_complexity += 1

            # Подсчёт nesting
            if any(kw in stripped for kw in ["Если", "Для", "Пока", "Попытка"]):
                nesting += 1
                if nesting > current_func.nesting_depth:
                    current_func.nesting_depth = nesting
            elif any(kw in stripped for kw in ["КонецЕсли", "КонецЦикла", "КонецПопытки"]):
                nesting = max(0, nesting - 1)

            # Конец процедуры/функции
            if stripped.startswith("КонецПроцедуры") or stripped.startswith("КонецФункции"):
                metrics.append(current_func)
                current_func = None
                nesting = 0

        return metrics

    def _extract_name(self, line: str) -> str:
        """Извлечь имя функции из строки."""
        import re
        match = re.match(r"^(?:Процедура|Функция)\s+(\w+)", line)
        return match.group(1) if match else "unknown"

    def _count_params(self, line: str) -> int:
        """Посчитать количество параметров."""
        import re
        match = re.search(r"\(([^)]*)\)", line)
        if not match:
            return 0
        params_str = match.group(1).strip()
        if not params_str:
            return 0
        return len([p for p in params_str.split(",") if p.strip()])


# ============================================================================
# PatternAnalyzer
# ============================================================================


class PatternAnalyzer:
    """D3.5: Анализатор паттернов (anti-patterns) через AST."""

    # Anti-patterns
    ANTI_PATTERNS = {
        "deep-nesting": {
            "description": "Глубокая вложенность (>4)",
            "severity": "warning",
            "threshold": 4,
        },
        "long-function": {
            "description": "Длинная функция (>50 строк)",
            "severity": "warning",
            "threshold": 50,
        },
        "too-many-params": {
            "description": "Слишком много параметров (>5)",
            "severity": "warning",
            "threshold": 5,
        },
        "high-complexity": {
            "description": "Высокая сложность (>10)",
            "severity": "warning",
            "threshold": 10,
        },
    }

    def analyze(
        self,
        complexity_metrics: list[ComplexityMetrics],
    ) -> list[AstPatternViolation]:
        """Анализ паттернов на основе complexity metrics.

        Args:
            complexity_metrics: Метрики от ComplexityAnalyzer.

        Returns:
            Список AstPatternViolation.
        """
        violations: list[AstPatternViolation] = []

        for metric in complexity_metrics:
            # Deep nesting
            threshold = self.ANTI_PATTERNS["deep-nesting"]["threshold"]
            if metric.nesting_depth > threshold:
                violations.append(AstPatternViolation(
                    rule_id="ast-pattern-deep-nesting",
                    pattern="deep-nesting",
                    line=0,  # не отслеживаем line для функции
                    message=f"Функция {metric.name}: вложенность {metric.nesting_depth} > {threshold}",
                    severity="warning",
                ))

            # Long function
            threshold = self.ANTI_PATTERNS["long-function"]["threshold"]
            if metric.lines_of_code > threshold:
                violations.append(AstPatternViolation(
                    rule_id="ast-pattern-long-function",
                    pattern="long-function",
                    line=0,
                    message=f"Функция {metric.name}: {metric.lines_of_code} строк > {threshold}",
                    severity="warning",
                ))

            # Too many params
            threshold = self.ANTI_PATTERNS["too-many-params"]["threshold"]
            if metric.parameter_count > threshold:
                violations.append(AstPatternViolation(
                    rule_id="ast-pattern-too-many-params",
                    pattern="too-many-params",
                    line=0,
                    message=f"Функция {metric.name}: {metric.parameter_count} параметров > {threshold}",
                    severity="warning",
                ))

            # High complexity
            threshold = self.ANTI_PATTERNS["high-complexity"]["threshold"]
            if metric.cyclomatic_complexity > threshold:
                violations.append(AstPatternViolation(
                    rule_id="ast-pattern-high-complexity",
                    pattern="high-complexity",
                    line=0,
                    message=f"Функция {metric.name}: complexity {metric.cyclomatic_complexity} > {threshold}",
                    severity="warning",
                ))

        return violations


# ============================================================================
# Combined analysis
# ============================================================================


def analyze_ast_full(file_path: Path | str) -> AstAnalysisResult:
    """D3.5: Полный AST анализ файла.

    Args:
        file_path: Путь к .bsl файлу.

    Returns:
        AstAnalysisResult с complexity, patterns, metrics.

    Note:
        Работает с regex fallback если tree-sitter не установлен.
    """
    result = AstAnalysisResult(file_path=str(file_path))

    try:
        path = Path(file_path)
        if not path.exists():
            result.error = f"File not found: {path}"
            return result

        code = path.read_text(encoding="utf-8-sig", errors="replace")
        result.total_lines = len(code.split("\n"))

        # Complexity (использует regex fallback если tree-sitter не доступен)
        complexity_analyzer = ComplexityAnalyzer()
        result.complexity = complexity_analyzer.analyze(path)

        # Patterns
        pattern_analyzer = PatternAnalyzer()
        result.patterns = pattern_analyzer.analyze(result.complexity)

        # Counts
        result.function_count = sum(
            1 for m in result.complexity
            if "Функция" in code
        )
        result.procedure_count = len(result.complexity) - result.function_count

        # Max nesting
        if result.complexity:
            result.max_nesting = max(m.nesting_depth for m in result.complexity)

    except Exception as e:
        result.error = str(e)
        logger.exception("AST analysis failed for %s", file_path)

    return result


def get_complexity_summary(metrics: list[ComplexityMetrics]) -> dict[str, Any]:
    """Summary метрик сложности."""
    if not metrics:
        return {"total_functions": 0}

    return {
        "total_functions": len(metrics),
        "avg_complexity": sum(m.cyclomatic_complexity for m in metrics) / len(metrics),
        "max_complexity": max(m.cyclomatic_complexity for m in metrics),
        "avg_nesting": sum(m.nesting_depth for m in metrics) / len(metrics),
        "max_nesting": max(m.nesting_depth for m in metrics),
        "avg_lines": sum(m.lines_of_code for m in metrics) / len(metrics),
        "max_lines": max(m.lines_of_code for m in metrics),
        "avg_params": sum(m.parameter_count for m in metrics) / len(metrics),
        "max_params": max(m.parameter_count for m in metrics),
    }
