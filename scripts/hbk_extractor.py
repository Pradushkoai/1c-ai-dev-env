#!/usr/bin/env python3
"""
Распаковщик .hbk файлов 1С (синтакс-помощник).

Формат .hbk:
- 16 байт: заголовок 1С (signature + flags + size)
- Дальше: TOC (оглавление) — строки вида "XXXXXXXX YYYYYYYY ZZZZZZZZ\r\n"
- Дальше: ~1000+ ZIP local file headers (PK\x03\x04) с deflate-сжатыми данными
- В конце: ZIP Central Directory + EOCD

Скрипт:
1. Извлекает все PK\x03\x04 файлы из .hbk
2. Распаковывает каждый через zlib (deflate)
3. Сохраняет в указанную директорию
"""

import os
import sys
import struct
import zlib
from pathlib import Path


def parse_hbk_file(hbk_path):
    """
    Парсит .hbk файл.
    Возвращает список словарей с информацией о каждом встроенном файле.
    """
    with open(hbk_path, 'rb') as f:
        data = f.read()
    
    print(f"Размер файла: {len(data)} байт")
    
    # Заголовок 1С (первые 16 байт)
    header = data[:16]
    print(f"Заголовок 1С: {header.hex()}")
    
    # Поиск всех PK\x03\x04 local file headers
    files = []
    pos = 0
    while pos < len(data):
        pk_pos = data.find(b'PK\x03\x04', pos)
        if pk_pos == -1 or pk_pos + 30 > len(data):
            break
        
        # Парсим local file header (30 байт)
        header_data = data[pk_pos:pk_pos+30]
        try:
            (sig, ver, flags, method, mtime, mdate, crc,
             comp_size, uncomp_size, name_len, extra_len) = struct.unpack('<IHHHHHIIIHH', header_data)
        except struct.error:
            pos = pk_pos + 4
            continue
        
        # Имя файла
        name_start = pk_pos + 30
        name = data[name_start:name_start+name_len].decode('utf-8', errors='replace')
        
        # Данные файла
        data_start = name_start + name_len + extra_len
        
        # Если comp_size == 0 — данные могут идти до следующего PK
        # В стандартном ZIP это не так, но 1С может использовать потоковый режим
        if comp_size == 0:
            # Ищем следующий PK
            next_pk = data.find(b'PK\x03\x04', data_start)
            if next_pk == -1:
                comp_size = len(data) - data_start
            else:
                comp_size = next_pk - data_start
        
        files.append({
            'name': name,
            'offset': pk_pos,
            'data_offset': data_start,
            'comp_size': comp_size,
            'uncomp_size': uncomp_size,
            'method': method,
            'crc': crc,
            'flags': flags,
        })
        
        pos = data_start + comp_size
    
    return files


def extract_file_data(data, file_info):
    """Распаковывает данные одного файла из .hbk."""
    data_start = file_info['data_offset']
    comp_size = file_info['comp_size']
    method = file_info['method']
    flags = file_info['flags']
    
    # Если флаг 0x08 установлен — comp_size в заголовке = 0,
    # реальный размер в Data Descriptor после сжатых данных
    # (signature PK\x07\x08 или без сигнатуры: crc, comp_size, uncomp_size)
    if comp_size == 0 or (flags & 0x08):
        # Ищем Data Descriptor после сжатых данных
        # В streaming ZIP после сжатых данных идёт:
        #   [опционально PK\x07\x08] + CRC32 (4) + CompSize (4) + UncompSize (4)
        # Но мы не знаем где конец сжатых данных — придётся использовать
        # zlib.decompressobj для потоковой декомпрессии
        
        if method == 8:
            # Используем декомпрессор, который сам определит конец
            decompressor = zlib.decompressobj(-15)
            try:
                # Декомпрессируем от data_start до конца файла
                result = decompressor.decompress(data[data_start:])
                # unused_data содержит то, что после сжатых данных
                if decompressor.unused_data:
                    actual_comp_size = len(data) - data_start - len(decompressor.unused_data)
                else:
                    actual_comp_size = len(data) - data_start
                return result
            except zlib.error as e:
                print(f"  ❌ Ошибка распаковки {file_info['name']}: {e}")
                return None
    
    raw = data[data_start:data_start + comp_size]
    
    if method == 0:
        return raw
    elif method == 8:
        try:
            return zlib.decompress(raw, -15)
        except zlib.error as e:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                print(f"  ❌ Ошибка распаковки {file_info['name']}: {e}")
                return None
    else:
        print(f"  ⚠️ Неизвестный метод сжатия {method} для {file_info['name']}")
        return None


def safe_filename(name):
    """Делает имя файла безопасным для файловой системы."""
    # Заменяем недопустимые символы
    safe = name.replace('/', '_').replace('\\', '_').replace(':', '_')
    safe = safe.replace('*', '_').replace('?', '_').replace('"', '_')
    safe = safe.replace('<', '_').replace('>', '_').replace('|', '_')
    return safe


def extract_hbk(hbk_path, output_dir):
    """Главная функция: распаковывает .hbk в указанную директорию."""
    hbk_path = Path(hbk_path)
    output_dir = Path(output_dir)
    
    print(f"\n{'='*60}")
    print(f"Распаковка: {hbk_path.name}")
    print(f"В: {output_dir}")
    print(f"{'='*60}")
    
    # Парсим
    files = parse_hbk_file(str(hbk_path))
    print(f"Найдено файлов в архиве: {len(files)}")
    
    if not files:
        print("❌ Файлы не найдены")
        return 0
    
    # Создаём выходную директорию
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Читаем данные .hbk один раз
    with open(hbk_path, 'rb') as f:
        data = f.read()
    
    # Распаковываем каждый файл
    success = 0
    failed = 0
    
    for i, file_info in enumerate(files, 1):
        if i % 50 == 0 or i == len(files):
            print(f"  Прогресс: {i}/{len(files)}")
        
        # Безопасное имя
        safe_name = safe_filename(file_info['name'])
        if not safe_name:
            safe_name = f"unnamed_{i}"
        
        # Если имя без расширения — добавляем .html (обычно это страницы справки)
        if '.' not in safe_name:
            safe_name += '.html'
        
        out_path = output_dir / safe_name
        
        # Распаковываем
        content = extract_file_data(data, file_info)
        if content is None:
            failed += 1
            continue
        
        # Записываем
        try:
            with open(out_path, 'wb') as f:
                f.write(content)
            success += 1
        except Exception as e:
            print(f"  ❌ Ошибка записи {out_path}: {e}")
            failed += 1
    
    print(f"\n✅ Успешно: {success}")
    print(f"❌ Ошибок:  {failed}")
    return success


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 hbk_extractor.py <hbk_file> <output_dir>")
        print("               python3 hbk_extractor.py <hbk_dir>/*.hbk <output_root>")
        sys.exit(1)
    
    hbk_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    # Поддержка wildcard
    import glob
    hbk_files = glob.glob(hbk_path)
    if not hbk_files:
        hbk_files = [hbk_path]
    
    total_success = 0
    for hbk in hbk_files:
        # Имя выходной директории — по имени .hbk файла без расширения
        hbk_name = Path(hbk).stem
        out = Path(output_dir) / hbk_name
        total_success += extract_hbk(hbk, out)
    
    print(f"\n{'='*60}")
    print(f"ИТОГО: распаковано {total_success} файлов из {len(hbk_files)} .hbk")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
