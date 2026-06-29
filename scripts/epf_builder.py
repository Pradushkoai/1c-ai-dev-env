#!/usr/bin/env python3
"""
epf_builder.py — Упаковщик .epf/.erf файлов (внешних обработок/отчётов 1С).

Формат .epf — это контейнер 1С (как .cf), содержащий:
- Метаданные обработки (корневой UUID файл)
- Модуль объекта (UUID.0/text — контейнер с info+text)
- Формы (UUID.N/text с встроенным BSL)
- Макеты (UUID.N/text)

Структура .epf (на основе v8unpack):
- Container 0 (32-битный): root metadata
  - UUID файл — метаданные обработки {1,{2,{1,{2,UUID,UUID},...}}}
  - version, versions
- Container 1 (64-битный): все вложенные объекты
  - UUID — метаданные
  - UUID.0/ — контейнер с info+text (модуль объекта)
  - UUID.1/ — формы (контейнер)
  - UUID.2/ — макеты (контейнер)

Использование:
    from epf_builder import build_epf
    build_epf(source_dir, output_epf_path)
"""
from __future__ import annotations

import io
import os
import struct
import sys
import zlib
from pathlib import Path

# Добавляем scripts/ в path
sys.path.insert(0, '/home/z/my-project/repo_work/scripts')
sys.path.insert(0, str(Path(__file__).parent))

try:
    from cf_extractor import (
        V8_SIGNATURE, V8_SIGNATURE_64,
        HEADER_SIZE, BLOCK_HEADER_SIZE, DEFAULT_BLOCK_SIZE,
        HEADER_SIZE_64, BLOCK_HEADER_SIZE_64, DEFAULT_BLOCK_SIZE_64,
        END_MARKER, END_MARKER_64,
    )
except ImportError:
    # Fallback константы
    V8_SIGNATURE = b'\xFF\xFF\xFF\x7F'
    V8_SIGNATURE_64 = b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
    HEADER_SIZE = 16
    BLOCK_HEADER_SIZE = 31
    DEFAULT_BLOCK_SIZE = 0x200  # 512
    HEADER_SIZE_64 = 20
    BLOCK_HEADER_SIZE_64 = 55
    DEFAULT_BLOCK_SIZE_64 = 0x10000  # 65536
    END_MARKER = 0x7FFFFFFF
    END_MARKER_64 = 0xFFFFFFFFFFFFFFFF


# ============================================================================
# WRITER КОНТЕЙНЕРОВ 1С
# ============================================================================

class V8ContainerWriter:
    """Writer контейнеров 1С (32 и 64 бита).

    Формат контейнера (32-битный):
    - Заголовок (16 байт): sig(4)=0x7FFFFFFF + default_block_size(4) + count_files(4) + reserved(4)
    - Блоки данных с заголовком 31 байт:
      \r\n + hex(8) + ' ' + hex(8) + ' ' + hex(8) + ' ' + \r\n
    - TOC: тройки (desc_offset, data_offset, end_marker) по 12 байт
    - file_description: created(8) + modified(8) + unknown(4) + name(UTF-16 LE)
    """

    def __init__(self, is_64bit: bool = False):
        self.is_64bit = is_64bit
        self.files: list[tuple[str, bytes]] = []
        if is_64bit:
            self.default_block_size = DEFAULT_BLOCK_SIZE_64
            self.end_marker = END_MARKER_64
            self.header_size = HEADER_SIZE_64
            self.block_header_size = BLOCK_HEADER_SIZE_64
            self.entry_size = 24  # 3 × int64
            self.entry_fmt = '<3Q'
        else:
            self.default_block_size = DEFAULT_BLOCK_SIZE
            self.end_marker = END_MARKER
            self.header_size = HEADER_SIZE
            self.block_header_size = BLOCK_HEADER_SIZE
            self.entry_size = 12  # 3 × int32
            self.entry_fmt = '<3i'

    def add_file(self, name: str, data: bytes) -> None:
        """Добавляет файл в контейнер."""
        self.files.append((name, data))

    def build(self) -> bytes:
        """Собирает контейнер в bytes."""
        if not self.files:
            return b''

        # Результирующий буфер
        result = io.BytesIO()

        # 1. Заголовок контейнера
        sig = V8_SIGNATURE_64 if self.is_64bit else V8_SIGNATURE
        count_files = len(self.files)
        if self.is_64bit:
            result.write(struct.pack('<Q3i', int.from_bytes(sig, 'little'),
                                       self.default_block_size, count_files, 0))
        else:
            result.write(struct.pack('<4i', int.from_bytes(sig, 'little'),
                                       self.default_block_size, count_files, 0))

        # 2. TOC (Table of Contents)
        # Сначала вычисляем смещения
        toc_size = count_files * self.entry_size
        # TOC занимает один или несколько блоков
        toc_blocks_count = max(1, (toc_size + self.default_block_size - 1) // self.default_block_size)
        toc_data_size = toc_blocks_count * self.default_block_size

        # Заполняем TOC данными (пока нули, потом обновим)
        toc_start_offset = result.tell()

        # Резервируем место под TOC
        # TOC состоит из блоков: каждый блок имеет заголовок + данные
        toc_block_data = bytearray(toc_size)
        for i, (name, data) in enumerate(self.files):
            # Пока заполняем нулями — обновим после расчёта смещений
            pass

        # Записываем TOC блоки (один блок для простоты, если помещается)
        # Формат блока: \r\n + hex(doc_size) + ' ' + hex(block_size) + ' ' + hex(next) + ' ' + \r\n + data
        doc_size = toc_size
        block_size = self.default_block_size
        next_block = self.end_marker

        if self.is_64bit:
            header = f'\r\n{doc_size:016X} {block_size:016X} {next_block:016X} \r\n'.encode('ascii')
        else:
            header = f'\r\n{doc_size:08X} {block_size:08X} {next_block:08X} \r\n'.encode('ascii')

        result.write(header)
        # Дополняем TOC до block_size
        toc_padded = bytes(toc_block_data) + b'\x00' * (block_size - len(toc_block_data))
        result.write(toc_padded)

        # 3. Вычисляем смещения для каждого файла
        # Каждый файл = description (заголовок + блок) + data (заголовок + блоки)

        # Текущее смещение (после TOC)
        current_offset = result.tell()

        file_entries = []  # [(desc_offset, data_offset), ...]

        for name, data in self.files:
            # Description: 20 байт (created(8) + modified(8) + unknown(4)) + name UTF-16-LE
            name_bytes = name.encode('utf-16-le') + b'\x00\x00'
            desc_data = b'\x00' * 20 + name_bytes
            desc_size = len(desc_data)

            # Data: исходные данные (сжимаем если возможно)
            try:
                compressed = zlib.compress(data)
                if len(compressed) < len(data):
                    file_data = compressed
                else:
                    file_data = data
            except:
                file_data = data
            data_size = len(file_data)

            # Description блок
            desc_offset = current_offset
            desc_block_size = self.default_block_size
            if self.is_64bit:
                desc_header = f'\r\n{desc_size:016X} {desc_block_size:016X} {self.end_marker:016X} \r\n'.encode('ascii')
            else:
                desc_header = f'\r\n{desc_size:08X} {desc_block_size:08X} {self.end_marker:08X} \r\n'.encode('ascii')
            result.write(desc_header)
            # Дополняем desc до block_size
            desc_padded = desc_data + b'\x00' * (desc_block_size - len(desc_data))
            result.write(desc_padded)
            current_offset += len(desc_header) + desc_block_size

            # Data блоки (может быть несколько для больших файлов)
            data_offset = current_offset
            remaining = file_data
            block_index = 0
            while remaining:
                chunk = remaining[:self.default_block_size]
                remaining = remaining[self.default_block_size:]
                if remaining:
                    next_off = self.end_marker  # упрощаем — один блок
                else:
                    next_off = self.end_marker

                if self.is_64bit:
                    data_header = f'\r\n{data_size:016X} {len(chunk):016X} {next_off:016X} \r\n'.encode('ascii')
                else:
                    data_header = f'\r\n{data_size:08X} {len(chunk):08X} {next_off:08X} \r\n'.encode('ascii')
                result.write(data_header)
                chunk_padded = chunk + b'\x00' * (self.default_block_size - len(chunk))
                result.write(chunk_padded)
                current_offset += len(data_header) + self.default_block_size
                if block_index > 0:
                    break  # упрощаем — не поддерживаем multi-block
                block_index += 1

            file_entries.append((desc_offset, data_offset))

        # 4. Обновляем TOC с реальными смещениями
        result.seek(toc_start_offset + self.block_header_size)  # пропускаем заголовок TOC блока

        for desc_off, data_off in file_entries:
            if self.is_64bit:
                result.write(struct.pack('<3Q', desc_off, data_off, self.end_marker))
            else:
                result.write(struct.pack('<3i', desc_off, data_off, self.end_marker))

        result.seek(0, 2)  # в конец
        return result.getvalue()


def build_container(files: list[tuple[str, bytes]], is_64bit: bool = False) -> bytes:
    """Собирает контейнер 1С из списка файлов.

    Args:
        files: [(name, data), ...]
        is_64bit: Использовать 64-битный формат

    Returns:
        bytes: Контейнер
    """
    writer = V8ContainerWriter(is_64bit=is_64bit)
    for name, data in files:
        writer.add_file(name, data)
    return writer.build()


# ============================================================================
# УПАКОВЩИК .epf
# ============================================================================

def build_epf(source_dir: str, output_path: str, object_name: str = None,
              object_type: str = 'DataProcessor') -> dict:
    """Упаковывает структуру каталога в .epf файл.

    Args:
        source_dir: Папка со структурой (из code_generator.py)
        output_path: Куда сохранить .epf
        object_name: Имя объекта (если None — берётся из имени папки)
        object_type: 'DataProcessor' или 'Report'

    Returns:
        dict: {file_path, size, files_included}
    """
    source_dir = Path(source_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if object_name is None:
        object_name = source_dir.name

    # 1. Читаем метаданные объекта
    metadata_file = source_dir / f'{object_name}.xml'
    if not metadata_file.exists():
        # Ищем любой .xml в корне
        xml_files = list(source_dir.glob('*.xml'))
        if xml_files:
            metadata_file = xml_files[0]
            object_name = metadata_file.stem
        else:
            raise FileNotFoundError(f"Metadata XML not found in {source_dir}")

    metadata_content = metadata_file.read_bytes()

    # 2. Читаем модуль объекта
    module_path = source_dir / 'Ext' / 'Module.bsl'
    module_content = b''
    if module_path.exists():
        module_content = module_path.read_bytes()

    # 3. Формируем файлы для контейнера
    # Container 0 (32-бит): root metadata
    # - UUID файл с метаданными
    # - version, versions

    import uuid as uuid_mod
    obj_uuid = str(uuid_mod.uuid4())

    # Корневой файл метаданных (имя = UUID)
    root_files = [
        (obj_uuid, metadata_content),
        ('version', b'{\r\n{216,0,\r\n{80316,0}\r\n}\r\n}'),
        ('versions', b'{1,6,"",' + obj_uuid.encode() + b'}'),
    ]

    container0 = build_container(root_files, is_64bit=False)

    # 4. Container 1 (64-бит): модуль и формы
    # Формируем файлы: UUID (метаданные), UUID.0/ (модуль в контейнере info+text)

    # UUID.0 — контейнер с info+text (модуль объекта)
    module_container_files = [
        ('info', b'{3,1,0,"",0}'),
        ('text', module_content),
    ]
    module_container = build_container(module_container_files, is_64bit=False)

    container1_files = [
        (obj_uuid, metadata_content),  # метаданные (повторяем)
        (f'{obj_uuid}.0', module_container),  # модуль объекта
    ]

    # 5. Добавляем формы если есть
    forms_dir = source_dir / 'Forms'
    if forms_dir.exists():
        form_index = 1
        for form_dir in sorted(forms_dir.iterdir()):
            if not form_dir.is_dir():
                continue
            form_name = form_dir.name
            form_meta = form_dir / f'{form_name}.xml'
            form_module = form_dir / 'Ext' / 'Form' / 'Module.bsl'
            form_xml = form_dir / 'Ext' / 'Form.xml'

            # Форма — это контейнер с info+text
            form_files = [('info', b'{3,1,0,"",0}')]
            if form_module.exists():
                form_files.append(('text', form_module.read_bytes()))
            else:
                form_files.append(('text', b''))

            form_container = build_container(form_files, is_64bit=False)

            if form_meta.exists():
                container1_files.append((f'{obj_uuid}.{form_index}', form_container))
                container1_files.append((str(uuid_mod.uuid4()), form_meta.read_bytes()))
            form_index += 1

    container1 = build_container(container1_files, is_64bit=True)

    # 6. Собираем финальный .epf
    with open(output_path, 'wb') as f:
        f.write(container0)
        f.write(container1)

    size = output_path.stat().st_size

    return {
        'file_path': str(output_path),
        'size': size,
        'object_name': object_name,
        'object_type': object_type,
        'uuid': obj_uuid,
        'files_included': len(root_files) + len(container1_files),
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 3:
        print("Использование: python3 epf_builder.py <source_dir> <output.epf>")
        print()
        print("Пример:")
        print("  python3 epf_builder.py /tmp/test_processing /tmp/processing.epf")
        sys.exit(1)

    source_dir = sys.argv[1]
    output = sys.argv[2]

    result = build_epf(source_dir, output)
    print(f"\n✅ .epf создан: {result['file_path']}")
    print(f"   Размер: {result['size']} байт")
    print(f"   Объект: {result['object_name']} ({result['object_type']})")
    print(f"   UUID: {result['uuid']}")
    print(f"   Файлов внутри: {result['files_included']}")


if __name__ == '__main__':
    main()
