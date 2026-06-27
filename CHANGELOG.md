# Changelog

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
