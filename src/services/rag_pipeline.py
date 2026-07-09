"""
rag_pipeline.py — RAG pipeline для AI-coding в 1С (S8).

RAG (Retrieval-Augmented Generation) — подход, при котором LLM получает
контекст из базы знаний перед генерацией ответа.

Pipeline:
1. Query → BM25+vector search по методам платформы 1С
2. Query → search по коду конфигурации
3. Query → knowledge base (паттерны, антипаттерны)
4. Context assembly → объединение найденных результатов
5. LLM generation → Ollama генерирует ответ с контекстом

Использование:
    from src.services.rag_pipeline import RagPipeline

    rag = RagPipeline()
    if rag.is_available():
        answer = rag.ask("Как создать справочник в 1С?", config_name="ut11")
        print(answer.text)
    else:
        print("RAG недоступен — нужен Ollama")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm_ollama import OllamaClient, OllamaResponse

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    """Результат RAG pipeline."""

    answer: OllamaResponse
    context_sources: list[str] = field(default_factory=list)
    context_length: int = 0
    search_results_count: int = 0
    rag_available: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict."""
        return {
            "answer": self.answer.to_dict(),
            "context_sources": self.context_sources,
            "context_length": self.context_length,
            "search_results_count": self.search_results_count,
            "rag_available": self.rag_available,
            "error": self.error,
        }


class RagPipeline:
    """RAG pipeline для AI-coding в 1С (S8).

    Объединяет:
    - BM25+vector search (поиск методов платформы 1С)
    - Knowledge base (паттерны, антипаттерны)
    - Ollama LLM (генерация ответа с контекстом)

    Attributes:
        ollama: OllamaClient для LLM генерации
        index_path: Путь к fast-search-index.json
        max_context_length: Максимум символов в контексте (default: 4000)
    """

    # Системный промпт для 1С разработки
    SYSTEM_PROMPT = (
        "Ты — эксперт 1С разработчик с глубоким знанием платформы 1С:Предприятие 8.3. "
        "Отвечай на русском языке. Используй предоставленный контекст (методы платформы 1С, "
        "паттерны разработки) для точных ответов. "
        "Если контекст не содержит ответа, скажи что не знаешь и предложи изучить документацию. "
        "Всегда соблюдай стандарты 1С (STD 456): табы для отступов, области в коде, "
        "ключевые слова запросов КАПСОМ."
    )

    def __init__(
        self,
        ollama: OllamaClient | None = None,
        index_path: Path | None = None,
        max_context_length: int = 4000,
        max_context_tokens: int = 0,
    ) -> None:
        """Инициализация RAG pipeline.

        Args:
            ollama: OllamaClient (если None — создаётся новый).
            index_path: Путь к fast-search-index.json.
                Если None — будет определён через Project.
            max_context_length: Максимум символов в контексте для LLM (fallback).
            max_context_tokens: F2.8: Максимум ТОКЕНОВ в контексте (приоритет над char-based).
                Если 0 — используется char-based (backward compat).
                Рекомендуется: 3000-8000 в зависимости от модели Ollama.
        """
        self.ollama = ollama or OllamaClient()
        self._index_path = index_path
        self._max_context = max_context_length
        self._max_context_tokens = max_context_tokens

    def is_available(self) -> bool:
        """Проверить, доступен ли RAG pipeline.

        Returns:
            True если Ollama доступен.
        """
        return self.ollama.is_available()

    def ask(
        self,
        query: str,
        config_name: str = "",
        limit: int = 5,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> RagResult:
        """Задать вопрос RAG pipeline.

        Args:
            query: Вопрос/запрос на естественном языке.
            config_name: Имя конфигурации 1С (для поиска по коду).
            limit: Максимум результатов поиска.
            model: Модель Ollama (если None — default).
            temperature: Temperature для LLM.
            max_tokens: Максимум токенов в ответе.

        Returns:
            RagResult с ответом и метаданными.
        """
        if not self.is_available():
            return RagResult(
                answer=OllamaResponse(error="Ollama not available"),
                rag_available=False,
                error="RAG pipeline недоступен — Ollama не запущен. "
                "Установите Ollama: https://ollama.ai и запустите: ollama run llama3.1:8b",
            )

        # 1. Сбор контекста
        context, sources, search_count = self._gather_context(query, config_name, limit)

        # 2. LLM генерация
        response = self.ollama.generate(
            prompt=query,
            context=context,
            system=self.SYSTEM_PROMPT,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return RagResult(
            answer=response,
            context_sources=sources,
            context_length=len(context),
            search_results_count=search_count,
            rag_available=True,
        )

    def _gather_context(
        self,
        query: str,
        config_name: str,
        limit: int,
    ) -> tuple[str, list[str], int]:
        """Собрать контекст для RAG из多个 источников.

        Args:
            query: Поисковый запрос.
            config_name: Имя конфигурации.
            limit: Максимум результатов.

        Returns:
            (context_text, sources, total_results)
        """
        context_parts: list[str] = []
        sources: list[str] = []
        total_results = 0

        # 1. Поиск по методам платформы 1С
        platform_context = self._search_platform_methods(query, limit)
        if platform_context:
            context_parts.append("=== МЕТОДЫ ПЛАТФОРМЫ 1С ===")
            context_parts.append(platform_context)
            sources.append("platform_methods")
            total_results += limit

        # 2. Поиск по коду конфигурации
        if config_name:
            config_context = self._search_config_code(query, config_name, limit)
            if config_context:
                context_parts.append(f"\n=== КОД КОНФИГУРАЦИИ '{config_name}' ===")
                context_parts.append(config_context)
                sources.append("config_code")
                total_results += limit

        # 3. Knowledge base (паттерны)
        kb_context = self._search_knowledge_base(query, limit)
        if kb_context:
            context_parts.append("\n=== БАЗА ЗНАНИЙ ===")
            context_parts.append(kb_context)
            sources.append("knowledge_base")
            total_results += limit

        context = "\n".join(context_parts)

        # F2.8: Token-aware truncation (приоритет над char-based)
        if self._max_context_tokens > 0:
            from .prompt_library import truncate_to_token_limit

            context = truncate_to_token_limit(context, self._max_context_tokens)
        elif len(context) > self._max_context:
            # Fallback: char-based (backward compat)
            context = context[: self._max_context] + "\n... (контекст обрезан)"

        return context, sources, total_results

    def _search_platform_methods(self, query: str, limit: int) -> str:
        """Поиск по методам платформы 1С (BM25+vector).

        Returns:
            Текстовый контекст с найденными методами.
        """
        try:
            if self._index_path and self._index_path.exists():
                from .search_hybrid import search_hybrid_auto

                results = search_hybrid_auto(self._index_path, query, limit=limit)
                if not results:
                    return ""

                lines: list[str] = []
                for r in results[:limit]:
                    name = r.get("name_ru") or r.get("name_en") or ""
                    desc = r.get("description", "")[:200]
                    syntax = r.get("syntax", "")[:200]
                    if name:
                        lines.append(f"• {name}")
                        if syntax:
                            lines.append(f"  Синтаксис: {syntax}")
                        if desc:
                            lines.append(f"  Описание: {desc}")
                return "\n".join(lines)
        except Exception as e:
            logger.debug("Platform methods search failed: %s", e)

        return ""

    def _search_config_code(self, query: str, config_name: str, limit: int) -> str:
        """Поиск по коду конфигурации 1С.

        Returns:
            Текстовый контекст с найденными методами.
        """
        try:
            from src.project import Project

            project = Project.from_cwd()
            results = project.search_methods(query, limit=limit)
            if not results:
                return ""

            lines: list[str] = []
            for r in results[:limit]:
                name = r.get("name", "")
                module = r.get("module", "")
                if name:
                    lines.append(f"• {module}.{name}()")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Config code search failed: %s", e)

        return ""

    def _search_knowledge_base(self, query: str, limit: int) -> str:
        """Поиск по knowledge base (паттерны, антипаттерны).

        Returns:
            Текстовый контекст с найденными статьями.
        """
        try:
            from .knowledge_base import KnowledgeBase

            kb = KnowledgeBase()
            results = kb.search(query, limit=limit)
            if not results:
                return ""

            lines: list[str] = []
            for r in results[:limit]:
                title = r.get("title", "")
                category = r.get("category", "")
                if title:
                    lines.append(f"• [{category}] {title}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Knowledge base search failed: %s", e)

        return ""

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику RAG pipeline.

        Returns:
            {available, ollama_stats, max_context_length, max_context_tokens}
        """
        return {
            "available": self.is_available(),
            "ollama": self.ollama.get_stats(),
            "max_context_length": self._max_context,
            "max_context_tokens": self._max_context_tokens,
            "truncation_mode": "token" if self._max_context_tokens > 0 else "char",
            "system_prompt_length": len(self.SYSTEM_PROMPT),
        }
