"""
A4.7 (2026-07-06): Тесты для vector index persistence.

Покрывает:
- save_index: atomic write, validation (shape, dtype, count)
- load_index: round-trip, integrity check (hash mismatch)
- is_index_valid: model mismatch, vector_size mismatch
- get_index_info: fast metadata read
- delete_index: cleanup
- Edge cases: empty index, large index, corrupt file
- Integration с VectorSearch (mocked, без fastembed)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.services.vector_index_persistence import (
    SCHEMA_VERSION,
    IndexMetadata,
    LoadedIndex,
    VectorIndexPersistence,
    load_index_into_qdrant,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def persistence() -> VectorIndexPersistence:
    return VectorIndexPersistence()


@pytest.fixture
def sample_embeddings() -> np.ndarray:
    """10 векторов размерности 8 (детерминированные)."""
    np.random.seed(42)
    return np.random.rand(10, 8).astype(np.float32)


@pytest.fixture
def sample_payloads() -> list[dict]:
    """10 payloads (методов 1С)."""
    return [
        {
            "name_ru": f"Метод{i}",
            "name_en": f"Method{i}",
            "description": f"Описание метода {i}",
            "context": "Справочник",
        }
        for i in range(10)
    ]


# ============================================================================
# IndexMetadata dataclass tests
# ============================================================================


class TestIndexMetadata:
    def test_defaults(self) -> None:
        meta = IndexMetadata()
        assert meta.schema_version == SCHEMA_VERSION
        assert meta.model_name == ""
        assert meta.vector_size == 0
        assert meta.total_points == 0
        assert meta.payloads == []

    def test_with_values(self) -> None:
        meta = IndexMetadata(
            model_name="BAAI/bge-small-en-v1.5",
            vector_size=384,
            total_points=100,
        )
        assert meta.model_name == "BAAI/bge-small-en-v1.5"
        assert meta.vector_size == 384
        assert meta.total_points == 100


# ============================================================================
# save_index tests
# ============================================================================


class TestSaveIndex:
    def test_save_creates_two_files(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Save создаёт .npz и .json файлы."""
        path = tmp_path / "index"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="test-model", vector_size=8,
        )
        assert (tmp_path / "index.npz").exists()
        assert (tmp_path / "index.json").exists()

    def test_save_creates_parent_dirs(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Save создаёт родительские директории."""
        path = tmp_path / "deep" / "nested" / "index"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        assert (tmp_path / "deep" / "nested" / "index.npz").exists()

    def test_save_invalid_embeddings_type(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_payloads: list[dict],
    ) -> None:
        """Save с не-numpy типом падает."""
        with pytest.raises(TypeError, match="np.ndarray"):
            persistence.save_index(
                tmp_path / "x", [[1, 2], [3, 4]], sample_payloads[:2],
                model_name="m", vector_size=2,
            )

    def test_save_invalid_ndim(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_payloads: list[dict],
    ) -> None:
        """Save с 1D массивом падает."""
        with pytest.raises(ValueError, match="2D"):
            persistence.save_index(
                tmp_path / "x", np.array([1.0, 2.0, 3.0]),
                sample_payloads[:3],
                model_name="m", vector_size=3,
            )

    def test_save_count_mismatch(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Save с mismatched count падает."""
        with pytest.raises(ValueError, match="count"):
            persistence.save_index(
                tmp_path / "x", sample_embeddings,
                payloads=[{"a": 1}],   # 1 payload vs 10 embeddings
                model_name="m", vector_size=8,
            )

    def test_save_vector_size_mismatch(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Save с неверным vector_size падает."""
        with pytest.raises(ValueError, match="vector_size"):
            persistence.save_index(
                tmp_path / "x", sample_embeddings, sample_payloads,
                model_name="m", vector_size=16,   # actual is 8
            )

    def test_save_converts_to_float32(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_payloads: list[dict],
    ) -> None:
        """Save конвертирует float64 в float32."""
        emb_float64 = np.random.rand(5, 4).astype(np.float64)
        persistence.save_index(
            tmp_path / "x", emb_float64, sample_payloads[:5],
            model_name="m", vector_size=4,
        )
        # Load and check dtype
        loaded = persistence.load_index(tmp_path / "x")
        assert loaded is not None
        assert loaded.embeddings.dtype == np.float32

    def test_save_includes_payloads_in_metadata(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Metadata содержит payloads для последующей загрузки."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        meta = json.loads((tmp_path / "x.json").read_text(encoding="utf-8"))
        assert "payloads" in meta
        assert len(meta["payloads"]) == 10
        assert meta["payloads"][0]["name_ru"] == "Метод0"


# ============================================================================
# load_index tests
# ============================================================================


class TestLoadIndex:
    def test_load_returns_loaded_index(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Load возвращает LoadedIndex с embeddings, payloads, metadata."""
        path = tmp_path / "idx"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="test-model", vector_size=8,
        )
        loaded = persistence.load_index(path)
        assert loaded is not None
        assert isinstance(loaded, LoadedIndex)
        assert isinstance(loaded.embeddings, np.ndarray)
        assert isinstance(loaded.payloads, list)
        assert isinstance(loaded.metadata, IndexMetadata)

    def test_load_round_trip(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Round-trip: save → load даёт те же данные."""
        path = tmp_path / "idx"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        loaded = persistence.load_index(path)
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded.embeddings, sample_embeddings)
        assert loaded.payloads == sample_payloads
        assert loaded.metadata.model_name == "m"
        assert loaded.metadata.vector_size == 8
        assert loaded.metadata.total_points == 10

    def test_load_missing_file_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """Load несуществующего индекса → None."""
        assert persistence.load_index(tmp_path / "nope") is None

    def test_load_missing_metadata_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Load если metadata отсутствует → None."""
        # Создаём только .npz, без .json
        np.savez(tmp_path / "x.npz", embeddings=sample_embeddings)
        assert persistence.load_index(tmp_path / "x") is None

    def test_load_corrupt_metadata_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Load с повреждённым .json → None."""
        np.savez(tmp_path / "x.npz", embeddings=sample_embeddings)
        (tmp_path / "x.json").write_text("not json", encoding="utf-8")
        assert persistence.load_index(tmp_path / "x") is None

    def test_load_corrupt_embeddings_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Load с повреждённым .npz → None."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        # Corrupt the .npz
        (tmp_path / "x.npz").write_text("corrupt", encoding="utf-8")
        assert persistence.load_index(tmp_path / "x") is None

    def test_load_hash_mismatch_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Load с неверным embeddings_hash → None (corruption detected)."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        # Modify embeddings file directly
        data = np.load(tmp_path / "x.npz")
        emb = data["embeddings"]
        emb[0, 0] = 999.0   # corrupt
        np.savez(tmp_path / "x.npz", embeddings=emb)
        # Hash mismatch should be detected
        assert persistence.load_index(tmp_path / "x") is None


# ============================================================================
# is_index_valid tests
# ============================================================================


class TestIsValid:
    def test_valid_index(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Валидный индекс с совпадающей моделью → True."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m1", vector_size=8,
        )
        assert persistence.is_index_valid(tmp_path / "x", "m1", 8)

    def test_model_mismatch(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Другая модель → False."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m1", vector_size=8,
        )
        assert not persistence.is_index_valid(tmp_path / "x", "m2", 8)

    def test_vector_size_mismatch(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Другая размерность → False."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        assert not persistence.is_index_valid(tmp_path / "x", "m", 16)

    def test_missing_index(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """Несуществующий индекс → False."""
        assert not persistence.is_index_valid(tmp_path / "nope", "m", 8)


# ============================================================================
# get_index_info tests
# ============================================================================


class TestGetIndexInfo:
    def test_info_returns_metadata(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """get_index_info возвращает metadata без загрузки векторов."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
            description="test index",
        )
        info = persistence.get_index_info(tmp_path / "x")
        assert info is not None
        assert info.model_name == "m"
        assert info.vector_size == 8
        assert info.total_points == 10
        assert info.description == "test index"
        assert info.content_hash  # not empty
        assert info.embeddings_hash  # not empty
        assert info.created_at  # not empty

    def test_info_missing_returns_none(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        assert persistence.get_index_info(tmp_path / "nope") is None

    def test_info_does_not_load_embeddings(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """get_index_info НЕ загружает векторы (быстро)."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        # Delete embeddings file — info should still work
        (tmp_path / "x.npz").unlink()
        info = persistence.get_index_info(tmp_path / "x")
        assert info is not None  # metadata still readable


# ============================================================================
# delete_index tests
# ============================================================================


class TestDeleteIndex:
    def test_delete_removes_both_files(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        assert persistence.delete_index(tmp_path / "x") is True
        assert not (tmp_path / "x.npz").exists()
        assert not (tmp_path / "x.json").exists()

    def test_delete_missing_returns_false(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        assert persistence.delete_index(tmp_path / "nope") is False

    def test_delete_only_embeddings(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Delete работает если только .npz существует."""
        np.savez(tmp_path / "x.npz", embeddings=sample_embeddings)
        assert persistence.delete_index(tmp_path / "x") is True
        assert not (tmp_path / "x.npz").exists()


# ============================================================================
# Atomic write tests
# ============================================================================


class TestAtomicWrite:
    def test_no_tmp_file_left_on_success(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """После успешного save нет .tmp файлов."""
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        assert not list(tmp_path.glob("*.tmp"))

    def test_overwrite_existing(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """Перезапись существующего индекса работает."""
        path = tmp_path / "x"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        # Overwrite with new data
        new_emb = np.random.rand(10, 8).astype(np.float32)
        persistence.save_index(
            path, new_emb, sample_payloads,
            model_name="m", vector_size=8,
        )
        loaded = persistence.load_index(path)
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded.embeddings, new_emb)


# ============================================================================
# Hash computation tests
# ============================================================================


class TestHashComputation:
    def test_payloads_hash_deterministic(
        self, persistence: VectorIndexPersistence, sample_payloads: list[dict]
    ) -> None:
        """Hash от одинаковых payloads одинаковый."""
        h1 = persistence._compute_payloads_hash(sample_payloads)
        h2 = persistence._compute_payloads_hash(sample_payloads)
        assert h1 == h2

    def test_payloads_hash_differs_for_different(
        self, persistence: VectorIndexPersistence
    ) -> None:
        """Hash от разных payloads разный."""
        h1 = persistence._compute_payloads_hash([{"a": 1}])
        h2 = persistence._compute_payloads_hash([{"a": 2}])
        assert h1 != h2

    def test_payloads_hash_order_independent(
        self, persistence: VectorIndexPersistence
    ) -> None:
        """Hash не зависит от порядка ключей в dict."""
        h1 = persistence._compute_payloads_hash([{"a": 1, "b": 2}])
        h2 = persistence._compute_payloads_hash([{"b": 2, "a": 1}])
        assert h1 == h2  # sort_keys=True в json.dumps

    def test_embeddings_hash_deterministic(
        self,
        persistence: VectorIndexPersistence,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Hash от одинаковых embeddings одинаковый."""
        h1 = persistence._compute_embeddings_hash(sample_embeddings)
        h2 = persistence._compute_embeddings_hash(sample_embeddings.copy())
        assert h1 == h2

    def test_embeddings_hash_differs(
        self,
        persistence: VectorIndexPersistence,
        sample_embeddings: np.ndarray,
    ) -> None:
        """Hash от разных embeddings разный."""
        h1 = persistence._compute_embeddings_hash(sample_embeddings)
        modified = sample_embeddings.copy()
        modified[0, 0] = 999.0
        h2 = persistence._compute_embeddings_hash(modified)
        assert h1 != h2


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_index(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """Пустой индекс (0 точек) — валидный case."""
        empty_emb = np.zeros((0, 8), dtype=np.float32)
        persistence.save_index(
            tmp_path / "x", empty_emb, [],
            model_name="m", vector_size=8,
        )
        loaded = persistence.load_index(tmp_path / "x")
        assert loaded is not None
        assert loaded.embeddings.shape == (0, 8)
        assert loaded.payloads == []
        assert loaded.metadata.total_points == 0

    def test_single_point(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """Индекс с 1 точкой."""
        emb = np.random.rand(1, 4).astype(np.float32)
        persistence.save_index(
            tmp_path / "x", emb, [{"name": "single"}],
            model_name="m", vector_size=4,
        )
        loaded = persistence.load_index(tmp_path / "x")
        assert loaded is not None
        assert loaded.metadata.total_points == 1

    def test_large_index(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """Индекс с 1000 точек (compression check)."""
        np.random.seed(123)
        emb = np.random.rand(1000, 16).astype(np.float32)
        payloads = [{"id": i} for i in range(1000)]
        persistence.save_index(
            tmp_path / "x", emb, payloads,
            model_name="m", vector_size=16,
        )
        loaded = persistence.load_index(tmp_path / "x")
        assert loaded is not None
        assert loaded.metadata.total_points == 1000
        np.testing.assert_array_almost_equal(loaded.embeddings, emb)


# ============================================================================
# Integration: load_index_into_qdrant (mocked)
# ============================================================================


class TestLoadIntoQdrant:
    def test_load_into_qdrant_returns_count(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """load_index_into_qdrant загружает точки в Qdrant."""
        path = tmp_path / "x"
        persistence.save_index(
            path, sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )

        # Mock QdrantClient
        mock_client = MagicMock()
        mock_client.upsert = MagicMock()

        count = load_index_into_qdrant(persistence, path, mock_client, "test_collection")
        assert count == 10
        # upsert called multiple times (batch_size=100, 10 points = 1 batch)
        assert mock_client.upsert.call_count >= 1

    def test_load_into_qdrant_missing_index_returns_minus_one(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
    ) -> None:
        """load_index_into_qdrant с несуществующим индексом → -1."""
        mock_client = MagicMock()
        count = load_index_into_qdrant(
            persistence, tmp_path / "nope", mock_client, "coll"
        )
        assert count == -1
        mock_client.upsert.assert_not_called()


# ============================================================================
# Integration с VectorSearch (mocked fastembed)
# ============================================================================


class TestVectorSearchIntegration:
    """Тесты что VectorSearch использует persistence (mocked)."""

    def test_is_index_cached_false_when_no_cache(
        self, tmp_path: Path
    ) -> None:
        """is_index_cached=False когда нет кэша."""
        from src.services.search_vector import VectorSearch
        vs = VectorSearch()
        # is_index_cached не требует fastembed
        assert vs.is_index_cached(tmp_path / "nope") is False

    def test_save_embeddings_called_on_build(
        self,
        tmp_path: Path,
        sample_payloads: list[dict],
    ) -> None:
        """build_index вызывает _save_embeddings (если fastembed available)."""
        from src.services.search_vector import VectorSearch
        vs = VectorSearch()
        # Mock _save_embeddings чтобы проверить вызов
        with patch.object(vs, "_save_embeddings") as mock_save, \
             patch.object(vs, "_ensure_initialized"), \
             patch.object(vs, "_save_index"), \
             patch.object(vs, "_client"), \
             patch("src.services.search_vector.VectorSearch.MODEL_NAME", "test"):
            # Mock model.embed
            vs._model = MagicMock()
            vs._model.embed = MagicMock(
                return_value=[np.random.rand(8).astype(np.float32) for _ in sample_payloads]
            )
            vs._client = MagicMock()

            vs.build_index(sample_payloads, tmp_path / "idx")
            mock_save.assert_called_once()

    def test_load_or_build_uses_cache_if_valid(
        self,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        """load_or_build_index использует кэш если валиден."""
        from src.services.search_vector import VectorSearch
        from src.services.vector_index_persistence import VectorIndexPersistence

        # Pre-create cached index with VectorSearch's actual model & vector_size
        persistence = VectorIndexPersistence()
        vectors_path = tmp_path / "idx_vectors"

        # Generate embeddings matching VectorSearch.VECTOR_SIZE (384)
        np.random.seed(42)
        matching_emb = np.random.rand(10, VectorSearch.VECTOR_SIZE).astype(np.float32)

        persistence.save_index(
            vectors_path, matching_emb, sample_payloads,
            model_name=VectorSearch.MODEL_NAME, vector_size=VectorSearch.VECTOR_SIZE,
        )

        vs = VectorSearch()
        # Mock _ensure_initialized and _client
        with patch.object(vs, "_ensure_initialized"), \
             patch.object(vs, "_client") as mock_client, \
             patch.object(vs, "build_index") as mock_build:
            mock_client.upsert = MagicMock()
            count = vs.load_or_build_index(sample_payloads, tmp_path / "idx")
            assert count == 10
            mock_build.assert_not_called()  # didn't fall back to rebuild

    def test_load_or_build_falls_back_to_build(
        self,
        tmp_path: Path,
        sample_payloads: list[dict],
    ) -> None:
        """load_or_build_index rebuilds если кэш невалиден."""
        from src.services.search_vector import VectorSearch
        vs = VectorSearch()
        with patch.object(vs, "_ensure_initialized"), \
             patch.object(vs, "build_index", return_value=42) as mock_build:
            count = vs.load_or_build_index(sample_payloads, tmp_path / "idx")
            assert count == 42
            mock_build.assert_called_once()


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_info_on_missing(self, tmp_path: Path, capsys) -> None:
        from src.services.vector_index_persistence import main
        import sys
        sys.argv = ["vip", "info", str(tmp_path / "nope")]
        rc = main()
        assert rc == 1

    def test_cli_info_on_existing(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
        capsys,
    ) -> None:
        from src.services.vector_index_persistence import main
        import sys
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        sys.argv = ["vip", "info", str(tmp_path / "x")]
        rc = main()
        assert rc == 0

    def test_cli_delete(
        self,
        persistence: VectorIndexPersistence,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_payloads: list[dict],
    ) -> None:
        from src.services.vector_index_persistence import main
        import sys
        persistence.save_index(
            tmp_path / "x", sample_embeddings, sample_payloads,
            model_name="m", vector_size=8,
        )
        sys.argv = ["vip", "delete", str(tmp_path / "x")]
        rc = main()
        assert rc == 0
        assert not (tmp_path / "x.npz").exists()
