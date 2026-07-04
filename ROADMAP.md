# Roadmap

> Дорожная карта развития 1c-ai-dev-env.

## Текущая версия: v6.0.0 (Beta)

v6.0.0 завершает план v2 (Solo Edition). 19 из 20 задач выполнены.
Проект находится в **Beta**-статусе: ядро стабильно, но Production-Ready
откладывается до выполнения критериев ниже.

> ⚠️ **Корректировка от 2026-07-04**: ранее v6.0.0 заявлялся как
> "Production-Ready". После аудита статус понижен до Beta — см.
> [ADR-0006](adr/0006-scope-reduction-v6.md) и критерии перехода ниже.
> Это более честная оценка для solo-dev проекта без реальных
> пользователей SaaS/Enterprise фич.

### Критерии перехода Beta → Production-Ready

Переход к Production-Ready состоится при выполнении **всех** условий:

1. **Coverage ≥ 80%** (текущее: 71.44%, цель: этап 5.2)
2. **mypy strict без исключений** (warn_return_any + disallow_any_generics, этап 3.1-3.2)
3. **Реальные пользователи** — ≥ 3 внешних issue/PR от non-author
4. **Bus factor > 1** — ≥ 1 активный контрибьютор кроме автора
5. **Документация актуальна** — Stability Matrix в README, все public APIs задокументированы
6. **Нет критических TODO/FIXME** без issue-ссылки (этап 3.4)
7. **Demo-конфигурация** проходит smoke-тест у внешнего пользователя (этап 7.1)

До выполнения этих условий проект остаётся Beta. Использовать в
production — на свой риск.

### Ключевые метрики v6.0.0
- 1475 тестов, coverage 71.44%
- mypy 0 errors (strict с исключениями — этап 3 уберёт их)
- 45 MCP tools (sync + snapshot)
- mcp_server.py: 139 строк (было 1245)
- Гибридный поиск BM25+vector
- Prometheus metrics + NoOp fallback
- Backup: GitLab mirror + git bundle
- Fuzzing: atheris для парсеров
- Sphinx + doctest документация

## План v3: Post-v6.0 Strategic Roadmap

> ⚠️ **Корректировка от 2026-07-04**: ранее здесь были даты Q2 2027 — Q2 2028
> при заявленных "✅ DONE" статусах. Это противоречие (нельзя быть DONE с
> будущей датой) — даты заменены на фактические, а "future" задачи
> (SaaS/Enterprise/Plugin) перенесены в [BACKLOG](#backlog-long-term) до
> появления команды. См. [ADR-0006](adr/0006-scope-reduction-v6.md).

### Выполнено (v6.0.0)

| ID | Задача | Статус |
|----|--------|--------|
| S7 | Release v6.0 | ✅ DONE |
| S6 | Developer Onboarding | ✅ DONE |
| S5 | Security Hardening | ✅ DONE (commit 1a8a673) |
| S4 | Performance Optimization | ✅ DONE (commit 23d12dc) |
| S8 | RAG с Ollama | ✅ DONE (commit c20ae65) |

### Заморожено (SaaS/Enterprise/Plugin, ADR-0006)

Перенесено в BACKLOG до появления команды и реальных пользователей.
Код сохранён в `experimental/` (см. задачу 0.1).

| ID | Задача | Причина заморозки |
|----|--------|--------------------|
| S1 | SaaS-подготовка | Solo-dev не тянет multi-tenant; 0 реальных tenants |
| S3 | Enterprise Features | 0 enterprise-пользователей; поддержка тяжёлая |
| S2 | Plugin System | 0 плагинов от community; over-engineering |

## BACKLOG (long-term)

Задачи, запускаемые после выполнения критериев Beta → Production-Ready:

- **S1** Multi-config в одном Project (namespace isolation)
- **S3** Enterprise features (RBAC, audit log, SSO)
- **S2** Plugin System (real plugins from community)
- **HTTP transport для MCP** (вместо stdio) — только после S1

## История версий

| Версия | Дата | Описание |
|--------|------|----------|
| v6.0.0 | 2026-07-03 | Beta, план v2 завершён. Production-Ready отложено (ADR-0006) |
| v5.4.0 | 2026-07-02 | Beta, план v2 старт |
| v5.3.0 | 2026-07-02 | Pre-release подготовка |

## Принципы

1. **Без regression** — каждый спринт зелёный CI
2. **Spec-driven** — крупные изменения через OpenSpec proposal
3. **Coverage-first** — новый код покрывается тестами; gate растёт 70→80%
4. **Type safety** — mypy strict без исключений (warn_return_any, disallow_any_generics)
5. **Backward compat** — breaking changes с DeprecationWarning за 1 минор до удаления
6. **Реалистичный SemVer** — никаких скачков 5.3→6.0 за день без существенных изменений
7. **Future-me Documentation** — ADR для нетривиальных решений
8. **Sustainable Pace** — 2-3 задачи/спринт, без перегруза solo-dev
9. **Scope discipline** — замораживать future-proofing до появления реальной потребности
10. **Security by Design** — validation и audit в каждом компоненте
