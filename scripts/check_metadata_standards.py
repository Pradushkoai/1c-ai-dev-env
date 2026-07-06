#!/usr/bin/env python3
"""
check_metadata_standards.py — CLI wrapper для src.services.analyzers.check_metadata_standards.

Этап 1.2, Группа 1c: логика перенесена в src/services/analyzers/check_metadata_standards.py.

Пример:
    python3 scripts/check_metadata_standards.py data/configs/priemka
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 check_metadata_standards.py <config_dir>")
        print()
        print("Пример:")
        print("  python3 check_metadata_standards.py data/configs/priemka")
        sys.exit(1)

    from src.services.analyzers.check_metadata_standards import check_metadata, format_violations

    config_dir = Path(sys.argv[1])
    if not config_dir.exists():
        print(f"❌ Папка не найдена: {config_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Проверка метаданных: {config_dir}")
    print()

    violations = check_metadata(config_dir)
    print(format_violations(violations))

    has_errors = any(v.severity == "error" for v in violations)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
