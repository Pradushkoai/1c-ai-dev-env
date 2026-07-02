"""
TaskProcessor — единый пайплайн для решения задач 1С.

solve(query, config_name) → TaskContext:
    1. Поиск методов платформы 1С (BM25, если есть индекс)
    2. API-справочник конфигурации (api-reference.json)
    3. Структура объектов (unified-metadata-index.json)
    4. СКД-схемы (skd-index.json)
    5. Формы (form-index.json)
    6. База знаний (knowledge_base/)
    7. Стандарты 1С (check_1c_standards.py — 56 правил)

check(file_path, level) → CheckResult:
    quick:    check_1c_standards + security + transactions + queries (без Java)
    standard: quick + BSL LS
    full:     standard + code_metrics + metadata_standards

Это единая бизнес-логика, которую используют И CLI И MCP-сервер.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path

from ..models.task import (
    CheckResult,
    CodeMetric,
    FormHit,
    KnowledgeArticleHit,
    MetadataObjectHit,
    ModuleApiHit,
    PlatformMethodHit,
    SkdSchemaHit,
    TaskContext,
    Violation,
)
from .path_manager import PathManager

logger = logging.getLogger(__name__)


class TaskProcessor:
    """Оркестратор: собирает контекст задачи / запускает анализаторы."""

    def __init__(self, paths: PathManager):
        self._paths = paths

    # ─────────────────────────────────────────────
    # SOLVE: собрать контекст для LLM
    # ─────────────────────────────────────────────

    def solve(
        self,
        query: str,
        config_name: str = "",
        limit: int = 5,
    ) -> TaskContext:
        """Собрать полный контекст для LLM по задаче."""
        ctx = TaskContext(query=query, config_name=config_name)

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) >= 2]

        # 1. Методы платформы 1С
        self._search_platform_methods(ctx, query, limit)

        # 2-5. Источники по конфигурации
        if config_name:
            self._search_api_reference(ctx, config_name, query_words, limit)
            self._search_metadata(ctx, config_name, query_words, limit)
            self._search_skd(ctx, config_name, query_words, limit)
            self._search_forms(ctx, config_name, query_words, limit)
        else:
            ctx.warnings.append("Конфигурация не указана — поиск по метаданным пропущен")

        # 6. База знаний
        self._search_knowledge_base(ctx, query, limit)

        # 7. Стандарты (summary — что доступно для проверки)
        ctx.standards_summary = self._standards_summary()

        return ctx

    def _search_platform_methods(self, ctx: TaskContext, query: str, limit: int) -> None:
        """BM25 поиск по методам платформы 1С (если есть индекс)."""
        try:
            from .search_bm25 import search_auto
        except ImportError:
            ctx.missing_sources.append("platform_methods (search_bm25 module)")
            return

        index_path = self._paths.fast_search_index
        if not index_path.exists():
            ctx.missing_sources.append("platform_methods (index not built)")
            return

        try:
            results = search_auto(index_path, query, limit=limit)
            for r in results:
                ctx.platform_methods.append(
                    PlatformMethodHit(
                        name_ru=r.get("name_ru", ""),
                        name_en=r.get("name_en", ""),
                        score=float(r.get("score", 0.0)),
                        syntax=r.get("syntax", ""),
                        description=r.get("description", ""),
                        context=r.get("context", ""),
                    )
                )
        except Exception as e:
            ctx.warnings.append(f"platform_methods search failed: {e}")

    def _search_api_reference(
        self,
        ctx: TaskContext,
        config_name: str,
        query_words: list[str],
        limit: int,
    ) -> None:
        """Поиск модулей и методов в api-reference.json."""
        api_json = self._paths.config_api_reference_json(config_name)
        if not api_json.exists():
            ctx.missing_sources.append(f"api_reference (no api-reference.json for {config_name})")
            return

        try:
            with open(api_json, encoding="utf-8") as f:
                modules = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            ctx.warnings.append(f"api_reference load failed: {e}")
            return

        relevant = [m for m in modules if any(w in m.get("name", "").lower() for w in query_words)]
        for m in relevant[:limit]:
            ctx.api_modules.append(
                ModuleApiHit(
                    name=m.get("name", ""),
                    methods_count=m.get("methods_count", 0),
                    methods=m.get("methods", [])[:3],
                )
            )

    def _search_metadata(
        self,
        ctx: TaskContext,
        config_name: str,
        query_words: list[str],
        limit: int,
    ) -> None:
        """Поиск объектов / подсистем / подписок / регламентных в unified-metadata-index."""
        unified_path = self._paths.root / "derived" / "configs" / config_name / "unified-metadata-index.json"
        if not unified_path.exists():
            ctx.missing_sources.append(f"metadata (no unified-metadata-index.json for {config_name})")
            return

        try:
            with open(unified_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            ctx.warnings.append(f"metadata load failed: {e}")
            return

        # Объекты
        for type_name, objs in meta.get("objects", {}).items():
            for obj in objs:
                obj_name = obj.get("name", "").lower()
                if any(w in obj_name for w in query_words):
                    children = obj.get("child_objects", {})
                    ctx.metadata_objects.append(
                        MetadataObjectHit(
                            type=obj.get("type", type_name),
                            name=obj.get("name", ""),
                            synonym=obj.get("synonym", ""),
                            attributes_count=len(children.get("attributes", [])),
                            tabular_sections_count=len(children.get("tabular_sections", [])),
                            forms_count=len(children.get("forms", [])),
                        )
                    )

        # Подсистемы
        for s in meta.get("subsystems", []):
            if any(w in s.get("name", "").lower() for w in query_words):
                ctx.subsystems.append(s)

        # Подписки на события
        for e in meta.get("event_subscriptions", []):
            if any(w in e.get("name", "").lower() or w in e.get("handler", "").lower() for w in query_words):
                ctx.event_subscriptions.append(e)

        # Регламентные задания
        for s in meta.get("scheduled_jobs", []):
            if any(w in s.get("name", "").lower() or w in s.get("method_name", "").lower() for w in query_words):
                ctx.scheduled_jobs.append(s)

    def _search_skd(
        self,
        ctx: TaskContext,
        config_name: str,
        query_words: list[str],
        limit: int,
    ) -> None:
        """Поиск СКД-схем."""
        skd_path = self._paths.root / "derived" / "configs" / config_name / "skd-index.json"
        if not skd_path.exists():
            ctx.missing_sources.append(f"skd (no skd-index.json for {config_name})")
            return

        try:
            with open(skd_path, encoding="utf-8") as f:
                skd = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            ctx.warnings.append(f"skd load failed: {e}")
            return

        for s in skd.get("schemas", []):
            haystack = (s.get("parent_name", "") + " " + s.get("name", "")).lower()
            if any(w in haystack for w in query_words):
                schema = s.get("schema", {})
                ctx.skd_schemas.append(
                    SkdSchemaHit(
                        parent_type=s.get("parent_type", ""),
                        parent_name=s.get("parent_name", ""),
                        name=s.get("name", ""),
                        data_sets_count=len(schema.get("data_sets", [])),
                        parameters_count=len(schema.get("parameters", [])),
                    )
                )

    def _search_forms(
        self,
        ctx: TaskContext,
        config_name: str,
        query_words: list[str],
        limit: int,
    ) -> None:
        """Поиск форм."""
        form_path = self._paths.root / "derived" / "configs" / config_name / "form-index.json"
        if not form_path.exists():
            ctx.missing_sources.append(f"forms (no form-index.json for {config_name})")
            return

        try:
            with open(form_path, encoding="utf-8") as f:
                form_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            ctx.warnings.append(f"forms load failed: {e}")
            return

        for f in form_data.get("forms", []):
            haystack = (f.get("name", "") + " " + f.get("parent_name", "")).lower()
            if any(w in haystack for w in query_words):
                ctx.forms.append(
                    FormHit(
                        parent_type=f.get("parent_type", ""),
                        parent_name=f.get("parent_name", ""),
                        name=f.get("name", ""),
                        element_count=f.get("form", {}).get("element_count", 0),
                    )
                )

    def _search_knowledge_base(self, ctx: TaskContext, query: str, limit: int) -> None:
        """Поиск по базе знаний (паттерны, антипаттерны, best practices)."""
        try:
            from .knowledge_base import KnowledgeBase
        except ImportError:
            ctx.missing_sources.append("knowledge_base (module)")
            return

        try:
            kb = KnowledgeBase()
            results = kb.search(query, limit=limit)
            for r in results:
                ctx.knowledge_articles.append(
                    KnowledgeArticleHit(
                        category=r.get("category", ""),
                        title=r.get("title", ""),
                        score=float(r.get("score", 0.0)),
                        path=r.get("path", r.get("file", "")),
                    )
                )
        except Exception as e:
            ctx.warnings.append(f"knowledge_base search failed: {e}")

    def _standards_summary(self) -> dict:
        """Summary по доступным стандартам."""
        return {
            "bsl_ls_diagnostics": 187,
            "check_1c_standards_rules": 56,
            "check_metadata_rules": 18,
            "security_rules": 15,
            "transaction_rules": 6,
            "query_rules": 10,
            "code_metrics_count": 10,
            "total_checks": 302,
            "check_command": "1c-ai solve check <file.bsl> --level full",
        }

    # ─────────────────────────────────────────────
    # CHECK: запустить все анализаторы на .bsl файл
    # ─────────────────────────────────────────────

    def check(
        self,
        file_path: Path,
        level: str = "standard",
    ) -> CheckResult:
        """Запустить все анализаторы на .bsl файл.

        Args:
            file_path: путь к .bsl файлу
            level: quick | standard | full
                quick:    check_1c_standards + security + transactions + queries (без Java)
                standard: quick + BSL LS
                full:     standard + code_metrics + metadata_standards
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        result = CheckResult(file=str(file_path), level=level)

        scripts_dir = self._paths.scripts_dir

        def _load_script(script_name: str):
            # Если модуль уже загружен (например, тестом через sys.modules) — не перезагружаем
            if script_name in sys.modules:
                return sys.modules[script_name]
            script_path = scripts_dir / f"{script_name}.py"
            if not script_path.exists():
                # fallback на setup/scripts
                script_path = self._paths.root / "setup" / "scripts" / f"{script_name}.py"
            if not script_path.exists():
                return None
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[script_name] = mod
            spec.loader.exec_module(mod)
            return mod

        # 1. check_1c_standards (56 правил) — все уровни
        std_mod = _load_script("check_1c_standards")
        if std_mod:
            try:
                checker = std_mod.StandardsChecker()
                violations = checker.check_file(file_path)
                for v in violations:
                    result.violations.append(
                        Violation(
                            source="check_1c_standards",
                            rule_id=v.rule_id,
                            severity=v.severity,
                            line=v.line,
                            message=v.message,
                            file=v.file,
                        )
                    )
                result.analyzers_run.append("check_1c_standards")
            except Exception as e:
                logger.warning("check_1c_standards failed: %s", e)

        # 2. security_auditor (15 правил) — все уровни
        sec_mod = _load_script("security_auditor")
        if sec_mod:
            try:
                auditor = sec_mod.SecurityAuditor()
                sec_violations = auditor.audit_file(file_path)
                for v in sec_violations:
                    result.violations.append(
                        Violation(
                            source="security_auditor",
                            rule_id=v.rule_id,
                            severity=v.severity,
                            line=v.line,
                            message=v.message,
                            file=str(file_path),
                        )
                    )
                result.analyzers_run.append("security_auditor")
            except Exception as e:
                logger.warning("security_auditor failed: %s", e)

        # 3. transaction_checker (6 правил) — все уровни
        tx_mod = _load_script("transaction_checker")
        if tx_mod:
            try:
                tx_checker = tx_mod.TransactionChecker()
                tx_violations = tx_checker.check_file(file_path)
                for v in tx_violations:
                    result.violations.append(
                        Violation(
                            source="transaction_checker",
                            rule_id=v.rule_id,
                            severity=v.severity,
                            line=v.line,
                            message=v.message,
                            file=str(file_path),
                        )
                    )
                result.analyzers_run.append("transaction_checker")
            except Exception as e:
                logger.warning("transaction_checker failed: %s", e)

        # 4. query_analyzer (10 правил) — все уровни
        qa_mod = _load_script("query_analyzer")
        if qa_mod:
            try:
                qa_analyzer = qa_mod.QueryAnalyzer()
                qa_issues = qa_analyzer.analyze_file(file_path)
                for i in qa_issues:
                    result.violations.append(
                        Violation(
                            source="query_analyzer",
                            rule_id=i.rule_id,
                            severity=i.severity,
                            line=i.line,
                            message=i.message,
                            file=str(file_path),
                        )
                    )
                result.analyzers_run.append("query_analyzer")
            except Exception as e:
                logger.warning("query_analyzer failed: %s", e)

        # 5. BSL Language Server (187 диагностик) — standard / full
        if level in ("standard", "full"):
            if self._paths.bsl_ls_binary.exists():
                result.bsl_ls_available = True
                try:
                    # Импортируем bsl_analyzer лениво — он требует Java
                    from .bsl_analyzer import BslAnalyzer

                    analyzer = BslAnalyzer(self._paths)
                    bsl_result = analyzer.analyze(file_path)
                    for d in bsl_result.diagnostics:
                        result.violations.append(
                            Violation(
                                source="bsl_ls",
                                rule_id=d.get("code", ""),
                                severity=d.get("severity", "warning"),
                                line=d.get("line", 0),
                                message=d.get("message", ""),
                                file=str(file_path),
                            )
                        )
                    result.analyzers_run.append("bsl_ls")
                except Exception as e:
                    logger.warning("bsl_ls failed: %s", e)
            else:
                result.bsl_ls_available = False

        # 6. code_metrics — только full
        if level == "full":
            cm_mod = _load_script("code_metrics")
            if cm_mod:
                try:
                    analyzer = cm_mod.CodeMetricsAnalyzer()
                    metrics = analyzer.analyze_file(file_path)

                    cm = CodeMetric(
                        loc=getattr(metrics, "loc", 0),
                        lloc=getattr(metrics, "lloc", 0),
                        cyclomatic_complexity=getattr(metrics, "cyclomatic_complexity", 0.0),
                        cognitive_complexity=getattr(metrics, "cognitive_complexity", 0.0),
                        max_nesting=getattr(metrics, "max_nesting", 0),
                        methods_count=len(getattr(metrics, "methods", [])),
                        is_god_object=getattr(metrics, "is_god_object", False),
                        long_methods=[
                            {"name": m.name, "lloc": m.lloc, "line_start": m.line_start}
                            for m in getattr(metrics, "long_methods", [])
                        ],
                        health_score=getattr(metrics, "health_score", 0.0),
                    )
                    result.metrics = cm
                    result.analyzers_run.append("code_metrics")

                    # God Object как violation
                    if cm.is_god_object:
                        result.violations.append(
                            Violation(
                                source="code_metrics",
                                rule_id="GOD_OBJECT",
                                severity="error",
                                line=0,
                                message=f"God Object: {cm.loc} строк, {cm.methods_count} методов",
                                file=str(file_path),
                            )
                        )
                    for m in cm.long_methods:
                        result.violations.append(
                            Violation(
                                source="code_metrics",
                                rule_id="LONG_METHOD",
                                severity="warning",
                                line=m["line_start"],
                                message=f"Длинный метод {m['name']}: {m['lloc']} строк",
                                file=str(file_path),
                            )
                        )
                except Exception as e:
                    logger.warning("code_metrics failed: %s", e)

        # 7. Метаданные (18 правил) — только full
        if level == "full":
            meta_mod = _load_script("check_metadata_standards")
            if meta_mod:
                try:
                    checker2 = meta_mod.MetadataStandardsChecker()
                    meta_violations = checker2.check_path(file_path.parent if file_path.is_file() else file_path)
                    for v in meta_violations:
                        result.violations.append(
                            Violation(
                                source="check_metadata_standards",
                                rule_id=v.rule_id,
                                severity=v.severity,
                                line=v.line,
                                message=v.message,
                                file=v.file,
                            )
                        )
                    result.analyzers_run.append("check_metadata_standards")
                except Exception as e:
                    logger.warning("check_metadata_standards failed: %s", e)

        return result
