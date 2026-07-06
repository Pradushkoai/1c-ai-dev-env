#!/usr/bin/env python3
"""
architecture_analyzer.py — CLI wrapper для src.services.analyzers.architecture_analyzer.

Этап 1.2, Группа 1d: логика перенесена в src/services/analyzers/architecture_analyzer.py.

Пример:
    python3 scripts/architecture_analyzer.py data/configs/ut11
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 architecture_analyzer.py <config_dir>")
        print()
        print("Пример:")
        print("  python3 architecture_analyzer.py data/configs/ut11")
        sys.exit(1)

    from src.services.analyzers.architecture_analyzer import ArchitectureAnalyzer

    config_dir = Path(sys.argv[1])
    analyzer = ArchitectureAnalyzer()
    issues, modules = analyzer.analyze_config(config_dir)
    stats = analyzer.get_stats(issues)

    print(f"\n{'=' * 60}")
    print(f"АНАЛИЗ АРХИТЕКТУРЫ: {config_dir}")
    print(f"{'=' * 60}")
    print(f"Модулей проанализировано: {len(modules)}")
    print(f"Проблем найдено: {stats['total_issues']}")
    for sev, count in stats["by_severity"].items():
        print(f"  {sev}: {count}")

    print("\nПо правилам:")
    for rule, count in stats["by_rule"].items():
        print(f"  {rule}: {count}")

    if issues:
        print(f"\n{'=' * 60}")
        print("ДЕТАЛИ:")
        for issue in issues[:20]:
            print(f"\n  [{issue.severity}] {issue.rule_id} — {issue.module}")
            print(f"  {issue.message}")
            if issue.recommendation:
                print(f"  Рекомендация: {issue.recommendation}")


if __name__ == "__main__":
    main()
