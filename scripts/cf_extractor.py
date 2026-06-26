#!/usr/bin/env python3
"""
cf_extractor.py — Распаковщик .cf/.cfe/.epf файлов 1С.

Формат контейнера 1С:
- 4 байта: сигнатура 0xFF 0xFF 0xFF 0x7F
- 4 байта: first_empty_block_offset (int32 LE)
- 4 байта: default_block_size (int32 LE) — обычно 0x200 (512 байт)
- 4 байта: count_files (int32 LE) — кол-во файлов в TOC

Затем — Document с TOC (оглавлением):
- Заголовок блока (31 байт) + данные

TOC — массив записей по 8 байт (парами int32):
  - 4 байта: hex-имя файла (как строка ASCII, например "vers", "root")
  - 4 байта: тип/флаги
Запись-терминатор: 0x7FFFFFFF

После TOC: данные файлов (по цепочке блоков).
Каждый файл может быть:
- Вложенным контейнером (начинается с 0xFF 0xFF 0xFF 0x7F) — рекурсивно извлекаем
- Deflate-сжатыми данными (zlib raw, wbits=-15)
- Сырыми данными (XML, BSL)

Использование:
    python3 cf_extractor.py <file.cf> <output_dir>

Пример:
    python3 cf_extractor.py ut11.cf data/configs/ut11
"""
from __future__ import annotations

import os
import struct
import sys
import zlib
from pathlib import Path
from typing import Iterator, Optional

# Сигнатура контейнера 1С
V8_SIGNATURE = b'\xFF\xFF\xFF\x7F'
END_MARKER = 0x7FFFFFFF


class V8Container:
    """Контейнер 1С — формат хранения .cf/.cfe/.epf файлов."""

    HEADER_FMT = '<4i'  # 4 int32 little-endian
    HEADER_SIZE = 16
    BLOCK_HEADER_SIZE = 31
    INDEX_FMT = 'i'
    DEFAULT_BLOCK_SIZE = 0x200
    INDEX_BLOCK_SIZE = 0x200

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset
        self.first_empty_block_offset = 0
        self.default_block_size = self.DEFAULT_BLOCK_SIZE
        self.count_files = 0
        self.toc: list[tuple[str, int]] = []  # (name, type)
        self.size = 0

    def read(self) -> None:
        """Прочитать заголовок и TOC."""
        self._read_header()
        self._read_toc()

    def _read_header(self) -> None:
        """Читает 16-байтный заголовок контейнера."""
        if self.data[self.offset:self.offset + 4] != V8_SIGNATURE:
            raise ValueError(f"Неверная сигнатура контейнера по смещению {self.offset}")
        header = struct.unpack_from(self.HEADER_FMT, self.data, self.offset)
        self.first_empty_block_offset = header[1]
        self.default_block_size = header[2] if header[2] else self.DEFAULT_BLOCK_SIZE
        self.count_files = header[3]
        self.size += self.HEADER_SIZE

    def _read_block(self, file_offset: int) -> tuple[bytes, int, int]:
        """
        Читает один блок по цепочке.
        Возвращает (data, full_size, next_block_offset).
        """
        abs_offset = self.offset + file_offset
        # Заголовок блока: 31 байт
        # doc_size (2 hex) + current_block_size (8 hex) + sep(1) + next_offset (8 hex) + sep(1) + data_len (8 hex) + sep(1) + end(2)
        header = self.data[abs_offset:abs_offset + self.BLOCK_HEADER_SIZE]
        if len(header) < self.BLOCK_HEADER_SIZE:
            return b'', 0, 0

        # Парсим hex значения из заголовка
        try:
            # current_block_size = int(header[2:10], 16)
            next_block_offset = int(header[11:19], 16)
            data_len = int(header[20:28], 16)
        except ValueError:
            return b'', 0, 0

        # Читаем данные блока
        data_start = abs_offset + self.BLOCK_HEADER_SIZE
        block_data = self.data[data_start:data_start + data_len]

        # full_size = заголовок (31) + длина данных
        full_size = self.BLOCK_HEADER_SIZE + data_len

        return block_data, full_size, next_block_offset

    def _read_document(self, file_offset: int) -> tuple[bytes, int]:
        """
        Читает документ (цепочку блоков) целиком.
        Возвращает (data, total_size_in_container).
        """
        result = b''
        current_offset = file_offset
        total_size = 0
        max_iterations = 100000  # защита от зацикливания

        for _ in range(max_iterations):
            if current_offset >= len(self.data) - self.BLOCK_HEADER_SIZE:
                break

            block_data, full_size, next_offset = self._read_block(current_offset)
            if not block_data and full_size == 0:
                break

            result += block_data
            total_size += full_size

            if next_offset == 0 or next_offset == END_MARKER:
                break
            current_offset = next_offset

        return result, total_size

    def _read_toc(self) -> None:
        """Читает оглавление (TOC) — первый документ после заголовка."""
        # Первый документ содержит TOC
        toc_data, toc_size = self._read_document(self.HEADER_SIZE)
        self.size += toc_size

        # TOC: массив пар int32 (name, type), завершается END_MARKER
        index_size = struct.calcsize(self.INDEX_FMT)
        end_marker_bytes = struct.pack(self.INDEX_FMT, END_MARKER)

        # Берём всё до end_marker
        parts = toc_data.split(end_marker_bytes)
        if parts:
            toc_data = parts[0]

        self.toc = []
        for i in range(0, len(toc_data) - index_size * 2 + 1, index_size * 2):
            name_int, file_type = struct.unpack_from(f'2{self.INDEX_FMT}', toc_data, i)
            if name_int == 0 or name_int == END_MARKER:
                break
            # Имя файла — это 4 ASCII символа (little-endian int32)
            name_bytes = struct.pack(self.INDEX_FMT, name_int)
            name = name_bytes.decode('ascii', errors='replace').strip('\x00')
            self.toc.append((name, file_type))

    def extract(self, output_dir: Path, deflate: bool = True, recursive: bool = True,
                progress_prefix: str = '') -> int:
        """
        Извлечь файлы из контейнера.
        Возвращает количество извлечённых файлов.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = 0
        current_pos = self.HEADER_SIZE  # после заголовка

        # Читаем TOC-документ (первый)
        _, toc_full_size = self._read_document(current_pos)
        current_pos += toc_full_size

        for name, file_type in self.toc:
            if not name:
                continue
            file_data, doc_full_size = self._read_document(current_pos)
            current_pos += doc_full_size

            if not file_data:
                continue

            # Если данные сжаты (deflate) — распаковываем
            if deflate:
                try:
                    file_data = zlib.decompress(file_data, -15)
                except zlib.error:
                    pass  # данные не сжаты

            # Определяем, является ли файл вложенным контейнером
            is_container = file_data[:4] == V8_SIGNATURE

            file_path = output_dir / name

            if is_container and recursive:
                # Рекурсивно извлекаем вложенный контейнер
                nested_dir = file_path
                nested_dir.mkdir(parents=True, exist_ok=True)
                try:
                    nested = V8Container(file_data, 0)
                    nested.read()
                    extracted += nested.extract(nested_dir, deflate, recursive,
                                                progress_prefix + name + '/')
                except Exception:
                    # Если не удалось распаковать как контейнер — сохраняем как есть
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    extracted += 1
            else:
                # Сохраняем как файл
                # Если данные похожи на XML — добавляем расширение .xml
                if file_data[:5] == b'<?xml' or (file_data[:1] == b'<' and b'<' in file_data[:100]):
                    if file_path.suffix != '.xml':
                        file_path = file_path.with_suffix('.xml')
                elif file_data[:2] == b'PK':
                    # ZIP архив
                    if file_path.suffix != '.bin':
                        file_path = file_path.with_suffix('.bin')
                else:
                    # BSL или другой — оставляем как есть
                    if file_path.suffix == '':
                        file_path = file_path.with_suffix('.bin')

                with open(file_path, 'wb') as f:
                    f.write(file_data)
                extracted += 1

        return extracted


def extract_cf(cf_path: Path, output_dir: Path, recursive: bool = True) -> int:
    """
    Распаковать .cf/.cfe/.epf файл в указанную директорию.

    Args:
        cf_path: Путь к .cf файлу
        output_dir: Куда распаковывать
        recursive: Рекурсивно извлекать вложенные контейнеры

    Returns:
        Количество извлечённых файлов
    """
    with open(cf_path, 'rb') as f:
        data = f.read()

    if data[:4] != V8_SIGNATURE:
        raise ValueError(f"Файл {cf_path} не является контейнером 1С (нет сигнатуры 0xFF 0xFF 0xFF 0x7F)")

    container = V8Container(data, 0)
    container.read()
    return container.extract(output_dir, recursive=recursive)


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 cf_extractor.py <file.cf> <output_dir>")
        print()
        print("Пример:")
        print("  python3 cf_extractor.py ut11.cf data/configs/ut11")
        sys.exit(1)

    cf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not cf_path.exists():
        print(f"❌ Файл не найден: {cf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Распаковка: {cf_path}")
    print(f"В: {output_dir}")
    print(f"Размер файла: {cf_path.stat().st_size / 1024 / 1024:.1f} МБ")

    try:
        count = extract_cf(cf_path, output_dir)
        print(f"\n✅ Распаковано файлов: {count}")
        print(f"   Каталог: {output_dir}")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
