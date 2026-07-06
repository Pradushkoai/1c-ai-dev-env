#!/usr/bin/env python3
"""
cf_extractor.py — CLI wrapper для src.services.cf.extractor.

Этап 1.2, Группа 7: логика перенесена в src/services/cf/extractor.py.

Пример:
    python3 scripts/cf_extractor.py ut11.cf data/configs/ut11
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("Использование: python3 cf_extractor.py <file.cf> <output_dir>")
        print()
        print("Пример:")
        print("  python3 cf_extractor.py ut11.cf data/configs/ut11")
        sys.exit(1)

    from src.services.cf.extractor import extract_cf

    cf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not cf_path.exists():
        print(f"❌ Файл не найден: {cf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Распаковка: {cf_path}")
    print(f"В: {output_dir}")
    print(f"Размер файла: {cf_path.stat().st_size / 1024 / 1024:.1f} МБ")

    try:
        count = extract_cf(cf_path, output_dir)
        print(f"\n✅ Распаковано файлов: {count}")
        print(f"   Каталог: {output_dir}")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
