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
    print("=== 1. Методы платформы 1С (BM25+TF-IDF поиск) ===")
    from .services.search_bm25 import search_auto, detect_index_version

    index_path = project.paths.fast_search_index
    if index_path.exists():
        version = detect_index_version(index_path)
        algo_name = 'BM25+триграммы (v2)' if version == 2 else 'TF-IDF (v1, legacy)'
        print(f"   Алгоритм: {algo_name}")
        results = search_auto(index_path, query, limit=limit)
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
    """
    Проверяет .bsl код: BSL LS + 56 правил стандартов.

    Уровни проверки (--level):
    - quick:    только check_1c_standards (быстро, без Java)
    - standard: quick + BSL LS (по умолчанию)
    - full:     standard + check_metadata_standards (если есть XML метаданные)
    """
    from pathlib import Path
    import json

    level = getattr(args, 'level', 'standard')

    bsl_path = Path(args.path)
    if not bsl_path.is_absolute():
        bsl_path = project.paths.root / bsl_path

    if not bsl_path.exists():
        print(f"❌ Файл не найден: {bsl_path}")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  1c-ai solve: проверка кода [level={level}]            ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"\nФайл: {bsl_path}")
    print(f"Уровень: {level}")
    print()

    total_errors = 0
    total_warnings = 0

    # 1. check_1c_standards (56 правил) — все уровни
    print("=== 1. Проверка стандартов 1С (56 правил) ===")
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

    # 2. BSL Language Server (187 диагностик) — standard / full
    if level in ('standard', 'full'):
        print("=== 2. BSL Language Server (187 диагностик) ===")
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

    # 3. Метаданные (18 правил) — только full
    if level == 'full':
        print("=== 3. Проверка метаданных (18 правил) ===")
        meta_script = project.paths.scripts_dir / "check_metadata_standards.py"
        if not meta_script.exists():
            meta_script = project.paths.root / "setup" / "scripts" / "check_metadata_standards.py"
        if meta_script.exists():
            try:
                spec2 = importlib.util.spec_from_file_location("check_metadata_standards", meta_script)
                mod2 = importlib.util.module_from_spec(spec2)
                sys.modules["check_metadata_standards"] = mod2
                spec2.loader.exec_module(mod2)

                checker2 = mod2.MetadataStandardsChecker()
                meta_violations = checker2.check_path(bsl_path.parent if bsl_path.is_file() else bsl_path)
                meta_errors = sum(1 for v in meta_violations if v.severity == "error")
                meta_warnings = sum(1 for v in meta_violations if v.severity == "warning")
                total_errors += meta_errors
                total_warnings += meta_warnings

                print(f"  Найдено: {meta_errors} errors, {meta_warnings} warnings")
                for v in meta_violations[:10]:
                    print(f"  {v.severity.upper():7} {v.rule_id:25} {v.message[:80]}")
                print()
            except Exception as e:
                print(f"  ⚠️  Ошибка check_metadata: {e}\n")
        else:
            print("  ⚠️  check_metadata_standards.py не найден.\n")

    # Итоговый отчёт
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
        print(f"   1c-ai solve check {bsl_path} --level {level}")

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
            print("   export GITHUB_TOKEN=ghp_xxx")
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
            print("   Установите GITHUB_TOKEN: export GITHUB_TOKEN=ghp_xxx")
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
