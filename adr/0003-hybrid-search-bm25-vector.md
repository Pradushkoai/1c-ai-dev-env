# ADR-0003: Гибридный поиск BM25+vector

**Дата:** 2026-07-03
**Статус:** Accepted

## Контекст
BM25 + триграммы хорошо работают для точного совпадения ключевых слов,
но слабы для семантического поиска (синонимы, перефразировки). Infostart MCP
(конкурент) использует Qdrant + embeddings. Нужно было решить: оставить
только BM25 или добавить векторный поиск.

## Рассмотренные варианты
1. **Только BM25** — оставить как есть
   - Pros: простота, нет зависимостей
   - Cons: слабый семантический поиск
2. **Только vector** — заменить BM25 на vector
   - Pros: лучший семантический поиск
   - Cons: хуже для точного совпадения, требует GPU/CPU для embeddings
3. **Гибридный BM25+vector** — комбинировать
   - Pros: лучшее из обоих миров, graceful fallback
   - Cons: сложнее, ~2x latency

## Решение
Вариант 3 (гибридный). Создан src/services/search_hybrid.py:
- alpha=0.5 (баланс BM25 и vector)
- Нормализация scores в [0,1] (min-max)
- Объединение по name_en (уникальный ключ)
- Combined score = alpha * bm25 + (1-alpha) * vector
- Поле 'source': 'hybrid'/'bm25'/'vector'
- Graceful fallback: если fastembed/qdrant не установлены → чистый BM25

## Последствия
- extras [rag] опциональны (fastembed + qdrant-client)
- Без extras [rag] — проект работает с чистым BM25
- Project.search_methods() автоматически использует hybrid через search_hybrid_auto()
- Latency hybrid ~2x BM25 (приемлемо для интерактивного поиска)
