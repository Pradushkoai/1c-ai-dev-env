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
from typing import Any

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

# Этап 2.2: утилиты вынесены в пакет epf/
from .epf import EpfFactoryResult, patch_ext_proc_json, patch_form_id_json, validate_bsl, verify_round_trip
from .epf.json_patcher import (
    replace_in_tree as _replace_in_tree,  # noqa: F401 — re-export для обратной совместимости с tests
)

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
# Результат, утилиты и BSL-валидатор вынесены в пакет epf/ (Этап 2.2):
#   from .epf import EpfFactoryResult, validate_bsl, patch_ext_proc_json,
#                    patch_form_id_json, verify_round_trip
# ────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────
# Главный класс
# ────────────────────────────────────────────────────────────────
class EpfFactory:
    """Полный цикл создания внешней обработки 1С (.epf) из шаблонов.

    P2.4: create_epf разбит на pipeline из 10 этапов.
    Каждый этап — отдельный метод, который возвращает True/False (успех/провал)
    и записывает ошибку в result.error при провале.

    F1.2 (2026-07-05): Реализует ServiceProtocol (name, initialize, is_available).
    """

    # F1.2: ServiceProtocol implementation
    @property
    def name(self) -> str:
        return "epf_factory"

    def initialize(self) -> None:
        """F1.2: Проверка что шаблоны существуют."""
        if not TEMPLATES_DIR.exists():
            raise FileNotFoundError(f"Шаблоны EPF не найдены: {TEMPLATES_DIR}")

    def is_available(self) -> bool:
        """F1.2: EpfFactory доступен если шаблоны существуют."""
        return TEMPLATES_DIR.exists()

    def create_epf(
        self,
        name: str,
        synonym: str | None,
        bsl_code: str,
        output_epf: str | Path,
        form_name: str = "Форма",
        form_spec: dict[str, Any] | str | Path | None = None,
        work_dir: str | Path | None = None,
        save_sources: bool = False,
        skip_bsl_validation: bool = False,
    ) -> EpfFactoryResult:
        """Создать .epf с указанными параметрами.

        Pipeline из 10 этапов:
        1. _prepare_work_dir — подготовка рабочего каталога
        2. _copy_templates — копирование шаблонов v8unpack
        3. _apply_form_spec — генерация Form.elem.json из DSL (опционально)
        4. _generate_uuids — генерация новых UUID для обработки и формы
        5. _patch_ext_proc — подстановка name/synonym/UUID в ExternalDataProcessor.json
        6. _patch_form_id — подстановка UUID в Form.id.json
        7. _write_bsl_module — запись BSL-кода и подсчёт строк
        8. _validate_bsl — проверка через BSL LS (опционально)
        9. _build_epf — сборка .epf через v8unpack + патч block_size
        10. _verify_and_finalize — round-trip проверка + сигнатура + cleanup

        Args:
            name: Имя обработки (латиница/кириллица, без пробелов)
            synonym: Синоним (если None — = name)
            bsl_code: BSL-код модуля формы
            output_epf: Куда сохранить .epf
            form_name: Имя формы (по умолчанию "Форма")
            form_spec: Описание формы (dict / str-путь / Path / None)
            work_dir: Рабочий каталог (по умолчанию /tmp/epf_factory_<uuid>)
            save_sources: Сохранить v8unpack-исходники в work_dir
            skip_bsl_validation: Пропустить проверку BSL LS

        Returns:
            EpfFactoryResult
        """
        result = EpfFactoryResult(name=name, synonym=synonym or name)
        output_epf = Path(output_epf)

        # Pipeline context — передаётся между этапами
        ctx: dict[str, Any] = {
            "name": name,
            "synonym": synonym or name,
            "bsl_code": bsl_code,
            "output_epf": output_epf,
            "form_name": form_name,
            "form_spec": form_spec,
            "work_dir": Path(work_dir) if work_dir else None,
            "save_sources": save_sources,
            "skip_bsl_validation": skip_bsl_validation,
            "src_dir": None,
            "form_dir": None,
            "bsl_path": None,
            "temp_dir": None,
        }

        # Pipeline — каждый этап может прервать выполнение, вернув False
        pipeline = [
            self._prepare_work_dir,
            self._copy_templates,
            self._apply_form_spec,
            self._generate_uuids,
            self._patch_ext_proc,
            self._patch_form_id,
            self._write_bsl_module,
            self._validate_bsl,
            self._build_epf,
            self._verify_and_finalize,
        ]

        for stage in pipeline:
            if not stage(result, ctx):
                return result  # ошибка уже в result.error

        result.ok = True
        return result

    # ─── Pipeline этапы (P2.4) ──────────────────────────────────

    def _prepare_work_dir(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 1: Подготовка рабочего каталога."""
        work_dir = ctx["work_dir"]
        if work_dir is None:
            work_dir = Path(tempfile.gettempdir()) / f"epf_factory_{uuid.uuid4().hex[:8]}"
        work_dir = Path(work_dir)
        if work_dir.exists():
            shutil.rmtree(work_dir)
        ctx["work_dir"] = work_dir
        ctx["src_dir"] = work_dir / "src"
        ctx["form_dir"] = ctx["src_dir"] / "Form" / ctx["form_name"]
        ctx["temp_dir"] = work_dir / "build_temp"
        return True

    def _copy_templates(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 2: Копирование шаблонов v8unpack."""
        src_dir = ctx["src_dir"]
        form_dir = ctx["form_dir"]
        try:
            src_dir.mkdir(parents=True, exist_ok=True)
            form_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(TPL_EXT_PROC, src_dir / "ExternalDataProcessor.json")
            shutil.copy(TPL_FORM, form_dir / "Form.json")
            shutil.copy(TPL_FORM_ID, form_dir / "Form.id.json")
            shutil.copy(TPL_FORM_ELEM_EMPTY, form_dir / "Form.elem.json")
        except Exception as e:
            result.error = f"Ошибка копирования шаблонов: {e}"
            return False
        return True

    def _apply_form_spec(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 3: Генерация Form.elem.json из form_spec DSL (опционально)."""
        form_spec = ctx["form_spec"]
        if form_spec is None:
            return True  # опциональный этап

        form_dir = ctx["form_dir"]
        try:
            from .form_elem_builder import build_form_elem

            # form_spec может быть dict, str (путь к файлу) или Path
            if isinstance(form_spec, (str, Path)):
                spec_path = Path(form_spec)
                if not spec_path.exists():
                    result.error = f"form_spec файл не найден: {spec_path}"
                    return False
                with open(spec_path, encoding="utf-8") as f:
                    spec_dict = json.load(f)
            elif isinstance(form_spec, dict):
                spec_dict = form_spec
            else:
                result.error = f"form_spec должен быть dict, str или Path, получен {type(form_spec).__name__}"
                return False

            # Генерируем Form.elem.json из DSL, ИСПОЛЬЗУЯ template как базу
            # Template уже прошёл проверку 1С — добавление реквизитов сохраняет валидность.
            form_elem = build_form_elem(spec_dict, base_template_path=TPL_FORM_ELEM_TEMPLATE)
            with open(form_dir / "Form.elem.json", "w", encoding="utf-8") as f:
                json.dump(form_elem, f, ensure_ascii=False, indent=2)
        except Exception as e:
            result.error = f"Ошибка генерации Form.elem.json из form_spec: {e}"
            return False
        return True

    def _generate_uuids(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 4: Генерация новых UUID для обработки и формы."""
        result.proc_uuid = str(uuid.uuid4())
        result.form_uuid = str(uuid.uuid4())
        # Сохраняем old_form_uuid из шаблона для _patch_ext_proc
        form_id_path = ctx["form_dir"] / "Form.id.json"
        with open(form_id_path, encoding="utf-8") as f:
            ctx["old_form_uuid"] = json.load(f).get("uuid", "")
        return True

    def _patch_ext_proc(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 5: Подстановка name/synonym/UUID в ExternalDataProcessor.json."""
        try:
            self._patch_ext_proc_json(
                ctx["src_dir"] / "ExternalDataProcessor.json",
                old_name="ОбходТерриторииСПереключателемФонСоЗвуком",
                new_name=ctx["name"],
                old_synonym="Обход территории с переключателем фон со звуком",
                new_synonym=ctx["synonym"],
                old_proc_uuid="",  # будет заполнено из шаблона
                new_proc_uuid=result.proc_uuid,
                old_form_uuid=ctx["old_form_uuid"],
                new_form_uuid=result.form_uuid,
            )
        except Exception as e:
            result.error = f"Ошибка патча ExternalDataProcessor.json: {e}"
            return False
        return True

    def _patch_form_id(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 6: Подстановка UUID в Form.id.json."""
        try:
            self._patch_form_id_json(ctx["form_dir"] / "Form.id.json", result.form_uuid)
        except Exception as e:
            result.error = f"Ошибка патча Form.id.json: {e}"
            return False
        return True

    def _write_bsl_module(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 7: Запись BSL-кода модуля формы."""
        bsl_path = ctx["form_dir"] / "Form.obj.bsl"
        bsl_path.write_text(ctx["bsl_code"], encoding="utf-8")
        result.bsl_lines = ctx["bsl_code"].count("\n") + (0 if ctx["bsl_code"].endswith("\n") else 1)
        ctx["bsl_path"] = bsl_path
        return True

    def _validate_bsl(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 8: Проверка BSL через BSL LS (опционально)."""
        if ctx["skip_bsl_validation"]:
            return True
        bsl_res = validate_bsl(ctx["bsl_path"])
        if bsl_res.get("ok"):
            result.bsl_errors = bsl_res["errors"]
            result.bsl_warnings = bsl_res["warnings"]
        # Не блокируем сборку при ошибках BSL LS — это только предупреждения
        return True

    def _build_epf(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 9: Сборка .epf через v8unpack + патч block_size."""
        output_epf = ctx["output_epf"]
        src_dir = ctx["src_dir"]
        temp_dir = ctx["temp_dir"]

        output_epf.parent.mkdir(parents=True, exist_ok=True)
        if output_epf.exists():
            output_epf.unlink()
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        cmd = [_PYTHON, "-m", "v8unpack", "-B", str(src_dir), str(output_epf), "--temp", str(temp_dir)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            result.error = "v8unpack timeout при сборке"
            return False

        if proc.returncode != 0:
            result.error = f"v8unpack -B failed: {proc.stderr or proc.stdout}"
            return False

        if not output_epf.exists():
            result.error = f"Выходной файл не создан: {output_epf}"
            return False

        # Патч block_size → 512 (v8unpack 1.2.6 пишет неправильный)
        # v8unpack пишет block_size = doc_size, а 1С ожидает 0x200 (512).
        try:
            patch_script = _REPO_ROOT / "scripts" / "patch_epf_blocksize.py"
            if patch_script.exists():
                patched_path = output_epf.parent / f"{output_epf.stem}__patched.epf"
                patch_cmd = [_PYTHON, str(patch_script), str(output_epf), str(patched_path)]
                patch_proc = subprocess.run(patch_cmd, capture_output=True, text=True, timeout=30, check=False)
                if patch_proc.returncode == 0 and patched_path.exists():
                    shutil.move(str(patched_path), str(output_epf))
        except Exception as e:
            # Патч не критичен — продолжаем, но предупреждаем
            result.error = f"Предупреждение: patch_epf_blocksize не сработал: {e}"
            # Не возвращаем False — продолжаем

        # Проверяем сигнатуру 1С-контейнера
        with open(output_epf, "rb") as f:
            sig = f.read(4)
        if sig != b"\xff\xff\xff\x7f":
            result.error = f"Неверная сигнатура .epf: {sig.hex()}"
            return False

        result.epf_path = output_epf
        result.size_bytes = output_epf.stat().st_size
        return True

    def _verify_and_finalize(self, result: EpfFactoryResult, ctx: dict[str, Any]) -> bool:
        """Этап 10: Round-trip проверка + cleanup."""
        output_epf = ctx["output_epf"]
        src_dir = ctx["src_dir"]
        work_dir = ctx["work_dir"]
        temp_dir = ctx["temp_dir"]

        # Round-trip: распаковать .epf и сравнить BSL-модуль
        result.round_trip_ok = self._verify_round_trip(output_epf, src_dir, work_dir)

        # Cleanup
        if ctx["save_sources"]:
            result.work_dir = work_dir
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        else:
            with contextlib.suppress(Exception):
                shutil.rmtree(work_dir)
        return True

    # ─── Патчеры JSON — делегируют в epf.json_patcher (Этап 2.2) ───
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
    ) -> None:
        """Делегирует в epf.patch_ext_proc_json (Этап 2.2)."""
        patch_ext_proc_json(
            json_path,
            old_name,
            new_name,
            old_synonym,
            new_synonym,
            old_proc_uuid,
            new_proc_uuid,
            old_form_uuid,
            new_form_uuid,
            old_file_uuid,
            new_file_uuid,
        )

    def _patch_form_id_json(self, json_path: Path, new_uuid: str) -> None:
        """Делегирует в epf.patch_form_id_json (Этап 2.2)."""
        patch_form_id_json(json_path, new_uuid)

    # ─── Проверки — делегируют в epf.round_trip (Этап 2.2) ─────────
    def _verify_round_trip(
        self,
        epf_path: Path,
        original_src: Path,
        work_dir: Path,
    ) -> bool:
        """Делегирует в epf.verify_round_trip (Этап 2.2)."""
        return verify_round_trip(epf_path, original_src, work_dir)

    # ─── Утилиты ────────────────────────────────────────────────
    @staticmethod
    def list_templates() -> dict[str, Any]:
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
def _cli() -> None:
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
