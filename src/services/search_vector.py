"""
search_vector.py — Векторный поиск по методам 1С через fastembed + Qdrant.

P1.1: добавлен как альтернатива BM25 для семантического поиска.
В отличие от BM25 (keyword matching), векторный поиск понимает смысл:
- "найти элемент по коду" → найдёт "НайтиПоКоду()" даже без точного совпадения слов
- "создать новый документ" → найдёт методы создания документов
- Устойчив к синонимам и перефразировкам

Архитектура:
- fastembed (BAAI/bge-small-en-v1.5) — генерация embeddings на CPU
- Qdrant (in-memory mode) — хранение и поиск векторов
- Lazy import: если fastembed/qdrant не установлены → graceful fallback

Использование:
    from src.services.search_vector import VectorSearch

    vs = VectorSearch()  # lazy init fastembed + Qdrant
    if vs.is_available():
        vs.build_index(methods, index_path)
        results = vs.search("найти элемент по коду", limit=5)
    else:
        # fallback на BM25
        from src.services.search_bm25 import search_bm25
        results = search_bm25(index_path, query, limit)

Зависимости (extras [rag]):
    pip install -e ".[rag]"
    → fastembed, qdrant-client
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports — fastembed и qdrant тяжелые, импортируем только при использовании
_FASTEMBED_AVAILABLE: bool | None = None
_QDRANT_AVAILABLE: bool | None = None


def _check_fastembed() -> bool:
    """Проверить доступность fastembed (с кэшированием)."""
    global _FASTEMBED_AVAILABLE
    if _FASTEMBED_AVAILABLE is None:
        try:
            import fastembed  # noqa: F401

            _FASTEMBED_AVAILABLE = True
        except ImportError:
            _FASTEMBED_AVAILABLE = False
            logger.debug("fastembed не установлен. pip install fastembed для векторного поиска.")
    return _FASTEMBED_AVAILABLE


def _check_qdrant() -> bool:
    """Проверить доступность qdrant-client (с кэшированием)."""
    global _QDRANT_AVAILABLE
    if _QDRANT_AVAILABLE is None:
        try:
            from qdrant_client import QdrantClient  # noqa: F401

            _QDRANT_AVAILABLE = True
        except ImportError:
            _QDRANT_AVAILABLE = False
            logger.debug("qdrant-client не установлен. pip install qdrant-client для векторного поиска.")
    return _QDRANT_AVAILABLE


class VectorSearch:
    """Векторный поиск по методам 1С через fastembed + Qdrant.

    Lazy initialization: fastembed и Qdrant загружаются только при первом
    использовании. Если зависимости не установлены — is_available() вернёт False.

    Attributes:
        model: fastembed TextEmbedding модель
        client: QdrantClient (in-memory mode)
        collection_name: имя коллекции в Qdrant
    """

    # Модель для embeddings: BAAI/bge-small-en-v1.5 (мультиязычная, ~130MB)
    # Альтернативы: BAAI/bge-base-en-v1.5 (точнее, ~440MB)
    MODEL_NAME = "BAAI/bge-small-en-v1.5"
    COLLECTION_NAME = "1c_methods"
    VECTOR_SIZE = 384  # размерность bge-small-en-v1.5

    def __init__(self, model_name: str | None = None) -> None:
        """Инициализация VectorSearch (lazy — модель загружается при первом search/build).

        Args:
            model_name: Имя модели fastembed. Если None — используется MODEL_NAME.
        """
        self._model_name = model_name or self.MODEL_NAME
        self._model: Any = None  # fastembed.TextEmbedding
        self._client: Any = None  # QdrantClient
        self._initialized = False

    def is_available(self) -> bool:
        """Проверить, доступны ли fastembed и qdrant-client.

        Returns:
            True если обе зависимости установлены и векторный поиск возможен.
        """
        return _check_fastembed() and _check_qdrant()

    def _ensure_initialized(self) -> None:
        """Lazy init: загрузить модель и создать Qdrant client при первом вызове."""
        if self._initialized:
            return

        if not self.is_available():
            raise RuntimeError(
                "Векторный поиск недоступен: fastembed или qdrant-client не установлены. "
                "Установите: pip install -e '.[rag]'"
            )

        # Lazy import
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        logger.info("Загрузка модели fastembed: %s", self._model_name)
        self._model = TextEmbedding(model_name=self._model_name)

        # In-memory Qdrant (без Docker, без сервера)
        self._client = QdrantClient(":memory:")

        # Создаём коллекцию если не существует
        collections = self._client.get_collections().collections
        collection_names = [c.name for c in collections]
        if self.COLLECTION_NAME not in collection_names:
            self._client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Создана Qdrant коллекция: %s", self.COLLECTION_NAME)

        self._initialized = True

    def build_index(self, methods: list[dict], index_path: Path | None = None) -> int:
        """Построить векторный индекс по методам 1С.

        Args:
            methods: Список методов платформы 1С.
                Каждый метод: {name_ru, name_en, syntax, description, context}
            index_path: Путь для сохранения индекса (опционально).
                Если None — индекс хранится только в памяти Qdrant.

        Returns:
            Количество проиндексированных методов.
        """
        self._ensure_initialized()

        from qdrant_client.http.models import PointStruct

        # Очищаем коллекцию перед переиндексацией
        self._client.delete(collection_name=self.COLLECTION_NAME, points_selector=None)
        self._client.recreate_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config={"size": self.VECTOR_SIZE, "distance": "Cosine"},
        )

        # Подготавливаем тексты для embeddings
        texts: list[str] = []
        payloads: list[dict] = []
        for method in methods:
            # Комбинируем поля для embedding
            text_parts = [
                method.get("name_ru", ""),
                method.get("name_en", ""),
                method.get("description", ""),
                method.get("context", ""),
            ]
            text = " ".join(p for p in text_parts if p)
            texts.append(text)
            payloads.append(method)

        # Генерируем embeddings (batch)
        logger.info("Генерация embeddings для %d методов...", len(texts))
        embeddings = list(self._model.embed(texts))

        # Загружаем в Qdrant
        points = [
            PointStruct(id=idx, vector=emb.tolist(), payload=payload)
            for idx, (emb, payload) in enumerate(zip(embeddings, payloads, strict=True))
        ]

        # Batch upload (по 100 точек за раз)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(collection_name=self.COLLECTION_NAME, points=batch)

        logger.info("Векторный индекс построен: %d методов", len(points))

        # Опционально сохраняем индекс на диск
        if index_path:
            self._save_index(methods, index_path)
            # A4.7: также сохраняем embeddings для быстрого восстановления
            self._save_embeddings(index_path, embeddings, payloads)

        return len(points)

    def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """Векторный поиск по методам 1С.

        Args:
            query: Поисковый запрос (на естественном языке).
            limit: Максимум результатов.
            score_threshold: Минимальный score (0.0 — вернуть все).

        Returns:
            Список: [{score, name_ru, name_en, syntax, description, context}, ...]
            Отсортирован по убыванию score.
        """
        self._ensure_initialized()

        # Генерируем embedding для запроса
        query_embedding = list(self._model.embed([query]))[0]

        # Поиск в Qdrant
        search_results = self._client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            limit=limit,
            score_threshold=score_threshold,
        )

        results: list[dict] = []
        for hit in search_results:
            payload = hit.payload or {}
            results.append(
                {
                    "score": float(hit.score),
                    "name_ru": payload.get("name_ru", ""),
                    "name_en": payload.get("name_en", ""),
                    "syntax": payload.get("syntax", ""),
                    "description": payload.get("description", ""),
                    "context": payload.get("context", ""),
                }
            )

        return results

    def _save_index(self, methods: list[dict], index_path: Path) -> None:
        """Сохранить список методов в JSON (для последующей переиндексации).

        Векторный индекс хранится в памяти Qdrant и не сериализуется.
        Этот метод сохраняет исходные методы, чтобы при следующем запуске
        можно было быстро пересоздать индекс через build_index().
        """
        index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 3,  # v3 = vector index metadata
            "algorithm": "vector",
            "model": self._model_name,
            "vector_size": self.VECTOR_SIZE,
            "total_methods": len(methods),
            "methods": methods,
        }
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Векторный индекс metadata сохранён: %s", index_path)

    # =====================================================================
    # A4.7: Vector index persistence
    # =====================================================================

    def _save_embeddings(
        self,
        index_path: Path,
        embeddings: list[Any],
        payloads: list[dict],
    ) -> None:
        """A4.7: Сохранить embeddings через VectorIndexPersistence.

        Args:
            index_path: Базовый путь (тот же что и для _save_index).
            embeddings: Список векторов (от fastembed).
            payloads: Метаданные точек.

        Note:
            Persistence — это optimization, не должна ломать build_index.
            Если что-то не так с embeddings (mock, нестандартный тип) — логируем
            warning и пропускаем save.
        """
        try:
            import numpy as np

            from src.services.vector_index_persistence import VectorIndexPersistence

            persistence = VectorIndexPersistence()

            # Конвертируем list of arrays в единый numpy array
            emb_array = np.array([np.asarray(emb, dtype=np.float32) for emb in embeddings])

            # Путь для persistence — добавляем суффикс _vectors, чтобы не конфликтовать
            # с _save_index (который пишет methods.json)
            vectors_path = index_path.parent / (index_path.name + "_vectors")

            persistence.save_index(
                vectors_path,
                emb_array,
                payloads,
                model_name=self._model_name,
                vector_size=self.VECTOR_SIZE,
                description=f"1C methods vector index, {len(payloads)} points",
            )
        except (ValueError, TypeError) as e:
            # Persistence не должна ломать build_index
            logger.warning("Failed to save embeddings for persistence: %s", e)

    def load_or_build_index(
        self,
        methods: list[dict],
        index_path: Path,
    ) -> int:
        """A4.7: Загрузить индекс с диска или построить заново если невалиден.

        Алгоритм:
        1. Проверить есть ли сохранённый индекс (vectors.npz + vectors.json)
        2. Если есть и валиден — загрузить embeddings в Qdrant (БЕЗ генерации)
        3. Если нет или невалиден — построить заново через build_index()

        Это даёт 10-100× ускорение при повторных запусках.

        Args:
            methods: Список методов (используется только если нужно rebuild).
            index_path: Путь к индексу.

        Returns:
            Количество проиндексированных методов.
        """
        from src.services.vector_index_persistence import (
            VectorIndexPersistence,
            load_index_into_qdrant,
        )

        self._ensure_initialized()

        persistence = VectorIndexPersistence()
        vectors_path = index_path.parent / (index_path.name + "_vectors")

        # Check if cached index exists and is valid
        if persistence.is_index_valid(vectors_path, self._model_name, self.VECTOR_SIZE):
            logger.info("Загрузка векторного индекса из кэша: %s", vectors_path)
            count = load_index_into_qdrant(
                persistence, vectors_path, self._client, self.COLLECTION_NAME
            )
            if count > 0:
                logger.info("Векторный индекс загружен из кэша: %d методов", count)
                return count
            logger.warning("load_index_into_qdrant вернул 0 — rebuild")

        # Fallback: build from scratch
        logger.info("Кэш невалиден — rebuild векторного индекса с нуля")
        return self.build_index(methods, index_path)

    def is_index_cached(self, index_path: Path) -> bool:
        """A4.7: Проверить, есть ли валидный кэш индекса на диске.

        Args:
            index_path: Путь к индексу.

        Returns:
            True если кэш существует и совместим с текущей моделью.
        """
        from src.services.vector_index_persistence import VectorIndexPersistence

        persistence = VectorIndexPersistence()
        vectors_path = index_path.parent / (index_path.name + "_vectors")
        return persistence.is_index_valid(vectors_path, self._model_name, self.VECTOR_SIZE)

    def get_stats(self) -> dict[str, Any]:
        """Статистика векторного индекса.

        Returns:
            {available, model, collection_name, points_count}
        """
        if not self.is_available():
            return {
                "available": False,
                "reason": "fastembed или qdrant-client не установлены",
            }

        stats: dict[str, Any] = {
            "available": True,
            "model": self._model_name,
            "collection_name": self.COLLECTION_NAME,
            "vector_size": self.VECTOR_SIZE,
        }

        if self._initialized:
            try:
                count = self._client.count(collection_name=self.COLLECTION_NAME)
                stats["points_count"] = count.count
            except Exception as e:
                stats["points_count"] = -1
                stats["error"] = str(e)
        else:
            stats["points_count"] = 0
            stats["note"] = "Индекс не инициализирован (lazy init)"

        return stats


def build_vector_index_from_bm25(bm25_index_path: Path, vector_index_path: Path | None = None) -> int:
    """Построить векторный индекс из существующего BM25 индекса.

    Удобная функция для миграции: берёт методы из BM25 индекса
    и строит по ним векторный индекс.

    Args:
        bm25_index_path: Путь к BM25 индексу (fast-search-index.json).
        vector_index_path: Путь для сохранения векторного индекса metadata.

    Returns:
        Количество проиндексированных методов, или -1 если векторный поиск недоступен.
    """
    vs = VectorSearch()
    if not vs.is_available():
        logger.warning("Векторный поиск недоступен — пропуск build_vector_index")
        return -1

    # Загружаем методы из BM25 индекса
    with open(bm25_index_path, encoding="utf-8") as f:
        bm25_index = json.load(f)

    methods = bm25_index.get("methods", [])
    return vs.build_index(methods, vector_index_path)
