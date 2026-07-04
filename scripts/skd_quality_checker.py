#!/usr/bin/env python3
"""
skd_quality_checker.py — CLI wrapper для src.services.analyzers.skd_quality_checker.

Этап 1.2, Группа 1a: логика перенесена в src/services/analyzers/skd_quality_checker.py.

Пример:
    python3 scripts/skd_quality_checker.py /path/to/skd-index.json
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 skd_quality_checker.py <skd-index.json>")
        sys.exit(1)
    from src.services.analyzers.skd_quality_checker import SKDQualityChecker

    path = Path(sys.argv[1])
    checker = SKDQualityChecker()
    issues = checker.check_skd_index(path)
    stats = checker.get_stats(issues)
    print(f"\n{'=' * 60}")
    print(f"ПРОВЕРКА СКД: {path}")
    print(f"{'=' * 60}")
    print(f"Проблем: {stats['total']}")
    for sev, count in stats["by_severity"].items():
        print(f"  {sev}: {count}")
    if issues:
        print(f"\n{'=' * 60}")
        for i in issues[:20]:
            print(f"\n  [{i.severity}] {i.rule_id} — {i.schema_name}")
            print(f"  {i.message}")
    if stats["total"] == 0:
        print("\n✅ Проблем со СКД не найдено")


if __name__ == "__main__":
    main()
