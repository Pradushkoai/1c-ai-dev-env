# 1C AI Development Environment

> **Универсальная среда разработки на 1С с ИИ-ассистентом**: семантический поиск по 124 000+ методам, API-справочники конфигураций, анализ кода через BSL Language Server, проверка на 261 правило стандартов 1С, и **MCP-сервер** для интеграции с любой IDE/LLM (Cursor, Claude Desktop, VS Code, JetBrains).

[![Version](https://img.shields.io/badge/version-4.9.0-brightgreen.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)
[![Tests](https://img.shields.io/badge/tests-314%20passing-success.svg)](#тесты)

---

## Что внутри

| Компонент | Что даёт |
|-----------|----------|
| **BM25 + триграммы + стеммер** | Семантический поиск по 8141 методам платформы 1С (2 сек, без GPU) |
| **API-справочники** | 115 666 экспортных методов в 7419 модулях 4 конфигураций |
| **BSL Language Server v1.0.1** | 187 диагностик `.bsl` кода через Java |
| **check_1c_standards** | 56 правил стилистики, антипаттернов, запросов, клиент-сервера |
| **check_metadata_standards** | 18 правил для XML метаданных объектов |
| **cf_extractor** | Собственный парсер `.cf`/`.cfe`/`.epf` без v8unpack (Container32 + Container64) |
| **v8_metadata_parser V2** | Поддержка современного формата 1С 8.3.24+ (сдвинутые коды типов) |
| **hbk_extractor** | Распаковка `.hbk` синтакс-помощника 1С (80 файлов → 105469 HTML) |
| **MCP-сервер** | 8 tools для Cursor / Claude Desktop / VS Code / JetBrains |
| **DataPackage** | Persistence данных между сессиями (autosave/autoload) |
| **GitHub Releases** | Push/pull data-пакета через `gh` REST API |

---

## Быстрый старт

### Вариант 1: Установка с нуля

```bash
# 1. Клонировать
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# 2. Установить Python-пакет
pip install -e ".[dev,mcp]"

# 3. Проверить окружение
1c-ai validate
```

### Вариант 2: Восстановление из GitHub Release (если данные уже загружены)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env
pip install -e ".[dev,mcp]"

# 2. Установить BSL LS (опционально, для анализа .bsl)
bash install.sh

# 3. Восстановить данные из GitHub Release
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-pull     # скачать data-package (146 МБ)
1c-ai data autoload         # восстановить 4 конфигурации + BM25 индекс

# 4. Проверить
1c-ai config list           # 4 конфигурации
1c-ai search "найти элемент по коду"  # BM25 поиск
```

### Добавить новую конфигурацию

```bash
# Из ZIP выгрузки Конфигуратора
1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"

# Из .cf файла (через cf_extractor — без внешних зависимостей)
1c-ai config add --name erp --cf erp.cf --title "1С:ERP" --skip-build
1c-ai config build --name erp

# → Распакует в data/configs/erp/
# → Построит derived/configs/erp/api-reference.json (экспортные методы)
# → Построит derived/configs/erp/index.md (индекс метаданных)
```

### Программно (Python)

```python
from pathlib import Path
from src.project import Project

project = Project()

# Добавить конфигурацию
project.config_manager.add_from_cf("erp", Path("erp.cf"), "1С:ERP")
project.config_manager.build("erp")

# Поиск методов платформы (BM25 + триграммы)
results = project.search_methods("найти элемент по коду", limit=5)
for r in results:
    print(f"[{r['score']:.3f}] {r['name_ru']} — {r['syntax']}")

# API-справочник конфигурации
info = project.get_config_info("erp")
methods = project.get_api_methods("erp", "ОбщегоНазначения")

# Анализ .bsl файла
result = project.bsl_analyzer.analyze(Path("module.bsl"))
print(f"Найдено: {result.total} диагностик")
```

---

## Текущее состояние (v3.12.0)

### Загруженные конфигурации

| Конфигурация | Объектов | Модулей | Методов |
|--------------|---------|---------|---------|
| edo2 (ЭДО 2) | 2353 | 1473 | 22 506 |
| edo3 (ЭДО 3) | 2561 | 1646 | 24 266 |
| ut11 (УТ 11) | 1937 | 1118 | 15 809 |
| unp (УНП) | 5630 | 3182 | 53 085 |
| **Итого** | **12 481** | **7 419** | **115 666** |

**Платформа 1С**: 8141 методов (BM25 индекс, 11.7 МБ)

**DataPackage**: 146 МБ в [GitHub Release](https://github.com/Pradushkoai/1c-ai-dev-env/releases/tag/data-package)

---

## Требования

| Зависимость | Версия | Зачем |
|-------------|--------|-------|
| Python | 3.10+ | Скрипты, поиск, индексация, MCP-сервер |
| Java | 17+ | BSL Language Server (опционально, для `analyze_bsl`) |
| git | любая | Клонирование репозиториев стандартов 1С |
| unzip | любая | Распаковка ZIP и `.hbk` |

**Обязательные Python-зависимости** (`requirements.txt`):
```
python-dotenv>=1.0.0
```

**Опциональные** (`requirements-optional.txt`):
```
fastembed>=0.8.0    # RAG с нейросетевыми embeddings
qdrant-client>=1.0.0
mcp>=1.0.0          # MCP-сервер для IDE/LLM
```

**Для разработки** (`requirements-dev.txt`):
```
pytest>=7.0
mcp>=1.0.0
```

---

## Архитектура

4-слойная модель: `data/` → `derived/` → `tools/` → `runtime/`

```
data/       ← исходные (.cf, .hbk, конфигурации)
derived/    ← индексы (BM25, API-справочники, syntax-helper)
tools/      ← 15 git репозиториев стандартов 1С + BSL LS
runtime/    ← состояние (config-registry, session-resume, worklog)
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

### OOP-слой (src/)

```
src/
├── models/                 Конфигурация как данные
│   ├── configuration.py    Configuration dataclass
│   └── config_registry.py  ConfigurationRegistry
├── services/               Бизнес-логика
│   ├── path_manager.py     PathManager (вместо paths.py)
│   ├── config_manager.py   add/activate/archive/build
│   ├── bsl_analyzer.py     BSL LS wrapper + baseline/diff
│   ├── search.py           TF-IDF поиск (legacy, v1)
│   ├── search_bm25.py      BM25 + триграммы + стеммер (v2)
│   ├── data_package.py     Persistence (autosave/autoload)
│   └── github_releases.py  Push/pull через GitHub REST API
├── mcp_server.py           MCP-сервер (8 tools)
├── project.py              Project — оркестратор
├── cli.py                  Единый CLI
└── exceptions.py           Кастомные исключения
```

---

## Команды CLI

```bash
# Конфигурации
1c-ai config list                                # список
1c-ai config add --name X --zip Y                # добавить из ZIP
1c-ai config add --name X --cf Y                 # добавить из .cf
1c-ai config build --name X                      # индексы
1c-ai config build-all                           # все индексы

# Поиск (BM25 + триграммы)
1c-ai search "найти элемент по коду"             # авто-выбор алгоритма
python3 scripts/fast_search_1c.py build --algo bm25   # построить BM25
python3 scripts/fast_search_1c.py info           # версия индекса + BM25 параметры

# Анализ .bsl (требует Java + BSL LS)
1c-ai bsl analyze <path>                         # 187 диагностик
1c-ai bsl baseline <path>                        # сохранить baseline
1c-ai bsl diff <path>                            # только новые ошибки

# Проверка стандартов 1С (без Java)
1c-ai standards <path>                           # 56 правил
1c-ai standards <path> --format json             # JSON для CI
1c-ai standards <path> --severity error          # только errors

# Решение задач (автоматический цикл)
1c-ai solve context "создать справочник" --config ut11
1c-ai solve check scripts/module.bsl                    # quick (только стандарты)
1c-ai solve check scripts/module.bsl --level standard   # +BSL LS
1c-ai solve check scripts/module.bsl --level full       # +метаданные

# MCP-сервер (для IDE/LLM)
1c-ai mcp serve                                  # запустить (stdio)
1c-ai mcp tools                                  # список 8 tools

# Данные проекта (persistence между сессиями)
1c-ai data status                                # что доступно
1c-ai data autosave [--include-raw]              # сохранить в download/
1c-ai data autoload                              # восстановить
1c-ai data save-pkg -o backup.zip                # сохранить в ZIP
1c-ai data load-pkg backup.zip                   # восстановить из ZIP
1c-ai data info [backup.zip]                     # информация о пакете

# GitHub Releases (восстановление после пересоздания диска)
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-push                          # загрузить в Release
1c-ai data release-pull                          # скачать из Release
1c-ai data release-status                        # статус

# Backup/restore (старый интерфейс)
1c-ai backup create -o backup.zip
1c-ai backup restore backup.zip
1c-ai backup list

# Проверка окружения
1c-ai validate
```

Альтернативно: `python3 -m src.cli <command>`

---

## Подключение к IDE / LLM через MCP

Проект включает MCP-сервер (Model Context Protocol), который экспортирует **8 tools** для любой IDE/LLM с поддержкой MCP: Cursor, Claude Desktop, VS Code, JetBrains.

### Установка

```bash
pip install -e ".[mcp]"   # добавит mcp>=1.0.0
```

### Доступные tools (8)

| Tool | Что делает | Возвращает |
|------|-----------|------------|
| `list_configs` | Список загруженных конфигураций 1С | `[{name, version, status, objects_count, api_methods_count}]` |
| `search_1c_methods` | BM25 поиск по 8141 методам платформы | `[{score, name_ru, name_en, syntax, description, context}]` |
| `get_api_reference` | API-справочник общих модулей | список модулей или методы модуля |
| `analyze_bsl` | Анализ `.bsl` через BSL LS (187 диагностик) | `{total, by_code, diagnostics}` |
| `check_standards` | Проверка на 56 правил (без Java) | `[{rule_id, severity, line, message}]` |
| `solve_context` | Сбор контекста для задачи | `{platform_methods, config_info, standards_summary}` |
| `solve_check` | Полная проверка `.bsl` кода | `{total_errors, total_warnings, verdict, details}` |
| `data_status` | Статус данных проекта | `{has_platform_index, configs[], autosave_available}` |

### Конфиг для Cursor / VS Code

Добавьте в `~/.cursor/mcp.json` (или `~/.vscode/mcp.json`):

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

### Конфиг для Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) или `~/.config/Claude/claude_desktop_config.json` (Linux):

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

### Принципы

- **MCP-сервер — read-only**: только читает готовые индексы
- **CLI = admin**: загрузка/индексация через `1c-ai config add/build`
- **MCP = аналитика**: поиск, проверка, сбор контекста
- **Любой MCP-клиент**: не привязан к конкретной IDE

📖 **Полная документация**: [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) — инструкции для Cursor, Claude Desktop, VS Code (Continue/Cline), JetBrains, примеры использования, устранение неисправностей.

---

## Тесты

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

**314 тестов** покрывают:
- PathManager, ConfigManager, Configuration model
- BSLAnalyzer (с реальным BSL LS, мок subprocess)
- Search: TF-IDF (legacy) + BM25 + триграммы + стеммер
- cf_extractor (32 + 64 бита), v8_metadata_parser V2
- backup_manager, data_package, github_releases
- check_1c_standards (56 правил), check_metadata_standards (18 правил)
- API-методы Project (list_configs_info, get_config_info, get_api_methods)
- MCP-сервер (8 tools, E2E через stdio)
- 3 интеграционных теста с реальным BSL LS (`@requires_bsl_ls`)

---

## Persistence данных

Проблема: в облачных средах диск может пересоздаваться между сессиями — данные (`data/`, `derived/`) теряются.

**Решение:** DataPackage + GitHub Releases

```bash
# Сохранить всё в один ZIP
1c-ai data autosave --include-raw
# → download/1c-ai-data-package.zip (146 МБ)
# → включает: 4 configs + BM25 индекс + config-registry

# Загрузить в GitHub Release
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
1c-ai data release-push
# → https://github.com/USER/REPO/releases/tag/data-package

# В новой сессии — восстановить
1c-ai data release-pull   # скачать 146 МБ
1c-ai data autoload       # восстановить 4 configs + BM25
```

**Структура пакета:**
```
data-package/
├── manifest.json                  метаданные (версия, дата, конфиги)
├── runtime/
│   └── config-registry.json       реестр конфигураций
├── derived/
│   ├── configs/<name>/            индексы (api-reference.json, index.md)
│   └── platform/                  BM25 индекс + syntax-helper
└── data/                          (опционально, --include-raw)
    └── configs/<name>/            распакованные конфигурации
```

---

## Инструменты и стандарты 1С

| Инструмент | Что даёт |
|------------|----------|
| [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) v1.0.1 | 187 диагностик `.bsl` кода |
| [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) | 94 скила: JSON DSL для метаданных |
| [EDT-MCP](https://github.com/DitriXNew/EDT-MCP) | 168 проверок качества кода |
| [ai_rules_1c](https://github.com/comol/ai_rules_1c) | 28 правил разработки + 13 ролей |
| [1c-standards-claude-skill](https://github.com/Pradushkoai/1c-standards-claude-skill) | Стандарты ИТС (разделы 01, 03, 04, 12) |
| **cf_extractor** (собственный) | Распаковка `.cf`/`.cfe`/`.epf` (Container32 + Container64) |
| **v8_metadata_parser V2** (собственный) | Парсинг метаданных 1С 8.3.24+ |
| **BM25 search** (собственный) | Семантический поиск (k1=1.5, b=0.75, триграммы, стеммер) |
| **hbk_extractor** (собственный) | Распаковка `.hbk` синтакс-помощника |

---

## Roadmap

- ✅ **v3.7.0**: MCP-сервер (8 tools) + IDE интеграция
- ✅ **v3.8.0**: BM25 + триграммы + стеммер (улучшенный поиск)
- ✅ **v3.9.0**: DataPackage (persistence между сессиями)
- ✅ **v3.10.0**: GitHub Releases (push/pull data-пакета)
- ✅ **v3.11.0**: v8_metadata_parser V2 (полное извлечение объектов)
- ✅ **v3.12.0**: Все 4 конфигурации полностью извлечены (115 666 методов)
- ✅ **v3.13.0**: Протокол 5 ролей для решения задач 1С
- ✅ **v3.14.0**: Замена 5 ролей на чек-лист
- ✅ **v3.14.1**: Упрощение — 2 функции репозитория, убран чек-лист
- ✅ **v3.15.0**: search_code (115K методов), BSL-синонимы ru↔en, --ci/--json режимы
- 🔲 **v3.16.0** (план): Векторный поиск через fastembed + qdrant

---

## 2 функции репозитория

1. **MCP-сервер** для сторонних клиентов (Cursor, Claude Desktop, VS Code, JetBrains) —
   9 tools: `list_configs`, `search_1c_methods`, `search_code`, `get_api_reference`, `analyze_bsl`,
   `check_standards`, `solve_context`, `solve_check`, `data_status`.
   📖 [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md)

2. **Источник информации по 1С** для ассистента —
   BM25 поиск по 8141 методам платформы, API-справочники 4 конфигураций
   (115 666 методов), 56 правил стандартов 1С, BSL Language Server (187 диагностик).

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Содействие

См. [CONTRIBUTING.md](CONTRIBUTING.md)

## Changelog

См. [CHANGELOG.md](CHANGELOG.md)
