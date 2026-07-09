"""
A4.3 (2026-07-06): Тесты для streaming responses.

Проверяет:
- is_streaming_supported() возвращает True
- OllamaClient.generate_stream() метод существует
- generate_stream возвращает generator
- Mocked streaming: chunks yield'ятся правильно
- Edge cases: пустой response, connection error
- Collect streaming: собрать все chunks в строку
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.services.llm_ollama import OllamaClient
from src.services.prompt_library import is_streaming_supported


# ============================================================================
# is_streaming_supported tests
# ============================================================================


class TestIsStreamingSupported:
    def test_returns_true(self) -> None:
        """is_streaming_supported возвращает True (Ollama поддерживает streaming)."""
        assert is_streaming_supported() is True

    def test_returns_bool(self) -> None:
        """Возвращает bool, не строку."""
        result = is_streaming_supported()
        assert isinstance(result, bool)


# ============================================================================
# generate_stream method tests
# ============================================================================


class TestGenerateStreamMethod:
    def test_method_exists(self) -> None:
        """Метод generate_stream существует."""
        client = OllamaClient()
        assert hasattr(client, "generate_stream")
        assert callable(client.generate_stream)

    def test_returns_generator(self) -> None:
        """generate_stream возвращает generator."""
        client = OllamaClient()

        # Mock urlopen чтобы вернуть пустой stream
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.__iter__ = MagicMock(return_value=iter([]))

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.generate_stream("test prompt")
            # Generator
            assert hasattr(result, "__next__") or hasattr(result, "__iter__")


# ============================================================================
# Mocked streaming tests
# ============================================================================


class TestMockedStreaming:
    """Тесты streaming с mock'ом HTTP response."""

    def _make_mock_response(self, chunks: list[dict]) -> MagicMock:
        """Создать mock response с chunks."""
        lines = [json.dumps(c).encode("utf-8") + b"\n" for c in chunks]
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.__iter__ = MagicMock(return_value=iter(lines))
        return mock_response

    def test_stream_yields_chunks(self) -> None:
        """generate_stream yield'ит chunks."""
        client = OllamaClient()

        chunks = [
            {"response": "Hello", "done": False},
            {"response": " world", "done": False},
            {"response": "!", "done": True},
        ]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test"))

        assert result == ["Hello", " world", "!"]

    def test_stream_stops_on_done(self) -> None:
        """Streaming останавливается когда done=True."""
        client = OllamaClient()

        chunks = [
            {"response": "First", "done": False},
            {"response": "Second", "done": True},
            {"response": "Third", "done": False},  # не должно прийти
        ]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test"))

        assert result == ["First", "Second"]

    def test_stream_empty_response(self) -> None:
        """Пустой response — нет chunks."""
        client = OllamaClient()

        chunks = [{"response": "", "done": True}]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test"))

        assert result == []

    def test_stream_skips_empty_chunks(self) -> None:
        """Пустые chunks пропускаются."""
        client = OllamaClient()

        chunks = [
            {"response": "", "done": False},  # пустой — пропускается
            {"response": "Real", "done": False},
            {"response": "", "done": False},  # пустой — пропускается
            {"response": " content", "done": True},
        ]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test"))

        assert result == ["Real", " content"]

    def test_stream_handles_invalid_json(self) -> None:
        """Невалидный JSON пропускается."""
        client = OllamaClient()

        # Mix of valid and invalid JSON lines
        lines = [
            b'{"response": "Valid", "done": false}\n',
            b'invalid json line\n',
            b'{"response": " End", "done": true}\n',
        ]

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.__iter__ = MagicMock(return_value=iter(lines))

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = list(client.generate_stream("test"))

        # Invalid JSON пропускается, valid chunks приходят
        assert result == ["Valid", " End"]

    def test_stream_collects_to_string(self) -> None:
        """Сборка всех chunks в строку."""
        client = OllamaClient()

        chunks = [
            {"response": "Hello", "done": False},
            {"response": " ", "done": False},
            {"response": "World", "done": False},
            {"response": "!", "done": True},
        ]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            collected = "".join(client.generate_stream("test"))

        assert collected == "Hello World!"

    def test_stream_with_context(self) -> None:
        """Streaming с context параметром."""
        client = OllamaClient()

        chunks = [{"response": "Response", "done": True}]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            list(client.generate_stream("prompt", context="my context"))

        # Проверяем что urlopen был вызван
        mock_urlopen.assert_called_once()

    def test_stream_with_system_prompt(self) -> None:
        """Streaming с system prompt."""
        client = OllamaClient()

        chunks = [{"response": "OK", "done": True}]
        mock_resp = self._make_mock_response(chunks)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test", system="You are assistant"))

        assert result == ["OK"]


# ============================================================================
# Stream vs non-stream comparison tests
# ============================================================================


class TestStreamVsNonStream:
    """Сравнение streaming и non-streaming режимов."""

    def test_stream_and_generate_both_exist(self) -> None:
        """И generate, и generate_stream существуют."""
        client = OllamaClient()
        assert hasattr(client, "generate")
        assert hasattr(client, "generate_stream")

    def test_stream_uses_stream_true_in_payload(self) -> None:
        """generate_stream отправляет stream=True в payload."""
        client = OllamaClient()

        chunks = [{"response": "X", "done": True}]
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(return_value=iter([
            json.dumps(c).encode("utf-8") + b"\n" for c in chunks
        ]))

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            list(client.generate_stream("test"))

            # Проверяем что Request был создан с правильным data
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            # data должен содержать stream: true
            import json as json_mod
            payload = json_mod.loads(req.data.decode("utf-8"))
            assert payload["stream"] is True


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_stream_with_empty_prompt(self) -> None:
        """Пустой prompt — streaming работает."""
        client = OllamaClient()
        chunks = [{"response": "X", "done": True}]
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(return_value=iter([
            json.dumps(c).encode("utf-8") + b"\n" for c in chunks
        ]))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream(""))
        assert result == ["X"]

    def test_stream_with_max_tokens(self) -> None:
        """Streaming с max_tokens."""
        client = OllamaClient()
        chunks = [{"response": "X", "done": True}]
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(return_value=iter([
            json.dumps(c).encode("utf-8") + b"\n" for c in chunks
        ]))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test", max_tokens=100))
        assert result == ["X"]

    def test_stream_with_temperature(self) -> None:
        """Streaming с temperature."""
        client = OllamaClient()
        chunks = [{"response": "X", "done": True}]
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(return_value=iter([
            json.dumps(c).encode("utf-8") + b"\n" for c in chunks
        ]))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list(client.generate_stream("test", temperature=0.1))
        assert result == ["X"]


# ============================================================================
# Integration: simulated real Ollama streaming
# ============================================================================


class TestIntegrationSimulated:
    """Интеграционный тест: симуляция реального streaming от Ollama."""

    def test_full_streaming_session(self) -> None:
        """Полная streaming сессия с несколькими chunks."""
        client = OllamaClient()

        # Симулируем chunks как от реального Ollama
        chunks = [
            {"response": "Процедура", "done": False, "model": "llama3.1"},
            {"response": " Тест", "done": False, "model": "llama3.1"},
            {"response": "()\n", "done": False, "model": "llama3.1"},
            {"response": "    Сообщить", "done": False, "model": "llama3.1"},
            {"response": "(\"Hello\");", "done": False, "model": "llama3.1"},
            {"response": "\nКонецПроцедуры", "done": False, "model": "llama3.1"},
            {"response": "", "done": True, "model": "llama3.1",
             "total_duration": 1000000000, "eval_count": 20},
        ]

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(return_value=iter([
            json.dumps(c).encode("utf-8") + b"\n" for c in chunks
        ]))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            collected = "".join(client.generate_stream("Создай процедуру"))

        expected = 'Процедура Тест()\n    Сообщить("Hello");\nКонецПроцедуры'
        assert collected == expected
