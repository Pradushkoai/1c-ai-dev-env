#!/usr/bin/env python3
"""
diff_analyzer.py — CLI wrapper для src.services.diff.

Этап 1.2, Группа 3: логика перенесена в src/services/diff.py.
Этот файл — тонкая CLI-обёртка для запуска из командной строки.

Использование:
    python3 scripts/diff_analyzer.py <old-index.json> <new-index.json>
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("Использование: python3 diff_analyzer.py <old-index.json> <new-index.json>")
        sys.exit(1)

    # Импорт из src/services/ (после pip install -e .)
    from src.services.diff import DiffAnalyzer

    analyzer = DiffAnalyzer()
    diff = analyzer.compare(Path(sys.argv[1]), Path(sys.argv[2]))
    print(analyzer.format_report(diff))


if __name__ == "__main__":
    main()
