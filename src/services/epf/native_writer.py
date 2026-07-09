"""
T5.1a (2026-07-06): Native EPF writer — запись .epf без v8unpack.

Проблема: Текущий EpfFactory использует v8unpack через subprocess для сборки
.epf файлов. Это:
1. Внешняя зависимость (v8unpack может быть недоступен)
2. Медленно (subprocess + I/O)
3. Баг block_size TOC (ADR-0007) требует workaround

Решение: NativeEpfWriter — пишет структуру EPF напрямую на Python.

EPF формат (контейнер 1С):
1. Header: 8 байт magic + version + page size
2. Catalog (TOC): список элементов с адресами
3. Data pages: данные (XML, BSL, JSON)

Структура EPF:
- ExternalDataProcessor.json — метаданные обработки
- Form/Форма/Form.xml — метаданные формы
- Form/Форма/Module.bsl — BSL модуль формы
- Form/Форма/Form.elem.json — элементы формы (формат v8unpack)

ВАЖНО: Полная реализация бинарного формата 1С крайне сложна (~5000+ строк).
Этот модуль реализует:
1. Структуру EPF как набор файлов (без бинарной упаковки)
2. Writer для создания .epf структуры в директории
3. Pack в ZIP-подобный формат (для тестирования)
4. Reader для распаковки обратно

Для production сборки реальных .epf (двоичный формат 1С) всё ещё требуется
v8unpack. NativeEpfWriter — это первый шаг к полной native реализации.

Использование:
    from src.services.epf.native_writer import NativeEpfWriter

    writer = NativeEpfWriter()
    result = writer.write_epf(
        output_path=Path("my.epf"),
        metadata={"name": "МояОбработка", "synonym": "Моя обработка"},
        module_bsl='Процедура МойаОбработка()\\nКонецПроцедуры',
        form_xml="<Form>...</Form>",
    )
"""

from __future__ import annotations

import io
import json
import logging
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Magic numbers для EPF контейнера (имитация формата 1С)
EPF_MAGIC = b"\xff\xff\xff\xff\x1c\x00\x00\x00"
EPF_VERSION = 2
EPF_PAGE_SIZE = 512

# Структура EPF директории
EPF_FILES = {
    "metadata": "ExternalDataProcessor.json",
    "form_metadata": "Form/Форма/Form.xml",
    "form_module": "Form/Форма/Module.bsl",
    "form_elements": "Form/Форма/Form.elem.json",
}


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class EpfContent:
    """Содержимое EPF файла."""

    metadata: dict[str, Any] = field(default_factory=dict)
    module_bsl: str = ""
    form_xml: str = ""
    form_elements: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Валидация содержимого. Возвращает список ошибок."""
        errors: list[str] = []

        if not self.metadata:
            errors.append("metadata is empty")
        elif "name" not in self.metadata:
            errors.append("metadata must have 'name'")

        if not self.module_bsl:
            errors.append("module_bsl is empty")

        if not self.form_xml:
            errors.append("form_xml is empty")

        return errors


@dataclass
class EpfWriteResult:
    """Результат записи EPF."""

    success: bool
    output_path: Path | None = None
    file_size: int = 0
    files_written: list[str] = field(default_factory=list)
    error: str = ""


# ============================================================================
# Native EPF Writer
# ============================================================================


class NativeEpfWriter:
    """T5.1a: Native writer для EPF файлов.

    Пишет структуру EPF в формате ZIP-контейнера (имитация 1С формата).
    Каждый файл EPF хранится как отдельная запись в архиве.

    Это позволяет:
    1. Создавать .epf без v8unpack
    2. Тестировать структуру без бинарной упаковки
    3. Иметь fallback если v8unpack недоступен
    """

    def write_epf(
        self,
        output_path: str | Path,
        content: EpfContent,
        *,
        compress: bool = True,
    ) -> EpfWriteResult:
        """Записать EPF файл.

        Args:
            output_path: Путь к .epf файлу.
            content: Содержимое EPF (EpfContent).
            compress: Использовать компрессию ZIP.

        Returns:
            EpfWriteResult с результатом.
        """
        output_path = Path(output_path)

        # Валидация
        errors = content.validate()
        if errors:
            return EpfWriteResult(
                success=False,
                error=f"Validation failed: {'; '.join(errors)}",
            )

        try:
            # Создаём директорию если нужно
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Пишем ZIP-контейнер
            files_written: list[str] = []

            with zipfile.ZipFile(
                output_path, "w",
                compression=zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED,
            ) as zf:
                # 1. Metadata
                metadata_json = self._serialize_metadata(content.metadata)
                zf.writestr(EPF_FILES["metadata"], metadata_json)
                files_written.append(EPF_FILES["metadata"])

                # 2. Form metadata XML
                zf.writestr(EPF_FILES["form_metadata"], content.form_xml)
                files_written.append(EPF_FILES["form_metadata"])

                # 3. Form module BSL
                zf.writestr(EPF_FILES["form_module"], content.module_bsl)
                files_written.append(EPF_FILES["form_module"])

                # 4. Form elements (если есть)
                if content.form_elements:
                    elem_json = json.dumps(
                        content.form_elements, ensure_ascii=False, indent=2
                    )
                    zf.writestr(EPF_FILES["form_elements"], elem_json)
                    files_written.append(EPF_FILES["form_elements"])

            file_size = output_path.stat().st_size

            logger.info(
                "EPF written: %s (%d bytes, %d files)",
                output_path, file_size, len(files_written),
            )

            return EpfWriteResult(
                success=True,
                output_path=output_path,
                file_size=file_size,
                files_written=files_written,
            )

        except Exception as e:
            logger.exception("Failed to write EPF: %s", output_path)
            return EpfWriteResult(
                success=False,
                error=f"Write failed: {e}",
            )

    def write_epf_from_dir(
        self,
        source_dir: str | Path,
        output_path: str | Path,
    ) -> EpfWriteResult:
        """Записать EPF из директории с исходниками.

        Args:
            source_dir: Директория с файлами EPF (ExternalDataProcessor.json, Form/, etc.)
            output_path: Путь к .epf файлу.

        Returns:
            EpfWriteResult.
        """
        source_dir = Path(source_dir)

        if not source_dir.exists():
            return EpfWriteResult(
                success=False,
                error=f"Source directory not found: {source_dir}",
            )

        try:
            # Читаем файлы из директории
            content = self._read_content_from_dir(source_dir)
            return self.write_epf(output_path, content)

        except Exception as e:
            return EpfWriteResult(
                success=False,
                error=f"Failed to read source dir: {e}",
            )

    def _read_content_from_dir(self, source_dir: Path) -> EpfContent:
        """Прочитать содержимое EPF из директории."""
        content = EpfContent()

        # Metadata
        meta_path = source_dir / EPF_FILES["metadata"]
        if meta_path.exists():
            content.metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        # Form module
        module_path = source_dir / EPF_FILES["form_module"]
        if module_path.exists():
            content.module_bsl = module_path.read_text(encoding="utf-8")

        # Form XML
        form_path = source_dir / EPF_FILES["form_metadata"]
        if form_path.exists():
            content.form_xml = form_path.read_text(encoding="utf-8")

        # Form elements
        elem_path = source_dir / EPF_FILES["form_elements"]
        if elem_path.exists():
            content.form_elements = json.loads(elem_path.read_text(encoding="utf-8"))

        return content

    def _serialize_metadata(self, metadata: dict[str, Any]) -> str:
        """Сериализовать metadata в JSON."""
        # Добавляем стандартные поля если их нет
        meta = dict(metadata)
        meta.setdefault("version", 1)
        meta.setdefault("algorithm", "native")
        return json.dumps(meta, ensure_ascii=False, indent=2)


# ============================================================================
# Native EPF Reader
# ============================================================================


class NativeEpfReader:
    """T5.1a: Native reader для EPF файлов (обратный writer)."""

    def read_epf(self, epf_path: str | Path) -> EpfContent | None:
        """Прочитать EPF файл.

        Args:
            epf_path: Путь к .epf файлу.

        Returns:
            EpfContent если успешно, иначе None.
        """
        epf_path = Path(epf_path)

        if not epf_path.exists():
            logger.warning("EPF file not found: %s", epf_path)
            return None

        try:
            with zipfile.ZipFile(epf_path, "r") as zf:
                content = EpfContent()

                # Metadata
                if EPF_FILES["metadata"] in zf.namelist():
                    meta_data = zf.read(EPF_FILES["metadata"])
                    content.metadata = json.loads(meta_data.decode("utf-8"))

                # Form module
                if EPF_FILES["form_module"] in zf.namelist():
                    content.module_bsl = zf.read(EPF_FILES["form_module"]).decode("utf-8")

                # Form XML
                if EPF_FILES["form_metadata"] in zf.namelist():
                    content.form_xml = zf.read(EPF_FILES["form_metadata"]).decode("utf-8")

                # Form elements
                if EPF_FILES["form_elements"] in zf.namelist():
                    elem_data = zf.read(EPF_FILES["form_elements"])
                    content.form_elements = json.loads(elem_data.decode("utf-8"))

                return content

        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to read EPF %s: %s", epf_path, e)
            return None

    def list_epf_files(self, epf_path: str | Path) -> list[str]:
        """Список файлов в EPF контейнере."""
        epf_path = Path(epf_path)
        if not epf_path.exists():
            return []

        try:
            with zipfile.ZipFile(epf_path, "r") as zf:
                return zf.namelist()
        except zipfile.BadZipFile:
            return []


# ============================================================================
# Convenience functions
# ============================================================================


def write_epf(
    output_path: str | Path,
    *,
    name: str,
    synonym: str = "",
    module_bsl: str = "",
    form_xml: str = "",
    description: str = "",
) -> EpfWriteResult:
    """Удобная функция для создания EPF.

    Args:
        output_path: Путь к .epf файлу.
        name: Имя обработки.
        synonym: Синоним.
        module_bsl: BSL код модуля.
        form_xml: XML формы.
        description: Описание.

    Returns:
        EpfWriteResult.
    """
    content = EpfContent(
        metadata={
            "name": name,
            "synonym": synonym,
            "description": description,
        },
        module_bsl=module_bsl,
        form_xml=form_xml,
    )
    writer = NativeEpfWriter()
    return writer.write_epf(output_path, content)


def read_epf(epf_path: str | Path) -> EpfContent | None:
    """Удобная функция для чтения EPF."""
    reader = NativeEpfReader()
    return reader.read_epf(epf_path)


# ============================================================================
# Binary format helpers (для будущей полной native реализации)
# ============================================================================


def write_epf_header(stream: io.BytesIO) -> None:
    """Записать заголовок EPF (имитация формата 1С).

    Реальный формат 1С использует сложный бинарный формат с:
    - 8-байтным magic header
    - Версия формата
    - Размер страницы
    - Catalog (TOC)

    Это заглушка для будущей полной реализации.
    """
    stream.write(EPF_MAGIC)
    stream.write(struct.pack("<I", EPF_VERSION))
    stream.write(struct.pack("<I", EPF_PAGE_SIZE))


def read_epf_header(stream: io.BytesIO) -> tuple[int, int] | None:
    """Прочитать заголовок EPF.

    Returns:
        (version, page_size) если валидный, иначе None.
    """
    magic = stream.read(len(EPF_MAGIC))
    if magic != EPF_MAGIC:
        return None

    version = struct.unpack("<I", stream.read(4))[0]
    page_size = struct.unpack("<I", stream.read(4))[0]
    return (version, page_size)


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для native EPF writer."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Native EPF writer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    write_parser = subparsers.add_parser("write", help="Write EPF file")
    write_parser.add_argument("--output", "-o", required=True, help="Output .epf path")
    write_parser.add_argument("--name", required=True, help="Processor name")
    write_parser.add_argument("--synonym", default="", help="Synonym")
    write_parser.add_argument("--module", required=True, help="Path to Module.bsl")
    write_parser.add_argument("--form", required=True, help="Path to Form.xml")

    read_parser = subparsers.add_parser("read", help="Read EPF file")
    read_parser.add_argument("--input", "-i", required=True, help="Input .epf path")

    list_parser = subparsers.add_parser("list", help="List EPF contents")
    list_parser.add_argument("--input", "-i", required=True, help="Input .epf path")

    args = parser.parse_args()

    if args.command == "write":
        module_bsl = Path(args.module).read_text(encoding="utf-8")
        form_xml = Path(args.form).read_text(encoding="utf-8")
        result = write_epf(
            args.output,
            name=args.name,
            synonym=args.synonym,
            module_bsl=module_bsl,
            form_xml=form_xml,
        )
        if result.success:
            print(f"✅ EPF written: {result.output_path} ({result.file_size} bytes)")
            return 0
        print(f"❌ Failed: {result.error}")
        return 1

    if args.command == "read":
        content = read_epf(args.input)
        if content is None:
            print(f"❌ Failed to read: {args.input}")
            return 1
        print(f"Name: {content.metadata.get('name', '')}")
        print(f"Module size: {len(content.module_bsl)} chars")
        print(f"Form XML size: {len(content.form_xml)} chars")
        return 0

    if args.command == "list":
        reader = NativeEpfReader()
        files = reader.list_epf_files(args.input)
        print(f"Files in {args.input}:")
        for f in files:
            print(f"  - {f}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
