#!/usr/bin/env python3
"""
epf_builder.py — Создание и сборка внешних обработок 1С (.epf) без платформы 1С.

Использует Python-пакет `v8unpack` (saby) для распаковки/сборки бинарных
контейнеров 1С формата CF/CFE/EPF (сигнатура 0x7FFFFFFF).

Возможности:
    - build_epf(src_dir, output_epf) — собрать .epf из каталога исходников
    - extract_epf(epf_path, dest_dir) — распаковать .epf в каталог
    - create_epf_from_template(template_epf, name, synonym, bsl_code, output_epf)
        — создать новую обработку на базе шаблона
    - replace_form_module(src_dir, form_name, bsl_code)
        — заменить модуль формы в распакованных исходниках
    - rename_data_processor(src_dir, new_name, new_synonym)
        — переименовать обработку в исходниках

Формат исходников v8unpack (после распаковки):
    src/
    ├── ExternalDataProcessor.json       — метаданные обработки
    └── Form/
        └── <ИмяФормы>/
            ├── Form.json                — метаданные формы
            ├── Form.id.json             — UUID формы
            ├── Form.elem.json           — элементы формы
            └── Form.obj.bsl             — модуль формы (BSL-код)

Требования:
    pip install v8unpack   (saby v8unpack ≥ 1.2.6)

Автор: Bratuha Dev Team
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

# Python-интерпретатор с установленным v8unpack
_PYTHON = os.environ.get("EPF_PYTHON", sys.executable)


def _run_v8unpack(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Запустить v8unpack как модуль Python.

    Returns:
        (returncode, stdout, stderr)
    """
    cmd = [_PYTHON, "-m", "v8unpack"] + args
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def extract_epf(epf_path: str | Path, dest_dir: str | Path) -> dict:
    """Распаковать .epf файл в каталог исходников.

    Args:
        epf_path: путь к .epf файлу
        dest_dir: куда распаковывать (создаётся автоматически)

    Returns:
        dict с ключами:
            - ok: bool
            - src_dir: Path
            - files: list[Path] — список файлов исходников
            - error: str (если ok=False)
    """
    epf_path = Path(epf_path)
    dest_dir = Path(dest_dir)
    temp_dir = dest_dir.parent / f"{dest_dir.name}__temp"

    if not epf_path.exists():
        return {"ok": False, "error": f"Файл не найден: {epf_path}"}

    # Очистка
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    code, out, err = _run_v8unpack(["-E", str(epf_path), str(dest_dir), "--temp", str(temp_dir)])
    if code != 0:
        return {"ok": False, "error": f"v8unpack -E failed: {err or out}"}

    # Чистим temp
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    files = sorted(p for p in dest_dir.rglob("*") if p.is_file())
    return {"ok": True, "src_dir": dest_dir, "files": files}


def build_epf(src_dir: str | Path, output_epf: str | Path) -> dict:
    """Собрать .epf файл из каталога исходников.

    Args:
        src_dir: каталог с распакованными исходниками
                 (должен содержать ExternalDataProcessor.json)
        output_epf: путь к выходному .epf файлу

    Returns:
        dict с ключами:
            - ok: bool
            - epf_path: Path
            - size_bytes: int
            - files_included: int
            - error: str (если ok=False)
    """
    src_dir = Path(src_dir)
    output_epf = Path(output_epf)

    if not src_dir.exists():
        return {"ok": False, "error": f"Каталог исходников не найден: {src_dir}"}

    ext_proc_json = src_dir / "ExternalDataProcessor.json"
    if not ext_proc_json.exists():
        return {"ok": False, "error": f"В каталоге нет ExternalDataProcessor.json: {src_dir}"}

    # Подготовка temp и выходного пути
    temp_dir = output_epf.parent / f"{output_epf.stem}__temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    output_epf.parent.mkdir(parents=True, exist_ok=True)
    if output_epf.exists():
        output_epf.unlink()

    code, out, err = _run_v8unpack(["-B", str(src_dir), str(output_epf), "--temp", str(temp_dir)])
    if code != 0:
        return {"ok": False, "error": f"v8unpack -B failed: {err or out}"}

    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    if not output_epf.exists():
        return {"ok": False, "error": f"Выходной файл не создан: {output_epf}"}

    # Проверяем сигнатуру 1С-контейнера
    with open(output_epf, "rb") as f:
        sig = f.read(4)
    if sig != b"\xff\xff\xff\x7f":
        return {"ok": False, "error": f"Неверная сигнатура файла: {sig.hex()} (ожидалась ffffff7f)"}

    files_included = sum(1 for _ in src_dir.rglob("*") if _.is_file())
    return {
        "ok": True,
        "epf_path": output_epf,
        "size_bytes": output_epf.stat().st_size,
        "files_included": files_included,
    }


def _replace_in_tree(obj, replacements: dict):
    """Рекурсивно заменить значения в JSON-дереве.

    replacements: {old_value: new_value} — для строковых узлов,
                  {old_uuid: new_uuid} — для UUID-строк.
    Применяет replacements ко всем строковым узлам дерева.
    """
    if isinstance(obj, str):
        # Прямое совпадение
        if obj in replacements:
            return replacements[obj]
        # Совпадение с обёрнутыми кавычками 1С: "\"OldName\""
        if obj.startswith('"') and obj.endswith('"'):
            inner = obj[1:-1]
            if inner in replacements:
                return f'"{replacements[inner]}"'
        return obj
    if isinstance(obj, list):
        return [_replace_in_tree(x, replacements) for x in obj]
    if isinstance(obj, dict):
        return {k: _replace_in_tree(v, replacements) for k, v in obj.items()}
    return obj


def rename_data_processor(src_dir: str | Path, new_name: str, new_synonym: str | None = None) -> dict:
    """Переименовать обработку в распакованных исходниках.

    Обновляет ExternalDataProcessor.json:
        - name → new_name
        - name2.ru → new_synonym (если задан, иначе = new_name)
        - uuid (новый, чтобы 1С не ругалась на дубликат)
        - Все вхождения старого имени и UUID в header/copyinfo

    Args:
        src_dir: каталог с исходниками
        new_name: новое имя обработки (латиница/кириллица, без пробелов)
        new_synonym: новый синоним (если None — используется new_name)

    Returns:
        dict с ключами: ok, old_name, new_name, new_uuid, error
    """
    src_dir = Path(src_dir)
    json_path = src_dir / "ExternalDataProcessor.json"

    if not json_path.exists():
        return {"ok": False, "error": f"Не найден {json_path}"}

    if not re.match(r"^[A-Za-zА-Яа-яёЁ0-9_]+$", new_name):
        return {"ok": False, "error": f"Недопустимое имя обработки: {new_name}"}

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    old_name = data.get("name", "")
    old_uuid = data.get("uuid", "")
    old_synonym = data.get("name2", {}).get("ru", "")
    new_uuid = str(uuid.uuid4())
    new_synonym_final = new_synonym or new_name

    # Карта замен: что → на что (применяется ко всем строковым узлам дерева)
    replacements = {}
    if old_name and old_name != new_name:
        replacements[old_name] = new_name
    if old_uuid and old_uuid != new_uuid:
        replacements[old_uuid] = new_uuid
    if old_synonym and old_synonym != new_synonym_final:
        replacements[old_synonym] = new_synonym_final

    data["name"] = new_name
    data["uuid"] = new_uuid
    data.setdefault("name2", {})["ru"] = new_synonym_final

    # Рекурсивно заменяем в header, copyinfo, version, и любом другом вложенном дереве
    if replacements:
        for key in ("header", "copyinfo", "version"):
            if key in data:
                data[key] = _replace_in_tree(data[key], replacements)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "old_name": old_name,
        "new_name": new_name,
        "old_uuid": old_uuid,
        "new_uuid": new_uuid,
        "old_synonym": old_synonym,
        "new_synonym": new_synonym_final,
    }


def replace_form_module(src_dir: str | Path, form_name: str, bsl_code: str) -> dict:
    """Заменить модуль указанной формы.

    Args:
        src_dir: каталог с исходниками
        form_name: имя формы (имя папки в Form/)
        bsl_code: новый BSL-код модуля

    Returns:
        dict: ok, bsl_path, lines, error
    """
    src_dir = Path(src_dir)
    bsl_path = src_dir / "Form" / form_name / "Form.obj.bsl"

    if not bsl_path.parent.exists():
        return {"ok": False, "error": f"Форма не найдена: {bsl_path.parent}"}

    bsl_path.write_text(bsl_code, encoding="utf-8")
    lines = bsl_code.count("\n") + (0 if bsl_code.endswith("\n") else 1)
    return {"ok": True, "bsl_path": bsl_path, "lines": lines}


def create_epf_from_template(
    template_epf: str | Path,
    name: str,
    synonym: str | None,
    bsl_code: str,
    output_epf: str | Path,
    form_name: str = "Форма",
    work_dir: str | Path | None = None,
) -> dict:
    """Создать новую обработку на базе шаблона.

    Workflow:
        1. Распаковать template_epf → work_dir/src
        2. Переименовать обработку (name, synonym, новый UUID)
        3. Заменить модуль формы на bsl_code
        4. Собрать в output_epf

    Args:
        template_epf: путь к .epf файлу-шаблону
        name: имя новой обработки (без пробелов, латиница/кириллица)
        synonym: синоним (если None — = name)
        bsl_code: код модуля формы
        output_epf: куда сохранить результат
        form_name: имя формы в шаблоне (по умолчанию "Форма")
        work_dir: временный каталог (по умолчанию /tmp/epf_<uuid>)

    Returns:
        dict: ok, epf_path, size_bytes, error
    """
    template_epf = Path(template_epf)
    output_epf = Path(output_epf)

    if work_dir is None:
        work_dir = Path(f"/tmp/epf_build_{uuid.uuid4().hex[:8]}")
    work_dir = Path(work_dir)
    src_dir = work_dir / "src"

    # 1. Распаковка шаблона
    res = extract_epf(template_epf, src_dir)
    if not res["ok"]:
        return res

    # 2. Переименование
    res = rename_data_processor(src_dir, name, synonym)
    if not res["ok"]:
        return res

    # 3. Замена модуля формы
    res = replace_form_module(src_dir, form_name, bsl_code)
    if not res["ok"]:
        return res

    # 4. Сборка
    res = build_epf(src_dir, output_epf)
    if not res["ok"]:
        return res

    # Чистим temp
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    return {
        "ok": True,
        "epf_path": output_epf,
        "size_bytes": res["size_bytes"],
        "files_included": res["files_included"],
    }


def verify_epf(epf_path: str | Path) -> dict:
    """Проверить .epf файл: сигнатура + round-trip extraction.

    Args:
        epf_path: путь к .epf

    Returns:
        dict: ok, signature, size_bytes, files_extracted, error
    """
    epf_path = Path(epf_path)
    if not epf_path.exists():
        return {"ok": False, "error": f"Файл не найден: {epf_path}"}

    with open(epf_path, "rb") as f:
        sig = f.read(4)

    if sig != b"\xff\xff\xff\x7f":
        return {"ok": False, "error": f"Неверная сигнатура: {sig.hex()}"}

    # Round-trip extraction test
    work_dir = Path(f"/tmp/epf_verify_{uuid.uuid4().hex[:8]}")
    res = extract_epf(epf_path, work_dir / "src")
    if not res["ok"]:
        return res

    files_count = len(res["files"])
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    return {
        "ok": True,
        "signature": sig.hex(),
        "size_bytes": epf_path.stat().st_size,
        "files_extracted": files_count,
    }


# ──────────────────────────────────────────────────────────────────
# CLI: python epf_builder.py extract|build|verify|create <args>
# ──────────────────────────────────────────────────────────────────
def _cli():
    if len(sys.argv) < 2:
        print("Usage: epf_builder.py <extract|build|verify|create> ...")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "extract":
        if len(sys.argv) != 4:
            print("Usage: epf_builder.py extract <input.epf> <dest_dir>")
            sys.exit(1)
        res = extract_epf(sys.argv[2], sys.argv[3])
    elif cmd == "build":
        if len(sys.argv) != 4:
            print("Usage: epf_builder.py build <src_dir> <output.epf>")
            sys.exit(1)
        res = build_epf(sys.argv[2], sys.argv[3])
    elif cmd == "verify":
        if len(sys.argv) != 3:
            print("Usage: epf_builder.py verify <file.epf>")
            sys.exit(1)
        res = verify_epf(sys.argv[2])
    elif cmd == "create":
        if len(sys.argv) < 5:
            print("Usage: epf_builder.py create <template.epf> <name> <output.epf> [--bsl file.bsl] [--synonym TEXT]")
            sys.exit(1)
        template = sys.argv[2]
        name = sys.argv[3]
        output = sys.argv[4]
        bsl_code = ""
        synonym = None
        for i in range(5, len(sys.argv)):
            if sys.argv[i] == "--bsl" and i + 1 < len(sys.argv):
                bsl_code = Path(sys.argv[i + 1]).read_text(encoding="utf-8")
                i += 1
            elif sys.argv[i] == "--synonym" and i + 1 < len(sys.argv):
                synonym = sys.argv[i + 1]
                i += 1
        if not bsl_code:
            # Минимальный пустой модуль
            bsl_code = f"// {name} — модуль формы\n\n#Область ПрограммныйИнтерфейс\n\n#КонецОбласти\n\n#Область СлужебныеПроцедурыИФункции\n\n#КонецОбласти\n"
        res = create_epf_from_template(template, name, synonym, bsl_code, output)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    _cli()
