# Architecture Decision Records (ADR)

> ADR каталог для 1c-ai-dev-env.
> Каждое нетривиальное архитектурное решение документируется здесь.
> S6 (план v3: Post-v6.0 Strategic Roadmap).

## Что такое ADR

ADR (Architecture Decision Record) — короткий документ, описывающий
архитектурное решение: контекст, рассмотренные варианты, выбранное решение,
посствия. Помогает future-me и другим разработчикам понять, почему
сделано именно так.

## Формат ADR

```markdown
# ADR-NNNN: Название решения

**Дата:** YYYY-MM-DD
**Статус:** Accepted | Superseded by ADR-XXXX | Deprecated

## Контекст
Почему нужно принять решение? Какие проблемы решаем?

## Рассмотренные варианты
1. Вариант A — описание, pros/cons
2. Вариант B — описание, pros/cons

## Решение
Какой вариант выбран и почему?

## Последствия
Что меняется? Какие риски?
```

## Индекс ADR

| ADR | Название | Дата | Статус |
|-----|----------|------|--------|
| [ADR-0001](0001-solo-development-path.md) | Выбор solo-development path | 2026-07-03 | Accepted |
| [ADR-0002](0002-mcp-tools-categorization.md) | Категоризация 45 MCP tools | 2026-07-03 | Accepted |
| [ADR-0003](0003-hybrid-search-bm25-vector.md) | Гибридный поиск BM25+vector | 2026-07-03 | Accepted |
| [ADR-0004](0004-graceful-fallback-pattern.md) | Graceful fallback pattern | 2026-07-03 | Accepted |
| [ADR-0005](0005-snapshot-testing-for-contracts.md) | Snapshot testing для MCP contracts | 2026-07-03 | Accepted |
| [ADR-0006](0006-scope-reduction-v6.md) | Scope Reduction v6.x — заморозка SaaS/Enterprise/Plugin | 2026-07-04 | Accepted |
| [ADR-0007](0007-v8unpack-workaround-retention.md) | v8unpack 1.2.6 block_size баг — сохранение workaround | 2026-07-04 | Accepted |
| [ADR-0008](0008-language-policy-russian.md) | Язык проекта — русский | 2026-07-04 | Accepted |

## Как добавить ADR

1. Скопируй `0000-template.md`
2. Заполни: контекст, варианты, решение, последствия
3. Назови `NNNN-kebab-case-name.md` (следующий номер)
4. Обнови индекс выше
5. Закоммить с сообщением: `docs(adr): ADR-NNNN название`
