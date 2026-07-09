"""
Модели задач: TaskContext и CheckResult.

Единый контракт между CLI / MCP / internal API.

TaskContext — что собрано для LLM (платформа + конфигурация + стандарты + база знаний)
CheckResult — что нашли анализаторы (violations + verdict + metrics)
"""

from __future__ import annotations
from typing import Any

from dataclasses import dataclass, field


@dataclass
class PlatformMethodHit:
    """Один результат поиска метода платформы 1С."""

    name_ru: str = ""
    name_en: str = ""
    score: float = 0.0
    syntax: str = ""
    description: str = ""
    context: str = ""
    # Авто-проверка доступности (заполняется в _search_platform_methods)
    availability_raw: str = ""
    availability_warning: str = ""  # "НЕ доступен на клиенте!" если метод недоступен в типичном контексте


@dataclass
class ModuleApiHit:
    """Один модуль из api-reference.json."""

    name: str = ""
    methods_count: int = 0
    methods: list[dict] = field(default_factory=list)  # top-N методов


@dataclass
class MetadataObjectHit:
    """Один объект из unified-metadata-index.json."""

    type: str = ""
    name: str = ""
    synonym: str = ""
    attributes_count: int = 0
    tabular_sections_count: int = 0
    forms_count: int = 0


@dataclass
class SkdSchemaHit:
    """Одна СКД-схема из skd-index.json."""

    parent_type: str = ""
    parent_name: str = ""
    name: str = ""
    data_sets_count: int = 0
    parameters_count: int = 0


@dataclass
class FormHit:
    """Одна форма из form-index.json."""

    parent_type: str = ""
    parent_name: str = ""
    name: str = ""
    element_count: int = 0


@dataclass
class KnowledgeArticleHit:
    """Статья из базы знаний."""

    category: str = ""
    title: str = ""
    score: float = 0.0
    path: str = ""


@dataclass
class TaskContext:
    """Единый контекст для LLM при решении задачи.

    Используется:
    - CLI: 1c-ai solve context "..." --config ut11
    - MCP: solve_context(query=..., config=...)
    - Internal: src.services.task_processor.TaskProcessor.solve()
    """

    query: str = ""
    config_name: str = ""

    # Источники (могут быть пустыми если данных нет)
    platform_methods: list[PlatformMethodHit] = field(default_factory=list)
    api_modules: list[ModuleApiHit] = field(default_factory=list)
    metadata_objects: list[MetadataObjectHit] = field(default_factory=list)
    subsystems: list[dict] = field(default_factory=list)
    event_subscriptions: list[dict] = field(default_factory=list)
    scheduled_jobs: list[dict] = field(default_factory=list)
    skd_schemas: list[SkdSchemaHit] = field(default_factory=list)
    forms: list[FormHit] = field(default_factory=list)
    knowledge_articles: list[KnowledgeArticleHit] = field(default_factory=list)

    # Стандарты (summary — что доступно)
    standards_summary: dict[str, Any] = field(default_factory=dict)

    # Что НЕ удалось найти (для диагностики)
    missing_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "config": self.config_name,
            "platform_methods": [
                {
                    "name_ru": m.name_ru,
                    "name_en": m.name_en,
                    "score": m.score,
                    "syntax": m.syntax,
                    "description": m.description,
                    "context": m.context,
                    "availability_raw": m.availability_raw,
                    "availability_warning": m.availability_warning,
                }
                for m in self.platform_methods
            ],
            "api_modules": [m.__dict__ for m in self.api_modules],
            "metadata_objects": [m.__dict__ for m in self.metadata_objects],
            "subsystems": self.subsystems,
            "event_subscriptions": self.event_subscriptions,
            "scheduled_jobs": self.scheduled_jobs,
            "skd_schemas": [s.__dict__ for s in self.skd_schemas],
            "forms": [f.__dict__ for f in self.forms],
            "knowledge_articles": [k.__dict__ for k in self.knowledge_articles],
            "standards_summary": self.standards_summary,
            "missing_sources": self.missing_sources,
            "warnings": self.warnings,
        }

    @property
    def total_hits(self) -> int:
        """Суммарное количество найденных релевантных сущностей."""
        return (
            len(self.platform_methods)
            + len(self.api_modules)
            + len(self.metadata_objects)
            + len(self.skd_schemas)
            + len(self.forms)
            + len(self.knowledge_articles)
        )


@dataclass
class Violation:
    """Одно нарушение от одного из анализаторов."""

    source: str  # bsl_ls | check_1c_standards | security_auditor | ...
    rule_id: str
    severity: str  # error | warning | critical | high | info
    line: int = 0
    message: str = ""
    file: str = ""


@dataclass
class CodeMetric:
    """Метрики кода (от code_metrics analyzer)."""

    loc: int = 0
    lloc: int = 0
    cyclomatic_complexity: float = 0.0
    cognitive_complexity: float = 0.0
    max_nesting: int = 0
    methods_count: int = 0
    is_god_object: bool = False
    long_methods: list[dict] = field(default_factory=list)
    health_score: float = 0.0


@dataclass
class CheckResult:
    """Результат полной проверки .bsl файла.

    Единый формат для CLI / MCP / internal.
    """

    file: str = ""
    level: str = "standard"  # quick | standard | full
    violations: list[Violation] = field(default_factory=list)
    metrics: CodeMetric | None = None
    bsl_ls_available: bool = False
    analyzers_run: list[str] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(1 for v in self.violations if v.severity.lower() in ("error", "critical", "high"))

    @property
    def total_warnings(self) -> int:
        return sum(1 for v in self.violations if v.severity.lower() not in ("error", "critical", "high"))

    @property
    def verdict(self) -> str:
        """ready | warnings | errors"""
        if self.total_errors == 0 and self.total_warnings == 0:
            return "ready"
        if self.total_errors == 0:
            return "warnings"
        return "errors"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "level": self.level,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "verdict": self.verdict,
            "bsl_ls_available": self.bsl_ls_available,
            "analyzers_run": self.analyzers_run,
            "violations": [
                {
                    "source": v.source,
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "line": v.line,
                    "message": v.message,
                    "file": v.file,
                }
                for v in self.violations
            ],
            "metrics": self.metrics.__dict__ if self.metrics else None,
        }
