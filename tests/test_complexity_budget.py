"""
Тест для P0.3: Complexity Budget.

Проверяет, что количество функций с complexity ≥ D не превышает baseline.
CI gate основан на radon, этот тест — для локальной проверки.
"""

from __future__ import annotations

import subprocess
import sys


def test_complexity_budget_not_exceeded() -> None:
    """Количество функций с complexity ≥ D не должно превышать baseline (14)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", "src/", "-n", "D"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        # radon не установлен — skip
        import pytest

        pytest.skip("radon не установлен")

    # Подсчитываем функции/методы с complexity ≥ D
    violations = 0
    for line in result.stdout.splitlines():
        # Строки вида "    F 99:0 cmd_data - F (52)" или "    M 69:4 MetricsCollector.get_stats - C (13)"
        if line.startswith("    F ") or line.startswith("    M "):
            violations += 1

    BASELINE = 14  # см. docs/COMPLEXITY_BASELINE.md
    assert violations <= BASELINE, (
        f"Complexity budget violated: {violations} > {BASELINE} (baseline). "
        f"Новые функции с complexity ≥ D добавлены. "
        f"Отрефактори или обнови baseline в docs/COMPLEXITY_BASELINE.md"
    )


def test_no_extreme_complexity_functions() -> None:
    """Не должно быть функций с complexity ≥ F (26+) — критические."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", "src/", "-n", "F"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        import pytest

        pytest.skip("radon не установлен")

    # Считаем функции с complexity F
    f_count = 0
    for line in result.stdout.splitlines():
        if line.startswith("    F ") or line.startswith("    M "):
            # Извлекаем complexity grade из строки вида "    F 99:0 cmd_data - F (52)"
            parts = line.split(" - ")
            if len(parts) >= 2:
                grade_part = parts[-1].strip().split()[0]
                if grade_part == "F":
                    f_count += 1

    # Известные F-функции (технический долг)
    # cmd_data в cli.py — F (52)
    KNOWN_F_BASELINE = 1
    assert f_count <= KNOWN_F_BASELINE, (
        f"Новая функция с complexity F обнаружена! "
        f"F count: {f_count}, baseline: {KNOWN_F_BASELINE}. "
        f"Это критично — отрефактори обязательно."
    )
