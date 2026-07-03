# Roadmap

> Дорожная карта развития 1c-ai-dev-env.

## Текущая версия: v6.0.0 (Production-Ready)

v6.0.0 завершает план v2 (Solo Edition). 19 из 20 задач выполнены.
Проект перешёл от Beta к Production-ready.

### Ключевые метрики v6.0.0
- 1475 тестов, coverage 71.44%
- mypy 0 errors (strict, blocking)
- 45 MCP tools (sync + snapshot)
- mcp_server.py: 139 строк (было 1245)
- Гибридный поиск BM25+vector
- Prometheus metrics + NoOp fallback
- Backup: GitLab mirror + git bundle
- Fuzzing: atheris для парсеров
- Sphinx + doctest документация

## План v3: Post-v6.0 Strategic Roadmap

| ID | Задача | Приоритет | Статус |
|----|--------|-----------|--------|
| S7 | Release v6.0 | P0 | ✅ DONE |
| S6 | Developer Onboarding | P0 | ✅ DONE |
| S5 | Security Hardening | P1 | ✅ DONE (commit 1a8a673) |
| S1 | SaaS-подготовка | P1 | ✅ DONE (commit 066ed5a) |
| S3 | Enterprise Features | P2 | ✅ DONE (commit a5de768) |
| S2 | Plugin System | P2 | ✅ DONE (commit 909918b) |
| S4 | Performance Optimization | P2 | ✅ DONE (commit 23d12dc) |
| S8 | RAG с Ollama | P3 (future) | ✅ DONE (commit c20ae65) |

### Timeline
- **Q2 2027:** S7 Release v6.0 ✅, S6 Onboarding ✅
- **Q3 2027:** S5 Security ✅, S1 SaaS-подготовка ✅
- **Q4 2027:** S3 Enterprise ✅, S2 Plugin System ✅
- **Q1 2028:** S4 Performance ✅
- **Q2 2028+:** S8 RAG с Ollama ✅

Все 8 задач плана v3 завершены. Проект v6.0.0 полностью закрыт по плану.

## История версий

| Версия | Дата | Описание |
|--------|------|----------|
| v6.0.0 | 2026-07-03 | Production-ready, план v2 завершён |
| v5.4.0 | 2026-07-02 | Beta, план v2 старт |
| v5.3.0 | 2026-07-02 | Pre-release подготовка |

## Принципы

1. Без regression — каждый спринт зелёный CI
2. Spec-driven — крупные изменения через OpenSpec proposal
3. Coverage-first — новый код покрывается тестами
4. Type safety — mypy strict (disallow_untyped_defs)
5. Backward compat — breaking changes с DeprecationWarning
6. Automation First — CI/CD заменяет ревьюера
7. Future-me Documentation — ADR для нетривиальных решений
8. Sustainable Pace — 2-3 задачи/спринт
9. Scalability First — архитектура готова к масштабированию
10. Security by Design — validation и audit в каждом компоненте
