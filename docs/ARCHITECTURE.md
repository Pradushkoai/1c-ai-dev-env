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
│  ├── repos/     15 git репозиториев (форки)       │
│  └── bsl-ls/    BSL Language Server binary        │
├──────────────────────────────────────────────────┤
│  runtime/       ФАЙЛЫ РАБОТЫ                       │
│  ├── paths.env          Конфиг путей (shell)       │
│  ├── paths.py           Legacy Python-модуль (⚠)   │
│  ├── config-registry.json  Реестр конфигов        │
│  ├── session-resume.md  Точка входа               │
│  ├── soul.md            Персона ассистента        │
│  ├── user-profile.md    Профиль пользователя      │
│  └── worklog.md         Журнал работы             │
└──────────────────────────────────────────────────┘
```

## OOP-слой (src/)

Поверх 4-слойной файловой структуры работает Python-пакет `src/`:

```
src/
├── models/         Конфигурация как данные
│   ├── configuration.py      Configuration dataclass
│   └── config_registry.py    ConfigurationRegistry
├── services/       Бизнес-логика
│   ├── path_manager.py       PathManager (вместо paths.py)
│   ├── config_manager.py     add/activate/archive/build
│   ├── bsl_analyzer.py       BSL LS wrapper + baseline/diff
│   └── search.py             TF-IDF поиск (единственная реализация)
├── project.py      Project — оркестратор
└── cli.py          Единый CLI: config, bsl, validate, search
```

Принцип: **одна ответственность — один модуль**. Логика TF-IDF
не дублируется между `cli.py` и `fast_search_1c.py` — обе точки
вызывают `src.services.search`.

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

**Основной источник:** `src/services/path_manager.py` — `PathManager` (OOP).
Используется во всём коде приложения (`src/cli.py`, `src/project.py`, сервисах).

**Legacy:** `runtime/paths.py` — процедурная обёртка над `paths.env`,
помечена как `@deprecated`, оставлена только для обратной совместимости
со старыми скриптами. Новый код должен использовать `PathManager`.

**Для shell-скриптов:** `runtime/paths.env` (загружается через `dotenv`).

При переносе в другую среду — изменить только `PROJECT_ROOT` в `paths.env`
или передать `project_root` в `PathManager(project_root=...)`.
