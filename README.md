# 1C AI Development Environment

> **Универсальная среда разработки на 1С с ИИ-ассистентом**: извлечение и анализ метаданных из XML выгрузок 1С, 27 MCP tools для IDE/LLM, аудит безопасности (15 правил), метрики кода (10 показателей), проверка транзакций (6 правил), анализ запросов (10 правил), анализ архитектуры (10 правил), генерация обработок и отчётов на СКД, упаковка .epf файлов.

[![Version](https://img.shields.io/badge/version-4.10.0-brightgreen.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)
[![Tests](https://img.shields.io/badge/tests-504%20passing-success.svg)](#тесты)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-27-blue.svg)](#подключение-к-ide--llm-через-mcp)

---

## Что внутри

| Компонент | Что даёт |
|-----------|----------|
| **metadata_extractor** | Единый парсер 35+ типов объектов 1С из XML выгрузки (Catalog, Document, Register, Roles, Subsystems, Events, Jobs, и т.д.) |
| **api-reference** | BSL модули с экспортными методами (CommonModules, ObjectModule, ManagerModule, Forms, Commands) |
| **skd_parser** | Парсинг СКД-схем (DataCompositionSchema) — наборы данных, параметры, запросы |
| **form_analyzer** | Полный анализ форм: элементы, DataPath, события, дерево ChildItems |
| **security_auditor** | 15 правил: SQL-инъекции, Выполнить(), хардкод паролей/токенов, COM, RLS, path traversal |
| **code_metrics** | 10 метрик: LOC, cyclomatic/cognitive complexity, вложенность, дублирование, God Object, health score |
| **transaction_checker** | 6 правил: несбалансированные транзакции, без Try/Catch, интерактив, вложенность |
| **query_analyzer** | 10 правил: SELECT *, LIKE %, функции в WHERE, JOIN без ON, временные таблицы |
| **architecture_analyzer** | 10 правил: циклы зависимостей, God Object, мёртвый код, layering, regions |
| **form_quality_checker** | 10 правил: пустые/перегруженные формы, кнопки без команд, дубли |
| **skd_quality_checker** | 10 правил: СКД без параметров, пустые запросы, перегрузка |
| **diff_analyzer** | Сравнение версий конфигурации: добавлено/удалено/изменено |
| **code_generator** | Генерация обработок и отчётов на СКД (BSL + XML шаблоны) |
| **epf_builder** | Упаковка в .epf файл (контейнеры 1С) |
| **code_validator** | Валидация BSL/XML (синтаксис, структура, области) |
| **BSL Language Server** | 187 диагностик через Java (v1.0.1) |
| **check_1c_standards** | 56 правил стилистики, запросов, клиент-сервера |
| **check_metadata_standards** | 18 правил для XML метаданных |
| **knowledge_base** | Паттерны, антипаттерны, best practices (6 статей) |
| **BM25 + триграммы + стеммер** | Семантический поиск по методам платформы 1С |
| **MCP-сервер** | 27 tools для Cursor / Claude Desktop / VS Code / JetBrains |
| **DataPackage** | Persistence данных между сессиями (GitHub Releases) |

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

### Добавить конфигурацию 1С

```bash
# Из ZIP выгрузки Конфигуратора (рекомендуется — полные метаданные)
1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"
1c-ai config build --name ut11

# → Распакует в data/configs/ut11/
# → Построит 4 индекса:
#   - derived/configs/ut11/unified-metadata-index.json (35 типов объектов)
#   - derived/configs/ut11/api-reference.json (BSL модули + методы)
#   - derived/configs/ut11/skd-index.json (СКД-схемы)
#   - derived/configs/ut11/form-index.json (формы + элементы)
```

### Восстановление из GitHub Release

```bash
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-pull     # скачать data-package
1c-ai data autoload         # восстановить конфигурации + индексы
1c-ai config list           # проверить
```

---

## Текущее состояние (v4.10.0)

### Конфигурация УТ11 (полная XML выгрузка)

| Метрика | Значение |
|---------|----------|
| BSL файлов | 7 141 |
| XML файлов | 20 411 |
| Типов объектов | 35 |
| Всего объектов | 7 128 |
| Реквизитов | 14 667 |
| Табличных частей | 1 064 |
| Форм | 2 985 |
| Команд | 484 |
| Ролей (с правами) | 641 |
| Подсистем | 42 |
| Подписок на события | 225 |
| Регламентных заданий | 154 |
| СКД-схем | 360 |
| Элементов форм | 59 489 |
| Событий форм | 7 973 |
| BSL модулей (api-reference) | 6 729 |
| Экспортных методов | 21 380 |

---

## Архитектура

```
data/           ← исходные XML выгрузки Конфигуратора
derived/        ← индексы (unified-metadata, api-reference, skd, form)
knowledge_base/ ← паттерны, антипаттерны, best practices
templates/      ← шаблоны BSL/XML для генерации
runtime/        ← состояние (config-registry, worklog)
```

### OOP-слой (src/)

```
src/
├── models/                 Конфигурация как данные
│   ├── configuration.py    Configuration dataclass
│   └── config_registry.py  ConfigurationRegistry
├── services/               Бизнес-логика
│   ├── path_manager.py     PathManager (4-слойная архитектура)
│   ├── config_manager.py   add/build — запускает все 4 парсера
│   ├── bsl_analyzer.py     BSL LS wrapper + baseline/diff
│   ├── search.py           TF-IDF поиск (legacy)
│   ├── search_bm25.py      BM25 + триграммы + стеммер
│   ├── search_code.py      BM25 по методам конфигураций
│   ├── call_graph.py       Граф вызовов методов
│   ├── knowledge_base.py   База знаний (паттерны)
│   ├── data_package.py     Persistence (autosave/autoload)
│   ├── github_releases.py  Push/pull через GitHub REST API
│   └── backup_manager.py   Backup/restore
├── mcp_server.py           MCP-сервер (27 tools)
├── project.py              Project — оркестратор
├── cli.py                  Единый CLI
└── exceptions.py           Кастомные исключения
```

### Скрипты (scripts/)

```
scripts/
├── metadata_extractor.py     Единый парсер 35 типов объектов
├── build_api_reference.py    BSL модули + экспортные методы
├── skd_parser.py             Парсер СКД-схем
├── form_analyzer.py          Анализ форм (ChildItems, DataPath, Events)
├── form_indexer.py           Индексация модулей форм
├── improved_cf_adapter.py    .cf → XML (извлечение BSL)
├── cf_extractor.py           Распаковка .cf (Container32/64)
├── v8_metadata_parser.py     Парсер метаданных v8unpack
├── security_auditor.py       15 правил безопасности
├── code_metrics.py           10 метрик кода
├── transaction_checker.py    6 правил транзакций
├── query_analyzer.py         10 правил запросов
├── architecture_analyzer.py  10 правил архитектуры
├── form_quality_checker.py   10 правил качества форм
├── skd_quality_checker.py    10 правил качества СКД
├── diff_analyzer.py          Сравнение версий
├── code_generator.py         Генерация обработок/отчётов
├── epf_builder.py            Упаковка .epf
├── code_validator.py         Валидация BSL/XML
├── check_1c_standards.py     56 правил стандартов
├── check_metadata_standards.py  18 правил метаданных
└── build_syntax_helper_index.py  Индекс синтакс-помощника
```

---

## Команды CLI

```bash
# Конфигурации
1c-ai config list                                # список
1c-ai config add --name X --zip Y                # добавить из ZIP
1c-ai config add --name X --cf Y                 # добавить из .cf
1c-ai config build --name X                      # все 4 индекса
1c-ai config build-all                           # все конфигурации

# Поиск
1c-ai search "найти элемент по коду"             # методы платформы
1c-ai search-code "создать заказ" --config ut11  # методы конфигурации

# Граф вызовов
1c-ai call-graph --config ut11 --action stats
1c-ai call-graph --config ut11 --action callers --module ОбменДокументы --method ВыполнитьОбмен

# Анализ .bsl
1c-ai bsl analyze <path>                         # 187 диагностик (BSL LS)
1c-ai standards <path>                           # 56 правил (без Java)

# Решение задач
1c-ai solve context "создать справочник" --config ut11  # 8 источников контекста
1c-ai solve check <file.bsl> --level full               # 7 анализаторов

# MCP-сервер
1c-ai mcp serve                                  # запустить (stdio)
1c-ai mcp tools                                  # список 27 tools

# Данные
1c-ai data status                                # что доступно
1c-ai data autosave [--include-raw]              # сохранить
1c-ai data autoload                              # восстановить
1c-ai data release-push                          # в GitHub Release
1c-ai data release-pull                          # из GitHub Release

# Проверка окружения
1c-ai validate
```

---

## Подключение к IDE / LLM через MCP

27 MCP tools для Cursor, Claude Desktop, VS Code, JetBrains.

### Конфиг

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "python3",
      "args": ["-m", "src.cli", "mcp", "serve"],
      "cwd": "/path/to/1c-ai-dev-env"
    }
  }
}
```

### Доступные tools (27)

**Поиск и навигация (6):**
| Tool | Что делает |
|------|-----------|
| `list_configs` | Список конфигураций |
| `search_1c_methods` | BM25 поиск по методам платформы |
| `search_code` | BM25 поиск по методам конфигурации |
| `call_graph` | Граф вызовов (callers, callees, dead-code, cycles) |
| `get_api_reference` | API-справочник модулей |
| `get_form_elements` | Элементы формы |

**Извлечение данных (4):**
| Tool | Что делает |
|------|-----------|
| `get_object_structure` | Полная структура объекта (35 типов) |
| `get_skd_schema` | СКД-схема отчёта |
| `get_form_structure` | Дерево элементов формы с DataPath и событиями |
| `data_status` | Статус данных проекта |

**Анализ и аудит (8):**
| Tool | Что делает |
|------|-----------|
| `analyze_bsl` | BSL LS — 187 диагностик |
| `check_standards` | 56 правил стандартов 1С |
| `audit_security` | 15 правил безопасности |
| `get_code_metrics` | 10 метрик (LOC, complexity, God Object, health score) |
| `check_transactions` | 6 правил транзакций |
| `analyze_queries` | 10 правил запросов 1С |
| `analyze_architecture` | 10 правил архитектуры |
| `check_form_quality` | 10 правил качества форм |

**Качество и сравнение (3):**
| Tool | Что делает |
|------|-----------|
| `check_skd_quality` | 10 правил качества СКД |
| `diff_configs` | Сравнение версий конфигурации |
| `validate_generated` | Валидация сгенерированного кода |

**Генерация (3):**
| Tool | Что делает |
|------|-----------|
| `generate_processing` | Генерация внешней обработки |
| `generate_report` | Генерация отчёта на СКД |
| `build_epf` | Упаковка в .epf файл |

**Контекст и знания (3):**
| Tool | Что делает |
|------|-----------|
| `solve_context` | Сбор контекста (8 источников) |
| `solve_check` | Полная проверка (7 анализаторов) |
| `get_knowledge` | База знаний (паттерны, антипаттерны) |

📖 **Полная документация**: [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md)

---

## Единый стандарт обработки конфигурации

При загрузке новой конфигурации `config build` запускает 4 парсера:

```
data/configs/<name>/ (XML выгрузка)
    ↓
    1. metadata_extractor.py → unified-metadata-index.json
       (35 типов объектов, Roles, Subsystems, Events, Jobs, Configuration.xml)
    2. build_api_reference.py → api-reference.json
       (BSL модули, экспортные методы, формы, команды)
    3. skd_parser.py → skd-index.json
       (СКД-схемы, наборы данных, параметры, запросы)
    4. form_analyzer.py → form-index.json
       (формы, элементы, DataPath, события)
    ↓
derived/configs/<name>/
```

После этого работают 25 из 27 MCP tools.

## Единый стандарт обработки задачи

### solve context — сбор контекста (8 источников)

1. Методы платформы (BM25)
2. API конфигурации (api-reference)
3. Структура объектов (unified-metadata-index)
4. Подсистемы + Подписки на события + Регламентные задания
5. СКД-схемы (skd-index)
6. Формы (form-index)
7. База знаний (паттерны, best practices)
8. Стандарты (56 правил)

### solve check — проверка кода (7 анализаторов)

| Уровень | Анализаторы |
|---------|------------|
| quick | check_1c_standards + security + transactions + queries |
| standard | quick + BSL LS (187 диагностик) |
| full | standard + code_metrics + metadata_standards |

---

## Тесты

```bash
python3 -m pytest tests/ -v
```

**504 теста** покрывают:
- metadata_extractor (29 тестов: 35 типов объектов, Roles, Subsystems, Events)
- security_auditor (37 тестов: 15 правил)
- code_metrics (28 тестов: 10 метрик)
- transaction_checker (18 тестов: 6 правил)
- architecture_analyzer (10 тестов: 10 правил)
- query_analyzer (16 тестов: 10 правил)
- form_quality_checker (13 тестов: 10 правил)
- skd_quality_checker (10 тестов: 10 правил)
- diff_analyzer (13 тестов: сравнение версий)
- MCP-сервер (27 tools, E2E через stdio)
- ConfigManager, PathManager, Search, cf_extractor, и др.

---

## Persistence данных

```bash
# Сохранить
1c-ai data autosave --include-raw
1c-ai data release-push

# Восстановить
1c-ai data release-pull
1c-ai data autoload
```

---

## Roadmap

- ✅ **v4.1.0**: Единый парсер метаданных (35 типов объектов)
- ✅ **v4.2.0**: Security Audit (15 правил)
- ✅ **v4.3.0**: Code Metrics (10 метрик, health score)
- ✅ **v4.4.0**: Transaction Checker (6 правил)
- ✅ **v4.5.0**: Architecture Analyzer (10 правил)
- ✅ **v4.6.0**: Query Analyzer (10 правил)
- ✅ **v4.7.0**: Form Quality Checker (10 правил)
- ✅ **v4.8.0**: SKD Quality Checker + Diff Analyzer
- ✅ **v4.9.0**: 27 MCP tools, синхронизация версий
- ✅ **v4.10.0**: Единый стандарт обработки конфигураций и задач
- 🔲 **v4.11.0**: CLI команды для новых анализаторов
- 🔲 **v4.12.0**: Векторный поиск (fastembed + qdrant)

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Changelog

См. [CHANGELOG.md](CHANGELOG.md)
