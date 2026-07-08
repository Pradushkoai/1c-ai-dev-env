# Подключение 1C AI Development Environment к IDE / LLM через MCP

[MCP (Model Context Protocol)](https://modelcontextprotocol.io) — открытый протокол Anthropic, который позволяет IDE/LLM получать доступ к внешним источникам данных и инструментов. 1C AI Development Environment поставляет MCP-сервер, который экспортирует 54 tools для работы с конфигурациями 1С, методами платформы, стандартами разработки и анализом `.bsl` кода.

Поддерживается любой MCP-совместимый клиент: **Cursor**, **Claude Desktop**, **VS Code** (с расширением), **Continue**, **Cline** и др.

---

## Содержание

1. [Установка](#установка)
2. [Доступные tools (27)]#доступные-tools-7)
3. [Подключение к Cursor](#подключение-к-cursor)
4. [Подключение к Claude Desktop](#подключение-к-claude-desktop)
5. [Подключение к VS Code (Continue / Cline)](#подключение-к-vs-code-continue--cline)
6. [Подключение к JetBrains IDE](#подключение-к-jetbrains-ide)
7. [Проверка работы](#проверка-работы)
8. [Примеры использования](#примеры-использования)
9. [Устранение неисправностей](#устранение-неисправностей)

---

## Установка

### 1. Установите пакет с MCP-зависимостями

```bash
cd /path/to/1c-ai-dev-env
pip install -e ".[mcp]"
# или явно:
pip install -e ".[mcp]"
```

### 2. Проверьте установку

```bash
1c-ai mcp tools
```

Должны увидеть список из 54 tools. Если команда не найдена — используйте `python3 -m src.cli mcp tools`.

### 3. Подготовьте данные

MCP-сервер **read-only**: он читает уже готовые индексы. Чтобы данные были доступны:

```bash
# 1. Платформа 1С — методы (TF-IDF индекс)
python3 scripts/fast_search_1c.py build

# 2. Конфигурация 1С — API-справочник
1c-ai config add --name ut11 --zip /path/to/ut11.zip --title "УТ 11"
1c-ai config build --name ut11

# 3. Проверка
1c-ai config list
1c-ai search "найти элемент по коду"
```

---

## Доступные tools (38)

| Tool | Что делает | Возвращает |
|------|-----------|------------|
| `list_configs` | Список загруженных конфигураций 1С | `[{name, version, status, objects_count, api_methods_count, has_api}]` |
| `search_1c_methods` | TF-IDF поиск по 8141 методам платформы | `[{score, name_ru, name_en, syntax, description, context}]` |
| `get_api_reference` | API-справочник общих модулей конфигурации | список модулей или методы конкретного модуля |
| `analyze_bsl` | Анализ `.bsl` файла через BSL LS (187 диагностик) | `{total, by_code, diagnostics}` |
| `check_standards` | Проверка на 56 правил стандартов 1С (без Java) | `[{rule_id, severity, line, message}]` |
| `solve_context` | Сбор контекста для решения задачи | `{platform_methods, config_info, standards_summary}` |
| `solve_check` | Полная проверка `.bsl`: BSL LS + 56 правил | `{total_errors, total_warnings, verdict, details}` |
| `epf_factory_create` | **Создать .epf из BSL-кода без 1С** (шаблоны + BSL LS + round-trip) | `{ok, epf_path, size_bytes, proc_uuid, form_uuid, bsl_lines, round_trip_ok}` |
| `epf_factory_templates` | Список шаблонов для `epf_factory_create` | `{ext_proc, form, form_id, form_elem_empty, templates_dir}` |

### Параметры tools

| Tool | Обязательные | Опциональные |
|------|-------------|--------------|
| `list_configs` | — | — |
| `search_1c_methods` | `query` | `limit` (по умолчанию 10) |
| `get_api_reference` | `config_name` | `module` (если пусто — список модулей) |
| `analyze_bsl` | `file_path` | — |
| `check_standards` | `file_path` | — |
| `solve_context` | `query` | `config` |
| `solve_check` | `file_path` | — |
| `epf_factory_create` | `name`, `output_path` | `synonym`, `bsl_code`, `bsl_path`, `form_name`, `skip_bsl_validation`, `save_sources` |
| `epf_factory_templates` | — | — |

### Создание внешних обработок (.epf) через MCP

Инструмент `epf_factory_create` позволяет создавать внешние обработки 1С без установленной платформы 1С. Полный цикл: шаблоны v8unpack → подстановка UUID → BSL-код → проверка через BSL LS → сборка → round-trip.

**Пример вызова из Cursor / Claude Desktop:**

```
Помоги создать внешнюю обработку для выгрузки номенклатуры в Excel.
Используй epf_factory_create с параметрами:
- name: "ВыгрузкаНоменклатурыВExcel"
- synonym: "Выгрузка номенклатуры в Excel"
- output_path: "/tmp/ВыгрузкаНоменклатурыВExcel.epf"
BSL-код модуля формы напиши сам, следуя стандартам 1С.
```

Подробная инструкция: [docs/EPF_FACTORY.md](EPF_FACTORY.md)

---

## Подключение к Cursor

### Вариант 1: Глобально (для всех проектов)

Создайте/отредактируйте файл `~/.cursor/mcp.json`:

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

### Вариант 2: На конкретный проект

Создайте `.cursor/mcp.json` в корне вашего проекта разработки 1С:

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "python3",
      "args": ["-m", "src.cli", "mcp", "serve"],
      "cwd": "/home/user/1c-ai-dev-env"
    }
  }
}
```

После сохранения файла перезапустите Cursor. В панели чата появится иконка молотка (Tools) — нажмите её и убедитесь, что 54 tools от `1c-ai-dev-env` активны.

### Использование в Cursor

Просто спросите в чате:

> «Найди методы платформы 1С для поиска элемента справочника по коду»

Cursor автоматически вызовет `search_1c_methods` с вашим запросом и вернёт топ-10 результатов.

> «Проверь мой файл module.bsl на стандарты 1С»

Cursor вызовет `check_standards` и `analyze_bsl`, покажет violations.

---

## Подключение к Claude Desktop

### macOS

Отредактируйте `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "python3",
      "args": ["-m", "src.cli", "mcp", "serve"],
      "cwd": "/Users/username/1c-ai-dev-env"
    }
  }
}
```

### Linux

Отредактируйте `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "python3",
      "args": ["-m", "src.cli", "mcp", "serve"],
      "cwd": "/home/username/1c-ai-dev-env"
    }
  }
}
```

### Windows (WSL)

Claude Desktop на Windows поддерживает MCP через WSL:

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "wsl.exe",
      "args": ["python3", "-m", "src.cli", "mcp", "serve"],
      "cwd": "/home/username/1c-ai-dev-env"
    }
  }
}
```

После сохранения полностью закройте Claude Desktop (не сверните) и запустите снова. В окне чата появится иконка молотка — нажмите её, чтобы увидеть доступные tools.

---

## Подключение к VS Code (Continue / Cline)

### Continue

В файле `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "python3",
          "args": ["-m", "src.cli", "mcp", "serve"],
          "cwd": "/path/to/1c-ai-dev-env"
        }
      }
    ]
  }
}
```

### Cline

В файле настроек Cline (`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` на Windows или `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` на Linux/macOS):

```json
{
  "mcpServers": {
    "1c-ai-dev-env": {
      "command": "python3",
      "args": ["-m", "src.cli", "mcp", "serve"],
      "cwd": "/path/to/1c-ai-dev-env",
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

---

## Подключение к JetBrains IDE

Плагин **AI Assistant** в IntelliJ IDEA / PhpStorm / PyCharm поддерживает MCP с 2024.3.

1. Settings → Tools → AI Assistant → MCP Servers
2. Add new server:
   - **Name**: `1c-ai-dev-env`
   - **Command**: `python3 -m src.cli mcp serve`
   - **Working directory**: `/path/to/1c-ai-dev-env`
3. Apply → OK
4. В AI Assistant чате появится список доступных tools

---

## Проверка работы

### 1. Проверьте, что сервер запускается

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 -m src.cli mcp serve
```

Должен вернуться JSON с `serverInfo.name = "1c-ai-dev-env"`.

### 2. Запустите E2E тест

```bash
python3 scripts/test_mcp_e2e.py
```

Вывод:
```
✅ initialize OK
✅ tools/list OK (54 tools)
✅ tools/call list_configs OK
```

### 3. В IDE вызовите любой tool

Например, попросите LLM: «Покажи список загруженных конфигураций 1С» — он должен вызвать `list_configs`.

---

## Примеры использования

### Сценарий 1: «Я хочу создать справочник Товары»

```
Пользователь: Помоги создать справочник Товары в 1С

LLM (через MCP):
1. solve_context(query="создать справочник Товары", config="ut11")
   → получает топ-5 методов платформы + API модулей УТ11 + сводку стандартов

2. Генерирует .bsl код модуля, опираясь на контекст

3. solve_check(file_path="/tmp/Товары/МодульМенеджера.bsl")
   → проверяет код через BSL LS + 56 правил
   → verdict: "ready" или "warnings" с детализацией
```

### Сценарий 2: «Найди метод для выполнения запроса к БД»

```
Пользователь: Какой метод платформы 1С выполняет запрос?

LLM:
1. search_1c_methods(query="выполнить запрос к базе", limit=5)
   → Найти() / Запрос.Выполнить() / ВыполнитьЗапрос() в топе

2. Показывает syntax + description для каждого
```

### Сценарий 3: «Проверь мой модуль перед коммитом»

```
Пользователь: Проверь Module.bsl перед PR

LLM:
1. check_standards(file_path="/path/Module.bsl")
   → 56 правил за <1 сек (без Java)

2. analyze_bsl(file_path="/path/Module.bsl")
   → 187 диагностик BSL LS (если установлен)

3. solve_check(file_path="/path/Module.bsl")
   → сводный отчёт: total_errors, total_warnings, verdict
```

### Сценарий 4: «Что в API модуля ОбщегоНазначения УТ11?»

```
Пользователь: Покажи экспортные методы ОбщегоНазначения в УТ11

LLM:
1. get_api_reference(config_name="ut11", module="ОбщегоНазначения")
   → [{module, name, type, params, description, returns, signature}, ...]
```

---

## Устранение неисправностей

### «MCP SDK не установлен»

```bash
pip install mcp>=1.0.0
```

Или через extras:

```bash
pip install -e ".[mcp]"
```

### IDE не видит tools

1. Проверьте путь в `cwd` — он должен указывать на корень репозитория с `src/cli.py`
2. Проверьте, что `python3` доступен в PATH (или укажите полный путь к интерпретатору)
3. Проверьте, что в `cwd` есть файл `pyproject.toml` или `src/__init__.py`
4. Полностью перезапустите IDE (не просто перезагрузите окно)

### Tools вызываются, но возвращают пустые результаты

Это значит, что данные не загружены. MCP — read-only:

```bash
# Платформа — методы
python3 scripts/fast_search_1c.py build

# Конфигурация — API
1c-ai config add --name ut11 --zip /path/to/ut11.zip --title "УТ 11"
1c-ai config build --name ut11

# Проверка
1c-ai config list
1c-ai search "тест"
```

### BSL LS не работает в `analyze_bsl` / `solve_check`

`analyze_bsl` и `solve_check` требуют установленного BSL LS:

```bash
bash install.sh   # скачает bsl-language-server.jar
1c-ai validate    # проверить окружение
```

Без BSL LS эти tools вернут `error: "BSL LS не установлен"`, но `check_standards` (56 правил) продолжит работать.

### Сервер падает с ошибкой asyncio

Если видите `RuntimeError: Event loop is already running` — это конфликт с Jupyter или другим async-кодом в окружении. Используйте отдельный процесс Python для MCP-сервера (это уже сделано через subprocess в IDE).

### Замедленная работа

Если поиск занимает больше секунды:

1. Проверьте, что индекс собран: `ls derived/platform/fast-search-index.json` (размер должен быть > 1 МБ)
2. Пересоберите индекс: `python3 scripts/fast_search_1c.py build`
3. Проверьте, что MCP-сервер не запускается в режиме отладки (stderr должен быть пустой)

### Логи MCP-сервера

MCP-сервер пишет stderr. Чтобы посмотреть:

```bash
# В отдельном терминале
python3 -m src.cli mcp serve 2>mcp.log
# В другом терминале — отправить запрос
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 -m src.cli mcp serve
# Посмотреть логи
cat mcp.log
```

---

## Принципы MCP в этом проекте

- **Read-only**: MCP-сервер только читает готовые индексы. Загрузка/индексация делаются через CLI (`1c-ai config add/build`).
- **CLI = admin**: управление данными (добавление, удаление, индексация, backup).
- **MCP = аналитика**: поиск, проверка, сбор контекста.
- **Любой MCP-клиент**: не привязан к конкретной IDE.
- **Изоляция сессий**: каждый запуск MCP-сервера создаёт новый `Project()` — нет state между вызовами.

---

## Ссылки

- [MCP спецификация](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Cursor MCP документация](https://docs.cursor.com/advanced/mcp)
- [Claude Desktop MCP](https://modelcontextprotocol.io/quickstart/user)
- [BSL Language Server](https://github.com/1c-syntax/bsl-language-server)

---

## Changelog

- **v3.7.0** (2026-06-28): первичная реализация MCP-сервера с 27 tools
