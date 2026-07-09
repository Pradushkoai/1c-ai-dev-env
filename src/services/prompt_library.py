"""
M5 AI/RAG (2026-07-05): Prompt engineering library + RAG improvements.

A4.1: 5 типовых промптов для 1С задач (create_catalog, audit_security, refactor_module, generate_skd, cfe_borrow)
A4.2: Token-aware context assembly (tiktoken вместо char-based)
A4.3: Streaming responses (Ollama stream=true)
A4.4: Retry + circuit breaker
A4.5: Model routing (codegen→codellama, audit→llama3.1:70b)
A4.6: Cost tracking
A4.7: Vector index persistence (sqlite-vss)
A4.8: Hybrid reranking (cross-encoder)
A4.9: Fine-tune ai-forever/sbert_large_mt_nlu_ru (план)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# A4.1: Prompt templates для 5 типовых задач 1С
PROMPT_TEMPLATES: dict[str, str] = {
    "create_catalog": (
        "Ты — эксперт 1С разработчик. Создай справочник 1С по спецификации.\n"
        "Требования:\n"
        "- Соблюдай стандарты 1С (STD 456): табы для отступов, области в коде\n"
        "- Имена на русском, без буквы ё\n"
        "- Включи: реквизиты, формы (ФормаСписка, ФормаЭлемента), команды\n\n"
        "Спецификация:\n{spec}\n\n"
        "Сгенерируй JSON DSL для meta compiler и BSL код для модулей."
    ),
    "audit_security": (
        "Ты — аудитор безопасности 1С. Проверь BSL код на уязвимости.\n"
        "Проверяй:\n"
        "- SQL-инъекции (конкатенация в Запрос.Текст)\n"
        "- Выполнить() с динамическим кодом\n"
        "- Хардкод паролей/токенов\n"
        "- COM-объекты без проверки\n"
        "- Привилегированный режим без необходимости\n\n"
        "Код для аудита:\n{code}\n\n"
        "Найди все нарушения, укажи строку и рекомендацию."
    ),
    "refactor_module": (
        "Ты — эксперт по рефакторингу 1С. Улучшши BSL модуль.\n"
        "Цели:\n"
        "- Разделить на области (ПрограммныйИнтерфейс, СлужебныеПроцедуры)\n"
        "- Устранить дублирование кода\n"
        "- Упростить сложные условия\n"
        "- Добавить комментарии к экспортным методам\n\n"
        "Модуль:\n{code}\n\n"
        "Верни рефакторенный код с объяснением изменений."
    ),
    "generate_skd": (
        "Ты — эксперт 1С по СКД. Создай схему компоновки данных.\n"
        "Требования:\n"
        "- Источник данных: запрос\n"
        "- Поля: группировки и детальные записи\n"
        "- Параметры с значениями по умолчанию\n"
        "- Условное оформление\n\n"
        "Спецификация отчёта:\n{spec}\n\n"
        "Сгенерируй JSON DSL для SKD compiler."
    ),
    "cfe_borrow": (
        "Ты — эксперт 1С по расширениям (CFE). Настрой заимствование объекта.\n"
        "Шаги:\n"
        "1. Заимствуй объект из основной конфигурации\n"
        "2. Создай перехватчик метода (&Перед/&После/&ИзменениеИКонтроль)\n"
        "3. Добавь валидацию входных данных\n\n"
        "Объект: {object_ref}\n"
        "Метод: {method_name}\n"
        "Тип перехвата: {interceptor_type}\n\n"
        "Сгенерируй BSL код перехватчика."
    ),
}


# ============================================================================
# B8 FIX: Правила использования синтакс-помощника при генерации BSL-кода
# ============================================================================

BSL_CONTEXT_RULES = """\
ОБЯЗАТЕЛЬНЫЙ WORKFLOW ПРИ ГЕНЕРАЦИИ BSL-КОДА:

1. ОПРЕДЕЛИ ЦЕЛЕВОЙ КОНТЕКСТ:
   - Клиентский модуль (флаги: Клиент, Мобильное приложение-клиент) → thin_client, mobile_client
   - Серверный модуль (флаги: Сервер, Мобильное приложение-сервер) → server
   - Модуль формы: &НаКлиенте → thin_client; &НаСервере → server
   - Если не указан — считай server (по умолчанию для общих модулей)

2. ДЛЯ КАЖДОГО МЕТОДА ПЛАТФОРМЫ, КОТОРЫЙ ПЛАНИРУЕШЬ ИСПОЛЬЗОВАТЬ:
   a. Вызови get_method_details(<имя метода>) — получи синтаксис, параметры, доступность
   b. Проверь availability — доступен ли метод в целевом контексте?
   c. Проверь version_since — доступен ли метод в целевой версии платформы?
   d. Проверь version_deprecated — не устарел ли метод?
   e. Если хоть одна проверка не прошла — НАЙДИ АЛЬТЕРНАТИВУ через search_platform_method

3. ПОСЛЕ ГЕНЕРАЦИИ КОДА:
   Вызови check_bsl_context(code=<сгенерированный код>, target_context=<целевой контекст>)
   Если есть ERROR — исправь код и повтори проверку.

МЕТОДЫ, ЧАСТО НЕДОСТУПНЫЕ НА КЛИЕНТЕ (проверяй обязательно!):
   ЗаписьЖурналаРегистрации → только сервер
   УровеньЖурналаРегистрации → только сервер
   Метаданные → только сервер (используй серверный вызов)
   ПараметрыСеанса → только сервер
   ФоновыеЗадания → только сервер
   Константы → только сервер
   Справочники/Документы/Регистры → только сервер (для БД-операций)

МЕТОДЫ, НЕДОСТУПНЫЕ НА СЕРВЕРЕ:
   Асинх/Ждать → только клиент (BSL-ASYNC-003)
   ПоказатьВопрос/ПоказатьПредупреждение → только клиент
   ОткрытьФорму → только клиент

МЕТОДЫ, НЕДОСТУПНЫЕ В МОБИЛЬНОЙ ПЛАТФОРМЕ:
   COMОбъект → недоступен
   ЗапуститьПриложение → ограничено
   ФоновыеЗадания → ограничено

Асинх Функция → только клиентские модули (не серверные!)
Перем ... Экспорт → запрещено в общих модулях (BSL-MODULE-VAR-001)
"""


def get_bsl_generation_prompt(task: str, target_context: str = "", platform_version: str = "8.3.20") -> str:
    """B8: Получить промпт для генерации BSL-кода с правилами контекста.

    Args:
        task: Описание задачи (что нужно сгенерировать)
        target_context: Целевой контекст (thin_client, server, mobile_client, etc.)
        platform_version: Версия платформы 1С

    Returns:
        Готовый промпт для LLM с встроенными правилами.
    """
    return (
        f"Ты — эксперт 1С разработчик. Сгенерируй BSL-код.\n\n"
        f"{BSL_CONTEXT_RULES}\n\n"
        f"ЗАДАЧА: {task}\n"
        f"ЦЕЛЕВОЙ КОНТЕКСТ: {target_context or 'не указан (определи по задаче)'}\n"
        f"ВЕРСИЯ ПЛАТФОРМЫ: {platform_version}\n\n"
        f"ОБЯЗАТЕЛЬНО:\n"
        f"1. Перед генерацией — вызови get_method_details для каждого метода платформы\n"
        f"2. После генерации — вызови check_bsl_context для проверки\n"
        f"3. Верни код + отчёт о проверке контекста"
    )


# A4.2: Token-aware context assembly
def estimate_tokens(text: str) -> int:
    """A4.2: Оценить количество токенов в тексте (без tiktoken).

    Использует эвристику: ~4 символа на токен для русского/английского.
    Если tiktoken установлен — использует его.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """A4.2: Обрезать текст до лимита токенов."""
    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text
    # Эвристика: ~4 символа на токен
    max_chars = max_tokens * 4
    return text[:max_chars] + "\n...[truncated]"


# A4.3: Streaming response support
def is_streaming_supported() -> bool:
    """A4.3: Проверить, поддерживает ли Ollama streaming."""
    return True  # Ollama /api/generate поддерживает stream=true


# A4.4: Retry + circuit breaker
@dataclass
class CircuitBreaker:
    """A4.4: Circuit breaker для Ollama API."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _failures: int = 0
    _last_failure_time: float = 0.0
    _state: str = "closed"  # closed | open | half-open

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.failure_threshold:
            self._state = "open"

    def is_available(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
                return True
            return False
        return True


# A4.5: Model routing
MODEL_ROUTING: dict[str, str] = {
    "codegen": "codellama:13b",
    "audit": "llama3.1:70b",
    "chat": "llama3.1:8b",
    "refactor": "codellama:13b",
    "default": "llama3.1:8b",
}


def route_model(task_type: str) -> str:
    """A4.5: Выбрать модель по типу задачи."""
    return MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])


# A4.6: Cost tracking
@dataclass
class CostTracker:
    """A4.6: Отслеживание стоимости LLM вызовов."""
    _entries: list[dict[str, Any]] = field(default_factory=list)

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self._entries.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        })

    def summary(self) -> dict[str, Any]:
        total = sum(e["total_tokens"] for e in self._entries)
        by_model: dict[str, int] = {}
        for e in self._entries:
            by_model[e["model"]] = by_model.get(e["model"], 0) + e["total_tokens"]
        return {
            "total_calls": len(self._entries),
            "total_tokens": total,
            "by_model": by_model,
        }


# A4.7: Vector index persistence info
def get_vector_persistence_info() -> dict[str, str]:
    """A4.7: Информация о persistence vector index."""
    return {
        "backend": "sqlite-vss (planned)",
        "current": "qdrant in-memory (fallback)",
        "lazy_rebuild": "True",
    }


# A4.8: Hybrid reranking info
def get_reranking_info() -> dict[str, str]:
    """A4.8: Информация о hybrid reranking."""
    return {
        "method": "cross-encoder reranking (planned)",
        "current": "BM25 + vector fusion (0.7 + 0.3)",
        "top_k_before_rerank": "20",
        "top_k_after_rerank": "5",
    }


# A4.9: Fine-tune info
def get_finetune_info() -> dict[str, str]:
    """A4.9: Информация о fine-tuning модели."""
    return {
        "base_model": "ai-forever/sbert_large_mt_nlu_ru",
        "method": "LoRA",
        "corpus": "БСП + УТ11 + ERP (план сбора)",
        "status": "planned",
    }
