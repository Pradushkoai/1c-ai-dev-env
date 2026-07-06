"""
S8: Тесты для RAG с Ollama (llm_ollama.py + rag_pipeline.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from src.services.llm_ollama import OllamaClient, OllamaResponse, DEFAULT_OLLAMA_URL, DEFAULT_MODEL
from src.services.rag_pipeline import RagPipeline, RagResult


# ============================================================================
# Тесты — OllamaResponse
# ============================================================================


class TestOllamaResponse:
    """Проверка OllamaResponse dataclass."""

    def test_default_values(self) -> None:
        """OllamaResponse имеет корректные defaults."""
        r = OllamaResponse()
        assert r.text == ""
        assert r.done is True
        assert r.error == ""

    def test_latency_ms(self) -> None:
        """latency_ms конвертирует наносекунды в миллисекунды."""
        r = OllamaResponse(total_duration=1_000_000)  # 1ms in ns
        assert r.latency_ms == 1.0

    def test_tokens_generated(self) -> None:
        """tokens_generated = eval_count."""
        r = OllamaResponse(eval_count=42)
        assert r.tokens_generated == 42

    def test_to_dict(self) -> None:
        """to_dict возвращает корректный dict."""
        r = OllamaResponse(text="hello", model="llama3.1", eval_count=5, total_duration=1_000_000)
        d = r.to_dict()
        assert d["text"] == "hello"
        assert d["model"] == "llama3.1"
        assert d["tokens_generated"] == 5
        assert d["latency_ms"] == 1.0


# ============================================================================
# Тесты — OllamaClient
# ============================================================================


class TestOllamaClient:
    """Проверка OllamaClient."""

    def test_init_default(self) -> None:
        """OllamaClient с defaults."""
        client = OllamaClient()
        assert client.base_url == DEFAULT_OLLAMA_URL
        assert client.model == DEFAULT_MODEL
        assert client.timeout == 120

    def test_init_custom(self) -> None:
        """OllamaClient с custom params."""
        client = OllamaClient(base_url="http://custom:8080", model="qwen2.5", timeout=60)
        assert client.base_url == "http://custom:8080"
        assert client.model == "qwen2.5"
        assert client.timeout == 60

    def test_init_from_env(self) -> None:
        """OllamaClient берёт URL и model из env vars."""
        import os

        with patch.dict(os.environ, {"OLLAMA_URL": "http://env:9999", "OLLAMA_MODEL": "mistral"}):
            # Пересоздаём client — DEFAULT_MODEL уже вычислен, но __init__ читает env
            client = OllamaClient()
            assert client.base_url == "http://env:9999"
            assert client.model == "mistral"

    def test_is_available_false_when_no_server(self) -> None:
        """is_available() → False когда сервер недоступен."""
        client = OllamaClient(base_url="http://nonexistent:99999")
        assert client.is_available() is False

    def test_is_available_true_with_mock(self) -> None:
        """is_available() → True когда сервер отвечает."""
        client = OllamaClient(base_url="http://localhost:11434")
        with patch.object(client, "_request", return_value={"models": []}):
            assert client.is_available() is True

    def test_list_models_with_mock(self) -> None:
        """list_models() возвращает модели."""
        client = OllamaClient()
        mock_response = {
            "models": [
                {"name": "llama3.1:8b", "size": 5000000000, "modified_at": "2026-01-01"},
                {"name": "qwen2.5:7b", "size": 4500000000, "modified_at": "2026-01-02"},
            ]
        }
        with patch.object(client, "_request", return_value=mock_response):
            models = client.list_models()
        assert len(models) == 2
        assert models[0]["name"] == "llama3.1:8b"

    def test_list_models_empty(self) -> None:
        """list_models() → пустой список при ошибке."""
        client = OllamaClient()
        with patch.object(client, "_request", return_value=None):
            models = client.list_models()
        assert models == []

    def test_generate_success(self) -> None:
        """generate() возвращает OllamaResponse с текстом."""
        client = OllamaClient()
        mock_response = {
            "response": "Справочник создаётся через Метаданные → Справочники → Добавить",
            "model": "llama3.1:8b",
            "total_duration": 5_000_000_000,  # 5 seconds in ns
            "eval_count": 10,
            "prompt_eval_count": 50,
            "done": True,
        }
        with patch.object(client, "_request", return_value=mock_response):
            result = client.generate(prompt="Как создать справочник?")

        assert result.text == "Справочник создаётся через Метаданные → Справочники → Добавить"
        assert result.model == "llama3.1:8b"
        assert result.tokens_generated == 10
        assert result.done is True
        assert result.error == ""

    def test_generate_with_context(self) -> None:
        """generate() с context — промпт содержит контекст."""
        client = OllamaClient()
        mock_response = {"response": "ответ", "model": "test", "done": True}

        with patch.object(client, "_request", return_value=mock_response) as mock_req:
            client.generate(
                prompt="вопрос",
                context="контекст 1С",
                system="системный промпт",
            )

            # Проверяем что payload содержит промпт с контекстом
            call_args = mock_req.call_args
            payload = call_args[0][2]  # third positional arg = payload
            assert "КОНТЕКСТ" in payload["prompt"]
            assert "контекст 1С" in payload["prompt"]
            assert "системный промпт" in payload["prompt"]

    def test_generate_connection_error(self) -> None:
        """generate() при connection error → OllamaResponse с error."""
        client = OllamaClient()
        with patch.object(client, "_request", side_effect=urllib.error.URLError("Connection refused")):
            result = client.generate(prompt="test")
        assert result.error != ""
        assert "Connection" in result.error or "connection" in result.error.lower()

    def test_generate_no_response(self) -> None:
        """generate() при None response → OllamaResponse с error."""
        client = OllamaClient()
        with patch.object(client, "_request", return_value=None):
            result = client.generate(prompt="test")
        assert "No response" in result.error

    def test_get_stats(self) -> None:
        """get_stats() возвращает корректную статистику."""
        client = OllamaClient(base_url="http://test:1234", model="test-model")
        with (
            patch.object(client, "is_available", return_value=True),
            patch.object(client, "list_models", return_value=[{"name": "test-model"}]),
        ):
            stats = client.get_stats()
        assert stats["available"] is True
        assert stats["base_url"] == "http://test:1234"
        assert stats["default_model"] == "test-model"
        assert stats["models_count"] == 1

    def test_get_stats_unavailable(self) -> None:
        """get_stats() когда Ollama недоступен."""
        client = OllamaClient()
        with patch.object(client, "is_available", return_value=False):
            stats = client.get_stats()
        assert stats["available"] is False
        assert stats["models"] == []
        assert stats["models_count"] == 0

    def test_build_prompt_with_all_parts(self) -> None:
        """_build_prompt включает system, context, prompt."""
        client = OllamaClient()
        prompt = client._build_prompt(
            prompt="Как создать справочник?",
            context="Справочники — объекты 1С",
            system="Ты эксперт 1С",
        )
        assert "Ты эксперт 1С" in prompt
        assert "КОНТЕКСТ" in prompt
        assert "Справочники — объекты 1С" in prompt
        assert "Как создать справочник?" in prompt
        assert "Ответ:" in prompt

    def test_build_prompt_default_system(self) -> None:
        """_build_prompt с пустым system использует default."""
        client = OllamaClient()
        prompt = client._build_prompt(prompt="test", context="", system="")
        assert "эксперт 1С" in prompt  # default system prompt

    def test_build_prompt_no_context(self) -> None:
        """_build_prompt без context — нет блока КОНТЕКСТ."""
        client = OllamaClient()
        prompt = client._build_prompt(prompt="test", context="", system="")
        assert "КОНТЕКСТ" not in prompt


# ============================================================================
# Тесты — RagPipeline
# ============================================================================


class TestRagPipeline:
    """Проверка RagPipeline."""

    def test_init_default(self) -> None:
        """RagPipeline инициализируется."""
        rag = RagPipeline()
        assert rag is not None
        assert rag.ollama is not None

    def test_is_available_false(self) -> None:
        """is_available() → False когда Ollama недоступен."""
        rag = RagPipeline()
        with patch.object(rag.ollama, "is_available", return_value=False):
            assert rag.is_available() is False

    def test_is_available_true(self) -> None:
        """is_available() → True когда Ollama доступен."""
        rag = RagPipeline()
        with patch.object(rag.ollama, "is_available", return_value=True):
            assert rag.is_available() is True

    def test_ask_unavailable(self) -> None:
        """ask() при недоступном Ollama → RagResult с error."""
        rag = RagPipeline()
        with patch.object(rag.ollama, "is_available", return_value=False):
            result = rag.ask("Как создать справочник?")
        assert result.rag_available is False
        assert "Ollama" in result.error

    def test_ask_success(self) -> None:
        """ask() успешно генерирует ответ."""
        rag = RagPipeline()
        mock_response = OllamaResponse(
            text="Справочник создаётся через Конфигуратор",
            model="llama3.1:8b",
            eval_count=5,
        )

        with (
            patch.object(rag.ollama, "is_available", return_value=True),
            patch.object(rag.ollama, "generate", return_value=mock_response),
            patch.object(rag, "_gather_context", return_value=("контекст", ["platform"], 5)),
        ):
            result = rag.ask("Как создать справочник?")

        assert result.rag_available is True
        assert result.answer.text == "Справочник создаётся через Конфигуратор"
        assert result.context_sources == ["platform"]
        assert result.search_results_count == 5
        assert result.error == ""

    def test_ask_to_dict(self) -> None:
        """ask() результат можно сериализовать через to_dict()."""
        rag = RagPipeline()
        mock_response = OllamaResponse(text="ответ", model="test")

        with (
            patch.object(rag.ollama, "is_available", return_value=True),
            patch.object(rag.ollama, "generate", return_value=mock_response),
            patch.object(rag, "_gather_context", return_value=("", [], 0)),
        ):
            result = rag.ask("test")

        d = result.to_dict()
        assert "answer" in d
        assert "context_sources" in d
        assert "rag_available" in d

    def test_get_stats(self) -> None:
        """get_stats() возвращает корректную статистику."""
        rag = RagPipeline(max_context_length=5000)
        with (
            patch.object(rag.ollama, "is_available", return_value=True),
            patch.object(rag.ollama, "get_stats", return_value={"available": True, "models": []}),
        ):
            stats = rag.get_stats()
        assert stats["available"] is True
        assert stats["max_context_length"] == 5000
        assert "system_prompt_length" in stats

    def test_system_prompt_contains_1s(self) -> None:
        """SYSTEM_PROMPT содержит упоминание 1С."""
        assert "1С" in RagPipeline.SYSTEM_PROMPT or "1C" in RagPipeline.SYSTEM_PROMPT

    def test_context_truncation(self) -> None:
        """Контекст обрезается до max_context_length в _gather_context."""
        rag = RagPipeline(max_context_length=100)
        mock_response = OllamaResponse(text="ответ")

        # Проверяем что _gather_context обрезает длинный контекст
        long_context = "x" * 200

        # Мокаем _search_* методы чтобы вернуть длинный контекст
        with (
            patch.object(rag.ollama, "is_available", return_value=True),
            patch.object(rag.ollama, "generate", return_value=mock_response),
            patch.object(rag, "_search_platform_methods", return_value=long_context),
            patch.object(rag, "_search_config_code", return_value=""),
            patch.object(rag, "_search_knowledge_base", return_value=""),
        ):
            result = rag.ask("test")

        # context_length должен быть <= max_context_length + truncation message
        assert result.context_length <= 100 + 50  # 50 for truncation message overhead
