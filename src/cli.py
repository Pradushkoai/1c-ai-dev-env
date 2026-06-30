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


def cmd_config_add(project: Project, args: argparse.Namespace) -> None:
    """Добавить конфигурацию из ZIP или .cf файла."""
    if args.cf:
        config = project.config_manager.add_from_cf(args.name, Path(args.cf), args.title)
    else:
        config = project.config_manager.add_from_zip(args.name, Path(args.zip), args.title)
    print(f"✅ Добавлена: {config.name} v{config.version} ({config.objects_count} объектов)")
    if not args.skip_build:
        print("Индексация...")
        report = project.config_manager.build(args.name)
        print(f"  Индекс: {'✅' if report['index'] else '❌'}")
        print(f"  API:    {'✅' if report['api'] else '—'}")


def cmd_config_build(project: Project, args: argparse.Namespace) -> None:
    report = project.config_manager.build(args.name)
    print(f"✅ {args.name}: index={'✅' if report['index'] else '❌'} api={'✅' if report['api'] else '—'}")


def cmd_config_build_all(project: Project, args: argparse.Namespace) -> None:
    results = project.config_manager.build_all()
    for r in results:
        print(f"✅ {r['name']}: index={'✅' if r['index'] else '❌'} api={'✅' if r['api'] else '—'}")


def cmd_bsl_analyze(project: Project, args: argparse.Namespace) -> None:
    result = project.bsl_analyzer.analyze(Path(args.path))
    print(f"Всего: {result.total}")
    for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:4d}  {code}")


def cmd_bsl_baseline(project: Project, args: argparse.Namespace) -> None:
    result = project.bsl_analyzer.save_baseline(Path(args.path))
    print(f"✅ Baseline: {result.total} диагностик")


def cmd_bsl_diff(project: Project, args: argparse.Namespace) -> None:
    diff = project.bsl_analyzer.diff(Path(args.path))
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
    from .services.search_bm25 import search_auto, detect_index_version

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
    from .services.call_graph import build_call_graph
    import json as json_mod

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
            with open(api_json, 'r', encoding='utf-8') as f:
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
    from .services.backup_manager import BackupManager
    from pathlib import Path

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
    from pathlib import Path

    if args.solve_command == 'context':
        _solve_context(project, args)
    elif args.solve_command == 'check':
        _solve_check(project, args)


def _solve_context(project: Project, args: argparse.Namespace) -> None:
    """Собирает полный контекст для LLM: все доступные источники."""
    import json

    query = args.query
    config_name = getattr(args, 'config', None)
    limit = getattr(args, 'limit', 5)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: сбор контекста для задачи              ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"\nЗадача: {query}")
    print()

    query_lower = query.lower()
    query_words = query_lower.split()

    # 1. Поиск методов платформы 1С (если есть индекс)
    print("=== 1. Методы платформы 1С ===")
    from .services.search_bm25 import search_auto, detect_index_version
    index_path = project.paths.fast_search_index
    if index_path.exists():
        results = search_auto(index_path, query, limit=limit)
        if results:
            for i, r in enumerate(results, 1):
                print(f"  {i}. [{r['score']:.3f}] {r['name_ru']} ({r.get('name_en', '')})")
                print(f"     Синтаксис: {r.get('syntax', '')}")
                if r.get('description'):
                    print(f"     Описание: {r['description'][:100]}")
            print()
        else:
            print("  Ничего не найдено.\n")
    else:
        print("  ⚠️  Индекс платформы не найден (не критично).\n")

    # 2. API-справочник конфигурации
    if config_name:
        print(f"=== 2. API конфигурации '{config_name}' ===")
        api_json = project.paths.config_api_reference_json(config_name)
        if api_json.exists():
            with open(api_json, 'r', encoding='utf-8') as f:
                modules = json.load(f)
            relevant = [m for m in modules if any(w in m['name'].lower() for w in query_words)]
            if relevant:
                print(f"  Найдено {len(relevant)} релевантных модулей:")
                for m in relevant[:limit]:
                    print(f"  • {m['name']}: {m.get('methods_count', 0)} методов")
                    for method in m.get('methods', [])[:3]:
                        print(f"    - {method['name']}({', '.join(p['name'] for p in method.get('params', []))})")
                print()
            else:
                print(f"  Релевантных модулей не найдено. Всего: {len(modules)}\n")
        else:
            print(f"  ⚠️  API-справочник не найден.\n")

        # 3. Структура объектов (unified-metadata-index)
        print(f"=== 3. Структура объектов '{config_name}' ===")
        unified_path = project.paths.root / "derived" / "configs" / config_name / "unified-metadata-index.json"
        if unified_path.exists():
            with open(unified_path, encoding='utf-8') as f:
                meta = json.load(f)
            # Ищем объекты по ключевым словам
            found_objects = []
            for type_name, objs in meta.get('objects', {}).items():
                for obj in objs:
                    obj_name = obj.get('name', '').lower()
                    if any(w in obj_name for w in query_words):
                        children = obj.get('child_objects', {})
                        found_objects.append({
                            'type': obj.get('type', ''),
                            'name': obj.get('name', ''),
                            'synonym': obj.get('synonym', ''),
                            'attrs': len(children.get('attributes', [])),
                            'ts': len(children.get('tabular_sections', [])),
                            'forms': len(children.get('forms', [])),
                        })
            if found_objects:
                print(f"  Найдено {len(found_objects)} объектов:")
                for o in found_objects[:limit]:
                    print(f"  • {o['type']}: {o['name']} — {o['synonym']}")
                    print(f"    Реквизитов: {o['attrs']}, ТЧ: {o['ts']}, Форм: {o['forms']}")
                print()
            else:
                print(f"  Объекты не найдены. Всего типов: {len(meta.get('objects', {}))}\n")

            # 4. Подсистемы
            subsystems = meta.get('subsystems', [])
            if subsystems:
                relevant_ss = [s for s in subsystems if any(w in s.get('name', '').lower() for w in query_words)]
                if relevant_ss:
                    print(f"  Подсистемы ({len(relevant_ss)} найдено):")
                    for s in relevant_ss[:3]:
                        print(f"  • {s.get('name', '')}: content={len(s.get('content', []))} объектов")
                    print()

            # 5. Подписки на события
            event_subs = meta.get('event_subscriptions', [])
            if event_subs:
                relevant_es = [e for e in event_subs if any(w in e.get('name', '').lower() or w in e.get('handler', '').lower() for w in query_words)]
                if relevant_es:
                    print(f"  Подписки на события ({len(relevant_es)} найдено):")
                    for e in relevant_es[:3]:
                        print(f"  • {e.get('name', '')}: event={e.get('event', '')}, handler={e.get('handler', '')}")
                    print()

            # 6. Регламентные задания
            scheduled_jobs = meta.get('scheduled_jobs', [])
            if scheduled_jobs:
                relevant_sj = [s for s in scheduled_jobs if any(w in s.get('name', '').lower() or w in s.get('method_name', '').lower() for w in query_words)]
                if relevant_sj:
                    print(f"  Регламентные задания ({len(relevant_sj)} найдено):")
                    for s in relevant_sj[:3]:
                        print(f"  • {s.get('name', '')}: method={s.get('method_name', '')}, use={s.get('use', '')}")
                    print()
        else:
            print(f"  ⚠️  unified-metadata-index не найден.\n")

        # 7. СКД-схемы
        print(f"=== 4. СКД-схемы '{config_name}' ===")
        skd_path = project.paths.root / "derived" / "configs" / config_name / "skd-index.json"
        if skd_path.exists():
            with open(skd_path, encoding='utf-8') as f:
                skd = json.load(f)
            schemas = skd.get('schemas', [])
            relevant_skd = [s for s in schemas if any(w in s.get('parent_name', '').lower() or w in s.get('name', '').lower() for w in query_words)]
            if relevant_skd:
                print(f"  Найдено {len(relevant_skd)} СКД-схем:")
                for s in relevant_skd[:3]:
                    schema = s.get('schema', {})
                    ds = schema.get('data_sets', [])
                    params = schema.get('parameters', [])
                    print(f"  • {s.get('parent_name', '')}: {s.get('name', '')}")
                    print(f"    Наборов данных: {len(ds)}, Параметров: {len(params)}")
                print()
            else:
                print(f"  СКД не найдены. Всего: {len(schemas)}\n")
        else:
            print(f"  ⚠️  skd-index не найден.\n")

        # 8. Формы
        print(f"=== 5. Формы '{config_name}' ===")
        form_path = project.paths.root / "derived" / "configs" / config_name / "form-index.json"
        if form_path.exists():
            with open(form_path, encoding='utf-8') as f:
                form_data = json.load(f)
            forms = form_data.get('forms', [])
            relevant_forms = [f for f in forms if any(w in f.get('name', '').lower() or w in f.get('parent_name', '').lower() for w in query_words)]
            if relevant_forms:
                print(f"  Найдено {len(relevant_forms)} форм:")
                for f in relevant_forms[:3]:
                    print(f"  • {f.get('parent_type', '')}: {f.get('parent_name', '')}.{f.get('name', '')}")
                    print(f"    Элементов: {f.get('form', {}).get('element_count', 0)}")
                print()
            else:
                print(f"  Формы не найдены. Всего: {len(forms)}\n")
        else:
            print(f"  ⚠️  form-index не найден.\n")
    else:
        print("=== 2-5. Конфигурация ===")
        print("  ⚠️  Конфигурация не указана (--config). Пропускаем.\n")

    # 9. База знаний (паттерны, антипаттерны, best practices)
    print("=== 6. База знаний 1С ===")
    try:
        from .services.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        kb_results = kb.search(query, limit=limit)
        if kb_results:
            print(f"  Найдено {len(kb_results)} статей:")
            for r in kb_results:
                print(f"  • [{r['category']}] {r['title']} (score={r['score']})")
            print()
        else:
            print("  Статьи не найдены.\n")
    except Exception:
        print("  ⚠️  База знаний недоступна.\n")

    # 10. Стандарты (из check_1c_standards.py, не из tools/repos/)
    print("=== 7. Стандарты 1С (56 правил) ===")
    print("  Доступные проверки (check_1c_standards.py):")
    print("  • Стиль: имена, длина строк, нестingVariables, венгерская нотация")
    print("  • Запросы: конкатенация, LIKE %, функции в WHERE, подзапросы")
    print("  • Клиент-сервер: DB в &НаКлиенте, серверные вызовы в цикле")
    print("  • Безопасность: хардкод, Выполнить(), COM-объекты")
    print("  • Транзакции: без Try/Catch, интерактив в транзакции")
    print()

    # 11. Контрольный список после генерации
    print("=== 8. После генерации кода — выполните проверки ===")
    print(f"  1c-ai solve check <file.bsl> --level full")
    print(f"  (BSL LS + 56 правил + security + metrics + transactions + queries)")
    print()
    print("─" * 60)
    print("Контекст собран. LLM может генерировать код,")
    print("опираясь на методы, структуру, СКД, формы и стандарты выше.")


def _solve_check(project: Project, args: argparse.Namespace) -> None:
    """
    Полная проверка .bsl кода: 7 анализаторов.

    Уровни проверки (--level):
    - quick:    check_1c_standards + security + transactions + queries (без Java)
    - standard: quick + BSL LS
    - full:     standard + metadata_standards + code_metrics

    CI-режим (--ci): только errors, exit code 1 при errors
    JSON-режим (--json): полный JSON-отчёт
    """
    from pathlib import Path
    import json as json_mod
    import importlib.util

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

    total_errors = 0
    total_warnings = 0
    all_violations = []
    scripts_dir = project.paths.scripts_dir

    def _load_script(script_name):
        script_path = scripts_dir / f"{script_name}.py"
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
        checker = std_mod.StandardsChecker()
        violations = checker.check_file(bsl_path)
        for v in violations:
            sev = v.severity
            if sev == "error":
                total_errors += 1
            else:
                total_warnings += 1
            all_violations.append({
                "source": "check_1c_standards",
                "rule_id": v.rule_id,
                "severity": sev,
                "line": v.line,
                "message": v.message,
                "file": v.file,
            })

    # 2. security_auditor (15 правил) — все уровни
    sec_mod = _load_script("security_auditor")
    if sec_mod:
        auditor = sec_mod.SecurityAuditor()
        sec_violations = auditor.audit_file(bsl_path)
        for v in sec_violations:
            sev = v.severity.lower()
            if sev in ('critical', 'high'):
                total_errors += 1
            else:
                total_warnings += 1
            all_violations.append({
                "source": "security_auditor",
                "rule_id": v.rule_id,
                "severity": sev,
                "line": v.line,
                "message": v.message,
                "file": str(bsl_path),
            })

    # 3. transaction_checker (6 правил) — все уровни
    tx_mod = _load_script("transaction_checker")
    if tx_mod:
        tx_checker = tx_mod.TransactionChecker()
        tx_violations = tx_checker.check_file(bsl_path)
        for v in tx_violations:
            sev = v.severity.lower()
            if sev in ('critical', 'high'):
                total_errors += 1
            else:
                total_warnings += 1
            all_violations.append({
                "source": "transaction_checker",
                "rule_id": v.rule_id,
                "severity": sev,
                "line": v.line,
                "message": v.message,
                "file": str(bsl_path),
            })

    # 4. query_analyzer (10 правил) — все уровни
    qa_mod = _load_script("query_analyzer")
    if qa_mod:
        qa_analyzer = qa_mod.QueryAnalyzer()
        qa_issues = qa_analyzer.analyze_file(bsl_path)
        for i in qa_issues:
            sev = i.severity.lower()
            if sev in ('critical', 'high'):
                total_errors += 1
            else:
                total_warnings += 1
            all_violations.append({
                "source": "query_analyzer",
                "rule_id": i.rule_id,
                "severity": sev,
                "line": i.line,
                "message": i.message,
                "file": str(bsl_path),
            })

    # 5. BSL Language Server (187 диагностик) — standard / full
    bsl_ls_available = False
    if level in ('standard', 'full'):
        if project.paths.bsl_ls_binary.exists():
            bsl_ls_available = True
            try:
                result = project.bsl_analyzer.analyze(bsl_path)
                for d in result.diagnostics:
                    sev = d.get('severity', 'warning').lower()
                    if sev == 'error':
                        total_errors += 1
                    else:
                        total_warnings += 1
                    all_violations.append({
                        "source": "bsl_ls",
                        "rule_id": d.get('code', ''),
                        "severity": sev,
                        "line": d.get('line', 0),
                        "message": d.get('message', ''),
                        "file": str(bsl_path),
                    })
            except Exception:
                pass

    # 6. code_metrics — только full
    if level == 'full':
        cm_mod = _load_script("code_metrics")
        if cm_mod:
            analyzer = cm_mod.CodeMetricsAnalyzer()
            metrics = analyzer.analyze_file(bsl_path)
            if metrics.is_god_object:
                total_errors += 1
                all_violations.append({
                    "source": "code_metrics",
                    "rule_id": "GOD_OBJECT",
                    "severity": "error",
                    "line": 0,
                    "message": f"God Object: {metrics.code_lines} строк, {len(metrics.methods)} методов",
                    "file": str(bsl_path),
                })
            for method in metrics.long_methods:
                total_warnings += 1
                all_violations.append({
                    "source": "code_metrics",
                    "rule_id": "LONG_METHOD",
                    "severity": "warning",
                    "line": method.line_start,
                    "message": f"Длинный метод {method.name}: {method.lloc} строк",
                    "file": str(bsl_path),
                })

    # 7. Метаданные (18 правил) — только full
    if level == 'full':
        meta_mod = _load_script("check_metadata_standards")
        if meta_mod:
            try:
                checker2 = meta_mod.MetadataStandardsChecker()
                meta_violations = checker2.check_path(bsl_path.parent if bsl_path.is_file() else bsl_path)
                for v in meta_violations:
                    sev = v.severity
                    if sev == "error":
                        total_errors += 1
                    else:
                        total_warnings += 1
                    all_violations.append({
                        "source": "check_metadata_standards",
                        "rule_id": v.rule_id,
                        "severity": sev,
                        "line": v.line,
                        "message": v.message,
                        "file": v.file,
                    })
            except Exception:
                pass

    # Verdict
    if total_errors == 0 and total_warnings == 0:
        verdict = "ready"
    elif total_errors == 0:
        verdict = "warnings"
    else:
        verdict = "errors"

    # ─── Вывод ───
    if json_mode:
        report = {
            "file": str(bsl_path),
            "level": level,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "verdict": verdict,
            "bsl_ls_available": bsl_ls_available,
            "violations": all_violations if not ci_mode else [v for v in all_violations if v["severity"] in ("error", "critical", "high")],
        }
        print(json_mod.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1 if total_errors > 0 else 0)

    if ci_mode:
        errors_only = [v for v in all_violations if v["severity"] in ("error", "critical", "high")]
        if errors_only:
            print(f"❌ {total_errors} errors found:")
            for v in errors_only[:20]:
                print(f"  {v['source']:25} {v['rule_id']:25} line {v['line']:4}  {v['message'][:80]}")
            if len(errors_only) > 20:
                print(f"  ... и ещё {len(errors_only) - 20}")
        else:
            print(f"✅ No errors ({total_warnings} warnings)")
        sys.exit(1 if total_errors > 0 else 0)

    # Человекочитаемый вывод
    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: проверка кода [level={level}]            ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"\nФайл: {bsl_path}")
    print(f"Уровень: {level}")
    print(f"Анализаторы: check_1c_standards + security + transactions + queries", end="")
    if level in ('standard', 'full'):
        print(f" + BSL_LS", end="")
    if level == 'full':
        print(f" + code_metrics + metadata", end="")
    print("\n")

    by_source = {}
    for v in all_violations:
        by_source.setdefault(v["source"], []).append(v)

    for source, violations in by_source.items():
        errors = [v for v in violations if v["severity"] in ("error", "critical", "high")]
        warnings = [v for v in violations if v["severity"] not in ("error", "critical", "high")]
        print(f"=== {source} ({len(errors)} errors, {len(warnings)} warnings) ===")
        for v in violations[:15]:
            print(f"  {v['severity'].upper():8} {v['rule_id']:25} line {v['line']:4}  {v['message'][:80]}")
        if len(violations) > 15:
            print(f"  ... и ещё {len(violations) - 15}")
        print()

    print("─" * 60)
    print(f"ИТОГО: {total_errors} errors, {total_warnings} warnings")
    print()
    if verdict == "ready":
        print("✅ Код прошёл все проверки! Готов к коммиту.")
    elif verdict == "warnings":
        print("⚠️  Нет критичных ошибок, но есть warnings.")
    else:
        print("❌ Есть критичные ошибки. Код НЕ готов к коммиту.")

    sys.exit(1 if total_errors > 0 else 0)


def cmd_mcp(project: Project, args: argparse.Namespace) -> None:
    """Управление MCP-сервером."""
    if args.mcp_command == 'serve':
        try:
            from .mcp_server import run_mcp_server
            import asyncio
            asyncio.run(run_mcp_server())
        except ImportError as e:
            print(f"❌ MCP SDK не установлен: {e}")
            print("   Установите: pip install mcp")
            sys.exit(1)
    elif args.mcp_command == 'tools':
        # Выводим список tools без запуска сервера
        try:
            from .mcp_server import create_mcp_server
            import asyncio

            async def _list():
                server = create_mcp_server()
                # Достаём handler через декоратор
                # Простой путь — повторно вызвать описание
                from .mcp_server import _get_tools_description
                return _get_tools_description()

            tools = asyncio.run(_list())
            print(f"MCP tools ({len(tools)}):")
            print()
            for t in tools:
                print(f"  • {t['name']}")
                print(f"    {t['description']}")
                print()
        except ImportError as e:
            print(f"❌ MCP SDK не установлен: {e}")
            sys.exit(1)


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
        print(f"  Включая derived: да")
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
            print(f"Манифест:")
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
                print(f"  Восстановить: 1c-ai data autoload")

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

        print(f"Загрузка в GitHub Releases...")
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

        print(f"Скачивание из GitHub Releases...")
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

    cfg_sub.add_parser("build-all", help="Индексы для всех")

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


if __name__ == "__main__":
    main()
