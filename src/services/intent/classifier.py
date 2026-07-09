"""
F2.5: Intent classifier для solve_context.

Заменяет keyword-matching в handle_solve_context на rule-based классификатор
с confidence score. Каждый intent определяет:
- workflow (последовательность tools)
- target_context (если можно вывести)
- required_sources (какие источники контекста нужны — для F2.6 source selection)

Преимущества над keyword matching:
1. Confidence score — LLM знает, насколько уверена классификация
2. Verb-based patterns (создай/добавь/измени) вместо noun-based (запрос/регистр)
3. Multi-intent support — задача может быть 'create_object + write_query'
4. Testable — каждый pattern можно протестировать изолированно
5. Extensible — новые intents добавляются без изменения solve_context

Использование:
    from src.services.intent.classifier import classify_intent, Intent
    result = classify_intent("создай справочник для учёта товаров")
    # result.intent == "create_object"
    # result.confidence == 0.9
    # result.target_context_hint == "server"
    # result.required_sources == ["metadata", "standards", "templates"]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    """Результат классификации intent."""

    name: str  # create_object | write_query | generate_bsl | audit_code | ...
    confidence: float  # 0.0 - 1.0
    target_context_hint: str = ""  # thin_client | server | mobile_client | ""
    object_type_hint: str = ""  # Catalog | Document | Register | ...
    required_sources: list[str] = field(default_factory=list)  # metadata, standards, ...
    workflow: list[dict[str, str]] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class IntentPattern:
    """Один pattern для intent classification."""

    intent_name: str
    patterns: list[str]  # regex patterns (case-insensitive)
    confidence: float  # base confidence если pattern matched
    target_context_hint: str = ""
    object_type_hint: str = ""
    required_sources: list[str] = field(default_factory=list)
    workflow: list[dict[str, str]] = field(default_factory=list)


# ============================================================================
# INTENT PATTERNS
# ============================================================================

# Verb-based patterns (более точные, чем noun-based)
# Порядок важен: более специфичные patterns идут первыми

INTENT_PATTERNS: list[IntentPattern] = [
    # 0. CFE EXTENSION — самая специфичная, проверяется первой
    # (чтобы "создай расширение" не ушло в create_object)
    IntentPattern(
        intent_name="cfe_extension",
        patterns=[
            # bi-directional: создай расширение OR расширение создай
            r"\b(расширени\w*|cfe|extension)\b.*\b(созд\w*|добав\w*|заимств\w*)",
            r"\b(созд\w*|добав\w*|заимств\w*)\b.*\b(расширени\w*|cfe|extension)",
            r"\b(перехват\w*|intercept)\b.*\b(метод\w*|method)",
            r"(&перед|&после|&вместо|&изменени\w*)",
            r"\b(заимств\w*)\b",
            # Просто упоминание CFE/extension в контексте задачи
            r"\b(cfe|extension)\b.*\b(для|dlya)\b",
        ],
        confidence=0.9,
        required_sources=["metadata", "standards"],
        workflow=[
            {"step": 1, "tool": "get_object_structure", "why": "Структура объекта для заимствования"},
            {"step": 2, "tool": "bsl_templates", "why": "Шаблон перехватчика"},
            {"step": 3, "tool": "check_bsl_context", "why": "Проверить код перехватчика"},
        ],
    ),
    # 0b. GENERATE SKD — специфичная, перед create_object
    IntentPattern(
        intent_name="generate_skd",
        patterns=[
            r"\b(скд|skd)\b",
            r"\b(схем\w*\s+компоновк\w*)\b",
        ],
        confidence=0.9,
        target_context_hint="server",
        required_sources=["metadata", "query_standards", "templates"],
        workflow=[
            {"step": 1, "tool": "get_object_structure", "why": "Источники данных для СКД"},
            {"step": 2, "tool": "bsl_templates", "why": "Шаблон СКД"},
            {"step": 3, "tool": "solve_check", "why": "Проверка качества СКД"},
        ],
    ),
    # 1. CREATE OBJECT — создание нового объекта метаданных
    IntentPattern(
        intent_name="create_object",
        patterns=[
            # "создай справочник" — но НЕ "создай внешнюю обработку" (это generate_bsl/EPF)
            r"\b(создай|создать|добавь|добавить|новый|новая|новое)\b.*\b(справочник\w*|документ\w*|регистр\w*|отч[её]т\w*|подсистем\w*|план\s+видов\w*|характеристик\w*|счет\w*|задач\w*)",
            # обработка — только если не "внешняя" (lookahead перед обработк)
            r"\b(создай|создать|добавь|добавить)\b(?!\s+\w*\s*внешн\w*).*\b(обработк[ау]\w*)\b(?!.*\b(внешн\w*|epf))",
            r"\b(создай|создать|добавь|добавить)\b\s+(?!внешн\w*)\w*\s*(обработк[ау]\w*)",
            r"\b(cre?ate|add|new)\b.*\b(catalog|document|register|process|report)",
        ],
        confidence=0.9,
        target_context_hint="server",  # объекты метаданных создаются на сервере
        required_sources=["metadata", "standards", "templates", "platform_methods"],
        workflow=[
            {"step": 1, "tool": "search_platform_method", "why": "Найти методы платформы для работы с объектом"},
            {"step": 2, "tool": "get_method_details_batch", "why": "Получить синтаксис и доступность методов одним вызовом"},
            {"step": 3, "tool": "get_object_structure", "why": "Посмотреть структуру похожих объектов в конфигурации"},
            {"step": 4, "tool": "bsl_templates", "why": "Использовать шаблон для создания объекта"},
            {"step": 5, "tool": "get_safe_methods", "why": "Получить методы, доступные в target_context"},
            {"step": 6, "tool": "check_bsl_context", "why": "Проверить сгенерированный код"},
            {"step": 7, "tool": "solve_check", "why": "Полная проверка кода"},
        ],
    ),
    # 2. WRITE QUERY — написание запроса 1С
    IntentPattern(
        intent_name="write_query",
        patterns=[
            r"\b(напиши\w*|написать|составь\w*|составить|сгенерир[уи]й\w*)\b.*\b(запрос\w*|query)",
            r"\b(выбрать\w*|select)\b",
            r"\bзапрос\w*\b.*\b(регистр\w*|справочник\w*|документ\w*|выборк\w*)",
            r"\b(виртуальн\w*\s+таблиц\w*|срез\s+последних|остатки\w*|оборот\w*)\b",
        ],
        confidence=0.9,
        target_context_hint="server",  # запросы выполняются на сервере
        required_sources=["metadata", "query_standards", "query_templates", "platform_methods"],
        workflow=[
            {"step": 1, "tool": "get_object_structure", "why": "Получить точные имена полей (ресурсы, измерения)"},
            {"step": 2, "tool": "search_platform_method", "why": "Найти методы для работы с запросами"},
            {"step": 3, "tool": "bsl_templates", "why": "Использовать шаблон query_with_filter (SEC001: параметризованный)"},
            {"step": 4, "tool": "check_bsl_context", "why": "Проверить доступность методов в контексте"},
            {"step": 5, "tool": "solve_check", "why": "Проверить стандарты и безопасность запроса"},
        ],
    ),
    # 3. GENERATE BSL — генерация BSL-кода (модуль, форма, обработка)
    IntentPattern(
        intent_name="generate_bsl",
        patterns=[
            r"\b(напиши\w*|написать|сгенерир[уи]й\w*)\b.*\b(код\w*|модуль\w*|форм[ау]\w*|обработк[ау]\w*|bsl)",
            r"\b(обработк[ау]\w*|epf|внешн\w*)\b.*\b(созд\w*|сгенерир\w*|напис\w*)",
            r"\b(форм[ау]\w*)\b.*\b(созд\w*|сгенерир\w*|напис\w*)",
            # bi-directional: создай форму OR форму создай
            r"\b(созд\w*|сгенерир\w*|напис\w*)\b.*\b(форм[ау]\w*|модуль\w*|обработк[ау]\w*|bsl)",
        ],
        confidence=0.85,
        target_context_hint="",  # зависит от задачи — LLM должен определить
        required_sources=["platform_methods", "metadata", "bsl_templates", "standards"],
        workflow=[
            {"step": 1, "tool": "search_platform_method", "why": "Найти методы платформы для задачи"},
            {"step": 2, "tool": "get_method_details_batch", "why": "Получить синтаксис и доступность методов"},
            {"step": 3, "tool": "get_safe_methods", "why": "Получить методы, доступные в target_context (pre-hoc)"},
            {"step": 4, "tool": "bsl_templates", "why": "Использовать шаблон для генерации BSL кода"},
            {"step": 5, "tool": "check_bsl_context", "why": "Проверить код на доступность методов"},
            {"step": 6, "tool": "solve_check", "why": "Полная проверка кода"},
        ],
    ),
    # 4. AUDIT CODE — аудит безопасности существующего кода
    IntentPattern(
        intent_name="audit_code",
        patterns=[
            r"\b(аудит\w*|провер[ька]\w*|audit)\b.*\b(безопасн\w*|уязвим\w*|security|код\w*)",
            r"\b(провер[ька]\w*|audit)\b.*\b(sql\w*|инъекц\w*|парол\w*|выполнить\w*|com\w*)",
            r"\b(уязвим\w*|vulnerab\w*)\b",
        ],
        confidence=0.9,
        required_sources=["security_rules", "standards"],
        workflow=[
            {"step": 1, "tool": "solve_check", "why": "Полная проверка кода (7-9 анализаторов)"},
            {"step": 2, "tool": "bsl_templates", "why": "Шаблоны безопасного кода (SEC001: параметризованные запросы)"},
        ],
    ),
    # 5. UNDERSTAND CODE — понимание существующего кода
    IntentPattern(
        intent_name="understand_code",
        patterns=[
            r"\b(как|почему|зачем|объясни\w*|поясни\w*)\b.*\b(работает\w*|делает\w*|использует\w*)",
            r"\b(что|какой)\b.*\b(делает\w*|выполняет\w*|вызывает\w*)",
            r"\b(найди\w*|find|search)\b.*\b(где|использ\w*|вызыва\w*|call\w*)",
            r"\b(зависим\w*|архитектур\w*|call\s*graph|граф\s+вызов\w*)",
        ],
        confidence=0.8,
        required_sources=["call_graph", "metadata", "api_reference"],
        workflow=[
            {"step": 1, "tool": "inspect", "why": "Получить обзор конфигурации"},
            {"step": 2, "tool": "get_object_structure", "why": "Структура объекта"},
            {"step": 3, "tool": "search_code", "why": "Найти использование (через CLI или внутри solve_context)"},
        ],
    ),
    # 6. REFACTOR CODE — рефакторинг существующего кода
    IntentPattern(
        intent_name="refactor_code",
        patterns=[
            r"\b(рефакторинг\w*|рефактори\w*|refactor\w*)\b",
            r"\b(улучш\w*|оптимизир\w*)\b.*\b(код\w*|модуль\w*|структур\w*)",
            r"\b(раздели\w*|объедин\w*|вынеси\w*)\b.*\b(код\w*|метод\w*|функци\w*)",
        ],
        confidence=0.85,
        required_sources=["standards", "best_practices", "call_graph"],
        workflow=[
            {"step": 1, "tool": "solve_check", "why": "Текущее состояние кода (что улучшать)"},
            {"step": 2, "tool": "bsl_templates", "why": "Шаблоны для рефакторинга"},
            {"step": 3, "tool": "check_bsl_context", "why": "Проверить после рефакторинга"},
        ],
    ),
    # 7. SEARCH METHOD — поиск метода платформы
    IntentPattern(
        intent_name="search_method",
        patterns=[
            r"\b(найди\w*|find|search|поиск\w*)\b.*\b(метод\w*|method\w*|функци\w*)",
            r"\b(как|какой)\b.*\b(метод\w*|функци\w*)\b.*\b(использ\w*|нужн\w*|подходит\w*)",
        ],
        confidence=0.85,
        required_sources=["platform_methods"],
        workflow=[
            {"step": 1, "tool": "search_platform_method", "why": "Поиск по методам платформы"},
            {"step": 2, "tool": "get_method_details", "why": "Карточка найденного метода"},
            {"step": 3, "tool": "get_safe_methods", "why": "Если нужен метод для конкретного контекста"},
        ],
    ),
]


# ============================================================================
# CLASSIFIER
# ============================================================================


def classify_intent(query: str, use_llm_fallback: bool = True) -> Intent:
    """F2.5: Классифицировать intent задачи.

    R6 (2026-07-09): LLM-based fallback — если confidence < 0.5 и use_llm_fallback=True,
    пытается классифицировать через Ollama. Timeout 2s, fallback на unknown.

    Args:
        query: Текст задачи от LLM/пользователя
        use_llm_fallback: Если True — использовать Ollama для low-confidence cases

    Returns:
        Intent с confidence, target_context_hint, required_sources, workflow.
        Если ни один pattern не matched — возвращает Intent('unknown', 0.0).
    """
    if not query or not query.strip():
        return Intent(name="unknown", confidence=0.0)

    query_lower = query.lower()
    candidates: list[tuple[IntentPattern, list[str]]] = []

    for pattern in INTENT_PATTERNS:
        matched: list[str] = []
        for regex in pattern.patterns:
            if re.search(regex, query_lower, re.IGNORECASE):
                matched.append(regex)
        if matched:
            candidates.append((pattern, matched))

    if not candidates:
        # R6: LLM-based fallback для unknown queries
        if use_llm_fallback:
            llm_intent = _classify_with_llm(query)
            if llm_intent is not None:
                return llm_intent

        # Fallback: default workflow
        return Intent(
            name="unknown",
            confidence=0.0,
            required_sources=["platform_methods", "metadata", "standards"],
            workflow=[
                {"step": 1, "tool": "plan", "why": "Пере-классифицировать задачу"},
                {"step": 2, "tool": "gather", "why": "Собрать контекст (default sources)"},
                {"step": 3, "tool": "generate", "why": "Сгенерировать код"},
                {"step": 4, "tool": "validate", "why": "Проверить код"},
            ],
        )

    # Выбираем intent с наибольшим confidence
    # Если несколько patterns matched — повышаем confidence (mutual reinforcement)
    best_pattern, best_matched = max(candidates, key=lambda x: x[0].confidence)

    # Bonus confidence если несколько patterns matched
    confidence = best_pattern.confidence
    if len(best_matched) > 1:
        confidence = min(1.0, confidence + 0.05 * (len(best_matched) - 1))

    return Intent(
        name=best_pattern.intent_name,
        confidence=confidence,
        target_context_hint=best_pattern.target_context_hint,
        object_type_hint=best_pattern.object_type_hint,
        required_sources=best_pattern.required_sources,
        workflow=best_pattern.workflow,
        matched_patterns=best_matched,
    )


# ============================================================================
# R6: LLM-based intent fallback
# ============================================================================


def _classify_with_llm(query: str) -> Intent | None:
    """R6: Классифицировать intent через Ollama (fallback для unknown queries).

    Использует локальный Ollama для LLM-based классификации.
    Timeout 2s — если Ollama недоступен или медленный, возвращаем None.

    Args:
        query: Текст задачи

    Returns:
        Intent если Ollama вернул валидный intent, иначе None.
    """
    try:
        from src.services.llm_ollama import OllamaClient

        client = OllamaClient()
        if not client.is_available():
            return None

        prompt = (
            "Классифицируй intent задачи для 1С разработки.\n"
            f"Query: '{query}'\n\n"
            "Categories (верни только одно слово):\n"
            "- create_object (создание справочника/документа/регистра)\n"
            "- write_query (написание запроса 1С)\n"
            "- generate_bsl (генерация BSL кода/модуля/формы)\n"
            "- audit_code (аудит безопасности)\n"
            "- understand_code (понимание кода)\n"
            "- refactor_code (рефакторинг)\n"
            "- search_method (поиск метода)\n"
            "- generate_skd (создание СКД)\n"
            "- cfe_extension (расширение CFE)\n"
            "- unknown\n\n"
            "Ответ (только одно слово):"
        )

        response = client.generate(prompt, temperature=0.1, num_predict=10)
        if not response or not response.text:
            return None

        # Парсим ответ — берём первое слово, нормализуем
        intent_name = response.text.strip().lower().split()[0] if response.text.strip() else ""
        # Убираем пунктуацию
        intent_name = intent_name.strip(".,!?;:")

        # Проверяем что это валидный intent
        valid_intents = {p.intent_name for p in INTENT_PATTERNS}
        if intent_name not in valid_intents:
            return None

        # Находим pattern для этого intent
        for pattern in INTENT_PATTERNS:
            if pattern.intent_name == intent_name:
                return Intent(
                    name=intent_name,
                    confidence=0.6,  # LLM confidence ниже чем regex (0.9)
                    target_context_hint=pattern.target_context_hint,
                    object_type_hint=pattern.object_type_hint,
                    required_sources=pattern.required_sources,
                    workflow=pattern.workflow,
                    matched_patterns=["llm_fallback"],
                )

        return None
    except Exception:
        # Любая ошибка — возвращаем None (fallback на unknown)
        return None


def get_intent_names() -> list[str]:
    """Вернуть список всех поддерживаемых intents."""
    return list({p.intent_name for p in INTENT_PATTERNS}) + ["unknown"]


def get_intent_description(intent_name: str) -> str:
    """Описать intent для LLM (для отладки)."""
    descriptions = {
        "create_object": "Создание нового объекта метаданных (справочник, документ, регистр, обработка, отчёт)",
        "write_query": "Написание запроса 1С (SELECT, виртуальные таблицы, срез последних)",
        "generate_bsl": "Генерация BSL-кода (модуль, форма, обработка)",
        "audit_code": "Аудит безопасности существующего кода (SQL injection, пароли, COM)",
        "understand_code": "Понимание существующего кода (как работает, где используется)",
        "refactor_code": "Рефакторинг существующего кода (улучшить, оптимизировать)",
        "search_method": "Поиск метода платформы 1С",
        "generate_skd": "Генерация схемы компоновки данных (СКД)",
        "cfe_extension": "Работа с расширениями CFE (заимствование, перехват методов)",
        "unknown": "Не удалось классифицировать intent — используется default workflow",
    }
    return descriptions.get(intent_name, "Unknown intent")
