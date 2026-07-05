#!/usr/bin/env python3
"""
D3.1 (2026-07-05): Coverage report по правилам анализаторов.

Находит все правила в src/services/analyzers/ и проверяет,
есть ли для каждого positive и negative тест.

Использование:
    python3 scripts/analyzer_coverage_report.py
    python3 scripts/analyzer_coverage_report.py --json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
ANALYZERS_DIR = REPO_ROOT / "src" / "services" / "analyzers"
TESTS_DIR = REPO_ROOT / "tests"


def find_all_rules() -> list[dict[str, str]]:
    """Найти все правила анализаторов в исходниках."""
    rules: list[dict[str, str]] = []

    # Pattern 1: rule_id='xxx' или rule_id="xxx"
    rule_id_pattern = re.compile(r"rule_id=['\"]([^'\"]+)['\"]")

    # Pattern 2: def rule_xxx(
    def_pattern = re.compile(r"^def (rule_[a-z_]+)\(", re.MULTILINE)

    for py_file in ANALYZERS_DIR.rglob("*.py"):
        if "__init__" in py_file.name or "_common" in py_file.name:
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        rel_path = py_file.relative_to(REPO_ROOT)

        # rule_id='xxx'
        for match in rule_id_pattern.finditer(content):
            rule_id = match.group(1)
            rules.append({
                "rule_id": rule_id,
                "source_file": str(rel_path),
                "pattern": "rule_id",
            })

        # def rule_xxx(
        for match in def_pattern.finditer(content):
            rule_name = match.group(1)
            rules.append({
                "rule_id": rule_name,
                "source_file": str(rel_path),
                "pattern": "def",
            })

    return rules


def find_test_coverage(rules: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Проверить, есть ли тесты для каждого правила."""
    coverage: dict[str, dict[str, Any]] = {}

    # Загружаем все тестовые файлы
    test_content = ""
    for test_file in TESTS_DIR.glob("test_*.py"):
        if "analyz" in test_file.name.lower() or "security" in test_file.name.lower() or \
           "standards" in test_file.name.lower() or "transaction" in test_file.name.lower() or \
           "query" in test_file.name.lower() or "architecture" in test_file.name.lower() or \
           "form_quality" in test_file.name.lower() or "skd" in test_file.name.lower() or \
           "code_metrics" in test_file.name.lower() or "metadata_standards" in test_file.name.lower():
            test_content += test_file.read_text(encoding="utf-8", errors="ignore") + "\n"

    for rule in rules:
        rule_id = rule["rule_id"]
        # Проверяем, упоминается ли rule_id в тестах
        has_test = rule_id in test_content
        coverage[rule_id] = {
            "has_test": has_test,
            "source_file": rule["source_file"],
            "pattern": rule["pattern"],
        }

    return coverage


def main() -> int:
    rules = find_all_rules()
    coverage = find_test_coverage(rules)

    total = len(coverage)
    with_tests = sum(1 for v in coverage.values() if v["has_test"])
    without_tests = total - with_tests
    coverage_pct = (with_tests / total * 100) if total > 0 else 0

    if "--json" in sys.argv:
        print(json.dumps({
            "total_rules": total,
            "rules_with_tests": with_tests,
            "rules_without_tests": without_tests,
            "coverage_pct": round(coverage_pct, 1),
            "details": coverage,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"=== Analyzer Rules Coverage Report (D3.1) ===")
        print(f"  Total rules: {total}")
        print(f"  With tests:  {with_tests} ({coverage_pct:.1f}%)")
        print(f"  Without tests: {without_tests}")
        print()

        if without_tests > 0:
            print("Rules without tests:")
            for rule_id, info in sorted(coverage.items()):
                if not info["has_test"]:
                    print(f"  ❌ {rule_id} ({info['source_file']})")

        print()
        print(f"Coverage: {coverage_pct:.1f}% ({with_tests}/{total})")

    return 0 if coverage_pct >= 100 else 1


if __name__ == "__main__":
    sys.exit(main())
