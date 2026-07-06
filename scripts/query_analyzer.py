#!/usr/bin/env python3
"""
query_analyzer.py — CLI wrapper для src.services.analyzers.query_analyzer.

Этап 1.2, Группа 1b: логика перенесена в src/services/analyzers/query_analyzer.py.

Пример:
    python3 scripts/query_analyzer.py module.bsl
    python3 scripts/query_analyzer.py /path/to/dir
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 query_analyzer.py <file.bsl|directory>")
        sys.exit(1)

    from src.services.analyzers.query_analyzer import QueryAnalyzer

    path = Path(sys.argv[1])
    analyzer = QueryAnalyzer()
    if path.is_file():
        issues = analyzer.analyze_file(path)
    elif path.is_dir():
        issues = analyzer.analyze_path(path)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)
    stats = analyzer.get_stats(issues)
    print(f"\n{'=' * 60}")
    print(f"АНАЛИЗ ЗАПРОСОВ: {path}")
    print(f"{'=' * 60}")
    print(f"Проблем: {stats['total']}")
    for sev, count in stats["by_severity"].items():
        print(f"  {sev}: {count}")
    if issues:
        print(f"\n{'=' * 60}")
        for i in issues[:20]:
            print(f"\n  [{i.severity}] {i.rule_id} (строка {i.line})")
            print(f"  {i.message}")
            if i.recommendation:
                print(f"  Рекомендация: {i.recommendation}")
    if stats["total"] == 0:
        print("\n✅ Проблем в запросах не найдено")


if __name__ == "__main__":
    main()
