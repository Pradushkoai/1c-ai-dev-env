"""
dsl_cmd.py — CLI команда для DSL компиляторов.

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

import sys

from src.project import Project


def cmd_dsl(project: Project, args: object) -> None:
    """JSON DSL → XML компиляторы для 1С."""
    from src.services.dsl_compiler import DslCompiler

    compiler = DslCompiler()

    if args.dsl_command == "meta":
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
            print("   Registered in Configuration.xml: ✅")
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
