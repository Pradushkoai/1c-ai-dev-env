#!/usr/bin/env python3
"""
Создание обработки "СписокГрафикаИВыполненияОбхода" —
форма списка документов ГрафикИВыполнениеОбхода из конфигурации «Обход».

Конфигурация «Обход» — мобильное приложение (MobilePlatformApplication).
В нём недоступен тип ПараметрыФормыДинамическогоСписка, поэтому программное
создание ДинамическийСписок невозможно. Решение: программно создать реквизит
формы «ТаблицаСписка» типа ТаблицаЗначений с колонками, создать визуальную
таблицу и заполнить её запросом из документа (аналогично ОбщаяФорма.ФормаОбходов).
"""
from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

# Добавляем scripts в path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from epf_builder import (
    extract_epf,
    build_epf,
    rename_data_processor,
    replace_form_module,
)
# BSL-модуль вынесен в отдельный файл — там используются реальные ТАБЫ
# для отступов (STD 456), которые невозможно сохранить в triple-quoted string
from spisok_bsl_module import BSL_MODULE

# ─── Параметры обработки ─────────────────────────────────────────
TEMPLATE_EPF = Path("/home/z/my-project/upload/ОбходТерриторииСПереключателемФонСоЗвуком.epf")
OUTPUT_EPF = Path("/home/z/my-project/download/СписокГрафикаИВыполненияОбхода.epf")

PROC_NAME = "СписокГрафикаИВыполненияОбхода"
PROC_SYNONYM = "Список графика и выполнения обхода"
FORM_NAME = "Форма"

# Основная таблица для запроса
MAIN_TABLE = "Документ.ГрафикИВыполнениеОбхода"


# ─── Сборка ─────────────────────────────────────────────────────
def main():
    print(f"=== Создание обработки {PROC_NAME} ===")
    print(f"Шаблон:     {TEMPLATE_EPF}")
    print(f"Результат:  {OUTPUT_EPF}")
    print(f"Форма:      список документов {MAIN_TABLE}")
    print()

    if not TEMPLATE_EPF.exists():
        print(f"❌ Шаблон не найден: {TEMPLATE_EPF}")
        sys.exit(1)

    work_dir = Path(f"/tmp/epf_spisok_gvo")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    src_dir = work_dir / "src"

    # 1. Распаковка шаблона
    print("1. Распаковка шаблона...")
    res = extract_epf(TEMPLATE_EPF, src_dir)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    print(f"   Распаковано файлов: {len(res['files'])}")

    # 2. Переименование обработки
    print(f"2. Переименование обработки → {PROC_NAME}...")
    res = rename_data_processor(src_dir, PROC_NAME, PROC_SYNONYM)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    print(f"   Старое имя: {res['old_name']}")
    print(f"   Новое имя:  {res['new_name']}")
    print(f"   Новый UUID: {res['new_uuid']}")

    # 3. Замена BSL-модуля формы
    print("3. Замена BSL-модуля формы...")
    res = replace_form_module(src_dir, FORM_NAME, BSL_MODULE)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    print(f"   Модуль формы: {res['lines']} строк")

    # 4. Сборка .epf
    print("4. Сборка .epf...")
    OUTPUT_EPF.parent.mkdir(parents=True, exist_ok=True)
    res = build_epf(src_dir, OUTPUT_EPF)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    print(f"   Размер: {res['size_bytes']} байт ({res['size_bytes']/1024:.1f} КБ)")
    print(f"   Файлов в исходниках: {res['files_included']}")

    # 5. Проверка round-trip
    print("5. Проверка round-trip...")
    from epf_builder import verify_epf
    res = verify_epf(OUTPUT_EPF)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    print(f"   Сигнатура: {res['signature']} (валидная)")
    print(f"   Извлечено файлов: {res['files_extracted']}")

    # 6. Распаковка для проверки BSL через репо-инструменты
    print("6. Проверка BSL через репо-инструмент solve check...")
    check_dir = work_dir / "check"
    if check_dir.exists():
        shutil.rmtree(check_dir)
    res = extract_epf(OUTPUT_EPF, check_dir)
    if not res["ok"]:
        print(f"❌ {res['error']}")
        sys.exit(1)
    bsl_path = check_dir / "Form" / "Форма" / "Form.obj.bsl"

    import subprocess
    result = subprocess.run(
        ["/home/z/.venv/bin/python", "-m", "src.cli", "solve", "check",
         str(bsl_path), "--level", "quick", "--config", "obhod"],
        capture_output=True, text=True, timeout=60,
        cwd="/home/z/my-project/repo_work"
    )
    # Извлекаем итоговую строку
    for line in result.stdout.split("\n"):
        if "ИТОГО" in line or "❌" in line or "✅" in line or "⚠️" in line:
            print(f"   {line.strip()}")

    # 7. Проверка имени в собранном файле
    print("7. Проверка имени обработки в собранном файле...")
    import json as _json
    with open(check_dir / "ExternalDataProcessor.json", "r", encoding="utf-8") as f:
        meta = _json.load(f)
    print(f"   name:    {meta['name']}")
    print(f"   uuid:    {meta['uuid']}")
    print(f"   synonym: {meta.get('name2', {}).get('ru')}")

    # Чистим temp
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    print()
    print(f"✅ EPF файл создан: {OUTPUT_EPF}")
    print(f"   Размер: {OUTPUT_EPF.stat().st_size / 1024:.1f} КБ")
    return OUTPUT_EPF


if __name__ == "__main__":
    main()
