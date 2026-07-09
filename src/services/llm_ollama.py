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

        R8 (2026-07-09): Поддержка MODEL_ROUTING — выбор модели по task_type.
        R9 (2026-07-09): CircuitBreaker — защита от каскадных failов.

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

        # R9: CircuitBreaker для защиты от каскадных failов
        from .prompt_library import CircuitBreaker
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        # R8: Model context window sizes (для max_tokens auto-sizing)
        self._model_context_windows: dict[str, int] = {
            "llama3.1:8b": 128000,
            "llama3.1:70b": 128000,
            "codellama:13b": 16000,
            "codellama:34b": 16000,
            "mistral:7b": 32000,
        }

    # R8: Model routing
    def get_model_for_task(self, task_type: str) -> str:
        """R8: Выбрать модель по типу задачи.

        Args:
            task_type: codegen, audit, chat, refactor, default

        Returns:
            Имя модели для Ollama.
        """
        from .prompt_library import MODEL_ROUTING, route_model
        return route_model(task_type)

    def get_context_window(self, model: str | None = None) -> int:
        """R8: Получить context window size для модели.

        Args:
            model: Имя модели (если None — self.model)

        Returns:
            Размер context window в токенах (default: 8000 если unknown).
        """
        use_model = model or self.model
        # Попытка exact match
        if use_model in self._model_context_windows:
            return self._model_context_windows[use_model]
        # Fuzzy match — ищем модель по префиксу
        for key, size in self._model_context_windows.items():
            if use_model.startswith(key.split(":")[0]):
                return size
        return 8000  # safe default

    def generate_for_task(
        self,
        prompt: str,
        task_type: str = "default",
        context: str = "",
        system: str = "",
        temperature: float = 0.7,
        max_tokens_ratio: float = 0.25,
    ) -> OllamaResponse:
        """R8: Генерация с автоматически выбранной моделью по task_type.

        Args:
            prompt: Пользовательский промпт.
            task_type: codegen, audit, chat, refactor, default.
            context: Контекст для RAG.
            system: Системный промпт.
            temperature: Temperature.
            max_tokens_ratio: Доля context window для ответа (default 0.25 = 25%).

        Returns:
            OllamaResponse с результатом генерации.
        """
        model = self.get_model_for_task(task_type)
        context_window = self.get_context_window(model)
        max_tokens = int(context_window * max_tokens_ratio)

        return self.generate(
            prompt=prompt,
            context=context,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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

        R9 (2026-07-09): CircuitBreaker — если 5+ failов подряд, circuit opens
        на 60s, возвращая immediate error без запроса к Ollama.

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

        # R9: CircuitBreaker — проверяем доступность
        if not self._circuit_breaker.is_available():
            return OllamaResponse(
                error="Circuit breaker open — Ollama unavailable (5+ failures)",
                model=use_model,
            )

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
                self._circuit_breaker.record_failure()
                return OllamaResponse(error="No response from Ollama", model=use_model)

            # R9: Успех — сбрасываем circuit breaker
            self._circuit_breaker.record_success()

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
            self._circuit_breaker.record_failure()
            return OllamaResponse(error=f"Connection error: {e}", model=use_model)
        except Exception as e:
            logger.warning("Ollama generate error: %s", e)
            self._circuit_breaker.record_failure()
            return OllamaResponse(error=f"Generate error: {e}", model=use_model)

    # R9: CircuitBreaker accessors
    def get_circuit_breaker_state(self) -> str:
        """R9: Получить состояние circuit breaker (closed|open|half-open)."""
        return self._circuit_breaker._state

    def reset_circuit_breaker(self) -> None:
        """R9: Сбросить circuit breaker (для тестов)."""
        self._circuit_breaker = type(self._circuit_breaker)(
            failure_threshold=self._circuit_breaker.failure_threshold,
            recovery_timeout=self._circuit_breaker.recovery_timeout,
        )

    def generate_stream(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Any:
        """A4.3: Streaming генерация текста через Ollama.

        Возвращает generator, который yield'ит chunks текста по мере их поступления.
        Ollama /api/generate с stream=true возвращает newline-delimited JSON,
        каждый объект содержит поле "response" с куском текста.

        Args:
            prompt: Пользовательский промпт.
            context: Контекст для RAG.
            model: Модель (если None — self.model).
            system: Системный промпт.
            temperature: Temperature.
            max_tokens: Максимум токенов.

        Yields:
            str chunks текста по мере генерации.

        Raises:
            urllib.error.URLError: Если Ollama недоступен.
        """
        use_model = model or self.model
        full_prompt = self._build_prompt(prompt, context, system)

        payload: dict[str, Any] = {
            "model": use_model,
            "prompt": full_prompt,
            "stream": True,  # A4.3: streaming mode
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        url = f"{self.base_url}/api/generate"
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        # Streaming: читаем response построчно
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            for line in response:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    text = chunk.get("response", "")
                    if text:
                        yield text
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

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
                result: dict[str, Any] | None = json.loads(body)
                return result
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
