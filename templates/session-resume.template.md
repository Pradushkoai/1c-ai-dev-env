# 📋 Резюме сессии

> Прочитай этот файл первым в новой сессии.

## ⚡ Быстрый старт

### Шаг 0: Проверить окружение
```bash
python3 -m src.cli validate
```

### Шаг 1: Прочитать контекст
1. `runtime/session-resume.md` (этот файл)
2. `runtime/soul.md` — персона + 3 принципа работы
3. `runtime/checklist.md` — чек-лист решения задач 1С (обязательно!)

### Шаг 2: Восстановить данные (если диск пересоздан)
```bash
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
python3 -m src.cli data release-pull   # скачать data-package
python3 -m src.cli data autoload       # восстановить 4 configs + BM25
python3 -m src.cli config list         # проверка: 4 конфигурации
```

## ⚠️ Как решать задачи 1С

При любой задаче по 1С-разработке — **обязательно** пройди чек-лист из
`runtime/checklist.md`. Это не ритуал, а проверяемые условия.

### Кратко: 3 принципа
1. **Уточни ТЗ** — не выдумывай реквизиты/методы/формы. Спроси.
2. **Используй репозиторий** — `search`, `solve_context`, `get_api_reference`
3. **Проверь результат** — `check_standards`, `solve_check --level full`

### 3 режима работы репозитория
| Режим | Кто агент | Когда |
|-------|-----------|-------|
| A. MCP-сервер | Cursor/Claude | Внешняя IDE |
| B. Прямая работа со мной | Я (LLM) | Сейчас |
| C. CLI напрямую | Пользователь | Без меня |

В режиме B — я агент, чек-лист мой процесс.

## 📊 Конфигурации (v3.14.0)

```bash
python3 -m src.cli config list
```

| Конфиг | Объектов | Модулей | Методов |
|--------|---------|---------|---------|
| edo2   | 2353    | 1473    | 22 506 |
| edo3   | 2561    | 1646    | 24 266 |
| ut11   | 1937    | 1118    | 15 809 |
| unp    | 5630    | 3182    | 53 085 |

Платформа 1С: 8141 методов (BM25 индекс)

## 🧰 Команды

```bash
# Конфигурации
python3 -m src.cli config list
python3 -m src.cli config add --name X --cf Y.cf --title "T"
python3 -m src.cli config build --name X

# Поиск (BM25)
python3 -m src.cli search "найти элемент по коду"

# Анализ .bsl
python3 -m src.cli bsl analyze <path>
python3 -m src.cli standards <path>

# Решение задач (использует чек-лист!)
python3 -m src.cli solve context "задача" --config ut11
python3 -m src.cli solve check <file.bsl> --level full

# MCP-сервер (для IDE)
python3 -m src.cli mcp serve
python3 -m src.cli mcp tools

# Данные
python3 -m src.cli data status
python3 -m src.cli data autosave --include-raw
python3 -m src.cli data autoload
python3 -m src.cli data release-push / release-pull / release-status
```

## 📚 Документация
- `runtime/checklist.md` — чек-лист решения задач 1С (ОБЯЗАТЕЛЬНО)
- `docs/ARCHITECTURE.md` — 4-слойная архитектура проекта
- `docs/MCP_INTEGRATION.md` — подключение к IDE (режим A)
- `CHANGELOG.md` — история версий (v3.14.0 — последняя)
