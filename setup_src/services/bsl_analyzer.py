"""
Анализатор .bsl файлов через BSL Language Server.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set


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
    def diagnostic_set(self) -> Set[str]:
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

    def __init__(self, binary_path: Path, config_path: Path):
        self._binary = binary_path
        self._config = config_path
        self._baseline: Optional[Set[str]] = None

    def analyze(self, source: Path, output_dir: Optional[Path] = None) -> AnalysisResult:
        """Анализ файла или директории."""
        import tempfile
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp())
        else:
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
        """Сохранить baseline для последующего diff."""
        result = self.analyze(source)
        self._baseline = result.diagnostic_set
        return result

    def diff(self, source: Path) -> DiffResult:
        """Показать только новые диагностики."""
        if self._baseline is None:
            raise RuntimeError("Нет baseline. Сначала вызовите save_baseline().")

        result = self.analyze(source)
        current_set = result.diagnostic_set

        new_keys = current_set - self._baseline
        fixed_keys = self._baseline - current_set

        self._baseline = current_set  # обновляем baseline

        return DiffResult(
            new=[d for d in result.diagnostics if d["key"] in new_keys],
            fixed=[{"key": k} for k in sorted(fixed_keys)],
            current=result,
        )

    @property
    def has_baseline(self) -> bool:
        return self._baseline is not None
