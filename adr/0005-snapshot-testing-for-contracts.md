# ADR-0005: Snapshot testing для MCP contracts

**Дата:** 2026-07-03
**Статус:** Accepted

## Контекст
45 MCP tools — это контракт с LLM-агентами (Cursor, Claude). Любое
изменение имён, описаний или inputSchema может сломать下游 потребителей.
Без команды (solo-dev) нужен автоматический контроль контракта.

## Рассмотренные варианты
1. **Unit тесты с assertions** — проверять конкретные значения
   - Pros: точность
   - Cons: много кода, сложно поддерживать
2. **Snapshot testing (pytest-snapshot)** — эталонные файлы
   - Pros: автоматический diff, легко обновлять
   - Cons: ещё одна зависимость
3. **Contract testing (pact)** — формальный контракт
   - Pros: самый строгий
   - Cons: overkill для solo-dev

## Решение
Вариант 2 (snapshot testing). pytest-snapshot:
- 7 snapshot файлов: tool_names, tool_count, tool_descriptions,
  tool_input_schemas, static_descriptions, static_descriptions_names,
  static_descriptions_required_params
- 4 контрактных теста (не snapshot): sync, not_empty, type=object, has_properties
- Обновление: `pytest --snapshot-update` (осознанное действие)
- CI blocking при mismatch

## Последствия
- Любое изменение MCP tools → visible diff в snapshot
- Обновление snapshot = ADR запись с обоснованием
- Snapshot файлы в git (эталонные, не временные)
- Добавлен pytest-snapshot в dev dependencies
