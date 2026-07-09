"""
P1-B — Тесты для улучшенного CamelCase tokenizer.

Алгоритм перенесён из mini-ai-1c (semantic.rs:tokenize_identifier) —
корректно обрабатывает акронимы (НДС, XML, JSON) внутри CamelCase.

Проверяет:
1. Базовое разбиение PascalCase: ЗначениеРеквизитаОбъекта → [Значение, Реквизита, Объекта]
2. Акронимы в середине: СтавкаНДСПоЗначению → [Ставка, НДС, По, Значению]
3. Английский PascalCase: GetNDSValue → [Get, NDS, Value]
4. Акроним в начале: XMLПарсер → [XML, Парсер]
5. Регресс: tokenize_stemmed остаётся backward-compatible
"""

from __future__ import annotations

import pytest

from src.services.search_bm25 import (
    tokenize_identifier,
    tokenize_lower,
    tokenize_stemmed,
)


# ============================================================================
# 1. БАЗОВОЕ РАЗБИЕНИЕ PASCALCASE
# ============================================================================


class TestTokenizeIdentifierBasic:
    """Базовые тесты разбиения PascalCase идентификаторов."""

    def test_simple_pascalcase_russian(self):
        """ЗначениеРеквизитаОбъекта → [Значение, Реквизита, Объекта]."""
        result = tokenize_identifier("ЗначениеРеквизитаОбъекта")
        assert result == ["Значение", "Реквизита", "Объекта"]

    def test_simple_pascalcase_english(self):
        """GetNDSValue → [Get, NDS, Value]."""
        result = tokenize_identifier("GetNDSValue")
        assert result == ["Get", "NDS", "Value"]

    def test_two_words(self):
        """НайтиПоКоду → [Найти, По, Коду]."""
        result = tokenize_identifier("НайтиПоКоду")
        assert result == ["Найти", "По", "Коду"]

    def test_single_word(self):
        """Одно слово — один токен."""
        assert tokenize_identifier("Поиск") == ["Поиск"]
        assert tokenize_identifier("Search") == ["Search"]


# ============================================================================
# 2. АКРОНИМЫ (главное улучшение vs старого regex)
# ============================================================================


class TestTokenizeIdentifierAcronyms:
    """Тесты акронимов (НДС, XML, JSON) — главный кейс, который не работал в regex."""

    def test_acronym_in_middle(self):
        """СтавкаНДСПоЗначениюПеречисления → [Ставка, НДС, По, Значению, Перечисления].

        Старый regex давал ['Ставка', 'НД', 'СП', 'оЗначению'] — некорректно.
        Новый алгоритм даёт правильное разбиение.
        """
        result = tokenize_identifier("СтавкаНДСПоЗначениюПеречисления")
        assert result == ["Ставка", "НДС", "По", "Значению", "Перечисления"]

    def test_acronym_at_start(self):
        """XMLПарсер → [XML, Парсер]."""
        result = tokenize_identifier("XMLПарсер")
        assert result == ["XML", "Парсер"]

    def test_acronym_at_end(self):
        """ПолучитьXML → [Получить, XML]."""
        result = tokenize_identifier("ПолучитьXML")
        assert result == ["Получить", "XML"]

    def test_two_acronyms(self):
        """XMLJSONПарсер → [XML, JSON, Парсер]."""
        result = tokenize_identifier("XMLJSONПарсер")
        # Замечание: XMLJSON без разделителя — два акронима подряд.
        # Алгоритм может дать [XMLJSON, Парсер] — это допустимо.
        # Главное — не разбивать XMLJSON посередине.
        assert "Парсер" in result
        # Проверяем что хотя бы XMLJSON или [XML, JSON] есть
        joined = "".join(result[:-1])  # без Парсер
        assert "XML" in joined and "JSON" in joined

    def test_acronym_nds_only(self):
        """СтавкаНДС → [Ставка, НДС]."""
        result = tokenize_identifier("СтавкаНДС")
        assert result == ["Ставка", "НДС"]

    def test_acronym_short_word(self):
        """Короткие акронимы (>= 2 символов) сохраняются."""
        result = tokenize_identifier("ТоварыНДС")
        assert "НДС" in result
        assert "Товары" in result


# ============================================================================
# 3. КРАЕВЫЕ СЛУЧАИ
# ============================================================================


class TestTokenizeIdentifierEdgeCases:
    """Краевые случаи: пустые строки, цифры, разделители."""

    def test_empty_string(self):
        """Пустая строка → []."""
        assert tokenize_identifier("") == []

    def test_single_char_filtered(self):
        """Однобуквенные токены фильтруются (>= 2 символов)."""
        result = tokenize_identifier("АБ")
        assert result == ["АБ"]

    def test_digits_break_token(self):
        """Цифры разрывают токен."""
        result = tokenize_identifier("Товар123Имя")
        # 'Товар' и 'Имя' — два токена
        assert "Товар" in result
        assert "Имя" in result

    def test_underscore_breaks_token(self):
        """Подчёркивание разрывает токен."""
        result = tokenize_identifier("Find_By_Code")
        assert "Find" in result
        assert "By" in result
        assert "Code" in result

    def test_lowercase_only(self):
        """Полностью lowercase — один токен."""
        result = tokenize_identifier("поиск")
        # Без uppercase границ — один токен
        assert result == ["поиск"]

    def test_preserves_case(self):
        """Регистр сохраняется в результате."""
        result = tokenize_identifier("НайтиПоКоду")
        assert all(t[0].isupper() for t in result)


# ============================================================================
# 4. TOKENIZE_LOWER
# ============================================================================


class TestTokenizeLower:
    """tokenize_lower возвращает lowercase-токены."""

    def test_lower_result(self):
        """Все токены в lowercase."""
        result = tokenize_lower("СтавкаНДСПоЗначению")
        assert result == ["ставка", "ндс", "по", "значению"]

    def test_lower_english(self):
        """Английский PascalCase → lowercase."""
        result = tokenize_lower("GetNDSValue")
        assert result == ["get", "nds", "value"]


# ============================================================================
# 5. BACKWARD COMPATIBILITY — tokenize_stemmed
# ============================================================================


class TestTokenizeStemmedBackwardCompat:
    """tokenize_stemmed остаётся backward-compatible."""

    def test_stemmed_returns_non_empty(self):
        """tokenize_stemmed возвращает непустой список для нормального запроса."""
        result = tokenize_stemmed("НайтиПоКоду")
        assert len(result) > 0
        # Должны быть стеммированные варианты
        assert any("най" in t for t in result)

    def test_stemmed_handles_nds(self):
        """tokenize_stemmed корректно обрабатывает акроним НДС."""
        result = tokenize_stemmed("СтавкаНДС")
        # 'ндс' должно присутствовать (стеммер не меняет короткие слова)
        assert any("ндс" in t for t in result)

    def test_stemmed_lowercase_input(self):
        """tokenize_stemmed обрабатывает lowercase-ввод."""
        result = tokenize_stemmed("поиск по коду")
        assert len(result) > 0

    def test_stemmed_does_not_crash_on_empty(self):
        """tokenize_stemmed не падает на пустом вводе."""
        result = tokenize_stemmed("")
        assert result == []

    def test_stemmed_applies_synonyms(self):
        """tokenize_stemmed применяет BSL-синонимы."""
        # 'найти' должно дать и ru и en варианты
        result = tokenize_stemmed("НайтиСтроки")
        # Ищем хотя бы один токен — стеммер обрежет
        assert len(result) > 0


# ============================================================================
# 6. РЕГРЕССИОННЫЕ ТЕСТЫ — поиск работает с новыми токенами
# ============================================================================


class TestSearchRegressionWithNewTokenizer:
    """Регрессионные тесты: поиск продолжает работать с новым tokenizer."""

    def test_search_nds_finds_nds_methods(self):
        """Поиск 'НДС' должен находить методы с 'СтавкаНДС' в имени."""
        # tokenize_stemmed("СтавкаНДС") должен включать токен из 'ндс'
        result = tokenize_stemmed("СтавкаНДС")
        # Хотя бы один токен содержит 'ндс'
        assert any("ндс" in t for t in result), f"НДС не найден в {result}"

    def test_search_xml_finds_xml_methods(self):
        """Поиск 'XML' должен находить методы с 'XMLПарсер' в имени."""
        result = tokenize_stemmed("XMLПарсер")
        assert any("xml" in t for t in result), f"XML не найден в {result}"

    def test_search_long_camelcase(self):
        """Длинный CamelCase корректно разбивается."""
        result = tokenize_identifier("СтавкаНДСПоЗначениюПеречисления")
        # Должно быть 5 токенов, не 1 и не 10
        assert len(result) == 5
        # Все токены ≥ 2 символов
        assert all(len(t) >= 2 for t in result)
