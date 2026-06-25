# Архитектура: 4-слойная модель

## Обзор

Проект использует 4-слойную архитектуру с чётким разделением ответственности:

```
┌──────────────────────────────────────────────────┐
│  data/          ИСХОДНЫЕ ДАННЫЕ (от пользователя) │
│  ├── configs/   Конфигурации 1С (распакованные)   │
│  ├── archives/  ZIP архивы                        │
│  └── hbk/       Исходные .hbk файлы               │
├──────────────────────────────────────────────────┤
│  derived/       ПРОИЗВОДНЫЕ (генерируются)         │
│  ├── configs/   Индексы по конфигурациям          │
│  │   └── <name>/ index.md, api-reference.md/json  │
│  └── platform/  Индексы платформы 1С              │
│      ├── syntax-helper/   Распакованные .hbk      │
│      ├── syntax-helper-index.json                 │
│      └── fast-search-index.json                   │
├──────────────────────────────────────────────────┤
│  tools/         ИНСТРУМЕНТЫ                        │
│  ├── repos/     16 git репозиториев (форки)       │
│  └── bsl-ls/    BSL Language Server binary        │
├──────────────────────────────────────────────────┤
│  runtime/       ФАЙЛЫ РАБОТЫ                       │
│  ├── paths.env          Конфиг путей              │
│  ├── paths.py           Python-модуль путей       │
│  ├── config-registry.json  Реестр конфигов        │
│  ├── session-resume.md  Точка входа               │
│  ├── soul.md            Персона ассистента        │
│  ├── user-profile.md    Профиль пользователя      │
│  └── worklog.md         Журнал работы             │
└──────────────────────────────────────────────────┘
```

## Принципы

1. **data/ не изменяется скриптами** — только чтение
2. **derived/ полностью генерируется** — можно удалить и пересоздать
3. **tools/ клонируется install.sh** — не хранится в git
4. **runtime/ — рабочие файлы** — session-resume, worklog, paths

## Жизненный цикл

```
ПОЛЬЗОВАТЕЛЬ ДАЁТ        СКРИПТЫ ГЕНЕРИРУЮТ
                         │
data/configs/ut11/  ────→ derived/configs/ut11/index.md
                         derived/configs/ut11/api-reference.md
                         
data/hbk/*.hbk      ────→ derived/platform/syntax-helper/
                         derived/platform/syntax-helper-index.json
                         derived/platform/fast-search-index.json
```

## Управление конфигурациями

```bash
# Добавить новую конфигурацию
python3 scripts/register_config.py add --name erp --zip erp.zip --title "1С:ERP"
# → data/configs/erp/ (распаковка)
# → runtime/config-registry.json (регистрация)
# → derived/configs/erp/index.md (индекс)
# → derived/configs/erp/api-reference.md (API)

# Все индексы
python3 scripts/register_config.py build-all

# Список
python3 scripts/register_config.py list
```

## Единый конфиг путей

`runtime/paths.env` — для shell-скриптов
`runtime/paths.py` — для Python-скриптов

При переносе в другую среду — изменить только `PROJECT_ROOT` в `paths.env`.
