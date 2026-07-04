#!/usr/bin/env python3
"""
security_auditor.py — CLI wrapper для src.services.analyzers.security_auditor.

Этап 1.2, Группа 1e: логика перенесена в src/services/analyzers/security_auditor.py.

Пример:
    python3 scripts/security_auditor.py module.bsl
    python3 scripts/security_auditor.py data/configs/ut11/CommonModules/
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 security_auditor.py <file.bsl|directory>")
        print()
        print("Примеры:")
        print("  python3 security_auditor.py module.bsl")
        print("  python3 security_auditor.py data/configs/ut11/CommonModules/")
        sys.exit(1)

    from src.services.analyzers.security_auditor import SecurityAuditor

    path = Path(sys.argv[1])
    auditor = SecurityAuditor()

    if path.is_file():
        violations = auditor.audit_file(path)
    elif path.is_dir():
        violations = auditor.audit_path(path)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)

    stats = auditor.get_stats(violations)

    print(f"\n{'=' * 60}")
    print(f"АУДИТ БЕЗОПАСНОСТИ: {path}")
    print(f"{'=' * 60}")
    print(f"\nВсего нарушений: {stats['total_violations']}")
    print(f"  CRITICAL: {stats['critical_count']}")
    print(f"  HIGH:     {stats['high_count']}")
    print(f"  MEDIUM:   {stats['medium_count']}")
    print(f"  LOW:      {stats['low_count']}")

    if violations:
        print(f"\n{'=' * 60}")
        print("ДЕТАЛИ:")
        print(f"{'=' * 60}")
        for v in violations:
            print(f"\n  [{v.severity}] {v.rule_id} (строка {v.line})")
            print(f"  {v.message}")
            print(f"  Рекомендация: {v.recommendation}")

    print(f"\n{'=' * 60}")
    if stats["critical_count"] > 0:
        print("❌ КРИТИЧЕСКИЕ уязвимости — требуется немедленное исправление!")
    elif stats["high_count"] > 0:
        print("⚠️ Высокий риск — исправить как можно скорее")
    elif stats["medium_count"] > 0:
        print("⚠️ Средний риск — рекомендуется исправить")
    elif stats["low_count"] > 0:
        print("ℹ️ Низкий риск — на усмотрение разработчика")
    else:
        print("✅ Нарушений безопасности не найдено")


if __name__ == "__main__":
    main()
