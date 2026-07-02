#!/usr/bin/env python3
"""
cf_extractor.py — Распаковщик .cf/.cfe/.epf файлов 1С.

Поддерживает два формата контейнеров 1С:
1. Container (32-битный) — сигнатура 0xFF 0xFF 0xFF 0x7F (4 байта)
2. Container64 (64-битный) — сигнатура 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF 0xFF (8 байт)

Формат контейнера (32-битный, на основе v8unpack):
- Заголовок (16 байт): sig(4)=0x7FFFFFFF + default_block_size(4)=512 + count_files(4) + reserved(4)
- Блоки данных с текстовым заголовком 31 байт:
  \\r\\n + hex(8) + ' ' + hex(8) + ' ' + hex(8) + ' ' + \\r\\n
- TOC: тройки (desc_offset, data_offset, END_MARKER) по 12 байт
- file_description: created(8) + modified(8) + unknown(4) + name(UTF-16 LE, до конца)

Container64 (64-битный):
- Заголовок (20 байт): sig(8)=0xFFFFFFFFFFFFFFFF + default_block_size(4) + count_files(4) + reserved(4)
- Блоки с заголовком 55 байт: \\r\\n + hex(16) + ' ' + hex(16) + ' ' + hex(16) + ' ' + \\r\\n
- TOC: тройки по 24 байта (3 × int64/Q)
- INDEX_BLOCK_SIZE = 0x10000 (65536)

.cf файл содержит:
- Контейнер 0 (32-битный) — корневые метаданные (version, versions, root, UUID-файлы)
- Контейнер 1 (часто 64-битный) — все объекты метаданных (Catalogs, Documents, CommonModules)

Использование:
    python3 cf_extractor.py <file.cf> <output_dir>
"""

from __future__ import annotations

import struct
import sys
import zlib
from collections import OrderedDict
from pathlib import Path

# Сигнатуры контейнеров 1С
V8_SIGNATURE = b"\xff\xff\xff\x7f"  # 32-битный (4 байта)
V8_SIGNATURE_64 = b"\xff\xff\xff\xff\xff\xff\xff\xff"  # 64-битный (8 байт)
END_MARKER = 0x7FFFFFFF
END_MARKER_64 = 0xFFFFFFFFFFFFFFFF

# Размеры для 32-битного контейнера
HEADER_SIZE = 16
BLOCK_HEADER_SIZE = 31
DEFAULT_BLOCK_SIZE = 0x200  # 512
INDEX_BLOCK_SIZE = 0x200  # 512
BLOCK_HEADER_FMT = "2s8s1s8s1s8s1s2s"

# Размеры для 64-битного контейнера
HEADER_SIZE_64 = 20
BLOCK_HEADER_SIZE_64 = 55
DEFAULT_BLOCK_SIZE_64 = 0x10000  # 65536
INDEX_BLOCK_SIZE_64 = 0x10000
BLOCK_HEADER_FMT_64 = "2s16s1s16s1s16s1s2s"


class V8Block:
    """Блок данных в контейнере 1С."""

    __slots__ = ("doc_size", "current_block_size", "next_block_offset", "data")

    def __init__(self, doc_size: int, current_block_size: int, next_block_offset: int, data: bytes):
        self.doc_size = doc_size
        self.current_block_size = current_block_size
        self.next_block_offset = next_block_offset
        self.data = data


class V8Container:
    """Контейнер 1С — формат хранения .cf/.cfe/.epf файлов. Поддерживает 32 и 64 бита."""

    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset
        self.is_64bit = False
        self.first_empty_block_offset = 0
        self.default_block_size = DEFAULT_BLOCK_SIZE
        self.index_block_size = INDEX_BLOCK_SIZE
        self.end_marker = END_MARKER
        self.block_header_size = BLOCK_HEADER_SIZE
        self.block_header_fmt = BLOCK_HEADER_FMT
        self.files: OrderedDict[str, bytes] = OrderedDict()
        self.size = 0

    def read(self) -> None:
        """Прочитать заголовок и все файлы."""
        self._detect_format()
        self._read_header()
        self._read_files()

    def _detect_format(self) -> None:
        """Определяет формат контейнера (32 или 64 бита)."""
        sig = self.data[self.offset : self.offset + 8]
        if sig[:4] == V8_SIGNATURE:
            self.is_64bit = False
            self.block_header_size = BLOCK_HEADER_SIZE
            self.block_header_fmt = BLOCK_HEADER_FMT
            self.index_block_size = INDEX_BLOCK_SIZE
            self.end_marker = END_MARKER
        elif sig == V8_SIGNATURE_64:
            self.is_64bit = True
            self.block_header_size = BLOCK_HEADER_SIZE_64
            self.block_header_fmt = BLOCK_HEADER_FMT_64
            self.index_block_size = INDEX_BLOCK_SIZE_64
            self.end_marker = END_MARKER_64
        else:
            raise ValueError(f"Неверная сигнатура контейнера по смещению {self.offset}")

    def _read_header(self) -> None:
        """Читает заголовок контейнера."""
        if self.is_64bit:
            # 1Q3i: sig(8) + default_block_size(4) + count_files(4) + reserved(4) = 20
            sig, default_block_size, count_files, _ = struct.unpack_from("<Q3i", self.data, self.offset)
            self.default_block_size = default_block_size if default_block_size else DEFAULT_BLOCK_SIZE_64
            self.size += HEADER_SIZE_64
        else:
            sig, default_block_size, count_files, _ = struct.unpack_from("<4i", self.data, self.offset)
            self.default_block_size = default_block_size if default_block_size else DEFAULT_BLOCK_SIZE
            self.size += HEADER_SIZE

        self.first_empty_block_offset = self.end_marker

    def _read_block(self, file_offset: int, max_data_length: int = None) -> V8Block:
        """Читает один блок по смещению."""
        abs_offset = self.offset + file_offset
        header_bytes = self.data[abs_offset : abs_offset + self.block_header_size]
        if len(header_bytes) < self.block_header_size:
            return V8Block(0, 0, self.end_marker, b"")

        parts = struct.unpack(self.block_header_fmt, header_bytes)
        # parts: (\r\n, hex_doc_size, ' ', hex_block_size, ' ', hex_next, ' ', \r\n)
        try:
            doc_size = int(parts[1], 16)
            current_block_size = int(parts[3], 16)
            next_block_offset = int(parts[5], 16)
        except ValueError:
            return V8Block(0, 0, self.end_marker, b"")

        if max_data_length is None:
            max_data_length = min(current_block_size, doc_size)

        data_size = min(current_block_size, max_data_length)
        data_start = abs_offset + self.block_header_size
        block_data = self.data[data_start : data_start + data_size]

        return V8Block(doc_size, current_block_size, next_block_offset, block_data)

    def _read_document(self, file_offset: int, min_block_size: int = 0) -> tuple[bytes, int]:
        """Читает документ (цепочку блоков). Возвращает (данные, полный_размер)."""
        result = b""
        current_offset = file_offset
        left_bytes = None
        max_iterations = 100000
        total_size = 0

        for _ in range(max_iterations):
            if current_offset >= len(self.data) - self.block_header_size:
                break
            if current_offset == self.end_marker or current_offset < 0:
                break

            max_data = None if left_bytes is None else left_bytes
            block = self._read_block(current_offset, max_data)
            if not block.data and block.doc_size == 0:
                break

            if left_bytes is None:
                left_bytes = block.doc_size

            result += block.data
            left_bytes -= len(block.data)
            total_size += self.block_header_size + block.current_block_size

            if left_bytes <= 0 or block.next_block_offset == self.end_marker:
                break
            current_offset = block.next_block_offset

        return result, total_size

    def _read_files(self) -> None:
        """Читает TOC и все файлы контейнера."""
        header_size = HEADER_SIZE_64 if self.is_64bit else HEADER_SIZE
        # TOC: тройки (desc_offset, data_offset, end_marker)
        # 32-бит: 3 × int32 = 12 байт; 64-бит: 3 × int64 = 24 байта
        entry_size = 24 if self.is_64bit else 12
        entry_fmt = "<3Q" if self.is_64bit else "<3i"

        toc_data, toc_size = self._read_document(header_size, self.index_block_size)
        entries = []
        for i in range(0, len(toc_data) - entry_size + 1, entry_size):
            desc_offset, data_offset, terminator = struct.unpack_from(entry_fmt, toc_data, i)
            if desc_offset == self.end_marker or desc_offset == 0:
                break
            if data_offset == self.end_marker or data_offset == 0:
                break
            entries.append((desc_offset, data_offset))

        max_end = header_size + toc_size
        for desc_offset, data_offset in entries:
            desc_data, desc_size = self._read_document(desc_offset)
            if len(desc_data) < 20:
                continue

            name_bytes = desc_data[20:]
            try:
                name = name_bytes.decode("utf-16-le").split("\x00")[0]
            except UnicodeDecodeError:
                name = name_bytes.decode("utf-16-le", errors="replace").split("\x00")[0]

            if not name:
                continue

            file_data, data_size = self._read_document(data_offset, self.default_block_size)
            self.files[name] = file_data

            max_end = max(max_end, desc_offset + desc_size)
            max_end = max(max_end, data_offset + data_size)

        self.size = max_end

    def extract(self, output_dir: Path, deflate: bool = True, recursive: bool = True, progress_prefix: str = "") -> int:
        """Извлечь файлы из контейнера."""
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted = 0

        for name, file_data in self.files.items():
            if not name:
                continue

            if deflate:
                try:
                    file_data = zlib.decompress(file_data, -15)
                except zlib.error:
                    pass

            is_container = file_data[:4] == V8_SIGNATURE or file_data[:8] == V8_SIGNATURE_64

            safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
            file_path = output_dir / safe_name

            if is_container and recursive:
                try:
                    nested = V8Container(file_data, 0)
                    nested.read()
                    extracted += nested.extract(file_path, deflate, recursive, progress_prefix + name + "/")
                except Exception:
                    file_path = file_path.with_suffix(".bin")
                    with open(file_path, "wb") as f:
                        f.write(file_data)
                    extracted += 1
            else:
                if file_data[:5] == b"<?xml":
                    if file_path.suffix != ".xml":
                        file_path = file_path.with_suffix(".xml")
                elif file_path.suffix == "":
                    pass

                with open(file_path, "wb") as f:
                    f.write(file_data)
                extracted += 1

        return extracted


def extract_cf(cf_path: Path, output_dir: Path, recursive: bool = True) -> int:
    """
    Распаковать .cf/.cfe/.epf файл в указанную директорию.

    .cf файл содержит несколько последовательно идущих контейнеров:
    - Контейнер 0 (32-битный) — корневые метаданные
    - Контейнер 1 (часто 64-битный) — все объекты метаданных

    Args:
        cf_path: Путь к .cf файлу
        output_dir: Куда распаковывать
        recursive: Рекурсивно извлекать вложенные контейнеры

    Returns:
        Количество извлечённых файлов
    """
    with open(cf_path, "rb") as f:
        data = f.read()

    if data[:4] != V8_SIGNATURE and data[:8] != V8_SIGNATURE_64:
        raise ValueError(f"Файл {cf_path} не является контейнером 1С")

    output_dir.mkdir(parents=True, exist_ok=True)
    total_extracted = 0
    container_index = 0
    offset = 0

    while offset < len(data) - HEADER_SIZE:
        # Ищем любую из сигнатур
        pos_32 = data.find(V8_SIGNATURE, offset)
        pos_64 = data.find(V8_SIGNATURE_64, offset)

        if pos_32 == -1 and pos_64 == -1:
            break
        if pos_32 == -1:
            sig_pos = pos_64
        elif pos_64 == -1:
            sig_pos = pos_32
        else:
            sig_pos = min(pos_32, pos_64)

        try:
            container = V8Container(data, sig_pos)
            container.read()

            if not container.files:
                offset = sig_pos + 4
                continue

            container_dir = output_dir / str(container_index)
            extracted = container.extract(container_dir, recursive=recursive)
            if extracted > 0:
                total_extracted += extracted
                container_index += 1

            next_offset = sig_pos + max(container.size, HEADER_SIZE)
            if next_offset <= offset:
                next_offset = offset + 4
            offset = next_offset

        except Exception:
            offset = sig_pos + 4

    return total_extracted


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
