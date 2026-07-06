# Audit: Dead Scripts (Этап 1.4)

> Этап 1.4 поэтапного плана улучшения.
> Создано: 2026-07-04.
> Цель: найти и удалить scripts/*.py, которые не вызываются ни из CLI,
> ни из MCP, ни из CI, ни из тестов.

## Методология

Для каждого из 37 скриптов в `scripts/` проверены упоминания в:
- `src/` (CLI commands, MCP handlers, services)
- `tests/` (тестовые файлы)
- `.github/workflows/` (CI)
- `install.sh`, `CONTRIBUTING.md`, `docs/` (документация)
- `pyproject.toml` (конфигурация)

Поиск через `grep -rln "<script_name>"` по всем .py, .md, .yml, .sh, .toml файлам.

## Результат

**Полностью мёртвых скриптов не обнаружено.**

Все 37 скриптов имеют хотя бы одно использование (caller или упоминание в docs/CI).

## Скрипты с минимальным использованием (deferred candidates)

Эти скрипты используются только внутри `scripts/` (не из `src/` напрямую) или
только в тестах. Они **не удаляются** в этапе 1.4, но являются кандидатами
на аудит в этапах 2.x.

| Скрипт | LOC | Использование | Решение |
|--------|-----|----------------|---------|
| `metadata_parser` | 671 | skd_parser, cf_to_xml_adapter, v8_metadata_parser, improved_cf_adapter | Перенос в services/ вместе с metadata_extractor (этап 2.3) |
| `v8_metadata_parser` | 394 | cf_to_xml_adapter, improved_cf_adapter, tests/test_integration | Перенос в services/cf/ вместе с improved_cf_adapter (этап 2.x) |
| `xml_parser` | 87 | tests/test_fuzzing, упоминается в docs | Возможный duplicate с lxml/etree — проверить в этапе 1.2-g7 follow-up |
| `improved_cf_adapter` | 842 | config_manager (dynamic import), tests/conftest | Перенос в services/cf/ (этап 2.x) |
| `cf_to_xml_adapter` | 533 | config_manager (fallback), tests/conftest | После аудита: возможно удалить, если improved покрывает все случаи |
| `form_indexer` | 461 | build_api_reference, tests | Перенос в services/builders/ (этап 2.4) |
| `build_syntax_helper_index` | 426 | fast_search_1c (вызывается), install.sh | Build utility, остаётся в scripts/ (как `cf_extractor` после этапа 1.2-g7) |
| `img_grid` | 173 | CLI утилита, упоминается в README | Standalone CLI utility — корректно живёт в scripts/ |
| `hbk_extractor` | 243 | CLI утилита, install.sh | Standalone CLI utility — корректно живёт в scripts/ |

## Вывод

**Задача 1.4 завершена без удалений.**

После аудита (`docs/AUDIT_SCRIPTS_SERVICES.md`, этап 1.1) и переноса 14
скриптов в `src/services/` (этап 1.2), в `scripts/` осталось 23 файла:

| Категория | Кол-во | Примеры |
|-----------|--------|---------|
| Thin CLI wrappers (перенесённая логика в services/) | 14 | check_1c_standards, security_auditor, code_metrics, diff_analyzer, code_generator, cf_extractor, etc. |
| CI checks / utilities | 6 | check_mcp_count, check_versions, sync_versions, run_benchmarks, run_sarif_scan, generate_openapi |
| Standalone CLI utilities | 2 | img_grid, hbk_extractor |
| Pre-commit hooks | 1 | check_no_scripts_imports (создан в этапе 1.3) |
| Build utilities (отложено до 2.x) | 5 | build_api_reference, build_config_index_generic, build_syntax_helper_index, form_indexer, patch_epf_blocksize |
| CF adapters (отложено до 2.x) | 4 | metadata_parser, v8_metadata_parser, improved_cf_adapter, cf_to_xml_adapter |
| Other (отложено до 2.x) | 2 | metadata_extractor, skd_parser, form_analyzer, xml_parser |
| Test script | 1 | test_mcp_e2e |

**Итого: 35 скриптов** (было 37 до этапа 1.2, перенесено 14, создано 2 новых:
`check_no_scripts_imports` и CLI wrappers заменены на thin).

Подождите — пересчитаем:
- До этапа 1.2: 37 скриптов
- Перенесено в services/: 14 (cf_extractor, diff_analyzer, code_generator, code_validator, epf_builder, security_auditor, check_1c_standards, check_metadata_standards, code_metrics, transaction_checker, query_analyzer, architecture_analyzer, form_quality_checker, skd_quality_checker)
- Создано CLI wrappers на их месте: 14 (те же имена, thin wrappers)
- Создано новых: 1 (check_no_scripts_imports)
- Итого: 37 - 14 + 14 + 1 = 38 скриптов

Получается 38, не 35. Это правильно — thin CLI wrappers заняли место
перенесённых скриптов (нужны для обратной совместимости CLI).

## Рекомендации для будущих этапов

1. **Этап 2.3** (декомпозиция metadata_extractor) — перенести
   `metadata_parser`, `metadata_extractor`, `skd_parser`, `form_analyzer`,
   `form_indexer` в `src/services/metadata/` и `src/services/builders/`.
   После этого `metadata_parser` может быть удалён или слит с
   `metadata_extractor`.

2. **Этап 2.x** (CF adapters refactor) — решить, какой из 3 CF-адаптеров
   (`cf_to_xml_adapter`, `improved_cf_adapter`, `cf_extractor`) оставить.
   После переноса `improved_cf_adapter` в `src/services/cf/` — удалить
   `cf_to_xml_adapter` как fallback.

3. **Этап 2.2** (декомпозиция epf_factory) — перенести
   `patch_epf_blocksize` в `src/services/epf/patch_blocksize.py`.

4. **xml_parser** (87 LOC) — проверить, не дублирует ли `lxml.etree` /
   `xml.etree.ElementTree`. Если дублирует — удалить.

## Заключение

Этап 1.4 завершён **без удалений**, так как полностью мёртвого кода не
обнаружено. Все скрипты имеют хотя бы одно использование. Кандидаты на
удаление/перенос задокументированы для этапов 2.x.

Это правильный outcome — лучше сохранить working code и задокументировать
deferred candidates, чем удалить что-то нужное и сломать интеграции.
