#!/usr/bin/env python3
"""
Профилирование metadata_extractor и config build.

Этап 6.1: cProfile на синтетической конфигурации (реальные УТ11/БСП недоступны).
Сравнение с baseline в tests/test_benchmarks_synthetic.py.

Запуск:
    python3 scripts/profile_metadata_extractor.py
"""

from __future__ import annotations

import cProfile
import json
import pstats
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path


def create_synthetic_config(config_dir: Path, num_objects: int = 100) -> None:
    """Создать синтетическую конфигурацию 1С для профилирования.

    Args:
        config_dir: Каталог для конфигурации
        num_objects: Количество объектов каждого типа
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    # Configuration.xml
    (config_dir / "Configuration.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" uuid="00000000-0000-0000-0000-000000000000">
  <Configuration uuid="00000000-0000-0000-0000-000000000001">
    <Name>ТестоваяКонфигурация</Name>
    <Synonym>
      <Key>ru</Key>
      <Value>Тестовая конфигурация</Value>
    </Synonym>
    <Comment>Синтетическая конфигурация для профилирования</Comment>
    <Version>1.0.0</Version>
  </Configuration>
</MetaDataObject>
""",
        encoding="utf-8",
    )

    # Catalogs
    catalogs_dir = config_dir / "Catalogs"
    catalogs_dir.mkdir(exist_ok=True)
    for i in range(num_objects):
        catalog_name = f"Справочник{i:03d}"
        catalog_dir = catalogs_dir / catalog_name
        catalog_dir.mkdir(exist_ok=True)
        (catalog_dir / f"{catalog_name}.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" uuid="{i:08x}-0000-0000-0000-000000000001">
  <Catalog uuid="{i:08x}-0000-0000-0000-000000000002">
    <Name>{catalog_name}</Name>
    <Synonym><Key>ru</Key><Value>Справочник {i}</Value></Synonym>
    <CodeLength>9</CodeLength>
    <DescriptionLength>50</DescriptionLength>
    <Attributes>
      <Attribute uuid="{i:08x}-0000-0000-0000-000000000003">
        <Name>Реквизит1</Name>
        <Type><Type>String</Type><Type>Number</Type></Type>
      </Attribute>
    </Attributes>
  </Catalog>
</MetaDataObject>
""",
            encoding="utf-8",
        )


def profile_metadata_extractor(config_dir: Path, output_path: Path) -> dict:
    """Профилировать MetadataExtractor.extract_and_save.

    Returns:
        dict с метриками: time_seconds, num_objects, output_size_kb
    """
    from src.services.metadata.extractor import extract_and_save

    t0 = time.time()
    result = extract_and_save(config_dir, output_path)
    t1 = time.time()

    elapsed = t1 - t0
    output_size = output_path.stat().st_size / 1024 if output_path.exists() else 0

    return {
        "time_seconds": elapsed,
        "result": result,
        "output_size_kb": output_size,
        "config_dir": str(config_dir),
    }


def profile_with_cprofile(config_dir: Path, output_path: Path) -> str:
    """Профилировать с cProfile, вернуть топ-10 функций.

    Returns:
        Строка с отчётом cProfile (топ-10 по cumtime)
    """
    from src.services.metadata.extractor import extract_and_save

    profiler = cProfile.Profile()
    profiler.enable()
    extract_and_save(config_dir, output_path)
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(10)
    return stream.getvalue()


def main() -> None:
    print("=" * 60)
    print("ПРОФИЛИРОВАНИЕ metadata_extractor")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_dir = tmpdir / "config"
        output_path = tmpdir / "unified-metadata-index.json"

        # Создаём синтетическую конфигурацию
        print("\n1. Создание синтетической конфигурации (100 объектов)...")
        create_synthetic_config(config_dir, num_objects=100)
        print(f"   Конфигурация: {config_dir}")

        # Базовое время
        print("\n2. Замер времени (без cProfile)...")
        metrics = profile_metadata_extractor(config_dir, output_path)
        print(f"   Время: {metrics['time_seconds']:.3f} сек")
        print(f"   Размер индекса: {metrics['output_size_kb']:.1f} КБ")

        # cProfile
        print("\n3. cProfile (топ-10 функций по cumulative time)...")
        # Пересоздаём output (cProfile может замедлить)
        output_path.unlink(missing_ok=True)
        cprofile_report = profile_with_cprofile(config_dir, output_path)
        print(cprofile_report)

        # Записываем отчёт
        report_path = Path("docs/PERFORMANCE.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Performance Profiling (Этап 6.1)\n\n")
            f.write(f"Дата: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Метрики\n\n")
            f.write(f"| Метрика | Значение |\n")
            f.write(f"|---------|----------|\n")
            f.write(f"| Время (без cProfile) | {metrics['time_seconds']:.3f} сек |\n")
            f.write(f"| Размер индекса | {metrics['output_size_kb']:.1f} КБ |\n")
            f.write(f"| Конфигурация | 100 объектов (синтетическая) |\n\n")
            f.write("## cProfile топ-10 (cumulative time)\n\n")
            f.write("```\n")
            f.write(cprofile_report)
            f.write("```\n\n")
            f.write("## Примечания\n\n")
            f.write("- Профилирование на синтетической конфигурации (100 Catalogs)\n")
            f.write("- Реальные УТ11/БСП недоступны в окружении\n")
            f.write("- Для сравнения: tests/test_benchmarks_synthetic.py содержит synthetic benchmarks\n")
            f.write("- Задача 6.2: оптимизация топ-3 горячих функций\n")

        print(f"\n4. Отчёт сохранён: {report_path}")
        print("\n✅ Профилирование завершено.")


if __name__ == "__main__":
    main()
