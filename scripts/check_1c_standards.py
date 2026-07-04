#!/usr/bin/env python3
"""
check_1c_standards.py — CLI wrapper для src.services.analyzers.check_1c_standards.

Этап 1.2, Группа 1f: логика перенесена в src/services/analyzers/check_1c_standards.py.
Этап 2.1 (future): god-файл будет декомпозирован на 5 модулей по категориям правил.

Пример:
    python3 scripts/check_1c_standards.py module.bsl
    python3 scripts/check_1c_standards.py /path/to/dir --format json
    python3 scripts/check_1c_standards.py module.bsl --severity error --rules std-456,std-1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="check_1c_standards",
        description="Проверка .bsl файлов на соответствие стандартам разработки 1С",
    )
    parser.add_argument("path", help="Путь к .bsl файлу или директории")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Формат вывода (по умолчанию: text)",
    )
    parser.add_argument(
        "--severity",
        choices=["error", "warning", "all"],
        default="all",
        help="Минимальный уровень severity для вывода (по умолчанию: all)",
    )
    parser.add_argument(
        "--rules",
        help="Список rule_id через запятую (пусто = все правила)",
    )

    args = parser.parse_args()

    from src.services.analyzers.check_1c_standards import ALL_RULES, StandardsChecker, format_violations

    path = Path(args.path)
    if not path.exists():
        print(f"❌ Путь не существует: {path}", file=sys.stderr)
        return 2

    # Фильтрация правил
    rules = ALL_RULES
    if args.rules:
        wanted = set(r.strip() for r in args.rules.split(","))
        rules = [r for r in ALL_RULES if r.__name__.replace("rule_", "").replace("-", "_") in wanted]
        if not rules:
            print(f"❌ Не найдено правил: {args.rules}", file=sys.stderr)
            return 2

    checker = StandardsChecker(rules=rules)
    violations = checker.check_path(path)

    # Фильтрация по severity
    if args.severity == "error":
        violations = [v for v in violations if v.severity == "error"]
    elif args.severity == "warning":
        violations = [v for v in violations if v.severity in ("error", "warning")]

    print(format_violations(violations, args.format))

    # Exit code: 1 если есть errors
    has_errors = any(v.severity == "error" for v in violations)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
