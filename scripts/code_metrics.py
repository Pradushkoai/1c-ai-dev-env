#!/usr/bin/env python3
"""
code_metrics.py — CLI wrapper для src.services.analyzers.code_metrics.

Этап 1.2, Группа 1c: логика перенесена в src/services/analyzers/code_metrics.py.

Пример:
    python3 scripts/code_metrics.py module.bsl
    python3 scripts/code_metrics.py /path/to/dir
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python3 code_metrics.py <file.bsl|directory>")
        sys.exit(1)

    from src.services.analyzers.code_metrics import CodeMetricsAnalyzer, _print_metrics, _print_summary

    path = Path(sys.argv[1])
    analyzer = CodeMetricsAnalyzer()

    if path.is_file():
        metrics = analyzer.analyze_file(path)
        _print_metrics(metrics)
    elif path.is_dir():
        results = analyzer.analyze_path(path)
        summary = analyzer.get_summary(results)
        _print_summary(summary, results)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
