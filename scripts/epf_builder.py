#!/usr/bin/env python3
"""
epf_builder.py — CLI wrapper для src.services.epf_builder.

Этап 1.2, Группа 2: логика перенесена в src/services/epf_builder.py.
Этот файл — тонкая CLI-обёртка для запуска из командной строки.

Пример:
    python3 scripts/epf_builder.py /tmp/my_processing /tmp/output.epf
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 3:
        print("Использование: python3 epf_builder.py <source_dir> <output.epf>")
        sys.exit(1)

    from src.services.epf_builder import build_epf

    result = build_epf(sys.argv[1], sys.argv[2])
    print(f"\n✅ .epf создан: {result['file_path']}")
    print(f"   Размер: {result['size']} байт")
    print(f"   Объект: {result['object_name']} ({result['object_type']})")
    print(f"   UUID: {result['uuid']}")
    print(f"   Файлов внутри: {result['files_included']}")


if __name__ == "__main__":
    main()
