"""
Анализатор .bsl файлов через BSL Language Server.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


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
    by_code: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

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
                result.diagnostics.append({"key": diag.key, "code": diag.code, "line": diag.line, "message": diag.message})
                result.total += 1
                result.by_code[diag.code] = result.by_code.get(diag.code, 0) + 1
        return result


@dataclass
class DiffResult:
    """Результат diff анализа."""
    new: list = field(default_factory=list)
    fixed: list = field(default_factory=list)
    current: AnalysisResult = field(default_factory=AnalysisResult)


class BSLAnalyzer:
    """Анализ .bsl файлов через BSL Language Server."""

    BASELINE_FILE = Path("runtime/bsl-baseline.json")

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
        """Внутренний метод — запуск BSL LS."""
        # Очищаем output_dir от старых отчётов (защита от устаревшего bsl-json.json,
        # если новый запуск BSL LS упадёт и не создаст файл)
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self._binary),
            "-c", str(self._config),
            "analyze",
            "-s", str(source),
            "-r", "json",
            "-o", str(output_dir),
            "-q",
        ]
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)

        json_file = output_dir / "bsl-json.json"
        return AnalysisResult.from_json(json_file)

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
                json.dump(sorted(list(self._baseline)), f, ensure_ascii=False)

    def _load_baseline_from_file(self) -> None:
        """Загрузить baseline из JSON файла."""
        import json
        if self._baseline_path.exists():
            with open(self._baseline_path, encoding="utf-8") as f:
                self._baseline = set(json.load(f))
