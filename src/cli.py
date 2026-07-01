"""
Единый CLI для всех команд проекта.

Usage:
    1c-ai config list
    1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"
    1c-ai config build --name ut11
    1c-ai config build-all
    1c-ai bsl analyze <path>
    1c-ai bsl baseline <path>
    1c-ai bsl diff <path>
    1c-ai validate
    1c-ai search "найти по коду"
    1c-ai standards <path>            # проверка .bsl на стандарты 1С
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import Project


def cmd_config_list(project: Project, args: argparse.Namespace) -> None:
    configs = project.list_configs()
    if not configs:
        print("Нет конфигураций.")
        return
    print(f"{'Имя':<15} {'Версия':<15} {'Статус':<10} {'Объектов':<10} {'Путь'}")
    print("-" * 80)
    for c in configs:
        path = str(c.path) if c.path else (str(c.archive) if c.archive else "—")
        print(f"{c.name:<15} {c.version:<15} {c.status:<10} {c.objects_count:<10} {path}")


def _print_build_report(report: dict) -> None:
    """Унифицированный вывод отчёта build()."""
    name = report.get('name', '?')
    skipped = report.get('skipped', [])
    if skipped == ['all']:
        print(f"✅ {name}: все индексы уже свежие (skip)")
        return
    parts = []
    for key in ('metadata', 'api', 'skd', 'forms'):
        val = report.get(key)
        if val is True:
            tag = '✅'
            if key in skipped:
                tag = '⏭️'
        else:
            tag = '❌'
        parts.append(f"{key}={tag}")
    print(f"✅ {name}: {' '.join(parts)}")
    if skipped and skipped != ['all']:
        print(f"   ⏭️ Пропущено (уже свежие): {', '.join(skipped)}")


def cmd_config_add(project: Project, args: argparse.Namespace) -> None:
    """Добавить конфигурацию из ZIP или .cf файла."""
    if args.cf:
        config = project.config_manager.add_from_cf(args.name, Path(args.cf), args.title)
    else:
        config = project.config_manager.add_from_zip(args.name, Path(args.zip), args.title)
    print(f"✅ Добавлена: {config.name} v{config.version} ({config.objects_count} объектов)")
    if not args.skip_build:
        print("Индексация...")
        report = project.config_manager.build(args.name, force=True)
        _print_build_report(report)


def cmd_config_build(project: Project, args: argparse.Namespace) -> None:
    if getattr(args, 'check_freshness', False):
        report = project.config_manager.check_freshness(args.name)
        print(f"Конфигурация: {report.config_name}")
        print(f"Все индексы свежие: {'✅ да' if report.all_fresh else '❌ нет'}")
        if report.source_mtime:
            import time as _t
            print(f"Исходники изменены: {_t.ctime(report.source_mtime)}")
        if report.missing_indexes:
            print(f"Отсутствуют: {', '.join(report.missing_indexes)}")
        if report.stale_indexes:
            print(f"Устарели: {', '.join(report.stale_indexes)}")
        for idx in report.indexes:
            mark = '✅' if (idx.exists and not idx.is_stale) else '❌'
            print(f"  {mark} {idx.name}: exists={idx.exists}, stale={idx.is_stale}")
            if idx.stale_reason:
                print(f"      {idx.stale_reason}")
        return
    if getattr(args, 'validate', False):
        result = project.config_manager.validate_sources(args.name)
        print(f"Конфигурация: {args.name}")
        print(f"Валидна: {'✅ да' if result.is_valid else '❌ нет'}")
        print(f"  Configuration.xml: {'✅' if result.has_configuration_xml else '❌'}")
        print(f"  Метаданные-директории: {'✅' if result.has_metadata_dirs else '❌'}")
        print(f"  .bsl файлы: {'✅' if result.has_bsl_files else '—'}")
        if result.found_type_dirs:
            print(f"  Найденные типы: {', '.join(result.found_type_dirs)}")
        if result.errors:
            print("  Ошибки:")
            for e in result.errors:
                print(f"    ❌ {e}")
        if result.warnings:
            print("  Предупреждения:")
            for w in result.warnings:
                print(f"    ⚠️ {w}")
        return
    force = getattr(args, 'force', False)
    report = project.config_manager.build(args.name, force=force)
    _print_build_report(report)


def cmd_config_build_all(project: Project, args: argparse.Namespace) -> None:
    force = getattr(args, 'force', False)
    results = project.config_manager.build_all(force=force)
    for r in results:
        _print_build_report(r)


def cmd_bsl_analyze(project: Project, args: argparse.Namespace) -> None:
    try:
        result = project.bsl_analyzer.analyze(Path(args.path))
        print(f"Всего: {result.total}")
        for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:15]:
            print(f"  {count:4d}  {code}")
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
        print("   Установите: bash install.sh")
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")


def cmd_bsl_baseline(project: Project, args: argparse.Namespace) -> None:
    try:
        result = project.bsl_analyzer.save_baseline(Path(args.path))
        print(f"✅ Baseline: {result.total} диагностик")
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def cmd_bsl_diff(project: Project, args: argparse.Namespace) -> None:
    try:
        diff = project.bsl_analyzer.diff(Path(args.path))
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
        return
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    print(f"\n🆕 НОВЫЕ ({len(diff.new)}):")
    for d in diff.new[:20]:
        print(f"  + {d['code']} (строка {d['line']}): {d['message']}")
    print(f"\n✅ ИСПРАВЛЕННЫЕ ({len(diff.fixed)}):")
    for d in diff.fixed[:10]:
        print(f"  - {d['key']}")


def cmd_validate(project: Project, args: argparse.Namespace) -> None:
    checks = project.validate()
    all_ok = True
    for name, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {name}")
        if not ok:
            all_ok = False
    sys.exit(0 if all_ok else 1)


def cmd_search(project: Project, args: argparse.Namespace) -> None:
    """Семантический поиск по методам 1С (BM25/TF-IDF авто)."""
    from .services.search_bm25 import detect_index_version, search_auto

    index_path = project.paths.fast_search_index
    if not index_path.exists():
        print("❌ Индекс не найден. Запустите: python3 scripts/fast_search_1c.py build")
        sys.exit(1)

    version = detect_index_version(index_path)
    algo_name = 'BM25+триграммы (v2)' if version == 2 else 'TF-IDF (v1, legacy)'

    results = search_auto(index_path, args.query, args.limit)

    print(f'Поиск: "{args.query}"')
    print(f'Алгоритм: {algo_name}')
    print(f'Найдено: {len(results)} результатов')
    print()
    for rank, r in enumerate(results, 1):
        print(f'{rank}. [{r["score"]:.3f}] {r["name_ru"]} ({r["name_en"]})')
        print(f'   Контекст: {r["context"]}')
        print(f'   Синтаксис: {r["syntax"]}')
        if r['description']:
            print(f'   Описание: {r["description"]}')
        print()


def cmd_search_code(project: Project, args: argparse.Namespace) -> None:
    """Поиск по коду конфигурации (BM25 по 115 666 методов)."""
    from .services.search_code import search_code

    config_name = args.config
    if not config_name:
        print("❌ Укажите конфигурацию: 1c-ai search-code 'запрос' --config ut11")
        sys.exit(1)

    # Проверяем, что конфигурация существует
    configs = {c.name for c in project.list_configs()}
    if config_name not in configs:
        print(f"❌ Конфигурация '{config_name}' не найдена. Доступные: {', '.join(configs)}")
        sys.exit(1)

    results = search_code(config_name, args.query, args.limit, project.paths)

    print(f'Поиск по коду: "{args.query}"')
    print(f'Конфигурация: {config_name}')
    print(f'Найдено: {len(results)} результатов')
    print()
    for rank, r in enumerate(results, 1):
        print(f'{rank}. [{r["score"]:.3f}] {r["module"]}.{r["name"]}')
        print(f'   Тип: {r["type"]}')
        if r['signature']:
            print(f'   Сигнатура: {r["signature"]}')
        if r['description']:
            print(f'   Описание: {r["description"][:120]}')
        print()


def cmd_call_graph(project: Project, args: argparse.Namespace) -> None:
    """Граф вызовов методов конфигурации."""
    import json as json_mod

    from .services.call_graph import build_call_graph

    config_name = args.config
    configs = {c.name for c in project.list_configs()}
    if config_name not in configs:
        print(f"❌ Конфигурация '{config_name}' не найдена. Доступные: {', '.join(configs)}")
        sys.exit(1)

    graph = build_call_graph(config_name, project.paths)

    if args.action == 'stats':
        stats = graph.get_stats()
        print(f"Граф вызовов: {config_name}")
        print(f"  Рёбер (вызовов): {stats['total_edges']}")
        print(f"  Узлов (методов): {stats['total_nodes']}")
        print(f"  Уникальных вызывающих: {stats['unique_callers']}")
        print(f"  Уникальных вызываемых: {stats['unique_callees']}")

    elif args.action == 'callers':
        module = args.module
        method = args.method
        callers = graph.get_callers(module, method)
        if callers:
            print(f"Кто вызывает {module}.{method}():")
            for c in callers:
                print(f"  {c['module']}.{c['method']}()  [{c['file']}:{c['line']}]")
        else:
            print(f"Никто не вызывает {module}.{method}()")

    elif args.action == 'callees':
        module = args.module
        method = args.method
        callees = graph.get_callees(module, method)
        if callees:
            print(f"Кого вызывает {module}.{method}():")
            for c in callees:
                print(f"  → {c['module']}.{c['method']}()  [{c['file']}:{c['line']}]")
        else:
            print(f"{module}.{method}() никого не вызывает")

    elif args.action == 'dead-code':
        # Загружаем export methods из api-reference
        api_json = project.paths.config_api_reference_json(config_name)
        export_methods = []
        if api_json.exists():
            with open(api_json, encoding='utf-8') as f:
                modules = json_mod.load(f)
            for m in modules:
                for method in m.get('methods', []):
                    export_methods.append((m['name'], method['name']))
        dead = graph.find_dead_code(export_methods)
        if dead:
            print(f"Мёртвый код ({len(dead)} из {len(export_methods)} экспортных методов):")
            for mod, meth in dead:
                print(f"  {mod}.{meth}()")
        else:
            print("Мёртвый код не найден — все экспортные методы вызываются")

    elif args.action == 'cycles':
        cycles = graph.find_cycles()
        if cycles:
            print(f"Циклические зависимости ({len(cycles)}):")
            for c in cycles:
                print(f"  {' → '.join(c)}")
        else:
            print("Циклов не найдено")

    elif args.action == 'json':
        print(json_mod.dumps(graph.to_dict(), ensure_ascii=False, indent=2))


def cmd_standards(project: Project, args: argparse.Namespace) -> None:
    """Проверка .bsl файлов на соответствие стандартам разработки 1С."""
    import importlib.util
    from pathlib import Path

    # Загружаем скрипт как модуль
    script_path = project.paths.scripts_dir / "check_1c_standards.py"
    if not script_path.exists():
        script_path = project.paths.root / "setup" / "scripts" / "check_1c_standards.py"
    if not script_path.exists():
        print("❌ Скрипт check_1c_standards.py не найден")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("check_1c_standards", script_path)
    mod = importlib.util.module_from_spec(spec)
    # Регистрируем в sys.modules — нужно для @dataclass
    sys.modules["check_1c_standards"] = mod
    spec.loader.exec_module(mod)

    target = Path(args.path)
    if not target.is_absolute():
        target = project.paths.root / target

    checker = mod.StandardsChecker()
    violations = checker.check_path(target)

    # Фильтр по severity
    if args.severity == "error":
        violations = [v for v in violations if v.severity == "error"]

    output = mod.format_violations(violations, args.format)
    print(output)

    has_errors = any(v.severity == "error" for v in violations)
    sys.exit(1 if has_errors else 0)


def cmd_backup(project: Project, args: argparse.Namespace) -> None:
    """Управление backup/restore данных проекта."""
    from pathlib import Path

    from .services.backup_manager import BackupManager

    bm = BackupManager(project.paths)

    if args.backup_command == 'create':
        output = Path(args.output) if args.output else Path('download/backup.zip')
        if not output.is_absolute():
            output = project.paths.root / output
        output.parent.mkdir(parents=True, exist_ok=True)

        print(f"Создание backup: {output}")
        result = bm.create_backup(output, include_derived=args.include_derived)
        size_mb = result.stat().st_size / 1024 / 1024
        print(f"✅ Backup создан: {result}")
        print(f"   Размер: {size_mb:.1f} МБ")
        print(f"   Скачать: {result}")

    elif args.backup_command == 'restore':
        backup_path = Path(args.path)
        if not backup_path.is_absolute():
            backup_path = project.paths.root / backup_path

        print(f"Восстановление из: {backup_path}")
        stats = bm.restore_backup(backup_path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   Директорий: {', '.join(stats['dirs_restored'])}")
        print(f"   Размер: {stats['size_bytes'] / 1024 / 1024:.1f} МБ")

    elif args.backup_command == 'list':
        backup_dir = Path(args.dir) if args.dir else Path('download')
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

    if args.solve_command == 'context':
        _solve_context(project, args)
    elif args.solve_command == 'check':
        _solve_check(project, args)


def _solve_context(project: Project, args: argparse.Namespace) -> None:
    """Собирает полный контекст для LLM через TaskProcessor."""
    from .services.task_processor import TaskProcessor

    query = args.query
    config_name = getattr(args, 'config', None) or ""
    limit = getattr(args, 'limit', 5)

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
                    params = method.get('params', [])
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
            for s in ctx.skd_schemas:
                print(f"  • {s.parent_type}: {s.parent_name}: {s.name}")
                print(f"    Наборов данных: {s.data_sets_count}, Параметров: {s.parameters_count}")
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
        for r in ctx.knowledge_articles:
            print(f"  • [{r.category}] {r.title} (score={r.score})")
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
    from pathlib import Path

    from .services.task_processor import TaskProcessor

    level = getattr(args, 'level', 'standard')
    ci_mode = getattr(args, 'ci', False)
    json_mode = getattr(args, 'json', False)

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
    sarif_path = getattr(args, 'sarif', None)
    if sarif_path:
        from .services.sarif_reporter import SarifReporter
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
            report["violations"] = [
                v for v in report["violations"]
                if v["severity"] in ("error", "critical", "high")
            ]
        print(json_mod.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1 if result.total_errors > 0 else 0)

    # CI-режим
    if ci_mode:
        errors_only = [
            v for v in result.violations
            if v.severity in ("error", "critical", "high")
        ]
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
    if result.bsl_ls_available is False and level in ('standard', 'full'):
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


def cmd_mcp(project: Project, args: argparse.Namespace) -> None:
    """Управление MCP-сервером."""
    if args.mcp_command == 'serve':
        try:
            import asyncio

            from .mcp_server import run_mcp_server
            asyncio.run(run_mcp_server())
        except ImportError as e:
            print(f"❌ MCP SDK не установлен: {e}")
            print("   Установите: pip install mcp")
            sys.exit(1)
    elif args.mcp_command == 'tools':
        # Выводим список tools — парсим из mcp_server.py
        import re
        mcp_src = Path(__file__).parent / "mcp_server.py"
        src = mcp_src.read_text(encoding="utf-8")
        # Извлекаем все name="..." из types.Tool( блоков
        tools = re.findall(r'name="([a-z_0-9]+)"', src)
        # Убираем дубликаты сохраняя порядок
        seen = set()
        unique_tools = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                unique_tools.append(t)
        print(f"MCP tools ({len(unique_tools)}):")
        print()
        for t in unique_tools:
            print(f"  • {t}")


def cmd_data(project: Project, args: argparse.Namespace) -> None:
    """Управление данными проекта (persistence)."""
    from .services.data_package import DataPackage

    dp = DataPackage(project.paths)

    if args.data_command == 'save-pkg':
        output = Path(args.output) if args.output else dp.default_package_path
        if not output.is_absolute():
            output = project.paths.root / output

        print(f"Сохранение данных в: {output}")
        print(f"  Включая raw (data/): {'да' if args.include_raw else 'нет'}")
        print("  Включая derived: да")
        print()

        result = dp.save(
            output,
            include_raw=args.include_raw,
            include_derived=True,
            description=args.description or "",
        )

        size_mb = result.stat().st_size / 1024 / 1024
        info = dp.info(result)
        manifest = info.get("manifest", {})

        print(f"✅ Пакет создан: {result}")
        print(f"   Размер: {size_mb:.1f} МБ")
        print(f"   Файлов: {info['total_files']}")
        if manifest:
            print(f"   Конфигураций: {len(manifest.get('configs', []))}")
            print(f"   Создан: {manifest.get('created_at', '?')[:19]}")

    elif args.data_command == 'load-pkg':
        path = Path(args.path)
        if not path.is_absolute():
            path = project.paths.root / path

        if not path.exists():
            print(f"❌ Пакет не найден: {path}")
            sys.exit(1)

        print(f"Восстановление из: {path}")
        print()

        # Сначала покажем что внутри
        info = dp.info(path)
        manifest = info.get("manifest")
        if manifest:
            print(f"Пакет создан: {manifest.get('created_at', '?')[:19]}")
            print(f"Конфигураций: {len(manifest.get('configs', []))}")
            for c in manifest.get("configs", []):
                print(f"  • {c['name']} v{c['version']} — {c['objects_count']} объектов")
            print()

        # Распаковка
        stats = dp.load(path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   Из них derived: {stats['derived_restored']}")
        print(f"   Из них data (raw): {stats['raw_restored']}")
        print(f"   config-registry.json: {'✅' if stats['configs_loaded'] else '—'}")
        print()
        print("Теперь данные доступны для:")
        print("  • 1c-ai search '<запрос>'        — поиск по методам платформы")
        print("  • 1c-ai config list              — список конфигураций")
        print("  • 1c-ai mcp serve                — MCP-сервер для IDE")

    elif args.data_command == 'info':
        path = Path(args.path) if args.path else dp.default_package_path
        if not path.is_absolute():
            path = project.paths.root / path

        if not path.exists():
            print(f"❌ Пакет не найден: {path}")
            sys.exit(1)

        info = dp.info(path)
        print(f"Пакет: {path}")
        print(f"Размер: {info['size_mb']:.1f} МБ")
        print(f"Файлов: {info['total_files']}")
        if info["manifest"]:
            m = info["manifest"]
            print()
            print("Манифест:")
            print(f"  Версия: {m.get('version', '?')}")
            print(f"  Создан: {m.get('created_at', '?')[:19]}")
            print(f"  Включая raw: {m.get('include_raw', False)}")
            print(f"  Конфигураций: {len(m.get('configs', []))}")
            for c in m.get("configs", []):
                print(f"    • {c['name']} v{c['version']} — {c.get('objects_count', 0)} объектов")
            if m.get("description"):
                print(f"  Описание: {m['description']}")
        print()
        print(f"Первые {len(info['file_list_sample'])} файлов:")
        for f in info["file_list_sample"][:20]:
            print(f"  {f}")
        if info["total_files"] > 20:
            print(f"  ... и ещё {info['total_files'] - 20}")

    elif args.data_command == 'autosave':
        print(f"Автосохранение в: {dp.default_package_path}")
        result = dp.autosave(
            include_raw=args.include_raw,
            description=args.description or "Autosave",
        )
        size_mb = result.stat().st_size / 1024 / 1024
        info = dp.info(result)
        print(f"✅ Сохранено: {result}")
        print(f"   Размер: {size_mb:.1f} МБ, файлов: {info['total_files']}")

    elif args.data_command == 'autoload':
        if not dp.has_autosave():
            print(f"❌ Автосохранение не найдено: {dp.default_package_path}")
            print("   Сначала выполните: 1c-ai data autosave")
            sys.exit(1)

        print(f"Восстановление из: {dp.default_package_path}")
        stats = dp.load(dp.default_package_path)
        print(f"✅ Восстановлено файлов: {stats['files_restored']}")
        print(f"   derived: {stats['derived_restored']}")
        print(f"   data (raw): {stats['raw_restored']}")

    elif args.data_command == 'status':
        status = dp.status()
        print("Статус данных проекта:")
        print()
        print("Платформа 1С:")
        print(f"  Индекс поиска:      {'✅' if status['has_platform_index'] else '❌'}")
        print(f"  Методы (syntax-helper): {'✅' if status['has_platform_methods'] else '❌'}")
        print()
        print(f"Конфигурации ({len(status['configs'])}):")
        if not status["configs"]:
            print("  (нет)")
        else:
            print(f"  {'Имя':<15} {'Версия':<15} {'Статус':<10} {'API':<5} {'Индекс':<7} {'Raw':<5}")
            print("  " + "-" * 60)
            for c in status["configs"]:
                api = '✅' if c["has_api"] else '❌'
                der = '✅' if c["has_derived"] else '❌'
                raw = '✅' if c["has_raw"] else '—'
                print(f"  {c['name']:<15} {c['version']:<15} {c['status']:<10} {api:<5} {der:<7} {raw:<5}")
        print()
        print(f"Автосохранение: {'✅ доступно' if status['autosave_available'] else '❌ нет'}")
        if status["autosave_available"]:
            ai = status["autosave_info"]
            print(f"  Размер: {ai['size_mb']:.1f} МБ")
            print(f"  Файлов: {ai['total_files']}")
            if ai["manifest"]:
                print(f"  Создан: {ai['manifest'].get('created_at', '?')[:19]}")
                print("  Восстановить: 1c-ai data autoload")

    elif args.data_command == 'release-push':
        # Загрузить в GitHub Releases
        from .services.github_releases import GitHubReleases
        gh = GitHubReleases(project.paths)
        if not gh.is_configured():
            print("❌ GitHub Releases не настроен")
            print("   Установите GITHUB_TOKEN в окружении:")
            print("   export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>")
            sys.exit(1)

        if not dp.has_autosave():
            print("❌ Автосохранение не найдено. Сначала:")
            print("   1c-ai data autosave --include-raw")
            sys.exit(1)

        print("Загрузка в GitHub Releases...")
        print(f"   Repo: {gh._repo}")
        print(f"   Пакет: {dp.default_package_path}")
        print()
        result = gh.push(body=args.body or "Autosave data package")
        if result.get("success"):
            print(f"✅ Загружено в release '{result['tag']}'")
            print(f"   Размер: {result['size_mb']:.1f} МБ")
            print(f"   Release: {result['release_url']}")
            print(f"   Asset: {result['asset_url']}")
            print()
            print("В новой сессии восстановите:")
            print("   1c-ai data release-pull")
            print("   1c-ai data autoload")
        else:
            print(f"❌ Ошибка: {result.get('error', 'неизвестная')}")
            sys.exit(1)

    elif args.data_command == 'release-pull':
        # Скачать из GitHub Releases
        from .services.github_releases import GitHubReleases
        gh = GitHubReleases(project.paths)
        if not gh.is_configured():
            print("❌ GitHub Releases не настроен")
            print("   Установите GITHUB_TOKEN: export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>")
            sys.exit(1)

        print("Скачивание из GitHub Releases...")
        print(f"   Repo: {gh._repo}")
        print(f"   Target: {dp.default_package_path}")
        print()
        result = gh.pull()
        if result.get("success"):
            print(f"✅ Скачано в: {result['path']}")
            print(f"   Размер: {result['size_mb']:.1f} МБ")
            print(f"   Release tag: {result['tag']}")
            print()
            print("Восстановите данные:")
            print("   1c-ai data autoload")
        else:
            print(f"❌ Ошибка: {result.get('error', 'неизвестная')}")
            sys.exit(1)

    elif args.data_command == 'release-status':
        # Статус GitHub Releases
        from .services.github_releases import GitHubReleases
        gh = GitHubReleases(project.paths)
        status = gh.status()
        print("GitHub Releases статус:")
        print(f"  Настроен: {'✅' if status['configured'] else '❌'}")
        print(f"  Repo: {status['repo'] or '(не определён)'}")
        print(f"  Token: {'✅' if status['token_set'] else '❌'}")
        if status["configured"]:
            print(f"  Release существует: {'✅' if status['release_exists'] else '❌'}")
            if status["release_exists"]:
                print(f"  Tag: {status['release_tag']}")
                print(f"  Создан: {status['release_created_at']}")
                print(f"  Размер asset: {status['asset_size_mb']:.1f} МБ")
                print(f"  Имя asset: {status['asset_name']}")
                print(f"  URL: {status['release_url']}")
                print()
                print("Восстановить:")
                print("   1c-ai data release-pull")
                print("   1c-ai data autoload")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="src.cli",
        description="1C AI Development Environment CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # config
    p_cfg = sub.add_parser("config", help="Управление конфигурациями")
    cfg_sub = p_cfg.add_subparsers(dest="config_command", required=True)

    cfg_sub.add_parser("list", help="Список")

    p_add = cfg_sub.add_parser("add", help="Добавить из ZIP")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--zip", help="ZIP выгрузка конфигурации")
    p_add.add_argument("--cf", help=".cf/.cfe/.epf файл конфигурации")
    p_add.add_argument("--title", default="")
    p_add.add_argument("--skip-build", action="store_true")

    p_build = cfg_sub.add_parser("build", help="Индексы для одной")
    p_build.add_argument("--name", required=True)
    p_build.add_argument("--force", action="store_true", help="Перестроить даже если индексы свежие")
    p_build.add_argument("--check-freshness", action="store_true", help="Только проверить актуальность индексов")
    p_build.add_argument("--validate", action="store_true", help="Только проверить исходники")

    p_build_all = cfg_sub.add_parser("build-all", help="Индексы для всех")
    p_build_all.add_argument("--force", action="store_true", help="Перестроить даже если свежие")

    # bsl
    p_bsl = sub.add_parser("bsl", help="Анализ .bsl")
    bsl_sub = p_bsl.add_subparsers(dest="bsl_command", required=True)

    p_a = bsl_sub.add_parser("analyze", help="Анализ")
    p_a.add_argument("path")

    p_b = bsl_sub.add_parser("baseline", help="Сохранить baseline")
    p_b.add_argument("path")

    p_d = bsl_sub.add_parser("diff", help="Только новые ошибки")
    p_d.add_argument("path")

    # validate
    sub.add_parser("validate", help="Проверить окружение")

    # search
    p_search = sub.add_parser("search", help="Семантический поиск методов 1С")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--limit", type=int, default=10, help="Кол-во результатов")

    # search-code — поиск по коду конфигураций
    p_scode = sub.add_parser("search-code", help="Поиск по коду конфигурации (115K+ методов)")
    p_scode.add_argument("query", help="Поисковый запрос")
    p_scode.add_argument("--config", required=True, help="Имя конфигурации (ut11, edo2, edo3, unp)")
    p_scode.add_argument("--limit", type=int, default=10, help="Кол-во результатов")

    # call-graph — граф вызовов методов
    p_cgraph = sub.add_parser("call-graph", help="Граф вызовов методов конфигурации")
    p_cgraph.add_argument("--config", required=True, help="Имя конфигурации")
    p_cgraph.add_argument("action", choices=["stats", "callers", "callees", "dead-code", "cycles", "json"],
                          default="stats", help="Действие: stats (по умолчанию), callers, callees, dead-code, cycles, json")
    p_cgraph.add_argument("--module", help="Имя модуля (для callers/callees)")
    p_cgraph.add_argument("--method", help="Имя метода (для callers/callees)")

    # standards
    p_std = sub.add_parser("standards", help="Проверка .bsl на стандарты 1С")
    p_std.add_argument("path", help="Путь к .bsl файлу или директории")
    p_std.add_argument("--format", choices=["text", "json"], default="text",
                       help="Формат вывода")
    p_std.add_argument("--severity", choices=["error", "all"], default="all",
                       help="Минимальный уровень severity")

    # backup
    p_backup = sub.add_parser("backup", help="Backup/restore данных проекта")
    backup_sub = p_backup.add_subparsers(dest="backup_command", required=True)

    p_b_create = backup_sub.add_parser("create", help="Создать backup")
    p_b_create.add_argument("--output", "-o", help="Путь к ZIP файлу")
    p_b_create.add_argument("--include-derived", action="store_true",
                            help="Включить индексы derived/ (можно перестроить)")

    p_b_restore = backup_sub.add_parser("restore", help="Восстановить из backup")
    p_b_restore.add_argument("path", help="Путь к ZIP файлу")

    p_b_list = backup_sub.add_parser("list", help="Список backup'ов")
    p_b_list.add_argument("--dir", help="Папка с backup'ами")

    # solve
    p_solve = sub.add_parser("solve", help="Автоматический цикл решения задачи")
    solve_sub = p_solve.add_subparsers(dest="solve_command", required=True)

    p_s_ctx = solve_sub.add_parser("context", help="Собрать контекст для LLM")
    p_s_ctx.add_argument("query", help="Описание задачи")
    p_s_ctx.add_argument("--config", help="Имя конфигурации")
    p_s_ctx.add_argument("--limit", type=int, default=5, help="Кол-во результатов поиска")

    p_s_chk = solve_sub.add_parser("check", help="Проверить .bsl код")
    p_s_chk.add_argument("path", help="Путь к .bsl файлу")
    p_s_chk.add_argument("--config", help="Имя конфигурации")
    p_s_chk.add_argument("--level", choices=["quick", "standard", "full"],
                         default="standard",
                         help="Уровень проверки: quick (только стандарты), "
                              "standard (+BSL LS), full (+метаданные)")
    p_s_chk.add_argument("--ci", action="store_true",
                         help="CI-режим: только errors, exit code 1 при errors")
    p_s_chk.add_argument("--json", action="store_true",
                         help="JSON-вывод для парсинга в CI/CD")
    p_s_chk.add_argument("--sarif", metavar="PATH",
                         help="Записать SARIF 2.1.0 отчёт по указанному пути "
                              "(для GitHub Code Scanning)")

    # mcp
    p_mcp = sub.add_parser("mcp", help="MCP-сервер для IDE/LLM")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve", help="Запустить MCP-сервер (stdio)")
    mcp_sub.add_parser("tools", help="Вывести список доступных tools")

    # data — persistence данных
    p_data = sub.add_parser("data", help="Управление данными (persistence между сессиями)")
    data_sub = p_data.add_subparsers(dest="data_command", required=True)

    p_save = data_sub.add_parser("save-pkg", help="Сохранить данные в ZIP")
    p_save.add_argument("--output", "-o", help="Путь к ZIP (по умолчанию download/)")
    p_save.add_argument("--include-raw", action="store_true",
                        help="Включить data/ (распакованные конфиги — большой объём)")
    p_save.add_argument("--description", "-d", default="", help="Описание пакета")

    p_load = data_sub.add_parser("load-pkg", help="Восстановить данные из ZIP")
    p_load.add_argument("path", help="Путь к ZIP файлу")

    p_info = data_sub.add_parser("info", help="Информация о пакете без распаковки")
    p_info.add_argument("path", nargs="?", help="Путь к ZIP (по умолчанию autosave)")

    p_auto = data_sub.add_parser("autosave", help="Сохранить в стандартное место (download/)")
    p_auto.add_argument("--include-raw", action="store_true")
    p_auto.add_argument("--description", "-d", default="")

    data_sub.add_parser("autoload", help="Восстановить из стандартного места (download/)")

    data_sub.add_parser("status", help="Статус данных: что доступно, что нужно перестроить")

    # GitHub Releases
    p_rpush = data_sub.add_parser("release-push", help="Загрузить пакет в GitHub Releases")
    p_rpush.add_argument("--body", "-b", default="", help="Описание релиза")

    data_sub.add_parser("release-pull", help="Скачать пакет из GitHub Releases")

    data_sub.add_parser("release-status", help="Статус GitHub Releases интеграции")

    # dsl — JSON DSL компиляторы
    p_dsl = sub.add_parser("dsl", help="JSON DSL → XML компиляторы для 1С")
    dsl_sub = p_dsl.add_subparsers(dest="dsl_command", required=True)

    p_dsl_meta = dsl_sub.add_parser("meta", help="Скомпилировать объект метаданных")
    p_dsl_meta.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_meta.add_argument("--json-string", help="JSON-строка")
    p_dsl_meta.add_argument("--output-dir", required=True)

    p_dsl_form = dsl_sub.add_parser("form", help="Скомпилировать форму")
    p_dsl_form.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_form.add_argument("--json-string", help="JSON-строка")
    p_dsl_form.add_argument("--output-path", required=True)

    p_dsl_skd = dsl_sub.add_parser("skd", help="Скомпилировать СКД")
    p_dsl_skd.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_skd.add_argument("--json-string", help="JSON-строка")
    p_dsl_skd.add_argument("--output-path", required=True)

    p_dsl_mxl = dsl_sub.add_parser("mxl", help="Скомпилировать MXL-макет")
    p_dsl_mxl.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_mxl.add_argument("--json-string", help="JSON-строка")
    p_dsl_mxl.add_argument("--output-path", required=True)

    p_dsl_role = dsl_sub.add_parser("role", help="Скомпилировать роль")
    p_dsl_role.add_argument("--json-file", help="Путь к JSON-файлу")
    p_dsl_role.add_argument("--json-string", help="JSON-строка")
    p_dsl_role.add_argument("--output-dir", required=True)

    # cfe — работа с расширениями
    p_cfe = sub.add_parser("cfe", help="Работа с расширениями конфигураций (CFE)")
    cfe_sub = p_cfe.add_subparsers(dest="cfe_command", required=True)

    p_cfe_borrow = cfe_sub.add_parser("borrow", help="Заимствовать объект")
    p_cfe_borrow.add_argument("--extension-path", required=True)
    p_cfe_borrow.add_argument("--config-path", required=True)
    p_cfe_borrow.add_argument("--object-ref", required=True)

    p_cfe_patch = cfe_sub.add_parser("patch", help="Сгенерировать перехватчик метода")
    p_cfe_patch.add_argument("--extension-path", required=True)
    p_cfe_patch.add_argument("--module-path", required=True)
    p_cfe_patch.add_argument("--method-name", required=True)
    p_cfe_patch.add_argument("--interceptor-type", required=True,
        choices=["Before", "After", "ModificationAndControl"])
    p_cfe_patch.add_argument("--context", default="НаСервере")
    p_cfe_patch.add_argument("--is-function", action="store_true")

    p_cfe_diff = cfe_sub.add_parser("diff", help="Анализ расширения")
    p_cfe_diff.add_argument("--extension-path", required=True)
    p_cfe_diff.add_argument("--config-path", required=True)

    # skd-trace — трассировка поля СКД
    p_skd_trace = sub.add_parser("skd-trace", help="Трассировка поля СКД")
    p_skd_trace.add_argument("template_path")
    p_skd_trace.add_argument("field_name")

    # depgraph — граф зависимостей
    p_depgraph = sub.add_parser("depgraph", help="Граф зависимостей метаданных")
    depgraph_sub = p_depgraph.add_subparsers(dest="depgraph_command", required=True)

    p_dg_build = depgraph_sub.add_parser("build", help="Построить граф")
    p_dg_build.add_argument("--name", required=True)
    p_dg_build.add_argument("--output")

    p_dg_query = depgraph_sub.add_parser("query", help="Запрос к графу")
    p_dg_query.add_argument("--name", required=True)
    p_dg_query.add_argument("--query-type", required=True,
        choices=["what_depends_on", "dependencies_of", "transitive_dependencies",
                 "transitive_dependents", "find_cycles", "find_unused_objects",
                 "find_root_objects", "shortest_path", "stats"])
    p_dg_query.add_argument("--object")
    p_dg_query.add_argument("--target")

    p_dg_validate = depgraph_sub.add_parser("validate", help="Проверить что граф DAG")
    p_dg_validate.add_argument("--name", required=True)

    # openspec
    p_openspec = sub.add_parser("openspec", help="OpenSpec — управление изменениями")
    openspec_sub = p_openspec.add_subparsers(dest="openspec_command", required=True)

    p_os_init = openspec_sub.add_parser("init", help="Инициализировать openspec/")
    p_os_init.add_argument("--project-name")

    p_os_proposal = openspec_sub.add_parser("proposal", help="Создать proposal")
    p_os_proposal.add_argument("--change-id", required=True)
    p_os_proposal.add_argument("--title", required=True)
    p_os_proposal.add_argument("--context")
    p_os_proposal.add_argument("--approach")
    p_os_proposal.add_argument("--tasks")
    p_os_proposal.add_argument("--files")

    p_os_list = openspec_sub.add_parser("list", help="Список changes")
    p_os_list.add_argument("--archived", action="store_true")

    p_os_update = openspec_sub.add_parser("update", help="Обновить задачу")
    p_os_update.add_argument("--change-id", required=True)
    p_os_update.add_argument("--task-index", type=int, required=True)
    p_os_update.add_argument("--completed", action="store_true")
    p_os_update.add_argument("--not-completed", action="store_true")
    p_os_update.add_argument("--notes")

    p_os_archive = openspec_sub.add_parser("archive", help="Архивировать")
    p_os_archive.add_argument("--change-id", required=True)

    p_os_validate = openspec_sub.add_parser("validate", help="Валидация")
    p_os_validate.add_argument("--change-id", required=True)

    # session
    p_session = sub.add_parser("session", help="Управление AI-сессиями")
    session_sub = p_session.add_subparsers(dest="session_command", required=True)

    p_s_save = session_sub.add_parser("save", help="Сохранить сессию")
    p_s_save.add_argument("--task")
    p_s_save.add_argument("--completed")
    p_s_save.add_argument("--pending")
    p_s_save.add_argument("--next-action")
    p_s_save.add_argument("--decisions")
    p_s_save.add_argument("--modified")
    p_s_save.add_argument("--summary")

    session_sub.add_parser("restore", help="Восстановить сессию")
    session_sub.add_parser("retro", help="Ретроспектива")
    session_sub.add_parser("clear", help="Очистить сессию")

    # inspect — единый анализ
    p_inspect = sub.add_parser("inspect", help="Единый анализ объектов 1С")
    p_inspect.add_argument("target",
        choices=["cf", "meta", "form", "skd", "mxl", "role", "subsystem", "depgraph"])
    p_inspect.add_argument("path")
    p_inspect.add_argument("--mode", default="overview",
        choices=["overview", "brief", "full", "trace"])
    p_inspect.add_argument("--name")

    # epf-factory — полный цикл создания внешней обработки 1С (.epf)
    p_epf = sub.add_parser("epf-factory",
        help="Создание внешней обработки 1С (.epf) из шаблонов")
    epf_sub = p_epf.add_subparsers(dest="epf_command", required=True)

    p_epf_create = epf_sub.add_parser("create", help="Создать .epf из BSL-кода")
    p_epf_create.add_argument("--name", required=True,
        help="Имя обработки (латиница/кириллица, без пробелов)")
    p_epf_create.add_argument("--synonym", help="Синоним (по умолчанию = name)")
    p_epf_create.add_argument("--bsl", required=True,
        help="Путь к .bsl файлу с модулем формы")
    p_epf_create.add_argument("--output", required=True,
        help="Путь к выходному .epf файлу")
    p_epf_create.add_argument("--form-name", default="Форма",
        help="Имя формы (по умолчанию Форма)")
    p_epf_create.add_argument("--form-spec",
        help="Путь к JSON-файлу с DSL-описанием формы (реквизиты, колонки)")
    p_epf_create.add_argument("--save-sources", action="store_true",
        help="Сохранить v8unpack-исходники в work_dir (не удалять)")
    p_epf_create.add_argument("--skip-bsl-validation", action="store_true",
        help="Пропустить проверку BSL через BSL LS")

    epf_sub.add_parser("templates", help="Список доступных шаблонов")

    args = parser.parse_args()
    project = Project()

    if args.command == "config":
        if args.config_command == "list":
            cmd_config_list(project, args)
        elif args.config_command == "add":
            cmd_config_add(project, args)
        elif args.config_command == "build":
            cmd_config_build(project, args)
        elif args.config_command == "build-all":
            cmd_config_build_all(project, args)
    elif args.command == "bsl":
        if args.bsl_command == "analyze":
            cmd_bsl_analyze(project, args)
        elif args.bsl_command == "baseline":
            cmd_bsl_baseline(project, args)
        elif args.bsl_command == "diff":
            cmd_bsl_diff(project, args)
    elif args.command == "validate":
        cmd_validate(project, args)
    elif args.command == "search":
        cmd_search(project, args)
    elif args.command == "search-code":
        cmd_search_code(project, args)
    elif args.command == "call-graph":
        cmd_call_graph(project, args)
    elif args.command == "standards":
        cmd_standards(project, args)
    elif args.command == "backup":
        cmd_backup(project, args)
    elif args.command == "solve":
        cmd_solve(project, args)
    elif args.command == "mcp":
        cmd_mcp(project, args)
    elif args.command == "data":
        cmd_data(project, args)
    elif args.command == "dsl":
        cmd_dsl(project, args)
    elif args.command == "cfe":
        cmd_cfe(project, args)
    elif args.command == "skd-trace":
        cmd_skd_trace(project, args)
    elif args.command == "depgraph":
        cmd_depgraph(project, args)
    elif args.command == "openspec":
        cmd_openspec(project, args)
    elif args.command == "session":
        cmd_session(project, args)
    elif args.command == "inspect":
        cmd_inspect(project, args)
    elif args.command == "epf-factory":
        cmd_epf_factory(project, args)


# ============================================================================
# EPF Factory — полный цикл создания внешней обработки 1С
# ============================================================================

def cmd_epf_factory(project: Project, args: argparse.Namespace) -> None:
    """Полный цикл создания внешней обработки 1С (.epf) из шаблонов.

    Подход:
        1. Шаблоны ExternalDataProcessor.json / Form.json / Form.id.json /
           Form.elem.json (извлечены из реального EPF через v8unpack)
        2. Подстановка name, synonym, новых UUID (обработка + форма + file)
        3. Запись BSL-модуля формы
        4. Проверка BSL через BSL LS (опционально)
        5. Сборка .epf через v8unpack
        6. Проверка round-trip: распаковка и сравнение BSL-модуля
    """
    from .services.epf_factory import EpfFactory

    factory = EpfFactory()

    if args.epf_command == "templates":
        templates = factory.list_templates()
        print("Шаблоны epf-factory:")
        for k, v in templates.items():
            print(f"  {k:20s}  {v}")
        return

    if args.epf_command == "create":
        import json as json_mod
        from pathlib import Path as PathMod

        bsl_path = PathMod(args.bsl)
        if not bsl_path.exists():
            print(f"❌ BSL-файл не найден: {bsl_path}")
            sys.exit(2)
        bsl_code = bsl_path.read_text(encoding="utf-8")

        result = factory.create_epf(
            name=args.name,
            synonym=args.synonym,
            bsl_code=bsl_code,
            output_epf=args.output,
            form_name=args.form_name,
            form_spec=args.form_spec,
            save_sources=args.save_sources,
            skip_bsl_validation=args.skip_bsl_validation,
        )

        if not result.ok:
            print(f"❌ Ошибка: {result.error}")
            sys.exit(1)

        print(f"✅ EPF создан: {result.epf_path}")
        print(f"   Размер: {result.size_bytes} байт ({result.size_bytes/1024:.1f} КБ)")
        print(f"   Имя:    {result.name}")
        print(f"   Синоним: {result.synonym}")
        print(f"   UUID обработки: {result.proc_uuid}")
        print(f"   UUID формы:     {result.form_uuid}")
        print(f"   BSL-модуль: {result.bsl_lines} строк")
        if not args.skip_bsl_validation:
            print(f"   BSL LS: {result.bsl_errors} errors, {result.bsl_warnings} warnings")
        print(f"   Round-trip: {'✅ OK' if result.round_trip_ok else '❌ FAIL'}")
        if result.work_dir:
            print(f"   Исходники сохранены: {result.work_dir}")


# ============================================================================
# DSL — JSON DSL → XML компиляторы
# ============================================================================

def cmd_dsl(project: Project, args: argparse.Namespace) -> None:
    """JSON DSL → XML компиляторы для 1С."""
    from .services.dsl_compiler import DslCompiler

    compiler = DslCompiler()

    if args.dsl_command == "meta":
        # Compile metadata object
        import json as json_mod
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_meta(definition, args.output_dir)
        print(f"✅ {result.object_type}.{result.object_name}")
        print(f"   XML: {result.xml_path}")
        if result.module_paths:
            print(f"   Modules: {len(result.module_paths)}")
            for p in result.module_paths:
                print(f"     • {p}")
        if result.registered_in_config:
            print(f"   Registered in Configuration.xml: ✅")
        if result.warnings:
            for w in result.warnings:
                print(f"   ⚠️ {w}")

    elif args.dsl_command == "form":
        import json as json_mod
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_form(definition, args.output_path)
        print(f"✅ Form: {result.object_name}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "skd":
        import json as json_mod
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_skd(definition, args.output_path)
        print(f"✅ SKD: {result.object_name}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "mxl":
        import json as json_mod
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_mxl(definition, args.output_path)
        print(f"✅ MXL: {result.object_name}")
        print(f"   XML: {result.xml_path}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "role":
        import json as json_mod
        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_role(definition, args.output_dir)
        print(f"✅ Role: {result.object_name}")
        print(f"   Metadata: {result.xml_path}")
        if result.module_paths:
            print(f"   Rights.xml: {result.module_paths[0]}")


# ============================================================================
# CFE — работа с расширениями конфигураций
# ============================================================================

def cmd_cfe(project: Project, args: argparse.Namespace) -> None:
    """Работа с расширениями конфигураций 1С (CFE)."""
    from .services.cfe_manager import CfeManager

    manager = CfeManager()

    if args.cfe_command == "borrow":
        result = manager.borrow_object(
            Path(args.extension_path),
            Path(args.config_path),
            args.object_ref,
        )
        print(f"✅ Заимствован: {result.object_ref}")
        print(f"   XML созданы: {len(result.xml_created)}")
        for p in result.xml_created:
            print(f"     • {p}")
        if result.registered_in_config:
            print(f"   Регистрация в Configuration.xml: ✅")
        for w in result.warnings:
            print(f"   ⚠️ {w}")

    elif args.cfe_command == "patch":
        result = manager.patch_method(
            Path(args.extension_path),
            args.module_path,
            args.method_name,
            args.interceptor_type,
            args.context,
            args.is_function,
        )
        print(f"✅ Перехватчик: {result.interceptor_type} {result.method_name}")
        print(f"   BSL: {result.bsl_file}")

    elif args.cfe_command == "diff":
        result = manager.diff(
            Path(args.extension_path),
            Path(args.config_path),
        )
        print(f"=== CFE Diff ===")
        print(f"Расширение: {result.extension_path}")
        print(f"Конфигурация: {result.config_path}")
        print()
        print(f"Заимствованные объекты: {len(result.borrowed_objects)}")
        for obj in result.borrowed_objects:
            status = "✅" if obj["found_in_config"] else "⚠️"
            mod = "+" if obj["has_modifications"] else " "
            print(f"  {status} {obj['object_ref']} {mod}")
        print()
        print(f"Методы перехвата: {len(result.patch_methods)}")
        for patch in result.patch_methods:
            print(f"  • {patch['interceptor_type']:25} {patch['method_name']}  ({patch['module_path']})")
        if result.not_in_config:
            print()
            print(f"⚠️ Не найдены в конфигурации: {len(result.not_in_config)}")
            for ref in result.not_in_config:
                print(f"  • {ref}")


# ============================================================================
# SKD Trace — трассировка поля СКД
# ============================================================================

def cmd_skd_trace(project: Project, args: argparse.Namespace) -> None:
    """Трассировка поля СКД через всю цепочку."""
    import sys as sys_mod
    sys_mod.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from skd_parser import trace_field

    schema_path = Path(args.template_path)
    if not schema_path.exists():
        print(f"❌ Файл не найден: {schema_path}")
        sys.exit(2)

    result = trace_field(schema_path, args.field_name)
    if "error" in result:
        print(f"❌ {result['error']}")
        if "available_fields" in result:
            print(f"\nДоступные поля ({len(result['available_fields'])}):")
            for p in result["available_fields"][:20]:
                print(f"  • {p}")
        sys.exit(1)

    print(result["trace_text"])


# Добавляем в main() обработку новых команд


# ============================================================================
# DEPGRAPH — граф зависимостей метаданных
# ============================================================================

def cmd_depgraph(project: Project, args: argparse.Namespace) -> None:
    """Граф зависимостей метаданных 1С (networkx, без Neo4j)."""
    from .services.dependency_graph import DependencyGraph

    if args.depgraph_command == "build":
        dg = DependencyGraph()
        result = dg.build_from_metadata_index(args.name, project.paths)
        print(f"✅ Граф зависимостей: {result.config_name}")
        print(f"   Узлов: {len(result.nodes)}")
        print(f"   Рёбер: {len(result.edges)}")
        if result.warnings:
            for w in result.warnings:
                print(f"   ⚠️ {w}")
        # Сохраняем в файл
        output = args.output or f"derived/configs/{args.name}/dependency-graph.json"
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = project.paths.root / output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import json as json_mod
        out_path.write_text(
            json_mod.dumps(dg.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"   Сохранено: {out_path}")

    elif args.depgraph_command == "query":
        dg = DependencyGraph()
        dg.build_from_metadata_index(args.name, project.paths)

        if args.query_type == "what_depends_on":
            result = dg.what_depends_on(args.object)
            print(f"=== Что зависит от {args.object} ===")
            for r in result:
                print(f"  ← {r['source']} ({r['relation']}) {r['detail']}")
            print(f"\nИтого: {len(result)} зависимых")

        elif args.query_type == "dependencies_of":
            result = dg.dependencies_of(args.object)
            print(f"=== На что ссылается {args.object} ===")
            for r in result:
                print(f"  → {r['target']} ({r['relation']}) {r['detail']}")
            print(f"\nИтого: {len(result)} зависимостей")

        elif args.query_type == "transitive_dependencies":
            result = dg.transitive_dependencies(args.object)
            print(f"=== Транзитивные зависимости {args.object} ===")
            for r in result:
                print(f"  → {r}")
            print(f"\nИтого: {len(result)}")

        elif args.query_type == "transitive_dependents":
            result = dg.transitive_dependents(args.object)
            print(f"=== Кто зависит от {args.object} (транзитивно) ===")
            for r in result:
                print(f"  ← {r}")
            print(f"\nИтого: {len(result)}")

        elif args.query_type == "find_cycles":
            result = dg.find_cycles()
            print(f"=== Циклические зависимости ===")
            for i, cycle in enumerate(result, 1):
                print(f"  {i}. {' → '.join(cycle)}")
            print(f"\nИтого: {len(result)} циклов")

        elif args.query_type == "find_unused_objects":
            result = dg.find_unused_objects()
            print(f"=== Мёртвый код (на кого не ссылаются) ===")
            for r in result:
                print(f"  • {r}")
            print(f"\nИтого: {len(result)} объектов")

        elif args.query_type == "find_root_objects":
            result = dg.find_root_objects()
            print(f"=== Корневые объекты (на них ссылаются, сами ни на кого) ===")
            for r in result:
                print(f"  • {r}")
            print(f"\nИтого: {len(result)} объектов")

        elif args.query_type == "shortest_path":
            if not args.target:
                print("❌ Укажите --target")
                sys.exit(2)
            result = dg.shortest_path(args.object, args.target)
            if result:
                print(f"=== Кратчайший путь {args.object} → {args.target} ===")
                print(f"  {' → '.join(result)}")
            else:
                print(f"❌ Путь не найден: {args.object} → {args.target}")

        elif args.query_type == "stats":
            stats = dg.get_stats()
            print(f"=== Статистика графа ===")
            for k, v in stats.items():
                print(f"  {k}: {v}")

    elif args.depgraph_command == "validate":
        """Проверить что граф DAG (нет циклов)."""
        dg = DependencyGraph()
        dg.build_from_metadata_index(args.name, project.paths)
        stats = dg.get_stats()
        if stats["is_dag"]:
            print(f"✅ Граф — DAG (нет циклов)")
        else:
            print(f"❌ Граф содержит циклы: {stats['cycles']}")
            cycles = dg.find_cycles()
            for i, cycle in enumerate(cycles, 1):
                print(f"  {i}. {' → '.join(cycle)}")


# ============================================================================
# OPENSPEC — Specification-Driven Development
# ============================================================================

def cmd_openspec(project: Project, args: argparse.Namespace) -> None:
    """OpenSpec — управление изменениями."""
    from .services.openspec_manager import OpenSpecManager, SpecDelta

    osm = OpenSpecManager(project_root=project.paths.root)

    if args.openspec_command == "init":
        osm.init_project(args.project_name or "1C AI Dev Environment")
        print(f"✅ OpenSpec инициализирован: {project.paths.root / 'openspec'}")

    elif args.openspec_command == "proposal":
        tasks = args.tasks.split(",") if args.tasks else []
        files = args.files.split(",") if args.files else []
        change = osm.create_proposal(
            change_id=args.change_id,
            title=args.title,
            context=args.context or "",
            approach=args.approach or "",
            tasks=tasks,
            files=files,
        )
        print(f"✅ Proposal создан: {change.change_id}")
        print(f"   Title: {change.title}")
        print(f"   Tasks: {len(change.tasks)}")
        print(f"   Путь: {project.paths.root / 'openspec' / 'changes' / change.change_id}")

    elif args.openspec_command == "list":
        changes = osm.list_changes(include_archived=args.archived)
        if not changes:
            print("Нет changes.")
            return
        print(f"{'ID':<30} {'Title':<40} {'Status':<15} {'Progress':<10}")
        print("-" * 95)
        for c in changes:
            archived = " (arch)" if c["archived"] else ""
            print(f"{c['change_id']:<30} {c['title']:<40} {c['status']:<15} {c['progress']:<10}{archived}")

    elif args.openspec_command == "update":
        completed = None
        if args.completed:
            completed = True
        elif args.not_completed:
            completed = False
        result = osm.update_task(args.change_id, args.task_index, completed, args.notes or "")
        if result:
            print(f"✅ Задача {args.task_index} обновлена в '{args.change_id}'")
        else:
            print(f"❌ Не удалось обновить задачу {args.task_index} в '{args.change_id}'")

    elif args.openspec_command == "archive":
        result = osm.archive(args.change_id)
        if result:
            print(f"✅ Change '{args.change_id}' архивирован")
        else:
            print(f"❌ Не удалось архивировать '{args.change_id}'")

    elif args.openspec_command == "validate":
        errors = osm.validate(args.change_id)
        if not errors:
            print(f"✅ Change '{args.change_id}' валиден")
        else:
            print(f"❌ Ошибки в '{args.change_id}':")
            for e in errors:
                print(f"  • {e}")


# ============================================================================
# SESSION — управление контекстом AI-сессий
# ============================================================================

def cmd_session(project: Project, args: argparse.Namespace) -> None:
    """Управление контекстом AI-сессий."""
    from .services.session_manager import SessionManager

    sm = SessionManager(project_root=project.paths.root)

    if args.session_command == "save":
        completed = args.completed.split(",") if args.completed else []
        pending = args.pending.split(",") if args.pending else []
        files = args.modified.split(",") if args.modified else []
        decisions = args.decisions.split(",") if args.decisions else []
        path = sm.save(
            current_task=args.task or "",
            completed=completed,
            pending=pending,
            next_action=args.next_action or "",
            key_decisions=decisions,
            modified_files=files,
            context_summary=args.summary or "",
        )
        print(f"✅ Сессия сохранена: {path}")

    elif args.session_command == "restore":
        state = sm.restore()
        if not state:
            print("Нет сохранённой сессии.")
            return
        print(f"📅 Сессия от {state.date}")
        print(f"\n📋 Задача: {state.current_task}")
        if state.completed:
            print(f"\n✅ Выполнено ({len(state.completed)}):")
            for item in state.completed:
                print(f"  • {item}")
        if state.pending:
            print(f"\n⏳ Осталось ({len(state.pending)}):")
            for item in state.pending:
                print(f"  • {item}")
        if state.next_action:
            print(f"\n➡️ Следующий шаг: {state.next_action}")
        if state.key_decisions:
            print(f"\n🎯 Решения ({len(state.key_decisions)}):")
            for d in state.key_decisions:
                print(f"  • {d}")
        if state.modified_files:
            print(f"\n📁 Изменено файлов: {len(state.modified_files)}")

    elif args.session_command == "retro":
        print(sm.retro())

    elif args.session_command == "clear":
        if sm.clear():
            print("✅ Сессия очищена")
        else:
            print("Нет сохранённой сессии для очистки")


# ============================================================================
# INSPECT — единый анализ объектов 1С (как у конкурента)
# ============================================================================

def cmd_inspect(project: Project, args: argparse.Namespace) -> None:
    """Единый inspect — анализ объектов 1С с режимами.

    Аналог /inspect из 1c-ai-development-kit — объединяет:
    - cf-info (обзор конфигурации)
    - meta-info (объект метаданных)
    - form-info (форма)
    - skd-info (СКД с режимом trace)
    - mxl-info (MXL макет)
    - role-info (роль)
    - subsystem-info (подсистема)
    - depgraph-info (граф зависимостей)
    """
    import json as json_mod

    target = args.target
    mode = args.mode
    path = Path(args.path)

    if not path.exists():
        print(f"❌ Файл/каталог не найден: {path}")
        sys.exit(2)

    if target == "cf":
        # Обзор конфигурации (Configuration.xml)
        _inspect_cf(path, mode)

    elif target == "meta":
        # Объект метаданных
        _inspect_meta(path, mode, args.name)

    elif target == "form":
        # Форма
        _inspect_form(path, mode)

    elif target == "skd":
        # СКД (с trace mode)
        if mode == "trace":
            if not args.name:
                print("❌ Для trace mode укажите --name <поле>")
                sys.exit(2)
            import sys as sys_mod
            sys_mod.path.insert(0, str(project.paths.scripts_dir))
            from skd_parser import trace_field
            result = trace_field(path, args.name)
            if "error" in result:
                print(f"❌ {result['error']}")
                if "available_fields" in result:
                    print(f"\nДоступные поля ({len(result['available_fields'])}):")
                    for p in result["available_fields"][:20]:
                        print(f"  • {p}")
            else:
                print(result["trace_text"])
        else:
            _inspect_skd(path, mode)

    elif target == "mxl":
        _inspect_mxl(path, mode)

    elif target == "role":
        _inspect_role(path, mode)

    elif target == "subsystem":
        _inspect_subsystem(path, mode)

    elif target == "depgraph":
        # Граф зависимостей
        from .services.dependency_graph import DependencyGraph
        config_name = args.name
        if not config_name:
            print("❌ Для depgraph укажите --name <config_name>")
            sys.exit(2)
        dg = DependencyGraph()
        result = dg.build_from_metadata_index(config_name, project.paths)
        print(f"=== Граф зависимостей: {result.config_name} ===")
        print(f"Узлов: {len(result.nodes)}")
        print(f"Рёбер: {len(result.edges)}")
        stats = dg.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

    else:
        print(f"❌ Неизвестный target: {target}")
        print("Доступные: cf, meta, form, skd, mxl, role, subsystem, depgraph")
        sys.exit(2)


def _inspect_cf(config_path: Path, mode: str) -> None:
    """Обзор конфигурации."""
    import xml.etree.ElementTree as ET

    if config_path.is_dir():
        config_path = config_path / "Configuration.xml"
    if not config_path.exists():
        print(f"❌ Configuration.xml не найден: {config_path}")
        return

    tree = ET.parse(config_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Configuration.xml имеет root <MetaDataObject> или <Configuration>
    # Ищем Properties внутри
    config = root
    config_type = _strip_ns(root.tag)
    
    if config_type == "MetaDataObject":
        # Ищем Configuration внутри MetaDataObject
        for child in root:
            if _strip_ns(child.tag) == "Configuration":
                config = child
                break

    props = None
    for elem in config:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    print(f"=== Configuration ===")
    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects — счётчики по типам
    child_objects = None
    for elem in config:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        print(f"\n=== Объекты по типам ===")
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")


def _inspect_meta(meta_path: Path, mode: str, name: str | None = None) -> None:
    """Обзор объекта метаданных."""
    import xml.etree.ElementTree as ET

    if meta_path.is_dir():
        # В 1С выгрузке структура: Catalogs/<Name>/<Name>.xml ИЛИ Catalogs/<Name>.xml
        # Если передали директорию — ищем .xml рядом (на уровень выше)
        obj_name = meta_path.name  # например "Контрагенты"
        candidate = meta_path.parent / f"{obj_name}.xml"
        if candidate.exists():
            meta_path = candidate
        else:
            # Ищем внутри директории
            if name:
                candidate = meta_path / f"{name}.xml"
                if candidate.exists():
                    meta_path = candidate
            if meta_path.is_dir():
                # Берём первый .xml внутри
                xmls = list(meta_path.glob("*.xml"))
                if xmls:
                    meta_path = xmls[0]

    if not meta_path.exists():
        print(f"❌ Файл не найден: {meta_path}")
        return

    tree = ET.parse(meta_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Реальные файлы 1С имеют обёртку <MetaDataObject><Catalog>...</Catalog></MetaDataObject>
    obj_elem = root
    obj_type = _strip_ns(root.tag)

    if obj_type == "MetaDataObject":
        # Ищем первый дочерний элемент (Catalog, Document, и т.д.)
        for child in root:
            child_tag = _strip_ns(child.tag)
            if child_tag not in ("ConfigDumpInfo",):
                obj_elem = child
                obj_type = child_tag
                break

    print(f"=== {obj_type} ===")

    # Properties — внутри объекта
    props = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects
    child_objects = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        print(f"\n=== Дочерние объекты ===")
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")


def _inspect_form(form_path: Path, mode: str) -> None:
    """Обзор формы."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(form_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print(f"=== Form ===")

    # Считаем элементы
    item_counts: dict[str, int] = {}
    for elem in root.iter():
        tag = _strip_ns(elem.tag)
        if tag in ("InputField", "Button", "Group", "Label", "Table",
                    "Pages", "Page", "CheckBox", "RadioButton",
                    "Hyperlink", "ProgressBar", "TextDocField",
                    "SpreadSheetDocField", "Picture", "CalendarField",
                    "TrackBar", "CommandBar", "UsualGroup"):
            item_counts[tag] = item_counts.get(tag, 0) + 1

    print(f"Элементы:")
    for t, count in sorted(item_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")


def _inspect_skd(skd_path: Path, mode: str) -> None:
    """Обзор СКД."""
    import xml.etree.ElementTree as ET

    if skd_path.is_dir():
        candidate = skd_path / "Ext" / "Template.xml"
        if candidate.exists():
            skd_path = candidate

    tree = ET.parse(skd_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print(f"=== СКД ===")

    # DataSets
    data_sets = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "dataSet":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "name":
                    name_elem = child
                    break
            data_sets.append(name_elem.text if name_elem is not None else "?")

    print(f"Наборов данных: {len(data_sets)}")
    for ds in data_sets:
        print(f"  • {ds}")

    # Parameters — ищем в dataParameters (реальные параметры СКД)
    # Формат: dataParameters → item → parameter (с именем параметра)
    params = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "dataParameters":
            for item in elem:
                if _strip_ns(item.tag) == "item":
                    for child in item:
                        if _strip_ns(child.tag) == "parameter":
                            if child.text:
                                params.append(child.text)
            break

    # Fallback: если dataParameters пустой, ищем parameter с name
    if not params:
        for elem in root.iter():
            if _strip_ns(elem.tag) == "parameter":
                name_elem = None
                for child in elem:
                    if _strip_ns(child.tag) == "name":
                        name_elem = child
                        break
                if name_elem is not None and name_elem.text:
                    params.append(name_elem.text)

    print(f"\nПараметров: {len(params)}")
    for p in params[:20]:
        print(f"  • {p}")
    if len(params) > 20:
        print(f"  ... и ещё {len(params) - 20}")

    # Calculated fields
    calc_fields = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "calculatedField":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "dataPath":
                    name_elem = child
                    break
            calc_fields.append(name_elem.text if name_elem is not None else "?")

    if calc_fields:
        print(f"\nВычисляемых полей: {len(calc_fields)}")
        for cf in calc_fields:
            print(f"  • {cf}")

    # Total fields (resources)
    totals = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "totalField":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "dataPath":
                    name_elem = child
                    break
            totals.append(name_elem.text if name_elem is not None else "?")

    if totals:
        print(f"\nИтоговых полей (ресурсов): {len(totals)}")
        for t in totals:
            print(f"  • {t}")


def _inspect_mxl(mxl_path: Path, mode: str) -> None:
    """Обзор MXL макета."""
    import xml.etree.ElementTree as ET

    if mxl_path.is_dir():
        candidate = mxl_path / "Ext" / "Template.xml"
        if candidate.exists():
            mxl_path = candidate

    tree = ET.parse(mxl_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print(f"=== MXL Макет ===")

    # Areas
    areas = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "area":
            name = elem.get("name", "?")
            areas.append(name)

    print(f"Областей: {len(areas)}")
    for a in areas:
        print(f"  • {a}")

    # Columns
    cols = 0
    for elem in root.iter():
        if _strip_ns(elem.tag) == "column":
            cols += 1
    print(f"\nКолонок: {cols}")

    # Parameters
    params = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "parameter":
            name = elem.get("name", "?")
            params.append(name)
    if params:
        print(f"Параметров: {len(params)}")
        for p in params[:20]:
            print(f"  • {p}")


def _inspect_role(role_path: Path, mode: str) -> None:
    """Обзор роли."""
    import xml.etree.ElementTree as ET

    if role_path.is_dir():
        candidate = role_path / "Ext" / "Rights.xml"
        if candidate.exists():
            role_path = candidate
        else:
            obj_name = role_path.name
            candidate = role_path.parent / f"{obj_name}.xml"
            if candidate.exists():
                role_path = candidate
            else:
                xmls = list(role_path.glob("*.xml"))
                if xmls:
                    role_path = xmls[0]

    if not role_path.exists():
        print(f"❌ Файл не найден: {role_path}")
        return

    tree = ET.parse(role_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print(f"=== Role ===")

    # Реальный формат Rights.xml: <object><name>...</name><right><name>View</name><value>true</value></right></object>
    # Ищем все <object> (с маленькой буквы) или <Object>
    objects = []
    for elem in root.iter():
        tag = _strip_ns(elem.tag).lower()
        if tag == "object":
            obj_name = ""
            rights = []
            for child in elem:
                ctag = _strip_ns(child.tag).lower()
                if ctag == "name" and child.text:
                    obj_name = child.text.strip()
                elif ctag == "right":
                    right_name = ""
                    right_value = ""
                    for sub in child:
                        st = _strip_ns(sub.tag).lower()
                        if st == "name" and sub.text:
                            right_name = sub.text.strip()
                        elif st == "value" and sub.text:
                            right_value = sub.text.strip()
                    if right_value == "true":
                        rights.append(right_name)
            if obj_name:
                objects.append((obj_name, rights))

    if objects:
        print(f"Объектов с правами: {len(objects)}")
        for name, rights in objects[:20]:
            print(f"  • {name}: {', '.join(rights) if rights else '(нет прав)'}")
        if len(objects) > 20:
            print(f"  ... и ещё {len(objects) - 20}")
    else:
        # Возможно это файл метаданных роли (Role.xml), не Rights.xml
        print("(Rights.xml не найден — это файл метаданных роли)")
        props = None
        for elem in root.iter():
            if _strip_ns(elem.tag) == "Properties":
                props = elem
                break
        if props is not None:
            for prop in props:
                tag = _strip_ns(prop.tag)
                text = (prop.text or "").strip()
                if text and len(text) < 100:
                    print(f"  {tag}: {text}")


def _inspect_subsystem(subsystem_path: Path, mode: str) -> None:
    """Обзор подсистемы."""
    import xml.etree.ElementTree as ET

    if subsystem_path.is_dir():
        obj_name = subsystem_path.name
        candidate = subsystem_path.parent / f"{obj_name}.xml"
        if candidate.exists():
            subsystem_path = candidate
        else:
            xmls = list(subsystem_path.glob("*.xml"))
            if xmls:
                subsystem_path = xmls[0]

    if not subsystem_path.exists():
        print(f"❌ Файл не найден: {subsystem_path}")
        return

    tree = ET.parse(subsystem_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Поддержка обёртки MetaDataObject
    obj_elem = root
    if _strip_ns(root.tag) == "MetaDataObject":
        for child in root:
            if _strip_ns(child.tag) not in ("ConfigDumpInfo",):
                obj_elem = child
                break

    print(f"=== Subsystem ===")

    # Properties
    props = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects (content)
    child_objects = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        print(f"\n=== Содержимое ===")
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")




if __name__ == "__main__":
    main()
