#!/usr/bin/env python3
"""
transaction_checker.py — CLI wrapper для src.services.analyzers.transaction_checker.

Этап 1.2, Группа 1b: логика перенесена в src/services/analyzers/transaction_checker.py.

Пример:
    python3 scripts/transaction_checker.py module.bsl
    python3 scripts/transaction_checker.py /path/to/dir
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 transaction_checker.py <file.bsl|directory>")
        sys.exit(1)

    from src.services.analyzers.transaction_checker import TransactionChecker

    path = Path(sys.argv[1])
    checker = TransactionChecker()

    if path.is_file():
        violations = checker.check_file(path)
    elif path.is_dir():
        violations = checker.check_path(path)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)

    stats = checker.get_stats(violations)
    print(f"\n{'=' * 60}")
    print(f"ПРОВЕРКА ТРАНЗАКЦИЙ: {path}")
    print(f"{'=' * 60}")
    print(f"Нарушений: {stats['total']}")
    for sev, count in stats["by_severity"].items():
        print(f"  {sev}: {count}")

    if violations:
        print(f"\n{'=' * 60}")
        for v in violations:
            print(f"\n  [{v.severity}] {v.rule_id} (строка {v.line})")
            print(f"  {v.message}")
            if v.recommendation:
                print(f"  Рекомендация: {v.recommendation}")

    if stats["total"] == 0:
        print("\n✅ Нарушений транзакционной логики не найдено")


if __name__ == "__main__":
    main()
