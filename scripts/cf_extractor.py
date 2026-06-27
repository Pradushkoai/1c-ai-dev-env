#!/usr/bin/env python3
"""
cf_extractor.py — Распаковщик .cf/.cfe/.epf файлов 1С.

Формат контейнера 1С (на основе изучения исходников v8unpack и реальных .cf):

ЗАГОЛОВОК КОНТЕЙНЕРА (16 байт, 4 int32 LE):
  - 4 байта: сигнатура 0xFF 0xFF 0xFF 0x7F (= 0x7FFFFFFF = END_MARKER)
  - 4 байта: first_empty_block_offset
  - 4 байта: default_block_size (обычно 0x200 = 512)
  - 4 байта: count_files (часто 0, не используется — реальное кол-во из TOC)

БЛОК ДАННЫХ (заголовок 31 байт, формат '2s8s1s8s1s8s1s2s'):
  - 2 байта: \r\n (разделитель)
  - 8 байт: doc_size в hex (например "0000003c" = 60)
  - 1 байт: пробел
  - 8 байт: current_block_size в hex (например "00000200" = 512)
  - 1 байт: пробел
  - 8 байт: next_block_offset в hex (например "7fffffff" = END_MARKER)
  - 1 байт: пробел
  - 2 байта: \r\n (разделитель)
После заголовка — данные блока (current_block_size байт).

ПЕРВЫЙ ДОКУМЕНТ ПОСЛЕ ЗАГОЛОВКА — TOC (оглавление):
TOC содержит массив записей по 12 байт (3 int32 LE):
  - 4 байта: file_description_offset
  - 4 байта: file_data_offset
  - 4 байта: END_MARKER (terminator каждой записи)
Запись-терминатор всего TOC: пара (0, END_MARKER) или аналогично.

FILE_DESCRIPTION (структура):
  - 8 байт: created (datetime)
  - 8 байт: modified (datetime)
  - 4 байта: длина имени файла
  - N байт: имя файла в UTF-16 LE

FILE_DATA:
  Цепочка блоков (как документ). Если первый байт данных = 0xFF 0xFF 0xFF 0x7F —
  это вложенный контейнер (рекурсивно извлекаем). Иначе — raw deflate сжатые данные
  (zlib raw, wbits=-15) или несжатые данные.

Имена файлов в .cf:
  - "version", "versions", "root" — служебные
  - UUID (например "30ffe4cc-eef2-4371-8b26-046597e37e22") — метаданные или контейнеры

Использование:
    python3 cf_extractor.py <file.cf> <output_dir>

Пример:
    python3 cf_extractor.py ut11.cf data/configs/ut11
"""
from __future__ import annotations

import struct
import sys
import zlib
from collections import OrderedDict
from pathlib import Path

# Сигнатура контейнера 1С
V8_SIGNATURE = b'\xFF\xFF\xFF\x7F'
END_MARKER = 0x7FFFFFFF  # 2147483647

# Размеры
HEADER_SIZE = 16          # 4 int32
BLOCK_HEADER_SIZE = 31    # 2+8+1+8+1+8+1+2
DEFAULT_BLOCK_SIZE = 0x200  # 512
INDEX_BLOCK_SIZE = 0x200    # 512

# Формат заголовка блока: \r\n + hex(8) + ' ' + hex(8) + ' ' + hex(8) + ' ' + \r\n
BLOCK_HEADER_FMT = '2s8s1s8s1s8s1s2s'


class V8Block:
    """Блок данных в контейнере 1С."""
    __slots__ = ('doc_size', 'current_block_size', 'next_block_offset', 'data')

    def __init__(self, doc_size: int, current_block_size: int,
                 next_block_offset: int, data: bytes):
        self.doc_size = doc_size
        self.current_block_size = current_block_size
        self.next_block_offset = next_block_offset
        self.data = data


class V8Container:
    """Контейнер 1С — формат хранения .cf/.cfe/.epf файлов."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset
        self.first_empty_block_offset = 0
        self.default_block_size = DEFAULT_BLOCK_SIZE
        self.files: OrderedDict[str, bytes] = OrderedDict()
        self.size = 0

    def read(self) -> None:
        """Прочитать заголовок и все файлы."""
        self._read_header()
        self._read_files()

    def _read_header(self) -> None:
        """Читает 16-байтный заголовок контейнера."""
        if self.data[self.offset:self.offset + 4] != V8_SIGNATURE:
            raise ValueError(
                f"Неверная сигнатура контейнера по смещению {self.offset}"
            )
        sig, default_block_size, count_files, _ = struct.unpack_from(
            '<4i', self.data, self.offset
        )
        # header[0] = 0x7FFFFFFF (сигнатура/END_MARKER)
        # header[1] = default_block_size (обычно 512)
        # header[2] = count_files
        # header[3] = 0 (не используется)
        self.first_empty_block_offset = END_MARKER
        self.default_block_size = default_block_size if default_block_size else DEFAULT_BLOCK_SIZE
        self.size += HEADER_SIZE

    def _read_block(self, file_offset: int, max_data_length: int = None) -> V8Block:
        """
        Читает один блок по смещению.
        Возвращает V8Block с данными.
        """
        abs_offset = self.offset + file_offset
        header_bytes = self.data[abs_offset:abs_offset + BLOCK_HEADER_SIZE]
        if len(header_bytes) < BLOCK_HEADER_SIZE:
            return V8Block(0, 0, END_MARKER, b'')

        parts = struct.unpack(BLOCK_HEADER_FMT, header_bytes)
        # parts: (b'\r\n', b'0000003c', b' ', b'00000200', b' ', b'7fffffff', b' ', b'\r\n')
        try:
            doc_size = int(parts[1], 16)
            current_block_size = int(parts[3], 16)
            next_block_offset = int(parts[5], 16)
        except ValueError:
            return V8Block(0, 0, END_MARKER, b'')

        if max_data_length is None:
            max_data_length = min(current_block_size, doc_size)

        data_size = min(current_block_size, max_data_length)
        data_start = abs_offset + BLOCK_HEADER_SIZE
        block_data = self.data[data_start:data_start + data_size]

        return V8Block(doc_size, current_block_size, next_block_offset, block_data)

    def _read_document(self, file_offset: int, min_block_size: int = 0) -> bytes:
        """
        Читает документ (цепочку блоков) целиком.
        Возвращает все данные документа.
        """
        result = b''
        current_offset = file_offset
        left_bytes = None
        max_iterations = 100000  # защита от зацикливания

        for _ in range(max_iterations):
            if current_offset >= len(self.data) - BLOCK_HEADER_SIZE:
                break
            if current_offset == END_MARKER or current_offset < 0:
                break

            max_data = None if left_bytes is None else left_bytes
            block = self._read_block(current_offset, max_data)
            if not block.data and block.doc_size == 0:
                break

            if left_bytes is None:
                # Первый блок — определяем общий размер
                left_bytes = block.doc_size

            result += block.data
            left_bytes -= len(block.data)

            if left_bytes <= 0 or block.next_block_offset == END_MARKER:
                break
            current_offset = block.next_block_offset

        return result

    def _read_files(self) -> None:
        """Читает TOC и все файлы контейнера."""
        # Первый документ после заголовка — TOC
        toc_data = self._read_document(HEADER_SIZE, INDEX_BLOCK_SIZE)
        # TOC содержит тройки (file_description_offset, file_data_offset, END_MARKER)
        # Каждая запись — 12 байт (3 int32 LE)
        entry_size = 12
        entries = []
        for i in range(0, len(toc_data) - entry_size + 1, entry_size):
            desc_offset, data_offset, terminator = struct.unpack_from(
                '<3i', toc_data, i
            )
            if desc_offset == END_MARKER or desc_offset == 0:
                break
            if data_offset == END_MARKER or data_offset == 0:
                break
            entries.append((desc_offset, data_offset))

        # Читаем каждый файл
        for desc_offset, data_offset in entries:
            # Читаем описание файла
            desc_data = self._read_document(desc_offset)
            if len(desc_data) < 20:
                continue

            # Формат: created(8) + modified(8) + unknown(4) + name(UTF-16 LE, до конца)
            # Имя читается как desc_data[20:].decode('utf-16-le').split('\x00')[0]
            name_bytes = desc_data[20:]
            try:
                name = name_bytes.decode('utf-16-le').split('\x00')[0]
            except UnicodeDecodeError:
                name = name_bytes.decode('utf-16-le', errors='replace').split('\x00')[0]

            if not name:
                continue

            # Читаем данные файла
            file_data = self._read_document(data_offset, self.default_block_size)
            self.files[name] = file_data

    def extract(self, output_dir: Path, deflate: bool = True,
                recursive: bool = True, progress_prefix: str = '') -> int:
        """
        Извлечь файлы из контейнера.
        Возвращает количество извлечённых файлов.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted = 0

        for name, file_data in self.files.items():
            if not name:
                continue

            # Если данные сжаты (deflate) — пробуем распаковать
            if deflate:
                try:
                    file_data = zlib.decompress(file_data, -15)
                except zlib.error:
                    pass  # данные не сжаты

            # Определяем, является ли файл вложенным контейнером
            is_container = file_data[:4] == V8_SIGNATURE

            # Безопасное имя файла
            safe_name = name.replace('/', '_').replace('\\', '_').replace(':', '_')
            file_path = output_dir / safe_name

            if is_container and recursive:
                # Рекурсивно извлекаем вложенный контейнер
                try:
                    nested = V8Container(file_data, 0)
                    nested.read()
                    extracted += nested.extract(
                        file_path, deflate, recursive,
                        progress_prefix + name + '/'
                    )
                except Exception:
                    # Если не удалось — сохраняем как .bin
                    file_path = file_path.with_suffix('.bin')
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    extracted += 1
            else:
                # Определяем расширение по содержимому
                if file_data[:5] == b'<?xml':
                    if file_path.suffix != '.xml':
                        file_path = file_path.with_suffix('.xml')
                elif file_data[:2] == b'PK':
                    if file_path.suffix != '.bin':
                        file_path = file_path.with_suffix('.bin')
                elif file_path.suffix == '':
                    # Если нет расширения — оставляем как есть
                    pass

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
        raise ValueError(
            f"Файл {cf_path} не является контейнером 1С "
            f"(нет сигнатуры 0xFF 0xFF 0xFF 0x7F)"
        )

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
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
