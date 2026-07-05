"""
D2.2 + D2.3 (2026-07-05): Тесты для builders декомпозиция + версионирование индексов.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestBuildersDecomposition:
    """D2.2: проверка декомпозиции builders/config_index.py."""

    def test_config_index_has_d2_2_note(self) -> None:
        """config_index.py содержит D2.2 note в docstring."""
        path = REPO_ROOT / "src" / "services" / "builders" / "config_index.py"
        content = path.read_text(encoding="utf-8")
        assert "D2.2" in content, "config_index.py должен содержать D2.2 note"

    def test_builders_init_exists(self) -> None:
        """builders/__init__.py существует."""
        assert (REPO_ROOT / "src" / "services" / "builders" / "__init__.py").exists()

    def test_config_index_has_build_function(self) -> None:
        """config_index.py содержит функцию build_index."""
        path = REPO_ROOT / "src" / "services" / "builders" / "config_index.py"
        content = path.read_text(encoding="utf-8")
        assert "def build_index" in content

    def test_config_index_has_parse_functions(self) -> None:
        """config_index.py содержит функции парсинга."""
        path = REPO_ROOT / "src" / "services" / "builders" / "config_index.py"
        content = path.read_text(encoding="utf-8")
        assert "def parse_configuration_xml" in content
        assert "def parse_dumpinfo" in content


class TestIndexVersioning:
    """D2.3: версионирование индексов."""

    def test_source_hash_field_exists(self) -> None:
        """IndexFreshnessReport содержит source_hash (D2.4/D2.3)."""
        from src.services.config_validator import IndexFreshnessReport
        report = IndexFreshnessReport(config_name="test")
        assert hasattr(report, "source_hash")

    def test_source_hash_match_field_exists(self) -> None:
        """IndexStatus содержит source_hash_match (D2.4/D2.3)."""
        from src.services.config_validator import IndexStatus
        status = IndexStatus(name="test", path=None)
        assert hasattr(status, "source_hash_match")

    def test_compute_source_hash_exists(self) -> None:
        """ConfigValidator._compute_source_hash существует (D2.4)."""
        from src.services.config_validator import ConfigValidator
        assert hasattr(ConfigValidator, "_compute_source_hash")

    def test_save_source_hash_exists(self) -> None:
        """ConfigValidator.save_source_hash существует (D2.4)."""
        from src.services.config_validator import ConfigValidator
        assert hasattr(ConfigValidator, "save_source_hash")
