#!/usr/bin/env python3
"""
pre-commit hook: предупреждает об импортах из scripts/ в src/.

Этап 1.3: документирование границы scripts/services.

Запрещает:
- importlib.util.spec_from_file_location в src/ (dynamic import скриптов)
- sys.path.insert(0, scripts_dir) в src/
- from scripts.X import ... в src/

Разрешает:
- importlib.util в src/services/bsl_analyzer.py (BSL LS subprocess — обосновано)
- importlib.util в src/services/analyzers/__init__.py (_load_script с fallback)
- importlib.util в src/services/task_processor.py (_load_script с fallback)
- sys.path.insert в tests/ (временно, пока перенесены не все скрипты)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Файлы, где importlib.util / sys.path.insert разрешён (имеют fallback на прямой импорт
# или импортируют скрипты, перенос которых отложен до этапов 2.x)
ALLOWED_IMPORTLIB_FILES = {
    "src/services/analyzers/__init__.py",
    "src/services/task_processor.py",
    "src/services/bsl_analyzer.py",  # BSL LS subprocess
    "src/services/github_releases.py",  # git subprocess
    "src/services/config_manager.py",  # improved_cf_adapter fallback (Этап 1.2-g7)
    # Этап 2.3 (перенос metadata_extractor/skd_parser/form_analyzer) — пока отложено:
    "src/mcpserver/handlers/inspect_data.py",  # skd_parser.trace_field
    "src/mcpserver/handlers/dsl_cfe.py",  # skd_parser.trace_field
    "src/mcpserver/handlers/structure.py",  # metadata_extractor/skd_parser/form_analyzer hints
    "src/cli_commands/inspect.py",  # metadata_extractor/skd_parser/form_analyzer
    "src/cli_commands/tools.py",  # skd_parser
}

# Паттерны запрещённых конструкций
FORBIDDEN_PATTERNS = [
    (
        r"importlib\.util\.spec_from_file_location",
        "dynamic import скриптов через importlib.util.spec_from_file_location. Используй прямой from src.services.* import",
    ),
    (
        r"sys\.path\.insert\s*\(\s*0\s*,.*scripts",
        "sys.path.insert для scripts/. Скрипты должны быть thin wrappers, импортирующими from src.services.*",
    ),
    (
        r"^\s*from\s+scripts\.",
        "импорт из scripts/ в src/. Бизнес-логика должна быть в src/services/",
    ),
    (
        r"^\s*import\s+scripts\.",
        "импорт scripts/ в src/. Бизнес-логика должна быть в src/services/",
    ),
]


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Проверить файл на запрещённые паттерны. Возвращает [(line, pattern, message)]."""
    if not filepath.exists():
        return []

    rel_path = str(filepath).replace("\\", "/")
    # Нормализуем путь для сравнения с ALLOWED_IMPORTLIB_FILES
    if rel_path.startswith("./"):
        rel_path = rel_path[2:]

    # Разрешённые файлы пропускаем
    if rel_path in ALLOWED_IMPORTLIB_FILES:
        return []

    violations: list[tuple[int, str, str]] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern, message in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                violations.append((line_num, line.strip(), message))
    return violations


def main() -> int:
    # Проверяем только изменённые .py файлы в src/
    src_dir = Path("src")
    if not src_dir.exists():
        print("src/ not found, skipping check")
        return 0

    all_violations: list[tuple[Path, int, str, str]] = []
    for py_file in src_dir.rglob("*.py"):
        violations = check_file(py_file)
        for line_num, line, message in violations:
            all_violations.append((py_file, line_num, line, message))

    if not all_violations:
        return 0

    print("❌ Найдены запрещённые импорты из scripts/ в src/:\n")
    for filepath, line_num, line, message in all_violations:
        print(f"  {filepath}:{line_num}")
        print(f"    {line}")
        print(f"    → {message}\n")

    print("См. AGENTS.md → 'Где жить новому коду (Этап 1.3)' для решения-дерева.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
