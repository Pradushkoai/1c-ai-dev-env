# 1C AI Development Environment

> Среда для разработки на 1С с ИИ-ассистентом: синтакс-помощник, API-справочники, анализ кода, генерация объектов через JSON DSL.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# 2. Установить (интерактивно — спросит про .hbk и ZIP конфигурации)
bash install.sh
# Или только Python-пакет (без git-репозиториев и BSL LS):
# pip install -e ".[dev]"

# 3. Проверить
1c-ai validate
1c-ai config list

# 4. Работать
1c-ai search "найти элемент по коду"
1c-ai bsl analyze data/configs/<name>/path/to/file.bsl
```

### Добавить конфигурацию

```bash
1c-ai config add --name ut11 --zip /path/to/ut11.zip --title "УТ 11"
# → Распакует в data/configs/ut11/
# → Построит derived/configs/ut11/index.md (индекс метаданных)
# → Построит derived/configs/ut11/api-reference.md (API-справочник)
```

### Программно (Python)

```python
from src.project import Project

project = Project()
project.config_manager.add_from_zip("erp", Path("erp.zip"), "1С:ERP")
project.config_manager.build("erp")
result = project.bsl_analyzer.analyze(Path("file.bsl"))
```

---

## Требования

| Зависимость | Версия | Зачем |
|-------------|--------|-------|
| Python | 3.10+ | Скрипты, поиск, индексация |
| Java | 17+ | BSL Language Server |
| git | любая | Клонирование репозиториев |
| unzip | любая | Распаковка ZIP и `.hbk` |

**Обязательные Python-зависимости** (`requirements.txt`):
```
v8unpack>=1.2.6
python-dotenv>=1.0.0
```

**Опциональные** (для RAG с нейросетевыми embeddings и MCP-сервера — `requirements-optional.txt`):
```
fastembed>=0.8.0
qdrant-client>=1.0.0
mcp>=1.0.0
```

**Для разработки** (`requirements-dev.txt`):
```
pytest>=7.0
```

---

## Тесты

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

220 тестов покрывают: PathManager, ConfigManager, BSLAnalyzer (с реальным BSL LS), search (TF-IDF), Configuration model, cf_extractor (32+64 бита), v8_metadata_parser, backup_manager, check_1c_standards (56 правил), check_metadata_standards (18 правил), новые API-методы Project, MCP-сервер (7 tools). 3 интеграционных теста с реальным BSL LS (`@requires_bsl_ls`) — пропускаются если BSL LS не установлен.

---

## Архитектура

4-слойная модель: `data/` → `derived/` → `tools/` → `runtime/`

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Команды

```bash
# Конфигурации
1c-ai config list                              # список
1c-ai config add --name X --zip Y              # добавить из ZIP
1c-ai config build --name X                    # индексы
1c-ai config build-all                         # все индексы

# Поиск
1c-ai search "найти элемент по коду"           # TF-IDF поиск

# Анализ .bsl
1c-ai bsl analyze <path>                       # полный анализ (BSL LS)
1c-ai bsl baseline <path>                      # сохранить baseline
1c-ai bsl diff <path>                          # только новые ошибки

# Проверка стандартов 1С
1c-ai standards <path>                         # 42 правила (стилистика, антипаттерны)
1c-ai standards <path> --format json           # JSON вывод для CI
1c-ai standards <path> --severity error        # только errors

# Проверка метаданных конфигурации
python3 scripts/check_metadata_standards.py data/configs/ut11  # 18 правил XML

# Решение задач (автоматический цикл)
1c-ai solve context "создать справочник" --config ut11  # собрать контекст для LLM
1c-ai solve check scripts/module.bsl                    # проверить код (quick)
1c-ai solve check scripts/module.bsl --level full       # все 3 уровня проверок

# MCP-сервер (для IDE/LLM)
1c-ai mcp serve                                       # запустить MCP-сервер (stdio)
1c-ai mcp tools                                       # список доступных tools

# Backup/restore
1c-ai backup create -o backup.zip              # создать backup (data/ + runtime/)
1c-ai backup restore backup.zip                # восстановить из backup
1c-ai backup list                              # список backup'ов

# Проверка окружения
1c-ai validate                                 # проверить пути
```

Альтернативно можно использовать `python3 -m src.cli <command>`.

---

## Подключение к IDE / LLM через MCP

Проект включает MCP-сервер (Model Context Protocol), который экспортирует 7 tools для любой IDE/LLM с поддержкой MCP: Cursor, Claude Desktop, VS Code, Continue и т.д.

### Установка

```bash
pip install -r requirements-optional.txt   # добавит mcp>=1.0.0
```

### Доступные tools (7)

| Tool | Что делает |
|------|-----------|
| `list_configs` | Список загруженных конфигураций 1С |
| `search_1c_methods` | TF-IDF поиск по 8141 методам платформы |
| `get_api_reference` | API-справочник общих модулей конфигурации |
| `analyze_bsl` | Анализ .bsl через BSL LS (187 диагностик) |
| `check_standards` | Проверка на 56 правил стандартов 1С |
| `solve_context` | Сбор контекста для решения задачи |
| `solve_check` | Полная проверка .bsl кода |

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

Добавьте в `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) или `~/.config/Claude/claude_desktop_config.json` (Linux):

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

- **MCP-сервер — read-only**: только читает готовые индексы, не загружает данные
- **CLI = admin**: загрузка, индексация, backup делаются через `1c-ai config add/build`
- **MCP = аналитика**: поиск, проверка, сбор контекста
- **Любой MCP-клиент**: не привязан к конкретной IDE

📖 **Полная документация по подключению к IDE**: [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) — инструкции для Cursor, Claude Desktop, VS Code (Continue/Cline), JetBrains, примеры использования, устранение неисправностей.

---

## Инструменты

| Инструмент | Что даёт |
|------------|----------|
| [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) v1.0.1 | Анализ `.bsl` кода (187 диагностик, `--diff` режим) |
| [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) | 94 скила: JSON DSL для метаданных, форм, расширений |
| [EDT-MCP](https://github.com/DitriXNew/EDT-MCP) | 168 проверок качества кода |
| [ai_rules_1c](https://github.com/comol/ai_rules_1c) | 28 правил разработки + 13 ролей |
| v8unpack | Распаковка `.cf`/`.cfe` без платформы 1С |
| TF-IDF Search | Семантический поиск по методам 1С (2 сек, без GPU) |
| hbk_extractor | Распаковка `.hbk` синтакс-помощника 1С |

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Содействие

См. [CONTRIBUTING.md](CONTRIBUTING.md)
