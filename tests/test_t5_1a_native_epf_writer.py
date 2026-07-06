"""
T5.1a (2026-07-06): Тесты для Native EPF writer.

Проверяет:
- EpfContent dataclass: creation, validation
- NativeEpfWriter.write_epf: создание .epf файла
- NativeEpfReader.read_epf: чтение .epf файла
- Round-trip: write → read → compare
- write_epf_from_dir: создание из директории
- Binary header helpers
- Edge cases: пустой content, неверный path
- CLI
"""

from __future__ import annotations

import io
import json
import struct
from pathlib import Path

import pytest

from src.services.epf.native_writer import (
    EPF_FILES,
    EPF_MAGIC,
    EPF_PAGE_SIZE,
    EPF_VERSION,
    EpfContent,
    EpfWriteResult,
    NativeEpfReader,
    NativeEpfWriter,
    read_epf,
    read_epf_header,
    write_epf,
    write_epf_header,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_content() -> EpfContent:
    """Sample EPF content для тестов."""
    return EpfContent(
        metadata={
            "name": "ТестоваяОбработка",
            "synonym": "Тестовая обработка",
            "description": "Для теста",
        },
        module_bsl='Процедура МояОбработка() Экспорт\nСообщить("Привет");\nКонецПроцедуры',
        form_xml='<?xml version="1.0"?><Form xmlns="http://v8.1c.ru/8.3/xcf/logform"><ChildItems/></Form>',
        form_elements={"props": [{"name": "Объект", "type": "DataProcessorObject"}]},
    )


# ============================================================================
# EpfContent dataclass tests
# ============================================================================


class TestEpfContent:
    def test_defaults(self) -> None:
        content = EpfContent()
        assert content.metadata == {}
        assert content.module_bsl == ""
        assert content.form_xml == ""
        assert content.form_elements == {}

    def test_with_values(self, sample_content: EpfContent) -> None:
        assert sample_content.metadata["name"] == "ТестоваяОбработка"
        assert "МояОбработка" in sample_content.module_bsl
        assert "<Form" in sample_content.form_xml

    def test_validate_empty_content(self) -> None:
        """Пустой content имеет ошибки валидации."""
        content = EpfContent()
        errors = content.validate()
        assert len(errors) >= 3
        assert any("metadata" in e for e in errors)
        assert any("module_bsl" in e for e in errors)
        assert any("form_xml" in e for e in errors)

    def test_validate_no_name(self) -> None:
        """Metadata без name — ошибка."""
        content = EpfContent(
            metadata={"synonym": "X"},
            module_bsl="// code",
            form_xml="<Form/>",
        )
        errors = content.validate()
        assert any("name" in e for e in errors)

    def test_validate_valid_content(self, sample_content: EpfContent) -> None:
        """Валидный content — нет ошибок."""
        errors = sample_content.validate()
        assert errors == []


# ============================================================================
# NativeEpfWriter tests
# ============================================================================


class TestNativeEpfWriter:
    def test_write_epf_creates_file(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """write_epf создаёт .epf файл."""
        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        result = writer.write_epf(output, sample_content)

        assert result.success
        assert result.output_path == output
        assert output.exists()
        assert result.file_size > 0

    def test_write_epf_creates_zip(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Созданный файл — валидный ZIP."""
        import zipfile

        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        writer.write_epf(output, sample_content)

        assert zipfile.is_zipfile(output)

    def test_write_epf_contains_all_files(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """EPF содержит все 4 файла."""
        import zipfile

        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        result = writer.write_epf(output, sample_content)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert EPF_FILES["metadata"] in names
            assert EPF_FILES["form_metadata"] in names
            assert EPF_FILES["form_module"] in names
            assert EPF_FILES["form_elements"] in names

    def test_write_epf_files_written_list(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """files_written содержит список созданных файлов."""
        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        result = writer.write_epf(output, sample_content)

        assert len(result.files_written) == 4
        assert EPF_FILES["metadata"] in result.files_written

    def test_write_epf_invalid_content_returns_error(self, tmp_path: Path) -> None:
        """Невалидный content — ошибка."""
        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        result = writer.write_epf(output, EpfContent())

        assert not result.success
        assert "Validation failed" in result.error
        assert not output.exists()

    def test_write_epf_creates_parent_dirs(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Создаёт родительские директории."""
        writer = NativeEpfWriter()
        output = tmp_path / "deep" / "nested" / "test.epf"
        result = writer.write_epf(output, sample_content)

        assert result.success
        assert output.exists()

    def test_write_epf_without_form_elements(
        self, tmp_path: Path
    ) -> None:
        """EPF без form_elements — 3 файла."""
        writer = NativeEpfWriter()
        output = tmp_path / "test.epf"
        content = EpfContent(
            metadata={"name": "X"},
            module_bsl="// code",
            form_xml="<Form/>",
        )
        result = writer.write_epf(output, content)

        assert result.success
        assert len(result.files_written) == 3
        assert EPF_FILES["form_elements"] not in result.files_written

    def test_write_epf_with_compression(self, tmp_path: Path, sample_content: EpfContent) -> None:
        """С компрессией файл меньше."""
        writer = NativeEpfWriter()
        output_compressed = tmp_path / "compressed.epf"
        output_uncompressed = tmp_path / "uncompressed.epf"

        writer.write_epf(output_compressed, sample_content, compress=True)
        writer.write_epf(output_uncompressed, sample_content, compress=False)

        # Compressed should be smaller (или хотя бы не больше)
        assert output_compressed.stat().st_size <= output_uncompressed.stat().st_size


# ============================================================================
# NativeEpfReader tests
# ============================================================================


class TestNativeEpfReader:
    def test_read_epf_returns_content(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """read_epf возвращает EpfContent."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "test.epf"

        writer.write_epf(output, sample_content)
        content = reader.read_epf(output)

        assert content is not None
        assert isinstance(content, EpfContent)

    def test_read_epf_missing_file_returns_none(self, tmp_path: Path) -> None:
        """Несуществующий файл → None."""
        reader = NativeEpfReader()
        assert reader.read_epf(tmp_path / "nope.epf") is None

    def test_read_epf_invalid_zip_returns_none(self, tmp_path: Path) -> None:
        """Невалидный ZIP → None."""
        reader = NativeEpfReader()
        bad_file = tmp_path / "bad.epf"
        bad_file.write_text("not a zip", encoding="utf-8")
        assert reader.read_epf(bad_file) is None

    def test_list_epf_files(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """list_epf_files возвращает список файлов."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "test.epf"

        writer.write_epf(output, sample_content)
        files = reader.list_epf_files(output)

        assert len(files) == 4
        assert EPF_FILES["metadata"] in files

    def test_list_epf_files_missing(self, tmp_path: Path) -> None:
        """list_epf_files для несуществующего файла → []."""
        reader = NativeEpfReader()
        assert reader.list_epf_files(tmp_path / "nope.epf") == []


# ============================================================================
# Round-trip tests
# ============================================================================


class TestRoundTrip:
    """Round-trip: write → read → compare."""

    def test_round_trip_preserves_metadata(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Metadata сохраняется при round-trip."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "rt.epf"

        writer.write_epf(output, sample_content)
        read_content = reader.read_epf(output)

        assert read_content is not None
        assert read_content.metadata["name"] == sample_content.metadata["name"]
        assert read_content.metadata["synonym"] == sample_content.metadata["synonym"]

    def test_round_trip_preserves_module_bsl(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Module BSL сохраняется byte-for-byte."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "rt.epf"

        writer.write_epf(output, sample_content)
        read_content = reader.read_epf(output)

        assert read_content is not None
        assert read_content.module_bsl == sample_content.module_bsl

    def test_round_trip_preserves_form_xml(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Form XML сохраняется."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "rt.epf"

        writer.write_epf(output, sample_content)
        read_content = reader.read_epf(output)

        assert read_content is not None
        assert read_content.form_xml == sample_content.form_xml

    def test_round_trip_preserves_form_elements(
        self, tmp_path: Path, sample_content: EpfContent
    ) -> None:
        """Form elements сохраняются."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        output = tmp_path / "rt.epf"

        writer.write_epf(output, sample_content)
        read_content = reader.read_epf(output)

        assert read_content is not None
        assert read_content.form_elements == sample_content.form_elements


# ============================================================================
# write_epf_from_dir tests
# ============================================================================


class TestWriteFromDir:
    """Тесты write_epf_from_dir."""

    def test_write_from_dir_creates_epf(self, tmp_path: Path) -> None:
        """Создаёт EPF из директории с исходниками."""
        # Создаём исходники
        src_dir = tmp_path / "src"
        (src_dir / "Form" / "Форма").mkdir(parents=True)

        (src_dir / EPF_FILES["metadata"]).write_text(
            json.dumps({"name": "FromDir", "synonym": "From Dir"}),
            encoding="utf-8",
        )
        (src_dir / EPF_FILES["form_module"]).write_text(
            'Процедура Test() Экспорт\nКонецПроцедуры',
            encoding="utf-8",
        )
        (src_dir / EPF_FILES["form_metadata"]).write_text(
            '<?xml version="1.0"?><Form/>',
            encoding="utf-8",
        )

        writer = NativeEpfWriter()
        output = tmp_path / "from_dir.epf"
        result = writer.write_epf_from_dir(src_dir, output)

        assert result.success
        assert output.exists()

    def test_write_from_dir_missing_dir(self, tmp_path: Path) -> None:
        """Несуществующая директория — ошибка."""
        writer = NativeEpfWriter()
        result = writer.write_epf_from_dir(
            tmp_path / "nope", tmp_path / "out.epf"
        )
        assert not result.success
        assert "not found" in result.error


# ============================================================================
# Convenience functions tests
# ============================================================================


class TestConvenienceFunctions:
    def test_write_epf_function(self, tmp_path: Path) -> None:
        """Функция write_epf() создаёт EPF."""
        output = tmp_path / "conv.epf"
        result = write_epf(
            output,
            name="Конвейн",
            synonym="Конвейн",
            module_bsl='Процедура X() Экспорт\nКонецПроцедуры',
            form_xml='<Form/>',
        )
        assert result.success
        assert output.exists()

    def test_read_epf_function(self, tmp_path: Path) -> None:
        """Функция read_epf() читает EPF."""
        output = tmp_path / "conv.epf"
        write_epf(
            output,
            name="Test",
            module_bsl='// code',
            form_xml='<Form/>',
        )
        content = read_epf(output)
        assert content is not None
        assert content.metadata["name"] == "Test"


# ============================================================================
# Binary header helpers tests
# ============================================================================


class TestBinaryHeader:
    def test_write_header_writes_magic(self) -> None:
        """write_epf_header пишет magic bytes."""
        stream = io.BytesIO()
        write_epf_header(stream)
        data = stream.getvalue()
        assert data.startswith(EPF_MAGIC)

    def test_write_header_writes_version(self) -> None:
        """write_epf_header пишет версию."""
        stream = io.BytesIO()
        write_epf_header(stream)
        data = stream.getvalue()
        version = struct.unpack("<I", data[8:12])[0]
        assert version == EPF_VERSION

    def test_write_header_writes_page_size(self) -> None:
        """write_epf_header пишет page size."""
        stream = io.BytesIO()
        write_epf_header(stream)
        data = stream.getvalue()
        page_size = struct.unpack("<I", data[12:16])[0]
        assert page_size == EPF_PAGE_SIZE

    def test_read_header_returns_version_and_page_size(self) -> None:
        """read_epf_header возвращает version и page_size."""
        stream = io.BytesIO()
        write_epf_header(stream)
        stream.seek(0)
        result = read_epf_header(stream)
        assert result == (EPF_VERSION, EPF_PAGE_SIZE)

    def test_read_header_invalid_magic_returns_none(self) -> None:
        """Неверный magic → None."""
        stream = io.BytesIO(b"INVALID MAGIC BYTES")
        assert read_epf_header(stream) is None


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_module_bsl_fails_validation(self, tmp_path: Path) -> None:
        """Пустой module_bsl — ошибка валидации."""
        writer = NativeEpfWriter()
        content = EpfContent(
            metadata={"name": "X"},
            module_bsl="",  # пусто
            form_xml="<Form/>",
        )
        result = writer.write_epf(tmp_path / "test.epf", content)
        assert not result.success

    def test_empty_form_xml_fails_validation(self, tmp_path: Path) -> None:
        """Пустой form_xml — ошибка валидации."""
        writer = NativeEpfWriter()
        content = EpfContent(
            metadata={"name": "X"},
            module_bsl="// code",
            form_xml="",  # пусто
        )
        result = writer.write_epf(tmp_path / "test.epf", content)
        assert not result.success

    def test_large_module_bsl(self, tmp_path: Path) -> None:
        """Большой module_bsl (10KB)."""
        writer = NativeEpfWriter()
        large_bsl = '// Большой модуль\n' + 'Сообщить("x");\n' * 500
        content = EpfContent(
            metadata={"name": "Large"},
            module_bsl=large_bsl,
            form_xml="<Form/>",
        )
        result = writer.write_epf(tmp_path / "large.epf", content)
        assert result.success
        # После компрессии файл меньше исходного, но всё равно существенный
        assert result.file_size > 100  # ZIP minimum overhead

    def test_unicode_in_metadata(self, tmp_path: Path) -> None:
        """Unicode в metadata сохраняется."""
        writer = NativeEpfWriter()
        reader = NativeEpfReader()
        content = EpfContent(
            metadata={"name": "Обработка", "synonym": "Обработка с ё"},
            module_bsl='// Unicode: Привет мир',
            form_xml="<Form/>",
        )
        output = tmp_path / "unicode.epf"
        writer.write_epf(output, content)

        read_content = reader.read_epf(output)
        assert read_content is not None
        assert read_content.metadata["name"] == "Обработка"
        assert "ё" in read_content.metadata["synonym"]


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_write_and_read(self, tmp_path: Path, capsys) -> None:
        """CLI write + read round-trip."""
        import sys

        # Создаём исходные файлы
        module_path = tmp_path / "Module.bsl"
        module_path.write_text('Процедура X() Экспорт\nКонецПроцедуры', encoding="utf-8")
        form_path = tmp_path / "Form.xml"
        form_path.write_text('<?xml version="1.0"?><Form/>', encoding="utf-8")
        epf_path = tmp_path / "cli.epf"

        # Write
        sys.argv = [
            "native_writer", "write",
            "--output", str(epf_path),
            "--name", "CLI Test",
            "--synonym", "CLI Test",
            "--module", str(module_path),
            "--form", str(form_path),
        ]
        from src.services.epf.native_writer import main
        rc = main()
        assert rc == 0
        assert epf_path.exists()

        # Read
        sys.argv = ["native_writer", "read", "--input", str(epf_path)]
        rc = main()
        assert rc == 0

    def test_cli_list(self, tmp_path: Path, capsys) -> None:
        """CLI list показывает файлы."""
        import sys

        # Сначала создаём EPF
        epf_path = tmp_path / "list.epf"
        write_epf(
            epf_path,
            name="Test",
            module_bsl='// code',
            form_xml='<Form/>',
        )

        sys.argv = ["native_writer", "list", "--input", str(epf_path)]
        from src.services.epf.native_writer import main
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "Files in" in captured.out
