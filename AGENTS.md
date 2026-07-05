# AGENTS.md — Правила для AI-агентов в репозитории 1c-ai-dev-env

> **Этот файл — журнал произошедших инцидентов, превращённых в правила.**
> Каждое правило рождено реальной проблемой, а не теоретическими рассуждениями.
> AI-агенты (Codex, Cursor, Claude) читают этот файл перед каждой рабочей сессией.

---

## Рабочий процесс агента (4 этапа)

**Перед началом любой задачи:**

1. **Прочитай AGENTS.md** (этот файл) — компактный набор правил, обязательных для каждой сессии.
2. **Вызови `inspect cf <path>`** или `depgraph build --config <name>` для структурной карты 1С-конфигурации.
3. **Изучи контекст:**
   - `docs/` — архитектура репозитория (API, MCP, EPF Factory)
   - `knowledge_base/` — паттерны и антипаттерны 1С
   - `openspec/` — спецификации изменений
4. **Работай с кодом.** После изменений:
   - `.bsl` → `1c-ai solve check <file> --level standard`
   - `.py` → `pytest tests/test_<module>.py -v`

---

## Инфраструктурные правила

### BSL Language Server
- BSL LS установлен в `~/.local/bin/bsl-language-server` (Java 17+).
- **Если BSL LS не отвечает 10 секунд — дальше двигайся без него.** Используй только `check_1c_standards` (56 правил, без Java).
- Команда проверки: `1c-ai solve check <file.bsl> --level quick` (только стандарты, без BSL LS).

### v8unpack
- `v8unpack 1.2.6` имеет баг: TOC block_size пишется как `0x54` вместо `0x200`.
- **Всегда применяй патч `scripts/patch_epf_blocksize.py` после `v8unpack -B`.** EpfFactory делает это автоматически.
- Round-trip проверка: `v8unpack -E <epf> /tmp/check` → сравнить BSL-модуль.

### Мобильное приложение (конфигурация «Обход»)
- Конфигурация «Обход» — мобильное приложение (`MobilePlatformApplication`).
- **НЕ используй `ПараметрыФормыДинамическогоСписка`** — недоступен в мобильном приложении.
- Используй `ТаблицаЗначений` + запрос (аналогично `ОбщаяФорма.ФормаОбходов`).

### Кэш внешних обработок (1С 8.3.11+)
- 1С кэширует метаданные внешних обработок по имени файла.
- **После модификации EPF — меняй UUID** в ExternalDataProcessor.json (EpfFactory делает это автоматически).

---

## Процессные правила

### Перед работой с 1С-конфигурацией
- Изучи контекст через `1c-ai solve context "<задача>" --config <name>`.
- Проверь актуальность индексов: `1c-ai config build --name <name> --check-freshness`.
- Если индексы устарели — `1c-ai config build --name <name> --force`.

### Перед сборкой EPF
- Используй `1c-ai epf-factory create` (НЕ модифицируй готовый EPF вручную).
- BSL-модуль формы — с реальными **табами** (STD 456), не пробелами.
- Реквизиты формы объявляй **статически** через `--form-spec` (динамические через `ИзменитьРеквизиты` не видит компилятор).

### После изменений в коде
- `.bsl` → `1c-ai solve check <file> --level standard` (0 errors обязательно).
- `.py` → `pytest tests/test_<module>.py -v` (все тесты должны проходить).
- Метаданные 1С → `1c-ai inspect meta <path>` для проверки структуры.

### Критичные файлы (проверяй вручную)
- `src/mcp_server.py` — регистрация MCP-инструментов (45 tools).
- `src/cli.py` — регистрация CLI-команд (19 команд).
- `templates/epf_factory/Form.elem.template.json` — базовый шаблон формы (154 КБ, НЕ очищать).
- `src/services/epf_factory.py` — полный цикл сборки EPF.

---

## Архитектурные правила

### DRY (Don't Repeat Yourself)
- Перед разработкой новой функции — проверь, что похожего нет в `src/services/` или `scripts/`.
- Поиск по коду: `1c-ai search-code "<запрос>" --config <name>` для 1С, `grep -rn` для Python.

### Принцип минимальной достаточности
- AGENTS.md — компактный (этот файл, ~150 строк). Развёрнутые описания — в `docs/`.
- Не дублируй правила: если правило в AGENTS.md, не повторяй его в CONTRIBUTING.md.
- Если правило стало слишком детальным — перенеси в `docs/` и оставь ссылку.

### Локальность инструментов
- MCP-сервер локальный (stdio) — НЕ предлагай внешний MCP.
- dependency_graph и call_graph локальные — НЕ предлагай внешние графовые БД (Neo4j и т.д.).
- v8unpack локальный (Python) — НЕ предлагай 1cv8.exe для сборки EPF.

### Scope discipline (ADR-0006)
- `src/services/` = core, поддерживается и тестируется.
- `experimental/` = замороженные SaaS/Enterprise/Plugin модули, НЕ поддерживаются.
- НЕ импортируй из `experimental/` в `src/` или `tests/` (кроме `experimental/tests/`).
- НЕ возвращай модули из `experimental/` без выполнения критериев ADR-0006.
- Новые SaaS/Enterprise/Plugin фичи — только через ADR и при наличии реальных пользователей.

### Где жить новому коду (Этап 1.3)

Решение-дерево для нового кода:

```
Новый код?
│
├─ CLI-only утилита (запускается пользователем из командной строки)?
│   └─ scripts/ — thin CLI wrapper, импортирует from src.services.*
│
├─ Переиспользуется в MCP handlers или CLI commands?
│   └─ src/services/ — бизнес-логика, тестируется, импортируется через from src.services.*
│
├─ Модель данных (dataclass, Protocol, типы)?
│   └─ src/models/ — чистые данные, без бизнес-логики
│
├─ DSL компилятор (JSON -> XML)?
│   └─ src/dsl/ — компиляторы meta/form/skd/mxl/role
│
├─ MCP handler (новый MCP tool)?
│   └─ src/mcpserver/handlers/ — асинхронные handlers, вызывают services
│
├─ CLI command (новая команда 1c-ai)?
│   └─ src/cli_commands/ — синхронные команды, вызывают services
│
├─ CI check / build utility (запускается только в CI)?
│   └─ scripts/ — без бизнес-логики, только orchestration
│
└─ SaaS/Enterprise/Plugin фича?
    └─ experimental/ (только после ADR-0006)
```

Iron rules:
- ❌ НЕ используй `importlib.util.spec_from_file_location` для загрузки скриптов.
- ❌ НЕ используй `sys.path.insert(0, scripts_dir)` для импорта из scripts/.
- ❌ НЕ размещай бизнес-логику в `scripts/` — только thin CLI wrappers.
- ❌ НЕ импортируй из `scripts/` в `src/` — только наоборот (scripts/ -> src.services).
- ✅ `scripts/X.py` — тонкая обёртка: argparse + `from src.services.X import ...`.
- ✅ `src/services/X.py` — основная логика, тестируется, импортируется нормально.
- ✅ CLI wrappers в `scripts/` делаются через `if __name__ == "__main__": main()`.

Baseline (Этап 1.2 завершён 2026-07-04):
- 14 скриптов перенесено в src/services/ (анализаторы, генераторы, diff, cf_extractor)
- 12 dynamic imports устранено
- 4 sys.path.insert хака удалено
- Подробности: `docs/AUDIT_SCRIPTS_SERVICES.md`

### Структура BSL-модуля
- Области по стандартам 1С: `ПрограммныйИнтерфейс` → `СлужебныйПрограммныйИнтерфейс` → `СлужебныеПроцедурыИФункции` → `ОбработчикиСобытийФормы`.
- Экспортные процедуры — с комментариями-документацией.
- Без `ё` в коде (STD 456:1.1).
- Без EM DASH (`—`), используй дефис (`-`) (STD 456:1.2).
- Отступы — табы, не пробелы (STD 456).

### Язык проекта (ADR-0008)
- Комментарии и docstrings в `src/` — только русский.
- BSL-шаблоны (`templates/`) — только русский (выводятся пользователю).
- Сообщения об ошибках (`raise ValueError("...")`) — русский.
- Имена переменных, функций, классов — английский (Python convention).
- Импорты, технические термины (API, JSON, XML) — английский.
- README.md — основной (русский), README.en.md — волонтёрский перевод.
- НЕ переводи существующие комментарии на английский — это нарушение ADR-0008.

---

## Технические правила

### Имена обработок 1С
- Латиница или кириллица, без пробелов: `МояОбработка`, `Sync_HTTP_Orders`.
- НЕ: `Моя Обработка`, `Моя-Обработка`, `1Обработка`.

### Форма списка в мобильном приложении
- Используй `ТаблицаЗначений` + запрос (НЕ `ДинамическийСписок`).
- Реквизиты объявляй статически через `form_spec`.
- Визуальные элементы создавай программно в `ПриСозданииНаСервере`.

### Запросы 1С
- Ключевые слова КАПСОМ: `ВЫБРАТЬ`, `ИЗ`, `ГДЕ`, `УПОРЯДОЧИТЬ ПО`.
- Без `SELECT *` — указывай конкретные поля.
- Без функций в `WHERE` — замедляет запрос.

### subprocess (S8.2 — 2026-07-05)
- ❌ **НИКОГДА `shell=True`** — всегда list-form cmd: `subprocess.run(["cmd", "arg1", "arg2"], ...)`.
- ✅ **ВСЕГДА `timeout=N`** — без timeout процесс может зависнуть навсегда (DoS).
  - BSL LS: 60 сек (через `BSL_LS_TIMEOUT`)
  - v8unpack: 120 сек (сборка EPF), 60 сек (распаковка)
  - Скрипты индексации: 600 сек (10 мин, большие конфигурации)
  - git/curl: 5-120 сек в зависимости от операции
- ✅ **ВСЕГДА `capture_output=True`** — не засорять stdout/stderr пользователя.
- ✅ **Проверяй returncode** — либо `check=True` (raise при ошибке), либо явная проверка.
- ✅ **Не передавай user input в cmd** — все args должны быть из Path/static strings.
  - Если user input неизбежен — валидируй через regex (как `github_releases.py:76` для repo name).
- ✅ **Используй `sys.executable`** для запуска Python скриптов (не `"python3"` хардкод).
  - Исключение: скрипты, запускаемые из CI, где `python3` — стандарт.

**Audit (S8.2, 2026-07-05):** 8 файлов проверены, `shell=True` не используется нигде.
3 отсутствующих `timeout` добавлены (config_builder.py:261, config_manager.py:666, config_manager.py:678).

### Secrets management (S8.6 — 2026-07-05)
- ❌ **НИКОГДА не коммить `.env`** с реальными секретами — `.env` в `.gitignore`.
- ✅ **Используй `.env.example`** как шаблон — закомментированные placeholders, без реальных значений.
- ✅ **`.git-credentials` в `.gitignore`** — никогда не попадает в коммит.
- ✅ **detect-secrets в pre-commit** — hook автоматически проверяет код на секреты при коммите.
- ✅ **CI secret scanning** — `.github/workflows/secret-scanning.yml` проверяет на каждом push/PR.
- ✅ **GitHub Secrets для CI** — токены для CI хранятся в GitHub Settings → Secrets, не в коде.
- ✅ **Fine-grained PAT** — используйте fine-grained token с минимальными scope (1 репозиторий).
  - НЕ используйте classic token (доступ ко всем репозиториям).
  - Срок действия: 30 дней максимум.
  - Permissions: только необходимые (Contents, Workflows).
- ✅ **При утечке токена** — немедленно отзовите на github.com/settings/tokens.
  - Если токен попал в git history — используйте `git filter-branch` или BFG Repo-Cleaner.

**Audit (S8.6, 2026-07-05):** .env.example создан, .gitignore обновлён, detect-secrets в pre-commit,
CI workflow создан, .secrets.baseline создан.

### SAST — Static Analysis (S8.4 — 2026-07-06)
- ✅ **bandit** — Python AST analyzer. Конфиг: `bandit.toml`. Запуск: `bandit -c bandit.toml -r src/`.
- ✅ **semgrep** — multi-language SAST (Python + Dockerfile + BSL). Конфиг: `.semgrep.yml`.
- ✅ **CI: `.github/workflows/sast.yml`** — bandit + semgrep на каждом PR.
- ❌ **Никогда не коммить код с HIGH severity находками** — CI fail.
- ✅ **SARIF отчёты** загружаются в GitHub Security tab.
- ✅ **semgrep rules** покрывают: eval/exec, pickle.load, yaml.load без SafeLoader, shell=True, hardcoded passwords, os.system, path traversal, Dockerfile best practices, BSL Выполнить().
- ✅ **bandit skips**: B101 (assert в тестах), B311 (random для не-крипто).

**Audit (S8.4, 2026-07-06):** bandit.toml + .semgrep.yml созданы. CI workflow sast.yml создан.
Тесты: `tests/test_s8_4_sast.py` (17 тестов). Покрытие: реальные запуски bandit/semgrep на тестовых уязвимостях.

### SBOM (I7.9 — 2026-07-05)
- ✅ **SBOM генерируется через CycloneDX** — `.github/workflows/sbom-generation.yml`.
- ✅ **Формат: CycloneDX 1.5 JSON** — стандарт для supply chain compliance.
- ✅ **SBOM загружается в GitHub Release** — каждый release содержит `sbom.json`.
- ✅ **SBOM коммитится в репозиторий** — при push в main обновляется `sbom.json`.
- ✅ **Пользователи могут проверять transitive зависимости** на CVE через SBOM.

### Коммиты
- Формат: `<type>(<scope>): <description>` (см. CONTRIBUTING.md).
- Один коммит — одно логическое изменение.
- Перед коммитом: `pytest tests/` (все тесты должны проходить).

### Push
- Только в `main` после прохождения CI.
- PAT токен: использовать `gh auth login` (НЕ хранить токен в git remote URL).

---

## Антипаттерны (НЕ делать)

- ❌ **Модифицировать готовый EPF вручную** — используй `epf-factory`.
- ❌ **Создавать реквизиты через `ИзменитьРеквизиты()`** в мобильном приложении — компилятор их не видит.
- ❌ **Использовать `ПараметрыФормыДинамическогоСписка`** в мобильном приложении — недоступен.
- ❌ **Пробелы вместо табов** в BSL (STD 456).
- ❌ **Буква `ё`** в BSL-коде (STD 456:1.1).
- ❌ **EM DASH `—`** в BSL-коде (STD 456:1.2), используй дефис `-`.
- ❌ **Внешний MCP-сервер** — у нас локальный, не нужен внешний.
- ❌ **Дублировать правила** в AGENTS.md и CONTRIBUTING.md.

---

## История инцидентов (источник правил)

| Инцидент | Правило | Дата |
|---|---|---|
| 1С пишет «Ошибка формата потока» | Патч `block_size` после v8unpack | 2026-07-01 |
| «Переменная не определена (ТаблицаСписка)» | Реквизиты статически через form_spec | 2026-07-01 |
| «Тип не определен (ПараметрыФормыДинамическогоСписка)» | ТаблицаЗначений + запрос для мобильного | 2026-07-01 |
| BSL LS таймаут 60 сек | `--skip-bsl-validation` для быстрых сборок | 2026-07-01 |
| Дублирование UUID в EPF | EpfFactory генерирует новые UUID | 2026-07-01 |

---

## Ссылки

- [CONTRIBUTING.md](CONTRIBUTING.md) — правила для людей-контрибьюторов
- [README.md](README.md) — обзор репозитория
- [docs/AGENTS_MD.md](docs/AGENTS_MD.md) — расширенное описание AGENTS.md
- [docs/EPF_FACTORY.md](docs/EPF_FACTORY.md) — инструкция по созданию EPF
- [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) — интеграция с MCP
- [CHANGELOG.md](CHANGELOG.md) — история изменений

---

*Этот файл — живой документ. Добавляй правила при новых инцидентах, удаляй устаревшие.*
*Каждая новая строка — результат инцидента, а не фантазия.*
