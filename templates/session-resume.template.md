# 📋 Резюме сессии

> Прочитай этот файл первым в новой сессии.

## ⚡ Быстрый старт

### Шаг 0: Проверить окружение
```bash
python3 -m src.cli validate
```

### Шаг 1: Прочитать контекст
1. `runtime/session-resume.md` (этот файл)
2. `runtime/soul.md` — персона + 2 принципа работы

### Шаг 2: Восстановить данные (если диск пересоздан)
```bash
export GITHUB_TOKEN=ghp_xxx
python3 -m src.cli data release-pull   # скачать data-package
python3 -m src.cli data autoload       # восстановить 4 configs + BM25
python3 -m src.cli config list         # проверка: 4 конфигурации
```

## 📊 Конфигурации (v3.14.1)

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

# Решение задач
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
- `docs/ARCHITECTURE.md` — 4-слойная архитектура проекта
- `docs/MCP_INTEGRATION.md` — подключение к IDE
- `CHANGELOG.md` — история версий (v3.14.1 — последняя)
