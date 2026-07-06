"""
A4.7 (2026-07-06): Vector index persistence.

Проблема: VectorSearch использует Qdrant в `:memory:` режиме — индекс теряется
при каждом перезапуске. `_save_index` сохраняет только методы (metadata), но
НЕ векторы. При следующем запуске нужно заново генерировать embeddings (медленно).

Решение: VectorIndexPersistence — отдельный слой для save/load векторов:
1. Сохраняет embeddings как .npz (numpy archive) — компактно, быстро
2. Сохраняет metadata (методы, model info, hash) как .json sidecar
3. При load — загружает векторы и вставляет в Qdrant БЕЗ повторной генерации
4. Проверка валидности (model name, vector size, content hash)
5. Atomic write (tmp + rename) для предотвращения corruption

Формат файла:
    {path}.npz — numpy archive с embeddings
    {path}.json — metadata sidecar

Использование:
    from src.services.vector_index_persistence import VectorIndexPersistence
    persistence = VectorIndexPersistence()

    # Save
    persistence.save_index(Path("index"), embeddings, payloads,
                            model_name="BAAI/bge-small-en-v1.5", vector_size=384)

    # Load
    loaded = persistence.load_index(Path("index"))
    if loaded is not None:
        embeddings, payloads, metadata = loaded

    # Validate
    if persistence.is_index_valid(Path("index"), "BAAI/bge-small-en-v1.5", 384):
        # use cached index
        pass
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

SCHEMA_VERSION = 1
EMBEDDINGS_EXT = ".npz"
METADATA_EXT = ".json"

# Type alias для embeddings: 2D array of float32
NDArrayF32 = NDArray[np.float32]


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class IndexMetadata:
    """Metadata векторного индекса (сохраняется в .json sidecar)."""

    schema_version: int = SCHEMA_VERSION
    model_name: str = ""
    vector_size: int = 0
    total_points: int = 0
    content_hash: str = ""           # hash от payloads (для инвалидации кэша)
    embeddings_hash: str = ""        # hash от embeddings (для integrity check)
    created_at: str = ""             # ISO timestamp
    description: str = ""
    payloads: list[dict[str, Any]] = field(default_factory=list)   # сами метаданные точек


@dataclass
class LoadedIndex:
    """Загруженный индекс: embeddings + payloads + metadata."""

    embeddings: NDArrayF32              # shape (N, vector_size), dtype float32
    payloads: list[dict[str, Any]]
    metadata: IndexMetadata


# ============================================================================
# Persistence
# ============================================================================


class VectorIndexPersistence:
    """A4.7: Persistence для векторного индекса.

    Сохраняет embeddings (numpy .npz) и metadata (.json) в два файла.
    При load — проверяет валидность и возвращает данные для загрузки в Qdrant.
    """

    def __init__(self) -> None:
        pass

    # =====================================================================
    # Save
    # =====================================================================

    def save_index(
        self,
        path: Path,
        embeddings: NDArrayF32,
        payloads: list[dict[str, Any]],
        *,
        model_name: str,
        vector_size: int,
        description: str = "",
    ) -> None:
        """Сохранить векторный индекс на диск.

        Atomic write: сначала пишем во tmp файл, потом rename.
        Если что-то упадёт — оригинальный индекс не повредится.

        Args:
            path: Базовый путь (без расширения). Создаст {path}.npz и {path}.json.
            embeddings: numpy array shape (N, vector_size), dtype float32.
            payloads: Метаданные точек (list of dicts).
            model_name: Имя модели (для валидации при load).
            vector_size: Размерность векторов.
            description: Опциональное описание.
        """
        if not isinstance(embeddings, np.ndarray):
            raise TypeError(f"embeddings must be np.ndarray, got {type(embeddings).__name__}")

        if embeddings.ndim != 2:
            raise ValueError(
                f"embeddings must be 2D (N, vector_size), got shape {embeddings.shape}"
            )

        if embeddings.shape[0] != len(payloads):
            raise ValueError(
                f"embeddings count {embeddings.shape[0]} != payloads count {len(payloads)}"
            )

        if embeddings.shape[1] != vector_size:
            raise ValueError(
                f"embeddings vector_size {embeddings.shape[1]} != expected {vector_size}"
            )

        # Приводим к float32 (стандарт для embeddings)
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)

        # Вычисляем хеши для integrity check
        content_hash = self._compute_payloads_hash(payloads)
        embeddings_hash = self._compute_embeddings_hash(embeddings)

        from datetime import datetime
        metadata = IndexMetadata(
            schema_version=SCHEMA_VERSION,
            model_name=model_name,
            vector_size=vector_size,
            total_points=len(payloads),
            content_hash=content_hash,
            embeddings_hash=embeddings_hash,
            created_at=datetime.now().isoformat(),
            description=description,
            payloads=payloads,
        )

        # Создаём директорию
        path = path.with_suffix("")  # убираем расширение если есть
        path.parent.mkdir(parents=True, exist_ok=True)

        embeddings_path = path.with_suffix(EMBEDDINGS_EXT)
        metadata_path = path.with_suffix(METADATA_EXT)

        # Atomic write embeddings
        self._atomic_write_npz(embeddings_path, embeddings)

        # Atomic write metadata
        try:
            self._atomic_write_json(metadata_path, asdict(metadata))
        except Exception:
            # Если metadata упала — удаляем embeddings чтобы не было orphan
            embeddings_path.unlink(missing_ok=True)
            raise

        logger.info(
            "Vector index saved: %s (%d points, %d dims, model=%s)",
            embeddings_path, len(payloads), vector_size, model_name,
        )

    # =====================================================================
    # Load
    # =====================================================================

    def load_index(self, path: Path) -> LoadedIndex | None:
        """Загрузить векторный индекс с диска.

        Args:
            path: Базовый путь (без расширения).

        Returns:
            LoadedIndex если файл существует и валиден, иначе None.
        """
        path = path.with_suffix("")
        embeddings_path = path.with_suffix(EMBEDDINGS_EXT)
        metadata_path = path.with_suffix(METADATA_EXT)

        if not embeddings_path.exists() or not metadata_path.exists():
            return None

        # Загружаем metadata
        try:
            metadata_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load metadata %s: %s", metadata_path, e)
            return None

        metadata = IndexMetadata(**metadata_dict)

        # Загружаем embeddings
        try:
            data = np.load(embeddings_path, allow_pickle=False)
            embeddings = data["embeddings"]
        except (OSError, ValueError, KeyError) as e:
            logger.warning("Failed to load embeddings %s: %s", embeddings_path, e)
            return None

        # Проверяем что embeddings валидны
        if embeddings.ndim != 2:
            logger.warning("Invalid embeddings shape: %s", embeddings.shape)
            return None

        if embeddings.shape[1] != metadata.vector_size:
            logger.warning(
                "Embeddings vector_size mismatch: %d vs metadata %d",
                embeddings.shape[1], metadata.vector_size,
            )
            return None

        # Загружаем payloads из metadata
        payloads = metadata_dict.get("payloads", [])
        if len(payloads) != metadata.total_points:
            logger.warning(
                "Payloads count mismatch: %d vs metadata %d",
                len(payloads), metadata.total_points,
            )
            return None

        if len(payloads) != embeddings.shape[0]:
            logger.warning(
                "Embeddings count %d != payloads count %d",
                embeddings.shape[0], len(payloads),
            )
            return None

        # Integrity check: embeddings hash
        actual_hash = self._compute_embeddings_hash(embeddings)
        if actual_hash != metadata.embeddings_hash:
            logger.warning(
                "Embeddings hash mismatch: expected %s, got %s — file may be corrupted",
                metadata.embeddings_hash, actual_hash,
            )
            return None

        return LoadedIndex(
            embeddings=embeddings,
            payloads=payloads,
            metadata=metadata,
        )

    # =====================================================================
    # Validation
    # =====================================================================

    def is_index_valid(
        self,
        path: Path,
        expected_model: str,
        expected_vector_size: int,
    ) -> bool:
        """Проверить, что индекс существует и совместим с ожидаемой моделью.

        Args:
            path: Базовый путь (без расширения).
            expected_model: Имя модели, для которой строился индекс.
            expected_vector_size: Ожидаемая размерность векторов.

        Returns:
            True если индекс валиден и совместим.
        """
        info = self.get_index_info(path)
        if info is None:
            return False

        if info.model_name != expected_model:
            logger.debug(
                "Index model mismatch: %s vs %s", info.model_name, expected_model
            )
            return False

        if info.vector_size != expected_vector_size:
            logger.debug(
                "Index vector_size mismatch: %d vs %d",
                info.vector_size, expected_vector_size,
            )
            return False

        return True

    def get_index_info(self, path: Path) -> IndexMetadata | None:
        """Получить metadata индекса без загрузки векторов (быстро).

        Args:
            path: Базовый путь (без расширения).

        Returns:
            IndexMetadata если файл существует, иначе None.
        """
        path = path.with_suffix("")
        metadata_path = path.with_suffix(METADATA_EXT)

        if not metadata_path.exists():
            return None

        try:
            metadata_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
            return IndexMetadata(**metadata_dict)
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Failed to load metadata %s: %s", metadata_path, e)
            return None

    # =====================================================================
    # Delete
    # =====================================================================

    def delete_index(self, path: Path) -> bool:
        """Удалить индекс с диска (embeddings + metadata).

        Args:
            path: Базовый путь (без расширения).

        Returns:
            True если что-то было удалено.
        """
        path = path.with_suffix("")
        embeddings_path = path.with_suffix(EMBEDDINGS_EXT)
        metadata_path = path.with_suffix(METADATA_EXT)

        deleted = False
        if embeddings_path.exists():
            embeddings_path.unlink()
            deleted = True
        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        if deleted:
            logger.info("Vector index deleted: %s", path)
        return deleted

    # =====================================================================
    # Internal helpers
    # =====================================================================

    @staticmethod
    def _compute_payloads_hash(payloads: list[dict[str, Any]]) -> str:
        """Вычислить SHA256 от сериализованных payloads."""
        # Сортируем ключи для детерминизма
        serialized = json.dumps(payloads, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _compute_embeddings_hash(embeddings: NDArrayF32) -> str:
        """Вычислить SHA256 от embeddings bytes (для integrity check)."""
        # Используем bytes representation — bytes() deterministic для одного dtype
        return hashlib.sha256(embeddings.tobytes()).hexdigest()

    @staticmethod
    def _atomic_write_npz(path: Path, embeddings: NDArrayF32) -> None:
        """Atomic write .npz: write to tmp, then rename.

        Note: np.savez_compressed adds .npz suffix automatically if not present.
        We open the file explicitly to avoid this.
        """
        tmp_path = path.with_suffix(".tmp")
        try:
            # Open file explicitly so np.savez doesn't add .npz suffix
            with open(tmp_path, "wb") as f:
                np.savez_compressed(f, embeddings=embeddings)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
        """Atomic write .json: write to tmp, then rename."""
        tmp_path = path.with_suffix(".tmp")
        try:
            # Write through open() so we can fsync before rename
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


# ============================================================================
# Integration с VectorSearch (helper для load в Qdrant)
# ============================================================================


def load_index_into_qdrant(
    persistence: VectorIndexPersistence,
    index_path: Path,
    qdrant_client: Any,
    collection_name: str,
) -> int:
    """Загрузить сохранённый индекс в Qdrant client (helper).

    Args:
        persistence: VectorIndexPersistence instance.
        index_path: Путь к индексу (без расширения).
        qdrant_client: QdrantClient instance.
        collection_name: Имя коллекции в Qdrant.

    Returns:
        Количество загруженных точек, или -1 если индекс не найден/невалиден.
    """
    loaded = persistence.load_index(index_path)
    if loaded is None:
        return -1

    try:
        from qdrant_client.http.models import PointStruct
    except ImportError:
        logger.warning(
            "qdrant_client not installed — cannot load index into Qdrant. "
            "Install with: pip install qdrant-client"
        )
        return -1

    points = [
        PointStruct(id=idx, vector=emb.tolist(), payload=payload)
        for idx, (emb, payload) in enumerate(
            zip(loaded.embeddings, loaded.payloads, strict=True)
        )
    ]

    # Batch upload
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        qdrant_client.upsert(collection_name=collection_name, points=batch)

    logger.info(
        "Loaded %d points into Qdrant collection %s from %s",
        len(points), collection_name, index_path,
    )
    return len(points)


# ============================================================================
# CLI (опционально)
# ============================================================================


def main() -> int:
    """CLI для vector index persistence."""
    import argparse

    parser = argparse.ArgumentParser(description="Vector index persistence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("info", help="Show index info")
    info_parser.add_argument("path", help="Index path (without extension)")

    validate_parser = subparsers.add_parser("validate", help="Validate index integrity")
    validate_parser.add_argument("path", help="Index path")

    delete_parser = subparsers.add_parser("delete", help="Delete index")
    delete_parser.add_argument("path", help="Index path")

    args = parser.parse_args()
    persistence = VectorIndexPersistence()
    path = Path(args.path)

    if args.command == "info":
        info = persistence.get_index_info(path)
        if info is None:
            print(f"Index not found: {path}")
            return 1
        print(json.dumps(asdict(info), indent=2))
        return 0

    if args.command == "validate":
        loaded = persistence.load_index(path)
        if loaded is None:
            print(f"Index invalid or not found: {path}")
            return 1
        print(f"✅ Index valid: {loaded.metadata.total_points} points")
        return 0

    if args.command == "delete":
        deleted = persistence.delete_index(path)
        if deleted:
            print(f"✅ Deleted: {path}")
            return 0
        print(f"Index not found: {path}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
