#!/usr/bin/env python3
"""
code_validator.py — CLI wrapper для src.services.code_validator.

Этап 1.2, Группа 2: логика перенесена в src/services/code_validator.py.
Этот файл — тонкая CLI-обёртка для запуска из командной строки.

Пример:
    python3 scripts/code_validator.py /tmp/test_processing
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 code_validator.py <source_dir>")
        print()
        print("Пример:")
        print("  python3 code_validator.py /tmp/test_processing")
        sys.exit(1)

    from src.services.code_validator import validate_generated

    source_dir = sys.argv[1]
    result = validate_generated(source_dir)

    print(f"\n{'=' * 60}")
    print(f"ВАЛИДАЦИЯ: {source_dir}")
    print(f"{'=' * 60}")

    print(f"\nВердикт: {result['verdict'].upper()}")
    print(f"Ошибок: {result['total_errors']}")
    print(f"Предупреждений: {result['total_warnings']}")

    if result["structure"]["errors"]:
        print("\nСтруктурные ошибки:")
        for e in result["structure"]["errors"]:
            print(f"  ❌ {e['message']}")

    if result["structure"]["warnings"]:
        print("\nСтруктурные предупреждения:")
        for w in result["structure"]["warnings"]:
            print(f"  ⚠️ {w['message']}")

    for bsl in result.get("bsl_validation", []):
        if bsl.get("errors") or bsl.get("warnings"):
            print(f"\nBSL: {bsl['file']}")
            for e in bsl.get("errors", []):
                print(f"  ❌ Строка {e['line']}: {e['message']}")
            for w in bsl.get("warnings", []):
                print(f"  ⚠️ Строка {w['line']}: {w['message']}")

    for xml in result.get("xml_validation", []):
        if xml.get("errors") or xml.get("warnings"):
            print(f"\nXML: {xml['file']}")
            for e in xml.get("errors", []):
                print(f"  ❌ {e['message']}")
            for w in xml.get("warnings", []):
                print(f"  ⚠️ {w['message']}")

    print(f"\n{'=' * 60}")
    if result["verdict"] == "perfect":
        print("✅ Код идеален — готов к использованию!")
    elif result["verdict"] == "warnings":
        print("⚠️ Есть предупреждения, но код рабочий")
    else:
        print("❌ Есть ошибки — требуется исправление")


if __name__ == "__main__":
    main()
