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
    """Семантический поиск по методам 1С (TF-IDF)."""
    from .services.search import search as tfidf_search

    index_path = project.paths.fast_search_index
    if not index_path.exists():
        print("❌ Индекс не найден. Запустите: python3 scripts/fast_search_1c.py build")
        sys.exit(1)

    results = tfidf_search(index_path, args.query, args.limit)

    print(f'Поиск: "{args.query}"')
    print(f'Найдено: {len(results)} результатов')
    print()
    for rank, r in enumerate(results, 1):
        print(f'{rank}. [{r["score"]:.3f}] {r["name_ru"]} ({r["name_en"]})')
        print(f'   Контекст: {r["context"]}')
        print(f'   Синтаксис: {r["syntax"]}')
        if r['description']:
            print(f'   Описание: {r["description"]}')
        print()


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
    """Собирает контекст для LLM: методы платформы + API конфигурации + стандарты."""
    import json

    query = args.query
    config_name = getattr(args, 'config', None)
    limit = getattr(args, 'limit', 5)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: сбор контекста для задачи              ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"\nЗадача: {query}")
    print()

    # 1. Поиск методов платформы 1С
    print("=== 1. Методы платформы 1С (TF-IDF поиск) ===")
    from .services.search import search as tfidf_search

    index_path = project.paths.fast_search_index
    if index_path.exists():
        results = tfidf_search(index_path, query, limit=limit)
        if results:
            for i, r in enumerate(results, 1):
                print(f"  {i}. [{r['score']:.3f}] {r['name_ru']} ({r['name_en']})")
                print(f"     Контекст: {r['context']}")
                print(f"     Синтаксис: {r['syntax']}")
                if r.get('description'):
                    print(f"     Описание: {r['description'][:100]}")
                print()
        else:
            print("  Ничего не найдено.\n")
    else:
        print("  ⚠️  Индекс платформы не найден. Запустите: python3 scripts/fast_search_1c.py build\n")

    # 2. API-справочник конфигурации
    if config_name:
        print(f"=== 2. API конфигурации '{config_name}' ===")
        api_json = project.paths.config_api_reference_json(config_name)
        if api_json.exists():
            with open(api_json, 'r', encoding='utf-8') as f:
                modules = json.load(f)

            # Ищем модули по ключевым словам из запроса
            query_lower = query.lower()
            relevant = []
            for m in modules:
                # Простая эвристика — ищем совпадение в имени модуля
                if any(word in m['name'].lower() for word in query_lower.split()):
                    relevant.append(m)

            if relevant:
                print(f"  Найдено {len(relevant)} релевантных модулей:")
                for m in relevant[:limit]:
                    print(f"  • {m['name']}: {m.get('methods_count', 0)} методов")
                    # Показываем топ-3 метода
                    for method in m.get('methods', [])[:3]:
                        print(f"    - {method['name']}({', '.join(p['name'] for p in method.get('params', []))})")
                print()
            else:
                print(f"  Релевантных модулей не найдено. Всего модулей: {len(modules)}\n")
        else:
            print(f"  ⚠️  API-справочник не найден. Запустите: 1c-ai config build --name {config_name}\n")
    else:
        print("=== 2. API конфигурации ===")
        print("  ⚠️  Конфигурация не указана (--config). Пропускаем.\n")

    # 3. Стандарты 1С
    print("=== 3. Стандарты 1С для соблюдения ===")
    standards_dir = project.paths.root / "tools" / "repos" / "1c-standards-claude-skill" / "1c-standards" / "rules"
    if standards_dir.exists():
        print(f"  Доступно {len(list(standards_dir.glob('*.md')))} разделов стандартов ITS:")
        print("  • 01 — Создание и изменение объектов метаданных")
        print("  • 03 — Реализация обработки данных")
        print("  • 04 — Соглашения при написании кода (STD 454, 455, 456)")
        print("  • 12 — Клиент-серверное взаимодействие")
        print()
        print("  Ключевые правила:")
        print("  • Структура модуля: #Область ПрограммныйИнтерфейс / Служебный...")
        print("  • Запрещено: Сообщить(), Выполнить(), Вычислить(), ?(...)")
        print("  • Запрещено: точечная нотация (Товар.Цена)")
        print("  • Запрещено: запрос в цикле, Попытка вокруг DB")
        print()
    else:
        print("  ⚠️  Стандарты не найдены. Запустите: bash install.sh\n")

    # 4. Антипаттерны
    print("=== 4. Антипаттерны для избегания ===")
    antipatterns_path = project.paths.root / "tools" / "repos" / "ai_rules_1c" / "content" / "rules" / "anti-patterns.md"
    if antipatterns_path.exists():
        print("  CRITICAL:")
        print("  • Query in Loop — запрос в цикле")
        print("  • Direct Attribute Access — точечная нотация")
        print("  • Subquery in SELECT — подзапрос в SELECT")
        print("  • Excessive Client-Server Calls — лишние вызовы")
        print()
        print("  Полную документация: tools/repos/ai_rules_1c/content/rules/anti-patterns.md\n")
    else:
        print("  ⚠️  Файл антипаттернов не найден.\n")

    # 5. Проверки после генерации
    print("=== 5. После генерации кода — выполните проверку ===")
    print(f"  1c-ai solve check <file.bsl> --config {config_name or 'ut11'}")
    print(f"  1c-ai bsl analyze <file.bsl>")
    print(f"  1c-ai standards <file.bsl>")
    print()
    print("─" * 60)
    print("Контекст собран. Теперь LLM может генерировать код,")
    print("опираясь на методы, API и стандарты выше.")


def _solve_check(project: Project, args: argparse.Namespace) -> None:
    """Проверяет .bsl код: BSL LS + 22 правила стандартов."""
    from pathlib import Path
    import json

    bsl_path = Path(args.path)
    if not bsl_path.is_absolute():
        bsl_path = project.paths.root / bsl_path

    if not bsl_path.exists():
        print(f"❌ Файл не найден: {bsl_path}")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: проверка кода                          ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"\nФайл: {bsl_path}")
    print()

    total_errors = 0
    total_warnings = 0

    # 1. BSL Language Server (187 диагностик)
    print("=== 1. BSL Language Server (187 диагностик) ===")
    if project.paths.bsl_ls_binary.exists():
        try:
            result = project.bsl_analyzer.analyze(bsl_path)
            print(f"  Найдено: {result.total} диагностик")
            for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:10]:
                print(f"    {count:4d}  {code}")
            total_errors += sum(1 for d in result.diagnostics if d.get('severity', '').lower() == 'error')
            total_warnings += sum(1 for d in result.diagnostics if d.get('severity', '').lower() in ('warning', 'information', 'hint'))
            print()
        except Exception as e:
            print(f"  ⚠️  Ошибка BSL LS: {e}\n")
    else:
        print("  ⚠️  BSL LS не установлен. Запустите: bash install.sh\n")

    # 2. check_1c_standards (22 правила)
    print("=== 2. Проверка стандартов 1С (22 правила) ===")
    import importlib.util
    script_path = project.paths.scripts_dir / "check_1c_standards.py"
    if not script_path.exists():
        script_path = project.paths.root / "setup" / "scripts" / "check_1c_standards.py"
    if script_path.exists():
        spec = importlib.util.spec_from_file_location("check_1c_standards", script_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["check_1c_standards"] = mod
        spec.loader.exec_module(mod)

        checker = mod.StandardsChecker()
        violations = checker.check_file(bsl_path)

        std_errors = sum(1 for v in violations if v.severity == "error")
        std_warnings = sum(1 for v in violations if v.severity == "warning")
        total_errors += std_errors
        total_warnings += std_warnings

        print(f"  Найдено: {std_errors} errors, {std_warnings} warnings")
        for v in violations[:15]:
            print(f"  {v.severity.upper():7} {v.rule_id:25} {v.file}:{v.line}  {v.message[:80]}")
        if len(violations) > 15:
            print(f"  ... и ещё {len(violations) - 15}")
        print()
    else:
        print("  ⚠️  check_1c_standards.py не найден.\n")

    # 3. Итоговый отчёт
    print("─" * 60)
    print(f"ИТОГО: {total_errors} errors, {total_warnings} warnings")
    print()
    if total_errors == 0 and total_warnings == 0:
        print("✅ Код прошёл все проверки! Готов к коммиту.")
    elif total_errors == 0:
        print("⚠️  Нет критичных ошибок, но есть warnings.")
        print("   Исправьте warnings перед коммитом.")
    else:
        print("❌ Есть критичные ошибки. Код НЕ готов к коммиту.")
        print("   Исправьте все errors и повторите проверку:")
        print(f"   1c-ai solve check {bsl_path}")

    sys.exit(1 if total_errors > 0 else 0)


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
    elif args.command == "standards":
        cmd_standards(project, args)
    elif args.command == "backup":
        cmd_backup(project, args)
    elif args.command == "solve":
        cmd_solve(project, args)


if __name__ == "__main__":
    main()
