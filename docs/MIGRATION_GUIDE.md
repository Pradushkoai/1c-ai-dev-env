# Migration Guide: v5.4.0 → v6.0.0

> Руководство по обновлению с v5.4.0 до v6.0.0.
> S7 (план v3: Post-v6.0 Strategic Roadmap).

## Обзор

v6.0.0 — major release. Проект перешёл от Beta к Production-ready.
19 из 20 задач плана v2 (Solo Edition) выполнены.

## Breaking Changes

### 1. install.sh: обязательная целевая директория

**Было (v5.4.0):**
```bash
./install.sh  # использовал дефолт /home/z/my-project
```

**Стало (v6.0.0):**
```bash
./install.sh --target /path/to/project
# или
export ONEC_AI_DEV_ENV_ROOT=/path/to/project
./install.sh
```

Хардкод `/home/z/my-project` удалён. Целевая директория обязательна.

### 2. MCP tools: 45 tools (было 29 в статическом описании)

Статическое описание `_get_tools_description()` синхронизировано с `list_tools` handler.
Оба теперь возвращают 45 tools. CI блокирует рассинхронизацию.

### 3. mypy strict: disallow_untyped_defs для всех модулей

Все функции в `src/` должны иметь type annotations. CI blocking.

### 4. Coverage gate: 70% (было 30→50%)

CI требует минимум 70% coverage.

### 5. Complexity gate: baseline 14 D+ функций

CI блокирует добавление новых функций с cyclomatic complexity ≥ D (16+).

## Новые возможности

### Extras (optional dependencies)

```bash
# Векторный поиск (BM25 + vector)
pip install -e ".[rag]"  # fastembed + qdrant-client

# Prometheus metrics
pip install -e ".[metrics]"  # prometheus-client

# Всё вместе
pip install -e ".[dev,mcp,rag,metrics]"
```

### Векторный поиск (P1.1)

```bash
# С extras [rag] — гибридный BM25+vector
# Без extras [rag] — чистый BM25 (fallback автоматически)
```

### Prometheus metrics (P1.5)

```bash
# Запуск MCP сервера с /metrics endpoint
MCP_METRICS_PORT=8001 1c-ai mcp serve
```

### Snapshot testing (P1.6)

```bash
# Обновить snapshot при намеренном изменении MCP tools
pytest tests/test_mcp_tools_snapshot.py --snapshot-update
```

### EDT формат (P2.1)

```python
from src.services.edt_parser import EdtParser
parser = EdtParser()
objects = parser.parse("/path/to/edt/project")
```

### Sphinx документация (P2.6)

```bash
# Сгенерировать HTML документацию из docstring
sphinx-build -b html docs/sphinx/ docs/sphinx/_build/html
```

## Миграция

### Шаг 1: Обновление

```bash
git pull origin main
pip install -e ".[dev,mcp]"
```

### Шаг 2: Проверка

```bash
1c-ai validate
pytest tests/ --cov=src --cov-fail-under=70 -q
```

### Шаг 3: install.sh (если используется)

```bash
export ONEC_AI_DEV_ENV_ROOT=/your/project/path
./install.sh --target /your/project/path
```

### Шаг 4: Опциональные extras

```bash
pip install -e ".[rag,metrics]"  # векторный поиск + metrics
```

## Совместимость

| Компонент | v5.4.0 | v6.0.0 | Совместимость |
|-----------|--------|--------|---------------|
| MCP tools | 45 (handler), 29 (static) | 45 = 45 | ✅ Синхронизированы |
| CLI команды | 19 | 19 | ✅ Без изменений |
| BSL анализаторы | 11 | 11 | ✅ Без изменений |
| DSL компиляторы | 5 | 5 | ✅ Без изменений |
| API (Python) | — | — | ✅ Обратная совместимость |
| install.sh | /home/z/my-project хардкод | --target / env var | ⚠️ Breaking |
| Coverage gate | 50% | 70% | ⚠️ Строже |
| mypy | non-blocking | blocking (strict) | ⚠️ Строже |

## Откат

Если v6.0.0 вызывает проблемы:

```bash
git checkout v5.4.0
pip install -e ".[dev,mcp]"
```

## Поддержка

- Issues: https://github.com/Pradushkoai/1c-ai-dev-env/issues
- CHANGELOG: CHANGELOG.md
- Architecture: docs/ARCHITECTURE.md
