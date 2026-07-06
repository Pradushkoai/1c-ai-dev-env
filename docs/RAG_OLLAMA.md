# RAG с Ollama (S8)

> RAG (Retrieval-Augmented Generation) pipeline для офлайн AI-coding в 1С.
> S8 (план v3: Post-v6.0 Strategic Roadmap).

## Обзор

RAG pipeline объединяет:
1. **BM25+vector search** — поиск методов платформы 1С
2. **Knowledge base** — паттерны, антипаттерны, best practices
3. **Ollama LLM** — локальная LLM для генерации ответов с контекстом

Преимущество: полностью офлайн AI-coding в 1С без отправки данных в облако.

## Установка

### 1. Установить Ollama

```bash
# Linux/Mac
curl -fsSL https://ollama.ai/install.sh | sh

# Или скачать с https://ollama.ai
```

### 2. Загрузить модель

```bash
# LLaMA 3.1 8B (рекомендуется, ~5GB)
ollama pull llama3.1:8b

# Или Qwen 2.5 7B (лучше для русского)
ollama pull qwen2.5:7b
```

### 3. Настроить окружение

```bash
# Опционально: указать модель (default: llama3.1:8b)
export OLLAMA_MODEL=qwen2.5:7b

# Опционально: указать URL (default: http://localhost:11434)
export OLLAMA_URL=http://localhost:11434
```

## Использование

### Python API

```python
from src.services.rag_pipeline import RagPipeline

rag = RagPipeline()

if rag.is_available():
    result = rag.ask(
        query="Как создать справочник в 1С?",
        config_name="ut11",  # опционально
        limit=5,             # результатов поиска
    )
    print(result.answer.text)
    print(f"Sources: {result.context_sources}")
    print(f"Latency: {result.answer.latency_ms}ms")
else:
    print("Ollama не запущен. Запустите: ollama run llama3.1:8b")
```

### Проверка доступности

```python
from src.services.llm_ollama import OllamaClient

client = OllamaClient()
stats = client.get_stats()
print(stats)
# {'available': True, 'models': [{'name': 'llama3.1:8b', ...}], ...}
```

## Архитектура

```
src/services/
├── llm_ollama.py      # Ollama REST API client
├── rag_pipeline.py    # RAG pipeline (search + context + LLM)
├── search_hybrid.py   # BM25+vector search (P1.1)
├── search_bm25.py     # BM25 search
└── knowledge_base.py  # Knowledge base (паттерны)
```

### RAG Pipeline

1. **_search_platform_methods()** — BM25+vector search по методам платформы 1С
2. **_search_config_code()** — поиск по коду конфигурации (если указана)
3. **_search_knowledge_base()** — поиск по паттернам/антипаттернам
4. **_gather_context()** — объединение результатов, обрезка до max_context_length
5. **ollama.generate()** — LLM генерация с контекстом

### Системный промпт

Pipeline использует системный промпт:
> "Ты — эксперт 1С разработчик с глубоким знанием платформы 1С:Предприятие 8.3..."

Соблюдает стандарты 1С (STD 456): табы для отступов, области в коде,
ключевые слова запросов КАПСОМ.

## Системные требования

| Компонент | Требование |
|-----------|------------|
| Ollama | Установленный и запущенный |
| Модель | llama3.1:8b (~5GB) или qwen2.5:7b (~4.5GB) |
| RAM | Минимум 8GB (16GB рекомендуется) |
| GPU | Опционально (6GB VRAM для 8B модели) |
| CPU | Работает на CPU (медленнее, но функционально) |
| Интернет | Не требуется (полностью офлайн) |

## Fallback

Если Ollama не установлен:
- `rag.is_available()` → `False`
- `rag.ask()` → `RagResult` с `rag_available=False` и инструкцией по установке
- Проект полностью функционален без RAG (MCP tools работают без LLM)

## Метрики

| Метрика | Значение |
|---------|----------|
| Latency (8B, GPU) | ~2-5 секунд |
| Latency (8B, CPU) | ~30-60 секунд |
| Context length | До 4000 символов (настраиваемо) |
| Max tokens | 2048 (настраиваемо) |
| Temperature | 0.7 (настраиваемо) |
