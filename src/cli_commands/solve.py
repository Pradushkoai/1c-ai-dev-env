"""
solve.py — CLI команды для solve, standards и backup.

P2.1: вынесено из cli.py.
Команды: solve, standards, backup
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.project import Project


def cmd_standards(project: Project, args: argparse.Namespace) -> None:
    """Проверка .bsl файлов на соответствие стандартам разработки 1С."""
    # Этап 1.2, Группа 1f: прямой импорт из src.services.analyzers (dynamic import удалён)
    from src.services.analyzers.check_1c_standards import StandardsChecker, format_violations

    target = Path(args.path)
    if not target.is_absolute():
        target = project.paths.root / target

    checker = StandardsChecker()
    violations = checker.check_path(target)

    # Фильтр по severity
    if args.severity == "error":
        violations = [v for v in violations if v.severity == "error"]

    output = format_violations(violations, args.format)
    print(output)

    has_errors = any(v.severity == "error" for v in violations)
    sys.exit(1 if has_errors else 0)


def cmd_backup(project: Project, args: argparse.Namespace) -> None:
    """Управление backup/restore данных проекта."""

    from src.services.backup_manager import BackupManager

    bm = BackupManager(project.paths)

    if args.backup_command == "create":
        output = Path(args.output) if args.output else Path("download/backup.zip")
        if not output.is_absolute():
            output = project.paths.root / output
        output.parent.mkdir(parents=True, exist_ok=True)

        print(f"Создание backup: {output}")
        result = bm.create_backup(output, include_derived=args.include_derived)
        size_mb = result.stat().st_size / 1024 / 1024
        print(f"✅ Backup создан: {result}")
        print(f"   Размер: {size_mb:.1f} МБ")
        print(f"   Скачать: {result}")

    elif args.backup_command == "restore":
        backup_path = Path(args.path)
        if not backup_path.is_absolute():
            backup_path = project.paths.root / backup_path

        print(f"Восстановление из: {backup_path}")
        stats = bm.restore_backup(backup_path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   Директорий: {', '.join(stats['dirs_restored'])}")
        print(f"   Размер: {stats['size_bytes'] / 1024 / 1024:.1f} МБ")

    elif args.backup_command == "list":
        backup_dir = Path(args.dir) if args.dir else Path("download")
        if not backup_dir.is_absolute():
            backup_dir = project.paths.root / backup_dir

        backups = bm.list_backups(backup_dir)
        if not backups:
            print("Нет доступных backup'ов")
            return

        print(f"{'Имя':<30} {'Размер':<10} {'Файлов':<10} {'Создан'}")
        print("-" * 80)
        for b in backups:
            print(f"{b['name']:<30} {b['size_mb']:>6.1f} МБ {b['files']:>8}    {b['created_at'][:19]}")


def cmd_solve(project: Project, args: argparse.Namespace) -> None:
    """
    Автоматический цикл решения задачи с проверками.

    Две подкоманды:
    - context: собирает контекст для LLM (методы + API + стандарты)
    - check: проверяет сгенерированный .bsl код (BSL LS + 22 правила)
    """

    if args.solve_command == "context":
        _solve_context(project, args)
    elif args.solve_command == "check":
        _solve_check(project, args)


def _solve_context(project: Project, args: argparse.Namespace) -> None:
    """Собирает полный контекст для LLM через TaskProcessor."""
    from src.services.task_processor import TaskProcessor

    query = args.query
    config_name = getattr(args, "config", None) or ""
    limit = getattr(args, "limit", 5)

    processor = TaskProcessor(project.paths)
    ctx = processor.solve(query, config_name=config_name, limit=limit)

    print("╔══════════════════════════════════════════════════════╗")
    print("║  1c-ai solve: сбор контекста для задачи              ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"\nЗадача: {query}")
    if config_name:
        print(f"Конфигурация: {config_name}")
    print(f"Всего находок: {ctx.total_hits}")
    print()

    # 1. Методы платформы
    print("=== 1. Методы платформы 1С ===")
    if ctx.platform_methods:
        for i, r in enumerate(ctx.platform_methods, 1):
            print(f"  {i}. [{r.score:.3f}] {r.name_ru} ({r.name_en})")
            print(f"     Синтаксис: {r.syntax}")
            if r.description:
                print(f"     Описание: {r.description[:100]}")
        print()
    else:
        if "platform_methods" in " ".join(ctx.missing_sources):
            print("  ⚠️  Индекс платформы не найден (не критично).\n")
        else:
            print("  Ничего не найдено.\n")

    # 2. API-справочник
    if config_name:
        print(f"=== 2. API конфигурации '{config_name}' ===")
        if ctx.api_modules:
            print(f"  Найдено {len(ctx.api_modules)} релевантных модулей:")
            for m in ctx.api_modules:
                print(f"  • {m.name}: {m.methods_count} методов")
                for method in m.methods[:3]:
                    params = method.get("params", [])
                    print(f"    - {method['name']}({', '.join(p['name'] for p in params)})")
            print()
        else:
            if any("api_reference" in m for m in ctx.missing_sources):
                print("  ⚠️  API-справочник не найден.\n")
            else:
                print("  Релевантных модулей не найдено.\n")

        # 3. Структура объектов
        print(f"=== 3. Структура объектов '{config_name}' ===")
        if ctx.metadata_objects:
            print(f"  Найдено {len(ctx.metadata_objects)} объектов:")
            for o in ctx.metadata_objects:
                print(f"  • {o.type}: {o.name} — {o.synonym}")
                print(f"    Реквизитов: {o.attributes_count}, ТЧ: {o.tabular_sections_count}, Форм: {o.forms_count}")
            print()
        else:
            if any("metadata" in m for m in ctx.missing_sources):
                print("  ⚠️  unified-metadata-index не найден.\n")
            else:
                print("  Объекты не найдены.\n")

        if ctx.subsystems:
            print(f"  Подсистемы ({len(ctx.subsystems)} найдено):")
            for s in ctx.subsystems[:3]:
                print(f"  • {s.get('name', '')}: content={len(s.get('content', []))} объектов")
            print()

        if ctx.event_subscriptions:
            print(f"  Подписки на события ({len(ctx.event_subscriptions)} найдено):")
            for e in ctx.event_subscriptions[:3]:
                print(f"  • {e.get('name', '')}: event={e.get('event', '')}, handler={e.get('handler', '')}")
            print()

        if ctx.scheduled_jobs:
            print(f"  Регламентные задания ({len(ctx.scheduled_jobs)} найдено):")
            for s in ctx.scheduled_jobs[:3]:
                print(f"  • {s.get('name', '')}: method={s.get('method_name', '')}")
            print()

        # 4. СКД-схемы
        print(f"=== 4. СКД-схемы '{config_name}' ===")
        if ctx.skd_schemas:
            print(f"  Найдено {len(ctx.skd_schemas)} СКД-схем:")
            for schema in ctx.skd_schemas:
                print(f"  • {schema.parent_type}: {schema.parent_name}: {schema.name}")
                print(f"    Наборов данных: {schema.data_sets_count}, Параметров: {schema.parameters_count}")
            print()
        else:
            if any("skd" in m for m in ctx.missing_sources):
                print("  ⚠️  skd-index не найден.\n")
            else:
                print("  СКД не найдены.\n")

        # 5. Формы
        print(f"=== 5. Формы '{config_name}' ===")
        if ctx.forms:
            print(f"  Найдено {len(ctx.forms)} форм:")
            for f in ctx.forms:
                print(f"  • {f.parent_type}: {f.parent_name}.{f.name}")
                print(f"    Элементов: {f.element_count}")
            print()
        else:
            if any("forms" in m for m in ctx.missing_sources):
                print("  ⚠️  form-index не найден.\n")
            else:
                print("  Формы не найдены.\n")
    else:
        print("=== 2-5. Конфигурация ===")
        print("  ⚠️  Конфигурация не указана (--config). Пропускаем.\n")

    # 6. База знаний
    print("=== 6. База знаний 1С ===")
    if ctx.knowledge_articles:
        print(f"  Найдено {len(ctx.knowledge_articles)} статей:")
        for article in ctx.knowledge_articles:
            print(f"  • [{article.category}] {article.title} (score={article.score})")
        print()
    else:
        print("  Статьи не найдены.\n")

    # 7. Стандарты
    print("=== 7. Стандарты 1С ===")
    ss = ctx.standards_summary
    print(f"  Всего проверок: {ss.get('total_checks', 0)}")
    print(f"  • BSL LS: {ss.get('bsl_ls_diagnostics', 0)} диагностик")
    print(f"  • check_1c_standards: {ss.get('check_1c_standards_rules', 0)} правил")
    print(f"  • security_auditor: {ss.get('security_rules', 0)} правил")
    print(f"  • transaction_checker: {ss.get('transaction_rules', 0)} правил")
    print(f"  • query_analyzer: {ss.get('query_rules', 0)} правил")
    print(f"  • code_metrics: {ss.get('code_metrics_count', 0)} метрик")
    print(f"  • metadata_standards: {ss.get('check_metadata_rules', 0)} правил")
    print()

    # 8. После генерации
    print("=== 8. После генерации кода — выполните проверки ===")
    print(f"  {ss.get('check_command', '1c-ai solve check <file.bsl> --level full')}")
    print()
    print("─" * 60)
    print("Контекст собран. LLM может генерировать код,")
    print("опираясь на методы, структуру, СКД, формы и стандарты выше.")


def _solve_check(project: Project, args: argparse.Namespace) -> None:
    """
    Полная проверка .bsl кода через TaskProcessor.

    Уровни проверки (--level):
    - quick:    check_1c_standards + security + transactions + queries (без Java)
    - standard: quick + BSL LS
    - full:     standard + metadata_standards + code_metrics

    CI-режим (--ci): только errors, exit code 1 при errors
    JSON-режим (--json): полный JSON-отчёт
    """
    import json as json_mod

    from src.services.task_processor import TaskProcessor

    level = getattr(args, "level", "standard")
    ci_mode = getattr(args, "ci", False)
    json_mode = getattr(args, "json", False)

    bsl_path = Path(args.path)
    if not bsl_path.is_absolute():
        bsl_path = project.paths.root / bsl_path

    if not bsl_path.exists():
        if json_mode:
            print(json_mod.dumps({"error": f"Файл не найден: {bsl_path}"}, ensure_ascii=False))
        else:
            print(f"❌ Файл не найден: {bsl_path}")
        sys.exit(2)

    processor = TaskProcessor(project.paths)
    result = processor.check(bsl_path, level=level)

    # SARIF-режим (приоритет над другими форматами)
    sarif_path = getattr(args, "sarif", None)
    if sarif_path:
        from src.services.sarif_reporter import SarifReporter

        sarif_out = Path(sarif_path)
        if not sarif_out.is_absolute():
            sarif_out = project.paths.root / sarif_out
        SarifReporter().write(result, sarif_out)
        print(f"✅ SARIF: {sarif_out} ({result.total_errors} errors, {result.total_warnings} warnings)")
        # Также краткий вывод в stdout
        print(f"   Verdict: {result.verdict}")
        sys.exit(1 if result.total_errors > 0 else 0)

    # JSON-режим
    if json_mode:
        report = result.to_dict()
        if ci_mode:
            report["violations"] = [v for v in report["violations"] if v["severity"] in ("error", "critical", "high")]
        print(json_mod.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1 if result.total_errors > 0 else 0)

    # CI-режим
    if ci_mode:
        errors_only = [v for v in result.violations if v.severity in ("error", "critical", "high")]
        if errors_only:
            print(f"❌ {result.total_errors} errors found:")
            for v in errors_only[:20]:
                print(f"  {v.source:25} {v.rule_id:25} line {v.line:4}  {v.message[:80]}")
            if len(errors_only) > 20:
                print(f"  ... и ещё {len(errors_only) - 20}")
        else:
            print(f"✅ No errors ({result.total_warnings} warnings)")
        sys.exit(1 if result.total_errors > 0 else 0)

    # Человекочитаемый вывод
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: проверка кода [level={level}]            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"\nФайл: {bsl_path}")
    print(f"Уровень: {level}")
    print(f"Анализаторы ({len(result.analyzers_run)}): {' + '.join(result.analyzers_run)}")
    if result.bsl_ls_available is False and level in ("standard", "full"):
        print("⚠️  BSL LS не установлен — диагностики Java пропущены")
    print()

    by_source: dict[str, list] = {}
    for v in result.violations:
        by_source.setdefault(v.source, []).append(v)

    for source, violations in by_source.items():
        errors = [v for v in violations if v.severity in ("error", "critical", "high")]
        warnings = [v for v in violations if v.severity not in ("error", "critical", "high")]
        print(f"=== {source} ({len(errors)} errors, {len(warnings)} warnings) ===")
        for v in violations[:15]:
            print(f"  {v.severity.upper():8} {v.rule_id:25} line {v.line:4}  {v.message[:80]}")
        if len(violations) > 15:
            print(f"  ... и ещё {len(violations) - 15}")
        print()

    # Метрики (если full)
    if result.metrics:
        m = result.metrics
        print("=== code_metrics ===")
        print(f"  LOC: {m.loc}, LLOC: {m.lloc}")
        print(f"  Cyclomatic: {m.cyclomatic_complexity:.1f}, Cognitive: {m.cognitive_complexity:.1f}")
        print(f"  Max nesting: {m.max_nesting}, Methods: {m.methods_count}")
        print(f"  Health score: {m.health_score:.1f}/100")
        if m.is_god_object:
            print("  ❌ God Object detected!")
        if m.long_methods:
            print(f"  Long methods ({len(m.long_methods)}):")
            for lm in m.long_methods[:5]:
                print(f"    • {lm['name']} ({lm['lloc']} строк, line {lm['line_start']})")
        print()

    print("─" * 60)
    print(f"ИТОГО: {result.total_errors} errors, {result.total_warnings} warnings")
    print()
    verdict = result.verdict
    if verdict == "ready":
        print("✅ Код прошёл все проверки! Готов к коммиту.")
    elif verdict == "warnings":
        print("⚠️  Нет критичных ошибок, но есть warnings.")
    else:
        print("❌ Есть критичные ошибки. Код НЕ готов к коммиту.")

    sys.exit(1 if result.total_errors > 0 else 0)
