# ADR-0001: Выбор solo-development path

**Дата:** 2026-07-03
**Статус:** Accepted

## Контекст
Проект 1c-ai-dev-env разрабатывается одним разработчиком (Pradushkoai).
План v1 предполагал командную разработку (bus factor 1→3+, good-first-issues,
community outreach). Однако разработчик явно указал, что будет работать один.
Нужно было решить: адаптировать план для solo или сохранить team-oriented подход.

## Рассмотренные варианты
1. **Сохранить v1 (team-oriented)** — привлекать контрибьюторов
   - Pros: больше ресурсов, быстрее разработка
   - Cons: требует времени на community management, onboarding, code review
2. **Адаптировать для solo (v2 Solo Edition)** — убрать team tasks, добавить automation
   - Pros: реалистичные сроки, фокус на automation вместо people
   - Cons: bus factor = 1, риск knowledge loss
3. **Гибрид** — solo + минимальное community engagement
   - Pros: баланс
   - Cons: сложнее управлять

## Решение
Выбран вариант 2 (v2 Solo Edition). План v1 адаптирован:
- Удалены: bus factor task, good-first-issues, community outreach
- Добавлены: 6 новых solo-dev задач (complexity budget, mutation testing,
  snapshot testing, dependency hygiene, backup strategy, fuzzing)
- Принцип: "Automation First — CI/CD заменяет ревьюера"

## Последствия
- Срок увеличен с 6 до 8-10 месяцев (sustainable pace)
- Coverage target снижен с 75% до 70% (solo realistisch)
- Bus factor = 1 остаётся риском, но митигируется через:
  - ADR каталог (этот документ)
  - doctest в коде
  - docs-as-code (Sphinx)
  - backup strategy (GitLab mirror + git bundle)
- v3 план добавляет SaaS/Plugin/Enterprise как technology-level подготовку
