"""
cfe_cmd.py — CLI команда для работы с CFE (расширения конфигураций).

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

from pathlib import Path

from src.project import Project


def cmd_cfe(project: Project, args: object) -> None:
    """Работа с расширениями конфигураций 1С (CFE)."""
    from typing import Any

    from src.services.cfe_manager import CfeManager

    manager = CfeManager()

    if args.cfe_command == "borrow":
        result: Any = manager.borrow_object(
            Path(args.extension_path),
            Path(args.config_path),
            args.object_ref,
        )
        print(f"✅ Заимствован: {result.object_ref}")
        print(f"   XML созданы: {len(result.xml_created)}")
        for p in result.xml_created:
            print(f"     • {p}")
        if result.registered_in_config:
            print("   Регистрация в Configuration.xml: ✅")
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
        print("=== CFE Diff ===")
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
