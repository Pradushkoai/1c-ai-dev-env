"""
Тесты для векторного поиска (P1.1: search_vector.py).

Поскольку fastembed и qdrant-client могут быть не установлены в тестовом
окружении, тесты разделены на:
1. Тесты без зависимостей (is_available, fallback, статистика)
2. Тесты с моками fastembed и qdrant (build_index, search)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.search_vector import VectorSearch, _check_fastembed, _check_qdrant


# ============================================================================
# Тесты без зависимостей (is_available, fallback)
# ============================================================================


class TestVectorSearchAvailability:
    """Проверка доступности векторного поиска."""

    def test_is_available_returns_bool(self) -> None:
        """is_available() возвращает bool."""
        vs = VectorSearch()
        result = vs.is_available()
        assert isinstance(result, bool)

    def test_is_available_false_without_deps(self) -> None:
        """is_available() → False если fastembed/qdrant не установлены."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=False),
            patch("src.services.search_vector._check_qdrant", return_value=False),
        ):
            vs = VectorSearch()
            assert vs.is_available() is False

    def test_is_available_true_with_deps(self) -> None:
        """is_available() → True если обе зависимости установлены."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            assert vs.is_available() is True

    def test_is_available_false_with_only_fastembed(self) -> None:
        """is_available() → False если только fastembed установлен."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=False),
        ):
            vs = VectorSearch()
            assert vs.is_available() is False

    def test_is_available_false_with_only_qdrant(self) -> None:
        """is_available() → False если только qdrant установлен."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=False),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            assert vs.is_available() is False


class TestVectorSearchInit:
    """Проверка инициализации VectorSearch."""

    def test_init_with_default_model(self) -> None:
        """__init__ с default model_name."""
        vs = VectorSearch()
        assert vs._model_name == VectorSearch.MODEL_NAME
        assert vs._initialized is False
        assert vs._model is None
        assert vs._client is None

    def test_init_with_custom_model(self) -> None:
        """__init__ с custom model_name."""
        vs = VectorSearch(model_name="custom-model")
        assert vs._model_name == "custom-model"

    def test_ensure_initialized_raises_without_deps(self) -> None:
        """_ensure_initialized() → RuntimeError если зависимости не установлены."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=False),
            patch("src.services.search_vector._check_qdrant", return_value=False),
        ):
            vs = VectorSearch()
            with pytest.raises(RuntimeError, match="недоступен"):
                vs._ensure_initialized()


class TestVectorSearchStats:
    """Проверка get_stats()."""

    def test_get_stats_unavailable(self) -> None:
        """get_stats() когда векторный поиск недоступен."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=False),
            patch("src.services.search_vector._check_qdrant", return_value=False),
        ):
            vs = VectorSearch()
            stats = vs.get_stats()
            assert stats["available"] is False
            assert "reason" in stats

    def test_get_stats_available_not_initialized(self) -> None:
        """get_stats() когда доступен, но не инициализирован."""
        with (
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            stats = vs.get_stats()
            assert stats["available"] is True
            assert stats["model"] == VectorSearch.MODEL_NAME
            assert stats["collection_name"] == VectorSearch.COLLECTION_NAME
            assert stats["points_count"] == 0
            assert "note" in stats


# ============================================================================
# Тесты с моками fastembed и qdrant
# ============================================================================


def _mock_fastembed_module() -> tuple[MagicMock, MagicMock]:
    """Создать мок-модуль fastembed с TextEmbedding."""
    mock_embedding = MagicMock()
    mock_embedding.tolist.return_value = [0.1] * VectorSearch.VECTOR_SIZE

    mock_model = MagicMock()
    mock_model.embed.return_value = iter([mock_embedding])

    mock_module = MagicMock()
    mock_module.TextEmbedding = MagicMock(return_value=mock_model)
    return mock_module, mock_model


def _mock_qdrant_module() -> tuple[MagicMock, MagicMock]:
    """Создать мок-модуль qdrant_client с QdrantClient."""
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])

    mock_module = MagicMock()
    mock_module.QdrantClient = MagicMock(return_value=mock_client)
    return mock_module, mock_client


class TestVectorSearchBuildIndex:
    """Проверка build_index() с моками."""

    def test_build_index_with_mocks(self) -> None:
        """build_index() строит индекс с моками fastembed и qdrant."""
        import sys

        methods = [
            {
                "name_ru": "НайтиПоКоду",
                "name_en": "FindByCode",
                "syntax": "НайтиПоКоду(Код)",
                "description": "Находит элемент справочника по коду",
                "context": "Справочники",
            },
            {
                "name_ru": "СоздатьДокумент",
                "name_en": "CreateDocument",
                "syntax": "СоздатьДокумент()",
                "description": "Создаёт новый документ",
                "context": "Документы",
            },
        ]

        mock_fe_module, mock_model = _mock_fastembed_module()
        mock_qdrant_module, mock_client = _mock_qdrant_module()

        # Настраиваем embed для 2 методов
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [0.1] * VectorSearch.VECTOR_SIZE
        mock_model.embed.return_value = iter([mock_embedding, mock_embedding])

        with (
            patch.dict(
                sys.modules,
                {
                    "fastembed": mock_fe_module,
                    "qdrant_client": mock_qdrant_module,
                    "qdrant_client.http": MagicMock(),
                    "qdrant_client.http.models": MagicMock(),
                },
            ),
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            count = vs.build_index(methods)

        assert count == 2
        assert vs._initialized is True

    def test_build_index_saves_metadata(self, tmp_path: Path) -> None:
        """build_index() сохраняет metadata при указании index_path."""
        import sys

        methods = [
            {"name_ru": "Тест", "name_en": "Test", "description": "Test method", "context": ""},
        ]

        mock_fe_module, _ = _mock_fastembed_module()
        mock_qdrant_module, _ = _mock_qdrant_module()

        index_path = tmp_path / "vector-index.json"

        with (
            patch.dict(
                sys.modules,
                {
                    "fastembed": mock_fe_module,
                    "qdrant_client": mock_qdrant_module,
                    "qdrant_client.http": MagicMock(),
                    "qdrant_client.http.models": MagicMock(),
                },
            ),
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            vs.build_index(methods, index_path)

        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert data["version"] == 3
        assert data["algorithm"] == "vector"
        assert data["total_methods"] == 1


class TestVectorSearchSearch:
    """Проверка search() с моками."""

    def test_search_returns_results(self) -> None:
        """search() возвращает результаты с моками."""
        import sys

        mock_fe_module, _ = _mock_fastembed_module()
        mock_qdrant_module, mock_client = _mock_qdrant_module()

        # Мокаем результаты поиска Qdrant
        mock_hit = MagicMock()
        mock_hit.score = 0.95
        mock_hit.payload = {
            "name_ru": "НайтиПоКоду",
            "name_en": "FindByCode",
            "syntax": "НайтиПоКоду(Код)",
            "description": "Находит элемент по коду",
            "context": "Справочники",
        }
        mock_client.search.return_value = [mock_hit]

        with (
            patch.dict(
                sys.modules,
                {
                    "fastembed": mock_fe_module,
                    "qdrant_client": mock_qdrant_module,
                    "qdrant_client.http": MagicMock(),
                    "qdrant_client.http.models": MagicMock(),
                },
            ),
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            results = vs.search("найти элемент по коду", limit=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.95
        assert results[0]["name_ru"] == "НайтиПоКоду"
        assert results[0]["name_en"] == "FindByCode"

    def test_search_returns_empty_on_no_results(self) -> None:
        """search() возвращает пустой список если нет результатов."""
        import sys

        mock_fe_module, _ = _mock_fastembed_module()
        mock_qdrant_module, mock_client = _mock_qdrant_module()
        mock_client.search.return_value = []

        with (
            patch.dict(
                sys.modules,
                {
                    "fastembed": mock_fe_module,
                    "qdrant_client": mock_qdrant_module,
                    "qdrant_client.http": MagicMock(),
                    "qdrant_client.http.models": MagicMock(),
                },
            ),
            patch("src.services.search_vector._check_fastembed", return_value=True),
            patch("src.services.search_vector._check_qdrant", return_value=True),
        ):
            vs = VectorSearch()
            results = vs.search("несуществующий запрос", limit=5)

        assert results == []
