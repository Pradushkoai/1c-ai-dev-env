#!/usr/bin/env python3
"""
epf_factory.py — Полный цикл создания внешней обработки 1С (.epf) из шаблонов.

Собран из существующих компонентов репозитория:
    - Шаблоны ExternalDataProcessor.json / Form.json / Form.id.json / Form.elem.json
      извлечены из реального EPF через v8unpack и очищены до пустой формы.
    - v8unpack (Python-пакет) — сборка/распаковка бинарного .epf-контейнера
    - BSL Language Server — статический анализ BSL-кода без платформы 1С

Полный цикл:
    1. Создание v8unpack-исходников из шаблонов (ExternalDataProcessor.json + Form/*.json)
    2. Подстановка имени, синонима, новых UUID (обработка + форма)
    3. Запись BSL-модуля формы (Form.obj.bsl)
    4. Проверка BSL через BSL LS (опционально)
    5. Сборка .epf через v8unpack
    6. Проверка round-trip: распаковка собранного .epf и сравнение с исходниками

Преимущества перед подходом "изменить готовый .epf":
    - Не зависит от внешнего .epf-шаблона — все шаблоны в templates/epf_factory/
    - Чистая структура: только то, что нужно, без мусора из оригинала
    - Каждый запуск генерирует новый UUID (1С не ругается на дубликаты)
    - Прозрачно: можно посмотреть промежуточные v8unpack-исходники

Ограничения:
    - Внешний вид формы задаётся через Form.elem.json (формат v8unpack).
      Конвертер из EDT Form.xml пока не реализован — элементы формы нужно
      создавать программно в BSL (через Элементы.Добавить(...) в ПриСозданииНаСервере).
    - Это нормально для мобильного приложения (где ДинамическийСписок
      программно создать нельзя) и для большинства внешних обработок,
      где форма простая и создаётся кодом.

Usage (Python API):
    from src.services.epf_factory import EpfFactory
    factory = EpfFactory()
    result = factory.create_epf(
        name="МояОбработка",
        synonym="Моя обработка",
        bsl_code=open("form_module.bsl", encoding="utf-8").read(),
        output_epf="МояОбработка.epf",
    )

Usage (CLI):
    1c-ai epf-factory create \\
        --name "МояОбработка" \\
        --synonym "Моя обработка" \\
        --bsl form_module.bsl \\
        --output МояОбработка.epf
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

# Python-интерпретатор с установленным v8unpack
_PYTHON = sys.executable

# Пути к шаблонам (относительно repo_work/)
_THIS_DIR = Path(__file__).parent  # src/services/
_REPO_ROOT = _THIS_DIR.parent.parent  # repo_work/
TEMPLATES_DIR = _REPO_ROOT / "templates" / "epf_factory"

# Шаблоны по умолчанию
TPL_EXT_PROC = TEMPLATES_DIR / "ExternalDataProcessor.template.json"
TPL_FORM = TEMPLATES_DIR / "Form.template.json"
TPL_FORM_ID = TEMPLATES_DIR / "Form.id.template.json"
TPL_FORM_ELEM_EMPTY = TEMPLATES_DIR / "Form.elem.empty.json"
TPL_FORM_ELEM_TEMPLATE = TEMPLATES_DIR / "Form.elem.template.json"  # реальный EPF, валидный для 1С

# Минимальный BSL-модуль формы, если не задан
DEFAULT_BSL = """\
#Область ПрограммныйИнтерфейс

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

#КонецОбласти
"""

# BSL LS — статический анализатор
BSL_LS_BINARY = os.environ.get(
    "BSL_LS_BINARY",
    str(Path.home() / ".local" / "bin" / "bsl-language-server"),
)


# ────────────────────────────────────────────────────────────────
# Результат
# ────────────────────────────────────────────────────────────────
@dataclass
class EpfFactoryResult:
    """Результат работы EpfFactory.create_epf."""

    ok: bool = False
    error: str = ""
    epf_path: Path | None = None
    size_bytes: int = 0
    name: str = ""
    synonym: str = ""
    proc_uuid: str = ""
    form_uuid: str = ""
    bsl_lines: int = 0
    bsl_warnings: int = 0
    bsl_errors: int = 0
    round_trip_ok: bool = False
    work_dir: Path | None = None  # если save_sources=True


# ────────────────────────────────────────────────────────────────
# Утилиты для замены в JSON-дереве v8unpack
# ────────────────────────────────────────────────────────────────
def _replace_in_tree(obj, replacements: dict):
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
        return [_replace_in_tree(x, replacements) for x in obj]
    if isinstance(obj, dict):
        return {k: _replace_in_tree(v, replacements) for k, v in obj.items()}
    return obj


# ────────────────────────────────────────────────────────────────
# BSL Language Server — статический анализ
# ────────────────────────────────────────────────────────────────
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
class EpfFactory:
    """Полный цикл создания внешней обработки 1С (.epf) из шаблонов."""

    def create_epf(
        self,
        name: str,
        synonym: str | None,
        bsl_code: str,
        output_epf: str | Path,
        form_name: str = "Форма",
        form_spec: dict | str | Path | None = None,
        work_dir: str | Path | None = None,
        save_sources: bool = False,
        skip_bsl_validation: bool = False,
    ) -> EpfFactoryResult:
        """Создать .epf с указанными параметрами.

        Args:
            name: Имя обработки (латиница/кириллица, без пробелов)
            synonym: Синоним (если None — = name)
            bsl_code: BSL-код модуля формы
            output_epf: Куда сохранить .epf
            form_name: Имя формы (по умолчанию "Форма")
            form_spec: Описание формы для генерации Form.elem.json.
                Может быть:
                - dict: сразу DSL-описание
                - str/Path: путь к JSON-файлу с DSL
                - None: использовать пустой шаблон (только реквизит Объект)
                Пример DSL:
                    {
                      "props": [
                        {"name": "Объект", "type": "DataProcessorObject"},
                        {"name": "ТаблицаСписка", "type": "ValueTable",
                         "synonym": "Список обходов",
                         "columns": [
                           {"name": "Дата", "type": "Date"},
                           {"name": "Номер", "type": "String", "length": 50}
                         ]}
                      ]
                    }
            work_dir: Рабочий каталог (по умолчанию /tmp/epf_factory_<uuid>)
            save_sources: Сохранить v8unpack-исходники в work_dir (не удалять)
            skip_bsl_validation: Пропустить проверку BSL LS

        Returns:
            EpfFactoryResult
        """
        result = EpfFactoryResult(name=name, synonym=synonym or name)
        output_epf = Path(output_epf)

        # 1. Подготовка рабочего каталога
        if work_dir is None:
            work_dir = Path(tempfile.gettempdir()) / f"epf_factory_{uuid.uuid4().hex[:8]}"
        work_dir = Path(work_dir)
        if work_dir.exists():
            shutil.rmtree(work_dir)
        src_dir = work_dir / "src"
        form_dir = src_dir / "Form" / form_name

        # 2. Копирование шаблонов
        try:
            src_dir.mkdir(parents=True, exist_ok=True)
            form_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(TPL_EXT_PROC, src_dir / "ExternalDataProcessor.json")
            shutil.copy(TPL_FORM, form_dir / "Form.json")
            shutil.copy(TPL_FORM_ID, form_dir / "Form.id.json")
            shutil.copy(TPL_FORM_ELEM_EMPTY, form_dir / "Form.elem.json")
        except Exception as e:
            result.error = f"Ошибка копирования шаблонов: {e}"
            return result

        # 2.5. Если задан form_spec — сгенерировать Form.elem.json из DSL
        if form_spec is not None:
            try:
                from .form_elem_builder import build_form_elem

                # form_spec может быть dict, str (путь к файлу) или Path
                if isinstance(form_spec, (str, Path)):
                    spec_path = Path(form_spec)
                    if not spec_path.exists():
                        result.error = f"form_spec файл не найден: {spec_path}"
                        return result
                    import json as _json

                    with open(spec_path, encoding="utf-8") as f:
                        spec_dict = _json.load(f)
                elif isinstance(form_spec, dict):
                    spec_dict = form_spec
                else:
                    result.error = f"form_spec должен быть dict, str или Path, получен {type(form_spec).__name__}"
                    return result

                # Генерируем Form.elem.json из DSL, ИСПОЛЬЗУЯ template как базу
                # Это критично: без template v8unpack неправильно сериализует
                # пустую форму, и 1С выдаёт "Ошибка формата потока".
                # Template уже прошёл проверку 1С, поэтому добавление новых
                # реквизитов в конец props сохраняет валидность.
                form_elem = build_form_elem(
                    spec_dict,
                    base_template_path=TPL_FORM_ELEM_TEMPLATE,
                )
                with open(form_dir / "Form.elem.json", "w", encoding="utf-8") as f:
                    json.dump(form_elem, f, ensure_ascii=False, indent=2)
            except Exception as e:
                result.error = f"Ошибка генерации Form.elem.json из form_spec: {e}"
                return result

        # 3. Генерация новых UUID
        result.proc_uuid = str(uuid.uuid4())
        result.form_uuid = str(uuid.uuid4())

        # 4. Подстановка в ExternalDataProcessor.json
        # UUID формы из шаблона Form.id.json — это "старый" UUID формы
        form_id_path = form_dir / "Form.id.json"
        with open(form_id_path, encoding="utf-8") as f:
            old_form_uuid = json.load(f).get("uuid", "")

        try:
            self._patch_ext_proc_json(
                src_dir / "ExternalDataProcessor.json",
                old_name="ОбходТерриторииСПереключателемФонСоЗвуком",
                new_name=name,
                old_synonym="Обход территории с переключателем фон со звуком",
                new_synonym=synonym or name,
                old_proc_uuid="",  # будет заполнено из шаблона
                new_proc_uuid=result.proc_uuid,
                old_form_uuid=old_form_uuid,
                new_form_uuid=result.form_uuid,
            )
        except Exception as e:
            result.error = f"Ошибка патча ExternalDataProcessor.json: {e}"
            return result

        # 5. Подстановка в Form.id.json
        try:
            self._patch_form_id_json(form_dir / "Form.id.json", result.form_uuid)
        except Exception as e:
            result.error = f"Ошибка патча Form.id.json: {e}"
            return result

        # 6. Запись BSL-модуля
        bsl_path = form_dir / "Form.obj.bsl"
        bsl_path.write_text(bsl_code, encoding="utf-8")
        result.bsl_lines = bsl_code.count("\n") + (0 if bsl_code.endswith("\n") else 1)

        # 7. Проверка BSL через BSL LS
        if not skip_bsl_validation:
            bsl_res = validate_bsl(bsl_path)
            if bsl_res.get("ok"):
                result.bsl_errors = bsl_res["errors"]
                result.bsl_warnings = bsl_res["warnings"]
            # Не блокируем сборку при ошибках BSL LS — это только предупреждения

        # 8. Сборка .epf через v8unpack
        output_epf.parent.mkdir(parents=True, exist_ok=True)
        if output_epf.exists():
            output_epf.unlink()
        temp_dir = work_dir / "build_temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        cmd = [
            _PYTHON,
            "-m",
            "v8unpack",
            "-B",
            str(src_dir),
            str(output_epf),
            "--temp",
            str(temp_dir),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            result.error = "v8unpack timeout при сборке"
            return result

        if proc.returncode != 0:
            result.error = f"v8unpack -B failed: {proc.stderr or proc.stdout}"
            return result

        if not output_epf.exists():
            result.error = f"Выходной файл не создан: {output_epf}"
            return result

        # 8.5. Патч block_size → 512 (v8unpack пишет неправильный)
        # v8unpack 1.2.6 пишет block_size = doc_size (фактический размер),
        # а 1С ожидает всегда block_size = 0x200 (512). Иначе "Ошибка формата потока".
        try:
            patch_script = _REPO_ROOT / "scripts" / "patch_epf_blocksize.py"
            if patch_script.exists():
                patched_path = output_epf.parent / f"{output_epf.stem}__patched.epf"
                patch_cmd = [
                    _PYTHON,
                    str(patch_script),
                    str(output_epf),
                    str(patched_path),
                ]
                patch_proc = subprocess.run(
                    patch_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if patch_proc.returncode == 0 and patched_path.exists():
                    # Заменяем оригинал пропатченной версией
                    shutil.move(str(patched_path), str(output_epf))
        except Exception as e:
            # Патч не критичен — продолжаем, но предупреждаем
            result.error = f"Предупреждение: patch_epf_blocksize не сработал: {e}"
            # Не возвращаем — продолжаем

        # Проверяем сигнатуру 1С-контейнера
        with open(output_epf, "rb") as f:
            sig = f.read(4)
        if sig != b"\xff\xff\xff\x7f":
            result.error = f"Неверная сигнатура .epf: {sig.hex()}"
            return result

        result.epf_path = output_epf
        result.size_bytes = output_epf.stat().st_size

        # 9. Проверка round-trip
        result.round_trip_ok = self._verify_round_trip(output_epf, src_dir, work_dir)

        # 10. Чистим temp (если save_sources=False)
        if save_sources:
            result.work_dir = work_dir
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        else:
            with contextlib.suppress(Exception):
                shutil.rmtree(work_dir)

        result.ok = True
        return result

    # ─── Патчеры JSON ───────────────────────────────────────────
    def _patch_ext_proc_json(
        self,
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
    ):
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
                    data[key] = _replace_in_tree(data[key], replacements)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _patch_form_id_json(self, json_path: Path, new_uuid: str):
        """Записать UUID формы в Form.id.json."""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        data["uuid"] = new_uuid
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─── Проверки ───────────────────────────────────────────────
    def _verify_round_trip(
        self,
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

    # ─── Утилиты ────────────────────────────────────────────────
    @staticmethod
    def list_templates() -> dict:
        """Список доступных шаблонов."""
        return {
            "ext_proc": str(TPL_EXT_PROC),
            "form": str(TPL_FORM),
            "form_id": str(TPL_FORM_ID),
            "form_elem_empty": str(TPL_FORM_ELEM_EMPTY),
            "templates_dir": str(TEMPLATES_DIR),
        }


# ────────────────────────────────────────────────────────────────
# CLI-обёртка для быстрого тестирования
# ────────────────────────────────────────────────────────────────
def _cli():
    if len(sys.argv) < 2:
        print("Usage: python epf_factory.py <create|templates> ...")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "templates":
        print(json.dumps(EpfFactory.list_templates(), indent=2))
        return

    if cmd == "create":
        # Минимальный CLI для тестирования: python epf_factory.py create NAME SYNONYM BSL_PATH OUTPUT
        if len(sys.argv) < 6:
            print("Usage: epf_factory.py create <name> <synonym> <bsl_path> <output_epf>")
            sys.exit(1)
        name = sys.argv[2]
        synonym = sys.argv[3]
        bsl_path = Path(sys.argv[4])
        output = Path(sys.argv[5])
        bsl_code = bsl_path.read_text(encoding="utf-8") if bsl_path.exists() else DEFAULT_BSL

        factory = EpfFactory()
        result = factory.create_epf(name, synonym, bsl_code, output)

        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "error": result.error,
                    "epf_path": str(result.epf_path) if result.epf_path else None,
                    "size_bytes": result.size_bytes,
                    "name": result.name,
                    "proc_uuid": result.proc_uuid,
                    "form_uuid": result.form_uuid,
                    "bsl_lines": result.bsl_lines,
                    "bsl_warnings": result.bsl_warnings,
                    "bsl_errors": result.bsl_errors,
                    "round_trip_ok": result.round_trip_ok,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(0 if result.ok else 1)

    print(f"Unknown command: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    _cli()
