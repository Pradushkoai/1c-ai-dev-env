#!/usr/bin/env python3
"""
register_config.py — CLI обёртка над src.services.config_manager.ConfigManager.

Все вызовы делегируются в ООП-слой. Дублирования логики нет.
"""

import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.project import Project


def main():
    parser = argparse.ArgumentParser(description="Управление конфигурациями 1С")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list")
    p_add = sub.add_parser("add")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--zip", required=True)
    p_add.add_argument("--title", default="")
    p_add.add_argument("--skip-build", action="store_true")
    p_build = sub.add_parser("build")
    p_build.add_argument("--name", required=True)
    sub.add_parser("build-all")
    p_rm = sub.add_parser("remove")
    p_rm.add_argument("--name", required=True)

    args = parser.parse_args()
    project = Project()

    if args.command == "list":
        configs = project.list_configs()
        if not configs:
            print("Нет конфигураций.")
            return
        for c in configs:
            print(f"  {c.name:<15} {c.version:<15} {c.status:<10} {c.objects_count:<10} {c.path or c.archive or '—'}")
    elif args.command == "add":
        config = project.config_manager.add_from_zip(args.name, Path(args.zip), args.title)
        print(f"✅ {config.name} v{config.version} ({config.objects_count} объектов)")
        if not args.skip_build:
            project.config_manager.build(args.name)
    elif args.command == "build":
        project.config_manager.build(args.name)
        print(f"✅ {args.name}")
    elif args.command == "build-all":
        project.config_manager.build_all()
    elif args.command == "remove":
        project.config_manager.remove(args.name)
        print(f"✅ {args.name} удалена")


if __name__ == "__main__":
    main()
