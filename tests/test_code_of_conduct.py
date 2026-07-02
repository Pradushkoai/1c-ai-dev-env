"""
Тесты для P2.16: CODE_OF_CONDUCT.md расширен до Contributor Covenant 2.1.

До фикса: CODE_OF_CONDUCT.md содержал всего 19 строк с краткими принципами.
После фикса: полный текст Contributor Covenant 2.1 (~140 строк), индустриальный
стандарт для open-source проектов.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
COC_FILE = REPO_ROOT / "CODE_OF_CONDUCT.md"


class TestCodeOfConduct:
    """CODE_OF_CONDUCT.md должен соответствовать Contributor Covenant 2.1."""

    def test_file_exists(self) -> None:
        assert COC_FILE.exists(), "CODE_OF_CONDUCT.md must exist"

    def test_minimum_length(self) -> None:
        """Должен быть минимум 100 строк (было 19 до P2.16)."""
        content = COC_FILE.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        assert line_count >= 100, (
            f"CODE_OF_CONDUCT.md must have >=100 lines (Contributor Covenant 2.1), "
            f"got {line_count}"
        )

    def test_mentions_contributor_covenant(self) -> None:
        """Должен ссылаться на Contributor Covenant."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "Contributor Covenant" in content, (
            "CODE_OF_CONDUCT.md must mention 'Contributor Covenant'"
        )

    def test_version_2_1(self) -> None:
        """Должна быть версия 2.1."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "2.1" in content, "Must reference version 2.1"

    def test_has_our_pledge_section(self) -> None:
        """Должна быть секция 'Our Pledge'."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "Our Pledge" in content or "Наше обещание" in content

    def test_has_our_standards_section(self) -> None:
        """Должна быть секция 'Our Standards'."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "Our Standards" in content or "Наши стандарты" in content

    def test_has_enforcement_section(self) -> None:
        """Должна быть секция 'Enforcement'."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "Enforcement" in content or "Применение" in content

    def test_has_enforcement_guidelines(self) -> None:
        """Должны быть 4 уровня enforcement: Correction, Warning, Temp Ban, Perm Ban."""
        content = COC_FILE.read_text(encoding="utf-8")
        for level in ("Correction", "Warning", "Temporary Ban", "Permanent Ban"):
            assert level in content, f"Missing enforcement level: {level}"

    def test_has_attribution_section(self) -> None:
        """Должна быть секция Attribution со ссылкой на Contributor Covenant."""
        content = COC_FILE.read_text(encoding="utf-8")
        assert "Attribution" in content
        assert "contributor-covenant.org" in content

    def test_lists_unacceptable_behaviors(self) -> None:
        """Должен перечислять недопустимые поведения."""
        content = COC_FILE.read_text(encoding="utf-8")
        # Ключевые слова из CC 2.1
        assert "harassment" in content.lower() or "преследование" in content.lower()
        assert "sexualized" in content.lower() or "сексуального" in content.lower()

    def test_protected_characteristics_listed(self) -> None:
        """Должен перечислять защищённые характеристики (race, gender, etc.)."""
        content = COC_FILE.read_text(encoding="utf-8")
        # Хотя бы несколько защищённых характеристик
        protected = ["race", "gender", "religion", "nationality"]
        found = sum(1 for p in protected if p in content.lower())
        assert found >= 3, (
            f"CODE_OF_CONDUCT.md must list protected characteristics, "
            f"found {found}/4: race, gender, religion, nationality"
        )
