#!/usr/bin/env python3
"""
Пакетное извлечение .cf файлов с помощью improved_cf_adapter.
"""
import sys
import os
import shutil
import subprocess
import time
from pathlib import Path

# Добавляем scripts/ в path
sys.path.insert(0, '/home/z/my-project/repo_work/scripts')
sys.path.insert(0, '/home/z/my-project/scripts')

from cf_extractor import extract_cf
from improved_cf_adapter import convert_cf_to_xml_format


def process_cf(cf_path: str, output_dir: str, config_name: str = None):
    """Извлекает .cf файл и конвертирует в XML формат."""
    cf_path = Path(cf_path)
    output_dir = Path(output_dir)
    config_name = config_name or cf_path.stem
    
    print(f"\n{'='*60}")
    print(f"Обработка: {config_name}")
    print(f"  .cf файл: {cf_path}")
    print(f"  Выход: {output_dir}")
    print(f"{'='*60}")
    
    if not cf_path.exists():
        print(f"  ❌ Файл не найден: {cf_path}")
        return None
    
    # Создаём временные папки
    raw_dir = output_dir.parent / f'{config_name}_raw_tmp'
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True)
    
    try:
        # Шаг 1: Распаковка .cf
        print(f"\n[1/2] Распаковка .cf ({cf_path.stat().st_size / 1024 / 1024:.1f} MB)...")
        start = time.time()
        count = extract_cf(cf_path, raw_dir)
        elapsed = time.time() - start
        print(f"  ✅ Распаковано {count} файлов за {elapsed:.1f} сек")
        
        # Шаг 2: Конвертация в XML формат
        print(f"\n[2/2] Конвертация в XML формат...")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        
        start = time.time()
        stats = convert_cf_to_xml_format(raw_dir, output_dir)
        elapsed = time.time() - start
        print(f"  ✅ Конвертация завершена за {elapsed:.1f} сек")
        print(f"     CommonModules: {stats['common_modules']}")
        print(f"     ObjectModules: {stats['object_modules']}")
        print(f"     ManagerModules: {stats['manager_modules']}")
        print(f"     CommonForms: {stats['common_forms']}")
        print(f"     Object Forms (вложенные): {stats['object_forms']}")
        print(f"     CommonCommands: {stats['common_commands']}")
        print(f"     Subsystems: {stats['subsystems']}")
        print(f"     CommandInterfaces: {stats['command_interfaces']}")
        print(f"     Всего BSL модулей: {stats['total_bsl_modules']}")
        
        return stats
    finally:
        # Удаляем временную папку
        if raw_dir.exists():
            shutil.rmtree(raw_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 batch_cf_extract.py <cf_file_or_dir> [output_dir]")
        print()
        print("Примеры:")
        print("  python3 batch_cf_extract.py /tmp/edo2.cf /home/z/my-project/repo_work/data/configs/edo2")
        print("  python3 batch_cf_extract.py /tmp/ /home/z/my-project/repo_work/data/configs/")
        sys.exit(1)
    
    source = Path(sys.argv[1])
    output_base = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/home/z/my-project/repo_work/data/configs')
    
    if source.is_file() and source.suffix == '.cf':
        # Один .cf файл
        config_name = source.stem
        output_dir = output_base if output_base.is_file() or not output_base.name.count('.') else output_base / config_name
        if output_base == Path('/home/z/my-project/repo_work/data/configs'):
            output_dir = output_base / config_name
        process_cf(source, output_dir, config_name)
    elif source.is_dir():
        # Папка с .cf файлами
        for cf_file in sorted(source.glob('*.cf')):
            config_name = cf_file.stem
            output_dir = output_base / config_name
            process_cf(cf_file, output_dir, config_name)
    else:
        print(f"❌ Неверный источник: {source}")
        sys.exit(1)


if __name__ == '__main__':
    main()
