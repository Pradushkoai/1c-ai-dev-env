# ADR-0009: Architecture refactor strategy

**Status:** Accepted (July 2026)  
**Phase:** 4.2 of refactoring plan  
**Supersedes:** —  
**Superseded by:** —

## Context

После серии доработок (P1.5 статический валидатор запросов, P1-A tree-sitter-bsl, P1-B CamelCase tokenizer) в репозитории 1c-ai-dev-env накопился технический долг:

- **14 pre-existing test failures** — поле `_next_steps` добавлено в MCP handlers, тесты не обновлены
- **Дубликаты модулей** — `bsl_ast.py` (113 LOC) и `bsl_tree_sitter.py` (280 LOC) делают похожую работу
- **Разбросанный CLI** — `scripts/` (39 файлов) и `src/cli_commands/` (13 файлов) без чёткого разделения
- **Раздутые handlers** — 8 файлов в `mcpserver/handlers/` без доменной группировки
- **Два источника истины** — `tool_definitions.py` (879 LOC) с двумя списками tools
- **Смешанные ответственности** — `call_graph.py` (668 LOC) с regex + tree-sitter + graph + алгоритмами
- **Coverage 72%** при цели 80%

Рассматривали 3 варианта:
1. **Rewrite с нуля** — переписать весь репозиторий
2. **Оставить как есть** — продолжать накапливать долг
3. **Big bang refactor** — один большой PR с всеми изменениями
4. **Strangler Fig Pattern** — постепенная замена проблемных частей

## Decision

Выбрали **Strangler Fig Pattern** (Martin Fowler, 2004) — постепенная замена проблемных частей с сохранением рабочего кода.

План из 4 фаз:

| Фаза | Название | Срок | Главная цель |
|------|----------|------|--------------|
| 1 | Стабилизация | 1 неделя | Починить test failures, удалить мёртвый код |
| 2 | Архитектурный каркас | 2 недели | core/services/adapters с Protocol-контрактами |
| 3 | Консолидация | 1 неделя | Схлопнуть дубликаты CLI/handlers/tool_def/call_graph |
| 4 | Документация | 3 дня | C4, ADR-0009, ROADMAP, DEPENDENCIES |

## Alternatives considered

### 1. Rewrite с нуля

**Отклонено.** Аргумент Joel Spolsky «Things You Should Never Do» (2000): код — это запечатлённое знание о багах, edge cases, неочевидных зависимостях. Переписывание выбрасывает это знание.

Конкретные потери:
- v8unpack баг (ADR-0007) — известный workaround, переписывание заставит повторно открыть
- BSL LS quirks — 187 диагностик с нюансами в `bsl_ls_rules.py`
- 1С XML форматы — 12 спецификаций в `docs/1c-xml-specs/`
- 6 месяцев работы — 24 400 LOC в src/ невозможно переписать быстрее
- MCP-клиенты (Cursor, Claude) зависят от имён tools — любая несовместимость = regression

Критерии когда rewrite оправдан (ни один не выполняется):
- ❌ Архитектура фундаментально неправильная — у нас 4-слойная, чистая
- ❌ Технологический стек устарел — Python 3.12, современные deps
- ❌ Накопленный долг делает любое изменение рискованным — 8 ADR, scope discipline
- ❌ Команда не может объяснить, почему код работает — ADR объясняют
- ❌ Production-инциденты от архитектурных проблем — Beta, инцидентов нет

### 2. Оставить как есть

**Отклонено.** Долг растёт, новое добавляется поверх. После P1.5/P1-A/P1-B накопилось критическое количество. Дальше — разработка станет невозможной.

### 3. Big bang refactor

**Отклонено.** Один большой PR с всеми изменениями:
- Невозможно review
- Невозможно откатить
- Тесты красные до конца
- Bisect невозможен
- Высокий риск regression

## Consequences

### Положительные

- **Backward compat на каждом шаге** — MCP tools работают на каждой фазе
- **Рабочий репозиторий в любой момент** — можно остановиться после любой фазы
- **Каждая фаза тестируема** — отдельный коммит, тесты green
- **Низкий риск** — изменения локальные, не архитектурные в ядре
- **Видимый результат** — после Фазы 1 (неделя) уже лучше, чем было

### Отрицательные

- **5 недель вместо 2** (rewrite-оценка была нереалистичной)
- **Дисциплина принудительная** — каждый шаг отдельный коммит, нельзя «потом починю»
- **Двойная структура во время миграции** — старые + новые пути импорта (через re-export)

## Implementation

### Phase 1: Stabilization (1 week) — COMPLETED

- ✅ 1.1: 14 pre-existing test failures → 0 (commit `2b01873`)
- ✅ 1.2: experimental/ removed (commit `1f06f7d`, -1334 LOC)
- ✅ 1.3: bsl_ast.py → thin wrapper over bsl_tree_sitter (commit `2903194`)
- ✅ 1.4: scripts/ audited, 3 dead scripts removed (commit `61802ba`)

### Phase 2: Architectural skeleton (2 weeks) — COMPLETED

- ✅ Created src/core/ (metadata, search, analyzers, mcp) with re-export (commit `e3df9a5`)
- ✅ Created src/adapters/ with re-export
- ✅ Protocol contracts in each layer (protocols.py)
- ✅ Backward compat verified (same objects via identity check)

### Phase 3: Consolidation (1 week) — COMPLETED

- ✅ 3.1: CLI already consolidated (src/cli.py + src/cli_commands/)
- ✅ 3.2: Domain aggregate modules for handlers (commit `bb0f7b5`)
- ✅ 3.3: tool_definitions.py single source of truth (commit `5cd3017`, -256 LOC)
- ✅ 3.4: call_graph.py split into 3 modules (commit `7d00000`, 668→80 LOC)

### Phase 4: Documentation (3 days) — IN PROGRESS

- ✅ 4.1: docs/ARCHITECTURE_C4.md (this commit)
- ✅ 4.2: ADR-0009 (this document)
- ⏳ 4.3: ROADMAP update
- ⏳ 4.4: DEPENDENCIES.md

## Metrics

| Метрика | До | После |
|---------|-----|-------|
| Test failures (pre-existing) | 14 | 0 |
| experimental/ LOC | ~1334 | 0 |
| Дубликаты BSL модулей | 2 | 1 (thin wrapper) |
| scripts/ файлы | 42 | 39 |
| tool_definitions.py LOC | 879 | 623 |
| call_graph.py LOC | 668 | 80 (re-export) |
| Структура core/services/adapters | нет | да |
| Architecture diagram | нет | C4 |
| ADR | 8 | 10 (+0009, +0010 pending) |

## References

- Martin Fowler, "Strangler Fig Application" (2004): https://martinfowler.com/bliki/StranglerFigApplication.html
- Joel Spolsky, "Things You Should Never Do" (2000): https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/
- ADR-0006: Scope reduction v6 (froze SaaS/Enterprise/Plugin)
- ADR-0007: v8unpack workaround retention
- REFACTORING.md — detailed plan document
