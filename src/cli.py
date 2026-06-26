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


def cmd_config_list(project: Project, args):
    configs = project.list_configs()
    if not configs:
        print("Нет конфигураций.")
        return
    print(f"{'Имя':<15} {'Версия':<15} {'Статус':<10} {'Объектов':<10} {'Путь'}")
    print("-" * 80)
    for c in configs:
        path = str(c.path) if c.path else (str(c.archive) if c.archive else "—")
        print(f"{c.name:<15} {c.version:<15} {c.status:<10} {c.objects_count:<10} {path}")


def cmd_config_add(project: Project, args):
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


def cmd_config_build(project: Project, args):
    report = project.config_manager.build(args.name)
    print(f"✅ {args.name}: index={'✅' if report['index'] else '❌'} api={'✅' if report['api'] else '—'}")


def cmd_config_build_all(project: Project, args):
    results = project.config_manager.build_all()
    for r in results:
        print(f"✅ {r['name']}: index={'✅' if r['index'] else '❌'} api={'✅' if r['api'] else '—'}")


def cmd_bsl_analyze(project: Project, args):
    result = project.bsl_analyzer.analyze(Path(args.path))
    print(f"Всего: {result.total}")
    for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:4d}  {code}")


def cmd_bsl_baseline(project: Project, args):
    result = project.bsl_analyzer.save_baseline(Path(args.path))
    print(f"✅ Baseline: {result.total} диагностик")


def cmd_bsl_diff(project: Project, args):
    diff = project.bsl_analyzer.diff(Path(args.path))
    print(f"\n🆕 НОВЫЕ ({len(diff.new)}):")
    for d in diff.new[:20]:
        print(f"  + {d['code']} (строка {d['line']}): {d['message']}")
    print(f"\n✅ ИСПРАВЛЕННЫЕ ({len(diff.fixed)}):")
    for d in diff.fixed[:10]:
        print(f"  - {d['key']}")


def cmd_validate(project: Project, args):
    checks = project.validate()
    all_ok = True
    for name, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {name}")
        if not ok:
            all_ok = False
    sys.exit(0 if all_ok else 1)


def cmd_search(project: Project, args):
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


def cmd_standards(project: Project, args):
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


def main():
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


if __name__ == "__main__":
    main()
