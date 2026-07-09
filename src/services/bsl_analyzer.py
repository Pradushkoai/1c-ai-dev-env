"""
Анализатор .bsl файлов через BSL Language Server.

P2.2: добавлена изоляция BSL LS — subprocess с timeout, retry с backoff,
fallback на check_1c_standards (62 правил) при недоступности BSL LS.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# P2.2: настройки изоляции BSL LS
BSL_LS_TIMEOUT = 15  # секунд (увеличено с 10)
BSL_LS_MAX_RETRIES = 3
BSL_LS_RETRY_DELAYS = [1.0, 2.0, 4.0]  # exponential backoff (секунды)


@dataclass
class Diagnostic:
    """Одна диагностика BSL LS."""

    code: str
    line: int
    message: str
    severity: str = ""

    @property
    def key(self) -> str:
        return f"{self.code}|{self.line}|{self.message[:150]}"


@dataclass
class AnalysisResult:
    """Результат анализа файла/директории."""

    total: int = 0
    by_code: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[Any] = field(default_factory=list)

    @property
    def diagnostic_set(self) -> set[str]:
        return {d["key"] for d in self.diagnostics}

    @classmethod
    def from_json(cls, json_path: Path) -> AnalysisResult:
        if not json_path.exists():
            return cls()
        with open(json_path, "rb") as f:
            data = json.loads(f.read().decode("utf-8"))
        result = cls()
        for file_info in data.get("fileinfos", []):
            for d in file_info.get("diagnostics", []):
                diag = Diagnostic(
                    code=d.get("code", "?"),
                    line=d.get("range", {}).get("start", {}).get("line", 0),
                    message=d.get("message", "")[:150],
                    severity=d.get("severity", ""),
                )
                result.diagnostics.append(
                    {"key": diag.key, "code": diag.code, "line": diag.line, "message": diag.message}
                )
                result.total += 1
                result.by_code[diag.code] = result.by_code.get(diag.code, 0) + 1
        return result


@dataclass
class DiffResult:
    """Результат diff анализа."""

    new: list[Any] = field(default_factory=list)
    fixed: list[Any] = field(default_factory=list)
    current: AnalysisResult = field(default_factory=AnalysisResult)


class BSLAnalyzer:
    """Анализ .bsl файлов через BSL Language Server.

    F1.2 (2026-07-05): Реализует ServiceProtocol (name, initialize, is_available).
    """

    BASELINE_FILE = Path("runtime/bsl-baseline.json")

    # F1.2: ServiceProtocol implementation
    @property
    def name(self) -> str:
        return "bsl_analyzer"

    def initialize(self) -> None:
        """F1.2: Проверка что BSL LS binary существует."""
        if not self._binary.exists():
            raise FileNotFoundError(f"BSL LS не найден: {self._binary}")

    def is_available(self) -> bool:
        """F1.2: BSL LS доступен если binary существует."""
        return self._binary.exists()

    def __init__(self, binary_path: Path, config_path: Path, project_root: Path | None = None):
        self._binary = binary_path
        self._config = config_path
        self._project_root = project_root or Path.cwd()
        self._baseline_path = self._project_root / self.BASELINE_FILE
        self._baseline: set[str] | None = None

    def analyze(self, source: Path, output_dir: Path | None = None) -> AnalysisResult:
        """Анализ файла или директории."""
        import tempfile

        if output_dir is None:
            # Используем контекстный менеджер для автоочистки
            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)
                return self._run_analysis(source, output_dir)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            return self._run_analysis(source, output_dir)

    def _run_analysis(self, source: Path, output_dir: Path) -> AnalysisResult:
        """Внутренний метод — запуск BSL LS с retry и timeout (P2.2)."""
        # Очищаем output_dir от старых отчётов (защита от устаревшего bsl-json.json,
        # если новый запуск BSL LS упадёт и не создаст файл)
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self._binary),
            "-c",
            str(self._config),
            "analyze",
            "-s",
            str(source),
            "-r",
            "json",
            "-o",
            str(output_dir),
            "-q",
        ]

        # P2.2: retry с exponential backoff
        last_error: Exception | None = None
        for attempt in range(BSL_LS_MAX_RETRIES):
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=BSL_LS_TIMEOUT,
                    check=True,
                )
                json_file = output_dir / "bsl-json.json"
                return AnalysisResult.from_json(json_file)
            except subprocess.TimeoutExpired:
                last_error = subprocess.TimeoutExpired(cmd, BSL_LS_TIMEOUT)
                logger.warning(
                    "BSL LS timeout (attempt %d/%d, %ds)",
                    attempt + 1,
                    BSL_LS_MAX_RETRIES,
                    BSL_LS_TIMEOUT,
                )
                if attempt < BSL_LS_MAX_RETRIES - 1:
                    delay = BSL_LS_RETRY_DELAYS[min(attempt, len(BSL_LS_RETRY_DELAYS) - 1)]
                    logger.info("Retrying in %s seconds...", delay)
                    time.sleep(delay)
            except subprocess.CalledProcessError as e:
                last_error = e
                logger.warning(
                    "BSL LS failed (attempt %d/%d): returncode=%d",
                    attempt + 1,
                    BSL_LS_MAX_RETRIES,
                    e.returncode,
                )
                if attempt < BSL_LS_MAX_RETRIES - 1:
                    delay = BSL_LS_RETRY_DELAYS[min(attempt, len(BSL_LS_RETRY_DELAYS) - 1)]
                    time.sleep(delay)

        # Все попытки исчерпаны — поднимаем исключение
        raise RuntimeError(f"BSL LS failed after {BSL_LS_MAX_RETRIES} attempts: {last_error}") from last_error

    def save_baseline(self, source: Path) -> AnalysisResult:
        """Сохранить baseline (в память + в файл)."""
        result = self.analyze(source)
        self._baseline = result.diagnostic_set
        self._save_baseline_to_file()
        return result

    def diff(self, source: Path) -> DiffResult:
        """Показать только новые диагностики."""
        # Загружаем baseline из файла если в памяти пусто
        if self._baseline is None:
            self._load_baseline_from_file()

        if self._baseline is None:
            raise RuntimeError("Нет baseline. Сначала вызовите: python3 -m src.cli bsl baseline <path>")

        result = self.analyze(source)
        current_set = result.diagnostic_set

        new_keys = current_set - self._baseline
        fixed_keys = self._baseline - current_set

        # Обновляем baseline (в памяти + в файле)
        self._baseline = current_set
        self._save_baseline_to_file()

        return DiffResult(
            new=[d for d in result.diagnostics if d["key"] in new_keys],
            fixed=[{"key": k} for k in sorted(fixed_keys)],
            current=result,
        )

    @property
    def has_baseline(self) -> bool:
        if self._baseline is not None:
            return True
        return self._baseline_path.exists()

    def _save_baseline_to_file(self) -> None:
        """Сериализовать baseline в JSON файл."""
        import json

        if self._baseline is not None:
            self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._baseline_path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._baseline), f, ensure_ascii=False)

    def _load_baseline_from_file(self) -> None:
        """Загрузить baseline из JSON файла."""
        if self._baseline_path.exists():
            with open(self._baseline_path, encoding="utf-8") as f:
                self._baseline = set(json.load(f))


# ============================================================================
# P2.2: bsl_ls_with_fallback декоратор
# ============================================================================


def bsl_ls_with_fallback(
    fallback_func: Callable[..., Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор: запуск BSL LS с fallback на check_1c_standards.

    Если BSL LS недоступен (timeout, exception) — вызывает fallback_func
    (обычно check_1c_standards с 62 правилами).

    Args:
        fallback_func: Функция для fallback (принимает те же аргументы).
            Если None — fallback возвращает пустой AnalysisResult.

    Usage:
        @bsl_ls_with_fallback(fallback=check_standards)
        def analyze_bsl(file_path: Path) -> AnalysisResult:
            analyzer = BSLAnalyzer(...)
            return analyzer.analyze(file_path)
    """
    import functools

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.warning(
                    "BSL LS unavailable, using fallback: %s",
                    type(e).__name__,
                )
                if fallback_func is not None:
                    return fallback_func(*args, **kwargs)
                # Если fallback не задан — возвращаем пустой результат
                return AnalysisResult()

        return wrapper

    return decorator
