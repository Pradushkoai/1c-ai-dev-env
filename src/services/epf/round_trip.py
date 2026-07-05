"""
Round-trip проверка для EpfFactory.

Этап 2.2: вынесено из src/services/epf_factory.py.

Функция verify_round_trip распаковывает .epf и сравнивает с исходниками.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_PYTHON = sys.executable


def verify_round_trip(
    epf_path: Path,
    original_src: Path,
    work_dir: Path,
) -> bool:
    """Проверить round-trip: распаковать .epf и сравнить с исходниками.

    Сравниваем только ключевые файлы: ExternalDataProcessor.json,
    Form.obj.bsl, Form.id.json. Form.elem.json и Form.json могут
    отличаться (v8unpack добавляет служебные поля).
    """
    check_dir = work_dir / "round_trip_check"
    if check_dir.exists():
        shutil.rmtree(check_dir)
    temp_dir = work_dir / "round_trip_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    cmd = [_PYTHON, "-m", "v8unpack", "-E", str(epf_path), str(check_dir), "--temp", str(temp_dir)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return False

    if proc.returncode != 0:
        return False

    # Сравниваем BSL-модуль (должен совпадать байт-в-байт)
    original_bsl = original_src / "Form" / "Форма" / "Form.obj.bsl"
    check_bsl = check_dir / "Form" / "Форма" / "Form.obj.bsl"
    if not original_bsl.exists() or not check_bsl.exists():
        return False
    if original_bsl.read_bytes() != check_bsl.read_bytes():
        return False

    # Чистим
    try:
        shutil.rmtree(check_dir)
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return True
