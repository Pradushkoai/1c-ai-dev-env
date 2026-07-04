#!/usr/bin/env python3
"""
form_quality_checker.py — CLI wrapper для src.services.analyzers.form_quality_checker.

Этап 1.2, Группа 1a: логика перенесена в src/services/analyzers/form_quality_checker.py.

Пример:
    python3 scripts/form_quality_checker.py /path/to/form-index.json
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 form_quality_checker.py <form-index.json>")
        sys.exit(1)
    from src.services.analyzers.form_quality_checker import FormQualityChecker

    path = Path(sys.argv[1])
    checker = FormQualityChecker()
    issues = checker.check_form_index(path)
    stats = checker.get_stats(issues)
    print(f"\n{'=' * 60}")
    print(f"ПРОВЕРКА КАЧЕСТВА ФОРМ: {path}")
    print(f"{'=' * 60}")
    print(f"Проблем: {stats['total']}")
    for sev, count in stats["by_severity"].items():
        print(f"  {sev}: {count}")
    if issues:
        print(f"\n{'=' * 60}")
        for i in issues[:20]:
            print(f"\n  [{i.severity}] {i.rule_id} — {i.form_name}")
            print(f"  {i.message}")
    if stats["total"] == 0:
        print("\n✅ Проблем с формами не найдено")


if __name__ == "__main__":
    main()
