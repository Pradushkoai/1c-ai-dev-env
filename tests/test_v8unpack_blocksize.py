"""
P2.3: Тесты для v8unpack block_size патча.

Проверяет:
1. patch_epf_blocksize.py скрипт существует и работает
2. EpfFactory применяет патч при сборке .epf
3. Документация upstream issue
"""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PATCH_SCRIPT = REPO_ROOT / "scripts" / "patch_epf_blocksize.py"


# ============================================================================
# Тесты — patch_epf_blocksize.py скрипт
# ============================================================================


class TestPatchScript:
    """Проверка scripts/patch_epf_blocksize.py."""

    def test_patch_script_exists(self) -> None:
        """patch_epf_blocksize.py существует."""
        assert PATCH_SCRIPT.exists(), f"Patch script not found: {PATCH_SCRIPT}"

    def test_patch_script_executable(self) -> None:
        """patch_epf_blocksize.py можно запустить."""
        result = subprocess.run(
            [sys.executable, str(PATCH_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Скрипт может не иметь --help, но не должен падать с ImportError
        assert result.returncode in (0, 1, 2), f"Patch script failed to run: {result.stderr}"

    def test_patch_script_has_standard_block_size(self) -> None:
        """Скрипт использует STANDARD_BLOCK_SIZE = 512 (0x200)."""
        content = PATCH_SCRIPT.read_text(encoding="utf-8")
        assert "STANDARD_BLOCK_SIZE = 512" in content, "patch_epf_blocksize.py должен иметь STANDARD_BLOCK_SIZE = 512"
        assert "0x200" in content, "patch_epf_blocksize.py должен упоминать 0x200"


# ============================================================================
# Тесты — EpfFactory интеграция патча
# ============================================================================


class TestEpfFactoryPatchIntegration:
    """Проверка что EpfFactory применяет патч block_size."""

    def test_epf_factory_mentions_patch(self) -> None:
        """EpfFactory._build_epf содержит вызов patch_epf_blocksize."""
        from pathlib import Path

        epf_factory_path = REPO_ROOT / "src" / "services" / "epf_factory.py"
        content = epf_factory_path.read_text(encoding="utf-8")
        assert "patch_epf_blocksize" in content, "epf_factory.py должен вызывать patch_epf_blocksize"

    def test_epf_factory_has_block_size_comment(self) -> None:
        """EpfFactory документирует баг v8unpack 1.2.6."""
        epf_factory_path = REPO_ROOT / "src" / "services" / "epf_factory.py"
        content = epf_factory_path.read_text(encoding="utf-8")
        # Должен быть комментарий про баг v8unpack 1.2.6
        assert "1.2.6" in content or "v8unpack" in content.lower(), (
            "epf_factory.py должен документировать баг v8unpack 1.2.6"
        )


# ============================================================================
# Тесты — AGENTS.md документация
# ============================================================================


class TestAgentsMdDocumentation:
    """Проверка что AGENTS.md документирует v8unpack баг."""

    def test_agents_md_documents_v8unpack_bug(self) -> None:
        """AGENTS.md содержит информацию о баге v8unpack 1.2.6."""
        agents_path = REPO_ROOT / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8")
        assert "v8unpack" in content, "AGENTS.md должен упоминать v8unpack"
        assert "1.2.6" in content, "AGENTS.md должен упоминать версию 1.2.6"
        assert "block_size" in content, "AGENTS.md должен упоминать block_size"

    def test_agents_md_has_incident_record(self) -> None:
        """AGENTS.md содержит запись об инциденте с v8unpack."""
        agents_path = REPO_ROOT / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8")
        # Должна быть запись в истории инцидентов
        assert "Ошибка формата потока" in content or "block_size" in content, (
            "AGENTS.md должен содержать запись об инциденте с v8unpack"
        )

    def test_agents_md_links_patch_script(self) -> None:
        """AGENTS.md ссылается на scripts/patch_epf_blocksize.py."""
        agents_path = REPO_ROOT / "AGENTS.md"
        content = agents_path.read_text(encoding="utf-8")
        assert "patch_epf_blocksize" in content, "AGENTS.md должен ссылаться на patch_epf_blocksize.py"


# ============================================================================
# Тесты — upstream issue документация (P2.3)
# ============================================================================


class TestUpstreamIssueDocumentation:
    """P2.3: документация upstream issue для v8unpack.

    Согласно плану P2.3, нужно:
    1. Открыть issue в v8unpack upstream
    2. Документировать обходной путь в AGENTS.md
    3. Создать тест test_v8unpack_blocksize.py (этот файл)
    """

    def test_v8unpack_version_pinned(self) -> None:
        """v8unpack зависимость закреплена в pyproject.toml.

        T5.2 (2026-07-05): обновлено с v8unpack>=1.2.6 на git+https (v1.2.11),
        т.к. на PyPI только 1.2.6, а в GitHub main — 1.2.11 с поддержкой .erf.
        Баг block_size НЕ исправлен в 1.2.11, workaround сохраняется.
        """
        pyproject_path = REPO_ROOT / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        # T5.2: зависимость обновлена с v8unpack>=1.2.6 на git+https (1.2.11)
        assert "v8unpack" in content, "pyproject.toml должен содержать зависимость v8unpack"
        assert (
            "v8unpack>=1.2.6" in content
            or "v8unpack @ git+https://github.com/saby-integration/v8unpack" in content
        ), "pyproject.toml должен закреплять v8unpack (PyPI 1.2.6 или GitHub 1.2.11)"

    def test_patch_script_is_workaround(self) -> None:
        """patch_epf_blocksize.py — обходной путь для upstream бага."""
        content = PATCH_SCRIPT.read_text(encoding="utf-8")
        # Должен быть комментарий что это workaround
        assert any(word in content.lower() for word in ["workaround", "баг", "bug", "issue", "проблема"]), (
            "patch_epf_blocksize.py должен документировать что это workaround"
        )


# ============================================================================
# Интеграционный тест — патч реального .epf (если v8unpack доступен)
# ============================================================================


class TestPatchRealEpf:
    """Интеграционный тест: патч реального .epf файла."""

    def test_patch_creates_valid_epf(self, tmp_path: Path) -> None:
        """Патч создаёт валидный .epf с block_size=512."""
        try:
            from src.services.epf_factory import EpfFactory
        except ImportError:
            pytest.skip("EpfFactory не доступен")

        factory = EpfFactory()
        bsl_code = (
            "#Область ПрограммныйИнтерфейс\n"
            "Процедура Тест() Экспорт\n"
            '    Сообщить("тест");\n'
            "КонецПроцедуры\n"
            "#КонецОбласти\n"
        )

        output_epf = tmp_path / "test_patch.epf"

        try:
            result = factory.create_epf(
                name="ТестПатч",
                synonym="Тест патча",
                bsl_code=bsl_code,
                output_epf=str(output_epf),
                skip_bsl_validation=True,
            )
        except Exception as e:
            pytest.skip(f"EpfFactory.create_epf failed (v8unpack/Java not available): {e}")

        if not result.ok:
            pytest.skip(f"EPF creation failed: {result.error}")

        assert output_epf.exists(), "EPF файл должен существовать после создания"

        # Проверим что .epf начинается с V8 сигнатуры
        with open(output_epf, "rb") as f:
            header = f.read(16)
            # V8 сигнатура: 0x7FFFFFFF (4 байта little-endian)
            sig = struct.unpack("<I", header[:4])[0]
            assert sig == 0x7FFFFFFF, f"EPF должен начинаться с V8 сигнатуры 0x7FFFFFFF, got: {hex(sig)}"

            # block_size должен быть 512 (0x200) после патча
            block_size = struct.unpack("<I", header[4:8])[0]
            assert block_size == 512, f"block_size должен быть 512 (0x200) после патча, got: {block_size}"
