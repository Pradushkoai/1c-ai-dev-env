"""
skd_trace_cmd.py — CLI команда для трассировки СКД.

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.project import Project


def cmd_skd_trace(project: Project, args: object) -> None:
    """Трассировка поля СКД через всю цепочку."""
    import sys as sys_mod

    sys_mod.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
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
