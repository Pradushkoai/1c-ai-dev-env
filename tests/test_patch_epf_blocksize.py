"""
Тесты для scripts/patch_epf_blocksize.py — патчер v8unpack бага.

Контекст (из AGENTS.md):
  v8unpack 1.2.6 пишет TOC block_size = doc_size (фактический размер данных),
  а 1С ожидает всегда block_size = 0x200 (512). Из-за этого «Ошибка формата потока».

  Патчер проходит по .epf и заменяет TOC block_size на 512.

Этот скрипт критичен для EpfFactory — без него собранные .epf не открываются в 1С.
AGENTS.md явно требует: «Всегда применяй патч scripts/patch_epf_blocksize.py
после v8unpack -B. EpfFactory делает это автоматически».
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path
_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from patch_epf_blocksize import (  # noqa: E402
    BLOCK_HEADER_SIZE,
    HEADER_SIZE,
    STANDARD_BLOCK_SIZE,
    V8_SIGNATURE,
    make_block_header,
    main,
    parse_block_header,
    patch_epf,
)


# ============================================================================
# Helpers — создание синтетических .epf для тестов
# ============================================================================


def _make_block_header_bytes(doc_size: int, block_size: int, next_block: int) -> bytes:
    """Создать заголовок блока (31 байт) в формате v8unpack."""
    return f"\r\n{doc_size:08x} {block_size:08x} {next_block:08x} \r\n".encode("ascii")


def _make_minimal_epf(
    header_block_size: int = STANDARD_BLOCK_SIZE,
    toc_block_size: int = 100,  # намеренно неправильный (должен быть 512)
    num_files: int = 1,
) -> bytes:
    """Создать минимальный валидный .epf с заданными block_size.

    Структура:
      - Header (16 байт): sig + header_block_size + num_files + reserved
      - TOC block: заголовок 31 байт + данные (num_files × 12 байт)
    """
    header = struct.pack("<IIII", V8_SIGNATURE, header_block_size, num_files, 0)
    # TOC data: num_files × 12 байт (3 × uint32: desc/data/next)
    toc_data = b"\x00" * (num_files * 12)
    toc_doc_size = BLOCK_HEADER_SIZE + len(toc_data)
    toc_header = _make_block_header_bytes(toc_doc_size, toc_block_size, 0x7FFFFFFF)
    return header + toc_header + toc_data


# ============================================================================
# Тесты — parse_block_header
# ============================================================================


class TestParseBlockHeader:
    """parse_block_header() — парсинг 31-байтного заголовка блока."""

    def test_parses_valid_header(self) -> None:
        """Должен парсить валидный заголовок блока."""
        header = _make_block_header_bytes(0x100, 0x200, 0x7FFFFFFF)
        result = parse_block_header(header, 0)
        assert result is not None
        assert result["doc_size"] == 0x100
        assert result["block_size"] == 0x200
        assert result["next_block"] == 0x7FFFFFFF
        assert result["header_size"] == BLOCK_HEADER_SIZE

    def test_returns_none_for_no_crlf_prefix(self) -> None:
        """Должен возвращать None если заголовок не начинается с \\r\\n."""
        bad_header = b"XX" + b"\x00" * (BLOCK_HEADER_SIZE - 2)
        assert parse_block_header(bad_header, 0) is None

    def test_returns_none_for_offset_beyond_data(self) -> None:
        """Должен возвращать None если offset + 31 > len(data)."""
        data = b"\r\n" + b"\x00" * 5  # всего 7 байт
        assert parse_block_header(data, 0) is None

    def test_returns_none_for_invalid_hex(self) -> None:
        """Должен возвращать None если hex значения невалидны."""
        # \r\n + 'ZZZZZZZZ ZZZZZZZZ ZZZZZZZZ' + ' \r\n
        bad = b"\r\nZZZZZZZZ ZZZZZZZZ ZZZZZZZZ \r\n"
        assert parse_block_header(bad, 0) is None

    def test_returns_none_for_wrong_parts_count(self) -> None:
        """Должен возвращать None если частей не 3."""
        bad = b"\r\n00000054 00000200 \r\n"  # только 2 части
        assert parse_block_header(bad, 0) is None


# ============================================================================
# Тесты — make_block_header
# ============================================================================


class TestMakeBlockHeader:
    """make_block_header() — создание нового заголовка блока."""

    def test_creates_31_byte_header(self) -> None:
        """Должен создавать заголовок ровно 31 байт."""
        header = make_block_header(0x100, 0x200, 0x7FFFFFFF)
        assert len(header) == BLOCK_HEADER_SIZE

    def test_starts_with_crlf(self) -> None:
        """Должен начинаться с \\r\\n."""
        header = make_block_header(0, 0, 0)
        assert header[:2] == b"\r\n"

    def test_ends_with_crlf(self) -> None:
        """Должен заканчиваться на ' \\r\\n (пробел + CRLF)."""
        header = make_block_header(0, 0, 0)
        assert header[-3:] == b" \r\n"

    def test_round_trips_with_parse(self) -> None:
        """make_block_header → parse_block_header должен быть identity."""
        original = {"doc_size": 0x100, "block_size": 0x200, "next_block": 0x7FFFFFFF}
        header_bytes = make_block_header(original["doc_size"], original["block_size"], original["next_block"])
        parsed = parse_block_header(header_bytes, 0)
        assert parsed is not None
        assert parsed["doc_size"] == original["doc_size"]
        assert parsed["block_size"] == original["block_size"]
        assert parsed["next_block"] == original["next_block"]


# ============================================================================
# Тесты — patch_epf
# ============================================================================


class TestPatchEpf:
    """patch_epf() — основной функционал патчера."""

    def test_patches_toc_block_size_to_512(self, tmp_path: Path) -> None:
        """TOC block_size должен стать 512 после патча."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        # Создаём .epf с неправильным TOC block_size (100 вместо 512)
        bad_epf = _make_minimal_epf(toc_block_size=100)
        input_epf.write_bytes(bad_epf)

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert result["blocks_patched"] >= 1

        # Проверяем что output имеет TOC block_size = 512
        patched_data = output_epf.read_bytes()
        toc_header = parse_block_header(patched_data, HEADER_SIZE)
        assert toc_header is not None
        assert toc_header["block_size"] == STANDARD_BLOCK_SIZE

    def test_no_patch_when_already_512(self, tmp_path: Path) -> None:
        """Если TOC block_size уже 512, не должен патчить."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        good_epf = _make_minimal_epf(toc_block_size=STANDARD_BLOCK_SIZE)
        input_epf.write_bytes(good_epf)

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert result["blocks_patched"] == 0
        # Output идентичен input
        assert output_epf.read_bytes() == good_epf

    def test_patches_header_block_size(self, tmp_path: Path) -> None:
        """Header block_size тоже должен стать 512 если был неправильный."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        # Header block_size = 100 (неправильный), TOC block_size = 512
        bad_epf = _make_minimal_epf(header_block_size=100, toc_block_size=STANDARD_BLOCK_SIZE)
        input_epf.write_bytes(bad_epf)

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert result["blocks_patched"] == 1
        # Проверяем что header block_size = 512
        patched_data = output_epf.read_bytes()
        _, header_bs, _, _ = struct.unpack_from("<IIII", patched_data, 0)
        assert header_bs == STANDARD_BLOCK_SIZE

    def test_returns_error_for_too_small_file(self, tmp_path: Path) -> None:
        """Должен возвращать ok=False для файла < 16 байт."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"
        input_epf.write_bytes(b"\x00" * 10)  # 10 байт < 16

        result = patch_epf(input_epf, output_epf)
        assert result["ok"] is False
        assert "слишком маленький" in result["error"]

    def test_returns_error_for_wrong_signature(self, tmp_path: Path) -> None:
        """Должен возвращать ok=False для файла с неверной сигнатурой."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        # Сигнатура 0x00000000 вместо 0x7FFFFFFF
        bad_header = struct.pack("<IIII", 0x00000000, 512, 1, 0)
        input_epf.write_bytes(bad_header + b"\x00" * 100)

        result = patch_epf(input_epf, output_epf)
        assert result["ok"] is False
        assert "сигнатур" in result["error"]

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        """Должен создавать родительские директории для output_path."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "subdir" / "nested" / "output.epf"

        input_epf.write_bytes(_make_minimal_epf(toc_block_size=100))

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert output_epf.exists()

    def test_block_details_recorded(self, tmp_path: Path) -> None:
        """block_details должен содержать информацию о патченных блоках."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        input_epf.write_bytes(_make_minimal_epf(toc_block_size=100))

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert len(result["block_details"]) >= 1
        detail = result["block_details"][0]
        assert "type" in detail
        assert "offset" in detail
        assert "old" in detail
        assert "new" in detail
        assert detail["new"] == STANDARD_BLOCK_SIZE

    def test_size_bytes_in_result(self, tmp_path: Path) -> None:
        """size_bytes в result должен равняться размеру output файла."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        epf_data = _make_minimal_epf(toc_block_size=100)
        input_epf.write_bytes(epf_data)

        result = patch_epf(input_epf, output_epf)

        assert result["ok"] is True
        assert result["size_bytes"] == len(epf_data)  # размер не меняется


# ============================================================================
# Тесты — main() CLI
# ============================================================================


class TestMain:
    """main() — CLI точка входа."""

    def test_main_patches_epf(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() должна пропатчить .epf и вывести результат."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        input_epf.write_bytes(_make_minimal_epf(toc_block_size=100))

        # Мокаем sys.argv
        old_argv = sys.argv
        try:
            sys.argv = ["patch_epf_blocksize.py", str(input_epf), str(output_epf)]
            main()
            captured = capsys.readouterr()
            assert "OK: True" in captured.out
            assert output_epf.exists()
        finally:
            sys.argv = old_argv

    def test_main_exits_on_wrong_args(self, tmp_path: Path) -> None:
        """main() должна exit(1) если аргументов не 3."""
        old_argv = sys.argv
        try:
            sys.argv = ["patch_epf_blocksize.py", "only_one_arg"]
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv

    def test_main_exits_on_invalid_file(self, tmp_path: Path) -> None:
        """main() должна exit(1) при ошибке обработки."""
        input_epf = tmp_path / "input.epf"
        output_epf = tmp_path / "output.epf"

        # Создаём невалидный .epf (нет сигнатуры)
        input_epf.write_bytes(b"\x00" * 100)

        old_argv = sys.argv
        try:
            sys.argv = ["patch_epf_blocksize.py", str(input_epf), str(output_epf)]
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv


# ============================================================================
# Тесты — константы
# ============================================================================


class TestConstants:
    """Константы модуля — проверка значений."""

    def test_v8_signature_value(self) -> None:
        """V8_SIGNATURE должен быть 0x7FFFFFFF."""
        assert V8_SIGNATURE == 0x7FFFFFFF

    def test_standard_block_size_value(self) -> None:
        """STANDARD_BLOCK_SIZE должен быть 512 (0x200)."""
        assert STANDARD_BLOCK_SIZE == 512
        assert STANDARD_BLOCK_SIZE == 0x200

    def test_header_size_value(self) -> None:
        """HEADER_SIZE должен быть 16 байт (sig + block_size + num_files + reserved)."""
        assert HEADER_SIZE == 16

    def test_block_header_size_value(self) -> None:
        """BLOCK_HEADER_SIZE должен быть 31 байт."""
        assert BLOCK_HEADER_SIZE == 31

    def test_header_size_is_4_times_uint32(self) -> None:
        """HEADER_SIZE должен вмещать 4 uint32 (4 × 4 = 16)."""
        assert HEADER_SIZE == 4 * 4
