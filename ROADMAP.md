# Roadmap

> Дорожная карта развития 1c-ai-dev-env.

## Текущая версия: v6.1.0 (Beta → approaching Production-Ready)

**July 2026 — Architecture refactoring completed (Phase 1-4 of plan).**

После завершения 4-фазного рефакторинга (см. [ADR-0009](adr/0009-architecture-refactor-strategy.md))
репозиторий существенно улучшился:

| Метрика | До рефакторинга | После |
|---------|-----------------|-------|
| Test failures (pre-existing) | 14 | 0 |
| experimental/ LOC | ~1334 | 0 |
| Дубликаты BSL модулей | 2 | 1 (thin wrapper) |
| scripts/ файлы | 42 | 39 |
| tool_definitions.py LOC | 879 | 623 |
| call_graph.py LOC | 668 | 80 (re-export) |
| Структура core/services/adapters | нет | да |
| Architecture diagram | нет | C4 |
| ADR | 8 | 10 |

### Критерии перехода Beta → Production-Ready

Переход к Production-Ready состоится при выполнении **всех** условий:

1. **Coverage ≥ 80%** (текущее: ~73%, цель: 80% — Phase 1 стабилизировала, Phase 2-3 сохранили)
2. **mypy strict без исключений** (warn_return_any ✅, disallow_any_generics gradual ✅)
3. **Реальные пользователи** — ≥ 3 внешних issue/PR от non-author (0 на данный момент)
4. **Bus factor > 1** — ≥ 1 активный контрибьютор кроме автора (0 на данный момент)
5. **Документация актуальна** — Stability Matrix в README ✅, C4 диаграмма ✅ (Phase 4.1), ADR-0009 ✅ (Phase 4.2), DEPENDENCIES.md ✅ (Phase 4.4)
6. **Нет критических TODO/FIXME** без issue-ссылки ✅
7. **Demo-конфигурация** проходит smoke-тест у внешнего пользователя ✅

**Осталось:** поднять coverage с 73% до 80% и получить реальных пользователей.

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
Код `experimental/` удалён в Phase 1.2 рефакторинга (ADR-0009).

## План v6.1: Architecture Refactoring (July 2026) — ✅ COMPLETED

4-фазный рефакторинг по Strangler Fig Pattern (см. [ADR-0009](adr/0009-architecture-refactor-strategy.md)).

| Фаза | Задача | Статус | Коммит |
|------|--------|--------|--------|
| 1.1 | Починить 14 pre-existing test failures | ✅ DONE | `2b01873` |
| 1.2 | Удалить experimental/ (-1334 LOC) | ✅ DONE | `1f06f7d` |
| 1.3 | bsl_ast.py → thin wrapper над bsl_tree_sitter | ✅ DONE | `2903194` |
| 1.4 | Аудит scripts/, удаление 3 мёртвых скриптов | ✅ DONE | `61802ba` |
| 2 | core/services/adapters слои с Protocol-контрактами | ✅ DONE | `e3df9a5` |
| 3.1 | CLI — уже организован (src/cli.py + cli_commands/) | ✅ DONE | (no change needed) |
| 3.2 | Handlers — domain aggregate modules | ✅ DONE | `bb0f7b5` |
| 3.3 | tool_definitions.py — single source of truth (-256 LOC) | ✅ DONE | `5cd3017` |
| 3.4 | call_graph.py — split into 3 modules (668→80 LOC) | ✅ DONE | `7d00000` |
| 4.1 | C4 architecture diagram | ✅ DONE | this commit |
| 4.2 | ADR-0009 refactor strategy | ✅ DONE | this commit |
| 4.3 | ROADMAP update | ✅ DONE | this commit |
| 4.4 | DEPENDENCIES.md | ✅ DONE | this commit |

### Заморожено (SaaS/Enterprise/Plugin, ADR-0006)

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

## Прогресс поэтапного плана улучшения (Этапы 0-7)

> Полный план: [docs/AUDIT_SCRIPTS_SERVICES.md](docs/AUDIT_SCRIPTS_SERVICES.md)

### Этап 0: Стабилизация ✅
- 0.1: Quarantine future-proofing → experimental/ (ADR-0006)
- 0.2: ROADMAP + CHANGELOG + SemVer обоснование
- 0.3: Статус понижен до Beta
- 0.4: ADR-0006 Scope Reduction

### Этап 1: Унификация scripts/services ✅
- 1.1: Аудит дублирования (37 скриптов)
- 1.2: 14 скриптов перенесено в src/services/ (12 dynamic imports устранено)
- 1.3: Документация границы scripts/services + pre-commit hook
- 1.4: Аудит мёртвых скриптов (0 найдено)

### Этап 2: Декомпозиция god-файлов ✅
- 2.1: check_1c_standards.py 1685→122 + 5 модулей в standards/
- 2.2: epf_factory.py 713→508 + 4 модуля в epf/
- 2.3: metadata_extractor.py перенесён в services.metadata
- 2.4: build_config_index_generic.py перенесён в services.builders
- 2.5: cfe_manager.py 718→650 + 2 модуля в cfe/

### Этап 3: Качество и типизация ✅
- 3.1: mypy warn_return_any = true
- 3.2: mypy disallow_any_generics (gradual, 5 чистых пакетов)
- 3.3: ADR-0007 v8unpack workaround сохранён
- 3.4: TODO/FIXME аудит — 0 для удаления

### Этап 4: i18n и документация ✅
- 4.1: ADR-0008 язык проекта русский
- 4.2: README Stability Matrix (16 подсистем)
- 4.3: CONTRIBUTING.md 3 how-to гайда
- 4.4: Sphinx +30 модулей в API reference

### Этап 5: Тесты и coverage ✅
- 5.1: Аудит 1624 тестов — 0 дубликатов
- 5.2: Coverage gate 70% → 72% (+23 теста)
- 5.3: 15 smoke-тестов для критических путей (2.2 сек)
- 5.4: Mutation testing gate 60% → 70%

### Этап 6: Производительность ✅
- 6.1: cProfile отчёт (docs/PERFORMANCE.md)
- 6.2: os.scandir() оптимизация (−47% calls, −50% time)
- 6.3: Benchmark regression-detection (blocking, 10%)

### Этап 7: Community-ready ✅
- 7.1: Demo-конфигурация + quickstart (demo/)
- 7.2: 10 good-first-issues (#12-#21)
- 7.3: 5 примеров использования MCP (docs/EXAMPLES.md)
- 7.4: Public roadmap (этот документ) + changelog feed

### Следующие этапы (не начаты)

- **Этап 8: Long-term** — нативный парсер EPF, BSL LS opt-in, multi-config

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
