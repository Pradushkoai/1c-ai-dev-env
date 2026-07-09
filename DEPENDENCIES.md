# DEPENDENCIES.md — Зависимости 1c-ai-dev-env

**Phase 4.4 of refactoring**  
**Дата:** July 2026

Классификация зависимостей по критичности для планирования миграций, plugin system и production-ready оценки.

---

## Критичные зависимости (без них не работает)

Эти зависимости обязательны. Без них проект не запускается.

| Зависимость | Версия | Назначение | Где используется |
|-------------|--------|------------|------------------|
| `python` | ≥ 3.12 | Runtime | Весь проект |
| `mcp` | ≥ 1.0, < 2.0 | MCP protocol | `src/core/mcp/` — 46 MCP tools |
| `networkx` | ≥ 3.0, < 4.0 | Графы зависимостей | `src/services/dependency_graph.py` |
| `v8unpack` | git main | Распаковка .cf/.cfe | `src/services/cf/extractor.py`, `src/services/cfe/` |
| `pydantic` | (через mcp) | Валидация моделей | MCP types |
| `structlog` | ≥ 24.0 | Структурированное логирование | `src/services/logger.py` |

---

## Опциональные зависимости (улучшают, но не обязательны)

Эти зависимости включают дополнительный функционал. Без них работает fallback.

| Зависимость | Версия | Назначение | Fallback без неё |
|-------------|--------|------------|------------------|
| `tree-sitter` | ≥ 0.25, < 1.0 | AST парсинг BSL | regex-based `bsl_ast.py` |
| `tree-sitter-bsl` | ≥ 0.1, < 1.0 | BSL грамматика для tree-sitter | regex-based парсинг |
| `fastembed` | ≥ 0.8, < 1.0 | Embeddings для векторного поиска | BM25 без векторного |
| `qdrant-client` | ≥ 1.0, < 2.0 | Vector DB для RAG | BM25 без RAG |
| `prometheus-client` | ≥ 0.20, < 1.0 | Metrics endpoint | NoOp fallback |
| `uvicorn` | ≥ 0.27, < 1.0 | HTTP transport для MCP | только stdio transport |
| `starlette` | ≥ 0.37, < 2.0 | HTTP framework для MCP | только stdio transport |

### Установка опциональных зависимостей

```bash
# Все опциональные (full feature set):
pip install -e ".[mcp,mcp-http,rag,metrics,ast]"

# Только MCP (минимум для production):
pip install -e ".[mcp]"

# MCP + AST (рекомендуется для разработки):
pip install -e ".[mcp,ast]"

# MCP + RAG (для векторного поиска):
pip install -e ".[mcp,rag,ast]"
```

---

## Внешние системы (не Python пакеты)

| Система | Тип | Назначение | Без неё |
|---------|-----|------------|--------|
| **BSL Language Server** | Java JAR (subprocess) | 187 диагностик BSL | 56 правил стандартов без Java |
| **Ollama** | HTTP API (localhost:11434) | Локальные LLM для RAG | RAG pipeline не работает |
| **1С:Предприятие 8** | Источник данных | Выгрузка .cf/.cfe | Нечего анализировать |
| **Java Runtime** | JRE ≥ 17 | Для BSL LS | BSL LS недоступен |

---

## Зависимости для разработки

Только для тестов и CI. Не нужны для runtime.

| Зависимость | Версия | Назначение |
|-------------|--------|------------|
| `pytest` | ≥ 8.0, < 9.0 | Тест runner |
| `pytest-cov` | ≥ 4.0, < 6.0 | Coverage |
| `pytest-benchmark` | ≥ 4.0, < 6.0 | Бенчмарки |
| `pytest-asyncio` | ≥ 0.23, < 1.0 | Async тесты |
| `pytest-snapshot` | ≥ 0.9, < 1.0 | Snapshot тесты для MCP tools |
| `hypothesis` | ≥ 6.0, < 7.0 | Property-based testing |
| `lxml` | ≥ 5.0, < 6.0 | XML parsing для тестов |
| `Pillow` | ≥ 10.2.0, < 12.0 | Image processing в тестах |
| `atheris` | ≥ 3.0, < 4.0 | Fuzzing для парсеров |
| `ruff` | ≥ 0.5, < 1.0 | Linter |
| `mypy` | ≥ 1.10, < 2.0 | Type checker |
| `bandit` | ≥ 1.7, < 2.0 | SAST |
| `semgrep` | ≥ 1.50, < 2.0 | Multi-language SAST |
| `radon` | ≥ 6.0, < 7.0 | Complexity metrics |
| `mutmut` | ≥ 3.0, < 4.0 | Mutation testing |
| `pip-audit` | ≥ 2.0, < 3.0 | CVE проверка зависимостей |
| `safety` | ≥ 3.0, < 4.0 | Vulnerability scanner |
| `pip-licenses` | ≥ 5.0, < 6.0 | License compliance |

---

## Кандидаты на вынос в plugin system (future)

Эти модули могут стать плагинами, когда будет реализован plugin system (заморожен по ADR-0006).

| Модуль | Зачем выносить | Текущий статус |
|--------|----------------|----------------|
| `src/services/epf_factory.py` | EPF creation — нишевая функциональность | stable |
| `src/services/cfe_manager.py` | CFE extensions — только для extension-based dev | stable |
| `src/services/dsl_compiler.py` | 5 DSL компиляторов — для code generation | stable |
| `src/services/rag_pipeline.py` | RAG с Ollama — требует отдельной infra | experimental |
| `src/services/openspec_manager.py` | OpenSpec — methodology, не всем нужна | stable |

---

## CVE Monitoring

Проект использует:
- `pip-audit` — проверка зависимостей на CVE
- `safety` — vulnerability scanner
- `.github/workflows/sast.yml` — SAST на каждый PR
- `.github/workflows/supply-chain.yml` — supply chain checks
- `src/services/cve_monitor.py` — мониторинг CVE через PyPI JSON API

См. ADR-0007 для workaround v8unpack (CVE не критический, но баг известный).

---

## License Compliance

Все зависимости проверены через `pip-licenses`:

| License | Количество | Совместимость |
|---------|------------|---------------|
| MIT | большинство | ✅ Commercial use OK |
| Apache 2.0 | tree-sitter-bsl, BSL LS | ✅ Commercial use OK |
| BSD-3 | networkx, pytest | ✅ Commercial use OK |
| MPL 2.0 | — | ✅ Commercial use OK |
| GPL | нет | — |

`v8unpack` — собственная лицензия saby-integration (разрешено использование).

---

## Обновление зависимостей

Dependabot настроен на monthly updates с limited PRs (см. `.github/dependabot.yml`).

Критичные обновления (security) — merge сразу.
Minor обновления — batch в один PR monthly.
Major обновления — отдельный ADR.

---

## Связанные ADR

- ADR-0006: Scope reduction v6 (заморозил SaaS/Enterprise/Plugin)
- ADR-0007: v8unpack workaround retention
- ADR-0009: Architecture refactor strategy (Phase 4.2)
- ADR-0010: Layered architecture with Protocol contracts (planned)
