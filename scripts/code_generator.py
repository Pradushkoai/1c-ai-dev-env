#!/usr/bin/env python3
"""
code_generator.py — CLI wrapper для src.services.code_generator.

Этап 1.2, Группа 2: логика перенесена в src/services/code_generator.py.
Этот файл — тонкая CLI-обёртка для запуска из командной строки.

Пример:
    python3 scripts/code_generator.py processing "МояОбработка" "Моя обработка" /tmp/out
    python3 scripts/code_generator.py report "ОтчетПоПродажам" "Отчёт по продажам" /tmp/out
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 5:
        print("Использование:")
        print("  python3 code_generator.py processing <name> <synonym> <output_dir> [description] [author]")
        print("  python3 code_generator.py report <name> <synonym> <output_dir> [description] [author] [data_source] [main_query]")
        sys.exit(1)

    from src.services.code_generator import generate_processing, generate_report

    obj_type = sys.argv[1]
    name = sys.argv[2]
    synonym = sys.argv[3]
    output_dir = sys.argv[4]
    description = sys.argv[5] if len(sys.argv) > 5 else ""
    author = sys.argv[6] if len(sys.argv) > 6 else ""

    if obj_type == "processing":
        result = generate_processing(name, synonym, output_dir, description, author)
    elif obj_type == "report":
        data_source = sys.argv[7] if len(sys.argv) > 7 else ""
        main_query = sys.argv[8] if len(sys.argv) > 8 else ""
        result = generate_report(name, synonym, output_dir, description, author, data_source, main_query)
    else:
        print(f"❌ Неизвестный тип: {obj_type}. Используйте 'processing' или 'report'.")
        sys.exit(1)

    print(f"✅ Сгенерировано: {result['stats']['total_files']} файлов в {output_dir}")
    for f in result["files"]:
        print(f"  {f['type']:8s} {f['path']}")


if __name__ == "__main__":
    main()
