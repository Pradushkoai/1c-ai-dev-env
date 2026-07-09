#!/usr/bin/env python3
"""Тесты для PlatformMethodsIndex — сервиса поиска методов платформы 1С.

Поток 5: Тесты на основе реальных ошибок пользователя.

Покрытие:
  - search() — FTS5 поиск
  - get_method() — получение по имени (O(1))
  - is_available_in() — проверка доступности
  - is_deprecated() — проверка устаревания
  - is_available_in_version() — проверка версии
  - get_methods_by_name() — коллизии имён
  - get_method_in_context() — разрешение коллизий
  - _compare_versions() — сравнение версий
"""

import pytest

from src.services.platform_methods_index import PlatformMethodsIndex


@pytest.fixture
def index():
    """Создаёт индекс для версии 8.3.20."""
    idx = PlatformMethodsIndex(platform_version="8.3.20")
    if not idx.is_available():
        pytest.skip("Platform methods index not built. Run: python3 scripts/build_platform_methods_index.py")
    yield idx
    idx.close()


class TestSearch:
    """FTS5 поиск методов платформы."""

    def test_search_write_log_event(self, index):
        """Поиск WriteLogEvent находит ЗаписьЖурналаРегистрации."""
        results = index.search("WriteLogEvent", limit=5)
        assert len(results) > 0
        assert any(r["name_en"] == "WriteLogEvent" for r in results)

    def test_search_russian_name(self, index):
        """Поиск по русскому имени."""
        results = index.search("ЗаписьЖурналаРегистрации", limit=5)
        assert len(results) > 0
        assert any(r["name_ru"] == "ЗаписьЖурналаРегистрации" for r in results)

    def test_search_returns_fields(self, index):
        """Результат содержит все нужные поля."""
        results = index.search("WriteLogEvent", limit=1)
        assert len(results) > 0
        r = results[0]
        assert "name_ru" in r
        assert "name_en" in r
        assert "category" in r
        assert "availability_raw" in r
        assert "version_since" in r


class TestGetMethod:
    """Получение метода по имени (O(1))."""

    def test_get_method_ru(self, index):
        """Получение по русскому имени."""
        method = index.get_method("ЗаписьЖурналаРегистрации")
        assert method is not None
        assert method["name_ru"] == "ЗаписьЖурналаРегистрации"
        assert method["name_en"] == "WriteLogEvent"

    def test_get_method_en(self, index):
        """Получение по английскому имени."""
        method = index.get_method("WriteLogEvent")
        assert method is not None
        assert method["name_ru"] == "ЗаписьЖурналаРегистрации"

    def test_get_method_not_found(self, index):
        """Несуществующий метод → None."""
        method = index.get_method("НесуществующийМетод12345")
        assert method is None

    def test_get_method_has_availability(self, index):
        """Метод имеет поле availability_json."""
        method = index.get_method("ЗаписьЖурналаРегистрации")
        assert method is not None
        assert method["availability_raw"]
        assert method["availability_json"]

    def test_get_method_has_version(self, index):
        """Метод имеет поле version_since."""
        method = index.get_method("ЗаписьЖурналаРегистрации")
        assert method is not None
        assert method["version_since"]


class TestIsAvailableIn:
    """Проверка доступности метода в контексте."""

    def test_zapis_zhurnala_on_client_false(self, index):
        """ЗаписьЖурналаРегистрации НЕ доступна на thin_client."""
        result = index.is_available_in("ЗаписьЖурналаРегистрации", ["thin_client"])
        assert result is False

    def test_zapis_zhurnala_on_server_true(self, index):
        """ЗаписьЖурналаРегистрации доступна на server."""
        result = index.is_available_in("ЗаписьЖурналаРегистрации", ["server"])
        assert result is True

    def test_unknown_method_returns_true(self, index):
        """Неизвестный метод → True (не можем проверить)."""
        result = index.is_available_in("НесуществующийМетод", ["thin_client"])
        assert result is True

    def test_with_object_type(self, index):
        """Проверка с object_type для разрешения коллизий."""
        # HTTPСоединение.Получить
        result = index.is_available_in("Получить", ["thin_client"], object_type="HTTPСоединение")
        # Должно найти метод HTTPСоединение.Получить
        assert isinstance(result, bool)


class TestCollisions:
    """Разрешение коллизий имён."""

    def test_get_methods_by_name(self, index):
        """Метод 'Получить' существует во множестве контекстов."""
        methods = index.get_methods_by_name("Получить")
        assert len(methods) > 100  # ~263 метода с именем 'Получить'

    def test_get_method_in_context(self, index):
        """HTTPСоединение.Получить — конкретный метод."""
        method = index.get_method_in_context("Получить", "HTTPСоединение")
        assert method is not None
        assert "HTTPСоединение" in method.get("category", "")


class TestVersionChecks:
    """Проверки версий."""

    def test_compare_versions(self):
        """Сравнение версий платформы."""
        assert PlatformMethodsIndex._compare_versions("8.3.18", "8.3.20") == -1
        assert PlatformMethodsIndex._compare_versions("8.3.20", "8.3.20") == 0
        assert PlatformMethodsIndex._compare_versions("8.3.25", "8.3.20") == 1
        assert PlatformMethodsIndex._compare_versions("8.0", "8.3.20") == -1

    def test_is_available_in_version(self, index):
        """ЗаписьЖурналаРегистрации доступна с 8.0."""
        assert index.is_available_in_version("ЗаписьЖурналаРегистрации", "8.0") is True
        assert index.is_available_in_version("ЗаписьЖурналаРегистрации", "8.3.20") is True
        assert index.is_available_in_version("ЗаписьЖурналаРегистрации", "7.0") is False


class TestListVersions:
    """Список доступных версий."""

    def test_list_versions(self, index):
        """Должна быть хотя бы одна версия."""
        versions = index.list_versions()
        assert len(versions) > 0
        assert "8.3.20" in versions
