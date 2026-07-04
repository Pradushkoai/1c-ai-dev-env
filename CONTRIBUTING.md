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

---

## How-to гайды (Этап 4.3)

### How-to: Добавить новый BSL-анализатор

BSL-анализатор — это функция, проверяющая .bsl файл на соответствие
стандартам 1С. Все анализаторы живут в `src/services/analyzers/`.

**Шаг 1: Выбери категорию**

| Категория | Файл | Примеры правил |
|-----------|------|----------------|
| Стиль кода | `standards/style.py` | no_yo, no_dashes, no_commented_code |
| Архитектура | `standards/architecture.py` | no_vypolnit, no_hardcoded_credentials |
| Запросы | `standards/queries.py` | no_pereyti, no_full_outer_join |
| Клиент-сервер | `standards/client_server.py` | no_transaction_in_nacliente |
| Разное | `standards/misc.py` | no_otkaz_lozh, no_deep_nesting |

Если правило не подходит ни к одной категории — добавь в `misc.py`.

**Шаг 2: Напиши правило**

```python
# src/services/analyzers/standards/style.py

def rule_no_my_antipattern(lines: list[str], file_path: Path) -> Iterator[Violation]:
    """Правило STD XXX: описание антипаттерна.

    Проверяет, что в коде нет 'МойАнтипаттерн'.
    """
    for i, line in enumerate(lines, start=1):
        if "МойАнтипаттерн" in line:
            col = line.index("МойАнтипаттерн") + 1
            yield Violation(
                file=str(file_path),
                line=i,
                col=col,
                rule_id="no-my-antipattern",
                severity="warning",
                message="МойАнтипаттерн запрещён — используйте ДругойПодход (STD XXX)",
            )
```

**Шаг 3: Зарегистрируй правило**

Добавь функцию в `RULES` list в конце файла:

```python
# src/services/analyzers/standards/style.py (конец файла)
RULES = [
    rule_no_non_breaking_spaces,
    # ... существующие правила ...
    rule_no_my_antipattern,  # ← добавь сюда
]
```

**Шаг 4: Напиши тест**

```python
# tests/test_check_standards.py

class TestNoMyAntipattern:
    def test_detects_antipattern(self, std):
        bsl = "Процедура Тест()\n    МойАнтипаттерн()\nКонецПроцедуры\n"
        violations = _check_rule(std, std.rule_no_my_antipattern, bsl)
        assert len(violations) == 1
        assert violations[0].rule_id == "no-my-antipattern"

    def test_no_antipattern_ok(self, std):
        bsl = "Процедура Тест()\n    ДругойПодход()\nКонецПроцедуры\n"
        violations = _check_rule(std, std.rule_no_my_antipattern, bsl)
        assert len(violations) == 0
```

**Шаг 5: Проверь**

```bash
python3 -m pytest tests/test_check_standards.py::TestNoMyAntipattern -v
python3 -m pytest tests/test_check_standards.py -q  # все тесты правил
```

### How-to: Добавить новый MCP tool

MCP tool — это функция, вызываемая IDE (Cursor, Claude Desktop) через
MCP-протокол. Все tools регистрируются в `src/mcpserver/tools/tool_definitions.py`.

**Шаг 1: Определи категорию**

| Категория | Handler файл | Примеры tools |
|-----------|--------------|---------------|
| Конфигурации | `handlers/config_search.py` | list_configs, data_status |
| Поиск | `handlers/config_search.py` | search_1c_methods, search_code |
| BSL анализ | `handlers/analyzers.py` | analyze_bsl, check_standards |
| Метаданные | `handlers/structure.py` | get_object_structure, get_skd_schema |
| Качество | `handlers/quality.py` | check_form_quality, diff_configs |
| Генерация | `handlers/generate.py` | generate_processing, build_epf |
| DSL/CFE | `handlers/dsl_cfe.py` | dsl_compile_meta, cfe_borrow |
| Inspect | `handlers/inspect_data.py` | inspect |
| Прочее | `handlers/misc.py` | get_knowledge, openspec_* |

**Шаг 2: Напиши handler**

```python
# src/mcpserver/handlers/quality.py

async def handle_my_new_check(project: Project, arguments: dict) -> list[types.TextContent]:
    """Handler для MCP tool: my_new_check."""
    file_path = arguments.get("file_path", "")
    if not file_path:
        return [
            types.TextContent(
                type="text", text=json.dumps({"error": "file_path required"}, ensure_ascii=False)
            )
        ]

    # Бизнес-логика — вызывай services
    from src.services.analyzers.my_checker import MyChecker
    checker = MyChecker()
    result = checker.check(Path(file_path))

    response = {"file_path": file_path, "issues": result.issues}
    return [types.TextContent(type="text", text=json.dumps(response, ensure_ascii=False, indent=2))]
```

**Шаг 3: Зарегистрируй tool definition**

```python
# src/mcpserver/tools/tool_definitions.py

def _make_my_new_check_tool() -> types.Tool:
    return types.Tool(
        name="my_new_check",
        description="Проверка моего антипаттерна в .bsl файле",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Путь к .bsl файлу"},
            },
            "required": ["file_path"],
        },
    )
```

**Шаг 4: Зарегистрируй handler**

```python
# src/mcpserver/handlers/quality.py (конец файла)
QUALITY_HANDLERS: dict[str, Callable[..., Any]] = {
    "get_knowledge": handle_get_knowledge,
    # ... существующие handlers ...
    "my_new_check": handle_my_new_check,  # ← добавь сюда
}
```

**Шаг 5: Обнови snapshot**

```bash
# После добавления tool — обнови snapshot
python3 -m pytest tests/test_mcp_tools_snapshot.py --snapshot-update
```

**Шаг 6: Проверь**

```bash
python3 -m pytest tests/test_mcp_handlers_quality.py -v
python3 -m pytest tests/test_mcp_tools_snapshot.py -v
python3 -m pytest tests/test_check_mcp_count.py -v  # проверка count
```

### How-to: Добавить новый DSL-компилятор

DSL-компилятор преобразует JSON-описание в XML-метаданные 1С.
Существующие компиляторы: meta, form, skd, mxl, role.

**Шаг 1: Создай модуль компилятора**

```python
# src/dsl/my_type.py

class MyTypeCompiler:
    """Компилятор JSON → XML для типа MyType."""

    def compile(self, json_spec: dict, output_path: Path) -> str:
        """Скомпилировать JSON в XML.

        Args:
            json_spec: JSON спецификация MyType
            output_path: Куда сохранить XML

        Returns:
            Сгенерированный XML
        """
        # Логика компиляции
        xml = self._generate_xml(json_spec)
        output_path.write_text(xml, encoding="utf-8")
        return xml

    def _generate_xml(self, spec: dict) -> str:
        # Генерация XML
        ...
```

**Шаг 2: Зарегистрируй в facade**

```python
# src/dsl/facade.py

from .my_type import MyTypeCompiler

class DslCompiler:
    def __init__(self):
        self._meta = MetaCompiler()
        self._form = FormCompiler()
        # ... существующие ...
        self._my_type = MyTypeCompiler()  # ← добавь

    def compile_my_type(self, json_spec: dict, output_path: Path) -> str:
        return self._my_type.compile(json_spec, output_path)
```

**Шаг 3: Добавь CLI команду**

```python
# src/cli_commands/tools.py

def cmd_dsl(project: Project, args: argparse.Namespace) -> None:
    if args.dsl_command == "my-type":
        from src.dsl import DslCompiler
        compiler = DslCompiler()
        spec = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        compiler.compile_my_type(spec, Path(args.output_path))
```

**Шаг 4: Добавь MCP tool** (опционально)

См. How-to: Добавить новый MCP tool выше.

**Шаг 5: Напиши тесты**

```python
# tests/test_dsl_my_type.py

class TestMyTypeCompiler:
    def test_basic_compile(self, tmp_path):
        compiler = MyTypeCompiler()
        spec = {"name": "МойОбъект", "synonym": "Мой объект"}
        output = tmp_path / "MyType.xml"
        xml = compiler.compile(spec, output)
        assert "<MyType>" in xml
        assert "МойОбъект" in xml
        assert output.exists()
```

**Шаг 6: Документация**

Добавь спецификацию в `docs/1c-xml-specs/my-type-dsl-spec.md`.

**Шаг 7: Проверь**

```bash
python3 -m pytest tests/test_dsl_my_type.py -v
python3 -m pytest tests/test_dsl_compiler.py -v
```
