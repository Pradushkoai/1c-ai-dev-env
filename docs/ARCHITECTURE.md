# Архитектура

## Обзор

Проект использует **4-слойную архитектуру** с чётким разделением ответственности:

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
│      ├── syntax-helper-index.json (8141 методов)  │
│      └── fast-search-index.json (BM25 v2)         │
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
├── models/                Конфигурация как данные
│   ├── configuration.py   Configuration dataclass
│   └── config_registry.py ConfigurationRegistry (CRUD)
├── services/              Бизнес-логика
│   ├── path_manager.py    PathManager (вместо paths.py)
│   ├── config_manager.py  add/activate/archive/build
│   ├── bsl_analyzer.py    BSL LS wrapper + baseline/diff
│   ├── search.py          TF-IDF поиск (legacy v1)
│   ├── search_bm25.py     BM25 + триграммы + стеммер (v2)
│   ├── data_package.py    Persistence (autosave/autoload)
│   └── github_releases.py Push/pull через GitHub REST API
├── mcp_server.py          MCP-сервер (27 tools)
├── project.py             Project — оркестратор
├── cli.py                 Единый CLI
└── exceptions.py          Кастомные исключения
```

### Принципы

1. **Одна ответственность — один модуль**. Логика BM25 не дублируется между
   `cli.py` и `fast_search_1c.py` — обе точки вызывают `src.services.search_bm25`
2. **Read-only в MCP**. MCP-сервер только читает готовые индексы, не загружает данные
3. **CLI = admin**. Загрузка, индексация, backup делаются через CLI
4. **MCP = аналитика**. Поиск, проверка, сбор контекста

## Жизненный цикл данных

```
ПОЛЬЗОВАТЕЛЬ ДАЁТ            СКРИПТЫ ГЕНЕРИРУЮТ
                             │
data/configs/ut11/    ────→  derived/configs/ut11/
  (распакованный .cf)          ├── api-reference.json (экспортные методы)
                              ├── api-reference.md
                              └── index.md (индекс метаданных)

data/hbk/*.hbk        ────→  derived/platform/
                              ├── syntax-helper/ (распакованные HTML)
                              ├── syntax-helper-index.json (8141 методов)
                              └── fast-search-index.json (BM25 v2)
```

## Алгоритмы поиска

### BM25 + триграммы + стеммер (v2, по умолчанию)

Файл: `src/services/search_bm25.py`

- **BM25** (k1=1.5, b=0.75) — золотой стандарт полнотекстового поиска
  - Учитывает насыщение TF (saturation)
  - Нормализует длину документа
- **Стеммер** для русского и английского (без внешних зависимостей)
  - Обрезает окончания: "поиска" → "поиск", "searching" → "search"
- **Триграммы** с Жаккар-сходством — устойчивость к опечаткам
  - "найтипокоду" находит "НайтиПоКоду"
- **Гибридный режим**: 0.75 × BM25 + 0.25 × триграммы

### TF-IDF (v1, legacy)

Файл: `src/services/search.py`

- Косинусное сходство с инвертированным индексом
- Сохранён для обратной совместимости
- `search_auto()` выбирает алгоритм по версии индекса

### Сравнение на реальных данных

Запрос: "найти элемент справочника по коду"

| Алгоритм | Топ-1 | Score |
|----------|-------|-------|
| BM25 | `НайтиПоКоду` (CatalogManager) | 0.951 ✅ |
| TF-IDF | `Найти` (общий метод) | 0.278 ❌ |

## Управление конфигурациями

```bash
# Добавить конфигурацию из .cf (через cf_extractor)
1c-ai config add --name ut11 --cf ut11.cf --title "УТ 11" --skip-build
1c-ai config build --name ut11

# Добавить из ZIP выгрузки Конфигуратора
1c-ai config add --name erp --zip erp.zip --title "1С:ERP"

# Все индексы
1c-ai config build-all

# Список
1c-ai config list
```

### Формат метаданных 1С

`v8_metadata_parser.py` поддерживает два формата .cf:

- **V1 (классический, 8.2)**: `TYPE_MAP_V1` — Code 4=CommonModule, 17=Catalog, 18=Document
- **V2 (современный, 8.3.24+)**: `TYPE_MAP_V2` — Code 12=CommonModule, 20=Catalog, 40=Document

V2 установлен на основе анализа реальных .cf файлов. Сдвиг кодов произошёл
из-за добавления новых типов объектов в 1С 8.3.24+.

## Persistence данных

### Проблема
В облачных средах диск может пересоздаваться между сессиями —
`data/` и `derived/` теряются. `runtime/` (в git) сохраняется.

### Решение: DataPackage + GitHub Releases

```bash
# 1. Сохранить всё в ZIP
1c-ai data autosave --include-raw
# → download/1c-ai-data-package.zip
# → включает manifest.json + runtime/ + derived/ + data/

# 2. Загрузить в GitHub Release
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-push

# 3. В новой сессии — восстановить
1c-ai data release-pull   # скачать
1c-ai data autoload       # распаковать
```

### Структура пакета

```
data-package/
├── manifest.json                  метаданные (версия, дата, конфиги, размер)
├── runtime/
│   └── config-registry.json       реестр конфигураций
├── derived/
│   ├── configs/<name>/            индексы (api-reference.json, index.md)
│   └── platform/                  BM25 индекс + syntax-helper
└── data/                          (опционально, --include-raw)
    └── configs/<name>/            распакованные конфигурации
```

## MCP-сервер

Файл: `src/mcp_server.py`

Экспортирует **27 tools** через Model Context Protocol:

| Tool | Назначение |
|------|-----------|
| `list_configs` | Список загруженных конфигураций |
| `search_1c_methods` | BM25 поиск по методам платформы |
| `get_api_reference` | API-справочник конфигурации |
| `analyze_bsl` | BSL LS анализ (187 диагностик) |
| `check_standards` | 56 правил стандартов 1С |
| `solve_context` | Сбор контекста для задачи |
| `solve_check` | Полная проверка .bsl кода |
| `data_status` | Статус данных проекта |

Подробнее: [docs/MCP_INTEGRATION.md](MCP_INTEGRATION.md)

## Единый конфиг путей

**Основной источник:** `src/services/path_manager.py` — `PathManager` (OOP).
Используется во всём коде приложения.

**Legacy:** `runtime/paths.py` — процедурная обёртка над `paths.env`,
помечена как `@deprecated`, оставлена для обратной совместимости
со старыми скриптами.

**Для shell-скриптов:** `runtime/paths.env` (загружается через `dotenv`).

При переносе в другую среду — изменить только `PROJECT_ROOT` в `paths.env`
или передать `project_root` в `PathManager(project_root=...)`.

## Тесты

314 тестов покрывают все ключевые компоненты:

```
tests/
├── test_path_manager.py          PathManager
├── test_config_manager.py        ConfigManager (add/build/archive)
├── test_configuration.py         Configuration model
├── test_bsl_analyzer.py          BSL LS wrapper (mock subprocess)
├── test_search_bm25.py           BM25 + триграммы + стеммер
├── test_fast_search.py           TF-IDF (legacy)
├── test_cf_extractor.py          cf_extractor (32 + 64 бита)
├── test_v8_metadata_parser.py    V2 type map
├── test_data_package.py          DataPackage persistence
├── test_github_releases.py       GitHub Releases (mock subprocess)
├── test_check_standards.py       56 правил check_1c_standards
├── test_metadata_standards.py    18 правил check_metadata_standards
├── test_project_api.py           API-методы Project
├── test_mcp_server.py            MCP-сервер (27 tools)
├── test_solve.py                 solve context/check
├── test_backup_manager.py        backup/restore
└── test_integration.py           интеграционные тесты с BSL LS
```
