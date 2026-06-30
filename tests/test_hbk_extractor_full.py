"""
Тесты для hbk_extractor.
Проверяем parse_hbk_file и extract_file_data на синтетическом .hbk.
"""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import hbk_extractor
import pytest


def _make_local_file_header(name: bytes, compressed_data: bytes, uncompressed_data: bytes, method: int = 8):
    """Создать ZIP local file header (30 байт) + name + data."""
    name_len = len(name)
    extra_len = 0
    comp_size = len(compressed_data)
    uncomp_size = len(uncompressed_data)
    crc = zlib.crc32(uncompressed_data) & 0xFFFFFFFF

    header = struct.pack(
        '<IHHHHHIIIHH',
        0x04034b50,  # PK\x03\x04
        20,  # version
        0,  # flags
        method,  # compression method (8=deflate, 0=store)
        0,  # mtime
        0,  # mdate
        crc,
        comp_size,
        uncomp_size,
        name_len,
        extra_len,
    )
    return header + name + compressed_data


def test_parse_hbk_file_with_one_entry(tmp_path):
    """parse_hbk_file находит PK\x03\x04 заголовок и корректно парсит имя."""
    # Создаём синтетический .hbk: 16 байт заголовок 1С + один ZIP-файл
    content = b"1C HBK HEADER  \x00\x00"  # 16 байт
    payload = b"<html>Test page</html>"
    compressed = zlib.compress(payload, wbits=-15)  # raw deflate
    name = b"test_page.html"

    local_header = _make_local_file_header(name, compressed, payload)
    content += local_header

    hbk_path = tmp_path / "test.hbk"
    hbk_path.write_bytes(content)

    files = hbk_extractor.parse_hbk_file(str(hbk_path))

    assert len(files) == 1
    f = files[0]
    assert "test_page.html" in f["name"]
    assert f["comp_size"] > 0
    assert f["uncomp_size"] == len(payload)
    assert f["method"] == 8  # deflate


def test_parse_hbk_file_multiple_entries(tmp_path):
    """parse_hbk_file находит несколько PK-заголовков."""
    content = b"1C HBK HEADER  \x00\x00"  # 16 байт

    for i in range(3):
        payload = f"<html>Page {i}</html>".encode()
        compressed = zlib.compress(payload, wbits=-15)
        name = f"page_{i}.html".encode()
        content += _make_local_file_header(name, compressed, payload)

    hbk_path = tmp_path / "multi.hbk"
    hbk_path.write_bytes(content)

    files = hbk_extractor.parse_hbk_file(str(hbk_path))

    assert len(files) == 3
    names = [f["name"] for f in files]
    assert "page_0.html" in names
    assert "page_1.html" in names
    assert "page_2.html" in names


def test_parse_hbk_file_empty(tmp_path):
    """Пустой .hbk (только заголовок) → пустой список."""
    hbk_path = tmp_path / "empty.hbk"
    hbk_path.write_bytes(b"1C HBK HEADER  \x00\x00")

    files = hbk_extractor.parse_hbk_file(str(hbk_path))
    assert files == []


def test_extract_file_data_deflate(tmp_path):
    """extract_file_data распаковывает deflate-сжатые данные."""
    payload = b"<html><body>Hello, 1C!</body></html>"
    compressed = zlib.compress(payload, wbits=-15)

    file_info = {
        "name": "test.html",
        "data_offset": 0,
        "comp_size": len(compressed),
        "method": 8,  # deflate
        "crc": 0,
        "flags": 0,
    }

    result = hbk_extractor.extract_file_data(compressed, file_info)
    assert result == payload


def test_extract_file_data_store(tmp_path):
    """extract_file_data работает с method=0 (store, без сжатия)."""
    payload = b"Uncompressed content"
    file_info = {
        "name": "test.txt",
        "data_offset": 0,
        "comp_size": len(payload),
        "method": 0,  # store
        "crc": 0,
        "flags": 0,
    }

    result = hbk_extractor.extract_file_data(payload, file_info)
    assert result == payload


def test_extract_file_data_invalid(tmp_path):
    """extract_file_data возвращает None при повреждённых данных."""
    file_info = {
        "name": "bad.html",
        "data_offset": 0,
        "comp_size": 100,
        "method": 8,
        "crc": 0,
        "flags": 0,
    }

    result = hbk_extractor.extract_file_data(b"GARBAGE DATA NOT DEFLATE", file_info)
    # Должен вернуть None или пустые данные при ошибке
    assert result is None or result == b""


def test_safe_filename():
    """safe_filename заменяет недопустимые символы."""
    assert hbk_extractor.safe_filename("normal_name.txt") == "normal_name.txt"
    assert hbk_extractor.safe_filename("path/with/slashes") == "path_with_slashes"
    assert hbk_extractor.safe_filename("file*with?special") == "file_with_special"
    assert hbk_extractor.safe_filename('quote"in"name') == "quote_in_name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
