"""
bsl.py — CLI команды для BSL анализа и валидации.

P2.1: вынесено из cli.py.
Команды: bsl analyze, bsl baseline, bsl diff, validate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.project import Project


def cmd_bsl_analyze(project: Project, args: argparse.Namespace) -> None:
    try:
        result = project.bsl_analyzer.analyze(Path(args.path))
        print(f"Всего: {result.total}")
        for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:15]:
            print(f"  {count:4d}  {code}")
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
        print("   Установите: bash install.sh")
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")


def cmd_bsl_baseline(project: Project, args: argparse.Namespace) -> None:
    try:
        result = project.bsl_analyzer.save_baseline(Path(args.path))
        print(f"✅ Baseline: {result.total} диагностик")
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def cmd_bsl_diff(project: Project, args: argparse.Namespace) -> None:
    try:
        diff = project.bsl_analyzer.diff(Path(args.path))
    except FileNotFoundError as e:
        print(f"❌ BSL Language Server не установлен: {e}")
        return
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    print(f"\n🆕 НОВЫЕ ({len(diff.new)}):")
    for d in diff.new[:20]:
        print(f"  + {d['code']} (строка {d['line']}): {d['message']}")
    print(f"\n✅ ИСПРАВЛЕННЫЕ ({len(diff.fixed)}):")
    for d in diff.fixed[:10]:
        print(f"  - {d['key']}")


def cmd_validate(project: Project, args: argparse.Namespace) -> None:
    checks = project.validate()
    all_ok = True
    for name, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {name}")
        if not ok:
            all_ok = False
    sys.exit(0 if all_ok else 1)
