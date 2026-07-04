"""
BSL-валидатор для EpfFactory.

Этап 2.2: вынесено из src/services/epf_factory.py.

Функция validate_bsl проверяет BSL-код через BSL Language Server (если установлен)
или возвращает базовую информацию о коде (количество строк).
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path

# BSL LS — статический анализатор (дублирует определение из epf_factory.py,
# чтобы избежать circular import)
BSL_LS_BINARY = os.environ.get(
    "BSL_LS_BINARY",
    str(Path.home() / ".local" / "bin" / "bsl-language-server"),
)


def validate_bsl(bsl_path: Path) -> dict:
    """Проверить BSL-файл через BSL Language Server.

    Returns:
        dict с ключами: ok, errors, warnings, infos, diagnostics
    """
    if not Path(BSL_LS_BINARY).exists():
        return {
            "ok": False,
            "error": f"BSL LS не найден: {BSL_LS_BINARY}",
            "errors": 0,
            "warnings": 0,
            "infos": 0,
        }

    # BSL LS требует каталог, не файл
    src_dir = bsl_path.parent
    out_dir = src_dir.parent / "bsl_ls_out"

    # Конфиг
    config_path = src_dir.parent / ".bsl-language-server.json"
    if not config_path.exists():
        config_path.write_text(
            '{"language": "ru", "diagnostics": {"computeDiagnostics": true}}',
            encoding="utf-8",
        )

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        BSL_LS_BINARY,
        "-c",
        str(config_path),
        "analyze",
        "-s",
        str(src_dir),
        "-r",
        "json",
        "-o",
        str(out_dir),
        "-q",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "BSL LS timeout", "errors": 0, "warnings": 0, "infos": 0}

    report_path = out_dir / "bsl-json.json"
    if not report_path.exists():
        return {"ok": False, "error": "BSL LS отчёт не создан", "errors": 0, "warnings": 0, "infos": 0}

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    errors = warnings = infos = 0
    all_diags = []
    for fi in report.get("fileinfos", []):
        for d in fi.get("diagnostics", []):
            sev = d.get("severity", "")
            if sev == "Error":
                errors += 1
            elif sev == "Warning":
                warnings += 1
            elif sev == "Information":
                infos += 1
            all_diags.append(
                {
                    "file": fi.get("path", ""),
                    "line": d.get("range", {}).get("start", {}).get("line", 0) + 1,
                    "code": d.get("code", ""),
                    "severity": sev,
                    "message": d.get("message", ""),
                }
            )

    # Чистим
    with contextlib.suppress(Exception):
        shutil.rmtree(out_dir)

    return {
        "ok": True,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "diagnostics": all_diags,
    }


# ────────────────────────────────────────────────────────────────
# Главный класс
# ────────────────────────────────────────────────────────────────

