"""
analyzers.py — ABC Analyzer protocol для OCP-compliant архитектуры.

P2.12: до фикса TaskProcessor.check() содержал 7 if-блоков, по одному на
каждый analyzer. Добавление нового analyzer требовало модификации
TaskProcessor.check() — нарушение Open-Closed Principle.

После фикса: вводится Analyzer Protocol с методом check_file().
TaskProcessor может использовать список self._analyzers, который
итеративно вызывается. Новые analyzer'ы добавляются через регистрацию
в списке, без модификации TaskProcessor.check().

Замечание: для обратной совместимости существующий метод check() сохранён.
Новый метод check_via_analyzers() использует Analyzer protocol.
Миграция на новый API — постепенная.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..path_manager import PathManager

# ============================================================================
# Protocol
# ============================================================================


@runtime_checkable
class Analyzer(Protocol):
    """
    Protocol для всех анализаторов BSL/XML кода.

    Конкретные реализации: BSLAnalyzerAdapter, SecurityAuditorAdapter,
    StandardsCheckerAdapter, TransactionCheckerAdapter, QueryAnalyzerAdapter,
    CodeMetricsAdapter, MetadataStandardsAdapter.

    Каждый Analyzer:
    1. Имеет уникальное имя (source) — используется в Violation.source.
    2. Имеет уровень запуска (level): 'quick' | 'standard' | 'full'.
    3. Возвращает list[Violation] для данного файла.
    4. Должен быть устойчив к ошибкам (не падать на одном файле).
    """

    @property
    def source(self) -> str:
        """Уникальное имя analyzer'а (например, 'security_auditor')."""
        ...

    @property
    def min_level(self) -> str:
        """Минимальный уровень запуска: 'quick' | 'standard' | 'full'.

        - 'quick': запускается на всех уровнях (quick/standard/full).
        - 'standard': запускается на standard и full.
        - 'full': запускается только на full.
        """
        ...

    def check_file(self, file_path: Path) -> list[AnalyzerViolation]:
        """
        Запустить analyzer на файле.

        Args:
            file_path: Путь к .bsl или .xml файлу.

        Returns:
            Список нарушений (пустой если нарушений нет).
        """
        ...


# ============================================================================
# Dataclass for violations
# ============================================================================


@dataclass
class AnalyzerViolation:
    """Нарушение, найденное analyzer'ом."""

    rule_id: str
    severity: str  # error | warning | info
    line: int
    message: str
    file: str = ""
    source: str = ""  # имя analyzer'а, который нашёл нарушение


# ============================================================================
# Level hierarchy
# ============================================================================


# Уровни проверки в порядке возрастания строгости.
# analyzer с min_level='quick' запускается на всех уровнях.
# analyzer с min_level='full' запускается только на level='full'.
_LEVEL_ORDER: dict[str, int] = {"quick": 0, "standard": 1, "full": 2}


def _level_allows(level: str, min_level: str) -> bool:
    """Проверить, что analyzer с min_level должен запускаться на данном level."""
    return _LEVEL_ORDER.get(level, 0) >= _LEVEL_ORDER.get(min_level, 0)


# ============================================================================
# Helper для загрузки скриптов из scripts/
# ============================================================================


def _load_script(script_name: str, paths: PathManager) -> object | None:
    """
    Загрузить analyzer-модуль.

    Этап 1.2, Группа 1: приоритет — прямой импорт из src.services.analyzers.<name>.
    Fallback (для анализаторов, ещё не перенесённых) — dynamic import из scripts/.

    Использует sys.modules кэш — если модуль уже загружен, не перезагружает.

    Args:
        script_name: Имя анализатора (например, 'security_auditor').
        paths: PathManager для fallback на scripts/.

    Returns:
        Загруженный модуль или None если не найден.
    """
    if script_name in sys.modules:
        return sys.modules[script_name]

    # Этап 1.2: сначала пробуем прямой импорт из пакета analyzers
    try:
        import importlib

        mod = importlib.import_module(f"src.services.analyzers.{script_name}")
        sys.modules[script_name] = mod
        return mod
    except ImportError:
        pass

    # Fallback: dynamic import из scripts/ (для анализаторов, ещё не перенесённых)
    import importlib.util

    script_path = paths.scripts_dir / f"{script_name}.py"
    if not script_path.exists():
        # fallback на setup/scripts
        script_path = paths.root / "setup" / "scripts" / f"{script_name}.py"
    if not script_path.exists():
        return None

    spec = importlib.util.spec_from_file_location(script_name, script_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Adapter'ы для существующих analyzer'ов
# ============================================================================


class _ScriptBasedAnalyzer:
    """
    Базовый класс для adapter'ов, которые загружают analyzer из scripts/.

    Конкретные adapter'ы наследуются и определяют:
    - source: имя analyzer'а (идентификатор)
    - min_level: минимальный уровень запуска
    - _script_name: имя .py файла в scripts/ (без расширения)
    - _analyzer_class_name: имя класса в скрипте
    - _analyzer_method: имя метода ('check_file' | 'audit_file' | 'analyze_file')
    """

    source: str = ""
    min_level: str = "quick"
    _script_name: str = ""
    _analyzer_class_name: str = ""
    _analyzer_method: str = "check_file"

    def __init__(self, paths: PathManager) -> None:
        self._paths = paths

    def _get_analyzer(self) -> object | None:
        """Загрузить и инстанцировать analyzer из скрипта."""
        mod = _load_script(self._script_name, self._paths)
        if mod is None:
            return None
        cls = getattr(mod, self._analyzer_class_name, None)
        if cls is None:
            return None
        analyzer: object | None = cls()
        return analyzer

    def check_file(self, file_path: Path) -> list[AnalyzerViolation]:
        """Запустить analyzer и преобразовать результаты в AnalyzerViolation."""
        analyzer = self._get_analyzer()
        if analyzer is None:
            return []

        try:
            method = getattr(analyzer, self._analyzer_method)
            raw_violations = method(file_path)
        except Exception:
            return []

        result: list[AnalyzerViolation] = []
        for v in raw_violations:
            result.append(
                AnalyzerViolation(
                    rule_id=getattr(v, "rule_id", ""),
                    severity=getattr(v, "severity", "warning"),
                    line=getattr(v, "line", 0),
                    message=getattr(v, "message", ""),
                    file=getattr(v, "file", str(file_path)),
                )
            )
        return result


class StandardsCheckerAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/check_1c_standards.py (56 правил)."""

    source = "check_1c_standards"
    min_level = "quick"
    _script_name = "check_1c_standards"
    _analyzer_class_name = "StandardsChecker"
    _analyzer_method = "check_file"


class SecurityAuditorAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/security_auditor.py (15 правил)."""

    source = "security_auditor"
    min_level = "quick"
    _script_name = "security_auditor"
    _analyzer_class_name = "SecurityAuditor"
    _analyzer_method = "audit_file"


class TransactionCheckerAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/transaction_checker.py (6 правил)."""

    source = "transaction_checker"
    min_level = "quick"
    _script_name = "transaction_checker"
    _analyzer_class_name = "TransactionChecker"
    _analyzer_method = "check_file"


class QueryAnalyzerAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/query_analyzer.py (10 правил)."""

    source = "query_analyzer"
    min_level = "quick"
    _script_name = "query_analyzer"
    _analyzer_class_name = "QueryAnalyzer"
    _analyzer_method = "analyze_file"


class CodeMetricsAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/code_metrics.py — метрики (только full level)."""

    source = "code_metrics"
    min_level = "full"
    _script_name = "code_metrics"
    _analyzer_class_name = "CodeMetricsAnalyzer"
    _analyzer_method = "analyze_file"


class MetadataStandardsAdapter(_ScriptBasedAnalyzer):
    """Adapter для scripts/check_metadata_standards.py (18 правил, full level)."""

    source = "check_metadata_standards"
    min_level = "full"
    _script_name = "check_metadata_standards"
    _analyzer_class_name = "MetadataStandardsChecker"
    _analyzer_method = "check_path"


# ============================================================================
# Registry
# ============================================================================


def get_default_analyzers(paths: PathManager) -> list[Analyzer]:
    """
    Возвращает список всех стандартных analyzer'ов в порядке выполнения.

    Порядок соответствует оригинальному TaskProcessor.check():
    1. StandardsChecker (quick)
    2. SecurityAuditor (quick)
    3. TransactionChecker (quick)
    4. QueryAnalyzer (quick)
    5. CodeMetrics (full)
    6. MetadataStandards (full)

    BSL LS (standard level) опущен — требует Java и обрабатывается отдельно.

    Args:
        paths: PathManager для загрузки скриптов.

    Returns:
        Список analyzer'ов.
    """
    return [
        StandardsCheckerAdapter(paths),
        SecurityAuditorAdapter(paths),
        TransactionCheckerAdapter(paths),
        QueryAnalyzerAdapter(paths),
        CodeMetricsAdapter(paths),
        MetadataStandardsAdapter(paths),
    ]


def run_analyzers(
    analyzers: list[Analyzer],
    file_path: Path,
    level: str = "standard",
) -> tuple[list[AnalyzerViolation], list[str]]:
    """
    Запустить список analyzer'ов на файле.

    Args:
        analyzers: Список Analyzer для запуска.
        file_path: Путь к файлу для анализа.
        level: Уровень проверки ('quick' | 'standard' | 'full').

    Returns:
        Кортеж (violations, analyzers_run):
        - violations: список всех найденных нарушений.
        - analyzers_run: имена analyzer'ов, которые были запущены.
    """
    violations: list[AnalyzerViolation] = []
    analyzers_run: list[str] = []

    for analyzer in analyzers:
        # Пропускаем analyzer'ы, чей min_level выше текущего.
        if not _level_allows(level, analyzer.min_level):
            continue
        try:
            analyzer_violations = analyzer.check_file(file_path)
            # Проставляем source в каждое нарушение.
            for v in analyzer_violations:
                if not v.source:
                    v.source = analyzer.source
            analyzers_run.append(analyzer.source)
            violations.extend(analyzer_violations)
        except Exception:
            # Analyzer упал — логируем и продолжаем (как в оригинале).
            continue

    return violations, analyzers_run


# ============================================================================
# Реестр для регистрации custom analyzer'ов (OCP)
# ============================================================================


# Глобальный реестр analyzer-классов (factory functions).
# Позволяет сторонним коду регистрировать свои analyzer'ы без модификации
# TaskProcessor. Соответствует OCP.
_ANALYZER_REGISTRY: dict[str, type] = {}


def register_analyzer(name: str, analyzer_cls: type) -> None:
    """
    Зарегистрировать custom analyzer в глобальном реестре.

    После регистрации analyzer будет добавлен в get_default_analyzers()
    при вызове с тем же name.

    Args:
        name: Уникальное имя analyzer'а.
        analyzer_cls: Класс, реализующий Analyzer protocol.
    """
    if name in _ANALYZER_REGISTRY:
        raise ValueError(f"Analyzer '{name}' already registered")
    _ANALYZER_REGISTRY[name] = analyzer_cls


def get_registered_analyzers() -> dict[str, type]:
    """Получить копию реестра зарегистрированных analyzer'ов."""
    return dict(_ANALYZER_REGISTRY)
