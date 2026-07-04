# Contributing to 1C AI Development Environment

Спасибо за интерес к проекту! Любой вклад приветствуется.

**Быстрый старт:** см. [docs/QUICK_START.md](docs/QUICK_START.md) (5 минут до первого запуска).
**Roadmap:** см. [ROADMAP.md](ROADMAP.md).
**Архитектурные решения:** см. [adr/](adr/) (Architecture Decision Records).

## Как внести вклад

### Сообщение об ошибке
1. Проверь существующие issues — возможно уже есть
2. Создай новый issue с шаблоном (описание, шаги, ожидание, реальность)

### Предложение улучшения
1. Создай issue с меткой `enhancement`
2. Опиши что улучшить и зачем

### Pull Request
1. Fork репозитория
2. Создай ветку: `git checkout -b feature/my-feature`
3. **Запусти тесты локально** (см. ниже) — все должны проходить
4. Если добавляешь новый функционал — добавь тесты
5. Если изменяешь MCP tools — обнови snapshot: `pytest tests/test_mcp_tools_snapshot.py --snapshot-update`
6. Если нетривиальное архитектурное решение — создай ADR в `adr/`
7. Коммить с понятными сообщениями
6. Создай PR с описанием изменений

## Разработка

### Установка окружения

```bash
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# Установка пакета (editable mode + dev + mcp зависимости)
pip install -e ".[dev,mcp]"

# Или полная установка через install.sh (клонирует git-репозитории, BSL LS, и т.д.)
bash install.sh --non-interactive
```

### Запуск тестов

```bash
# Все тесты
python3 -m pytest tests/ -v

# Конкретный модуль
python3 -m pytest tests/test_search_bm25.py -v

# С покрытием (если установлен pytest-cov)
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

Тесты **не требуют** Java/BSL LS/внешних скриптов — все внешние вызовы замокированы через `unittest.mock.patch`. Полный прогон ~25 секунд.

После `pip install -e .` пакет `src` доступен для импорта без sys.path хаков.

### Что покрывают тесты (314 тестов)

| Файл | Что тестирует | Кол-во |
|------|--------------|--------|
| `test_path_manager.py` | Поиск paths.env, 4 слоя архитектуры, env-подстановка | 6 |
| `test_config_manager.py` | add_from_zip/cf, build, archive/activate | 8 |
| `test_bsl_analyzer.py` | Парсинг BSL LS JSON, baseline persistence | 6 |
| `test_search_bm25.py` | BM25 + триграммы + стеммер + auto-detect | 39 |
| `test_fast_search.py` | TF-IDF (legacy): tokenize, build_index, search | 7 |
| `test_configuration.py` | Configuration model: from_dict, to_dict, is_active | 5 |
| `test_cf_extractor.py` | cf_extractor (Container32 + Container64) | ~10 |
| `test_v8_metadata_parser.py` | V2 type map, парсинг обоих паттернов имён | 17 |
| `test_data_package.py` | DataPackage save/load/autosave/autoload | 27 |
| `test_github_releases.py` | GitHub Releases push/pull (mock subprocess) | 24 |
| `test_check_standards.py` | 56 правил check_1c_standards | ~15 |
| `test_metadata_standards.py` | 18 правил check_metadata_standards | ~10 |
| `test_project_api.py` | API-методы Project (list_configs_info, etc.) | 12 |
| `test_mcp_server.py` | MCP-сервер (8 tools, call_tool handler) | 16 |
| `test_solve.py` | solve context/check | ~5 |
| `test_backup_manager.py` | backup/restore | ~5 |
| `test_integration.py` | Полный flow с реальным BSL LS | 3 |

### Добавление новых тестов

1. Создай `tests/test_<module>.py`
2. Используй `tmp_path` fixture для временных файлов — не пиши в `/tmp` напрямую
3. Мокай внешние вызовы через `unittest.mock.patch`:
   ```python
   from unittest.mock import patch, MagicMock
   with patch("src.services.config_manager.subprocess.run") as mock_run:
       mock_run.return_value = MagicMock(returncode=0)
       # твой код
   ```
4. Импортируй через `from src.<module> import <name>` (после `pip install -e .`)

## Стандарты кода

### Версионирование (SemVer)

Проект следует [Semantic Versioning](https://semver.org/):

- **MAJOR** (4.0.0) — breaking changes (удаление API, несовместимые изменения)
- **MINOR** (3.x.0) — новые функции (backward compatible)
- **PATCH** (3.x.y) — исправления багов (backward compatible)

Правила:
- Новые MCP tools → MINOR
- Новые правила проверок → MINOR
- Новые сервисы (data_package, github_releases) → MINOR
- Исправления багов → PATCH
- Breaking changes → MAJOR — **редко**

### Python скрипты
- Python 3.10+
- **Используй `PathManager`** из `src.services.path_manager` (paths.py удалён в P2.15)
- Типы — через type hints (`from __future__ import annotations` для | None синтаксиса)
- Для CLI — argparse, единая точка входа `python3 -m src.cli`
- Для нового кода — `logging` вместо `print` для диагностических сообщений
- Кастомные исключения из `src.exceptions` (ConfigNotFoundError, BuildError, etc.)

### Где жить новому коду (Этап 1.3)

Подробное решение-дерево — в [`AGENTS.md`](AGENTS.md#где-жить-новому-коду-этап-13).

Кратко:
- **`src/services/`** — бизнес-логика, тестируется, импортируется через `from src.services.*`
- **`scripts/`** — thin CLI wrappers (argparse + `from src.services.* import`) или CI utilities
- **`src/models/`** — модели данных (dataclass, Protocol)
- **`src/dsl/`** — DSL-компиляторы (JSON → XML)
- **`src/mcpserver/handlers/`** — MCP handlers (async)
- **`src/cli_commands/`** — CLI commands (sync)
- **`experimental/`** — замороженные SaaS/Enterprise/Plugin (ADR-0006)

**Iron rules:**
- ❌ НЕ используй `importlib.util.spec_from_file_location` для загрузки скриптов
- ❌ НЕ используй `sys.path.insert(0, scripts_dir)` для импорта из scripts/
- ❌ НЕ размещай бизнес-логику в `scripts/` — только thin CLI wrappers
- ❌ НЕ импортируй из `scripts/` в `src/`

### Язык проекта (ADR-0008)

Проект **русскоязычный**. См. [ADR-0008](adr/0008-language-policy-russian.md).

- **Комментарии и docstrings** в `src/` — только русский.
- **BSL-шаблоны** (`templates/`) — только русский (выводятся пользователю).
- **Сообщения об ошибках** (`raise ValueError("...")`) — русский.
- **Имена переменных, функций, классов** — английский (Python convention).
- **Импорты, технические термины** (API, JSON, XML) — английский.
- **README.md** — основной (русский), README.en.md — волонтёрский перевод.
- **Commit messages** — русский с английскими префиксами (`feat:`, `fix:`, etc.).

 НЕ переводи существующие комментарии на английский — это нарушение ADR-0008.

### Shell скрипты
- `#!/bin/bash` + `set -e`
- Используй `source paths.env` для путей в shell

### Markdown
- Русский язык (основной)
- Таблицы для структурированных данных
- Emoji для навигации (✅ ❌ ⚠️ 🔲)

## Структура проекта

```
1c-ai-dev-env/
├── src/                      OOP-пакет
│   ├── models/               Configuration, ConfigurationRegistry
│   ├── services/             PathManager, ConfigManager, BSLAnalyzer,
│   │                         search, search_bm25, data_package,
│   │                         github_releases
│   ├── mcp_server.py         MCP-сервер (8 tools)
│   ├── project.py            Project — оркестратор
│   ├── cli.py                Единый CLI
│   └── exceptions.py         Кастомные исключения
├── scripts/                  Standalone-скрипты
│   ├── cf_extractor.py       Парсер .cf (Container32/64)
│   ├── v8_metadata_parser.py V2 type map
│   ├── cf_to_xml_adapter.py  Конвертер в XML формат
│   ├── hbk_extractor.py      Распаковка .hbk
│   ├── build_api_reference.py API-справочник
│   ├── build_config_index_generic.py  Индекс метаданных
│   ├── fast_search_1c.py     CLI для поиска (BM25/TF-IDF)
│   ├── check_1c_standards.py 56 правил
│   ├── check_metadata_standards.py  18 правил XML
│   └── test_mcp_e2e.py       E2E тест MCP-сервера
├── tests/                    pytest-тесты
├── docs/                     Документация
│   ├── ARCHITECTURE.md       4-слойная архитектура
│   └── MCP_INTEGRATION.md    Подключение к IDE
├── .github/workflows/        CI
├── install.sh                Установщик (BSL LS + git-репозитории)
├── pyproject.toml            Упаковка + 1c-ai CLI entry point + все зависимости
│                             (P1.3: requirements*.txt удалены, pyproject-only модель)
├── paths.env                 Конфиг путей (shell)
└── manifest.json             Реестр компонентов
```

После `pip install -e .` пакет `src/` доступен для импорта через `from src.services...`, а команды `1c-ai` и `1c-ai-mcp` доступны глобально.

## CI

GitHub Actions (`.github/workflows/ci.yml`) запускается на каждый push/PR:
1. Установка зависимостей (`pip install -e ".[dev]"` — все в pyproject.toml)
2. Проверка синтаксиса всех Python файлов (`py_compile`)
3. Запуск `pytest tests/`

PR не может быть смёрджен, если CI красный.

## Workflow разработки с persistence

Если работаешь над функционалом, требующим данных (4 конфигурации + BM25 индекс):

```bash
# 1. Восстановить данные из GitHub Release
1c-ai data release-pull
1c-ai data autoload

# 2. Разработка...
# (изменения в коде)

# 3. Перед завершением — сохранить обновлённые данные
1c-ai data autosave --include-raw
1c-ai data release-push

# 4. Commit + push кода
git add -A && git commit -m "feat: ..." && git push
```
