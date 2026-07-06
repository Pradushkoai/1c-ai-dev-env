# Quick Start (5 минут)

> Быстрый старт для новых разработчиков. S6 (план v3).

## 1. Установка (2 минуты)

```bash
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env
pip install -e ".[dev,mcp]"
```

## 2. Проверка (1 минута)

```bash
1c-ai validate
```

## 3. Первый запуск MCP (1 минута)

```bash
# Запуск MCP сервера (для Cursor/Claude)
1c-ai mcp serve

# В другом терминале — проверка
1c-ai mcp tools  # должен показать 45 tools
```

## 4. Тесты (1 минута)

```bash
pytest tests/ --cov=src --cov-fail-under=70 -q --no-header \
  --ignore=tests/test_benchmarks.py --ignore=tests/test_e2e.py \
  --ignore=tests/test_integration.py -p no:cacheprovider
```

## Готово!

Проект установлен и работает. Дальше:
- [README.md](../README.md) — полный обзор
- [AGENTS.md](../AGENTS.md) — правила для AI-агентов
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура
- [MCP_INTEGRATION.md](MCP_INTEGRATION.md) — подключение к IDE
- [adr/](../adr/) — Architecture Decision Records
