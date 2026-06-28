# 📋 Резюме сессии

> Заполняется после install.sh. Прочитай этот файл первым в новой сессии.

## ⚡ Быстрый старт

### Шаг 0: Проверить окружение
```bash
python3 -m src.cli validate
```

### Шаг 1: Прочитать контекст
1. `runtime/session-resume.md` (этот файл)
2. `runtime/soul.md` — персона + **обязательный протокол задач 1С**
3. `runtime/user-profile.md` — профиль пользователя
4. `docs/TASK_PROTOCOL.md` — полная спецификация 5 ролей

### Шаг 2: Восстановить данные (если диск пересоздан)
```bash
export GITHUB_TOKEN=ghp_xxx
python3 -m src.cli data release-pull   # скачать data-package
python3 -m src.cli data autoload       # восстановить 4 configs + BM25
python3 -m src.cli config list         # проверка: 4 конфигурации
```

## ⚠️ Обязательный протокол задач 1С

**При любой задаче по 1С-разработке** — соблюдаю протокол из `docs/TASK_PROTOCOL.md`:

```
🧠 Архитектор     → solve_context, проектирование
👨‍💻 Программист   → .bsl код по плану
🎨 Стилист        → check_standards + analyze_bsl
📝 Документатор   → docstring + examples
✅ Проверяющий     → solve_check --level full + verdict
```

### 3 протокола запуска
| Тип | Роли |
|------|------|
| **A. Полный** (фича, рефакторинг) | 🧠 → 👨‍💻 → 🎨 → 📝 → ✅ |
| **B. Стандартный** (bugfix) | 👨‍💻 → 🎨 → ✅ |
| **C. Быстрый** (опечатка) | 👨‍💻 → ✅ |

### Алгоритм при получении задачи
1. Определить: задача по 1С? → применить протокол
2. Объявить протокол и роли
3. Выполнить каждую роль с объявлением: `🧠 [Архитектор] ...`
4. Финальный отчёт Проверяющего с verdict

**Критически:** НЕ писать код сразу. Сначала Архитектор и `solve_context`.

## 📊 Конфигурации (v3.12.0)

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
python3 -m src.cli bsl baseline <path>
python3 -m src.cli bsl diff <path>

# Стандарты (56 правил, без Java)
python3 -m src.cli standards <path>

# Решение задач (использует протокол ролей!)
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
- `docs/TASK_PROTOCOL.md` — протокол 5 ролей для задач 1С
- `docs/ARCHITECTURE.md` — 4-слойная архитектура проекта
- `docs/MCP_INTEGRATION.md` — подключение к IDE
- `CHANGELOG.md` — история версий (v3.12.0 — последняя)
