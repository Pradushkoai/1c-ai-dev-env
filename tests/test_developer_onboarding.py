"""
S6: Тесты для Developer Onboarding.

Проверяет:
1. QUICK_START.md существует и корректен
2. ROADMAP.md существует и содержит v3 план
3. ADR каталог существует с 5+ записями
4. CONTRIBUTING.md обновлён (ссылается на QUICK_START, ROADMAP, ADR)
5. MIGRATION_GUIDE.md существует
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestQuickStart:
    """Проверка docs/QUICK_START.md."""

    def test_quick_start_exists(self) -> None:
        """docs/QUICK_START.md существует."""
        path = REPO_ROOT / "docs" / "QUICK_START.md"
        assert path.exists(), "docs/QUICK_START.md must exist (S6)"

    def test_quick_start_has_installation(self) -> None:
        """QUICK_START содержит инструкцию установки."""
        content = (REPO_ROOT / "docs" / "QUICK_START.md").read_text(encoding="utf-8")
        assert "pip install" in content, "QUICK_START must have installation"

    def test_quick_start_has_5_minutes(self) -> None:
        """QUICK_START упоминает 5 минут."""
        content = (REPO_ROOT / "docs" / "QUICK_START.md").read_text(encoding="utf-8")
        assert "5" in content and ("мин" in content or "minute" in content.lower()), (
            "QUICK_START should mention 5 minutes"
        )

    def test_quick_start_has_validate(self) -> None:
        """QUICK_START содержит 1c-ai validate."""
        content = (REPO_ROOT / "docs" / "QUICK_START.md").read_text(encoding="utf-8")
        assert "1c-ai validate" in content or "validate" in content, "QUICK_START should mention validate command"

    def test_quick_start_has_links(self) -> None:
        """QUICK_START содержит ссылки на другие документы."""
        content = (REPO_ROOT / "docs" / "QUICK_START.md").read_text(encoding="utf-8")
        assert "README.md" in content, "QUICK_START should link to README"
        assert "AGENTS.md" in content, "QUICK_START should link to AGENTS"
        assert "adr/" in content, "QUICK_START should link to ADR"


class TestRoadmap:
    """Проверка ROADMAP.md."""

    def test_roadmap_exists(self) -> None:
        """ROADMAP.md существует в корне репозитория."""
        path = REPO_ROOT / "ROADMAP.md"
        assert path.exists(), "ROADMAP.md must exist (S6)"

    def test_roadmap_has_v3_plan(self) -> None:
        """ROADMAP содержит план v3."""
        content = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        assert "v3" in content or "S7" in content, "ROADMAP must reference v3 plan"

    def test_roadmap_has_current_version(self) -> None:
        """ROADMAP указывает текущую версию v6.0.0."""
        content = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        assert "6.0.0" in content, "ROADMAP must reference v6.0.0"

    def test_roadmap_has_principles(self) -> None:
        """ROADMAP содержит принципы."""
        content = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        assert "Automation First" in content or "Sustainable Pace" in content, "ROADMAP must contain principles"

    def test_roadmap_has_timeline(self) -> None:
        """ROADMAP содержит timeline."""
        content = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        assert "Q2 2027" in content or "Q3 2027" in content, "ROADMAP must contain timeline"


class TestADR:
    """Проверка ADR каталога."""

    def test_adr_dir_exists(self) -> None:
        """adr/ директория существует."""
        path = REPO_ROOT / "adr"
        assert path.is_dir(), "adr/ directory must exist (S6)"

    def test_adr_readme_exists(self) -> None:
        """adr/README.md существует."""
        path = REPO_ROOT / "adr" / "README.md"
        assert path.exists(), "adr/README.md must exist"

    def test_adr_template_exists(self) -> None:
        """adr/0000-template.md существует."""
        path = REPO_ROOT / "adr" / "0000-template.md"
        assert path.exists(), "adr/0000-template.md must exist"

    def test_adr_has_5_records(self) -> None:
        """ADR каталог содержит 5+ записей (не считая README и template)."""
        adr_dir = REPO_ROOT / "adr"
        adr_files = [f for f in adr_dir.glob("*.md") if f.name not in ("README.md", "0000-template.md")]
        assert len(adr_files) >= 5, f"Expected 5+ ADR records, found {len(adr_files)}: {[f.name for f in adr_files]}"

    def test_adr_0001_solo_path(self) -> None:
        """ADR-0001 (solo development path) существует."""
        path = REPO_ROOT / "adr" / "0001-solo-development-path.md"
        assert path.exists(), "ADR-0001 must exist"

    def test_adr_readme_has_index(self) -> None:
        """adr/README.md содержит индекс ADR."""
        content = (REPO_ROOT / "adr" / "README.md").read_text(encoding="utf-8")
        assert "ADR-0001" in content, "adr/README.md must index ADR-0001"
        assert "ADR-0005" in content, "adr/README.md must index ADR-0005"


class TestContributingUpdated:
    """Проверка что CONTRIBUTING.md обновлён для v6.0."""

    def test_contributing_links_quick_start(self) -> None:
        """CONTRIBUTING ссылается на QUICK_START.md."""
        content = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "QUICK_START" in content, "CONTRIBUTING must link to QUICK_START"

    def test_contributing_links_roadmap(self) -> None:
        """CONTRIBUTING ссылается на ROADMAP.md."""
        content = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "ROADMAP" in content, "CONTRIBUTING must link to ROADMAP"

    def test_contributing_links_adr(self) -> None:
        """CONTRIBUTING ссылается на adr/."""
        content = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "adr/" in content, "CONTRIBUTING must link to adr/"

    def test_contributing_mentions_snapshot_update(self) -> None:
        """CONTRIBUTING упоминает обновление snapshot."""
        content = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "snapshot-update" in content or "snapshot" in content.lower(), (
            "CONTRIBUTING must mention snapshot update for MCP tools"
        )


class TestMigrationGuide:
    """Проверка docs/MIGRATION_GUIDE.md."""

    def test_migration_guide_exists(self) -> None:
        """docs/MIGRATION_GUIDE.md существует."""
        path = REPO_ROOT / "docs" / "MIGRATION_GUIDE.md"
        assert path.exists(), "docs/MIGRATION_GUIDE.md must exist (S7/S6)"

    def test_migration_guide_has_breaking_changes(self) -> None:
        """MIGRATION_GUIDE описывает breaking changes."""
        content = (REPO_ROOT / "docs" / "MIGRATION_GUIDE.md").read_text(encoding="utf-8")
        assert "Breaking" in content or "breaking" in content.lower(), "MIGRATION_GUIDE must describe breaking changes"

    def test_migration_guide_has_install_sh_change(self) -> None:
        """MIGRATION_GUIDE описывает изменение install.sh."""
        content = (REPO_ROOT / "docs" / "MIGRATION_GUIDE.md").read_text(encoding="utf-8")
        assert "install.sh" in content, "MIGRATION_GUIDE must mention install.sh change"
        assert "ONEC_AI_DEV_ENV_ROOT" in content or "--target" in content, (
            "MIGRATION_GUIDE must mention --target / ONEC_AI_DEV_ENV_ROOT"
        )
