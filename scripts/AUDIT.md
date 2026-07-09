# Scripts Audit — Phase 1.4

**Дата:** July 2026  
**Ответственный:** Tech Lead  
**Статус:** Completed

## Удалённые скрипты (3 шт., ~22 KB)

| Скрипт | LOC | Причина удаления |
|--------|-----|------------------|
| `fix_tool_defs.py` | 285 | Одноразовый скрипт для правки tool_definitions.py — задача выполнена |
| `fix_tool_workflow_hints.py` | 188 | Одноразовый скрипт для добавления workflow hints — задача выполнена |
| `profile_metadata_extractor.py` | 196 | Одноразовый профайлер для этапа 6.1 — профилирование завершено, baseline зафиксирован в `tests/test_benchmarks_synthetic.py` |

Все 3 скрипта не имели упоминаний в `src/`, `tests/`, `docs/`, CI-конфигах, `pyproject.toml`, `README.md`.

## Оставшиеся скрипты (39 шт.)

Классификация по назначению:

### CI checks / utilities (6 шт.)
Используются в `.github/workflows/` или как pre-commit hooks.

- `check_mcp_count.py` — проверка количества MCP tools (CI gate)
- `check_versions.py` — pre-commit hook для синхронизации версий
- `check_no_scripts_imports.py` — проверка что src/ не импортирует scripts/
- `sync_versions.py` — синхронизация версий в pyproject.toml/README/__init__
- `run_benchmarks.py` — запуск бенчмарков в CI
- `run_sarif_scan.py` — SARIF отчёт для GitHub Code Scanning

### Build utilities (5 шт.)
Скрипты сборки индексов и метаданных.

- `metadata_extractor.py` — основной сборщик `unified-metadata-index.json`
- `fast_search_1c.py` — сборщик TF-IDF индекса по методам платформы 1С
- `build_api_reference.py` — сборщик `api-reference.json`
- `build_config_index_generic.py` — generic сборщик индекса конфигурации
- `build_syntax_helper_index.py` — индекс синтакс-помощника

### Анализаторы (15 шт.)
Аналитические утилиты, используемые как библиотеки или CLI.

- `analyzer_coverage_report.py` — отчёт покрытия анализаторов
- `architecture_analyzer.py` — анализ архитектуры
- `cf_extractor.py` — распаковка .cf файлов
- `cf_to_xml_adapter.py` — адаптер CF → XML
- `check_1c_standards.py` — проверка стандартов 1С
- `check_metadata_standards.py` — проверка стандартов метаданных
- `code_generator.py` — генератор кода
- `code_metrics.py` — метрики кода
- `code_validator.py` — валидатор BSL синтаксиса
- `diff_analyzer.py` — анализ diff между конфигурациями
- `epf_builder.py` — сборщик .epf файлов
- `form_analyzer.py` — анализ форм
- `form_indexer.py` — индексатор форм
- `form_quality_checker.py` — проверка качества форм
- `security_auditor.py` — аудитор безопасности

### Парсеры (7 шт.)
Парсеры специфичных форматов 1С.

- `hbk_extractor.py` — парсер .hbk файлов справки 1С
- `improved_cf_adapter.py` — улучшенный адаптер CF
- `metadata_parser.py` — общий парсер метаданных
- `query_analyzer.py` — анализатор запросов 1С
- `skd_parser.py` — парсер СКД схем
- `skd_quality_checker.py` — проверка качества СКД
- `v8_metadata_parser.py` — парсер v8 metadata
- `xml_parser.py` — общий XML парсер

### Утилиты (5 шт.)
Прочие вспомогательные скрипты.

- `generate_openapi.py` — генератор OpenAPI спецификации
- `img_grid.py` — утилита для изображений
- `patch_epf_blocksize.py` — патчер blocksize в .epf
- `test_mcp_e2e.py` — E2E тест MCP сервера
- `transaction_checker.py` — проверка транзакций BSL

## Рекомендации

### Фаза 3 (консолидация)
В Фазе 3 (Consolidation) продакшн-команды должны переехать в `src/cli/commands/`:
- `metadata_extractor.py` → `src/cli/commands/config.py`
- `fast_search_1c.py` → `src/cli/commands/search.py`
- Остальные build-скрипты — по мере необходимости

### Не трогать
- CI checks (6 шт.) — оставляем в `scripts/`, они запускаются из workflows
- E2E тесты (`test_mcp_e2e.py`) — оставляем, используется в CONTRIBUTING.md
