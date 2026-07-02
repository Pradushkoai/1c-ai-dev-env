#!/usr/bin/env python3
"""
run_sarif_scan.py — Запуск 1С анализаторов и генерация SARIF для GitHub Code Scanning.

Используется в .github/workflows/code-scanning.yml.
Вынесено в отдельный файл, чтобы избежать проблем с YAML-отступами в inline python3 -c.

Использование:
    python3 scripts/run_sarif_scan.py "file1.bsl file2.bsl" output.sarif
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _empty_sarif() -> dict:
    """Пустой SARIF для случая, когда нет .bsl файлов или все ошибки.

    SARIF 2.1.0: runs[].tool.driver (без вложенного "tool").
    """
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "1C AI Dev Env",
                        "version": "5.2.0",
                        "informationUri": "https://github.com/Pradushkoai/1c-ai-dev-env",
                        "rules": [],
                    }
                },
                "results": [],
            }
        ],
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: run_sarif_scan.py <bsl_files_space_sep> <output_sarif>", file=sys.stderr)
        return 1

    bsl_files_arg = sys.argv[1]
    output_path = Path(sys.argv[2])

    bsl_files = [f.strip() for f in bsl_files_arg.split() if f.strip()]

    if not bsl_files:
        print("No .bsl files to scan")
        sarif = _empty_sarif()
        output_path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
        return 0

    print(f"Scanning {len(bsl_files)} file(s):")
    for f in bsl_files:
        print(f"  - {f}")

    # Импортируем после проверки аргументов (быстрее для случая без файлов)
    try:
        from src.services.task_processor import TaskProcessor
        from src.services.sarif_reporter import SarifReporter
        from src.project import Project

        project = Project.from_cwd()
        processor = TaskProcessor(project.paths)
        reporter = SarifReporter()
    except Exception as e:
        print(f"⚠️  Failed to initialize analyzers: {e}", file=sys.stderr)
        sarif = _empty_sarif()
        output_path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
        return 0

    results = []
    for f in bsl_files:
        p = Path(f)
        if not p.exists():
            print(f"  ⚠️  {f}: file not found, skipping")
            continue
        try:
            r = processor.check(p, level="quick")  # без BSL LS (нет Java)
            results.append(r)
        except Exception as e:
            print(f"  ⚠️  {f}: {e}")

    if results:
        sarif = reporter.convert_multiple(results)
    else:
        sarif = _empty_sarif()

    output_path.write_text(
        json.dumps(sarif, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_errors = sum(r.total_errors for r in results)
    total_warnings = sum(r.total_warnings for r in results)
    print(f"SARIF: {len(results)} files, {total_errors} errors, {total_warnings} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
