# Audit: scripts/ vs src/services/

> Этап 1.1 поэтапного плана улучшения.
> Создано: 2026-07-04.
> Цель: составить матрицу дублирования между 37 скриптами (~16.5K LOC) и
> 35 сервисами (~19.6K LOC), классифицировать каждый скрипт по 3
> категориям, выявить мёртвый код.

## Контекст проблемы

Текущая архитектура имеет **3 способа** вызова скриптов из `src/`:

1. **`importlib.util.spec_from_file_location`** — динамический импорт
   по пути файла (12 мест в `src/mcpserver/handlers/` и `src/cli_commands/`)
2. **`sys.path.insert(0, scripts_dir)` + `import`** — модификация sys.path
   (4 места)
3. **Прямой путь к файлу** — `script_path = project.paths.scripts_dir / "X.py"`
   (2 места)

Все 3 способа **хрупки**: ломаются при переименовании скрипта,
затрудняют тестирование (нельзя `pytest`-cover без sys.path хаков),
нарушают IDE-навигацию, усложняют type-checking.

## Сводная статистика

| Метрика | Значение |
|---------|----------|
| Скриптов в `scripts/` | 37 |
| Сервисов в `src/services/` | 35 |
| LOC в `scripts/` | ~16 500 |
| LOC в `src/services/` | ~19 600 |
| Скриптов с аналогом в `services/` (по имени) | 0 (нет прямых совпадений) |
| Динамических import'ов (`importlib.util`) | 12 |
| `sys.path.insert` для scripts/ | 4 |
| Скриптов, вызываемых из MCP handlers | 14 |
| Скриптов, вызываемых из CLI commands | 8 |
| Скриптов без callers (мёртвые candidates) | 7 (после аудита — 0 полностью мёртвых) |

## Категории скриптов

### Категория A — Уникальная логика, candidates для переноса в `src/services/`

Скрипты с реальной бизнес-логикой, вызываемые из MCP/CLI. Должны
стать полноценными сервисами с импортом `from src.services.X import Y`.

| Скрипт | LOC | Callers (MCP/CLI/services) | Категория переноса |
|--------|-----|----------------------------|--------------------|
| `security_auditor` | 715 | analyzers, sarif_reporter, task_processor, quality.py | → `services/analyzers/security.py` |
| `check_1c_standards` | 1738 | analyzers, sarif_reporter, task_processor, solve.py | → `services/analyzers/standards.py` (разбить по этапу 2.1) |
| `check_metadata_standards` | 554 | analyzers, sarif_reporter, task_processor | → `services/analyzers/metadata.py` |
| `code_metrics` | 560 | analyzers, quality, sarif_reporter, task_processor | → `services/analyzers/metrics.py` |
| `transaction_checker` | 376 | analyzers, quality, sarif_reporter, task_processor | → `services/analyzers/transactions.py` |
| `query_analyzer` | 378 | analyzers, sarif_reporter, task_processor | → `services/analyzers/queries.py` |
| `architecture_analyzer` | 585 | quality.py | → `services/analyzers/architecture.py` |
| `form_quality_checker` | 323 | quality.py | → `services/analyzers/forms.py` |
| `skd_quality_checker` | 259 | quality.py | → `services/analyzers/skd.py` |
| `diff_analyzer` | 278 | quality.py | → `services/diff.py` |
| `code_generator` | 501 | generate.py | → `services/code_generator.py` |
| `code_validator` | 514 | generate.py | → `services/code_validator.py` |
| `epf_builder` | 324 | generate.py | → `services/epf_builder.py` |
| `metadata_extractor` | 1102 | config_builder, structure | → `services/metadata/extractor.py` (этап 2.3) |
| `form_analyzer` | 472 | config_builder, structure | → `services/metadata/forms.py` |
| `skd_parser` | 682 | config_builder, structure | → `services/metadata/skd.py` |
| `build_api_reference` | 720 | config_builder, config_manager | → `services/builders/api_index.py` (этап 2.4) |
| `build_config_index_generic` | 1018 | config_manager | → `services/builders/` (этап 2.4, разбить по 5 индексам) |
| `fast_search_1c` | 200 | search.py (CLI) | **Уже thin CLI wrapper** над `src.services.search_bm25` (Этап 1.2-G4: убран sys.path.insert) |

**Итого candidates для переноса:** 19 скриптов, ~10 550 LOC.

### Категория B — Парсеры метаданных, используемые только внутри `scripts/`

Скрипты, которые вызываются другими скриптами (не из `src/` напрямую).
Кандидаты на перенос вместе с их callers (категория A).

| Скрипт | LOC | Callers (внутри scripts/) | Решение |
|--------|-----|---------------------------|---------|
| `metadata_parser` | 671 | skd_parser, cf_to_xml_adapter, v8_metadata_parser, improved_cf_adapter | Перенести в `services/metadata/parser.py` вместе с callers (этап 2.3) |
| `cf_to_xml_adapter` | 533 | config_manager (через importlib) | Перенести в `services/cf/adapter.py` (этап 2.x) |
| `improved_cf_adapter` | 842 | config_manager | Перенести в `services/cf/improved_adapter.py` |
| `cf_extractor` | 365 | config_manager | Перенести в `services/cf/extractor.py` |
| `v8_metadata_parser` | 394 | cf_to_xml_adapter, improved_cf_adapter, tests/test_integration | Перенести в `services/cf/v8_parser.py` |
| `form_indexer` | 461 | build_api_reference, tests | Перенести в `services/builders/form_indexer.py` (этап 2.4) |
| `build_syntax_helper_index` | 426 | fast_search_1c | **Build utility** (как build_api_reference), остаётся в scripts/ (Этап 1.2-G4: убран sys.path.insert) |
| `patch_epf_blocksize` | 180 | epf_factory (через importlib) | Перенести в `services/epf/patch_blocksize.py` (этап 2.2) |
| `xml_parser` | 87 | tests/test_fuzzing, упоминается в docs | Перенести в `services/xml_parser.py` (общая утилита) |

**Итого:** 9 скриптов, ~3 908 LOC. Переносятся вместе с категорией A.

### Категория C — CI/infrastructure скрипты (остаются в `scripts/`)

Это правильно живущие thin wrappers или CI-утилиты. **НЕ переносятся.**

| Скрипт | LOC | Назначение | Почему остаётся |
|--------|-----|------------|-----------------|
| `check_mcp_count` | 135 | CI gate (MCP tools count) | CI check, не business-logic |
| `check_versions` | 68 | CI gate (version sync) | CI check |
| `sync_versions` | 108 | CI utility (sync versions across files) | CI utility |
| `run_benchmarks` | 211 | CI benchmarks runner | CI runner, не используется в runtime |
| `run_sarif_scan` | 104 | CI SARIF scan runner | Уже импортирует `src.services.sarif_reporter` ✓ |
| `generate_openapi` | 153 | CI/docs: OpenAPI spec generation | Build-time utility |
| `test_mcp_e2e` | 123 | E2E test runner | Test script |
| `img_grid` | 173 | CLI utility (LLM-friendly grid on screenshots) | Standalone CLI utility, упоминается в README |
| `hbk_extractor` | 243 | CLI utility (extract from .hbk files) | Standalone CLI utility, упоминается в install.sh |

**Итого остаётся:** 9 скриптов, ~1 318 LOC. Это корректная граница.

### Категория D — Мёртвые скрипты (candidates на удаление)

После аудита **полностью мёртвых скриптов не обнаружено**. Все 37
скриптов имеют хотя бы одного caller (MCP/CLI/services/tests/CI/docs).

Скрипты с минимальным использованием (требуют ручной проверки перед
этапом 1.4):

| Скрипт | LOC | Использование | Решение |
|--------|-----|----------------|---------|
| `v8_metadata_parser` | 394 | tests/test_integration.py + 2 scripts | Проверить, не дублирует ли metadata_extractor |
| `xml_parser` | 87 | tests/test_fuzzing.py + docs | Возможный duplicate с lxml/etree в services |
| `improved_cf_adapter` | 842 | config_manager + tests | Проверить, не дублирует ли cf_to_xml_adapter |

**Вывод:** задача 1.4 (удаление мёртвых скриптов) сокращается до
минимума — после аудита нет явно мёртвого кода. Рекомендация: при
переносе (1.2) проверять дубликаты и удалять по ходу.

## Карта дублирования

### Дубликаты парсеров метаданных (выявленные)

| Что | Где | Дублирование |
|-----|-----|--------------|
| `metadata_extractor` (1102) vs `metadata_parser` (671) | scripts/ vs scripts/ | Оба парсят метаданные 1С. extractor — единый парсер 35 типов, parser — вероятно, старая версия. **Проверить после переноса.** |
| `cf_to_xml_adapter` (533) vs `improved_cf_adapter` (842) | scripts/ vs scripts/ | Оба адаптируют .cf → XML. improved — вероятно, новая версия. **Проверить, какой использовать.** |
| `xml_parser` (87) | scripts/ | Возможно дублирует `lxml.etree` / `xml.etree.ElementTree`, уже используемые в services. **Проверить.** |

### Дубликаты адаптеров конфигурации

`improved_cf_adapter` (842) vs `cf_to_xml_adapter` (533) vs
`cf_extractor` (365) — три парсера .cf формата в scripts/. Нужно
решить, какой оставить, после переноса в services/.

## План переноса (для задачи 1.2)

Перенос делать **по группам**, каждый PR — одна группа:

### Группа 1: Анализаторы (P0, 5-7 скриптов)

Перенести в `src/services/analyzers/` (новый пакет):

- `security_auditor` → `analyzers/security.py`
- `check_1c_standards` → `analyzers/standards.py` (god-файл, этап 2.1 разобьёт)
- `check_metadata_standards` → `analyzers/metadata.py`
- `code_metrics` → `analyzers/metrics.py`
- `transaction_checker` → `analyzers/transactions.py`
- `query_analyzer` → `analyzers/queries.py`
- `architecture_analyzer` → `analyzers/architecture.py`
- `form_quality_checker` → `analyzers/forms.py`
- `skd_quality_checker` → `analyzers/skd.py`

Обновить callers:
- `src/services/analyzers.py` (facade) — заменить dynamic import на `from .analyzers.X`
- `src/services/sarif_reporter.py` — то же
- `src/services/task_processor.py` — то же
- `src/mcpserver/handlers/quality.py` — то же (12 dynamic import'ов)
- `src/cli_commands/solve.py` — то же

**Effort:** ~3 чел-дня. **Risk:** высокий — много callers.

### Группа 2: Генераторы (P1, 3 скрипта)

- `code_generator` → `services/code_generator.py`
- `code_validator` → `services/code_validator.py`
- `epf_builder` → `services/epf_builder.py`

Обновить `src/mcpserver/handlers/generate.py` (3 dynamic import'а).

**Effort:** ~1 чел-день. **Risk:** средний.

### Группа 3: Diff (P2, 1 скрипт)

- `diff_analyzer` → `services/diff.py`

Обновить `src/mcpserver/handlers/quality.py`.

**Effort:** ~0.5 чел-дня. **Risk:** низкий.

### Группа 4: Поиск (P1, 1 скрипт + зависимости)

- `fast_search_1c` → `services/search_platform.py`
- `build_syntax_helper_index` → переносится вместе (используется только в fast_search_1c)

Обновить `src/cli_commands/search.py`.

**Effort:** ~0.5 чел-дня. **Risk:** низкий.

### Группа 5: Парсеры метаданных (P2, отложить до этапа 2.3)

- `metadata_extractor`, `metadata_parser`, `form_analyzer`, `skd_parser`,
  `form_indexer`

Эти переносятся **вместе с этапом 2.3** (декомпозиция
metadata_extractor.py на 35 модулей по типам объектов). Отдельный
перенос сейчас создаст двойную работу.

**Effort:** учитывается в этапе 2.3 (6 чел-дней).

### Группа 6: Build индексов (P2, отложить до этапа 2.4)

- `build_config_index_generic`, `build_api_reference`

Переносятся вместе с этапом 2.4 (декомпозиция на 5 builder-модулей).

**Effort:** учитывается в этапе 2.4 (4 чел-дня).

### Группа 7: CF парсеры (P2, отложить)

- `cf_extractor`, `cf_to_xml_adapter`, `improved_cf_adapter`,
  `v8_metadata_parser`

Сначала (в рамках этой задачи) решить, какой из 3 cf-адаптеров
оставить, потом переносить. Возможный duplicate.

**Effort:** ~1.5 чел-дня. **Risk:** средний (нужно решение по дубликатам).

### Группа 8: Утилиты (P3, минимальный приоритет)

- `patch_epf_blocksize` → переносится с этапом 2.2 (epf_factory decomposition)
- `xml_parser` → возможно удалить (дублирует lxml/etree)

**Effort:** ~0.5 чел-дня.

## Сводка для задачи 1.2

| Группа | Скриптов | LOC | Effort (дни) | Когда |
|--------|----------|-----|--------------|-------|
| 1. Анализаторы | 9 | ~4 977 | 3 | Этап 1.2 |
| 2. Генераторы | 3 | ~1 339 | 1 | Этап 1.2 |
| 3. Diff | 1 | ~278 | 0.5 | Этап 1.2 |
| 4. Поиск | 1 (+1 dep) | ~626 | 0.5 | Этап 1.2 |
| 5. Метаданные | 5 | ~3 428 | (этап 2.3) | Этап 2.3 |
| 6. Build индексов | 2 | ~1 738 | (этап 2.4) | Этап 2.4 |
| 7. CF парсеры | 4 | ~2 134 | 1.5 | Этап 1.2 (после решения по дубликатам) |
| 8. Утилиты | 2 | ~267 | 0.5 | Этап 2.2 |
| **Итого Этап 1.2** | **14** | **~7 220** | **~6.5** | — |

План 1.2 оценивался в 8 чел-дней — фактически ~6.5 (без групп 5, 6, 8
которые переносятся в этапы 2.x). Запас 1.5 дня — на regression-фиксы.

## Рекомендации

1. **Начать с Группы 3 (Diff)** — самый маленький и изолированный
   перенос, проверит workflow (commit + tests + push).
2. **Затем Группа 4 (Поиск)** — тоже маленькая, добавит `build_syntax_helper_index`.
3. **Группа 2 (Генераторы)** — 3 скрипта, средний риск.
4. **Группа 1 (Анализаторы)** — самая большая, делать по 1-2 скрипта за
   коммит. Особое внимание: `check_1c_standards` (1738 LOC, много callers).
5. **Группа 7 (CF парсеры)** — после решения, какой adapter оставить.
6. **Группы 5, 6, 8** — отложить до этапов 2.3, 2.4, 2.2 соответственно.

## Anti-patterns, выявленные в коде

### 1. `importlib.util.spec_from_file_location` для scripts/

**Пример** (`src/mcpserver/handlers/quality.py:117`):
```python
spec = importlib.util.spec_from_file_location("security_auditor", sa_path)
sa_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa_mod)
```

**Проблема:** dynamic import по пути файла. Ломает IDE-навигацию,
type-checking, pytest coverage. Хрупко к переименованиям.

**Решение:** перенести логику в `src/services/`, импортировать как
`from src.services.analyzers.security import audit_security`.

### 2. `sys.path.insert(0, scripts_dir)`

**Пример** (`src/cli_commands/tools.py:256`):
```python
sys_mod.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
```

**Проблема:** модификация global sys.path. Влияет на другие модули в
том же процессе. Затрудняет тестирование.

**Решение:** перенести целевой скрипт в `src/services/`, импортировать
нормально.

### 3. Дубликаты парсеров

3 cf-адаптера (`cf_to_xml_adapter`, `improved_cf_adapter`, `cf_extractor`)
вероятно дублируют друг друга. Решение — после аудита оставить одного,
остальные удалить.

## Связанные документы

- [ADR-0006](../adr/0006-scope-reduction-v6.md) — scope discipline
- [ROADMAP.md](../ROADMAP.md) — поэтапный план
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — текущая архитектура
- [AGENTS.md](../AGENTS.md) — правила для AI-агентов (включая scope discipline)

---

*Этот документ — baseline для задачи 1.2 (перенос логики). После
переноса каждой группы обновлять соответствующую секцию.*
