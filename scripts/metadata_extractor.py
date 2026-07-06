#!/usr/bin/env python3
"""
metadata_extractor.py — CLI wrapper для src.services.metadata.extractor.

Этап 2.3: логика перенесена в src/services/metadata/extractor.py.

Пример:
    python3 scripts/metadata_extractor.py data/configs/ut11
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 metadata_extractor.py <config_dir> [output_path]")
        print()
        print("Пример:")
        print("  python3 metadata_extractor.py data/configs/ut11 derived/configs/ut11/unified-metadata-index.json")
        sys.exit(1)

    from src.services.metadata.extractor import extract_and_save

    config_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "unified-metadata-index.json"
    extract_and_save(config_dir, output)


if __name__ == "__main__":
    main()
