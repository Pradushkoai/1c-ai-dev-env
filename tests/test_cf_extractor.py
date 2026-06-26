"""
Тесты для cf_extractor.py.
Проверяем парсинг формата контейнера 1С на синтетических данных.
"""
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cf_extractor import V8Container, V8_SIGNATURE, END_MARKER, extract_cf


# ============================================================================
# ХЕЛПЕРЫ ДЛЯ СОЗДАНИЯ СИНТЕТИЧЕСКИХ КОНТЕЙНЕРОВ
# ============================================================================

def make_block_header(data_len: int, next_offset: int = 0) -> bytes:
    """Создаёт 31-байтный заголовок блока."""
    doc_size = f"{data_len:02X}"[:2]
    current_block_size = f"{data_len:08X}"
    next_hex = f"{next_offset:08X}"
    data_hex = f"{data_len:08X}"
    header = (
        doc_size.encode('ascii') +
        current_block_size.encode('ascii') +
        b'\x00' +
        next_hex.encode('ascii') +
        b'\x00' +
        data_hex.encode('ascii') +
        b'\x00\x00\x00'
    )
    return header


def make_block(data: bytes, next_offset: int = 0) -> bytes:
    """Создаёт блок (заголовок + данные)."""
    header = make_block_header(len(data), next_offset)
    return header + data


def raw_deflate(data: bytes) -> bytes:
    """Сжатие в raw deflate (без заголовков zlib)."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(data) + compressor.flush()


def make_container(files: list[tuple[str, bytes]], nested_containers: list[tuple[str, list]] = None) -> bytes:
    """
    Создаёт синтетический .cf контейнер.
    """
    nested_containers = nested_containers or []

    # TOC: пары (name_int, 0), завершается END_MARKER
    toc_data = b''
    all_entries = files + [(name, None) for name, _ in nested_containers]
    for name, _ in all_entries:
        name_bytes = name.encode('ascii').ljust(4, b'\x00')[:4]
        name_int = struct.unpack('<I', name_bytes)[0]
        toc_data += struct.pack('<II', name_int, 0)
    toc_data += struct.pack('<I', END_MARKER)

    # Заголовок контейнера
    header = struct.pack('<4i',
        struct.unpack('<I', V8_SIGNATURE)[0],
        0,
        0x200,
        len(all_entries)
    )

    # TOC блок
    toc_block = make_block(toc_data, 0)

    content = header + toc_block

    # Файлы (сжатые)
    for name, data in files:
        compressed = raw_deflate(data)
        block = make_block(compressed, 0)
        content += block

    # Вложенные контейнеры
    for name, nested_files in nested_containers:
        nested_data = make_container(nested_files)
        block = make_block(nested_data, 0)
        content += block

    return content


# ============================================================================
# ТЕСТЫ
# ============================================================================

def test_v8_signature():
    """Проверка сигнатуры контейнера."""
    assert V8_SIGNATURE == b'\xFF\xFF\xFF\x7F'


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
        ('vers', b'2.0'),
        ('root', b'<Configuration/>'),
    ])

    container = V8Container(container_data, 0)
    container.read()

    assert container.first_empty_block_offset == 0
    assert container.default_block_size == 0x200
    assert container.count_files == 2


def test_container_read_toc(tmp_path):
    """V8Container правильно читает TOC."""
    container_data = make_container([
        ('vers', b'2.0'),
        ('root', b'<Configuration/>'),
        ('meta', b'<Meta/>'),
    ])

    container = V8Container(container_data, 0)
    container.read()

    assert len(container.toc) == 3
    names = [entry[0] for entry in container.toc]
    assert 'vers' in names
    assert 'root' in names
    assert 'meta' in names


def test_extract_simple_files(tmp_path):
    """Извлечение простых файлов из контейнера."""
    test_files = [
        ('vers', b'2.0'),
        ('root', b'<?xml version="1.0"?><Configuration><Name>Test</Name></Configuration>'),
    ]

    container_data = make_container(test_files)
    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 2
    assert (out_dir / "vers").exists() or (out_dir / "vers.bin").exists()
    xml_files = list(out_dir.glob("*.xml")) + list(out_dir.glob("root*"))
    assert len(xml_files) >= 1


def test_extract_nested_container(tmp_path):
    """Извлечение вложенного контейнера."""
    container_data = make_container(
        files=[('vers', b'2.0')],
        nested_containers=[('root', [
            ('file1', b'data1'),
            ('file2', b'data2'),
        ])]
    )

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count >= 1
    assert (out_dir / "root").is_dir()


def test_extract_xml_file_gets_xml_extension(tmp_path):
    """XML файлы получают расширение .xml."""
    xml_content = b'<?xml version="1.0"?><ConfigDumpInfo><Configuration/></ConfigDumpInfo>'
    container_data = make_container([
        ('meta', xml_content),
    ])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    extract_cf(cf_path, out_dir)

    xml_files = list(out_dir.glob("*.xml"))
    assert len(xml_files) == 1
    content = xml_files[0].read_bytes()
    assert b'<Configuration' in content


def test_extract_multiple_files(tmp_path):
    """Извлечение нескольких файлов."""
    files = [
        (f'f{i:03d}', f'content {i}'.encode())
        for i in range(5)
    ]
    container_data = make_container(files)

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    count = extract_cf(cf_path, out_dir)

    assert count == 5


def test_extract_preserves_data(tmp_path):
    """Данные файлов сохраняются без искажений."""
    original_data = b'<?xml version="1.0"?>\n<Configuration>\n  <Name>TestConfig</Name>\n</Configuration>'
    container_data = make_container([
        ('root', original_data),
    ])

    cf_path = tmp_path / "test.cf"
    cf_path.write_bytes(container_data)

    out_dir = tmp_path / "out"
    extract_cf(cf_path, out_dir)

    xml_files = list(out_dir.glob("*.xml"))
    assert len(xml_files) == 1
    extracted_data = xml_files[0].read_bytes()
    assert extracted_data == original_data


def test_make_container_helper():
    """Хелпер make_container создаёт валидный контейнер."""
    container_data = make_container([('vers', b'1.0')])

    assert container_data[:4] == V8_SIGNATURE

    container = V8Container(container_data, 0)
    container.read()
    assert len(container.toc) == 1
    assert container.toc[0][0] == 'vers'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
