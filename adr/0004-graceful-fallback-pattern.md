# ADR-0004: Graceful fallback pattern

**Дата:** 2026-07-03
**Статус:** Accepted

## Контекст
Проект имеет несколько опциональных зависимостей (fastembed, qdrant-client,
prometheus-client, BSL LS). Нужно было решить: требовать все зависимости
или делать их опциональными с fallback.

## Рассмотренные варианты
1. **Требовать все зависимости** — установить всё по умолчанию
   - Pros: весь функционал доступен сразу
   - Cons: тяжёлая установка, конфликт зависимостей
2. **Опциональные extras с graceful fallback** — NoOp при отсутствии
   - Pros: лёгкая установка,渐进式 функциональность
   - Cons: больше кода (NoOp классы)

## Решение
Вариант 2 (graceful fallback). Паттерн:
- `is_available()` проверяет наличие зависимости
- NoOp реализация (NoOpMetric, NoOpRegistry) при отсутствии
- `get_metrics()` singleton возвращает PrometheusRegistry или NoOpRegistry
- `@with_metrics` работает без накладных расходов если NoOp
- BSL LS: `bsl_ls_with_fallback` декоратор → fallback на check_1c_standards

## Последствия
- pip install -e . работает без extras (базовый функционал)
- extras [rag], [metrics], [mcp] — опциональные расширения
- Каждая опциональная фича имеет NoOp fallback
- Паттерн задокументирован для будущих опциональных зависимостей
