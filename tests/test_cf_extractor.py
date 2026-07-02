"""
Тесты для cf_extractor.py.
Проверяем парсинг формата контейнера 1С (32 и 64 бита) на синтетических данных.

Формат контейнера 1С:
- 32-битный: сигнатура 0xFF 0xFF 0xFF 0x7F (4 байта)
- 64-битный: сигнатура 0xFF×8 (8 байт)

Структура:
- Заголовок (16 или 20 байт)
- Блоки данных с текстовым заголовком (31 или 55 байт)
- TOC: тройки (desc_offset, data_offset, END_MARKER)
- file_description: created(8) + modified(8) + unknown(4) + name(UTF-16 LE)
"""

import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cf_extractor import (
    BLOCK_HEADER_SIZE,
    BLOCK_HEADER_SIZE_64,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_BLOCK_SIZE_64,
    END_MARKER,
    END_MARKER_64,
    HEADER_SIZE,
    HEADER_SIZE_64,
    V8_SIGNATURE,
    V8_SIGNATURE_64,
    V8Container,
    extract_cf,
)

# ============================================================================
# ХЕЛПЕРЫ ДЛЯ СОЗДАНИЯ СИНТЕТИЧЕСКИХ КОНТЕЙНЕРОВ
# ============================================================================


def make_block_header_32(doc_size: int, current_block_size: int = 512, next_offset: int = END_MARKER) -> bytes:
    """Создаёт 31-байтный заголовок блока (32-битный формат)."""
    return (
        b"\r\n"
        + f"{doc_size:08x}".encode("ascii")
        + b" "
        + f"{current_block_size:08x}".encode("ascii")
        + b" "
        + f"{next_offset & 0xFFFFFFFF:08x}".encode("ascii")
        + b" \r\n"
    )


def make_block_header_64(doc_size: int, current_block_size: int = 65536, next_offset: int = END_MARKER_64) -> bytes:
    """Создаёт 55-байтный заголовок блока (64-битный формат)."""
    return (
        b"\r\n"
        + f"{doc_size:016x}".encode("ascii")
        + b" "
        + f"{current_block_size:016x}".encode("ascii")
        + b" "
        + f"{next_offset & 0xFFFFFFFFFFFFFFFF:016x}".encode("ascii")
        + b" \r\n"
    )


def make_block_32(data: bytes, next_offset: int = END_MARKER, block_size: int = 512) -> bytes:
    """Создаёт 32-битный блок (заголовок + данные)."""
    doc_size = len(data)
    header = make_block_header_32(doc_size, block_size, next_offset)
    padded_data = data + b"\x00" * (block_size - len(data)) if len(data) < block_size else data
    return header + padded_data[:block_size]


def make_block_64(data: bytes, next_offset: int = END_MARKER_64, block_size: int = 65536) -> bytes:
    """Создаёт 64-битный блок (заголовок + данные)."""
    doc_size = len(data)
    header = make_block_header_64(doc_size, block_size, next_offset)
    padded_data = data + b"\x00" * (block_size - len(data)) if len(data) < block_size else data
    return header + padded_data[:block_size]


def make_file_description(name: str, created: int = 0, modified: int = 0) -> bytes:
    """Создаёт file_description (created + modified + unknown + name)."""
    name_utf16 = name.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<QQI", created, modified, 0) + name_utf16


def make_container_32(files: list[tuple[str, bytes]]) -> bytes:
    """Создаёт синтетический 32-битный .cf контейнер."""
    header = struct.pack("<4i", END_MARKER, DEFAULT_BLOCK_SIZE, len(files), 0)

    # TOC
    toc_data = b""
    for _ in files:
        toc_data += struct.pack("<3i", 0, 0, END_MARKER)  # placeholder

    toc_block = make_block_32(toc_data, END_MARKER, DEFAULT_BLOCK_SIZE)

    # file_descriptions и file_data
    current_offset = HEADER_SIZE + DEFAULT_BLOCK_SIZE + BLOCK_HEADER_SIZE

    desc_blocks = []
    desc_offsets = []
    for name, _ in files:
        desc_offsets.append(current_offset)
        desc_data = make_file_description(name)
        desc_block = make_block_32(desc_data, END_MARKER, DEFAULT_BLOCK_SIZE)
        desc_blocks.append(desc_block)
        current_offset += BLOCK_HEADER_SIZE + DEFAULT_BLOCK_SIZE

    data_blocks = []
    data_offsets = []
    for _, data in files:
        data_offsets.append(current_offset)
        data_block = make_block_32(data, END_MARKER, DEFAULT_BLOCK_SIZE)
        data_blocks.append(data_block)
        current_offset += BLOCK_HEADER_SIZE + DEFAULT_BLOCK_SIZE

    # Пересобираем TOC с правильными offset'ами
    toc_data = b""
    for desc_off, data_off in zip(desc_offsets, data_offsets, strict=False):
        toc_data += struct.pack("<3i", desc_off, data_off, END_MARKER)
    toc_block = make_block_32(toc_data, END_MARKER, DEFAULT_BLOCK_SIZE)

    content = header + toc_block
    for db in desc_blocks:
        content += db
    for db in data_blocks:
        content += db

    return content


def make_container_64(files: list[tuple[str, bytes]]) -> bytes:
    """Создаёт синтетический 64-битный .cf контейнер."""
    header = struct.pack("<Q3i", END_MARKER_64, DEFAULT_BLOCK_SIZE_64, len(files), 0)

    # TOC — тройки int64
    toc_data = b""
    for _ in files:
        toc_data += struct.pack("<3Q", 0, 0, END_MARKER_64)  # placeholder

    toc_block = make_block_64(toc_data, END_MARKER_64, DEFAULT_BLOCK_SIZE_64)

    current_offset = HEADER_SIZE_64 + DEFAULT_BLOCK_SIZE_64 + BLOCK_HEADER_SIZE_64

    desc_blocks = []
    desc_offsets = []
    for name, _ in files:
        desc_offsets.append(current_offset)
        desc_data = make_file_description(name)
        desc_block = make_block_64(desc_data, END_MARKER_64, DEFAULT_BLOCK_SIZE_64)
        desc_blocks.append(desc_block)
        current_offset += BLOCK_HEADER_SIZE_64 + DEFAULT_BLOCK_SIZE_64

    data_blocks = []
    data_offsets = []
    for _, data in files:
        data_offsets.append(current_offset)
        data_block = make_block_64(data, END_MARKER_64, DEFAULT_BLOCK_SIZE_64)
        data_blocks.append(data_block)
        current_offset += BLOCK_HEADER_SIZE_64 + DEFAULT_BLOCK_SIZE_64

    # Пересобираем TOC
    toc_data = b""
    for desc_off, data_off in zip(desc_offsets, data_offsets, strict=False):
        toc_data += struct.pack("<3Q", desc_off, data_off, END_MARKER_64)
    toc_block = make_block_64(toc_data, END_MARKER_64, DEFAULT_BLOCK_SIZE_64)

    content = header + toc_block
    for db in desc_blocks:
        content += db
    for db in data_blocks:
        content += db

    return content


# ============================================================================
# ТЕСТЫ
# ============================================================================


def test_v8_signatures():
    """Проверка сигнатур контейнеров."""
    assert V8_SIGNATURE == b"\xff\xff\xff\x7f"
    assert V8_SIGNATURE_64 == b"\xff\xff\xff\xff\xff\xff\xff\xff"
    assert END_MARKER == 0x7FFFFFFF
    assert END_MARKER_64 == 0xFFFFFFFFFFFFFFFF


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


# --- 32-битные тесты ---


def test_container_32_read_header(tmp_path):
    """V8Container (32-бит) правильно читает заголовок."""
    container_data = make_container_32(
        [
            ("version", b"2.0"),
            ("root", b"<root/>"),
        ]
    )

    container = V8Container(container_data, 0)
    container.read()

    assert container.is_64bit is False
    assert container.default_block_size == DEFAULT_BLOCK_SIZE
    assert container.first_empty_block_offset == END_MARKER


def test_container_32_read_files(tmp_path):
    """V8Container (32-бит) правильно читает файлы."""
    container_data = make_container_32(
        [
            ("version", b"2.0"),
            ("root", b"<root/>"),
            ("test", b"data"),
        ]
    )

    container = V8Container(container_data, 0)
    container.read()

    assert len(container.files) == 3
    assert "version" in container.files
    assert "root" in container.files
    assert "test" in container.files


def test_extract_32_simple_files(tmp_path):
    """Извлечение простых файлов из 32-битного контейнера."""
    test_files = [
        ("version", b"2.0"),
        ("root", b"<Configuration><Name>Test</Name></Configuration>"),
    ]

    container_data = make_container_32(test_files)
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 2
    assert (out_dir / "0").exists()
    assert (out_dir / "0" / "version").exists()


def test_extract_32_preserves_data(tmp_path):
    """Данные файлов сохраняются без искажений (32-бит)."""
    original_data = b'{2,1,"test",\n{1,"ru","Test"}}'
    container_data = make_container_32([("metadata", original_data)])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    extract_cf(cf_path, out_dir)

    extracted = (out_dir / "0" / "metadata").read_bytes()
    assert extracted[: len(original_data)] == original_data


def test_extract_32_multiple_files(tmp_path):
    """Извлечение нескольких файлов (32-бит)."""
    files = [(f"file{i}", f"content {i}".encode()) for i in range(5)]
    container_data = make_container_32(files)

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count == 5


def test_extract_32_uuid_named_files(tmp_path):
    """Извлечение файлов с UUID именами (как в реальных .cf)."""
    uuid_name = "30ffe4cc-eef2-4371-8b26-046597e37e22"
    container_data = make_container_32(
        [
            ("version", b"2.0"),
            ("root", b"{2,uuid,hash}"),
            (uuid_name, b'{1,"metadata"}'),
        ]
    )

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count == 3
    assert (out_dir / "0" / uuid_name).exists()


# --- 64-битные тесты ---


def test_container_64_read_header(tmp_path):
    """V8Container (64-бит) правильно читает заголовок."""
    container_data = make_container_64(
        [
            ("version", b"2.0"),
            ("root", b"<root/>"),
        ]
    )

    container = V8Container(container_data, 0)
    container.read()

    assert container.is_64bit is True
    assert container.default_block_size == DEFAULT_BLOCK_SIZE_64
    assert container.first_empty_block_offset == END_MARKER_64


def test_container_64_read_files(tmp_path):
    """V8Container (64-бит) правильно читает файлы."""
    container_data = make_container_64(
        [
            ("version", b"2.0"),
            ("root", b"<root/>"),
            ("test", b"data"),
        ]
    )

    container = V8Container(container_data, 0)
    container.read()

    assert len(container.files) == 3
    assert "version" in container.files
    assert "root" in container.files
    assert "test" in container.files


def test_extract_64_simple_files(tmp_path):
    """Извлечение простых файлов из 64-битного контейнера."""
    test_files = [
        ("version", b"2.0"),
        ("root", b"<Configuration><Name>Test</Name></Configuration>"),
    ]

    container_data = make_container_64(test_files)
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 2
    assert (out_dir / "0").exists()
    assert (out_dir / "0" / "version").exists()


def test_extract_64_preserves_data(tmp_path):
    """Данные файлов сохраняются (64-бит)."""
    original_data = b'{2,1,"test",\n{1,"ru","Test"}}'
    container_data = make_container_64([("metadata", original_data)])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    extract_cf(cf_path, out_dir)

    extracted = (out_dir / "0" / "metadata").read_bytes()
    assert extracted[: len(original_data)] == original_data


# --- Многоконтейнерные тесты ---


def test_extract_multiple_containers(tmp_path):
    """Извлечение нескольких контейнеров из одного .cf файла."""
    # Два 32-битных контейнера подряд
    container1 = make_container_32([("version", b"1.0"), ("root", b"<r/>")])
    container2 = make_container_32([("metadata", b"data1"), ("extra", b"data2")])

    cf_data = container1 + container2
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(cf_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    # Должны извлечься оба контейнера
    assert (out_dir / "0").exists()
    assert (out_dir / "1").exists()
    assert count >= 4  # 2 файла в первом + 2 во втором


def test_extract_mixed_32_64_containers(tmp_path):
    """Извлечение смеси 32 и 64-битных контейнеров."""
    container1 = make_container_32([("version", b"1.0")])
    container2 = make_container_64([("metadata", b"data")])

    cf_data = container1 + container2
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(cf_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 2
    assert (out_dir / "0").exists()  # 32-битный
    assert (out_dir / "1").exists()  # 64-битный


# --- Форматные тесты ---


def test_make_block_header_32_format():
    """Заголовок 32-битного блока имеет правильный формат."""
    header = make_block_header_32(60, 512, END_MARKER)
    assert len(header) == BLOCK_HEADER_SIZE
    assert header.startswith(b"\r\n")
    assert header.endswith(b" \r\n")
    assert b"0000003c" in header  # 60 = 0x3c
    assert b"00000200" in header  # 512 = 0x200
    assert b"7fffffff" in header  # END_MARKER


def test_make_block_header_64_format():
    """Заголовок 64-битного блока имеет правильный формат."""
    header = make_block_header_64(60, 65536, END_MARKER_64)
    assert len(header) == BLOCK_HEADER_SIZE_64
    assert header.startswith(b"\r\n")
    assert header.endswith(b" \r\n")
    assert b"000000000000003c" in header  # 60 = 0x3c, 16 символов
    assert b"0000000000010000" in header  # 65536 = 0x10000
    assert b"ffffffffffffffff" in header  # END_MARKER_64


def test_make_file_description_format():
    """file_description имеет правильный формат."""
    desc = make_file_description("test_file")
    assert len(desc) >= 20
    name_part = desc[20:]
    name = name_part.decode("utf-16-le").split("\x00")[0]
    assert name == "test_file"


def test_make_container_32_helper():
    """Хелпер make_container_32 создаёт валидный контейнер."""
    container_data = make_container_32([("version", b"1.0")])
    assert container_data[:4] == V8_SIGNATURE

    container = V8Container(container_data, 0)
    container.read()
    assert len(container.files) == 1
    assert "version" in container.files


def test_make_container_64_helper():
    """Хелпер make_container_64 создаёт валидный 64-битный контейнер."""
    container_data = make_container_64([("version", b"1.0")])
    assert container_data[:8] == V8_SIGNATURE_64

    container = V8Container(container_data, 0)
    container.read()
    assert len(container.files) == 1
    assert "version" in container.files


def test_extract_creates_output_dir(tmp_path):
    """extract_cf создаёт выходную директорию."""
    container_data = make_container_32([("test", b"data")])
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "new_dir" / "subdir"
    extract_cf(cf_path, out_dir)

    assert out_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
