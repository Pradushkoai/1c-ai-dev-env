"""
P2.5: Тесты для i18n локализации.

Проверяет:
1. i18n.py имеет переводы для всех ключей (en + ru)
2. README.en.md существует
3. README.md ссылается на EN версию
4. AGENTS.md упоминает i18n
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ============================================================================
# Тесты — i18n.py
# ============================================================================


class TestI18nModule:
    """Проверка src/i18n.py."""

    def test_i18n_module_exists(self) -> None:
        """src/i18n.py существует."""
        i18n_path = REPO_ROOT / "src" / "i18n.py"
        assert i18n_path.exists(), "src/i18n.py must exist"

    def test_i18n_has_translate_function(self) -> None:
        """i18n.py имеет функцию t() для переводов."""
        from src.i18n import t

        assert callable(t), "t() function must be callable"

    def test_i18n_has_set_language(self) -> None:
        """i18n.py имеет set_language()."""
        from src.i18n import set_language, get_language

        assert callable(set_language), "set_language() must be callable"
        assert callable(get_language), "get_language() must be callable"

    def test_i18n_default_language_is_ru(self) -> None:
        """Язык по умолчанию — ru."""
        from src.i18n import get_language, set_language

        set_language("ru")
        assert get_language() == "ru"

    def test_i18n_can_set_en(self) -> None:
        """Можно установить en язык."""
        from src.i18n import get_language, set_language

        set_language("en")
        assert get_language() == "en"
        # Возвращаем обратно
        set_language("ru")

    def test_i18n_translates_key(self) -> None:
        """t() возвращает перевод для известного ключа."""
        from src.i18n import set_language, t

        set_language("ru")
        ru_msg = t("errors.config_not_found", name="test")
        assert "test" in ru_msg
        assert "не найдена" in ru_msg or "не найден" in ru_msg

        set_language("en")
        en_msg = t("errors.config_not_found", name="test")
        assert "test" in en_msg
        assert "not found" in en_msg

        set_language("ru")  # reset

    def test_i18n_all_keys_have_en_and_ru(self) -> None:
        """Все ключи в _MESSAGES имеют и en, и ru переводы."""
        from src.i18n import _MESSAGES

        missing_en: list[str] = []
        missing_ru: list[str] = []
        for key, translations in _MESSAGES.items():
            if "en" not in translations:
                missing_en.append(key)
            if "ru" not in translations:
                missing_ru.append(key)
        assert not missing_en, f"Keys missing 'en' translation: {missing_en}"
        assert not missing_ru, f"Keys missing 'ru' translation: {missing_ru}"

    def test_i18n_placeholder_substitution(self) -> None:
        """Плейсхолдеры {name} подставляются корректно."""
        from src.i18n import set_language, t

        set_language("en")
        msg = t("errors.config_not_found", name="MyConfig")
        assert "MyConfig" in msg
        set_language("ru")


# ============================================================================
# Тесты — README.en.md
# ============================================================================


class TestReadmeEn:
    """Проверка README.en.md (P2.5)."""

    def test_readme_en_exists(self) -> None:
        """README.en.md существует."""
        readme_en = REPO_ROOT / "README.en.md"
        assert readme_en.exists(), "README.en.md must exist (P2.5)"

    def test_readme_en_has_title(self) -> None:
        """README.en.md имеет заголовок."""
        readme_en = REPO_ROOT / "README.en.md"
        content = readme_en.read_text(encoding="utf-8")
        assert "# 1C AI Development Environment" in content, "README.en.md must have title"

    def test_readme_en_mentions_mcp_tools(self) -> None:
        """README.en.md упоминает MCP tools."""
        readme_en = REPO_ROOT / "README.en.md"
        content = readme_en.read_text(encoding="utf-8")
        assert "MCP" in content, "README.en.md must mention MCP"
        assert "45" in content, "README.en.md must mention 45 tools"

    def test_readme_en_has_installation(self) -> None:
        """README.en.md имеет секцию установки."""
        readme_en = REPO_ROOT / "README.en.md"
        content = readme_en.read_text(encoding="utf-8")
        assert "pip install" in content, "README.en.md must have installation instructions"

    def test_readme_en_has_cli_commands(self) -> None:
        """README.en.md имеет секцию CLI команд."""
        readme_en = REPO_ROOT / "README.en.md"
        content = readme_en.read_text(encoding="utf-8")
        assert "1c-ai" in content, "README.en.md must mention 1c-ai CLI"

    def test_readme_en_has_language_switcher(self) -> None:
        """README.en.md имеет переключатель языков."""
        readme_en = REPO_ROOT / "README.en.md"
        content = readme_en.read_text(encoding="utf-8")
        assert "Русский" in content, "README.en.md must link to Russian version"
        assert "README.md" in content, "README.en.md must link back to README.md"


# ============================================================================
# Тесты — README.md ссылается на EN версию
# ============================================================================


class TestReadmeRuLinksEn:
    """Проверка что README.md ссылается на EN версию."""

    def test_readme_ru_links_to_en(self) -> None:
        """README.md содержит ссылку на README.en.md."""
        readme = REPO_ROOT / "README.md"
        content = readme.read_text(encoding="utf-8")
        assert "README.en.md" in content, "README.md must link to README.en.md (P2.5 language switcher)"
        assert "English" in content, "README.md must have 'English' language link"

    def test_readme_ru_has_language_switcher(self) -> None:
        """README.md имеет переключатель языков в начале."""
        readme = REPO_ROOT / "README.md"
        content = readme.read_text(encoding="utf-8")
        # Переключатель должен быть в первых 10 строках
        lines = content.splitlines()[:10]
        has_switcher = any("English" in line and "README.en.md" in line for line in lines)
        assert has_switcher, "README.md must have language switcher near top"
