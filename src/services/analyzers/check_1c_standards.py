#!/usr/bin/env python3
"""
Проверка .bsl файлов на соответствие стандартам разработки 1С.

Основано на:
- ITS standard 456 «Тексты модулей» (https://its.1c.ru/db/v8std#content:456:hdoc)
- ITS standard 454 «Правила образования имен переменных»
- ITS standard 455 «Структура модуля»
- ai_rules_1c/content/rules/anti-patterns.md

Этап 2.1: декомпозиция god-файла. Логика перенесена в пакет standards/.
Этот файл — facade: ALL_RULES + StandardsChecker + format_violations.

Правила, которые проверяет BSL Language Server (Typo, длина строк, отступы),
здесь не дублируются. Этот скрипт фокусируется на стилистических правилах,
которые BSL LS не покрывает или покрывает слабо.

Использование:
    python3 check_1c_standards.py <path>              # проверить файл/директорию
    python3 check_1c_standards.py <path> --format json # JSON вывод для CI
    python3 check_1c_standards.py <path> --severity error  # только errors

Exit codes:
    0 — нет violations уровня error
    1 — есть violations уровня error
    2 — ошибка использования
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .standards import ALL_RULES, Violation  # noqa: F401
from .standards import *  # noqa: F401, F403 — re-export rule_* для обратной совместимости

# Все 56 правил из 5 модулей (style, architecture, queries, client_server, misc)


# ============================================================================
# CHECKER
# ============================================================================


class StandardsChecker:
    """Проверка .bsl файлов на соответствие стандартам 1С."""

    def __init__(self, rules: list | None = None):
        self.rules = rules or ALL_RULES

    def check_file(self, file_path: Path) -> list[Violation]:
        """Проверить один .bsl файл."""
        try:
            # Пробуем UTF-8, если не получится — windows-1251 (часто в 1С)
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="cp1251")
        except OSError as e:
            return [
                Violation(
                    file=str(file_path),
                    line=0,
                    col=0,
                    rule_id="read-error",
                    severity="error",
                    message=f"Не удалось прочитать файл: {e}",
                )
            ]

        lines = content.splitlines()
        violations = []
        for rule_fn in self.rules:
            violations.extend(rule_fn(lines, file_path))
        return violations

    def check_path(self, path: Path) -> list[Violation]:
        """Проверить .bsl файл или директорию."""
        if path.is_file():
            return self.check_file(path)

        violations = []
        for bsl_file in path.rglob("*.bsl"):
            violations.extend(self.check_file(bsl_file))
        return violations


# ============================================================================
# ФОРМАТИРОВАНИЕ
# ============================================================================


def format_violations(violations: list[Violation], output_format: str = "text") -> str:
    """Форматировать вывод."""
    if output_format == "json":
        return json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2)

    if not violations:
        return "✅ Нарушений не найдено."

    # Группируем по файлам
    by_file: dict[str, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    lines = []
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    lines.append(f"Найдено: {errors} errors, {warnings} warnings в {len(by_file)} файлах")
    lines.append("")

    for file_path in sorted(by_file.keys()):
        lines.append(f"📋 {file_path}")
        for v in by_file[file_path]:
            lines.append(v.format_text())
        lines.append("")

    return "\n".join(lines)


# CLI вынесен в scripts/check_1c_standards.py (Этап 1.2, Группа 1f).
