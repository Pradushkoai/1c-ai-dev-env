"""
query_optimizer.py — Предложения по оптимизации запросов 1С.

Phase C of Query Intelligence plan: принимает текст запроса → возвращает
предложения по оптимизации со ссылками на паттерны knowledge base.

Правила оптимизации (10 шт.):
- Существующие 10 правил из query_analyzer.py (переиспользуем)
- Новые правила производительности

Лицензия: MIT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.services.analyzers.query_analyzer import QueryAnalyzer, QueryIssue
from src.services.analyzers.query_templates import find_templates_by_keywords


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class OptimizationSuggestion:
    """Предложение по оптимизации."""

    rule_id: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    recommendation: str
    pattern_ref: str = ""
    optimized_fragment: str = ""  # оптимизированный фрагмент запроса


@dataclass
class OptimizationResult:
    """Результат оптимизации запроса."""

    issues: list[OptimizationSuggestion] = field(default_factory=list)
    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    pattern_refs: list[str] = field(default_factory=list)
    optimized_text: str = ""  # оптимизированная версия (если возможно)
    summary: str = ""
    total_issues: int = 0
    total_suggestions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [
                {
                    "rule_id": s.rule_id,
                    "severity": s.severity,
                    "message": s.message,
                    "recommendation": s.recommendation,
                    "pattern_ref": s.pattern_ref,
                    "optimized_fragment": s.optimized_fragment,
                }
                for s in self.issues
            ],
            "suggestions": [
                {
                    "rule_id": s.rule_id,
                    "severity": s.severity,
                    "message": s.message,
                    "recommendation": s.recommendation,
                    "pattern_ref": s.pattern_ref,
                }
                for s in self.suggestions
            ],
            "pattern_refs": self.pattern_refs,
            "optimized_text": self.optimized_text,
            "summary": self.summary,
            "total_issues": self.total_issues,
            "total_suggestions": self.total_suggestions,
        }


# ============================================================================
# OPTIMIZER
# ============================================================================


class QueryOptimizer:
    """Предлагает оптимизации для запроса 1С.

    Использует:
    - QueryAnalyzer для 10 базовых правил (Q001-Q010)
    - Дополнительные правила производительности (O001-O010)
    - Knowledge base для рекомендаций
    """

    def __init__(self, metadata_index: dict[str, Any] | None = None):
        self.metadata = metadata_index or {}
        self._query_analyzer = QueryAnalyzer()

    def optimize(self, query_text: str, config_name: str = "") -> OptimizationResult:
        """Предложить оптимизации для запроса.

        Args:
            query_text: Текст запроса 1С
            config_name: Имя конфигурации

        Returns:
            OptimizationResult с проблемами и предложениями.
        """
        if not query_text or not query_text.strip():
            result = OptimizationResult()
            result.summary = "Пустой запрос"
            return result

        result = OptimizationResult()

        # 1. Базовые правила из QueryAnalyzer (Q001-Q010)
        # QueryAnalyzer работает с BSL файлами, поэтому обернём запрос в BSL
        bsl_wrapper = f'Запрос.Текст = "{query_text}";'
        issues = self._query_analyzer.analyze_code(bsl_wrapper, "")

        for issue in issues:
            suggestion = OptimizationSuggestion(
                rule_id=issue.rule_id,
                severity=issue.severity.lower(),
                message=issue.message,
                recommendation=issue.recommendation,
            )
            # Проверяем, связан ли issue с паттерном
            if "knowledge_base" in issue.recommendation:
                # Извлекаем ссылку на паттерн
                pattern_match = re.search(r"(optimization_patterns\.md#[\w-]+)", issue.recommendation)
                if pattern_match:
                    suggestion.pattern_ref = pattern_match.group(1)
                    if suggestion.pattern_ref not in result.pattern_refs:
                        result.pattern_refs.append(suggestion.pattern_ref)

            # Критичные — в issues, остальные — в suggestions
            if suggestion.severity in ("critical", "high"):
                result.issues.append(suggestion)
            else:
                result.suggestions.append(suggestion)

        # 2. Дополнительные правила производительности (O001-O010)
        perf_suggestions = self._check_performance_rules(query_text)
        for s in perf_suggestions:
            if s.severity in ("critical", "high"):
                result.issues.append(s)
            else:
                result.suggestions.append(s)
            if s.pattern_ref and s.pattern_ref not in result.pattern_refs:
                result.pattern_refs.append(s.pattern_ref)

        # 3. Генерация summary
        result.total_issues = len(result.issues)
        result.total_suggestions = len(result.suggestions)
        result.summary = self._generate_summary(result)

        # 4. Оптимизированная версия (если есть предложения)
        result.optimized_text = self._generate_optimized_text(query_text, result)

        return result

    def _check_performance_rules(self, query_text: str) -> list[OptimizationSuggestion]:
        """Дополнительные правила производительности (O001-O010)."""
        suggestions: list[OptimizationSuggestion] = []
        text_upper = query_text.upper()

        # O001: SELECT TOP без ORDER BY
        if re.search(r"\b(?:ВЫБРАТЬ|SELECT)\s+(?:ПЕРВЫЕ|TOP\s)", query_text, re.IGNORECASE):
            if not re.search(r"\b(?:УПОРЯДОЧИТЬ|ORDER\s+BY)\b", query_text, re.IGNORECASE):
                suggestions.append(OptimizationSuggestion(
                    rule_id="O001",
                    severity="high",
                    message="SELECT TOP без ORDER BY — результат непредсказуем",
                    recommendation="Добавьте ORDER BY для детерминированного результата. См. паттерн: optimization_patterns.md#select-top-with-order",
                    pattern_ref="optimization_patterns.md#select-top-with-order",
                ))

        # O002: ИЛИ в WHERE
        where_match = re.search(r"\b(?:ГДЕ|WHERE)\s+(.+?)(?=\s+(?:СГРУППИРОВАТЬ|GROUP|УПОРЯДОЧИТЬ|ORDER|ИМЕЮЩИЕ|HAVING)|$)", query_text, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_text = where_match.group(1)
            if re.search(r"\b(?:ИЛИ|OR)\b", where_text, re.IGNORECASE):
                suggestions.append(OptimizationSuggestion(
                    rule_id="O002",
                    severity="medium",
                    message="ИЛИ в WHERE блокирует использование индексов",
                    recommendation="Замените на ОБЪЕДИНИТЬ ВСЕ. См. паттерн: optimization_patterns.md#or-to-union-all",
                    pattern_ref="optimization_patterns.md#or-to-union-all",
                ))

        # O003: Полное внешнее соединение
        if re.search(r"\b(?:ПОЛНОЕ\s+СОЕДИНЕНИЕ|FULL\s+(?:OUTER\s+)?JOIN)\b", query_text, re.IGNORECASE):
            suggestions.append(OptimizationSuggestion(
                rule_id="O003",
                severity="medium",
                message="Полное внешнее соединение (FULL JOIN) — медленно",
                recommendation="Рассмотрите альтернативу с двумя LEFT JOIN через ОБЪЕДИНИТЬ ВСЕ. См. паттерн: optimization_patterns.md#full-outer-join",
                pattern_ref="optimization_patterns.md#full-outer-join",
            ))

        # O004: JOIN с подзапросом
        if re.search(r"\b(?:ЛЕВОЕ|ВНУТРЕННЕЕ|ПРАВОЕ|ПОЛНОЕ)?\s*(?:СОЕДИНЕНИЕ|JOIN)\s+\(", query_text, re.IGNORECASE):
            suggestions.append(OptimizationSuggestion(
                rule_id="O004",
                severity="high",
                message="JOIN с подзапросом — крайне медленно",
                recommendation="Используйте временную таблицу. См. паттерн: optimization_patterns.md#temp-table-vs-join-subquery",
                pattern_ref="optimization_patterns.md#temp-table-vs-join-subquery",
            ))

        # O005: Виртуальная таблица без фильтра в параметрах
        vt_match = re.search(r"(РегистрНакопления|РегистрСведений)\.[\w]+\.(Остатки|Обороты|СрезПоследних)\s*\(([^)]*)\)", query_text, re.IGNORECASE)
        if vt_match:
            params = vt_match.group(3)
            # Если параметры пустые или только &Период — нет фильтра
            if not params.strip() or re.match(r"^\s*&\w+\s*,?\s*$", params.strip()):
                # Проверяем, есть ли WHERE после
                if re.search(r"\b(?:ГДЕ|WHERE)\b", query_text, re.IGNORECASE):
                    suggestions.append(OptimizationSuggestion(
                        rule_id="O005",
                        severity="high",
                        message="Виртуальная таблица без фильтра в параметрах + WHERE — медленно",
                        recommendation="Перенесите фильтр в параметры виртуальной таблицы. См. паттерн: optimization_patterns.md#virtual-table-params",
                        pattern_ref="optimization_patterns.md#virtual-table-params",
                    ))

        # O006: Разыменование через точку без ВЫРАЗИТЬ
        # Ищем_pattern: Таблица.Поле.Подполе (3 уровня через точку)
        if re.search(r"\b\w+\.\w+\.\w+\.\w+", query_text):
            if not re.search(r"\b(?:ВЫРАЗИТЬ|CAST)\b", query_text, re.IGNORECASE):
                suggestions.append(OptimizationSuggestion(
                    rule_id="O006",
                    severity="low",
                    message="Глубокое разыменование через точку — возможно нужен ВЫРАЗИТЬ",
                    recommendation="Используйте ВЫРАЗИТЬ для составных типов. См. паттерн: optimization_patterns.md#cast-composite-types",
                    pattern_ref="optimization_patterns.md#cast-composite-types",
                ))

        # O007: Отсутствие ИНДЕКСИРОВАТЬ ПО для временной таблицы
        if re.search(r"\b(?:ПОМЕСТИТЬ|INTO)\b", query_text, re.IGNORECASE):
            if not re.search(r"\b(?:ИНДЕКСИРОВАТЬ|INDEX\s+BY)\b", query_text, re.IGNORECASE):
                suggestions.append(OptimizationSuggestion(
                    rule_id="O007",
                    severity="medium",
                    message="Временная таблица без индекса — медленный JOIN",
                    recommendation="Добавьте ИНДЕКСИРОВАТЬ ПО для полей JOIN. См. паттерн: optimization_patterns.md#indexes",
                    pattern_ref="optimization_patterns.md#indexes",
                ))

        # O008: ОБЪЕДИНИТЬ без ВСЕ (удаляет дубликаты — доп. группировка)
        if re.search(r"\bОБЪЕДИНИТЬ\b(?!\s+ВСЕ)", query_text, re.IGNORECASE):
            suggestions.append(OptimizationSuggestion(
                rule_id="O008",
                severity="low",
                message="ОБЪЕДИНИТЬ без ВСЕ — удаляет дубликаты (дополнительная группировка)",
                recommendation="Используйте ОБЪЕДИНИТЬ ВСЕ если не нужны уникальные строки. См. паттерн: optimization_patterns.md#union-vs-union-all",
                pattern_ref="optimization_patterns.md#union-vs-union-all",
            ))

        return suggestions

    def _generate_summary(self, result: OptimizationResult) -> str:
        """Генерирует краткое описание результатов оптимизации."""
        if result.total_issues == 0 and result.total_suggestions == 0:
            return "Запрос оптимален — проблем и предложений не найдено."

        parts = []
        if result.total_issues > 0:
            parts.append(f"Найдено {result.total_issues} проблем (критичные/высокие)")
        if result.total_suggestions > 0:
            parts.append(f"{result.total_suggestions} предложений по улучшению")
        if result.pattern_refs:
            parts.append(f"Релевантные паттерны: {', '.join(result.pattern_refs)}")

        return ". ".join(parts) + "."

    def _generate_optimized_text(self, original: str, result: OptimizationResult) -> str:
        """Генерирует оптимизированную версию запроса (если возможно).

        Пока возвращает оригинальный текст — полная оптимизация требует
        AST-преобразований, что за рамками текущей фазы.
        """
        # TODO: Implement actual query rewriting based on suggestions
        return ""


# ============================================================================
# PUBLIC API
# ============================================================================


def optimize_query(
    query_text: str,
    metadata_index: dict[str, Any] | None = None,
    config_name: str = "",
) -> OptimizationResult:
    """Удобная функция для оптимизации запроса.

    Args:
        query_text: Текст запроса 1С
        metadata_index: Метаданные конфигурации (опционально)
        config_name: Имя конфигурации

    Returns:
        OptimizationResult с проблемами и предложениями.
    """
    optimizer = QueryOptimizer(metadata_index)
    return optimizer.optimize(query_text, config_name)
