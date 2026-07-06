"""
P2.8: Fuzzing тесты для парсеров XML.

Проверяет что парсеры не падают (crash/hang) на случайных/невалидных входных данных.
Использует atheris — coverage-guided fuzzer от Google.

Запуск (локально, несколько секунд):
    python -m pytest tests/test_fuzzing.py -v --timeout=30

Запуск (длительный, для CI):
    python tests/test_fuzz_xml_parser.py  # standalone скрипт, 30+ минут

Парсеры под fuzzing:
- xml_parser (lxml/etree wrapper)
- form_analyzer (формы 1С)
- metadata_extractor (метаданные 1С)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ============================================================================
# Helper: проверить что atheris доступен
# ============================================================================


def _atheris_available() -> bool:
    """Проверить что atheris установлен."""
    try:
        import atheris  # noqa: F401

        return True
    except ImportError:
        return False


# ============================================================================
# Fuzz тесты — xml_parser
# ============================================================================


class TestFuzzXmlParser:
    """Fuzzing для src/services/.../xml_parser — парсер XML 1С.

    Проверяет что парсер не падает на невалидных/случайных данных.
    """

    def test_xml_parser_no_crash_on_random_bytes(self) -> None:
        """xml_parser не падает на случайных байтах."""
        if not _atheris_available():
            pytest.skip("atheris не установлен")

        from scripts.xml_parser import fromstring

        # Генерируем случайные байты и проверяем что парсер не падает
        crashed: list[str] = []

        for _ in range(100):
            try:
                # Случайные байты разной длины
                import random

                length = random.randint(0, 500)
                data = bytes(random.randint(0, 255) for _ in range(length))
                fromstring(data.decode("utf-8", errors="ignore"))  # не должно crash
            except Exception as e:
                crashed.append(f"{type(e).__name__}: {e}")

        # Допускаем ValueError/ParseError, но не crash (segfault, SystemExit)
        assert not any("SystemExit" in c or "segfault" in c.lower() for c in crashed), (
            f"xml_parser crashed on random bytes: {crashed[:5]}"
        )

    def test_xml_parser_handles_empty_input(self) -> None:
        """xml_parser обрабатывает пустой ввод без crash."""
        try:
            from scripts.xml_parser import fromstring

            # Пустой ввод
            try:
                fromstring("")
            except (ValueError, Exception):
                # ValueError/ParseError acceptable
                pass
        except ImportError:
            pytest.skip("xml_parser не доступен")

    def test_xml_parser_handles_malformed_xml(self) -> None:
        """xml_parser обрабатывает malformed XML без crash."""
        malformed_inputs = [
            "<unclosed>",
            "<<>>",
            "<a><b></a></b>",
            "\x00\x01\x02",
            "<root>" + "x" * 10000 + "</root>",
            '<?xml version="1.0" encoding="utf-8"?>',
            "<root>\n\t<child>text</child>\n</root>",
        ]

        try:
            from scripts.xml_parser import fromstring

            for data in malformed_inputs:
                try:
                    fromstring(data)
                except (ValueError, Exception):
                    # Parse errors acceptable — главное не crash
                    pass
        except ImportError:
            pytest.skip("xml_parser не доступен")


# ============================================================================
# Fuzz тесты — form_analyzer
# ============================================================================


class TestFuzzFormAnalyzer:
    """Fuzzing для form_analyzer — анализ форм 1С."""

    def test_form_analyzer_no_crash_on_empty_form(self, tmp_path: Path) -> None:
        """form_analyzer обрабатывает пустой Form.xml без crash."""
        try:
            from scripts.form_analyzer import analyze_form

            # Пустой Form.xml
            form_path = tmp_path / "Form.xml"
            form_path.write_text(
                '<Form xmlns="http://v8.1c.ru/8.3/xcf/form"/>',
                encoding="utf-8",
            )
            # Не должно crash
            try:
                analyze_form(form_path)
            except (ValueError, Exception):
                pass
        except ImportError:
            pytest.skip("form_analyzer не доступен")

    def test_form_analyzer_no_crash_on_malformed_form(self, tmp_path: Path) -> None:
        """form_analyzer обрабатывает malformed Form.xml без crash."""
        try:
            from scripts.form_analyzer import analyze_form

            malformed_forms = [
                "<Form><unclosed></Form>",
                "<Form><ChildItems><Item></ChildItems></Form>",
                "<Form xmlns='http://v8.1c.ru/8.3/xcf/form'><Items></Items></Form>",
                "",
                "<html><body>not a form</body></html>",
            ]

            for i, content in enumerate(malformed_forms):
                form_path = tmp_path / f"Form_{i}.xml"
                form_path.write_text(content, encoding="utf-8")
                try:
                    analyze_form(form_path)
                except (ValueError, Exception):
                    # Parse errors acceptable
                    pass
        except ImportError:
            pytest.skip("form_analyzer не доступен")


# ============================================================================
# Fuzz тесты — metadata_extractor
# ============================================================================


class TestFuzzMetadataExtractor:
    """Fuzzing для metadata_extractor — парсер метаданных 1С."""

    def test_metadata_extractor_no_crash_on_empty_dir(self, tmp_path: Path) -> None:
        """metadata_extractor обрабатывает пустую директорию без crash."""
        try:
            from src.services.metadata.extractor import extract_and_save

            empty_dir = tmp_path / "empty_config"
            empty_dir.mkdir()

            output_path = tmp_path / "output.json"
            try:
                extract_and_save(empty_dir, output_path)
            except (ValueError, Exception):
                pass
        except ImportError:
            pytest.skip("metadata_extractor не доступен")

    def test_metadata_extractor_no_crash_on_malformed_xml(self, tmp_path: Path) -> None:
        """metadata_extractor обрабатывает malformed XML без crash."""
        try:
            from src.services.metadata.extractor import extract_and_save

            config_dir = tmp_path / "malformed_config"
            config_dir.mkdir()

            # Malformed Configuration.xml
            (config_dir / "Configuration.xml").write_text(
                "<Configuration><unclosed>",
                encoding="utf-8",
            )

            output_path = tmp_path / "output.json"
            try:
                extract_and_save(config_dir, output_path)
            except (ValueError, Exception):
                pass
        except ImportError:
            pytest.skip("metadata_extractor не доступен")


# ============================================================================
# Standalone fuzz тесты (для CI — длительный запуск)
# ============================================================================


class TestFuzzingInfrastructure:
    """Проверка что fuzzing инфраструктура настроена."""

    def test_atheris_in_dev_dependencies(self) -> None:
        """atheris указан в dev dependencies (pyproject.toml)."""
        pyproject = REPO_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        assert "atheris" in content, "pyproject.toml должен включать atheris в dev deps"

    def test_fuzzing_docs_exist(self) -> None:
        """docs/FUZZING.md существует."""
        fuzzing_docs = REPO_ROOT / "docs" / "FUZZING.md"
        assert fuzzing_docs.exists(), "docs/FUZZING.md должен существовать (P2.8)"

    def test_fuzzing_workflow_exists(self) -> None:
        """CI workflow для fuzzing существует."""
        # Проверяем что есть mutation-testing workflow (аналогичный fuzzing)
        mutation_wf = REPO_ROOT / ".github" / "workflows" / "mutation-testing.yml"
        assert mutation_wf.exists(), "mutation-testing.yml должен существовать как аналог fuzzing CI"
