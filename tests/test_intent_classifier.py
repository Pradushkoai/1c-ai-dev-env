"""
F2.5: Тесты для intent classifier.

Проверяет:
- Каждый intent распознаётся по характерным phrases
- Confidence score корректный
- target_context_hint и required_sources заполняются
- Unknown queries возвращают Intent('unknown', 0.0)
- Multi-pattern matching повышает confidence
"""

from __future__ import annotations

import pytest

from src.services.intent.classifier import (
    INTENT_PATTERNS,
    Intent,
    classify_intent,
    get_intent_description,
    get_intent_names,
)


# ============================================================================
# CREATE_OBJECT intent
# ============================================================================


class TestCreateObjectIntent:
    """Тесты для create_object intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "создай справочник для учёта товаров",
            "создать новый документ ПриходТовара",
            "добавь регистр накопления для продаж",
            "создай обработку для выгрузки данных",
            "создать отчёт по продажам",
            "create catalog for products",
            "добавить новую подсистему Склад",
        ],
    )
    def test_recognizes_create_object(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "create_object", f"Query: {query}"
        assert intent.confidence >= 0.9
        assert intent.target_context_hint == "server"
        assert "metadata" in intent.required_sources
        assert "templates" in intent.required_sources
        assert len(intent.workflow) > 0

    def test_does_not_match_just_noun(self):
        """Просто слово 'справочник' без глагола не должно match."""
        # 'справочник' без глагола — не create_object
        intent = classify_intent("расскажи про справочник")
        # Может быть understand_code или unknown
        assert intent.name != "create_object"


# ============================================================================
# WRITE_QUERY intent
# ============================================================================


class TestWriteQueryIntent:
    """Тесты для write_query intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "напиши запрос для выбора остатков",
            "составь запрос к регистру накопления",
            "запрос к виртуальной таблице Остатки",
            "срез последних по ценам",
            "select * from catalog",
            "выбрать документы за период",
        ],
    )
    def test_recognizes_write_query(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "write_query", f"Query: {query}"
        assert intent.confidence >= 0.9
        assert intent.target_context_hint == "server"
        assert "query_standards" in intent.required_sources
        assert "query_templates" in intent.required_sources


# ============================================================================
# GENERATE_BSL intent
# ============================================================================


class TestGenerateBslIntent:
    """Тесты для generate_bsl intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "напиши модуль для расчёта зарплаты",
            "сгенерируй код для обработки",
            "создай форму элемента",
            "напиши BSL код",
            "создать внешнюю обработку",
        ],
    )
    def test_recognizes_generate_bsl(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "generate_bsl", f"Query: {query}"
        assert intent.confidence >= 0.85
        assert "bsl_templates" in intent.required_sources
        assert "platform_methods" in intent.required_sources


# ============================================================================
# AUDIT_CODE intent
# ============================================================================


class TestAuditCodeIntent:
    """Тесты для audit_code intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "проверь код на безопасность",
            "аудит безопасности модуля",
            "найди уязвимости в коде",
            "audit code for SQL injection",
            "проверь на SQL инъекции",
        ],
    )
    def test_recognizes_audit_code(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "audit_code", f"Query: {query}"
        assert intent.confidence >= 0.9
        assert "security_rules" in intent.required_sources


# ============================================================================
# UNDERSTAND_CODE intent
# ============================================================================


class TestUnderstandCodeIntent:
    """Тесты для understand_code intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "как работает этот метод",
            "почему используется ЗаписьЖурналаРегистрации",
            "объясни что делает этот код",
            "граф вызовов для модуля",
        ],
    )
    def test_recognizes_understand_code(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "understand_code", f"Query: {query}"
        assert intent.confidence >= 0.8
        assert "call_graph" in intent.required_sources

    def test_understand_or_search_for_where_used(self):
        """'найди где используется метод' — может быть understand_code или search_method.

        Оба intent релевантны. Проверяем что хотя бы один из них распознан.
        """
        intent = classify_intent("найди где используется метод")
        assert intent.name in ("understand_code", "search_method"), f"Got: {intent.name}"
        assert intent.confidence >= 0.8


# ============================================================================
# REFACTOR_CODE intent
# ============================================================================


class TestRefactorCodeIntent:
    """Тесты для refactor_code intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "рефакторинг модуля",
            "улучшить код",
            "оптимизируй модуль",
            "раздели метод на части",
            "вынеси код в отдельную функцию",
        ],
    )
    def test_recognizes_refactor_code(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "refactor_code", f"Query: {query}"
        assert intent.confidence >= 0.85
        assert "standards" in intent.required_sources


# ============================================================================
# SEARCH_METHOD intent
# ============================================================================


class TestSearchMethodIntent:
    """Тесты для search_method intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "найди метод для записи в журнал",
            "какой метод использовать для парсинга JSON",
            "поиск функции СтрРазделить",
            "find method for HTTP request",
        ],
    )
    def test_recognizes_search_method(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "search_method", f"Query: {query}"
        assert intent.confidence >= 0.85
        assert "platform_methods" in intent.required_sources


# ============================================================================
# GENERATE_SKD intent
# ============================================================================


class TestGenerateSkdIntent:
    """Тесты для generate_skd intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "создай СКД для отчёта по продажам",
            "сгенерируй схему компоновки данных",
            "создать СКД отчёт",
        ],
    )
    def test_recognizes_generate_skd(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "generate_skd", f"Query: {query}"
        assert intent.confidence >= 0.9
        assert intent.target_context_hint == "server"


# ============================================================================
# CFE_EXTENSION intent
# ============================================================================


class TestCfeExtensionIntent:
    """Тесты для cfe_extension intent."""

    @pytest.mark.parametrize(
        "query",
        [
            "создай расширение для справочника",
            "заимствуй объект в CFE",
            "создай перехватчик метода &Перед",
            "добавь &После для ПриОткрытии",
            "extension для документа",
        ],
    )
    def test_recognizes_cfe_extension(self, query: str):
        intent = classify_intent(query)
        assert intent.name == "cfe_extension", f"Query: {query}"
        assert intent.confidence >= 0.9


# ============================================================================
# UNKNOWN intent
# ============================================================================


class TestUnknownIntent:
    """Тесты для unknown intent."""

    def test_empty_query(self):
        intent = classify_intent("")
        assert intent.name == "unknown"
        assert intent.confidence == 0.0

    def test_whitespace_query(self):
        intent = classify_intent("   ")
        assert intent.name == "unknown"
        assert intent.confidence == 0.0

    def test_unrecognized_query(self):
        """Запрос без явных patterns — unknown."""
        intent = classify_intent("привет как дела")
        assert intent.name == "unknown"
        assert intent.confidence == 0.0
        # Unknown всё равно имеет default workflow
        assert len(intent.workflow) > 0
        assert "platform_methods" in intent.required_sources


# ============================================================================
# Confidence and multi-pattern matching
# ============================================================================


class TestConfidenceBoost:
    """Тесты для confidence boost при multi-pattern matching."""

    def test_multi_pattern_increases_confidence(self):
        """Если несколько patterns matched — confidence выше."""
        # "создай справочник" — 1 pattern (create_object)
        single = classify_intent("создай справочник")
        # "создай новый справочник" — может match 2 patterns
        multi = classify_intent("создай новый справочник для учёта")

        # Multi-pattern должен иметь confidence >= single
        assert multi.confidence >= single.confidence


# ============================================================================
# Intent metadata
# ============================================================================


class TestIntentMetadata:
    """Тесты для metadata функций."""

    def test_get_intent_names_includes_all(self):
        names = get_intent_names()
        assert "create_object" in names
        assert "write_query" in names
        assert "generate_bsl" in names
        assert "audit_code" in names
        assert "unknown" in names

    def test_get_intent_description_for_known(self):
        desc = get_intent_description("create_object")
        assert "Создание" in desc
        assert "справочник" in desc

    def test_get_intent_description_for_unknown(self):
        desc = get_intent_description("nonexistent")
        assert desc == "Unknown intent"

    def test_all_patterns_have_required_fields(self):
        """Все INTENT_PATTERNS имеют обязательные поля."""
        for pattern in INTENT_PATTERNS:
            assert pattern.intent_name, f"Pattern missing intent_name: {pattern}"
            assert pattern.patterns, f"Pattern {pattern.intent_name} has no patterns"
            assert pattern.confidence > 0, f"Pattern {pattern.intent_name} has no confidence"
            assert pattern.required_sources, f"Pattern {pattern.intent_name} has no required_sources"
            assert pattern.workflow, f"Pattern {pattern.intent_name} has no workflow"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Граничные случаи."""

    def test_english_query(self):
        """Английские запросы тоже распознаются."""
        intent = classify_intent("create catalog for products")
        assert intent.name == "create_object"
        assert intent.confidence >= 0.9

    def test_mixed_case(self):
        """Регистр не важен."""
        intent = classify_intent("СОЗДАЙ СПРАВОЧНИК")
        assert intent.name == "create_object"

    def test_extra_whitespace(self):
        """Лишние пробелы не мешают."""
        intent = classify_intent("  создай   справочник  ")
        assert intent.name == "create_object"

    def test_intent_has_workflow_steps(self):
        """Каждый recognized intent имеет workflow с step fields."""
        intent = classify_intent("создай справочник")
        assert len(intent.workflow) > 0
        for step in intent.workflow:
            assert "step" in step
            assert "tool" in step
            assert "why" in step

    def test_intent_dataclass_serializable(self):
        """Intent dataclass можно сериализовать (для JSON response)."""
        intent = classify_intent("создай справочник")
        # Проверяем что все поля сериализуемы
        assert isinstance(intent.name, str)
        assert isinstance(intent.confidence, float)
        assert isinstance(intent.required_sources, list)
        assert isinstance(intent.workflow, list)
        assert isinstance(intent.matched_patterns, list)
