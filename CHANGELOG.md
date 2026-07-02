# Changelog


## [5.2.0] — 2026-07-02

### NEW: AGENTS.md — правила для AI-агентов (инцидент-ориентированный подход)

**Внедрён подход из статьи Егора Камелева** «AGENTS.md и Code Review Graph»
(Habr.com, июль 2026). AGENTS.md — текстовый Markdown-файл в корне репозитория,
который AI-агенты (Codex, Cursor, Claude) читают перед каждой рабочей сессией.

**Принцип создания — инцидент-ориентированность:** каждое правило рождено
реальной проблемой, а не теоретическими рассуждениями. AGENTS.md — это журнал
произошедших инцидентов, превращённых в правила.

**Новые файлы:**
- `AGENTS.md` (170 строк) — компактные правила для AI-агентов:
  - Рабочий процесс агента (4 этапа: правила → граф → документация → код)
  - Инфраструктурные правила (BSL LS, v8unpack, мобильное приложение, кэш)
  - Процессные правила (перед работой с конфигурацией, перед сборкой EPF,
    после изменений, критичные файлы)
  - Архитектурные правила (DRY, минимальная достаточность, локальность,
    структура BSL-модуля)
  - Технические правила (имена обработок, форма списка, запросы, коммиты, push)
  - Антипаттерны (8 пунктов «НЕ делать»)
  - История инцидентов (5 инцидентов → 5 правил)

- `docs/AGENTS_MD.md` (250 строк) — расширенное описание:
  - Что такое AGENTS.md и отличия от других файлов
  - Инцидент-ориентированный подход (4-шаговый цикл)
  - Рабочий процесс агента (4 этапа)
  - Категории правил (инфраструктурные, процессные, архитектурные, технические)
  - Примеры хороших и плохих правил
  - Поддержание актуальности
  - Связь с другими файлами

**Анализ статьи:**
- `download/Анализ_AGENTS_md_и_Code_Review_Graph.docx` (49 КБ) — аналитический
  отчёт: оценка вопросов и подходов статьи, сопоставление с инструментами
  репозитория, заключение о необходимости внедрения, пошаговый план.

**Обновлённые файлы:**
- `README.md` — добавлена секция «AI-агентам: читайте AGENTS.md» в начале
- `CHANGELOG.md` — этот раздел

**Соответствие подходам статьи:**

| Подход статьи | Статус в репо |
|---|---|
| AGENTS.md (единый файл правил) | ✅ Внедрено |
| Code Review Graph | ✅ Уже было (dependency_graph + call_graph) |
| Внешний MCP-сервер | ✅ Уже локальный (45 tools) |
| Папка doc/ (расширенная память) | ✅ Уже было (knowledge_base + docs + openspec) |
| Рабочий процесс 4 этапа | ✅ Формализовано в AGENTS.md |
| Инцидент-ориентированные правила | ✅ 5 правил из реальных инцидентов |
| Менеджер сессий | ✅ Уже было (session_manager) |
| База знаний | ✅ Уже было (knowledge_base/) |

**Итог:** 8 из 8 подходов статьи теперь реализованы в репозитории.
Внедрение заняло 3-4 часа (как и планировалось в аналитическом отчёте).


## [5.1.0] — 2026-07-01

### NEW: EPF Factory — создание внешних обработок 1С с нуля без 1С

**Новый сервис** `src/services/epf_factory.py` (470 строк) — полный цикл создания
`.epf` файлов без установленной платформы 1С. Собран из существующих компонентов
репозитория: v8unpack, BSL Language Server, шаблоны v8unpack-формата.

**Полный цикл (8 шагов):**
1. Копирование шаблонов v8unpack (`templates/epf_factory/`, 4 файла)
2. Генерация новых UUID (proc_uuid, form_uuid, file_uuid)
3. Патч `ExternalDataProcessor.json`: подстановка name/synonym/UUID в 11 мест
4. Патч `Form.id.json`: новый UUID формы
5. Запись `Form.obj.bsl` с BSL-кодом модуля формы
6. Проверка BSL через BSL Language Server (опционально)
7. Сборка `.epf` через `v8unpack -B`
8. Проверка round-trip: распаковка и сравнение BSL-модуля

**Шаблоны** (`templates/epf_factory/`):
- `ExternalDataProcessor.template.json` (3.6 КБ) — метаданные обработки
- `Form.template.json` (10 КБ) — метаданные формы (Platform + Mobile)
- `Form.id.template.json` (52 байта) — UUID формы
- `Form.elem.empty.json` (1 КБ) — пустая форма с реквизитом «Объект»

**CLI команда:**
```bash
1c-ai epf-factory create --name "МояОбработка" --bsl module.bsl --output /tmp/X.epf
1c-ai epf-factory templates
```

**MCP-инструменты (2):**
- `epf_factory_create` — создать .epf из BSL-кода (через Cursor/Claude Desktop)
- `epf_factory_templates` — список доступных шаблонов

**Тесты** (`tests/test_epf_factory_mcp.py`, 5 тестов):
- test_list_tools_includes_epf_factory
- test_epf_factory_templates
- test_epf_factory_create_with_bsl
- test_epf_factory_create_default_bsl
- test_epf_factory_create_error_no_name

**Документация:**
- `docs/EPF_FACTORY.md` — подробная инструкция (быстрый старт, CLI, Python API,
  MCP-инструменты, параметры, что внутри EPF, ограничения, решение проблем)

**Преимущества перед предыдущим подходом (модификация готового .epf):**
- Не зависит от внешнего .epf-шаблона
- Каждый запуск генерирует новые UUID (1С не ругается на дубликаты)
- Чистая структура: только то, что нужно, без мусора из оригинала
- Прозрачно: можно сохранить промежуточные v8unpack-исходники (`--save-sources`)

**Тест:** `СписокГрафикаИВыполненияОбхода.epf` (8.2 КБ) собран через
`1c-ai epf-factory create`, BSL LS: 0 errors, round-trip OK.


## [5.0.0] — 2026-07-01

### MAJOR: JSON DSL компиляторы + CFE + граф зависимостей + OpenSpec

**NEW: 5 JSON DSL компиляторов** (src/services/dsl_compiler.py, 1575 строк)
- MetaCompiler — 23 типа объектов 1С (Catalog, Document, Enum, и т.д.)
- FormCompiler — управляемые формы (Form.xml)
- SkdCompiler — СКД-схемы (DataCompositionSchema)
- MxlCompiler — MXL-макеты (печатные формы)
- RoleCompiler — роли 1С (Rights.xml) с пресетами view/edit и RLS

**NEW: CFE поддержка** (src/services/cfe_manager.py, 757 строк)
- cfe_borrow — заимствование объекта (ObjectBelonging=Adopted)
- cfe_patch_method — генерация &Перед/&После/&ИзменениеИКонтроль
- cfe_diff — анализ расширения

**NEW: Граф зависимостей метаданных** (src/services/dependency_graph.py, 475 строк)
- networkx вместо Neo4j (без внешних зависимостей)
- 8 типов запросов (what_depends_on, dependencies_of, find_cycles, и т.д.)
- Источники: реквизиты, ТЧ, регистраторы, подсистемы, подписки

**NEW: OpenSpec mini** (src/services/openspec_manager.py, 579 строк)
- Specification-Driven Development
- proposal/tasks/design/spec deltas
- create/load/update/archive/validate

**NEW: SessionManager** (src/services/session_manager.py, 232 строки)
- save/restore/retro/clear
- session-notes.md (Markdown) + session-state.json (JSON)

**NEW: SKD trace mode** (scripts/skd_parser.py)
- trace_field() — трассировка поля через dataset → calculated → resource

**NEW: img_grid утилита** (scripts/img_grid.py, 175 строк)
- Наложение сетки на скриншот печатной формы для LLM

**NEW: Единый inspect** (CLI + MCP)
- 8 типов анализа: cf, meta, form, skd, mxl, role, subsystem, depgraph
- 4 режима: overview, brief, full, trace

**NEW: 18 XML-спецификаций** (docs/1c-xml-specs/, 16K строк)
- 12 спецификаций XML-форматов 1С
- 5 спецификаций JSON DSL
- build-spec.md

**NEW: CLI команды**
- dsl (meta/form/skd/mxl/role)
- cfe (borrow/patch/diff)
- depgraph (build/query/validate)
- openspec (init/proposal/list/update/archive/validate)
- session (save/restore/retro/clear)
- inspect (cf/meta/form/skd/mxl/role/subsystem/depgraph)
- skd-trace

**NEW: MCP tools (36 всего)**
- dsl_compile_meta, dsl_compile_form, dsl_compile_skd, dsl_compile_mxl, dsl_compile_role
- cfe_borrow, cfe_patch_method, cfe_diff
- build_dependency_graph, dependency_query
- skd_trace, inspect
- openspec_proposal, openspec_list, openspec_update_task, openspec_archive

**IMPROVED: ConfigManager**
- validate_sources() — проверка Configuration.xml + обязательных директорий
- check_freshness() — mtime-сравнение исходников и индексов
- build(force, skip_if_fresh) — пропуск свежих индексов

**IMPROVED: TaskProcessor**
- solve() — 7 источников (было 3)
- check() — 7 анализаторов на 3 уровнях (quick/standard/full)

**IMPROVED: Инженерная зрелость**
- SARIF 2.1.0 output + GitHub Code Scanning workflow
- Pre-commit hooks (ruff + mypy + pytest)
- Coverage gate в CI
- Structlog (структурированное логирование)
- Docker compose (5 сервисов: cli, mcp-server, tests, coverage, lint)
- Property-based тесты (hypothesis, 13 инвариантов, ~1300 cases)
- Synthetic benchmarks в CI (19 тестов + SLA gate)

Статистика: 328 тестов (было 531 без property/benchmarks), 20 сервисов, 39 скриптов, 36 MCP tools

---

## [4.11.0] — 2026-06-30

### Quality improvements: benchmarks, E2E tests, lxml, CI

NEW: tests/test_benchmarks.py — 13 performance тестов
- XML parsing: single Catalog (0.2ms), Configuration (11ms), 100 Catalogs (118ms)
- BSL analysis: security_audit, code_metrics, transaction_check, query_analyzer
- Index loading: unified-metadata (3.8s), api-reference (1.3s), form-index (0.5s)

NEW: tests/test_e2e.py — 7 end-to-end тестов
- Full cycle: generate_processing → validate → build_epf
- Full cycle: generate_report → validate → build_epf
- Security audit on generated code (0 CRITICAL)
- Code metrics on generated code (health >= 80)
- Full solve_check (quick) on generated code (0 errors)

NEW: scripts/xml_parser.py — безопасный XML парсер с lxml fallback
NEW: tests/test_xml_parser.py — 6 тестов (включая XXE защиту)
NEW: scripts/check_versions.py — pre-commit hook для проверки версий
NEW: docs/API.md — программный API
NEW: docs/TROUBLESHOOTING.md — решение типичных проблем

UPDATE: .github/workflows/ci.yml — 3 jobs (lint + version-check + test)
UPDATE: requirements-optional.txt — lxml>=4.9.0

Статистика: 531 тест (было 504), 0 warnings

## [4.9.0] — 2026-06-30

### Технический долг: синхронизация версий + MCP tools

**Исправлено:**
- Version mismatch: manifest.json (4.1.0 → 4.9.0), pyproject.toml (3.17.0 → 4.9.0), README badge (3.12.0 → 4.9.0)
- DeprecationWarnings в metadata_extractor.py (6 строк `if properties else` → `if properties is not None else`)
- config-registry.json был пустой (0 конфигов) — восстановлен с УТ11

**Добавлено 6 новых MCP tools (всего 27):**
- `check_transactions` — проверка транзакций BSL
- `analyze_architecture` — анализ архитектуры конфигурации
- `analyze_queries` — анализ запросов 1С в BSL коде
- `check_form_quality` — проверка качества форм
- `check_skd_quality` — проверка качества СКД-схем
- `diff_configs` — сравнение версий конфигурации

**Статистика:**
- MCP tools: 27 (было 21)
- Тестов: 504 (0 warnings)

## [4.8.0] — 2026-06-30

### SKD Quality Checker + Diff Analyzer
- skd_quality_checker.py: 10 правил качества СКД-схем
- diff_analyzer.py: сравнение версий конфигурации (добавлено/удалено/изменено)
- 23 теста

## [4.7.0] — 2026-06-30

### Form Quality Checker
- form_quality_checker.py: 10 правил качества форм
- 13 тестов

## [4.6.0] — 2026-06-30

### Query Analyzer
- query_analyzer.py: 10 правил анализа запросов 1С внутри BSL
- 16 тестов

## [4.5.0] — 2026-06-30

### Architecture Analyzer
- architecture_analyzer.py: 10 правил архитектуры (циклы, God Object, мёртвый код, layering)
- 10 тестов

## [4.4.0] — 2026-06-30

### Transaction Checker
- transaction_checker.py: 6 правил проверки транзакций
- 18 тестов

## [4.3.0] — 2026-06-30

### Code Metrics
- code_metrics.py: 10 метрик (LOC, complexity, дублирование, God Object, health score)
- 28 тестов

## [4.2.0] — 2026-06-30

### Security Audit
- security_auditor.py: 15 правил безопасности (SQL-инъекции, хардкод, COM, RLS)
- 37 тестов

## [4.1.0] — 2026-06-30

### Единый универсальный парсер метаданных
- metadata_extractor.py: парсит 35 типов объектов 1С
- Configuration.xml, ConfigDumpInfo.xml, Roles, Subsystems, EventSubscriptions, ScheduledJobs
- 29 тестов

## [3.25.0] — 2026-06-29

### Этап 7 роадмапа v4.0: Обучающий контент (финальный этап!)

**Цель:** ИИ-ассистент «знает» паттерны 1С разработки и предлагает решения основываясь на лучших практиках.

#### Что добавлено:

##### 1. База знаний `knowledge_base/` (новая директория)
- **patterns/** — паттерны создания объектов:
  - `create_catalog.md` — создание справочника (структура, метаданные, модули)
  - `create_document.md` — создание документа (с движениями по регистрам)
  - `create_processing.md` — создание внешней обработки
  - `create_skd_report.md` — создание отчёта на СКД (с примером схемы)
- **antipatterns/** — антипаттерны:
  - `common_antipatterns.md` — 10 антипаттернов (запросы в цикле, бизнес-логика в форме, и т.д.)
- **best_practices/** — best practices:
  - `general_best_practices.md` — 20 практик (архитектура, запросы, транзакции, UI, и т.д.)
- **index.json** — индекс с keywords для поиска

##### 2. `src/services/knowledge_base.py` — сервис базы знаний (новый)
- `KnowledgeBase` класс:
  - `search(query, category, limit)` — поиск по keywords, title, содержимому
  - `get_item(item_id)` — полный текст статьи по ID
  - `list_all()` — список всех статей
  - `get_stats()` — статистика
- Ранжирование результатов по релевантности (score)

##### 3. MCP tool `get_knowledge` (новый, 19-й tool)
- Поиск по базе знаний: `get_knowledge(query='справочник')`
- Получение статьи: `get_knowledge(item_id='create_catalog')`
- Список всех: `get_knowledge()`
- Фильтр по категории: `get_knowledge(query='СКД', category='patterns')`

#### Содержимое базы знаний:
- **6 статей** всего
  - 4 паттерна (Catalog, Document, DataProcessor, Report/СКД)
  - 1 антипаттерны (10 общих)
  - 1 best practices (20 практик)
- Каждая статья: структура, примеры кода, best practices, антипаттерны

#### Примеры использования:
- `get_knowledge(query='справочник')` → найдёт "Создание справочника" (score=18)
- `get_knowledge(query='СКД отчёт')` → найдёт "Создание отчёта на СКД" (score=20)
- `get_knowledge(item_id='create_catalog')` → полный текст статьи

#### MCP tools: теперь 19 (было 18)
- Добавлен: `get_knowledge`

---

## 🎉 РОАДМАП v4.0 ЗАВЕРШЁН!

Все 7 этапов роадмапа выполнены:

| Этап | Версия | Описание | Статус |
|------|--------|----------|--------|
| 1 | v3.19.0 | Полная структура метаданных | ✅ |
| 2 | v3.20.0 | Парсинг СКД-схем | ✅ |
| 3 | v3.21.0 | Полный анализ форм | ✅ |
| 4 | v3.22.0 | Генерация BSL-кода | ✅ |
| 5 | v3.23.0 | Упаковка .epf | ✅ |
| 6 | v3.24.0 | Валидация | ✅ |
| 7 | v3.25.0 | Обучающий контент | ✅ |

**Итог v4.0:**
- 19 MCP tools (было 11)
- 6 новых скриптов: metadata_parser, skd_parser, form_analyzer, code_generator, epf_builder, code_validator
- 1 новый сервис: knowledge_base
- База знаний: 6 статей (паттерны, антипаттерны, best practices)
- Полный цикл: анализ конфигурации → генерация → валидация → упаковка .epf

## [3.24.0] — 2026-06-29

### Этап 6 роадмапа v4.0: Валидация и тестирование

**Цель:** Проверка сгенерированного кода на соответствие стандартам.

#### Что добавлено:

##### 1. `code_validator.py` — валидатор BSL и XML (новый скрипт)
- **BSLValidator** — базовая проверка BSL-синтаксиса (без Java):
  - Сбалансированность `#Область` / `#КонецОбласти`
  - Сбалансированность `Процедура`/`КонецПроцедуры`, `Функция`/`КонецФункции`
  - Сбалансированность `Если`/`КонецЕсли`, `Пока`/`КонецЦикла`, `Для`/`КонецЦикла`
  - Проверка `Экспорт` в объявлениях
  - Проверка `&НаСервере`/`&НаКлиенте` перед процедурами форм

- **XMLValidator** — проверка XML метаданных:
  - Парсинг через xml.etree.ElementTree
  - Проверка обязательных тегов (Name, Synonym, Properties)
  - Проверка UUID формата
  - Различение типов XML (Form, DataCompositionSchema, MetaDataObject)

- **validate_structure()** — структурная целостность:
  - Наличие Module.bsl, Form.xml, метаданных
  - Связи между файлами (DefaultForm → Forms/<Имя>)
  - Проверка СКД-схем для отчётов

- **validate_generated()** — полная валидация:
  - Возвращает verdict: `perfect` / `warnings` / `errors`
  - Подсчёт total_errors, total_warnings

##### 2. MCP tool `validate_generated` (новый, 18-й tool)
- Принимает source_dir (из generate_processing/generate_report)
- Возвращает: verdict, total_errors, total_warnings, детали по BSL/XML/структуре

#### Протестировано:
- `validate_generated(source_dir='/tmp/test_processing')` → verdict: PERFECT
- Проверка: 0 ошибок, 0 предупреждений

#### Полный цикл создания и проверки:
```
1. generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры')
   → структура в generated/ВыгрузкаНоменклатуры/

2. validate_generated(source_dir='generated/ВыгрузкаНоменклатуры')
   → verdict: perfect / warnings / errors

3. build_epf(source_dir='generated/ВыгрузкаНоменклатуры', output_path='ВыгрузкаНоменклатуры.epf')
   → .epf файл готов для 1С
```

#### MCP tools: теперь 18 (было 17)
- Добавлен: `validate_generated`

## [3.23.0] — 2026-06-29

### Этап 5 роадмапа v4.0: Упаковка .epf/.erf

**Цель:** Создание файлов внешних обработок/отчётов (.epf) для открытия в 1С.

#### Что добавлено:

##### 1. `epf_builder.py` — упаковщик .epf (новый скрипт)
- `V8ContainerWriter` — writer контейнеров 1С (32 и 64 бита)
  - Формат: заголовок + TOC + блоки данных
  - Поддержка сжатия zlib
  - UTF-16-LE кодирование имён файлов
- `build_epf(source_dir, output_path)` — упаковка каталога в .epf
  - Читает структуру из code_generator.py
  - Создаёт Container 0 (root metadata) и Container 1 (модули, формы)
  - Модули упаковываются в контейнеры info+text

##### 2. MCP tool `build_epf` (новый, 17-й tool)
- Принимает source_dir (из generate_processing/generate_report)
- Создаёт .epf файл
- Возвращает: file_path, size, object_name, uuid, files_included

#### Пример использования:
```
1. generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры')
   → создаёт структуру в generated/ВыгрузкаНоменклатуры/

2. build_epf(source_dir='generated/ВыгрузкаНоменклатуры', output_path='ВыгрузкаНоменклатуры.epf')
   → создаёт .epf файл (594 KB)
```

#### Структура .epf:
- Container 0 (32-битный): root metadata
  - UUID файл — метаданные обработки
  - version, versions
- Container 1 (64-битный): все вложенные объекты
  - UUID — метаданные
  - UUID.0/ — контейнер с info+text (модуль объекта)
  - UUID.N/ — формы (контейнер с info+text)

#### MCP tools: теперь 17 (было 16)
- Добавлен: `build_epf`

## [3.22.0] — 2026-06-29

### Этап 4 роадмапа v4.0: Генерация BSL-кода

**Цель:** Автоматическая генерация обработок и отчётов на СКД.

#### Что добавлено:

##### 1. `code_generator.py` — генератор BSL-кода и XML (новый скрипт)
- `generate_processing(name, synonym, ...)` — генерация внешней обработки
- `generate_report(name, synonym, ...)` — генерация отчёта на СКД
- Создаёт:
  - **Module.bsl** — модуль объекта (с СКД-логикой для отчётов)
  - **Form/Module.bsl** — модуль формы
  - **Form.xml** — описание элементов формы (с кнопкой Выполнить/Сформировать)
  - **Обработка.xml / Отчет.xml** — метаданные объекта
  - **Template.xml** — СКД-схема (DataCompositionSchema) для отчётов
  - **README.md** — документация

##### 2. Шаблоны BSL/XML в templates/
- `bsl/processing_object_module.bsl` — модуль объекта обработки
- `bsl/processing_form_module.bsl` — модуль формы обработки
- `bsl/skd_report_object_module.bsl` — модуль объекта отчёта (СКД-логика)
- `bsl/skd_report_form_module.bsl` — модуль формы отчёта
- `xml/data_processor_template.xml` — метаданные обработки
- `xml/report_template.xml` — метаданные отчёта

##### 3. MCP tools `generate_processing` и `generate_report` (новые, 15-й и 16-й)
- Генерация по имени и синониму
- Поддержка описания, автора, источника данных, готового запроса
- Возвращает список созданных файлов
- Сохраняет в `generated/<name>/`

#### Примеры:
- `generate_processing(name='ВыгрузкаНоменклатуры', synonym='Выгрузка номенклатуры')`
  → 6 файлов: metadata + BSL + form + README
- `generate_report(name='ОтчетПоПродажам', synonym='Отчёт по продажам',
   data_source='Документ.РеализацияТоваровУслуг')`
  → 8 файлов: metadata + BSL + СКД-схема + form + README

#### BSL шаблоны включают:
- Области: ПрограммныйИнтерфейс, СлужебныйПрограммныйИнтерфейс, СлужебныеПроцедурыИФункции
- Документирование: секции "Параметры:", "Возвращаемое значение:"
- СКД-логика: ПолучитьМакет → НастройкиПоУмолчанию → КомпоновщикМакета → ПроцессорВывода
- Обработчики: ПриСозданииНаСервере, ВыполнитьОбработку, СформироватьОтчет

#### MCP tools: теперь 16 (было 14)
- Добавлены: `generate_processing`, `generate_report`

## [3.21.0] — 2026-06-29

### Этап 3 роадмапа v4.0: Полный анализ форм

**Проблема:** `form_indexer.parse_form_xml()` извлекал только базовые элементы (имя, тип).
Не извлекались: DataPath (привязка к данным), события, свойства (Visible, Enabled, ReadOnly),
дерево элементов (ChildItems).

#### Что добавлено:

##### 1. `form_analyzer.py` — полный парсер форм (новый скрипт)
- Поиск всех форм: CommonForms, формы объектов (Catalogs, Documents, и т.д.)
- Рекурсивный парсинг элементов (ChildItems → дерево)
- Извлечение для каждого элемента:
  - type (InputField, Button, Table, UsualGroup, Page, и т.д.)
  - name, id, title
  - **data_path** — привязка к данным (например, `Список.Description`)
  - **visible, enabled, read_only** — свойства
  - **command_name** — для кнопок
  - **events** — события и обработчики (Event name → handler)
  - **children** — вложенные элементы (рекурсивно)
- Извлечение событий формы (на уровне формы)
- Подсчёт общего количества элементов

##### 2. MCP tool `get_form_structure` (новый, 14-й tool)
- Полная структура формы с деревом элементов
- Свойства элементов: data_path, visible, enabled, read_only
- События и обработчики
- Если form_name не указан — список всех форм с краткой информацией
- Фильтр по parent_name для уточнения
- Fuzzy search с подсказками

#### Статистика форм для УТ11:
- **3 174 формы** найдено
- По типам родителей:
  - CommonForm: 184
  - Catalogs: 822
  - Documents: 691
  - InformationRegisters: 323
  - DataProcessors: 295
  - Reports: 83
  - ChartsOfCharacteristicTypes: 17
  - ExchangePlans: 85
  - и др.
- **59 489 элементов** всего
- **7 973 событий** (обработчиков)
- Типы элементов:
  - InputField: 19 368
  - UsualGroup: 14 212
  - LabelField: 9 931
  - Button: 5 366
  - Page: 4 729
  - Table: 2 924
  - Pages: 1 682
  - CommandBar: 1 059

Пример: `get_form_structure(config_name='ut11', form_name='ФормаЭлемента', parent_name='Склады')`
вернёт дерево элементов с DataPath, событиями, свойствами.

#### MCP tools: теперь 14 (было 13)
- Добавлен: `get_form_structure`

## [3.20.0] — 2026-06-29

### Этап 2 роадмапа v4.0: Парсинг СКД-схем

**СКД (Схема Компоновки Данных)** — XML-формат 1С для декларативного описания отчётов.
Основной механизм отчётов в 1С 8.3. Хранится в:
- `Reports/<Имя>/Templates/ОсновнаяСхемаКомпоновкиДанных/Ext/Template.xml`
- `CommonTemplates/<Имя>/Ext/Template.xml`
- `DataProcessors/<Имя>/Templates/<Имя>/Ext/Template.xml`

#### Что добавлено:

##### 1. `skd_parser.py` — парсер СКД-схем (новый скрипт)
- Поиск всех СКД-схем в конфигурации (Reports, CommonTemplates, DataProcessors)
- Парсинг каждого элемента СКД:
  - **dataSources** — источники данных (Local/Remote)
  - **dataSets** — наборы данных (DataSetQuery, DataSetUnion, DataSetObject)
  - **fields** — поля наборов данных с title, role
  - **query** — текст запроса 1С (для DataSetQuery)
  - **main_table** — основная таблица (извлекается из запроса)
  - **parameters** — параметры с типами, значениями, ограничениями
  - **totalFields** — итоговые поля с выражениями (Сумма, Среднее, и т.д.)
  - **filters** — отборы
  - **calculatedFields** — вычисляемые поля с выражениями

##### 2. MCP tool `get_skd_schema` (новый, 13-й tool)
- Возвращает полную СКД-схему по имени отчёта
- Если report_name не указан — список всех СКД-схем с краткой информацией
- Fuzzy search с подсказками
- Читает skd-index.json для конфигурации

#### Статистика СКД для УТ11:
- **360 СКД-схем** найдено
- По типам:
  - Report: 306 (основная масса)
  - DataProcessor: 53
  - CommonTemplate: 1
- **409 наборов данных** (с запросами 1С)
- **2 177 параметров**
- **6 924 поля** в наборах данных
- **299 отчётов** имеют СКД-схемы

Пример: `get_skd_schema(config_name='ut11', report_name='ABCXYZАнализНоменклатуры')`
вернёт: наборы данных с запросом, поля (Номенклатура, ABC, XYZ), параметры (Период).

#### MCP tools: теперь 13 (было 12)
- Добавлен: `get_skd_schema`

## [3.19.0] — 2026-06-29

### Этап 1 роадмапа v4.0: Полная структура метаданных

**Проблема:** XML-файлы метаданных из .cf — это «заглушки» (только Name, Synonym, Comment).
Реальные XML-выгрузки Конфигуратора содержат ВСЮ структуру: реквизиты, табличные части,
предопределённые значения, формы, иерархию.

**Решение:** Загружена полная XML выгрузка УТ11 (636 МБ, 59K файлов). Создан
`metadata_parser.py` для извлечения полной структуры объектов. Добавлен MCP tool
`get_object_structure`.

#### Что добавлено:

##### 1. `metadata_parser.py` — парсер полных метаданных (новый скрипт)
- Парсит XML выгрузки Конфигуратора (не заглушки из .cf!)
- Поддерживает 7 типов объектов:
  - **Catalog** — справочники: реквизиты, ТЧ, иерархия, предопределённые
  - **Document** — документы: реквизиты, ТЧ, нумерация
  - **InformationRegister** — регистры сведений: измерения, ресурсы, реквизиты
  - **AccumulationRegister** — регистры накопления: измерения, ресурсы
  - **DataProcessor** — обработки: реквизиты, ТЧ, формы
  - **Report** — отчёты: реквизиты, ТЧ, формы
  - **Enum** — перечисления: значения
- Извлекает для каждого объекта:
  - Имя, UUID, синоним, комментарий
  - Стандартные реквизиты (StandardAttributes)
  - Реквизиты (Attributes) с типами данных, синонимами, проверками
  - Табличные части (TabularSections) с их реквизитами
  - Формы (список имён)
  - Команды (список имён)
  - Свойства (CodeLength, Hierarchical, DefaultObjectForm, и т.д.)

##### 2. MCP tool `get_object_structure` (новый, 12-й tool)
- Возвращает полную структуру объекта по имени
- Если object_name не указан — список всех объектов с краткой информацией
- Поддержка фильтра по типу (object_type)
- Fuzzy search с подсказками при опечатках
- Читает metadata-index.json для конфигурации

##### 3. Загружена полная XML выгрузка УТ11
- 636 МБ ZIP → 1.9 ГБ распакованных данных
- 59 172 файла (vs 14 836 из .cf)
- 7 141 BSL файлов (vs 3 379 из .cf)
- 20 411 XML файлов с полными метаданными
- Заменила «заглушки» из improved_cf_adapter на реальные данные

#### Статистика metadata-index для УТ11:
- 2 318 объектов распарсено
- 11 198 реквизитов
- 1 026 табличных частей
- 2 789 форм
- 446 команд
- По типам:
  - Catalog: 385
  - Document: 214
  - InformationRegister: 450
  - AccumulationRegister: 97
  - DataProcessor: 295
  - Report: 354
  - Enum: 523

#### MCP tools: теперь 12 (было 11)
- Добавлен: `get_object_structure`

## [3.18.0] — 2026-06-29

### Полное извлечение всех типов модулей из .cf и XML выгрузок

**Проблема:** Предыдущая версия (3.17.0) заявляла о поддержке форм из .cf, но фактически
извлекала только CommonModules и частично ObjectModule/ManagerModule. Формы, команды,
командный интерфейс, модуль приложения, модуль сеанса и модуль внешнего соединения
не извлекались.

**Решение:** Новый `improved_cf_adapter.py` корректно извлекает ВСЕ типы модулей из .cf
и обновлённый `form_indexer.py` индексирует все типы модулей.

#### Что добавлено:

##### 1. `improved_cf_adapter.py` — новый конвертер .cf → XML (вместо cf_to_xml_adapter.py)
- **CommonModules**: из UUID.0/text (контейнер info+text)
- **ObjectModule**: из UUID.0/text (контейнер) для Catalogs/Documents/etc.
- **ManagerModule**: из UUID.2 (прямой текст BSL) — ИСПРАВЛЕНО (ранее не извлекался)
- **CommonForms**: BSL встроен ВНУТРЬ данных формы (UUID.0 как текст) — ИСПРАВЛЕНО
- **Object Forms (вложенные)**: формы объектов с привязкой к родителю — ИСПРАВЛЕНО
- **CommonCommands**: модули команд из UUID.2 (прямой текст) — НОВОЕ
- **CommandInterface**: для подсистем из UUID.1/text — НОВОЕ
- **SubsystemModule**: модули подсистем из UUID.2 — НОВОЕ
- Правильное определение типа по содержимому (Type 1 = CommonForm, Type 29 = Subsystem)

##### 2. `form_indexer.py` — расширенная индексация
- Добавлены CommonCommands/<Имя>/Ext/CommandModule.bsl — общие команды
- Добавлены <Тип>/<Имя>/Commands/<Команда>/Ext/CommandModule.bsl — команды объектов
- Добавлены Subsystems/<Имя>/Ext/SubsystemModule.bsl — модули подсистем
- Добавлен Ext/OrdinaryApplicationModule.bsl — модуль обычного приложения
- Новые категории: 'Команды', 'Подсистемы', 'Модули конфигурации'
- Свойства modules: server, client_managed, external_connection корректно определяются

##### 3. `config_manager.py` — обновлён
- Использует `improved_cf_adapter.py` (предпочтительно) или `cf_to_xml_adapter.py` (fallback)
- Автоматически определяет наличие улучшенного адаптера

#### Статистика после переиндексации:

| Конфигурация | Модулей | Методов | Документов BM25 |
|--------------|---------|---------|-----------------|
| ut11         | 2 633   | 17 101  | 21 064          |
| edo2         | 3 142   | 27 513  | 31 759          |
| edo3         | 2 963   | 25 075  | 28 201          |
| unp          | 7 197   | 61 463  | 74 775          |
| obhod        | 9       | 24      | 24              |
| **ИТОГО**    | **15 944** | **131 176** | **155 823** |

#### Извлечение по типам модулей (.cf):
- CommonModules: 7 515 (ut11+edo2+edo3+unp)
- ObjectModules: 2 068
- ManagerModules: 2 502
- CommonForms: 3 773
- Object Forms (вложенные): 1 099
- CommonCommands: 279
- Subsystems: 1 542
- CommandInterfaces: 236

#### Примечание о модулях конфигурации:
- ManagedApplicationModule, SessionModule, ExternalConnectionModule — присутствуют
  в XML выгрузках (obhod, priemka) и индексируются корректно.
- В .cf файлах эти модули НЕ хранятся как отдельные файлы — они являются частью
  платформы 1С, а не конфигурации. Конфигуратор добавляет их автоматически.
- HomePageWorkArea.xml и CommandInterface.xml — присутствуют в XML выгрузках
  и частично извлекаются из .cf (для подсистем).

## [3.17.0] — 2026-06-29

### Извлечение и индексация форм конфигураций

**Новый инструмент:** `form_indexer.py` — извлечение модулей форм и элементов форм
из конфигураций 1С (как из ZIP выгрузки, так и из .cf).

**Что добавлено:**

#### 1. `form_indexer.py` — парсер форм (новый скрипт)
- `find_form_modules(config_dir)` — находит все модули форм:
  - CommonForms/<Имя>/Ext/Form/Module.bsl
  - <ТипОбъекта>/<Имя>/Forms/<ИмяФормы>/Ext/Form/Module.bsl
- `parse_form_xml(xml_path)` — парсит XML формы, извлекает элементы:
  - InputField (поля ввода)
  - Button (кнопки)
  - Table (таблицы)
  - UsualGroup, Pages, Page (группы)
  - CheckBox, RadioButton, и др.
  - Title, DataPath, CommandName для каждого элемента
- `add_forms_to_api_reference()` — интеграция в build_api_reference

#### 2. `build_api_reference.py` — обновлён
- После индексации CommonModules добавляет формы
- Формы в api-reference.json с type='Форма', category='Формы'
- Включает: methods (экспортные), form_elements (кнопки, поля), form_elements_count

#### 3. `cf_to_xml_adapter.py` — обновлён
- Добавлен `_extract_forms_from_cf()` — извлечение модулей форм из .cf
- Ищет вложенные контейнеры UUID.N/text с info файлами
- Определяет имя формы через парсинг info
- Связывает форму с родительским объектом (Document, Catalog, и т.д.)

#### 4. Новый MCP tool: `get_form_elements`
- `get_form_elements(config_name)` — список всех форм
- `get_form_elements(config_name, form_name)` — элементы конкретной формы
- Возвращает: name, type, title, data_path, command

#### 5. `search_code` — обновлён
- Теперь индексирует методы из модулей форм
- search_code находит методы в формах (а не только в CommonModules)

**Пример на obhod:**
```
Было: 3 модуля, 18 методов (только CommonModules)
Стало: 8 модулей, 23 метода (3 CommonModules + 5 форм)
Формы: ФормаАвторизации (8 элементов), ФормаИнцедента (31), 
       ФормаОбходов (23), ОбходТерритории.Форма (63)
```

### Статистика
- MCP tools: 11 (было 10, +get_form_elements)
- Тестов: 336 (без изменений — форма-индексатор протестирован на obhod)
- Новых файлов: `scripts/form_indexer.py`

## [3.16.0] — 2026-06-29

### call_graph — граф вызовов методов конфигурации

**Новый сервис + MCP tool + CLI** — анализ зависимостей между методами конфигурации.

```bash
# CLI
1c-ai call-graph --config obhod stats
1c-ai call-graph --config obhod callees --module ОбменДокументы --method ВыполнитьПолныйОбмен
1c-ai call-graph --config obhod dead-code
1c-ai call-graph --config obhod cycles

# MCP tool
call_graph(config_name='obhod', action='callees', module='ОбменДокументы', method='ВыполнитьПолныйОбмен')
```

**Возможности:**
- `stats` — статистика графа (рёбра, узлы)
- `callers` — кто вызывает данный метод
- `callees` — кого вызывает данный метод
- `dead-code` — экспортные методы, которые никто не вызывает
- `cycles` — циклические зависимости (DFS)
- `json` — полный граф в JSON

**Как работает:**
1. Парсит все .bsl файлы конфигурации
2. Находит кросс-модульные вызовы: `ОбменДокументы.ВыполнитьПолныйОбмен()`
3. Находит локальные вызовы: `ЛокальныйМетод()` внутри того же модуля
4. Фильтрует стандартные объекты (Справочники, Запрос, и т.д.)
5. Строит directed graph с быстрыми индексами

**Новый файл:** `src/services/call_graph.py` (~300 строк)

### Статистика
- MCP tools: 10 (было 9, +call_graph)
- Тестов: 336 (было 316, +20)
- Новых файлов: `src/services/call_graph.py`, `tests/test_call_graph.py`

## [3.15.1] — 2026-06-29

### Новая конфигурация: obhod (Обход)

Добавлена 5-я конфигурация — **obhod** v1.0.0 (обход/патрулирование).

**Статистика:**
| Конфигурация | Объектов | Модулей | Методов |
|--------------|---------|---------|---------|
| edo2         | 2353    | 1473    | 22 506 |
| edo3         | 2561    | 1646    | 24 266 |
| ut11         | 1937    | 1118    | 15 809 |
| unp          | 5630    | 3182    | 53 085 |
| obhod (нов.) | 17      | 3       | 18      |
| **Итого**    | **12498**| **7422**| **115 684** |

Плюс платформа 1С: 8141 методов (BM25 индекс)

**DataPackage:** 182.5 МБ, 60253 файлов (GitHub Release обновлён)

**Структура obhod:**
- CommonModules: ОбменДокументы (15 methods), ОбменНастройки (1), ФоновыеПроцедуры (2)
- Documents: ГрафикИВыполнениеОбхода, Инцидент
- CommonTemplates: драйверы сканеров (Атол, Mertech, Штрихкод1С, Cleverans)
- Roles: Администратор, Сторож

## [3.15.0] — 2026-06-29

### Топ-3 быстрых победы (из внешнего анализа)

#### 1. `search_code` — поиск по коду конфигураций (115 666 методов)

**Новый MCP tool + CLI команда** — BM25 поиск по экспортным методам
конфигураций. Самый частый запрос 1С-разработчика: «как у нас уже
сделано похожее?» — теперь работает.

```bash
# CLI
1c-ai search-code "создать заказ клиента" --config ut11 --limit 5

# MCP tool
search_code(query="создать заказ", config_name="ut11", limit=5)
```

Новый сервис: `src/services/search_code.py` — BM25 по api-reference.json.
При первом вызове строит индекс (4-5 сек), затем кэширует (0.4 сек).

Результат: `{score, module, name, type, signature, description, returns}`

#### 2. BSL-синонимы ru↔en

**100+ пар синонимов** в `search_bm25.py` — поиск независимо от языка.

Запрос `StrFind` находит `СтрНайти` (score 1.000).
Запрос `FindByCode` находит `НайтиПоКоду` (score 1.000).

Словарь покрывает: строковые функции, массивы, справочники, документы,
запросы, метаданные, дату/время, числа, преобразования типов, формы,
регистры.

#### 3. `--ci` и `--json` режимы для `solve_check`

**CI/CD-ready** — exit code и JSON-вывод для GitLab CI / GitHub Actions.

```bash
# CI-режим: только errors, exit code 1 при errors
1c-ai solve check module.bsl --ci
# exit 0 — OK, 1 — errors

# JSON-вывод для парсинга
1c-ai solve check module.bsl --json > report.json
```

**Изменения:**
- `--ci`: только errors, краткий вывод, exit code 1 при errors
- `--json`: полный JSON-отчёт (file, level, total_errors, verdict, violations)
- Exit code: 0 — OK, 1 — errors, 2 — usage (несуществующий файл)

### Статистика
- MCP tools: 9 (было 8, +search_code)
- Тестов: 316 passed, 3 skipped
- Новых файлов: `src/services/search_code.py`
- Новых строк кода: ~300

## [3.14.1] — 2026-06-29

### Упрощение — 2 функции репозитория

Убран лишний формализм (чек-лист с 5 фазами, 3 режима). Оставлено простое:

**2 функции репозитория:**
1. MCP-сервер для сторонних клиентов (Cursor, Claude Desktop, VS Code)
2. Источник информации по 1С для ассистента

Удалено:
- `templates/checklist.template.md` (5 фаз)
- `runtime/checklist.md`

Обновлено:
- `templates/soul.template.md` — 2 принципа (уточни ТЗ + используй инструменты)
- `templates/session-resume.template.md` — убрана ссылка на checklist
- `README.md` — секция «2 функции репозитория» вместо «3 режима» + «Чек-лист»
- `pyproject.toml` — version 3.14.1

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
