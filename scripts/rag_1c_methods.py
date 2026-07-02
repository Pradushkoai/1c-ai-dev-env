#!/usr/bin/env python3
"""
RAG-система для семантического поиска по методам 1С.

Использует:
- fastembed для embeddings (легковесный, на ONNX, без PyTorch)
- qdrant-client для векторного поиска (локальный режим, без docker)

Индексирует методы 1С из syntax-helper-index.json и позволяет
находить методы по семантическому описанию, а не только по имени.

Пример:
  python3 rag_1c_methods.py build    # построить индекс (один раз)
  python3 rag_1c_methods.py search "найти элемент справочника по коду"
"""

import json
import os
import sys

try:
    from fastembed import TextEmbedding
except ImportError:
    sys.exit('Этот скрипт требует опциональные зависимости: pip install -e ".[rag]"')
from pathlib import Path

# Пути
PROJECT_DIR = "/home/z/my-project"
METHODS_JSON = f"{PROJECT_DIR}/indexes/syntax-helper-index.json"
QDRANT_PATH = f"{PROJECT_DIR}/indexes/rag_qdrant"  # локальное файловое хранилище
COLLECTION_NAME = "1c_methods"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # лёгкая модель, ~130 МБ


def build_index():
    """Построить векторный индекс всех методов 1С."""
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    print(f"Загружаю методы из {METHODS_JSON}...")
    with open(METHODS_JSON, encoding="utf-8") as f:
        methods = json.load(f)

    print(f"Загружено {len(methods)} методов")

    # Подготовим тексты для embeddings — объединим имя, контекст, синтаксис, описание
    texts = []
    for i, m in enumerate(methods):
        name_ru = m.get("name_ru", "")
        name_en = m.get("name_en", "")
        context = m.get("context", "")
        syntax = m.get("syntax", "")
        description = m.get("description", "")
        returns = m.get("returns", "")

        # Формируем текст для embedding
        text = f"{name_ru} ({name_en}) | {context} | {syntax} | {description[:200]} | Returns: {returns[:100]}"
        texts.append(text)

    print(f"Инициализирую модель embeddings: {EMBEDDING_MODEL}...")
    model = TextEmbedding(EMBEDDING_MODEL)

    print(f"Генерирую embeddings для {len(texts)} методов...", flush=True)
    # Генерируем батчами — маленький размер для стабильности
    embeddings = []
    batch_size = 32  # меньше = стабильнее
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            batch_embeddings = list(model.embed(batch))
            embeddings.extend(batch_embeddings)
            done = min(i + batch_size, len(texts))
            if done % 100 == 0 or done == len(texts):
                print(f"  Прогресс: {done}/{len(texts)} ({100 * done // len(texts)}%)", flush=True)
        except Exception as e:
            print(f"  Ошибка на батче {i}: {e}", flush=True)
            # Добавляем пустые embeddings чтобы сохранить индексы
            embeddings.extend([None] * len(batch))

    print("Создаю Qdrant коллекцию...")
    # Удаляем старую БД если есть
    if os.path.exists(QDRANT_PATH):
        import shutil

        shutil.rmtree(QDRANT_PATH)

    client = QdrantClient(path=QDRANT_PATH)

    # Создаём коллекцию
    vector_size = len(embeddings[0])
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    # Загружаем точки батчами
    print(f"Загружаю {len(methods)} точек в Qdrant...")
    points_batch = []
    for i, (method, embedding) in enumerate(zip(methods, embeddings)):
        point = PointStruct(
            id=i,
            vector=embedding.tolist(),
            payload={
                "name_ru": method.get("name_ru", ""),
                "name_en": method.get("name_en", ""),
                "context": method.get("context", ""),
                "syntax": method.get("syntax", ""),
                "description": method.get("description", ""),
                "returns": method.get("returns", ""),
                "availability": method.get("availability", ""),
                "file": method.get("file", ""),
            },
        )
        points_batch.append(point)

        if len(points_batch) >= 100 or i == len(methods) - 1:
            client.upsert(collection_name=COLLECTION_NAME, points=points_batch)
            points_batch = []

    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"\n✅ Индекс построен: {count} методов в Qdrant")
    print(f"Хранилище: {QDRANT_PATH}")


def search(query, limit=10):
    """Семантический поиск методов по описанию."""
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient

    if not os.path.exists(QDRANT_PATH):
        print(f"❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build")
        sys.exit(1)

    print(f'Поиск: "{query}"')
    print()

    model = TextEmbedding(EMBEDDING_MODEL)
    query_embedding = list(model.embed([query]))[0]

    client = QdrantClient(path=QDRANT_PATH)
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding.tolist(),
        limit=limit,
    )

    for i, hit in enumerate(results, 1):
        payload = hit.payload
        score = hit.score
        name_ru = payload.get("name_ru", "")
        name_en = payload.get("name_en", "")
        context = payload.get("context", "")[:80]
        syntax = payload.get("syntax", "")[:120]

        print(f"{i}. [{score:.3f}] {name_ru} ({name_en})")
        print(f"   Контекст: {context}")
        print(f"   Синтаксис: {syntax}")
        print()


def info():
    """Показать информацию об индексе."""
    from qdrant_client import QdrantClient

    if not os.path.exists(QDRANT_PATH):
        print(f"❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build")
        return

    client = QdrantClient(path=QDRANT_PATH)
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"RAG индекс: {COLLECTION_NAME}")
    print(f"Методов в индексе: {count}")
    print(f"Хранилище: {QDRANT_PATH}")
    size = sum(f.stat().st_size for f in Path(QDRANT_PATH).rglob("*") if f.is_file())
    print(f"Размер: {size / 1024 / 1024:.1f} МБ")


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print(f"  python3 {sys.argv[0]} build              — построить индекс")
        print(f'  python3 {sys.argv[0]} search "<запрос>"  — семантический поиск')
        print(f"  python3 {sys.argv[0]} info               — информация об индексе")
        sys.exit(1)

    command = sys.argv[1]

    if command == "build":
        build_index()
    elif command == "search":
        if len(sys.argv) < 3:
            print('Укажи запрос: python3 rag_1c_methods.py search "найти элемент по коду"')
            sys.exit(1)
        search(sys.argv[2])
    elif command == "info":
        info()
    else:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
