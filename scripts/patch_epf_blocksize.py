#!/usr/bin/env python3
"""
patch_epf_blocksize.py — Пропатчивает .epf: block_size во ВСЕХ блоках → 512.

Проблема: v8unpack 1.2.6 пишет block_size = doc_size (фактический размер данных),
а 1С ожидает всегда block_size = 0x200 (512). Из-за этого "Ошибка формата потока".

Структура V8 контейнера:
  - Header (16 байт): sig + block_size + num_files + reserved
  - TOC block: заголовок 31 байт + данные (num_files × 12 байт: desc/data/next)
  - Для каждого файла: description block (по desc_offset) + data block (по data_offset)

Каждый блок имеет заголовок: \\r\\n + 8hex(doc_size) + ' ' + 8hex(block_size) + ' ' + 8hex(next) + ' \\r\\n

Патчер проходит по всем блокам (TOC + все desc + все data) и заменяет
block_size на 512.

Использование:
    python patch_epf_blocksize.py <input.epf> <output.epf>
"""
import struct
import sys
from pathlib import Path

V8_SIGNATURE = 0x7FFFFFFF
END_MARKER = 0x7FFFFFFF
STANDARD_BLOCK_SIZE = 512  # 0x200
HEADER_SIZE = 16
BLOCK_HEADER_SIZE = 31  # \r\n + 8hex + ' ' + 8hex + ' ' + 8hex + ' \r\n
ENTRY_SIZE = 12  # 3 × uint32


def parse_block_header(data: bytes, offset: int) -> dict | None:
    """Распарсить заголовок блока по offset.

    Возвращает dict: {doc_size, block_size, next_block, header_size}
    или None если это не блок.
    """
    if offset + BLOCK_HEADER_SIZE > len(data):
        return None
    header_bytes = data[offset:offset + BLOCK_HEADER_SIZE]
    if header_bytes[:2] != b'\r\n':
        return None
    # Парсим: \r\n + 8hex + ' ' + 8hex + ' ' + 8hex + ' \r\n
    try:
        text = header_bytes.decode('ascii')
    except UnicodeDecodeError:
        return None
    # Формат: "\r\n00000054 00000200 7fffffff \r\n"
    parts = text.strip().split()
    if len(parts) != 3:
        return None
    try:
        return {
            'doc_size': int(parts[0], 16),
            'block_size': int(parts[1], 16),
            'next_block': int(parts[2], 16),
            'header_size': BLOCK_HEADER_SIZE,
        }
    except ValueError:
        return None


def make_block_header(doc_size: int, block_size: int, next_block: int) -> bytes:
    """Создать новый заголовок блока (31 байт)."""
    return f'\r\n{doc_size:08x} {block_size:08x} {next_block:08x} \r\n'.encode('ascii')


def patch_epf(input_path: str | Path, output_path: str | Path) -> dict:
    """Пропатчить .epf файл: TOC block_size → 512.

    Анализ оригинального EPF (открывается в 1С):
      - Header block_size = 0x200 (всегда 512)
      - TOC block_size = 0x200 (всегда 512)
      - Description/data blocks: block_size = doc_size (фактический размер)

    v8unpack 1.2.6 пишет:
      - Header block_size = 0x200 (правильно)
      - TOC block_size = doc_size (НЕПРАВИЛЬНО, должен быть 0x200)
      - Description/data blocks: block_size = doc_size (правильно)

    Поэтому патчим ТОЛЬКО TOC block_size на 0x200.

    Args:
        input_path: исходный .epf (от v8unpack)
        output_path: куда сохранить пропатченный

    Returns:
        dict: {ok, error, blocks_patched, block_details}
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    if len(data) < HEADER_SIZE:
        return {"ok": False, "error": "Файл слишком маленький"}

    # Header
    sig, header_block_size, num_files, reserved = struct.unpack_from("<IIII", data, 0)
    if sig != V8_SIGNATURE:
        return {"ok": False, "error": f"Неверная сигнатура: {sig:08x}"}

    blocks_patched = 0
    block_details = []

    # 1. Header block_size → 512 (если не 512)
    if header_block_size != STANDARD_BLOCK_SIZE:
        struct.pack_into("<I", data, 4, STANDARD_BLOCK_SIZE)
        block_details.append({
            "type": "header",
            "offset": 4,
            "old": header_block_size,
            "new": STANDARD_BLOCK_SIZE,
        })
        blocks_patched += 1

    # 2. TOC block_size → 512 (КРИТИЧНО!)
    # TOC находится сразу после header, по offset 16
    toc_offset = HEADER_SIZE
    toc_header = parse_block_header(data, toc_offset)
    if toc_header is None:
        return {"ok": False, "error": "TOC block header не найден"}

    if toc_header['block_size'] != STANDARD_BLOCK_SIZE:
        new_header = make_block_header(
            toc_header['doc_size'],
            STANDARD_BLOCK_SIZE,
            toc_header['next_block'],
        )
        data[toc_offset:toc_offset + BLOCK_HEADER_SIZE] = new_header
        block_details.append({
            "type": "toc",
            "offset": toc_offset,
            "old": toc_header['block_size'],
            "new": STANDARD_BLOCK_SIZE,
        })
        blocks_patched += 1

    # Description/data blocks НЕ ТРОГАЕМ — у них block_size = doc_size (как в оригинале)

    # Сохраняем
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)

    return {
        "ok": True,
        "blocks_patched": blocks_patched,
        "block_details": block_details,
        "size_bytes": len(data),
    }


def main():
    if len(sys.argv) != 3:
        print("Использование: python patch_epf_blocksize.py <input.epf> <output.epf>")
        sys.exit(1)

    result = patch_epf(sys.argv[1], sys.argv[2])
    print(f"OK: {result['ok']}")
    print(f"Blocks patched: {result.get('blocks_patched', 0)} / {result.get('total_blocks', 0)}")
    print(f"Size: {result.get('size_bytes', 0)} bytes")
    if result.get('block_details'):
        print("\nPatched blocks:")
        for b in result['block_details']:
            print(f"  {b['type']} @ {b['offset']:08x}: {b['old']:08x} → {b['new']:08x}")
    if not result["ok"]:
        print(f"Error: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
