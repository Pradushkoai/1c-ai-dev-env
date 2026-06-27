"""
Тесты для cf_extractor.py.
Проверяем парсинг формата контейнера 1С на синтетических данных.

Формат контейнера 1С (на основе изучения реальных .cf файлов):
- Заголовок (16 байт): sig(4) + default_block_size(4) + count_files(4) + reserved(4)
- Блоки данных с текстовым заголовком 31 байт:
  \r\n + hex(8) + ' ' + hex(8) + ' ' + hex(8) + ' ' + \r\n
- TOC: тройки (desc_offset, data_offset, END_MARKER) по 12 байт
- file_description: created(8) + modified(8) + unknown(4) + name(UTF-16 LE, до конца)
"""
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cf_extractor import (
    V8Container, V8_SIGNATURE, END_MARKER,
    HEADER_SIZE, BLOCK_HEADER_SIZE, DEFAULT_BLOCK_SIZE,
    extract_cf
)


# ============================================================================
# ХЕЛПЕРЫ ДЛЯ СОЗДАНИЯ СИНТЕТИЧЕСКИХ КОНТЕЙНЕРОВ
# ============================================================================

def make_block_header(doc_size: int, current_block_size: int = 512,
                      next_offset: int = END_MARKER) -> bytes:
    """Создаёт 31-байтный заголовок блока (текстовый формат)."""
    return (
        b'\r\n'
        + f'{doc_size:08x}'.encode('ascii')
        + b' '
        + f'{current_block_size:08x}'.encode('ascii')
        + b' '
        + f'{next_offset & 0xFFFFFFFF:08x}'.encode('ascii')
        + b' \r\n'
    )


def make_block(data: bytes, next_offset: int = END_MARKER,
               block_size: int = 512) -> bytes:
    """Создаёт блок (заголовок + данные)."""
    doc_size = len(data)
    header = make_block_header(doc_size, block_size, next_offset)
    # Дополняем данные до block_size (как в реальном формате)
    padded_data = data + b'\x00' * (block_size - len(data)) if len(data) < block_size else data
    return header + padded_data[:block_size]


def make_file_description(name: str, created: int = 0, modified: int = 0) -> bytes:
    """Создаёт file_description (created + modified + unknown + name)."""
    name_utf16 = name.encode('utf-16-le') + b'\x00\x00'
    return struct.pack('<QQI', created, modified, 0) + name_utf16


def raw_deflate(data: bytes) -> bytes:
    """Сжатие в raw deflate (без заголовков zlib)."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(data) + compressor.flush()


def make_container(files: list[tuple[str, bytes]]) -> bytes:
    """
    Создаёт синтетический .cf контейнер.

    Args:
        files: [(name, data), ...] — простые файлы (несжатые)

    Returns:
        bytes — содержимое .cf файла
    """
    # Заголовок: sig(4) + default_block_size(4) + count_files(4) + reserved(4)
    header = struct.pack('<4i',
        END_MARKER,           # 0x7FFFFFFF
        DEFAULT_BLOCK_SIZE,   # 512
        len(files),           # count_files
        0                     # reserved
    )

    # TOC: тройки (desc_offset, data_offset, END_MARKER)
    # Сначала "резервируем" место для TOC (один блок)
    # После TOC идут file_descriptions, потом file_data
    toc_block_size = DEFAULT_BLOCK_SIZE
    toc_entries = []
    for i, (name, data) in enumerate(files):
        # desc_offset и data_offset вычисляются позже
        toc_entries.append((0, 0))  # placeholder

    # Создаём TOC данные
    toc_data = b''
    for desc_off, data_off in toc_entries:
        toc_data += struct.pack('<3i', desc_off, data_off, END_MARKER)

    # Заголовок + TOC блок (с данными toc_data)
    toc_block = make_block(toc_data, END_MARKER, DEFAULT_BLOCK_SIZE)

    # После TOC: file_descriptions (каждый в отдельном блоке)
    # Затем: file_data (каждый в отдельном блоке)
    current_offset = HEADER_SIZE + DEFAULT_BLOCK_SIZE + BLOCK_HEADER_SIZE  # после TOC блока

    # file_descriptions
    desc_blocks = []
    desc_offsets = []
    for name, _ in files:
        desc_offsets.append(current_offset)
        desc_data = make_file_description(name)
        desc_block = make_block(desc_data, END_MARKER, DEFAULT_BLOCK_SIZE)
        desc_blocks.append(desc_block)
        current_offset += BLOCK_HEADER_SIZE + DEFAULT_BLOCK_SIZE

    # file_data
    data_blocks = []
    data_offsets = []
    for _, data in files:
        data_offsets.append(current_offset)
        data_block = make_block(data, END_MARKER, DEFAULT_BLOCK_SIZE)
        data_blocks.append(data_block)
        current_offset += BLOCK_HEADER_SIZE + DEFAULT_BLOCK_SIZE

    # Теперь пересобираем TOC с правильными offset'ами
    toc_data = b''
    for desc_off, data_off in zip(desc_offsets, data_offsets):
        toc_data += struct.pack('<3i', desc_off, data_off, END_MARKER)
    toc_block = make_block(toc_data, END_MARKER, DEFAULT_BLOCK_SIZE)

    # Собираем всё вместе
    content = header + toc_block
    for db in desc_blocks:
        content += db
    for db in data_blocks:
        content += db

    return content


# ============================================================================
# ТЕСТЫ
# ============================================================================

def test_v8_signature():
    """Проверка сигнатуры контейнера."""
    assert V8_SIGNATURE == b'\xFF\xFF\xFF\x7F'
    assert END_MARKER == 0x7FFFFFFF


def test_extract_cf_invalid_file(tmp_path):
    """extract_cf падает на файле без сигнатуры."""
    bad_file = tmp_path / "bad.cf"
    bad_file.write_bytes(b"NOT A CF FILE")

    with pytest.raises(ValueError, match="не является контейнером"):
        extract_cf(bad_file, tmp_path / "out")


def test_extract_cf_nonexistent(tmp_path):
    """extract_cf падает на несуществующем файле."""
    with pytest.raises((FileNotFoundError, OSError)):
        extract_cf(tmp_path / "nope.cf", tmp_path / "out")


def test_container_read_header(tmp_path):
    """V8Container правильно читает заголовок."""
    container_data = make_container([
        ('version', b'2.0'),
        ('root', b'<root/>'),
    ])

    container = V8Container(container_data, 0)
    container._read_header()

    assert container.default_block_size == DEFAULT_BLOCK_SIZE
    assert container.first_empty_block_offset == END_MARKER


def test_container_read_files(tmp_path):
    """V8Container правильно читает файлы из контейнера."""
    container_data = make_container([
        ('version', b'2.0'),
        ('root', b'<root/>'),
        ('test', b'data'),
    ])

    container = V8Container(container_data, 0)
    container.read()

    assert len(container.files) == 3
    assert 'version' in container.files
    assert 'root' in container.files
    assert 'test' in container.files


def test_extract_simple_files(tmp_path):
    """Извлечение простых файлов из контейнера."""
    test_files = [
        ('version', b'2.0'),
        ('root', b'<Configuration><Name>Test</Name></Configuration>'),
    ]

    container_data = make_container(test_files)
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 2
    assert (out_dir / "version").exists()
    assert (out_dir / "root").exists()


def test_extract_preserves_data(tmp_path):
    """Данные файлов сохраняются без искажений."""
    original_data = b'{2,1,"test",\n{1,"ru","Test"}}'
    container_data = make_container([
        ('metadata', original_data),
    ])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    extract_cf(cf_path, out_dir)

    extracted = (out_dir / "metadata").read_bytes()
    # Данные могут быть дополнены нулями, берём оригинальную длину
    assert extracted[:len(original_data)] == original_data


def test_extract_multiple_files(tmp_path):
    """Извлечение нескольких файлов."""
    files = [
        (f'file{i}', f'content {i}'.encode())
        for i in range(5)
    ]
    container_data = make_container(files)

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count == 5
    for i in range(5):
        assert (out_dir / f'file{i}').exists()


def test_extract_uuid_named_files(tmp_path):
    """Извлечение файлов с UUID именами (как в реальных .cf)."""
    uuid_name = '30ffe4cc-eef2-4371-8b26-046597e37e22'
    container_data = make_container([
        ('version', b'2.0'),
        ('root', b'{2,uuid,hash}'),
        (uuid_name, b'{1,"metadata"}'),
    ])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count == 3
    assert (out_dir / uuid_name).exists()


def test_make_container_helper():
    """Хелпер make_container создаёт валидный контейнер."""
    container_data = make_container([('version', b'1.0')])

    # Должен начинаться с сигнатуры
    assert container_data[:4] == V8_SIGNATURE

    # V8Container должен уметь его прочитать
    container = V8Container(container_data, 0)
    container.read()
    assert len(container.files) == 1
    assert 'version' in container.files


def test_make_block_header_format():
    """Заголовок блока имеет правильный текстовый формат."""
    header = make_block_header(60, 512, END_MARKER)
    assert len(header) == BLOCK_HEADER_SIZE
    assert header.startswith(b'\r\n')
    assert header.endswith(b' \r\n')
    # doc_size = 60 = 0x3c, в hex = "0000003c"
    assert b'0000003c' in header
    # block_size = 512 = 0x200, в hex = "00000200"
    assert b'00000200' in header
    # next_offset = END_MARKER = 0x7FFFFFFF
    assert b'7fffffff' in header


def test_make_file_description_format():
    """file_description имеет правильный формат."""
    desc = make_file_description('test_file')
    # created(8) + modified(8) + unknown(4) + name(UTF-16 LE + null terminator)
    assert len(desc) >= 20
    # Имя должно быть в UTF-16 LE
    name_part = desc[20:]
    name = name_part.decode('utf-16-le').split('\x00')[0]
    assert name == 'test_file'


def test_extract_creates_output_dir(tmp_path):
    """extract_cf создаёт выходную директорию если её нет."""
    container_data = make_container([('test', b'data')])
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "new_dir" / "subdir"
    extract_cf(cf_path, out_dir)

    assert out_dir.exists()
    assert (out_dir / "test").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
