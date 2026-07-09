"""
TaskProcessor — единый пайплайн для решения задач 1С.

solve(query, config_name) → TaskContext:
    1. Поиск методов платформы 1С (BM25, если есть индекс)
    2. API-справочник конфигурации (api-reference.json)
    3. Структура объектов (unified-metadata-index.json)
    4. СКД-схемы (skd-index.json)
    5. Формы (form-index.json)
    6. База знаний (knowledge_base/)
    7. Стандарты 1С (check_1c_standards.py — 62 правил)

check(file_path, level) → CheckResult:
    quick:    check_1c_standards + security + transactions + queries (без Java)
    standard: quick + BSL LS
    full:     standard + code_metrics + metadata_standards

Это единая бизнес-логика, которую используют И CLI И MCP-сервер.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

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
        required_sources: list[str] | None = None,
    ) -> TaskContext:
        """Собрать контекст для LLM по задаче.

        F2.6: Source selection by intent — если required_sources указан,
        ищет ТОЛЬКО по релевантным источникам (не по всем 7).

        R15 (2026-07-09): Source mapping — intent classifier использует
        aliases (security_rules, query_standards, bsl_templates, call_graph,
        best_practices, templates), которые маппятся на реальные search методы.

        Args:
            query: Текст задачи
            config_name: Имя конфигурации (для metadata/api/skd/forms)
            limit: Лимит результатов на источник
            required_sources: Список источников для поиска (из intent classifier).
                Поддерживаются как canonical имена, так и aliases:
                - platform_methods (canonical)
                - metadata, api_reference, skd, forms (canonical)
                - knowledge_base, best_practices (alias → knowledge_base)
                - standards, security_rules (alias → standards)
                - query_standards (alias → standards + skd)
                - bsl_templates, templates (alias → knowledge_base)
                - call_graph (note only — not searched in solve())
                Если None — ищет по всем источникам (backward compat).
        """
        ctx = TaskContext(query=query, config_name=config_name)

        # R15: Source mapping — aliases → canonical
        SOURCE_ALIASES: dict[str, str] = {
            "best_practices": "knowledge_base",
            "templates": "knowledge_base",
            "bsl_templates": "knowledge_base",
            "security_rules": "standards",
            "query_standards": "standards",
            # query_standards also implies skd (query-related schemas)
        }
        # query_standards special case: also enable skd
        QUERY_STANDARDS_EXTRA = {"skd"}

        if required_sources:
            # Normalize: aliases → canonical
            normalized = set()
            for src in required_sources:
                canonical = SOURCE_ALIASES.get(src, src)
                normalized.add(canonical)
                if src == "query_standards":
                    normalized.update(QUERY_STANDARDS_EXTRA)
            active_sources = normalized
        else:
            active_sources = None  # all sources

        # F2.6: Если required_sources не указан — все источники (backward compat)
        all_sources = {
            "platform_methods", "metadata", "api_reference", "skd", "forms",
            "knowledge_base", "standards",
        }
        if active_sources is None:
            active_sources = all_sources.copy()

        # B5: автоопределение версии платформы из конфигурации
        if config_name:
            detected_version = self._detect_platform_version(config_name)
            if detected_version:
                ctx.warnings.append(f"platform_version={detected_version} (auto-detected from {config_name})")

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) >= 2]

        # 1. Методы платформы 1С
        if "platform_methods" in active_sources:
            self._search_platform_methods(ctx, query, limit)
        else:
            ctx.missing_sources.append("platform_methods (skipped by intent)")

        # 2-5. Источники по конфигурации
        if config_name:
            if "api_reference" in active_sources:
                self._search_api_reference(ctx, config_name, query_words, limit)
            if "metadata" in active_sources:
                self._search_metadata(ctx, config_name, query_words, limit)
            if "skd" in active_sources:
                self._search_skd(ctx, config_name, query_words, limit)
            if "forms" in active_sources:
                self._search_forms(ctx, config_name, query_words, limit)
        else:
            ctx.warnings.append("Конфигурация не указана — поиск по метаданным пропущен")

        # 6. База знаний (knowledge_base, best_practices, templates, bsl_templates → knowledge_base)
        if "knowledge_base" in active_sources:
            self._search_knowledge_base(ctx, query, limit)

        # 7. Стандарты (standards, security_rules, query_standards → standards)
        if "standards" in active_sources:
            ctx.standards_summary = self._standards_summary()

        # CR-12: call_graph — если в required_sources, добавляем summary в warnings
        if required_sources and "call_graph" in required_sources:
            ctx.warnings.append(
                "call_graph: use run_cli(command='call_graph', args={config_name, action:'stats'}) "
                "or explain(file_path) for full call graph analysis"
            )

        # F2.6: Добавляем info о source selection
        if required_sources:
            skipped = all_sources - active_sources
            if skipped:
                ctx.warnings.append(
                    f"F2.6 source selection: skipped {len(skipped)} source(s) "
                    f"({', '.join(sorted(skipped))}) — not required by intent"
                )

        return ctx

    def _search_platform_methods(self, ctx: TaskContext, query: str, limit: int) -> None:
        """Поиск по методам платформы 1С с авто-проверкой доступности.

        B4 FIX: Использует platform-methods.db (SQLite, методы платформы 1С)
        вместо fast-search-index.json (методы конфигурации УТ11).

        ОПТИМИЗАЦИЯ: Для каждого найденного метода АВТОМАТИЧЕСКИ проверяет
        доступность и добавляет предупреждение. LLM не нужно вызывать
        get_method_details отдельно — информация уже в ответе solve_context.
        """
        # B4 FIX: Сначала пробуем новый SQLite индекс платформы
        try:
            from .platform_methods_index import PlatformMethodsIndex

            index = PlatformMethodsIndex()
            if index.is_available():
                results = index.search(query, limit=limit)
                for r in results:
                    name_ru = r.get("name_ru", "")
                    avail_raw = r.get("availability_raw", "")

                    # Авто-проверка: доступен ли метод на клиенте?
                    avail_warning = ""
                    if avail_raw:
                        avail_lower = avail_raw.lower()
                        # Если в доступности НЕТ "тонкий клиент" и НЕТ "мобильный клиент"
                        # — это серверный метод, предупреждаем
                        is_server_only = (
                            "сервер" in avail_lower
                            and "тонкий клиент" not in avail_lower
                            and "мобильный клиент" not in avail_lower
                        )
                        if is_server_only:
                            avail_warning = (
                                f"⚠️ '{name_ru}' НЕ доступен на клиенте! "
                                f"Доступен только: {avail_raw}. "
                                f"Не используйте в клиентских модулях."
                            )

                    ctx.platform_methods.append(
                        PlatformMethodHit(
                            name_ru=name_ru,
                            name_en=r.get("name_en", ""),
                            score=float(r.get("score", 0.0)),
                            syntax=r.get("syntax", ""),
                            description=r.get("description", ""),
                            context=r.get("category", ""),
                            availability_raw=avail_raw,
                            availability_warning=avail_warning,
                        )
                    )
                return
        except Exception as e:
            ctx.warnings.append(f"platform_methods SQLite search failed: {e}")

        # Fallback на старый BM25 индекс (УТ11 — для обратной совместимости)
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

    def _detect_platform_version(self, config_name: str) -> str | None:
        """B5: Автоопределение версии платформы из Configuration.xml.

        Читает CompatibilityMode из Configuration.xml конфигурации
        и преобразует "Version8_3_20" → "8.3.20".

        Args:
            config_name: Имя конфигурации (например "УправлениеТорговлей")

        Returns:
            Версия платформы (например "8.3.20") или None если не удалось определить.
        """
        try:
            config_path = self._paths.config_path(config_name)
            config_xml = config_path / "Configuration.xml"
            if not config_xml.exists():
                return None

            import xml.etree.ElementTree as ET

            tree = ET.parse(config_xml)
            root = tree.getroot()

            # Ищем <CompatibilityMode>Version8_3_20</CompatibilityMode>
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "CompatibilityMode" and elem.text:
                    # "Version8_3_20" → "8.3.20"
                    version = elem.text.replace("Version", "").replace("_", ".")
                    return version

            return None
        except Exception:
            return None

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
        for ev in meta.get("event_subscriptions", []):
            if any(w in ev.get("name", "").lower() or w in ev.get("handler", "").lower() for w in query_words):
                ctx.event_subscriptions.append(ev)

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

    def _standards_summary(self) -> dict[str, Any]:
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

        def _load_script(script_name: str) -> Any:
            """Этап 1.2, Группа 1: приоритет — прямой импорт из src.services.analyzers.<name>.
            Fallback — dynamic import из scripts/ (для ещё не перенесённых анализаторов)."""
            # Если модуль уже загружен (например, тестом через sys.modules) — не перезагружаем
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
            # Fallback: dynamic import из scripts/
            import importlib.util

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

        # 1. check_1c_standards (62 правил) — все уровни
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
                            recommendation=getattr(v, 'recommendation', ''),
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
                            recommendation=getattr(v, 'recommendation', ''),
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
                            recommendation=getattr(v, 'recommendation', ''),
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
                            recommendation=getattr(i, 'recommendation', ''),
                        )
                    )
                result.analyzers_run.append("query_analyzer")
            except Exception as e:
                logger.warning("query_analyzer failed: %s", e)

        # 4b. data_exchange_checker (10 правил DX001-DX010) — все уровни
        # KB-EXP-2: проверка стандартов обмена данными
        # #std773 (ОбменДанными.Загрузка), #std701 (планы обмена), #std771, #std542
        dx_mod = _load_script("data_exchange_checker")
        if dx_mod:
            try:
                dx_checker = dx_mod.DataExchangeChecker()
                dx_violations = dx_checker.check_file(file_path)
                for v in dx_violations:
                    result.violations.append(
                        Violation(
                            source="data_exchange_checker",
                            rule_id=v.rule_id,
                            severity=v.severity,
                            line=v.line,
                            message=v.message,
                            file=str(file_path),
                            recommendation=getattr(v, 'recommendation', ''),
                        )
                    )
                result.analyzers_run.append("data_exchange_checker")
            except Exception as e:
                logger.warning("data_exchange_checker failed: %s", e)

        # 4c. bsl_context_checker — проверка доступности методов (B6)
        # Проверяет, что методы платформы доступны в целевом контексте
        # (клиент/сервер/мобильное приложение). Использует SQLite индекс.
        if level in ("standard", "full"):
            ctx_mod = _load_script("bsl_context_checker")
            if ctx_mod:
                try:
                    checker = ctx_mod.BslContextChecker(self._paths)
                    ctx_violations = checker.check_file(file_path)
                    for v in ctx_violations:
                        result.violations.append(
                            Violation(
                                source="bsl_context_checker",
                                rule_id=v.rule_id,
                                severity=v.severity,
                                line=v.line,
                                message=v.message,
                                file=str(file_path),
                                recommendation=getattr(v, 'recommendation', ''),
                            )
                        )
                    result.analyzers_run.append("bsl_context_checker")
                except Exception as e:
                    logger.warning("bsl_context_checker failed: %s", e)

        # 5. BSL Language Server (187 диагностик) — standard / full
        if level in ("standard", "full"):
            if self._paths.bsl_ls_binary.exists():
                result.bsl_ls_available = True
                try:
                    # Импортируем bsl_analyzer лениво — он требует Java
                    from .bsl_analyzer import BSLAnalyzer

                    analyzer = BSLAnalyzer(
                        self._paths.bsl_ls_binary,
                        self._paths.bsl_ls_config,
                        self._paths.root,
                    )
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
                                recommendation="См. документацию BSL LS для этой диагностики",
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
                                recommendation="Разделите модуль на несколько модулей по ответственности",
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
                                recommendation="Разделите метод на несколько меньших методов",
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
                                recommendation=getattr(v, 'recommendation', ''),
                            )
                        )
                    result.analyzers_run.append("check_metadata_standards")
                except Exception as e:
                    logger.warning("check_metadata_standards failed: %s", e)

        return result

    # ─────────────────────────────────────────────
    # P2.12: новый OCP-compliant API через Analyzer protocol
    # ─────────────────────────────────────────────

    def check_via_analyzers(
        self,
        file_path: Path,
        level: str = "standard",
    ) -> CheckResult:
        """
        Новый API проверки через Analyzer protocol (P2.12).

        В отличие от check(), использует список self._analyzers и итеративно
        вызывает analyzer.check_file() для каждого. Добавление нового
        analyzer'а не требует модификации этого метода — соответствует OCP.

        Возвращает тот же формат CheckResult, что и check(), поэтому
        результаты полностью совместимы.

        Args:
            file_path: путь к .bsl файлу
            level: quick | standard | full (см. check() для деталей)

        Returns:
            CheckResult с violations и analyzers_run.

        Note:
            BSL LS (standard level) в этой версии НЕ запускается через
            Analyzer protocol — он требует Java и обрабатывается отдельно
            в check(). В будущей миграции будет добавлен BSLAnalyzerAdapter.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        # Lazy import чтобы избежать циклических зависимостей.
        from .analyzers import get_default_analyzers, run_analyzers

        result = CheckResult(file=str(file_path), level=level)

        analyzers = get_default_analyzers(self._paths)
        violations, analyzers_run = run_analyzers(analyzers, file_path, level=level)

        # Преобразуем AnalyzerViolation в Violation (доменный объект).
        for v in violations:
            result.violations.append(
                Violation(
                    source=v.source,
                    rule_id=v.rule_id,
                    severity=v.severity,
                    line=v.line,
                    message=v.message,
                    file=v.file or str(file_path),
                )
            )
        result.analyzers_run.extend(analyzers_run)

        return result
