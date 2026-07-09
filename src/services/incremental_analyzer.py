"""
D3.4 (2026-07-05): Incremental analysis для BSL.

Анализирует только изменённые функции (не весь файл), используя hash
каждой функции для определения изменилась ли она.

Использование:
    from src.services.incremental_analyzer import IncrementalAnalyzer

    inc = IncrementalAnalyzer()
    result = inc.analyze_changed(Path("module.bsl"), baseline_path)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = __import__("logging").getLogger(__name__)


@dataclass
class IncrementalResult:
    """D3.4: Результат incremental analysis."""
    total_functions: int = 0
    changed_functions: int = 0
    unchanged_functions: int = 0
    changed_function_names: list[str] = field(default_factory=list)
    analysis_skipped: bool = False
    baseline_updated: bool = False


class IncrementalAnalyzer:
    """
    D3.4: Incremental analyzer — анализирует только изменённые функции.

    Вместо повторного анализа всего файла, вычисляет hash каждой функции
    и сравнивает с baseline. Если функция не изменилась — пропускает анализ.
    """

    def __init__(self) -> None:
        self._baseline: dict[str, str] = {}  # function_name → content_hash

    def analyze_changed(
        self,
        bsl_path: Path | str,
        baseline_path: Path | str | None = None,
    ) -> IncrementalResult:
        """
        Определить какие функции изменились с момента последнего анализа.

        Args:
            bsl_path: Путь к .bsl файлу.
            baseline_path: Путь к baseline JSON (function hashes).

        Returns:
            IncrementalResult с информацией о изменённых функциях.
        """
        bsl_path = Path(bsl_path)
        if not bsl_path.exists():
            return IncrementalResult()

        # Загрузить baseline
        if baseline_path:
            baseline_path = Path(baseline_path)
            if baseline_path.exists():
                self._baseline = json.loads(
                    baseline_path.read_text(encoding="utf-8")
                )

        # Парсим функции из BSL
        current_functions = self._extract_functions(bsl_path)

        result = IncrementalResult(total_functions=len(current_functions))

        for func_name, func_hash in current_functions.items():
            baseline_hash = self._baseline.get(func_name, "")
            if baseline_hash != func_hash:
                result.changed_functions += 1
                result.changed_function_names.append(func_name)
            else:
                result.unchanged_functions += 1

        if result.changed_functions == 0 and result.total_functions > 0:
            result.analysis_skipped = True

        # Обновить baseline
        self._baseline = current_functions
        result.baseline_updated = True

        # Сохранить обновлённый baseline
        if baseline_path:
            baseline_path.write_text(
                json.dumps(self._baseline, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return result

    def _extract_functions(self, bsl_path: Path) -> dict[str, str]:
        """
        Извлечь все функции/процедуры из BSL файла.

        Returns:
            dict: {function_name: content_hash}
        """
        content = bsl_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        functions: dict[str, str] = {}
        current_name: str | None = None
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Начало процедуры/функции
            if stripped.startswith("Процедура ") or stripped.startswith("Функция "):
                if current_name:
                    func_text = "\n".join(current_lines)
                    functions[current_name] = hashlib.sha256(
                        func_text.encode("utf-8")
                    ).hexdigest()

                # Извлечь имя
                parts = stripped.split("(")
                if len(parts) > 0:
                    name_part = parts[0].replace("Процедура", "").replace("Функция", "").strip()
                    current_name = name_part
                    current_lines = [line]
                continue

            # Конец процедуры/функции
            if stripped in ("КонецПроцедуры", "КонецПроцедуры;", "КонецФункции", "КонецФункции;"):
                if current_name:
                    current_lines.append(line)
                    func_text = "\n".join(current_lines)
                    functions[current_name] = hashlib.sha256(
                        func_text.encode("utf-8")
                    ).hexdigest()
                    current_name = None
                    current_lines = []
                continue

            if current_name:
                current_lines.append(line)

        return functions
