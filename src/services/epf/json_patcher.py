"""
JSON-патчеры для v8unpack шаблонов ExternalDataProcessor и Form.

Этап 2.2: вынесено из src/services/epf_factory.py.

Функции:
- replace_in_tree: рекурсивная замена значений в JSON-дереве
- patch_ext_proc_json: замена name/synonym/uuid в ExternalDataProcessor.json
- patch_form_id_json: запись UUID формы в Form.id.json
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def replace_in_tree(obj: Any, replacements: dict) -> Any:
    """Рекурсивно заменить значения в JSON-дереве v8unpack.

    replacements: {old_value: new_value} — применяется ко всем строковым узлам.
    Также обрабатывает обёрнутые кавычки 1С: '"OldValue"' → '"NewValue"'.
    """
    if isinstance(obj, str):
        if obj in replacements:
            return replacements[obj]
        # Обёрнутые кавычки 1С: "\"OldName\""
        if obj.startswith('"') and obj.endswith('"'):
            inner = obj[1:-1]
            if inner in replacements:
                return f'"{replacements[inner]}"'
        return obj
    if isinstance(obj, list):
        return [replace_in_tree(x, replacements) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_in_tree(v, replacements) for k, v in obj.items()}
    return obj


# ────────────────────────────────────────────────────────────────
# BSL Language Server — статический анализ
# ────────────────────────────────────────────────────────────────



def patch_ext_proc_json(
    json_path: Path,
    old_name: str,
    new_name: str,
    old_synonym: str,
    new_synonym: str,
    old_proc_uuid: str,
    new_proc_uuid: str,
    old_form_uuid: str,
    new_form_uuid: str,
    old_file_uuid: str = "",
    new_file_uuid: str = "",
) -> None:
    """Заменить name, synonym, uuid в ExternalDataProcessor.json.

    Берёт шаблон (с именем и UUID из исходной обработки) и заменяет все
    вхождения старых значений на новые во всём дереве (header, copyinfo, version).

    v8unpack хранит в ExternalDataProcessor.json ссылки на:
      - proc_uuid (UUID обработки) — встречается в 5 местах
      - form_uuid (UUID формы) — встречается в 4 местах
      - file_uuid (UUID файла-контейнера) — встречается в 2 местах
    Все три нужно заменять, иначе v8unpack при распаковке не найдёт форму.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Если old_proc_uuid не задан — берём из шаблона
    if not old_proc_uuid:
        old_proc_uuid = data.get("uuid", "")
    # Если old_file_uuid не задан — берём из шаблона
    if not old_file_uuid:
        old_file_uuid = data.get("file_uuid", "")
    # Если new_file_uuid не задан — генерируем
    if not new_file_uuid:
        new_file_uuid = str(uuid.uuid4())

    replacements = {}
    if old_name and old_name != new_name:
        replacements[old_name] = new_name
    if old_proc_uuid and old_proc_uuid != new_proc_uuid:
        replacements[old_proc_uuid] = new_proc_uuid
    if old_form_uuid and old_form_uuid != new_form_uuid:
        replacements[old_form_uuid] = new_form_uuid
    if old_file_uuid and old_file_uuid != new_file_uuid:
        replacements[old_file_uuid] = new_file_uuid
    if old_synonym and old_synonym != new_synonym:
        replacements[old_synonym] = new_synonym

    # Подставляем на верхнем уровне
    data["name"] = new_name
    data["uuid"] = new_proc_uuid
    data["file_uuid"] = new_file_uuid
    data.setdefault("name2", {})["ru"] = new_synonym

    # Рекурсивно заменяем в header, copyinfo, version
    if replacements:
        for key in ("header", "copyinfo", "version"):
            if key in data:
                data[key] = replace_in_tree(data[key], replacements)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def patch_form_id_json(json_path: Path, new_uuid: str) -> None:
    """Записать UUID формы в Form.id.json."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    data["uuid"] = new_uuid
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
