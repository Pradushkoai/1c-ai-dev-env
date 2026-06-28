# Changelog

## [3.14.0] — 2026-06-29

### Замена 5 ролей на чек-лист (проверяемые условия)

**Проблема:** протокол 5 ролей (v3.13.0) превратился в ритуал.
Ассистент объявлял роли, но не использовал их результаты —
генерировал код с выдуманными реквизитами, «проходил» все 5 ролей
формально, игнорировал errors от check_standards.

**Решение:** заменить формальные роли на **чек-лист с бинарными условиями**.

#### Что удалено:
- `docs/TASK_PROTOCOL.md` (5 ролей с целями/чек-листами/артефактами)
- `templates/task-roles/` (5 шаблонов ролей)
- `templates/role-switching-protocol.template.md` (3 протокола A/B/C)

#### Что добавлено:
- `templates/checklist.template.md` — 5 фаз с проверяемыми условиями:
  1. **Понимание задачи** — ТЗ полное? (если ❌ — спросить, не выдумывать)
  2. **Контекст** — solve_context, search, get_api_reference вызваны
  3. **Реализация** — код по ТЗ, методы из контекста
  4. **Проверка** — `check_standards: 0 errors`, `solve_check: verdict ∈ {ready, warnings}`
  5. **Документация** — docstring + примеры

- `templates/soul.template.md` — короткая персона с 3 принципами:
  1. Уточни ТЗ (не выдумывай)
  2. Используй репозиторий (search, solve_context, get_api_reference)
  3. Проверь результат (check_standards, solve_check)

#### Что обновлено:
- `templates/session-resume.template.md` — ссылка на checklist вместо TASK_PROTOCOL
- `README.md` — секции «3 режима использования» + «Чек-лист решения задач 1С»
- `pyproject.toml` — version 3.14.0

### 3 режима использования репозитория

Зафиксировано разделение 3 режимов:
- **A. MCP-сервер** — Cursor/Claude подключается к mcp_server.py (8 tools)
- **B. Прямая работа с LLM** — ассистент в чате, использует CLI как инструменты
- **C. CLI напрямую** — пользователь сам запускает 1c-ai команды

В режиме B ассистент следует чек-листу из `runtime/checklist.md`.

### Как передать контекст в новый чат

В новой сессии сказать ассистенту:
> «Прочитай `runtime/soul.md` и `runtime/checklist.md`»

После этого ассистент знает 3 принципа и 5 фаз чек-листа.

## [3.13.0] — 2026-06-28

### Протокол 5 ролей для решения задач 1С

При работе с ассистентом над задачей 1С (создать справочник, написать обработку, доработать модуль) — ассистент соблюдает **обязательный протокол 5 ролей**.

**5 ролей:**
- 🧠 **Архитектор** — `solve_context`, проектирование, план (метаданные, модули, методы платформы, стандарты)
- 👨‍💻 **Программист** — `.bsl` код по плану Архитектора
- 🎨 **Стилист** — `check_standards` (56 правил) + `analyze_bsl` (187 диагностик) + читаемость
- 📝 **Документатор** — docstring + примеры использования
- ✅ **Проверяющий** — `solve_check --level full` + regression + verdict

**3 протокола запуска:**
| Протокол | Триггер | Роли |
|----------|---------|------|
| A. Полный | Новая фича, рефакторинг, доработка типовой | 🧠 → 👨‍💻 → 🎨 → 📝 → ✅ |
| B. Стандартный | Bugfix, небольшая доработка | 👨‍💻 → 🎨 → ✅ |
| C. Быстрый | Опечатка, переименование | 👨‍💻 → ✅ |

**Новые файлы:**
- `docs/TASK_PROTOCOL.md` — полная спецификация (цели, чек-листы, артефакты, запреты, anti-patterns)
- `templates/task-roles/architect-plan.md` — шаблон плана Архитектора
- `templates/task-roles/programmer-code.md` — шаблон кода Программиста
- `templates/task-roles/stylist-checklist.md` — чек-лист Стилиста
- `templates/task-roles/documentator-template.md` — шаблон Документатора
- `templates/task-roles/verifier-report.md` — шаблон отчёта Проверяющего

**Обновлены:**
- `templates/soul.template.md` — обязательный протокол при задачах 1С
- `templates/session-resume.template.md` — протокол первым шагом
- `templates/role-switching-protocol.template.md` — 5 ролей + 3 протокола
- `runtime/soul.md`, `runtime/session-resume.md`, `runtime/role-switching-protocol.md` — актуальные копии
- `README.md` — секция «Протокол решения задач 1С»
- `pyproject.toml` — version 3.13.0

**Критические правила:**
- НЕ писать код сразу — сначала Архитектор и `solve_context`
- НЕ использовать методы платформы по памяти — только из контекста
- НЕ пропускать роли — даже для быстрой задачи
- НЕ игнорировать `verdict: errors` — возвращать Программисту
- Каждая роль объявляется явно: `🧠 [Архитектор] Анализирую...`

**Применение:** протокол работает в режиме прямого общения с ассистентом (чат, IDE с system prompt). Для MCP-режима (Cursor/Claude) LLM оркеструет сама, протокол служит ориентиром.

## [3.12.0] — 2026-06-28

### Все 4 конфигурации полностью извлечены

После исправления v8_metadata_parser (V2 type map в v3.11.0) все 4 конфигурации
теперь извлекаются полностью — с BSL модулями и экспортными методами.

**Итоговая статистика:**
| Конфигурация | Объектов | Модулей | Методов |
|--------------|---------|---------|---------|
| edo2         | 2353    | 1473    | 22506   |
| edo3         | 2561    | 1646    | 24266   |
| ut11         | 1937    | 1118    | 15809   |
| unp          | 5630    | 3182    | 53085   |
| **Итого**    | **12481** | **7419** | **115666** |

Плюс платформа 1С: 8141 методов (BM25 индекс, 11.7 МБ)

**DataPackage:**
- Размер: 146.2 МБ (было 59 МБ)
- Файлов: 60191
- Содержит: 4 конфигурации (data/configs/) + индексы (derived/) + платформа (derived/platform/)
- GitHub Release: https://github.com/Pradushkoai/1c-ai-dev-env/releases/tag/data-package

**MCP tools работают:**
- `list_configs` → 4 конфигурации
- `search_1c_methods` → BM25 по 8141 методам платформы
- `get_api_reference` → 115666 методов в 7419 модулях
- `data_status` → полный статус данных

**Workflow восстановления (для следующей сессии):**
```bash
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-pull     # скачать 146 МБ
1c-ai data autoload         # восстановить 4 configs + BM25
1c-ai config list           # 4 конфигурации
1c-ai search "найти элемент по коду"  # BM25 поиск
```

## [3.11.0] — 2026-06-28

### Полное извлечение объектов из .cf — v8_metadata_parser V2

Проблема: `cf_extractor` извлекал только 50 объектов из УТ11 (должно ~5440), потому что
`TYPE_MAP` в `v8_metadata_parser.py` использовала классические коды типов 1С (8.2),
а современные .cf файлы (8.3.24+) используют сдвинутые коды.

**Анализ реальных данных:**
- Code 12 = CommonModule (не Role как в V1) — 1232 объекта в УТ11
- Code 17 = DataProcessor (не Catalog)
- Code 20 = Catalog (не AccumulationRegister)
- Code 40 = Document (не WSReference)
- Code 14 = FunctionalOption (имена "Использовать...")
- Code 56, 57 = Catalog (подтипы)
- Code 19, 33 = InformationRegister (два подтипа)

**Изменения в `scripts/v8_metadata_parser.py`:**
- Новая `TYPE_MAP_V2` — карта кодов современного формата (8.3.24+)
- `TYPE_MAP_V1` сохранена для обратной совместимости со старыми .cf
- `detect_type_by_content()` — выбирает V2 → V1 → Unknown
- `re.match` вместо `re.search` для type code (избегает ложных срабатываний на sub-объектах)
- Поддержка двух паттернов имён:
  - `{1,0,UUID},"Name"` — стандартный (CommonModule, Catalog, Document, ...)
  - `{0,0,UUID},"Name"` — альтернативный (FunctionalOption, Constant, ...)
- Пропуск объектов без имени (sub-объекты: формы, команды)

**Изменения в `scripts/cf_to_xml_adapter.py`:**
- Сохранение BSL модулей для всех типов объектов (не только CommonModules)
- Поддержка ключа 'Module' (V2) в дополнение к 'ObjectModule' (V1)
- Сохранение ObjectModule.bsl + ManagerModule.bsl для Catalog/Document/etc.

**Реальные результаты:**
| Конфигурация | Было объектов | Стало объектов | Модулей | Методов |
|--------------|--------------|---------------|---------|---------|
| ut11         | 50           | 10089         | 1118    | 15809   |
| edo3         | 218          | 2561          | 1646    | 24266   |
| edo2         | 240          | 2353          | 1473    | 22506   |
| unp          | 659          | (в процессе)  | —       | —       |

**Тесты:**
- tests/test_v8_metadata_parser.py — переписаны под V2 (17 тестов)
- Покрытие: TYPE_MAP_V2, TYPE_MAP_V1, парсинг обоих паттернов имён,
  пропуск sub-объектов, unknown type codes
- Всего: 314 (было 311)

**DataPackage обновлён:**
- 59.4 МБ, 22398 файлов
- Конфигурации: edo2 (24266 methods) + edo3 (22506 methods) + BM25 platform index (8141 methods)
- ut11 и unp требуют повторного извлечения (см. следующий шаг)

### Следующие шаги (для следующей сессии)
1. Скачать .cf файлы (ut11, unp) из Google Drive
2. Извлечь через `1c-ai config add --cf X.cf --skip-build` + `1c-ai config build --name X`
3. `1c-ai data autosave --include-raw` — обновить пакет
4. `1c-ai data release-push` — загрузить в GitHub Releases

## [3.10.0] — 2026-06-28

### GitHub Releases integration — Фаза 3 завершена

**Новый сервис `src/services/github_releases.py`:**
- `GitHubReleases.push()` — загрузить data-package ZIP в GitHub Release
- `GitHubReleases.pull()` — скачать пакет из Release
- `GitHubReleases.status()` — статус интеграции
- `GitHubReleases.get_release()` / `list_releases()` — информация о релизах
- Авто-определение repo из `git remote origin`
- Использует REST API через `curl` (не требует `gh` CLI)
- Поддержка обновления существующих релизов (старые assets удаляются)

**CLI команды (`1c-ai data release-*`):**
- `1c-ai data release-push [--body TEXT]` — загрузить autosave пакет
- `1c-ai data release-pull` — скачать в download/
- `1c-ai data release-status` — статус интеграции

**Workflow для восстановления после пересоздания диска:**
```bash
# 1. Установить токен (один раз за сессию)
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>

# 2. Скачать пакет (39 МБ, 7 сек)
1c-ai data release-pull

# 3. Восстановить данные (секунды)
1c-ai data autoload

# 4. Проверить
1c-ai data status
1c-ai search "найти элемент по коду"
```

**Тесты:**
- tests/test_github_releases.py — 24 теста (мок subprocess)
- Покрытие: detect_repo, get_release, push (new/existing), pull, status
- Всего: 311 (было 287)

### Реальные данные загружены

- 4 конфигурации 1С: edo2 (240 объектов), edo3 (218), ut11 (50), unp (659)
- Платформа 1С: 8141 методов, BM25 индекс (11.7 МБ, 2.2 сек построение)
- DataPackage: 39 МБ, 34758 файлов, autosave + GitHub Release
- Release URL: https://github.com/Pradushkoai/1c-ai-dev-env/releases/tag/data-package

### BM25 vs TF-IDF — реальное сравнение

Запрос: "найти элемент справочника по коду"
- BM25: топ-1 = `НайтиПоКоду` (score 0.951) — точно то что нужно
- TF-IDF: топ-1 = `Найти` (score 0.278) — общий метод, менее релевантный

Запрос: "выполнить запрос к базе"
- BM25: топ-1 = `Выполнить` (QueryBuilder, score 0.933)
- BM25: топ-5 включает `ВыполнитьПакет` (ExecuteBatch)

## [3.9.0] — 2026-06-28

### Persistence данных — DataPackage

Проблема: диск `/home/z/my-project/` пересоздаётся между сессиями — данные (`data/`, `derived/`) теряются, остаётся только `runtime/config-registry.json` (в git).

**Новый сервис `src/services/data_package.py`:**
- `DataPackage.save(zip_path, include_raw, include_derived)` — сохранить всё в один ZIP
- `DataPackage.load(zip_path)` — восстановить
- `DataPackage.info(zip_path)` — метаданные без распаковки
- `DataPackage.autosave()` / `DataPackage.autoload()` — стандартное место (`download/1c-ai-data-package.zip`)
- `DataPackage.status()` — что доступно, что нужно перестроить
- Манифест с метаданными (версия, дата, конфигурации, размер)

**CLI команды (`1c-ai data`):**
- `1c-ai data save-pkg [-o PATH] [--include-raw] [-d DESCRIPTION]` — сохранить
- `1c-ai data load-pkg PATH` — восстановить
- `1c-ai data info [PATH]` — информация о пакете
- `1c-ai data autosave [--include-raw] [-d DESCRIPTION]` — стандартное место
- `1c-ai data autoload` — восстановить из стандартного места
- `1c-ai data status` — статус данных проекта

**Новый MCP tool `data_status`:**
- Возвращает: has_platform_index, has_platform_methods, configs[], autosave_available
- Если есть autosave — показывает команду для восстановления (`1c-ai data autoload`)
- LLM может вызвать, чтобы понять почему `search_1c_methods`/`get_api_reference` возвращают пустые результаты

**Тесты:**
- tests/test_data_package.py — 27 тестов
- 1 новый MCP тест (data_status)
- Всего: 287 (было 259)

### Улучшенный поиск — BM25 + триграммы + стеммер (v3.8.0 ранее)

- BM25 (k1=1.5, b=0.75) — золотой стандарт полнотекстового поиска
- Простой стеммер для русского/английского (без зависимостей)
- Триграммы с Жаккар-сходством — устойчивость к опечаткам
- Гибридный режим: 0.75 * BM25 + 0.25 * триграммы
- Версионирование индекса (v1=TF-IDF, v2=BM25)
- Auto-detect: `search_auto()` выбирает алгоритм

## [3.7.0] — 2026-06-28

### MCP-сервер — интеграция с IDE/LLM (Cursor, Claude Desktop, VS Code, и т.д.)

**Новый модуль `src/mcp_server.py`** — экспортирует 7 tools через Model Context Protocol.

Tools:
- `list_configs` — список загруженных конфигураций 1С
- `search_1c_methods` — TF-IDF поиск по 8141 методам платформы
- `get_api_reference` — API-справочник общих модулей конфигурации
- `analyze_bsl` — анализ .bsl через BSL LS (187 диагностик)
- `check_standards` — проверка на 56 правил стандартов 1С
- `solve_context` — сбор контекста для решения задачи
- `solve_check` — полная проверка .bsl кода

**Новые CLI команды:**
- `1c-ai mcp serve` — запустить MCP-сервер (stdio)
- `1c-ai mcp tools` — вывести список доступных tools

**Новые API-методы Project (Фаза 0):**
- `Project.list_configs_info()` — список конфигураций с детальной инфой (api_methods_count, has_api)
- `Project.get_config_info(name)` — детальная инфа о конфигурации (включая modules)
- `Project.get_api_methods(config_name, module_name)` — экспортные методы конфигурации
- `Project.search_methods(query, limit)` — обёртка над TF-IDF поиском

**Уровни проверки `1c-ai solve check`:**
- `--level quick` — только check_1c_standards (без Java)
- `--level standard` — quick + BSL LS (по умолчанию)
- `--level full` — standard + check_metadata_standards

**Зависимости:**
- `mcp>=1.0.0` добавлен в `requirements-optional.txt`

**Тесты:**
- 28 новых тестов (12 для Project API + 16 для MCP-сервера)
- Всего: 220 тестов (было 192)

### Принципы MCP
- **Read-only**: MCP-сервер только читает готовые индексы
- **CLI = admin**: загрузка/индексация через `1c-ai config add/build`
- **MCP = аналитика**: поиск, проверка, сбор контекста
- **Любой MCP-клиент**: не привязан к конкретной IDE

## [3.6.0] — 2026-06-28

### v8unpack убран, type hints, исключения, Dockerfile

**Кастомные исключения:**
- `src/exceptions.py` — `ConfigNotFoundError`, `ConfigExistsError`, `BuildError`, `AnalysisError`
- Используются в `ConfigManager`, `BSLAnalyzer`

**Type hints:**
- `cli.py` — все функции имеют аннотации параметров и возвращаемых значений

**Dockerfile:**
- Базовый образ `python:3.12-slim`
- Установка Java 17 + BSL LS через multi-stage build
- ENTRYPOINT: `1c-ai`

**Удалён v8unpack:**
- Заменён на собственный `scripts/cf_extractor.py` (Container64 + многоконтейнерные .cf)

## [3.4.0] — 2026-06-27

### 13 правил из 1c-standards-claude-skill (всего 42 в check_1c_standards)

**Новые правила на основе SKILL.md из tools/repos/1c-standards-claude-skill:**

Клиент-серверное взаимодействие (STD 12):
- no-transaction-in-nacliente (error): НачатьТранзакцию в &НаКлиенте
- no-db-in-nacliente (error): обращение к БД в &НаКлиенте
- no-server-call-in-loop (warning): серверные вызовы в цикле
- no-opovestit-on-server (warning): ОповеститьОбИзменении на сервере

Структура модуля (STD 455):
- procedures-outside-regions (warning): процедуры вне #Область
- export-in-wrong-region (warning): экспортные процедуры не в ПрограммныйИнтерфейс
- no-doc-comment (warning): экспортные процедуры без документации

Безопасность (STD 13):
- no-privileged-mode-without-reason (warning): ПривилегированныйРежим без обоснования
- check-pravo-dostupa-before-write (warning): запись без проверки ПравоДоступа
- no-com-object-bypass (error): COMОбъект/ADODB — обход прав 1С

Запросы (STD 03):
- no-query-concat (warning): конкатенация строк вместо Запрос.УстановитьПараметр
- query-keywords-lowercase (warning): ключевые слова запроса не КАПСОМ

Именование:
- no-bool-negative-names (warning): булевы переменные с отрицанием (НеПроверен)

**Итого проверок: 247** (187 BSL LS + 42 check_1c_standards + 18 check_metadata_standards)

## [3.3.0] — 2026-06-27

### check_metadata_standards.py — проверка метаданных конфигурации

**Новый скрипт `scripts/check_metadata_standards.py`** — проверяет XML метаданные
конфигурации 1С (не .bsl файлы, а объекты метаданных).

**15 правил проверки метаданных:**

Configuration:
- empty-vendor: Vendor не указан (STD 16)
- empty-version: Version не указана (STD 16)
- empty-name-prefix: NamePrefix не указан (STD 01)
- empty-compatibility-mode: CompatibilityMode не указан (STD 01)
- non-russian-script: ScriptVariant != Russian (STD 04)

Объекты метаданных (все типы):
- empty-synonym: синоним не заполнен (STD 01)
- name-with-spaces: имя содержит пробелы (STD 01)
- name-starts-with-digit: имя начинается с цифры (STD 01)

Справочники (Catalog):
- catalog-no-check-unique: CheckUnique=false при наличии кода (STD 01)
- catalog-no-list-form: нет DefaultListForm (STD 01)
- catalog-no-object-form: нет DefaultObjectForm (STD 01)

Общие модули (CommonModule):
- module-no-comment: Comment не заполнен (STD 04)
- module-no-synonym: синоним не заполнен (STD 01)
- module-server-no-suffix: серверный модуль без суффикса 'Сервер' (STD 04)
- module-client-no-suffix: клиентский модуль без суффикса 'Клиент' (STD 04)
- module-servercall-no-suffix: ServerCall без суффикса 'ВызовСервера' (STD 04)

Документы (Document):
- document-no-list-form: нет DefaultListForm (STD 01)
- document-no-check-unique: CheckUnique=false при наличии номера (STD 01)

**Протестировано на priemka:** 8 warnings найдено (Vendor, NamePrefix, CheckUnique, формы, комментарии).

**Итого проверок: 234** (187 BSL LS + 29 check_1c_standards + 18 check_metadata_standards)

## [3.2.0] — 2026-06-27

### Расширение check_1c_standards.py — 7 правил для запросов (всего 29)

**Новые правила на основе стандартов ITS (разделы 01, 03, 04, 08):**

| # | Правило | Severity | Что проверяет |
|---|---------|----------|---------------|
| 23 | no-pereyti | error | Оператор Перейти запрещён (STD 456) |
| 24 | no-zapis-zhurnala | warning | ЗаписьЖурналаРегистрации без явной задачи (STD 456) |
| 25 | no-full-outer-join | warning | ПОЛНОЕ ВНЕШНЕЕ СОЕДИНЕНИЕ — ограничено (STD 03) |
| 26 | no-obyedinit-bez-vse | warning | ОБЪЕДИНИТЬ без ВСЕ — проверьте (STD 03) |
| 27 | no-query-without-alias | warning | Источники данных без псевдонима КАК (STD 03) |
| 28 | no-obmen-dannimi-bez-proverki | warning | ОбменДанными.Загрузка без проверки (STD 01) |
| 29 | no-predlozhenie-vnechn | warning | ПоказатьВопрос/ПоказатьПредупреждение (STD 08) |

**Улучшения no-dot-notation:**
- Добавлены исключения для имён таблиц в запросах (Справочник, Документ, РегистрСведений, и т.д.)
- Пропуск строк внутри текстов запросов (ВЫБРАТЬ, ИЗ, СОЕДИНЕНИЕ)

**Итого проверок: 216** (187 BSL LS + 29 check_1c_standards)

## [3.1.0] — 2026-06-27

### 1c-ai solve — автоматический цикл решения задачи с проверками

**Новая команда `1c-ai solve` с двумя подкомандами:**

**`1c-ai solve context "задача" --config ut11`**
Собирает контекст для LLM перед генерацией кода:
1. TF-IDF поиск методов платформы 1С (8141 методов)
2. API-справочник конфигурации (релятивные модули по запросу)
3. Стандарты 1С (27 разделов ITS, ключевые правила)
4. Антипаттерны (CRITICAL: Query in Loop, Dot Notation, и др.)
5. Инструкция по проверке после генерации

**`1c-ai solve check <file.bsl>`**
Проверяет сгенерированный код одной командой:
1. BSL Language Server — 187 диагностик (синтаксис, типы, архитектура)
2. check_1c_standards — 22 правила (стилистика, антипаттерны, стандарты ITS)
3. Итоговый отчёт: "✅ Готов к коммиту" / "⚠️ Есть warnings" / "❌ Есть errors"
4. Exit code: 1 если есть errors, 0 если чисто или только warnings

**Полный цикл решения задачи:**
```bash
# Шаг 1: собрать контекст
1c-ai solve context "создать справочник Товары" --config ut11

# Шаг 2: LLM генерирует код (в чате)

# Шаг 3: проверить код
1c-ai solve check /tmp/new_module.bsl

# Шаг 4: если есть errors — исправить и повторить Шаг 3
```

**Всего проверок на каждый .bsl файл: 209** (187 BSL LS + 22 check_1c_standards)

## [3.0.0] — 2026-06-27

### Расширение check_1c_standards.py — 12 новых правил (всего 22)

**Новые правила на основе ai_rules_1c и стандартов ITS:**

| # | Правило | Severity | Что проверяет |
|---|---------|----------|---------------|
| 11 | no-soobshit | warning | Сообщить() → ОбщегоНазначения.СообщитьПользователю |
| 12 | no-vypolnit | error | Выполнить() — dynamic code execution |
| 13 | no-vychislit | error | Вычислить() — dynamic code evaluation |
| 14 | no-ternary | warning | ?(условие, з1, з2) — тернарный оператор |
| 15 | no-boolean-compare | warning | = Истина / = Ложь — избыточное сравнение |
| 16 | no-yoda-syntax | warning | Если 0 = Сумма — Yoda syntax |
| 17 | no-query-in-loop | error | Запрос в цикле — CRITICAL антипаттерн |
| 18 | no-dot-notation | warning | Товар.Цена → ОбщегоНазначения.ЗначениеРеквизитаОбъекта |
| 19 | no-hardcoded-credentials | error | Хардкод паролей/токенов |
| 20 | no-magic-numbers | warning | Магические числа > 99 |
| 21 | module-structure | warning | Отсутствие областей ПрограммныйИнтерфейс и т.д. |
| 22 | no-try-around-db | error | Попытка...Исключение вокруг DB operations |

**Умные исключения:**
- `Выполнить()` запрещён, но `Запрос.Выполнить()` — OK (метод объекта)
- `Товар.Цена` детектируется, но `Запрос.Текст` — OK (стандартный объект)
- Маленькие модули (< 20 строк) без областей — OK
- Комментарии пропускаются всеми правилами
- Числа 0, 1, 10 не считаются магическими

**Тесты:**
- 23 новых теста (positive + negative cases для каждого правила)
- Интеграционный тест всех новых правил на одном файле
- Итого: 168 тестов (было 145), проходят за 21 сек

## [2.9.1] — 2026-06-27

### BSL Language Server — интеграция подтверждена тестами

**Подтверждение работы BSL LS:**
- BSL LS v1.0.1 успешно устанавливается и запускается (Java 21 + собственная JRE)
- `1c-ai bsl analyze` — находит 7 диагностик на тестовом файле
- `1c-ai bsl baseline` — сохраняет baseline в `runtime/bsl-baseline.json`
- `1c-ai bsl diff` — находит 3 новые диагностики после изменения кода
- Диагностики BSL LS: InvalidCharacterInFile, CommentedCode, DeprecatedMessage,
  UnusedLocalVariable, EmptyStatement, MissingVariablesDescription, и др.

**Новые интеграционные тесты с реальным BSL LS:**
- `test_real_bsl_analyze_simple_file` — анализ файла с известными нарушениями
- `test_real_bsl_baseline_and_diff` — полный цикл baseline → diff
- `test_real_bsl_analyze_clean_file` — анализ чистого файла
- Тесты помечены `@requires_bsl_ls` — пропускаются если BSL LS не установлен
- Итого: 145 тестов (было 142), 3 новых реальных теста BSL LS

**Исправления:**
- `pyproject.toml` версия обновлена с 2.4.0 → 2.9.1

## [2.9.0] — 2026-06-27

### v8_metadata_parser + cf_to_xml_adapter + backup_manager

**Парсер структуры значений 1С:**
- `scripts/v8_metadata_parser.py`: парсер метаданных из распакованного .cf
- `scripts/cf_to_xml_adapter.py`: конвертер v8unpack → XML формат
- `ConfigManager.add_from_cf()` обновлён: распаковка + конвертация

**Backup/restore:**
- `src/services/backup_manager.py`: BackupManager
- CLI: `1c-ai backup create/restore/list`
- 12 тестов

## [2.8.0] — 2026-06-27

### cf_extractor — Container64 + многоконтейнерные .cf

- Поддержка 32-битных и 64-битных контейнеров 1С
- Многоконтейнерные .cf файлы
- Протестировано на 4 реальных .cf (УТ11, УНП, ЭДО2, ЭДО3)

## [2.7.0] — 2026-06-25

### cf_extractor.py — собственный парсер .cf

- Парсер формата контейнера 1С без зависимости от v8unpack
- 11 тестов

## [2.6.0] — 2026-06-25

### Проверка стандартов разработки 1С

**Новый скрипт `scripts/check_1c_standards.py`:**
- 10 правил, основанных на официальных стандартах ITS (454, 455, 456) и `ai_rules_1c/anti-patterns.md`:
  - `no-non-breaking-space` (error) — неразрывные пробелы U+00A0, U+2007, U+2009 (STD 456:1.2)
  - `no-wrong-dash` (error) — em/en-dash вместо дефиса (STD 456:1.2)
  - `no-yo-in-code` (warning) — буква «ё» в коде, кроме строковых литералов (STD 456:1.1)
  - `no-commented-code` (warning) — закомментированные BSL-конструкции (STD 456:3)
  - `todo-with-task` (warning) — TODO/FIXME без номера задачи «№ N» (STD 456:3)
  - `no-author-marks` (warning) — авторские пометки `// Фамилия:` (STD 456:3)
  - `no-hungarian-notation` (warning) — префиксы типа `м`, `стр`, `цел` (STD 454:2)
  - `no-short-variables` (warning) — имена переменных < 2 символов (STD 454:4)
  - `no-underscore-vars` (error) — имена, начинающиеся с `_` (STD 454:3)
  - `line-too-long` (warning) — строки > 120 символов (STD 456)
- Покрывает правила, которые BSL LS не проверяет или проверяет слабо
- Поддержка UTF-8 и windows-1251 кодировок (часто в 1С)
- Вывод: text (как ESLint) или JSON (для CI)
- Exit code: 1 если есть errors, 0 если только warnings или чисто

**CLI интеграция:**
- Новая команда: `1c-ai standards <path>` (или `python3 -m src.cli standards <path>`)
- Опции: `--format text|json`, `--severity error|all`

**Тесты:**
- `test_check_standards.py` — 29 тестов: каждое правило (positive + negative case), интеграционные тесты на директорию, JSON/text формат, cp1251 кодировка
- Итого: **95 тестов** (было 66), проходят за 0.53 сек

## [2.5.0] — 2026-06-25

### Тесты для парсера метаданных + интеграционные тесты

**Тесты для `build_config_index_generic.py` (последний непокрытый парсер):**
- `test_build_config_index.py` — 14 тестов:
  - Хелперы: `strip_ns`, `get_child`, `get_text`, `get_synonym_text` (3 теста)
  - `parse_configuration_xml`: валидный XML, missing file, без Configuration element (3 теста)
  - `parse_dumpinfo`: Catalog с UUID, Document с Form, Template+Command, modules (ObjectModule/ManagerModule), fields (Dimension/Resource), missing file, unknown type (7 тестов)
  - `build_index`: генерация Markdown с метаданными (1 тест)
- Все 1000 строк XML-парсера теперь покрыты тестами с синтетическими XML

**Интеграционные тесты (полный flow):**
- `test_integration.py` — 2 теста:
  - `test_integration_add_build_analyze`: создание ZIP → `add_from_zip` → `build` (реальные парсеры выполняются) → проверка `index.md`, `api-reference.md`, `api-reference.json` → BSL `analyze` (subprocess замокан) → проверка диагностики
  - `test_integration_archive_and_restore`: add → build → archive (проверка что path=None, archive существует, индексы сохранены) → activate (восстановление)
- Создаётся синтетическая мини-конфигурация 1С в ZIP: Configuration.xml, ConfigDumpInfo.xml, Catalogs/, CommonModules/ с .bsl файлом
- Тестируется реальное взаимодействие всех компонентов: PathManager → ConfigManager → ConfigRegistry → build_config_index_generic → build_api_reference → BSLAnalyzer

**Итого: 66 тестов** (было 50), проходят за 0.44 сек. Все парсеры проекта теперь покрыты.

## [2.4.0] — 2026-06-25

### pyproject.toml + editable install (большой рефакторинг)

**Упаковка как Python-пакет (PEP 517/518/621):**
- Добавлен `pyproject.toml` — пакет `1c-ai-dev-env` v2.4.0
- `setup_src/` переименован в `src/` (git mv, история сохранена)
- `[project.scripts]` — entry point `1c-ai = "src.cli:main"` (команда `1c-ai` вместо `python3 -m src.cli`)
- `[project.optional-dependencies]` — `rag` (fastembed, qdrant-client) и `dev` (pytest)
- Установка: `pip install -e .` (editable mode) или `pip install -e ".[dev]"`

**Упрощение install.sh:**
- Убран `cp -r setup_src src` — заменён на `pip install -e "$SETUP_DIR"`
- Больше не нужно синхронизировать `setup_src/` и `src/` вручную
- Пакет доступен через `from src.services...` после установки

**Очистка хаков:**
- `tests/conftest.py` — убран `sys.path.insert` хак
- Все 6 тестовых файлов — убраны `sys.path.insert` и `from setup_src...` → `from src...`
- Тесты теперь используют стандартный механизм импорта Python через установленный пакет

**CI обновлён:**
- `pip install -e ".[dev]"` вместо отдельных `pip install -r requirements*.txt`
- `find scripts src` вместо `find scripts setup_src`

**Документация:**
- README: `1c-ai validate` вместо `python3 -m src.cli validate` (с пометкой про альтернативу)
- CONTRIBUTING.md: обновлены инструкции установки, импорты в примерах
- ARCHITECTURE.md: структура обновлена под `src/`

**Обратная совместимость:**
- `python3 -m src.cli` по-прежнему работает (если пакет установлен или CWD = корень проекта)
- Старый корневой `src/` можно удалить — pip install -e . создаёт правильный импорт сам

## [2.3.0] — 2026-06-25

### Изменения (раунд 2, v5 отзыв)

**Тесты для парсеров (A4):**
- `test_hbk_extractor_full.py` — 7 тестов: `parse_hbk_file` на синтетическом .hbk (1 и 3 файла), `extract_file_data` (deflate/store/invalid), `safe_filename`
- `test_build_api_reference.py` — 10 тестов: `parse_module_bsl` (Функция Экспорт, Процедура Экспорт, skip non-export, multiple methods, empty, nonexistent), `parse_comment_block` (структура, пустой), `parse_module_xml` (валидный + невалидный)
- **Тесты нашли реальный баг**: `parse_comment_block` терял последний параметр при переходе в секцию "Возвращаемое значение:" — `current_param` сбрасывался без сохранения. Исправлено.
- Итого теперь **50 тестов** (было 33), все проходят за 0.28 сек

**Документация (D3):**
- `CONTRIBUTING.md` полностью переписан: добавлена секция «Запуск тестов», «Добавление новых тестов» (с примером mock), таблица покрытия, описание CI
- Явно указано: использовать `PathManager`, а не `paths.py` (deprecated)

**Портативность (A5):**
- `Project()` теперь корректно работает из любой поддиректории — поиск `paths.env` вверх по дереву (фикс из раунда 1)
- Проверено: `Project()` запущенный из `<root>/subdir/deep/` находит `<root>`

## [2.2.0] — 2026-06-25

### Изменения (раунд 1, v5 отзыв)

**Портативность (без хардкода):**
- `PathManager._detect_root()` — поиск `paths.env` вверх по дереву каталогов (как git ищет `.git`), fallback на `Path.cwd()` вместо хардкода `/home/z/my-project`
- `paths.py` — аналогичный поиск вверх вместо хардкода в fallback-логике

**Очистка мёртвого кода:**
- `paths.py`: удалены `config_ut11`, `config_priemka` (legacy-маппинг конкретных конфигов)
- `paths.Paths.get_config_path()`: fallback упрощён — возвращает `<configs_dir>/<name>` вместо хардкод-маппинга
- Удалён `setup_src/test_configuration.py` — дубликат `tests/test_configuration.py`, засорял продакшен-пакет после `install.sh`

**Точность обработки ошибок:**
- `ConfigManager._read_config_props()`: `except (ET.ParseError, Exception)` → `except ET.ParseError` + `except (OSError, PermissionError)` с логированием через `logging.warning`
- `BSLAnalyzer._run_analysis()`: `output_dir` очищается через `shutil.rmtree(..., ignore_errors=True)` перед запуском BSL LS — защита от устаревшего `bsl-json.json`, если новый запуск упадёт

**Корректность метаданных:**
- `manifest.json`: `python_dependencies` теперь содержит только обязательные (`v8unpack`, `python-dotenv`); `fastembed`, `qdrant-client` вынесены в `python_dependencies_optional`
- `manifest.json`: `forks.count` исправлен с 16 на 15 (фактическое число git-репозиториев)
- Унифицирована формулировка «15 git + BSL LS» в `install.sh`, `ARCHITECTURE.md`, `CHANGELOG.md`

**.gitignore усилен:**
- Добавлены `**/__pycache__/` и `*.pyo` для предотвращения случайного коммита артефактов

## [2.1.0] — 2026-06-25

### Изменения (раунд 1 рефакторинга)

**Безопасность и устойчивость:**
- `ConfigManager.add_from_zip()` и `activate()` теперь валидируют ZIP через `testzip()` и обрабатывают `BadZipFile` — повреждённый архив даёт понятное сообщение вместо стектрейса
- При ошибке распаковки временная директория автоматически очищается

**Устранение дублирования (DRY):**
- `scripts/fast_search_1c.py` теперь тонкая CLI-обёртка над `src.services.search` — TF-IDF логика живёт в одном месте, а не в трёх
- CLI (`src/cli.py`) и standalone-скрипт вызывают одну и ту же реализацию

**Очистка legacy:**
- `paths.py` помечен как `@deprecated` (DeprecationWarning при импорте)
- `install.sh` больше не вызывает `paths.py validate` — использует `python3 -m src.cli validate`
- ARCHITECTURE.md обновлён: описан OOP-слой `src/` и явно указано, что `PathManager` — первичный источник путей

### Изменения (раунд 2 рефакторинга)

**Тесты (pytest):**
- Полностью переработаны под pytest (вместо inline-тестов)
- `test_path_manager.py` — 6 тестов: определение root, 4 слоя, пути конфигов/платформы, validate, подстановка env
- `test_config_manager.py` — 8 тестов: add_from_zip (success/duplicate/not_found/bad_zip), count_objects, build с mock subprocess, archive/activate цикл
- `test_bsl_analyzer.py` — 6 тестов: AnalysisResult парсинг, Diagnostic.key, analyze с mock subprocess, персистентность baseline между вызовами
- `test_fast_search.py` — 7 тестов: tokenize (CamelCase, mixed, empty), build_index + search, limit
- `test_configuration.py` — 5 тестов: basic, from_dict, to_dict, is_active, common_modules_dir
- **Итого: 33 теста, все проходят за 0.24 сек**
- `subprocess` мокируется через `unittest.mock.patch` — тесты не требуют Java/BSL LS/внешних скриптов

**CI:**
- `.github/workflows/ci.yml` переведён на `pytest tests/`
- Проверка синтаксиса через `find ... -exec py_compile` вместо хардкода списка файлов
- Добавлен `requirements-dev.txt` (pytest)

**Документация:**
- ARCHITECTURE.md дополнен: добавлена диаграмма OOP-слоя `src/`, принцип DRY для TF-IDF

## [2.0.0] — 2026-06-24

### Добавлено

**4-слойная архитектура:**
- `data/` — исходные данные (configs, archives, hbk)
- `derived/` — производные (индексы по конфигурациям и платформе)
- `tools/` — инструменты (16 форкнутых репозиториев + BSL LS)
- `runtime/` — файлы работы (paths, registry, soul, session-resume)

**Универсальная система конфигураций:**
- `register_config.py` — CLI (add, register, activate, archive, build, build-all, list, remove)
- `build_api_reference.py` — универсальный парсер API (любая конфигурация)
- `config-registry.json` — реестр всех конфигураций
- `paths.env` + `paths.py` — единый конфиг путей

**Инструменты:**
- BSL Language Server v1.0.1 (анализ .bsl + --baseline/--diff)
- 94 скила Desko77 (JSON DSL: meta-compile, form-compile, cfe-*)
- 168 проверок EDT-MCP
- 187 диагностик BSL LS
- v8unpack (распаковка .cf/.cfe)
- TF-IDF семантический поиск (fast_search_1c.py)
- hbk_extractor.py (распаковка .hbk синтакс-помощника)

**Фичи из Hermes Agent:**
- Learning loop (auto-skill creation в learned-skills/)
- LSP post-write diff (bsl-analyze.sh --diff)
- user-profile.md + soul.md (персона)
- Role-switching protocol (4 роли, 3 протокола)

**Стандартные файлы:**
- LICENSE (MIT)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md
- .editorconfig
- .github/ (ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE)
- ARCHITECTURE.md

**Форки:**
- Все 15 репозиториев форкнуты на github.com/Pradushkoai/*
- manifest.json обновлён — URL указывают на форки

## [1.0.0] — 2026-06-23

- Initial release
- 8 скриптов, paths.env/paths.py, manifest.json, install.sh
- Шаблоны session-resume и project-context
