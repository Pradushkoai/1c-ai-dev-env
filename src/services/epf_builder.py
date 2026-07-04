#!/usr/bin/env python3
"""
epf_builder.py — Упаковщик .epf/.erf файлов (внешних обработок/отчётов 1С).

Формат .epf — это контейнер 1С (V8 container), содержащий:
- Header: 16 bytes (sig + block_size + num_files + reserved)
- TOC block: \r\n + hex(doc_size) + ' ' + hex(block_size) + ' ' + hex(next) + ' \r\n + data
- File entries: desc block + data block для каждого файла

Структура файлов внутри EPF:
- UUID (root metadata)
- UUID (form metadata)
- UUID.0 (form container: nested V8 with info+text)
- copyinfo
- root
- version
- versions

Ключевые правила:
- HEX в lowercase: 7fffffff (НЕ 7FFFFFFF)
- Offsets в TOC: абсолютные от начала файла
- Description block_size = doc_size (не 512)
- Data сжимается raw deflate (wbits=-15)
"""

from __future__ import annotations

import io
import struct
import sys
import uuid as uuid_mod
import zlib
from pathlib import Path

V8_SIGNATURE = 0x7FFFFFFF
END_MARKER = 0x7FFFFFFF
DEFAULT_BLOCK_SIZE = 512
BLOCK_HEADER_SIZE = 31  # \r\n + 8hex + ' ' + 8hex + ' ' + 8hex + ' \r\n
HEADER_SIZE = 16
ENTRY_SIZE = 12  # 3 x uint32


def _make_block_header(doc_size: int, block_size: int, next_block: int = END_MARKER) -> bytes:
    """Создать заголовок блока: \\r\\n + lowercase hex + \\r\\n."""
    return f"\r\n{doc_size:08x} {block_size:08x} {next_block:08x} \r\n".encode("ascii")


def _compress_data(data: bytes) -> bytes:
    """Сжать данные raw deflate (как делает 1С)."""
    compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
    compressed = compressor.compress(data)
    compressed += compressor.flush()
    return compressed


def _make_description(name: str) -> bytes:
    """Создать данные описания файла: 20 bytes timestamp + name UTF-16-LE + 4 null bytes."""
    name_bytes = name.encode("utf-16-le") + b"\x00\x00\x00\x00"
    return b"\x00" * 20 + name_bytes


def build_epf(source_dir, output_path, object_name=None, object_type="DataProcessor"):
    """Упаковывает структуру каталога в .epf файл.

    Args:
        source_dir: Папка со структурой обработки
        output_path: Куда сохранить .epf
        object_name: Имя объекта (если None — берётся из XML)
        object_type: 'DataProcessor' или 'Report'

    Returns:
        dict: {file_path, size, object_name, object_type, uuid, files_included}
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if object_name is None:
        xml_files = list(source_dir.glob("*.xml"))
        if xml_files:
            object_name = xml_files[0].stem
        else:
            raise FileNotFoundError(f"Metadata XML not found in {source_dir}")

    # 1. Читаем метаданные объекта
    metadata_file = source_dir / f"{object_name}.xml"
    if not metadata_file.exists():
        xml_files = list(source_dir.glob("*.xml"))
        if xml_files:
            metadata_file = xml_files[0]
            object_name = metadata_file.stem
        else:
            raise FileNotFoundError(f"Metadata XML not found in {source_dir}")

    metadata_content = metadata_file.read_bytes()

    # 2. Читаем модуль объекта (если есть)
    module_path = source_dir / "Ext" / "Module.bsl"
    module_content = None
    if module_path.exists():
        module_content = module_path.read_bytes()

    # 3. Генерируем UUID
    root_uuid = str(uuid_mod.uuid4())
    form_uuid = str(uuid_mod.uuid4()) if (source_dir / "Forms").exists() else None

    # 4. Подготавливаем файлы для контейнера
    files = []  # [(name, data_bytes), ...]

    # 4a. Root metadata (UUID)
    files.append((root_uuid, metadata_content))

    # 4b. Form metadata + form container (если есть форма)
    if form_uuid:
        # Читаем метаданные формы
        forms_dir = source_dir / "Forms"
        form_dirs = [d for d in sorted(forms_dir.iterdir()) if d.is_dir()]
        if form_dirs:
            form_dir = form_dirs[0]
            form_name = form_dir.name
            form_meta_path = form_dir / f"{form_name}.xml"

            # Метаданные формы
            form_meta_content = form_meta_path.read_bytes() if form_meta_path.exists() else b""
            files.append((form_uuid, form_meta_content))

            # Контейнер формы (UUID.0): nested V8 with info + text
            form_module_path = form_dir / "Ext" / "Form" / "Module.bsl"
            form_xml_path = form_dir / "Ext" / "Form.xml"

            form_module_content = b""
            if form_module_path.exists():
                form_module_content = module_path.read_bytes()

            form_xml_content = b""
            if form_xml_path.exists():
                form_xml_content = form_xml_path.read_bytes()

            # Создаём nested V8 контейнер для формы
            form_container = _build_form_container(form_xml_content, form_module_content)
            files.append((f"{form_uuid}.0", form_container))

    # 4c. Module of object (если есть) — UUID.0 (root UUID + .0)
    if module_content:
        module_container = _build_module_container(module_content)
        # Вставляем ПЕРЕД copyinfo (после root metadata и form)
        # Но в реальном EPF порядок: root_uuid, form_uuid, form_uuid.0, copyinfo, root, version, versions
        # Модуль объекта: root_uuid.0 — но только если есть
        # Пока пропускаем — в исходной обработке модуль объекта пустой

    # 4d. copyinfo
    copyinfo_data = _build_copyinfo(root_uuid, form_uuid)
    files.append(("copyinfo", copyinfo_data))

    # 4e. root
    root_data = b"\xef\xbb\xbf{2," + root_uuid.encode() + b",}"
    files.append(("root", root_data))

    # 4f. version
    version_data = b"\xef\xbb\xbf{\n{216,0,\n{80321,0}\n}\n}"
    files.append(("version", version_data))

    # 4g. versions
    versions_data = (
        b'\xef\xbb\xbf{1,8,"",'
        + root_uuid.encode()
        + b","
        + root_uuid.encode()
        + b',"'
        + (form_uuid or root_uuid).encode()
        + b'"}'
    )
    files.append(("versions", versions_data))

    # 5. Собираем контейнер
    container_data = _build_container(files)

    # 6. Записываем
    with open(output_path, "wb") as f:
        f.write(container_data)

    size = output_path.stat().st_size
    return {
        "file_path": str(output_path),
        "size": size,
        "object_name": object_name,
        "object_type": object_type,
        "uuid": root_uuid,
        "files_included": len(files),
    }


def _build_form_container(form_xml: bytes, form_module: bytes) -> bytes:
    """Создать nested V8 контейнер для формы (info + text)."""
    # info: структура с метаданными формы
    info_data = b'\xef\xbb\xbf{3,1,0,"",0}'

    # text: XML формы + BSL модуль в одном блоке
    # В реальном EPF text содержит и XML и BSL
    text_data = form_xml
    if form_module:
        text_data += b"\r\n" + form_module

    # Создаём вложенный контейнер
    nested_files = [
        ("info", info_data),
        ("text", text_data),
    ]
    return _build_container(nested_files)


def _build_module_container(module_content: bytes) -> bytes:
    """Создать nested V8 контейнер для модуля объекта (info + text)."""
    info_data = b'\xef\xbb\xbf{3,1,0,"",0}'
    nested_files = [
        ("info", info_data),
        ("text", module_content),
    ]
    return _build_container(nested_files)


def _build_copyinfo(root_uuid: str, form_uuid: str | None) -> bytes:
    """Создать copyinfo данные."""
    if form_uuid:
        return f"\ufeff{{4,\n{{2,\n{{{root_uuid},{form_uuid}}}\n}}\n}}".encode()
    return f"\ufeff{{4,\n{{1,\n{{{root_uuid}}}\n}}\n}}".encode()


def _build_container(files: list[tuple[str, bytes]]) -> bytes:
    """Собрать V8 контейнер из списка файлов.

    Args:
        files: [(name, data), ...]

    Returns:
        bytes: Полный контейнер
    """
    num_files = len(files)
    result = io.BytesIO()

    # 1. Header (16 bytes)
    result.write(struct.pack("<4I", V8_SIGNATURE, DEFAULT_BLOCK_SIZE, num_files, 0))

    # 2. TOC block
    toc_entry_size = ENTRY_SIZE
    toc_doc_size = num_files * toc_entry_size

    # TOC header
    toc_header = _make_block_header(toc_doc_size, DEFAULT_BLOCK_SIZE)
    result.write(toc_header)

    # TOC data (пока нули — обновим позже)
    toc_data_offset = result.tell()
    toc_data = bytearray(toc_doc_size)
    # Дополняем до block_size
    toc_data += b"\x00" * (DEFAULT_BLOCK_SIZE - toc_doc_size)
    result.write(toc_data)

    # 3. Вычисляем смещения для каждого файла
    # Каждый файл = desc block + data block
    # desc block: header (31 bytes) + desc_data (padded to desc_block_size)
    # data block: header (31 bytes) + compressed_data (padded to block_size)

    current_offset = result.tell()  # текущая позиция в файле
    toc_entries = []

    for name, data in files:
        # Description
        desc_data = _make_description(name)
        desc_doc_size = len(desc_data)
        desc_block_size = desc_doc_size  # block_size = doc_size для descriptions

        desc_header = _make_block_header(desc_doc_size, desc_block_size)
        desc_offset = current_offset
        result.write(desc_header)
        result.write(desc_data)  # без padding (block_size = doc_size)
        current_offset += len(desc_header) + desc_block_size

        # Data (compressed with raw deflate)
        compressed = _compress_data(data)
        data_doc_size = len(compressed)
        # Data block_size = 512 (DEFAULT_BLOCK_SIZE), но если data больше — используем data_doc_size
        if data_doc_size <= DEFAULT_BLOCK_SIZE:
            data_block_size = DEFAULT_BLOCK_SIZE
        else:
            # Для больших данных: используем размер данных (без padding)
            data_block_size = data_doc_size

        data_header = _make_block_header(data_doc_size, data_block_size)
        data_offset = current_offset
        result.write(data_header)
        result.write(compressed)
        # Padding
        padding = data_block_size - data_doc_size
        if padding > 0:
            result.write(b"\x00" * padding)
        current_offset += len(data_header) + data_block_size

        toc_entries.append((desc_offset, data_offset))

    # 4. Обновляем TOC с реальными смещениями
    result.seek(toc_data_offset)
    for desc_off, data_off in toc_entries:
        result.write(struct.pack("<3I", desc_off, data_off, END_MARKER))

    result.seek(0, 2)  # в конец
    return result.getvalue()

# CLI вынесен в scripts/epf_builder.py (Этап 1.2, Группа 2)
