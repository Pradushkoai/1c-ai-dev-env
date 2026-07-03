"""
config.py — CLI команды для управления конфигурациями 1С.

P2.1: вынесено из cli.py.
Команды: config list, config add, config build, config build-all
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.project import Project


def _print_build_report(report: dict) -> None:
    """Унифицированный вывод отчёта build()."""
    name = report.get("name", "?")
    skipped = report.get("skipped", [])
    if skipped == ["all"]:
        print(f"✅ {name}: все индексы уже свежие (skip)")
        return
    parts = []
    for key in ("metadata", "api", "skd", "forms"):
        val = report.get(key)
        if val is True:
            tag = "✅"
            if key in skipped:
                tag = "⏭️"
        else:
            tag = "❌"
        parts.append(f"{key}={tag}")
    print(f"✅ {name}: {' '.join(parts)}")
    if skipped and skipped != ["all"]:
        print(f"   ⏭️ Пропущено (уже свежие): {', '.join(skipped)}")


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
        report = project.config_manager.build(args.name, force=True)
        _print_build_report(report)


def cmd_config_build(project: Project, args: argparse.Namespace) -> None:
    if getattr(args, "check_freshness", False):
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
            mark = "✅" if (idx.exists and not idx.is_stale) else "❌"
            print(f"  {mark} {idx.name}: exists={idx.exists}, stale={idx.is_stale}")
            if idx.stale_reason:
                print(f"      {idx.stale_reason}")
        return
    if getattr(args, "validate", False):
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
    force = getattr(args, "force", False)
    build_report: dict = project.config_manager.build(args.name, force=force)
    _print_build_report(build_report)


def cmd_config_build_all(project: Project, args: argparse.Namespace) -> None:
    force = getattr(args, "force", False)
    results = project.config_manager.build_all(force=force)
    for r in results:
        _print_build_report(r)
