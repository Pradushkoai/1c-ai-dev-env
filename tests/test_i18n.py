"""
Тесты для src/i18n.py — локализация сообщений (en/ru).
"""

from __future__ import annotations

import pytest

from src.i18n import get_language, set_language, t


class TestLanguageSwitching:
    def test_default_language_is_ru(self):
        assert get_language() == "ru"

    def test_set_language_en(self):
        set_language("en")
        assert get_language() == "en"
        set_language("ru")  # restore

    def test_set_language_ru(self):
        set_language("ru")
        assert get_language() == "ru"

    def test_set_invalid_language_ignored(self):
        set_language("fr")
        assert get_language() == "ru"  # unchanged


class TestTranslation:
    def test_ru_config_not_found(self):
        set_language("ru")
        msg = t("errors.config_not_found", name="ut11")
        assert "ut11" in msg
        assert "не найдена" in msg

    def test_en_config_not_found(self):
        set_language("en")
        msg = t("errors.config_not_found", name="ut11")
        assert "ut11" in msg
        assert "not found" in msg
        set_language("ru")  # restore

    def test_ru_unknown_tool(self):
        set_language("ru")
        msg = t("errors.unknown_tool", name="bad_tool")
        assert "bad_tool" in msg
        assert "Unknown tool" in msg

    def test_en_unknown_tool(self):
        set_language("en")
        msg = t("errors.unknown_tool", name="bad_tool")
        assert "bad_tool" in msg
        assert "Unknown tool" in msg
        set_language("ru")

    def test_ru_file_not_found(self):
        set_language("ru")
        msg = t("errors.file_not_found", path="/tmp/test.bsl")
        assert "/tmp/test.bsl" in msg
        assert "не найден" in msg

    def test_en_file_not_found(self):
        set_language("en")
        msg = t("errors.file_not_found", path="/tmp/test.bsl")
        assert "/tmp/test.bsl" in msg
        assert "not found" in msg
        set_language("ru")

    def test_missing_key_returns_key(self):
        msg = t("nonexistent.key")
        assert msg == "nonexistent.key"

    def test_no_kwargs(self):
        set_language("ru")
        msg = t("errors.config_name_required")
        assert "config_name" in msg

    def test_partial_kwargs(self):
        """Если не все плейсхолдеры переданы — сообщение не падает."""
        set_language("ru")
        msg = t("errors.config_not_found")  # без name=
        assert "config_not_found" in msg or "не найдена" in msg

    def test_epf_build_failed_ru(self):
        set_language("ru")
        msg = t("errors.epf_build_failed", error="some error")
        assert "some error" in msg
        assert "v8unpack" in msg

    def test_epf_build_failed_en(self):
        set_language("en")
        msg = t("errors.epf_build_failed", error="some error")
        assert "some error" in msg
        assert "v8unpack" in msg
        set_language("ru")

    def test_success_messages_ru(self):
        set_language("ru")
        msg = t("success.config_added", name="ut11", version="11.5", objects="500")
        assert "ut11" in msg
        assert "11.5" in msg
        assert "500" in msg

    def test_success_messages_en(self):
        set_language("en")
        msg = t("success.config_added", name="ut11", version="11.5", objects="500")
        assert "ut11" in msg
        assert "11.5" in msg
        assert "500" in msg
        assert "Added" in msg
        set_language("ru")
