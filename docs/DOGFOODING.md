# Dogfooding (P3.2)

> Использование собственного MCP сервера для разработки самого проекта.
> P3.2 (план v2 Solo Edition) — ongoing стратегическая инициатива.

## Концепция

Dogfooding — это когда проект использует свой собственный продукт для
разработки. 1c-ai-dev-env предоставляет 45 MCP tools для AI-coding в 1С.
Мы используем эти же tools (через Cursor/Claude) для разработки самого
1c-ai-dev-env на Python.

**Преимущества:**
1. **Реальное тестирование UX** — обнаруживаем проблемы в боевых условиях
2. **Ускорение разработки** — AI-coding через собственный MCP
3. **Нахождение багов** — улучшения, которые не видны в тестах
4. **Маркетинг** — публичные инсайты привлекают community

## Что настроено

### knowledge_base/dev_patterns/

Паттерны разработки самого проекта:
- Архитектурные решения (4-layer, CQRS-lite, SRP)
- Частые ошибки (v8unpack block_size, install.sh хардкод)
- Лучшие практики (mypy strict, snapshot testing, fuzzing)

### Custom dev tools (roadmap)

Планируемые custom tools для разработки:
- `1c-ai-dev-dev-helper` — helper для разработки самого проекта
- `add_test_for_function` — генерация тестов для новой функции
- `generate_docstring` — автогенерация docstring из кода
- `create_adr` — создание Architecture Decision Record

## Процесс

### Еженедельная ретроспектива

Каждую неделю:
1. Что сработало при dogfooding
2. Что не сработало
3. Записи в `runtime/dogfooding_log.md`

### Productivity delta

Измерение ROI dogfooding:
- Часы с AI (через MCP) vs часы без AI
- Цель: +30% к скорости разработки

## Roadmap

- **P3.2 (этот документ):** Dogfooding концепция + документация ✅
- **Future:** knowledge_base/dev_patterns/ наполнение
- **Future:** Custom dev tools для разработки
- **Future:** Публичный dogfooding log (docs/DOGFOODING.md)
- **Future:** Productivity delta метрики

## Связанные документы

- `AGENTS.md` — правила для AI-агентов (уже используется)
- `docs/AGENTS_MD.md` — расширенное описание
- `docs/VECTOR_SEARCH.md` — векторный поиск (используется при dogfooding)
- `docs/METRICS.md` — метрики (отслеживание dogfooding)
