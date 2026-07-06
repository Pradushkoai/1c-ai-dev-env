#!/usr/bin/env python3
"""
build_config_index_generic.py — CLI wrapper для src.services.builders.config_index.

Этап 2.4: логика перенесена в src/services/builders/config_index.py.

Пример:
    python3 scripts/build_config_index_generic.py /path/to/config /path/to/output.json "Config Name"
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python3 build_config_index_generic.py <config_dir> <output_index> <config_name>")
        print()
        print("Example:")
        print("  python3 build_config_index_generic.py /home/z/my-project/config-priemka \\")
        print('       /home/z/my-project/config-priemka-index.md "Приемка товаров"')
        sys.exit(1)

    from src.services.builders.config_index import build_index

    config_dir = sys.argv[1]
    output_index = sys.argv[2]
    config_name = sys.argv[3]
    build_index(config_dir, output_index, config_name)


if __name__ == "__main__":
    main()
