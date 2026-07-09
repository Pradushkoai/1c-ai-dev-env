"""
epf_factory_cmd.py — CLI команда для epf-factory.

F1.6 (2026-07-05): вынесено из cli_commands/tools.py (531 LOC → 7 файлов).
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.project import Project


def cmd_epf_factory(project: Project, args: object) -> None:
    """Полный цикл создания внешней обработки 1С (.epf) из шаблонов.

    Подход:
        1. Шаблоны ExternalDataProcessor.json / Form.json / Form.id.json /
           Form.elem.json (извлечены из реального EPF через v8unpack)
        2. Подстановка name, synonym, новых UUID (обработка + форма + file)
        3. Запись BSL-модуля формы
        4. Проверка BSL через BSL LS (опционально)
        5. Сборка .epf через v8unpack
        6. Проверка round-trip: распаковка и сравнение BSL-модуля
    """
    from src.services.epf_factory import EpfFactory

    factory = EpfFactory()

    if args.epf_command == "templates":
        templates = factory.list_templates()
        print("Шаблоны epf-factory:")
        for k, v in templates.items():
            print(f"  {k:20s}  {v}")
        return

    if args.epf_command == "create":
        bsl_path = Path(args.bsl)
        if not bsl_path.exists():
            print(f"❌ BSL-файл не найден: {bsl_path}")
            sys.exit(2)
        bsl_code = bsl_path.read_text(encoding="utf-8")

        result = factory.create_epf(
            name=args.name,
            synonym=args.synonym,
            bsl_code=bsl_code,
            output_epf=args.output,
            form_name=args.form_name,
            form_spec=args.form_spec,
            save_sources=args.save_sources,
            skip_bsl_validation=args.skip_bsl_validation,
        )

        if not result.ok:
            print(f"❌ Ошибка: {result.error}")
            sys.exit(1)

        print(f"✅ EPF создан: {result.epf_path}")
        print(f"   Размер: {result.size_bytes} байт ({result.size_bytes / 1024:.1f} КБ)")
        print(f"   Имя:    {result.name}")
        print(f"   Синоним: {result.synonym}")
        print(f"   UUID обработки: {result.proc_uuid}")
        print(f"   UUID формы:     {result.form_uuid}")
        print(f"   BSL-модуль: {result.bsl_lines} строк")
        if not args.skip_bsl_validation:
            print(f"   BSL LS: {result.bsl_errors} errors, {result.bsl_warnings} warnings")
        print(f"   Round-trip: {'✅ OK' if result.round_trip_ok else '❌ FAIL'}")
        if result.work_dir:
            print(f"   Исходники сохранены: {result.work_dir}")
