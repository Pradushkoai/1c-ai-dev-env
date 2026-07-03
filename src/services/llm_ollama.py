"""
llm_ollama.py — Интеграция с локальной LLM через Ollama REST API.

S8 (план v3): RAG pipeline для полностью офлайн AI-coding в 1С.

Ollama — локальный REST API для запуска LLM моделей (LLaMA 3.1, Qwen 2.5).
Работает на CPU (медленно) или GPU (быстро). Не требует интернет.

Использование:
    from src.services.llm_ollama import OllamaClient

    client = OllamaClient()  # default: http://localhost:11434
    if client.is_available():
        response = client.generate(
            model="llama3.1:8b",
            prompt="Как создать справочник в 1С?",
            context="Справочник — это объект 1С для хранения нормативно-справочной информации...",
        )
        print(response)

Зависимости: нет (использует urllib из стандартной библиотеки).
Требует: установленный Ollama (https://ollama.ai) и загруженную модель.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Default Ollama API endpoint
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Default model (изменяется через env var OLLAMA_MODEL)
_DEFAULT_MODEL_FALLBACK = "llama3.1:8b"


def _get_default_model() -> str:
    """Получить модель по умолчанию из env var (вызывается в __init__)."""
    return os.environ.get("OLLAMA_MODEL", _DEFAULT_MODEL_FALLBACK)


# Для обратной совместимости
DEFAULT_MODEL = _get_default_model()


@dataclass
class OllamaResponse:
    """Ответ от Ollama API."""

    text: str = ""
    model: str = ""
    total_duration: int = 0  # наносекунды
    load_duration: int = 0
    prompt_eval_count: int = 0
    eval_count: int = 0
    done: bool = True
    error: str = ""

    @property
    def latency_ms(self) -> float:
        """Латентность в миллисекундах."""
        return self.total_duration / 1_000_000

    @property
    def tokens_generated(self) -> int:
        """Количество сгенерированных токенов."""
        return self.eval_count

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict."""
        return {
            "text": self.text,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 2),
            "tokens_generated": self.tokens_generated,
            "prompt_tokens": self.prompt_eval_count,
            "done": self.done,
            "error": self.error,
        }


class OllamaClient:
    """Клиент для Ollama REST API (S8).

    Ollama — локальный сервер для запуска LLM моделей.
    Не требует интернет, работает на CPU или GPU.

    Attributes:
        base_url: URL Ollama API (default: http://localhost:11434).
        model: Модель по умолчанию (default: llama3.1:8b или env OLLAMA_MODEL).
        timeout: Timeout запроса в секундах.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> None:
        """Инициализация Ollama client.

        Args:
            base_url: URL Ollama API. Если None — берётся из env OLLAMA_URL
                или DEFAULT_OLLAMA_URL.
            model: Модель по умолчанию. Если None — берётся из env OLLAMA_MODEL
                или DEFAULT_MODEL.
            timeout: Timeout запроса в секундах (default: 120).
        """
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.model = model or _get_default_model()
        self.timeout = timeout

    def is_available(self) -> bool:
        """Проверить, доступен ли Ollama сервер.

        Returns:
            True если сервер отвечает на /api/tags.
        """
        try:
            response = self._request("GET", "/api/tags")
            return response is not None
        except Exception as e:
            logger.debug("Ollama not available: %s", e)
            return False

    def list_models(self) -> list[dict[str, Any]]:
        """Получить список установленных моделей.

        Returns:
            Список моделей [{name, size, modified_at}].
        """
        try:
            response = self._request("GET", "/api/tags")
            if response is None:
                return []
            models = response.get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in models
            ]
        except Exception:
            return []

    def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> OllamaResponse:
        """Генерация текста через Ollama.

        Args:
            prompt: Пользовательский промпт (запрос).
            context: Контекст для RAG (найденные методы 1С, паттерны, и т.д.).
            model: Модель (если None — self.model).
            system: Системный промпт (роль/инструкции).
            temperature: Temperature (0.0 = deterministic, 1.0 = creative).
            max_tokens: Максимум токенов в ответе.
            stream: Stream mode (возвращает chunks). Не реализовано в sync версии.

        Returns:
            OllamaResponse с результатом генерации.
        """
        use_model = model or self.model

        # Формируем полный промпт с контекстом
        full_prompt = self._build_prompt(prompt, context, system)

        payload: dict[str, Any] = {
            "model": use_model,
            "prompt": full_prompt,
            "stream": False,  # всегда non-streaming для простоты
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            response = self._request("POST", "/api/generate", payload)
            if response is None:
                return OllamaResponse(error="No response from Ollama", model=use_model)

            return OllamaResponse(
                text=response.get("response", ""),
                model=response.get("model", use_model),
                total_duration=response.get("total_duration", 0),
                load_duration=response.get("load_duration", 0),
                prompt_eval_count=response.get("prompt_eval_count", 0),
                eval_count=response.get("eval_count", 0),
                done=response.get("done", True),
            )
        except urllib.error.URLError as e:
            logger.warning("Ollama connection error: %s", e)
            return OllamaResponse(error=f"Connection error: {e}", model=use_model)
        except Exception as e:
            logger.warning("Ollama generate error: %s", e)
            return OllamaResponse(error=f"Generate error: {e}", model=use_model)

    def _build_prompt(self, prompt: str, context: str, system: str) -> str:
        """Построить полный промпт с контекстом и системными инструкциями.

        Args:
            prompt: Пользовательский запрос.
            context: RAG контекст (методы 1С, паттерны).
            system: Системный промпт.

        Returns:
            Полный промпт для LLM.
        """
        parts: list[str] = []

        # Системный промпт
        if system:
            parts.append(system)
        else:
            # Default system prompt для 1С разработки
            parts.append(
                "Ты — эксперт 1С разработчик. Отвечай на русском языке. "
                "Используй предоставленный контекст для точных ответов. "
                "Если контекст не содержит ответа, скажи что не знаешь."
            )

        # RAG контекст
        if context:
            parts.append(f"\n--- КОНТЕКСТ ---\n{context}\n--- КОНЕЦ КОНТЕКСТА ---\n")

        # Пользовательский запрос
        parts.append(f"\nВопрос: {prompt}\n")

        parts.append("Ответ:")

        return "\n".join(parts)

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Выполнить HTTP запрос к Ollama API.

        Args:
            method: HTTP method (GET, POST).
            endpoint: API endpoint (e.g., /api/generate).
            payload: JSON payload for POST.

        Returns:
            JSON response dict или None при ошибке.
        """
        url = f"{self.base_url}{endpoint}"

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            logger.warning("Ollama HTTP error %d: %s", e.code, e.reason)
            return None
        except urllib.error.URLError as e:
            raise e  # re-raise для is_available() обработки
        except Exception as e:
            logger.warning("Ollama request error: %s", e)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику/статус Ollama.

        Returns:
            {available, base_url, model, models}
        """
        available = self.is_available()
        models = self.list_models() if available else []

        return {
            "available": available,
            "base_url": self.base_url,
            "default_model": self.model,
            "models": models,
            "models_count": len(models),
        }
