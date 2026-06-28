"""
Тесты для BM25+триграммы поиска (services/search_bm25.py).
"""
import json
import pytest
from pathlib import Path

from src.services.search_bm25 import (
    stem_russian, stem_english, stem,
    tokenize_stemmed,
    make_trigrams, trigram_similarity,
    build_index_bm25, search_bm25,
    detect_index_version, search_auto,
    BM25_K1, BM25_B,
)


# ============ СТЕММЕР ============

class TestStemmer:
    def test_russian_basic(self):
        assert stem_russian("поиск") == "поиск"
        assert stem_russian("поиска") == "поиск"
        assert stem_russian("поиске") == "поиск"
        assert stem_russian("поиску") == "поиск"

    def test_russian_long_word(self):
        # Длинные слова обрезаются
        result = stem_russian("настройками")
        assert result != "настройками"

    def test_russian_short_word_kept(self):
        # Короткие слова не обрезаются
        assert stem_russian("дом") == "дом"
        assert stem_russian("код") == "код"

    def test_english_basic(self):
        assert stem_english("search") == "search"
        assert stem_english("searching") != "searching"
        assert stem_english("searched") != "searched"
        assert stem_english("files") != "files"

    def test_english_short_word_kept(self):
        assert stem_english("cat") == "cat"
        assert stem_english("dog") == "dog"

    def test_stem_dispatches_by_lang(self):
        # Русское слово → русский стеммер
        assert stem("поиск") == stem_russian("поиск")
        # Английское → английский
        assert stem("search") == stem_english("search")


# ============ ТОКЕНИЗАЦИЯ ============

class TestTokenizeStemmed:
    def test_basic(self):
        tokens = tokenize_stemmed("поиск элемента")
        assert "поиск" in tokens
        # "элемента" → стеммер обрежет окончание
        assert any(t.startswith("элем") for t in tokens)

    def test_camel_case_split(self):
        tokens = tokenize_stemmed("НайтиПоКоду")
        # Должно разбиться на найти/по/код
        lowered = [t.lower() for t in tokens]
        assert any(t.startswith("найт") for t in lowered)
        assert "по" in lowered or any(t.startswith("по") for t in lowered)

    def test_empty(self):
        assert tokenize_stemmed("") == []
        assert tokenize_stemmed("...!!!") == []

    def test_mixed_lang(self):
        tokens = tokenize_stemmed("Найти test 123")
        assert len(tokens) >= 2

    def test_min_token_length(self):
        # Токены короче 2 символов отбрасываются
        tokens = tokenize_stemmed("а бв я")
        # "а" и "я" — 1 символ, отбрасываются; "бв" — 2 символа, остаётся
        assert all(len(t) >= 2 for t in tokens)


# ============ ТРИГРАММЫ ============

class TestTrigrams:
    def test_make_trigrams_basic(self):
        # "кот" → $$кот$$ → {'$$к', '$ко', 'кот', 'от$'}
        trigrams = make_trigrams("кот")
        assert "$$к" in trigrams
        assert "$ко" in trigrams
        assert "кот" in trigrams
        assert "от$" in trigrams

    def test_make_trigrams_short(self):
        trigrams = make_trigrams("а")
        # "$$а$$" → {'$$а', '$а$', 'а$$'}
        assert len(trigrams) == 3

    def test_make_trigrams_empty(self):
        assert make_trigrams("") == set()

    def test_similarity_identical(self):
        t = make_trigrams("найти")
        assert trigram_similarity(t, t) == 1.0

    def test_similarity_different(self):
        # Непересекающиеся множества → similarity = 0
        t1 = make_trigrams("найти")
        t2 = make_trigrams("удалить")
        assert trigram_similarity(t1, t2) == 0.0

    def test_similarity_partial_overlap(self):
        # Частично пересекающиеся слова (общие триграммы)
        t1 = make_trigrams("поиск")
        t2 = make_trigrams("поиска")
        sim = trigram_similarity(t1, t2)
        assert 0 < sim < 1.0

    def test_similarity_disjoint(self):
        t1 = make_trigrams("aaa")
        t2 = make_trigrams("zzz")
        assert trigram_similarity(t1, t2) == 0.0

    def test_similarity_empty(self):
        assert trigram_similarity(set(), set()) == 0.0
        assert trigram_similarity(make_trigrams("aaa"), set()) == 0.0


# ============ BM25 ИНДЕКС ============

@pytest.fixture
def methods_fixture(tmp_path):
    """Создать тестовый файл с методами 1С."""
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
            "description": "Поиск элемента справочника по наименованию",
            "returns": "СправочникСсылка",
        },
        {
            "name_ru": "УдалитьФайл",
            "name_en": "DeleteFile",
            "context": "ФайловаяСистема",
            "syntax": "УдалитьФайл(Путь)",
            "description": "Удаление файла с диска",
            "returns": "Булево",
        },
        {
            "name_ru": "СоздатьКаталог",
            "name_en": "CreateDirectory",
            "context": "ФайловаяСистема",
            "syntax": "СоздатьКаталог(Путь)",
            "description": "Создание нового каталога на диске",
            "returns": "Булево",
        },
    ]
    methods_path = tmp_path / "methods.json"
    with open(methods_path, 'w', encoding='utf-8') as f:
        json.dump(methods, f, ensure_ascii=False)
    return methods_path


@pytest.fixture
def bm25_index(methods_fixture, tmp_path):
    """Построить BM25 индекс."""
    index_path = tmp_path / "index.json"
    count = build_index_bm25(methods_fixture, index_path)
    assert count == 4
    return index_path


class TestBuildIndexBM25:
    def test_creates_v2_index(self, bm25_index):
        with open(bm25_index, 'r', encoding='utf-8') as f:
            index = json.load(f)
        assert index['version'] == 2
        assert index['algorithm'] == 'bm25'

    def test_has_required_fields(self, bm25_index):
        with open(bm25_index, 'r', encoding='utf-8') as f:
            index = json.load(f)
        assert 'methods' in index
        assert 'idf' in index
        assert 'inverted_index' in index
        assert 'doc_lengths' in index
        assert 'avg_doc_length' in index
        assert 'trigrams_index' in index
        assert 'method_trigrams' in index
        assert 'bm25_params' in index

    def test_bm25_params(self, bm25_index):
        with open(bm25_index, 'r', encoding='utf-8') as f:
            index = json.load(f)
        assert index['bm25_params']['k1'] == BM25_K1
        assert index['bm25_params']['b'] == BM25_B

    def test_methods_count(self, bm25_index):
        with open(bm25_index, 'r', encoding='utf-8') as f:
            index = json.load(f)
        assert index['total_methods'] == 4
        assert len(index['methods']) == 4

    def test_trigrams_built(self, bm25_index):
        with open(bm25_index, 'r', encoding='utf-8') as f:
            index = json.load(f)
        # Должны быть триграммы
        assert len(index['trigrams_index']) > 0
        assert len(index['method_trigrams']) == 4


# ============ BM25 ПОИСК ============

class TestSearchBM25:
    def test_exact_match(self, bm25_index):
        results = search_bm25(bm25_index, "найти по коду", limit=5)
        assert len(results) > 0
        # НайтиПоКоду должен быть в топ-1 или топ-2
        top_names = [r['name_ru'] for r in results[:2]]
        assert "НайтиПоКоду" in top_names

    def test_stemmed_match(self, bm25_index):
        # "поиска" → "поиск" через стеммер
        results = search_bm25(bm25_index, "поиска элемента", limit=5)
        assert len(results) > 0
        names = [r['name_ru'] for r in results]
        # Должен найти хотя бы один из методов поиска
        assert any("Найти" in n for n in names)

    def test_typo_tolerance(self, bm25_index):
        # Опечатка: "найтипокоду" vs "НайтиПоКоду"
        results = search_bm25(bm25_index, "найтипокоду", limit=5)
        # Благодаря триграммам должно найти
        assert len(results) > 0
        names = [r['name_ru'] for r in results]
        assert "НайтиПоКоду" in names

    def test_returns_score(self, bm25_index):
        results = search_bm25(bm25_index, "найти", limit=5)
        for r in results:
            assert 'score' in r
            assert isinstance(r['score'], (int, float))
            assert r['score'] >= 0

    def test_result_fields(self, bm25_index):
        results = search_bm25(bm25_index, "найти", limit=5)
        for r in results:
            assert 'name_ru' in r
            assert 'name_en' in r
            assert 'context' in r
            assert 'syntax' in r
            assert 'description' in r

    def test_empty_query(self, bm25_index):
        results = search_bm25(bm25_index, "", limit=5)
        assert results == []

    def test_limit(self, bm25_index):
        results = search_bm25(bm25_index, "найти", limit=2)
        assert len(results) <= 2

    def test_no_match(self, bm25_index):
        results = search_bm25(bm25_index, "qwertyxxxzzz", limit=5)
        # Может что-то найдёт через триграммы, но не должно быть confident match
        # Если результаты есть — score должен быть низким
        for r in results:
            assert r['score'] < 0.5

    def test_hybrid_vs_pure_bm25(self, bm25_index):
        # Гибридный должен дать лучшие результаты для опечаток
        hybrid_results = search_bm25(bm25_index, "найтипокоду", limit=5, hybrid=True)
        pure_results = search_bm25(bm25_index, "найтипокоду", limit=5, hybrid=False)
        # Гибридный должен найти НайтиПоКоду (через триграммы)
        hybrid_names = [r['name_ru'] for r in hybrid_results]
        assert "НайтиПоКоду" in hybrid_names

    def test_file_match_search(self, bm25_index):
        # Поиск связанный с файлами
        results = search_bm25(bm25_index, "удалить файл", limit=5)
        assert len(results) > 0
        top = results[0]
        # Должен найти УдалитьФайл в топ-1 или топ-2
        top2 = [r['name_ru'] for r in results[:2]]
        assert "УдалитьФайл" in top2


# ============ AUTO-DETECT ============

class TestAutoDetect:
    def test_detect_v2(self, bm25_index):
        assert detect_index_version(bm25_index) == 2

    def test_detect_v1(self, tmp_path):
        """v1 — без поля version."""
        v1_index = tmp_path / "v1.json"
        with open(v1_index, 'w', encoding='utf-8') as f:
            json.dump({
                "methods": [],
                "idf": {},
                "inverted_index": {},
                "total_methods": 0,
            }, f)
        assert detect_index_version(v1_index) == 1

    def test_detect_missing_file(self, tmp_path):
        assert detect_index_version(tmp_path / "nonexistent.json") == 0

    def test_search_auto_v2(self, bm25_index):
        results = search_auto(bm25_index, "найти по коду", limit=5)
        assert len(results) > 0

    def test_search_auto_v1_fallback(self, tmp_path):
        """search_auto для v1 индекса должен упасть на TF-IDF."""
        # Создаём v1 индекс
        from src.services.search import build_index
        methods = [
            {
                "name_ru": "Тест",
                "name_en": "Test",
                "context": "Test",
                "syntax": "Тест()",
                "description": "Тестовый метод",
                "returns": "",
            }
        ]
        methods_path = tmp_path / "m.json"
        with open(methods_path, 'w', encoding='utf-8') as f:
            json.dump(methods, f, ensure_ascii=False)

        v1_path = tmp_path / "v1_index.json"
        build_index(methods_path, v1_path)

        # search_auto должен определить v1 и использовать TF-IDF
        results = search_auto(v1_path, "тест", limit=5)
        assert len(results) > 0
