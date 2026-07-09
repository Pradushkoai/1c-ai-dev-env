# 1C AI Development Environment

> **Универсальная среда разработки на 1С с ИИ-ассистентом**: парсинг и анализ метаданных 1С из XML-выгрузок, 7 MCP tools для IDE/LLM, 11 анализаторов BSL-кода (150+ правил), JSON DSL → XML компиляторы (5 типов объектов), работа с расширениями CFE, граф зависимостей метаданных, трассировка СКД, генерация обработок/отчётов/макетов/ролей, **создание внешних обработок .epf с нуля без 1С**, SARIF для GitHub Code Scanning.

**Языки:** **Русский** | [English](README.en.md)

[![Version](https://img.shields.io/badge/version-6.0.0-brightgreen.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-Beta-yellow.svg)](ROADMAP.md#критерии-перехода-beta--production-ready)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)
[![Tests](https://img.shields.io/badge/tests-1595%20passing-success.svg)](#тесты)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-7-blue.svg)](#подключение-к-ide--llm-через-mcp)
[![CLI Commands](https://img.shields.io/badge/CLI%20commands-19-success.svg)](#cli-команды)

---

## 🤖 AI-агентам: читайте AGENTS.md

**Если вы AI-агент (Codex, Cursor, Claude) — начните с [`AGENTS.md`](AGENTS.md).**

AGENTS.md — компактный набор правил (170 строк), которые нужно знать перед
каждой рабочей сессией. Правила рождены реальными инцидентами, а не
теоретическими рассуждениями. Содержит:

- **Рабочий процесс агента** (4 этапа: правила → граф → документация → код)
- **Инфраструктурные правила** (BSL LS, v8unpack, мобильное приложение)
- **Процессные правила** (перед сборкой EPF, после изменений, критичные файлы)
- **Архитектурные правила** (DRY, локальность, структура BSL-модуля)
- **Технические правила** (имена обработок, форма списка, запросы, коммиты)
- **Антипаттерны** (8 пунктов «НЕ делать»)
- **История инцидентов** (5 инцидентов → 5 правил)

Расширенное описание: [`docs/AGENTS_MD.md`](docs/AGENTS_MD.md).

---

## Что внутри

### Анализ BSL-кода (11 анализаторов, 150+ правил)

| Компонент | Правил | Что проверяет |
|-----------|--------|---------------|
| **security_auditor** | 15 | SQL-инъекции, Выполнить(), хардкод паролей, COM, RLS, path traversal |
| **check_1c_standards** | 56 | Стиль кода, имена, длина строк, запросы, клиент-сервер |
| **transaction_checker** | 6 | Несбалансированные транзакции, без Try/Catch, интерактив |
| **query_analyzer** | 10 | SELECT *, LIKE %, функции в WHERE, JOIN без ON |
| **code_metrics** | 10 | LOC, цикломатическая/когнитивная сложность, God Object, health score |
| **architecture_analyzer** | 12 | Циклы зависимостей, мёртвый код, layering, regions |
| **form_quality_checker** | 9 | Пустые/перегруженные формы, кнопки без команд |
| **skd_quality_checker** | 9 | СКД без параметров, пустые запросы, перегрузка |
| **check_metadata_standards** | 18 | XML метаданных 1С |
| **code_validator** | — | BSL/XML синтаксис, структура, области |
| **BSL Language Server** | 187 | Внешний Java-анализатор (v1.0.1) |

### Парсинг метаданных 1С

| Компонент | Что делает |
|-----------|------------|
| **metadata_extractor** | Единый парсер 35 типов объектов из XML-выгрузки |
| **api-reference** | BSL модули с экспортными методами |
| **skd_parser** | Парсинг СКД-схем + trace mode (трассировка поля) |
| **form_analyzer** | Полный анализ форм: элементы, DataPath, события |
| **cf_extractor** | Собственный парсер .cf без v8unpack |
| **call_graph** | Граф вызовов BSL-методов |
| **dependency_graph** | Граф зависимостей метаданных (networkx) |

### Генерация кода (JSON DSL → XML)

| Компилятор | Что генерирует | Объектов |
|------------|----------------|----------|
| **MetaCompiler** | Метаданные 1С | 23 типа (Catalog, Document, Enum, и т.д.) |
| **FormCompiler** | Управляемые формы (Form.xml) | — |
| **SkdCompiler** | СКД-схемы (DataCompositionSchema) | — |
| **MxlCompiler** | MXL-макеты (печатные формы) | — |
| **RoleCompiler** | Роли 1С (Rights.xml) | — |

### Работа с расширениями (CFE)

| Операция | Что делает |
|----------|------------|
| **cfe_borrow** | Заимствование объекта (ObjectBelonging=Adopted) |
| **cfe_patch_method** | Генерация &Перед/&После/&ИзменениеИКонтроль |
| **cfe_diff** | Анализ расширения: что заимствовано, что перехвачено |

### Инфраструктура и инструменты

| Компонент | Что даёт |
|-----------|----------|
| **SARIF reporter** | SARIF 2.1.0 — аннотации в GitHub Code Scanning |
| **OpenSpec manager** | Specification-Driven Development (proposal/tasks/design) |
| **Session manager** | Сохранение/восстановление AI-сессий |
| **DslCompiler** | Единый фасад для 5 компиляторов |
| **TaskProcessor** | Единый пайплайн для CLI и MCP (7 источников + 7 анализаторов) |
| **ConfigManager** | Валидация исходников + freshness check индексов |
| **DataPackage** | Persistence данных через GitHub Releases |
| **EpfFactory** | Создание .epf с нуля без 1С (шаблоны v8unpack + BSL LS + round-trip) |
| **img_grid** | Сетка на скриншот печатных форм для LLM |
| **BM25 + триграммы** | Семантический поиск по методам платформы 1С |

---

## Stability Matrix

> Этап 4.2: явная маркировка стабильности каждой подсистемы.
> Проект в статусе **Beta** (см. [ROADMAP.md](ROADMAP.md#критерии-перехода-beta--production-ready)).

| Подсистема | Стабильность | Описание |
|------------|--------------|----------|
| **MCP server** (10 tools) | ✅ Stable | Основная функциональность, 1598 тестов |
| **CLI** (19 команд) | ✅ Stable | Все команды работают, тесты проходят |
| **BSL анализаторы** (11 шт, 150+ правил) | ✅ Stable | 62 правил в 5 модулях (Этап 2.1) |
| **DSL компиляторы** (5 типов) | ✅ Stable | meta, form, skd, mxl, role |
| **CFE manager** (borrow/patch/diff) | ✅ Stable | Декомпозирован в Этапе 2.5 |
| **Config manager** (add/build/validate) | ✅ Stable | Основной workflow |
| **Metadata extractor** (35 типов) | ✅ Stable | Перенесён в services.metadata (Этап 2.3) |
| **Search** (BM25 + vector) | ✅ Stable | Гибридный поиск с fallback |
| **Dependency graph** (networkx) | ✅ Stable | Граф зависимостей метаданных |
| **EpfFactory** (создание .epf) | ⚠️ Beta | Декомпозирован (Этап 2.2), но v8unpack workaround (ADR-0007) |
| **SARIF reporter** | ⚠️ Beta | Работает, но требует тестов на реальных CI |
| **OpenSpec manager** | ⚠️ Beta | SDD workflow, минимальное использование |
| **Session manager** | ⚠️ Beta | Сохранение/восстановление сессий |
| **EDT parser** | 🔬 Experimental | MVP (P2.1), 2 TODO (owners, register_records) |
| **RAG с Ollama** | 🔬 Experimental | Опциональная фича, требует Ollama |
| **Prometheus metrics** | 🔬 Experimental | Опционально, NoOp fallback |
| **SaaS/Enterprise/Plugin** | ❄️ Frozen | Перенесены в `experimental/` (ADR-0006) |

**Легенда:**
- ✅ **Stable** — основная функциональность, тесты проходят, API стабильно
- ⚠️ **Beta** — работает, но может измениться API или поведение
- 🔬 **Experimental** — MVP, может не работать в edge cases
- ❄️ **Frozen** — заморожено, не поддерживается (см. ADR-0006)

---

## Быстрый старт

### Установка

```bash
# 1. Клонировать
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# 2. Установить Python-пакет
pip install -e ".[dev,mcp]"

# 3. Установить BSL LS (опционально, для analyze_bsl)
bash install.sh

# 4. Проверить окружение
1c-ai validate
```

### Установка через Docker

```bash
# Собрать образ (multi-stage, ~5 минут первый раз)
docker compose build cli

# Проверить окружение
docker compose run --rm cli validate

# Запустить MCP-сервер для Cursor / Claude Desktop
docker compose up mcp-server

# Запустить тесты
docker compose run --rm tests

# Получить coverage отчёт
docker compose run --rm coverage

# Запустить линтеры
docker compose run --rm lint
```

### Добавить конфигурацию 1С

```bash
# Из ZIP выгрузки Конфигуратора
1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"
1c-ai config build --name ut11

# → Распакует в data/configs/ut11/
# → Построит 5 индексов:
#   - unified-metadata-index.json (35 типов объектов)
#   - api-reference.json (BSL модули + методы)
#   - skd-index.json (СКД-схемы)
#   - form-index.json (формы + элементы)
#   - dependency-graph.json (граф зависимостей)
```

### Проверка актуальности индексов

```bash
# Проверить — устарели ли индексы (mtime source vs index)
1c-ai config build --name ut11 --check-freshness

# Проверить валидность исходников
1c-ai config build --name ut11 --validate

# Принудительная пересборка
1c-ai config build --name ut11 --force
```

---

## CLI команды

### Управление конфигурациями

```bash
1c-ai config list                          # список конфигураций
1c-ai config add --name X --zip X.zip      # добавить из ZIP
1c-ai config build --name X                # построить индексы
1c-ai config build --name X --force        # принудительная пересборка
1c-ai config build --name X --check-freshness  # проверить актуальность
1c-ai config build --name X --validate     # проверить исходники
```

### Анализ BSL-кода

```bash
1c-ai standards module.bsl                 # 62 правил стандартов 1С
1c-ai bsl analyze module.bsl               # BSL LS (187 диагностик)
1c-ai bsl baseline module.bsl              # сохранить baseline
1c-ai bsl diff module.bsl                  # только новые ошибки
1c-ai solve check module.bsl --level full  # все 7 анализаторов
1c-ai solve check module.bsl --sarif out.sarif  # SARIF для GitHub
```

### Поиск

```bash
1c-ai search "найти элемент по коду"       # BM25 по методам платформы
1c-ai search-code "создать заказ" --config ut11  # BM25 по коду конфигурации
1c-ai call-graph --config ut11 --action stats    # граф вызовов методов
```

### Граф зависимостей метаданных

```bash
1c-ai depgraph build --name ut11           # построить граф
1c-ai depgraph query --name ut11 \
  --query-type what_depends_on \
  --object "Catalog.Контрагенты"           # кто зависит от объекта
1c-ai depgraph query --name ut11 --query-type find_cycles      # циклы
1c-ai depgraph query --name ut11 --query-type find_unused_objects  # мёртвый код
1c-ai depgraph validate --name ut11        # проверить что граф DAG
```

### JSON DSL → XML компиляторы

```bash
1c-ai dsl meta --json-file catalog.json --output-dir /path/to/config
1c-ai dsl form --json-file form.json --output-path Form.xml
1c-ai dsl skd --json-file skd.json --output-path Template.xml
1c-ai dsl mxl --json-file mxl.json --output-path Template.xml
1c-ai dsl role --json-file role.json --output-dir /path/to/Roles
```

### Работа с расширениями (CFE)

```bash
1c-ai cfe borrow --extension-path /ext --config-path /cfg \
  --object-ref "Catalog.Контрагенты"
1c-ai cfe patch --extension-path /ext \
  --module-path "Catalog.Контрагенты.ObjectModule" \
  --method-name ПриЗаписи --interceptor-type Before
1c-ai cfe diff --extension-path /ext --config-path /cfg
```

### Анализ СКД

```bash
1c-ai skd-trace Template.xml Сумма         # трассировка поля через всю цепочку
1c-ai inspect skd Template.xml --mode trace --name Сумма
```

### Единый inspect (анализ объектов 1С)

```bash
1c-ai inspect cf /path/to/Configuration.xml       # обзор конфигурации
1c-ai inspect meta /path/to/Catalog.xml            # объект метаданных
1c-ai inspect form /path/to/Form.xml               # форма
1c-ai inspect skd /path/to/Template.xml            # СКД
1c-ai inspect mxl /path/to/Template.xml            # MXL макет
1c-ai inspect role /path/to/Rights.xml             # роль
1c-ai inspect subsystem /path/to/Subsystem.xml     # подсистема
1c-ai inspect depgraph /path --name ut11           # граф зависимостей
```

### OpenSpec (управление изменениями)

```bash
1c-ai openspec init                             # инициализировать
1c-ai openspec proposal --change-id add-feature \
  --title "Add Feature" --tasks "T1,T2,T3"
1c-ai openspec list                             # список changes
1c-ai openspec update --change-id add-feature --task-index 0 --completed
1c-ai openspec archive --change-id add-feature  # архивировать
1c-ai openspec validate --change-id add-feature # валидация
```

### Управление сессиями

```bash
1c-ai session save --task "Реализация CFE" \
  --completed "borrow,patch" --pending "diff"
1c-ai session restore                           # восстановить
1c-ai session retro                             # ретроспектива
1c-ai session clear                             # очистить
```

### Persistence данных

```bash
1c-ai data save-pkg --output data-package.zip   # сохранить
1c-ai data load-pkg data-package.zip            # восстановить
1c-ai data autosave                             # автосохранение
1c-ai data autoload                             # автовосстановление
1c-ai data release-push                         # загрузить в GitHub Releases
1c-ai data release-pull                         # скачать из GitHub Releases
```

### Создание внешних обработок (.epf)

```bash
1c-ai epf-factory create \
    --name "МояОбработка" \
    --synonym "Моя обработка" \
    --bsl module.bsl \
    --output МояОбработка.epf                   # EPF с нуля, без 1С
1c-ai epf-factory templates                     # список шаблонов
```

> Полный цикл: шаблоны v8unpack → подстановка UUID → BSL-код → проверка через BSL LS → сборка → round-trip. Не требует установленной 1С. [Подробнее →](docs/EPF_FACTORY.md)

---

## Подключение к IDE / LLM через MCP

Проект включает собственный MCP-сервер с 10 tools для Cursor / Claude Desktop / VS Code / JetBrains.

### Настройка

**Cursor / Claude Desktop** — добавьте в `mcp.json`:

```json
{
  "mcpServers": {
    "1c-ai": {
      "command": "1c-ai-mcp",
      "args": []
    }
  }
}
```

**VS Code / JetBrains** — через stdio:

```bash
1c-ai mcp serve
```

### Категории MCP tools

| Категория | Tools | Назначение |
|-----------|-------|------------|
| **Конфигурации** | list_configs, data_status | Управление конфигурациями |
| **Поиск** | search_1c_methods, search_code | BM25 поиск по платформе и коду |
| **Анализ BSL** | analyze_bsl, check_standards, audit_security, check_transactions, analyze_queries, get_code_metrics, analyze_architecture | 11 анализаторов |
| **Метаданные** | get_object_structure, get_skd_schema, get_form_structure, get_form_elements, get_api_reference, call_graph | Парсинг и структура |
| **Качество** | check_form_quality, check_skd_quality, diff_configs | Проверка качества |
| **Генерация** | generate_processing, generate_report, build_epf, validate_generated | Кодогенерация |
| **Контекст** | solve_context, solve_check | TaskProcessor (7 источников + 7 анализаторов) |
| **База знаний** | get_knowledge | Паттерны, антипаттерны |
| **DSL компиляторы** | dsl_compile_meta, dsl_compile_form, dsl_compile_skd, dsl_compile_mxl, dsl_compile_role | JSON → XML |
| **CFE** | cfe_borrow, cfe_patch_method, cfe_diff | Расширения |
| **СКД** | skd_trace | Трассировка поля |
| **Граф зависимостей** | build_dependency_graph, dependency_query | networkx граф |
| **OpenSpec** | openspec_proposal, openspec_list, openspec_update_task, openspec_archive | SDD |
| **Inspect** | inspect | Единый анализ объектов |

---

## Архитектура

```
data/               ← исходные XML выгрузки Конфигуратора
derived/            ← индексы (metadata, api, skd, form, depgraph)
knowledge_base/     ← паттерны, антипаттерны, best practices
templates/          ← шаблоны BSL/XML
runtime/            ← состояние (config-registry, session-state)
docs/1c-xml-specs/  ← 19 спецификаций XML-форматов 1С (16K строк)
openspec/           ← Specification-Driven Development
```

### OOP-слой (src/)

```
src/
├── models/                 Конфигурация как данные
│   ├── configuration.py    Configuration dataclass
│   ├── config_registry.py  ConfigurationRegistry
│   └── task.py             TaskContext + CheckResult + Violation
├── services/               Бизнес-логика
│   ├── path_manager.py     PathManager (4-слойная архитектура)
│   ├── config_manager.py   add/build/validate/freshness
│   ├── task_processor.py   Единый пайплайн CLI/MCP
│   ├── dsl_compiler.py     5 компиляторов JSON → XML
│   ├── cfe_manager.py      Работа с расширениями CFE (Этап 2.5)
│   ├── diff.py             Сравнение конфигураций (Этап 1.2-g3)
│   ├── dependency_graph.py Граф зависимостей (networkx)
│   ├── openspec_manager.py SDD управление изменениями
│   ├── session_manager.py  Управление AI-сессиями
│   ├── sarif_reporter.py   SARIF 2.1.0 для GitHub Code Scanning
│   ├── bsl_analyzer.py     BSL LS wrapper + baseline/diff
│   ├── call_graph.py       Граф вызовов BSL-методов
│   ├── search_bm25.py      BM25 + триграммы + стеммер
│   ├── search_code.py      BM25 по методам конфигураций
│   ├── knowledge_base.py   База знаний
│   ├── data_package.py     Persistence (autosave/autoload)
│   ├── github_releases.py  Push/pull через GitHub REST API
│   ├── backup_manager.py   Backup/restore
│   ├── logger.py           Structlog (структурированное логирование)
│   ├── analyzers/          BSL анализаторы (Этап 1.2-g1)
│   │   ├── __init__.py     Analyzer Protocol + Adapters + _load_script
│   │   ├── standards/      62 правил в 5 модулях (Этап 2.1)
│   │   │   ├── style.py    10 правил стиля кода
│   │   │   ├── architecture.py  12 правил архитектуры
│   │   │   ├── queries.py  7 правил запросов
│   │   │   ├── client_server.py  13 правил клиент-сервер
│   │   │   └── misc.py     14 правил разного
│   │   ├── security_auditor.py   15 правил безопасности
│   │   ├── code_metrics.py       10 метрик кода
│   │   ├── transaction_checker.py  6 правил транзакций
│   │   ├── query_analyzer.py     10 правил запросов
│   │   ├── architecture_analyzer.py  12 правил архитектуры
│   │   ├── form_quality_checker.py   9 правил форм
│   │   ├── skd_quality_checker.py    9 правил СКД
│   │   └── check_metadata_standards.py  18 правил метаданных
│   ├── epf/                EpfFactory утилиты (Этап 2.2)
│   │   ├── result.py       EpfFactoryResult dataclass
│   │   ├── json_patcher.py Патчеры JSON v8unpack
│   │   ├── bsl_validator.py  BSL LS валидация
│   │   └── round_trip.py   Round-trip проверка
│   ├── epf_factory.py      Создание .epf (facade, Этап 2.2)
│   ├── code_generator.py   Генерация обработок/отчётов (Этап 1.2-g2)
│   ├── code_validator.py   Валидация BSL/XML (Этап 1.2-g2)
│   ├── epf_builder.py      Упаковщик .epf (Этап 1.2-g2)
│   ├── metadata/           Парсинг метаданных 1С (Этап 2.3)
│   │   └── extractor.py    35 типов объектов
│   ├── builders/           Построение индексов (Этап 2.4)
│   │   └── config_index.py unified-metadata-index
│   ├── cfe/                CFE утилиты (Этап 2.5)
│   │   ├── result.py       BorrowResult, PatchMethodResult, CfeDiffResult
│   │   └── cli.py          CLI helpers
│   └── cf/                 CF парсер (Этап 1.2-g7)
│       └── extractor.py    Парсер .cf контейнера
├── mcp_server.py           MCP-сервер (10 tools)
├── mcpserver/              MCP handlers (Этап 1.2)
│   ├── handlers/           8 групп handlers
│   └── tools/              Tool definitions
├── cli_commands/           CLI команды (Этап 1.2)
├── project.py              Project — оркестратор
├── cli.py                  Единый CLI (19 команд)
└── exceptions.py           Кастомные исключения
```

> **Этапы 1-2**: 14 скриптов перенесено из `scripts/` в `src/services/`,
> 5 god-файлов декомпозированы. См. [docs/AUDIT_SCRIPTS_SERVICES.md](docs/AUDIT_SCRIPTS_SERVICES.md).

---

## Тестирование

```bash
# Все тесты
python -m pytest tests/ -v

# Только ключевые тесты (быстро)
python -m pytest tests/test_dsl_compiler.py tests/test_cfe_manager.py \
  tests/test_dependency_graph.py tests/test_openspec_manager.py \
  tests/test_session_manager.py tests/test_skd_trace.py -v

# С coverage
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=30

# Property-based тесты (hypothesis)
python -m pytest tests/test_property.py -v --hypothesis-show-statistics

# Benchmarks
python -m pytest tests/test_benchmarks_synthetic.py --benchmark-only -v

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Статистика тестов

| Метрика | Значение |
|---------|----------|
| Тестовых файлов | 100 |
| Тест-функций | 1595 (unit + integration + e2e + snapshot) |
| Property-based тестов | 13 (hypothesis, ~1300 cases) |
| Synthetic benchmarks | 19 |
| Coverage gate | 70% (цель: 85%, факт: 71.4%) |
| Pre-commit hooks | ruff + mypy + pytest |

---

## CI/CD

| Workflow | Что делает |
|----------|------------|
| `ci.yml` — lint | ruff check + format + mypy |
| `ci.yml` — version-check | Проверка консистентности версий |
| `ci.yml` — test | pytest (unit + integration + e2e + benchmarks) |
| `ci.yml` — coverage | pytest --cov=src --cov-fail-under=30 |
| `ci.yml` — benchmark | Synthetic benchmarks + сравнение с baseline |
| `code-scanning.yml` | SARIF → GitHub Code Scanning (аннотации в PR) |

---

## Документация

| Раздел | Где |
|--------|-----|
| XML-спецификации 1С | `docs/1c-xml-specs/` — 19 файлов, 16K строк |
| Архитектура | `docs/ARCHITECTURE.md` |
| API | `docs/API.md` |
| MCP интеграция | `docs/MCP_INTEGRATION.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |
| База знаний | `knowledge_base/` — паттерны, антипаттерны, best practices |
| История изменений | `CHANGELOG.md` |

---

## Технологии

| Компонент | Технология |
|-----------|------------|
| Основной язык | Python 3.10+ |
| BSL Language Server | Java 17+ (v1.0.1, 187 диагностик) |
| MCP SDK | Python mcp |
| Граф зависимостей | networkx |
| Структурированное логирование | structlog |
| Линтинг | ruff + mypy |
| Тестирование | pytest + hypothesis + pytest-benchmark |
| Контейнеризация | Docker (multi-stage) + docker-compose |
| CI/CD | GitHub Actions (5 jobs + SARIF) |

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

---

## Благодарности

- [1c-ai-development-kit](https://github.com/Arman-Kudaibergenov/1c-ai-development-kit) — за JSON DSL спецификации и документацию по XML-форматам 1С
- [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) — за статический анализ BSL
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) — за Model Context Protocol
