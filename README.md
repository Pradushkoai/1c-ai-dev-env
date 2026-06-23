# 1C AI Development Environment

Среда разработки 1С с ИИ-ассистентом. Включает:
- 8 141 методов платформы 1С (синтакс-помощник)
- 16 654+ методов API типовых конфигураций (УТ11, УНП)
- BSL Language Server для анализа .bsl кода
- 94 скила для создания объектов/форм/расширений через JSON DSL
- TF-IDF семантический поиск
- 355 проверок качества кода (BSL LS + EDT-MCP)

## Быстрый старт

```bash
# 1. Клонировать
git clone <repo-url> && cd 1c-ai-dev-env

# 2. Установить
./setup/install.sh

# 3. Добавить конфигурацию (ZIP выгрузки)
./scripts/add_config.sh <google_drive_file_id> <name> "Title"

# 4. Распаковать .hbk синтакс-помощника
python3 scripts/hbk_extractor.py 'upload/*.hbk' syntax-helper

# 5. Построить индексы
python3 scripts/build_syntax_helper_index.py
python3 scripts/fast_search_1c.py build
```

## Структура

```
setup/          — что коммитить в GitHub (скрипты, конфиги, manifest)
config/         — выгрузка конфигурации пользователя
syntax/         — клонированные репозитории (ai_rules_1c, bsl-ls, и т.д.)
syntax-helper/  — распакованные .hbk файлы
indexes/        — сгенерированные индексы
learned-skills/ — auto-created skills (learning loop)
user-profile.md — профиль пользователя
soul.md         — персона ассистента
```

## Фичи из Hermes Agent

- **Learning loop** — после задач создаём skills в `learned-skills/`
- **LSP diff** — `bsl-analyze.sh --diff` показывает только новые ошибки
- **USER.md / SOUL.md** — `user-profile.md` + `soul.md`
- **Memory prefetch** — перед задачей grep worklog

## Лицензия

MIT
