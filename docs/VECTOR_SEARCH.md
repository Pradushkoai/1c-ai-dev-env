# Векторный поиск (P1.1)

> Гибридный поиск BM25 + vector для семантического поиска по методам 1С.
> Добавлено в P1.1 (план v2 Solo Edition).

## Обзор

1c-ai-dev-env поддерживает 3 режима поиска:

1. **BM25 + триграммы** (default, всегда доступен) — keyword matching
2. **Векторный поиск** (опционально, требует `extras [rag]`) — semantic matching
3. **Гибридный поиск** (авто, если vector доступен) — комбинирует BM25 + vector

## Когда использовать векторный поиск

| Сценарий | BM25 | Vector | Hybrid |
|----------|------|--------|--------|
| Точное совпадение ключевых слов | ✅ Лучше | ⚠️ | ✅ |
| Синонимы ("найти" → "Поиск") | ❌ | ✅ Лучше | ✅ |
| Перефразировка ("создать новый документ") | ❌ | ✅ Лучше | ✅ |
| Опечатки ("нйати" → "найти") | ✅ (триграммы) | ⚠️ | ✅ |
| Нетиповая конфигурация с нестандартными именами | ⚠️ | ✅ Лучше | ✅ |

**Рекомендация:** используйте гибридный поиск (default через `search_hybrid_auto`).

## Установка

```bash
# Установить с extras [rag] (fastembed + qdrant-client)
pip install -e ".[rag]"

# Или отдельно
pip install fastembed qdrant-client
```

**Размер модели:** BAAI/bge-small-en-v1.5 (~130MB) загружается при первом использовании.
**Qdrant:** работает in-memory (без Docker, без сервера).

## Использование

### Python API

```python
from src.services.search_vector import VectorSearch
from src.services.search_hybrid import search_hybrid, search_hybrid_auto

# Проверить доступность
vs = VectorSearch()
if vs.is_available():
    print("Векторный поиск доступен")
    print(vs.get_stats())
else:
    print("Установите: pip install -e '.[rag]'")

# Построить векторный индекс
methods = [
    {"name_ru": "НайтиПоКоду", "name_en": "FindByCode", "description": "...", ...},
    # ...
]
count = vs.build_index(methods, index_path=Path("vector-index.json"))

# Векторный поиск
results = vs.search("найти элемент по коду", limit=5)

# Гибридный поиск (BM25 + vector)
from src.services.search_hybrid import search_hybrid
results = search_hybrid(
    index_path=Path("fast-search-index.json"),
    query="найти элемент по коду",
    limit=10,
    alpha=0.5,  # 0.5 = баланс BM25 и vector
)

# Авто-выбор (рекомендуется)
results = search_hybrid_auto(index_path, query, limit=10)
# → hybrid если vector доступен, иначе BM25
```

### CLI

```bash
# Поиск через CLI (автоматически использует hybrid если доступен)
1c-ai search "найти элемент по коду"

# Проверить статус векторного поиска
1c-ai search --vector-status
```

### MCP tools

MCP tools `search_1c_methods` и `search_code` автоматически используют
гибридный поиск через `Project.search_methods()`, который вызывает
`search_hybrid_auto()`. Если векторный поиск недоступен — fallback на BM25.

## Архитектура

```
src/services/
├── search_bm25.py       # BM25 + триграммы (всегда доступен)
├── search_vector.py     # fastembed + Qdrant (extras [rag])
└── search_hybrid.py     # Комбинирует BM25 + vector
```

### Алгоритм гибридного поиска

1. **BM25 search** → top-N результатов, scores нормализованы в [0, 1]
2. **Vector search** → top-N результатов, scores (cosine similarity) в [0, 1]
3. **Объединение** по `name_en` (уникальный ключ метода)
4. **Combined score** = `alpha * bm25_score + (1 - alpha) * vector_score`
   - `alpha=0.5` — баланс (default)
   - `alpha=1.0` — только BM25
   - `alpha=0.0` — только vector
5. **Сортировка** по combined score, top-limit результатов

### Поле `source` в результатах

Каждый результат содержит поле `source`:
- `"hybrid"` — метод найден и BM25, и vector
- `"bm25"` — метод найден только BM25 (vector не нашёл)
- `"vector"` — метод найден только vector (BM25 не нашёл)

## Производительность

| Операция | Время | Память |
|----------|-------|--------|
| Загрузка модели (один раз) | ~5 сек | ~130 MB |
| build_index (1000 методов) | ~30 сек | ~50 MB |
| search (один запрос) | ~50 ms | ~10 MB |
| search_hybrid (BM25 + vector) | ~100 ms | ~60 MB |

**Latency hybrid ~2x BM25** — приемлемо для интерактивного поиска.

## Fallback стратегия

Если fastembed или qdrant-client не установлены:
- `VectorSearch.is_available()` → `False`
- `search_hybrid()` → fallback на чистый BM25 (source='bm25')
- `search_hybrid_auto()` → fallback на `search_auto()` (BM25)
- `Project.search_methods()` → автоматически использует fallback

Это гарантирует, что проект работает без `extras [rag]`, просто с BM25.

## Зависимости

| Пакет | Версия | Назначение | Extras |
|-------|--------|------------|--------|
| fastembed | >=0.8,<1.0 | Генерация embeddings (CPU) | [rag] |
| qdrant-client | >=1.0,<2.0 | Векторное хранилище (in-memory) | [rag] |

**Модель:** BAAI/bge-small-en-v1.5 (мультиязычная, 384 dimensions)
- Поддерживает русский и английский
- Работает на CPU (GPU не требуется)
- Размер: ~130 MB

## Roadmap

- **v6.0:** A/B сравнение качества на тестовой конфигурации (УТ 11)
- **v6.0:** Поддержка `search_code` (поиск по коду конфигурации)
- **Future:** Альтернативные модели (bge-base, multilingual-e5)
- **Future:** Qdrant server mode (для больших индексов, >100K методов)
