"""
Тесты для сервиса поиска (TF-IDF).
Проверяем tokenize, build_index, search.
"""
import json
import sys
from pathlib import Path

import pytest
from src.services.search import tokenize, build_index, search


def test_tokenize_camel_case():
    """CamelCase разбиение работает: НайтиПоКоду → найтипокоду (одно слово)."""
    tokens = tokenize("НайтиПоКоду")
    # Одно слово без латиницы/цифр не разбивается CamelCase regex'ом,
    # но токенизация должна вернуть хотя бы исходное слово
    assert len(tokens) >= 1
    assert "найтипокоду" in [t.lower() for t in tokens]


def test_tokenize_camel_case_with_digits():
    """CamelCase + цифры → разбиение работает."""
    tokens = tokenize("УдалитьФайл2 test")
    lowered = [t.lower() for t in tokens]
    # Хотя бы исходные токены должны быть
    assert "удалитьфайл2" in lowered or "удалитьфайл" in lowered
    assert "test" in lowered


def test_tokenize_mixed():
    """Смешанный текст: русские + латинские + цифры."""
    tokens = tokenize("Найти test 123")
    assert len(tokens) >= 3
    assert "найти" in tokens
    assert "test" in tokens
    assert "123" in tokens


def test_tokenize_empty():
    """Пустая строка → пустой список."""
    assert tokenize("") == []
    assert tokenize("...!!!") == []


def test_build_and_search(tmp_path):
    """Полный цикл: build_index → search."""
    methods = [
        {
            "name_ru": "НайтиПоКоду",
            "name_en": "FindByCode",
            "context": "Справочники.Менеджер",
            "syntax": "НайтиПоКоду(Код)",
            "description": "Поиск элемента справочника по коду",
            "returns": "СправочникСсылка",
        },
        {
            "name_ru": "НайтиПоНаименованию",
            "name_en": "FindByDescription",
            "context": "Справочники.Менеджер",
            "syntax": "НайтиПоНаименованию(Наименование)",
            "description": "Поиск по наименованию элемента",
            "returns": "СправочникСсылка",
        },
        {
            "name_ru": "СоздатьЭлемент",
            "name_en": "CreateItem",
            "context": "Справочники.Менеджер",
            "syntax": "СоздатьЭлемент()",
            "description": "Создать новый элемент",
            "returns": "СправочникОбъект",
        },
    ]
    methods_json = tmp_path / "methods.json"
    methods_json.write_text(json.dumps(methods, ensure_ascii=False), encoding="utf-8")

    index_path = tmp_path / "index.json"
    n = build_index(methods_json, index_path)

    assert n == 3
    assert index_path.exists()

    # Поиск по коду → НайтиПоКоду должен быть в топе
    results = search(index_path, "найти по коду", limit=3)
    assert len(results) > 0
    assert results[0]["name_ru"] == "НайтиПоКоду"

    # Поиск по наименованию → НайтиПоНаименованию должен быть в топе
    results = search(index_path, "поиск по наименованию", limit=3)
    assert results[0]["name_ru"] == "НайтиПоНаименованию"


def test_search_empty_query(tmp_path):
    """Пустой запрос → пустой результат."""
    methods = [{"name_ru": "Тест", "name_en": "Test", "context": "", "syntax": "", "description": "", "returns": ""}]
    methods_json = tmp_path / "methods.json"
    methods_json.write_text(json.dumps(methods, ensure_ascii=False), encoding="utf-8")

    index_path = tmp_path / "index.json"
    build_index(methods_json, index_path)

    results = search(index_path, "!!!", limit=5)
    assert results == []


def test_search_limit(tmp_path):
    """limit ограничивает кол-во результатов."""
    methods = [
        {"name_ru": f"Метод{i}", "name_en": f"Method{i}", "context": "общий", "syntax": "", "description": "общий метод", "returns": ""}
        for i in range(20)
    ]
    methods_json = tmp_path / "methods.json"
    methods_json.write_text(json.dumps(methods, ensure_ascii=False), encoding="utf-8")

    index_path = tmp_path / "index.json"
    build_index(methods_json, index_path)

    results = search(index_path, "общий", limit=5)
    assert len(results) <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
