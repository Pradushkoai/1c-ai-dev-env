# Архитектура

## Обзор

Проект использует **4-слойную архитектуру** с чётким разделением ответственности:

```
┌──────────────────────────────────────────────────┐
│  data/          ИСХОДНЫЕ ДАННЫЕ (от пользователя) │
│  ├── configs/   Конфигурации 1С (распакованные)   │
│  └── archives/  ZIP архивы                        │
├──────────────────────────────────────────────────┤
│  derived/       ПРОИЗВОДНЫЕ (генерируются)         │
│  ├── configs/   Индексы по конфигурациям          │
│  │   └── <name>/                                  │
│  │       ├── unified-metadata-index.json          │
│  │       ├── api-reference.json                   │
│  │       ├── skd-index.json                       │
│  │       ├── form-index.json                      │
│  │       └── dependency-graph.json                │
│  └── platform/  Индексы платформы 1С              │
│      └── fast-search-index.json (BM25 v2)         │
├──────────────────────────────────────────────────┤
│  knowledge_base/  БАЗА ЗНАНИЙ                     │
│  ├── patterns/      Паттерны (справочник, формы)  │
│  ├── antipatterns/  Антипаттерны                  │
│  ├── best_practices/ Best practices               │
│  └── query_optimization/ Оптимизация запросов     │
├──────────────────────────────────────────────────┤
│  runtime/       ФАЙЛЫ РАБОТЫ                       │
│  ├── config-registry.json  Реестр конфигов        │
│  └── session-state.json    Состояние AI-сессии    │
├──────────────────────────────────────────────────┤
│  docs/1c-xml-specs/  СПЕЦИФИКАЦИИ XML 1С          │
│  ├── 12 спецификаций XML-форматов                 │
│  ├── 5 спецификаций JSON DSL                      │
│  └── build-spec.md                                │
├──────────────────────────────────────────────────┤
│  openspec/      SPECIFICATION-DRIVEN DEV          │
│  ├── project.md                                    │
│  ├── changes/   Активные изменения                │
│  ├── specs/     Утверждённые спецификации         │
│  └── archive/   Завершённые изменения             │
└──────────────────────────────────────────────────┘
```

## OOP-слой (src/)

```
src/
├── models/                 Конфигурация как данные
│   ├── configuration.py    Configuration dataclass
│   ├── config_registry.py  ConfigurationRegistry
│   └── task.py             TaskContext + CheckResult + Violation + CodeMetric
│
├── services/               Бизнес-логика (21 сервис)
│   ├── path_manager.py     PathManager (4-слойная архитектура)
│   ├── config_manager.py   add/build/validate/freshness — управление конфигами
│   ├── task_processor.py   Единый пайплайн CLI/MCP (7 источников + 7 анализаторов)
│   ├── dsl_compiler.py     5 компиляторов JSON → XML (meta, form, skd, mxl, role)
│   ├── cfe_manager.py      Работа с расширениями CFE (borrow, patch, diff)
│   ├── dependency_graph.py Граф зависимостей метаданных (networkx)
│   ├── openspec_manager.py Specification-Driven Development
│   ├── session_manager.py  Управление AI-сессиями (save/restore/retro)
│   ├── sarif_reporter.py   SARIF 2.1.0 для GitHub Code Scanning
│   ├── bsl_analyzer.py     BSL LS wrapper + baseline/diff
│   ├── call_graph.py       Граф вызовов BSL-методов
│   ├── search_bm25.py      BM25 + триграммы + стеммер (поиск по платформе)
│   ├── search_code.py      BM25 по методам конфигураций
│   ├── knowledge_base.py   База знаний (паттерны, антипаттерны)
│   ├── data_package.py     Persistence (autosave/autoload)
│   ├── github_releases.py  Push/pull через GitHub REST API
│   ├── backup_manager.py   Backup/restore
│   ├── epf_factory.py      Создание .epf с нуля без 1С (шаблоны + BSL LS + round-trip)
│   └── logger.py           Structlog (структурированное логирование)
│
├── mcp_server.py           MCP-сервер (12 tools)
├── project.py              Project — оркестратор
├── cli.py                  Единый CLI (19 команд)
└── exceptions.py           Кастомные исключения
```

## Скрипты (scripts/)

39 скриптов для парсинга, анализа и генерации:

### Парсеры
- `metadata_extractor.py` — единый парсер 35 типов объектов 1С
- `build_api_reference.py` — построение API-справочника
- `skd_parser.py` — парсинг СКД + trace mode
- `form_analyzer.py` — анализ форм
- `cf_extractor.py` — собственный парсер .cf
- `xml_parser.py` — безопасный XML-парсер (lxml/etree)

### Анализаторы
- `security_auditor.py` — 15 правил безопасности
- `check_1c_standards.py` — 56 правил стандартов
- `transaction_checker.py` — 6 правил транзакций
- `query_analyzer.py` — 10 правил запросов
- `code_metrics.py` — 10 метрик кода
- `architecture_analyzer.py` — 12 правил архитектуры
- `form_quality_checker.py` — 9 правил качества форм
- `skd_quality_checker.py` — 9 правил качества СКД
- `check_metadata_standards.py` — 18 правил метаданных
- `code_validator.py` — валидация BSL/XML
- `diff_analyzer.py` — сравнение версий конфигурации

### Генераторы
- `code_generator.py` — генерация обработок и отчётов
- `epf_builder.py` — упаковка .epf (без установленной 1С)
- `img_grid.py` — сетка на скриншот печатных форм

### Инфраструктура
- `fast_search_1c.py` — BM25 индекс методов платформы
- `build_syntax_helper_index.py` — индекс синтаксис-хелпера
- `hbk_extractor.py` — извлечение из .hbk файлов

## Ключевые принципы

1. **Кроссплатформенность** — Python, работает на Linux/Mac/Windows
2. **Без установленной 1С** — работаем с XML-выгрузкой, не требуем 1С:Предприятие
3. **Без зависимости от AI-ассистента** — CLI + MCP, работает с любым AI
4. **Единая бизнес-логика** — TaskProcessor используется и CLI и MCP
5. **Тестирование** — 328 тестов + property-based (hypothesis) + benchmarks
6. **CI/CD** — 5 jobs (lint + test + coverage + benchmark + SARIF)
7. **Структурированное логирование** — structlog (JSON для CI, console для dev)
