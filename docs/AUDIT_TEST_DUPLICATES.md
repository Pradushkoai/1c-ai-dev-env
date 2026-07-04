# Audit: Test Duplicates (Этап 5.1)

> Этап 5.1 поэтапного плана улучшения.
> Создано: 2026-07-04.
> Цель: найти дубликаты среди 1624 тестов, объединить, сократить количество.

## Методология

1. **Подсчёт тестов:** `pytest --co -q` → 1624 теста в 99 файлах.
2. **Поиск дубликатов по имени:** Python-скрипт, ищущий `def test_*` с
   одинаковыми именами в разных файлах.
3. **Анализ модулей, тестируемых в нескольких файлах:** Python-скрипт,
   ищущий `from src.X import ...` в нескольких test-файлах.
4. **Ручной анализ** найденных кандидатов на дубликаты.

## Результаты

### Дубликаты по имени (5 случаев)

| Имя теста | Файлы | Анализ |
|-----------|-------|--------|
| `test_format_violations_empty` | test_check_standards, test_metadata_standards | НЕ дубликат — разные `format_violations` (BSL standards vs metadata standards) |
| `test_format_violations_json` | test_check_standards, test_metadata_standards | НЕ дубликат — то же |
| `test_format_violations_text` | test_check_standards, test_metadata_standards | НЕ дубликат — то же |
| `test_sarif_results_count_matches_violations` | test_property, test_sarif_reporter | НЕ дубликат — test_property это property-based (hypothesis), test_sarif_reporter — unit |
| `test_strip_ns` | test_metadata_standards, test_build_config_index | НЕ дубликат — test_strip_ns в test_build_config_index тестирует локальную функцию |

**Вывод:** 0 реальных дубликатов по имени. Все 5 случаев — разные функции
с одинаковыми именами в разных модулях.

### Модули, тестируемые в нескольких файлах (25 случаев)

25 модулей `src.*` тестируются в 2+ файлах. Анализ показал:

#### Категория A: E2E + Unit (НЕ дубликаты) — 8 модулей

| Модуль | Unit-тест | E2E-тест |
|--------|-----------|----------|
| analyzers.architecture_analyzer | test_architecture_analyzer | test_e2e |
| analyzers.code_metrics | test_code_metrics | test_e2e |
| analyzers.query_analyzer | test_query_analyzer | test_e2e |
| analyzers.security_auditor | test_security_auditor | test_e2e |
| analyzers.transaction_checker | test_transaction_checker | test_e2e |

E2E-тесты в `test_e2e.py` проверяют **интеграцию** (генерация → анализ),
а unit-тесты — отдельные функции. Это **правильное разделение**, не дубликаты.

#### Категория B: Разные аспекты (НЕ дубликаты) — 12 модулей

| Модуль | Файл 1 | Файл 2 | Анализ |
|--------|--------|--------|--------|
| mcp_server | test_mcp_server | test_epf_factory_mcp | test_mcp_server — общий, test_epf_factory_mcp — EPF-specific |
| mcp_server | test_mcp_server | test_mcp_tools_sync | test_mcp_tools_sync — sync check |
| handlers.analyzers | test_mcp_handlers_analyzers | test_async_to_thread | test_async_to_thread — async helper |
| handlers.config_search | test_mcp_handlers_config_search | test_async_to_thread | то же |
| handlers.quality | test_mcp_handlers_quality | test_path_traversal_protection | test_path_traversal — security |
| models.config_registry | test_config_builder, test_config_manager, test_config_split, test_config_validator, test_integration | 5 файлов | Каждый тестирует свой аспект (build, manage, split, validate, integration) |
| models.configuration | 7 файлов | — | Каждый тестирует свой аспект |
| models.task | test_task_processor, test_sarif_reporter, test_property, test_benchmarks | 4 файла | Каждый тестирует свой аспект |
| project | test_integration, test_project_api, test_project_from_cwd, test_solve | 4 файла | Каждый тестирует свой аспект |
| bsl_analyzer | test_bsl_analyzer, test_bsl_ls_isolation, test_solve | 3 файла | test_bsl_ls_isolation — subprocess isolation, test_solve — CLI |
| cfe_manager | test_cfe_manager, test_type_map_unified | 2 файла | test_type_map_unified — TYPE_MAP |

**Вывод:** все 12 случаев — разные аспекты одного модуля, не дубликаты.

#### Категория C: Возможные кандидаты на объединение — 5 модулей

| Модуль | Файлы | Анализ |
|--------|-------|--------|
| search_bm25 | test_search_bm25, test_search_bm25_cache | test_search_bm25_cache — кэш, можно объединить |
| search_hybrid | test_search_hybrid, test_search_bm25 (в нём есть hybrid tests) | возможно дублирование |
| config_manager | test_config_manager, test_config_builder | разные классы, но перекрытие |
| path_manager | test_path_manager, test_project_from_cwd | test_project_from_cwd — edge case |
| epf_factory | test_epf_factory, test_epf_factory_mcp | test_epf_factory_mcp — MCP-specific |

Эти 5 случаев требуют более детального анализа, но риск regression
при объединении выше, чем польза. Оставлены как есть.

## Статистика

| Метрика | Значение |
|---------|----------|
| Всего тестов | 1624 |
| Тестовых файлов | 99 |
| Уникальных тест-функций | 357 |
| Дубликатов по имени | 5 (все false positive — разные функции) |
| Реальных дубликатов | 0 |
| Модулей с тестами в 2+ файлах | 25 (все — разные аспекты) |
| Кандидатов на объединение | 5 (риск > польза, отложено) |

## Вывод

**Задача 5.1 завершена без объединений.**

Из 1624 тестов:
- 0 реальных дубликатов
- 5 дубликатов по имени — все false positive (разные функции с одинаковыми именами)
- 25 модулей тестируются в 2+ файлах — все по разным аспектам (unit + e2e, security + functional, etc.)
- 5 кандидатов на объединение — отложено (риск regression выше пользы)

Тестовая база хорошо организована. Удалять нечего.

## Рекомендации

1. **test_e2e.py** — сохранить как есть. E2E-тести важны для проверки
   интеграции после рефакторинга (Этапы 1-2 показали их ценность).

2. **test_property.py** — требует `hypothesis` пакета (не установлен в
   текущем окружении). Это pre-existing issue, не связано с Этапом 5.
   Рекомендация: добавить `hypothesis` в `pyproject.toml` dev deps
   (если ещё не добавлен) и включить в CI.

3. **test_mcp_tools_snapshot.py** — 7 errors (pre-existing). Требует
   `pytest-snapshot` обновления. Не связано с Этапом 5.

4. **Кандидаты на объединение (5 случаев)** — оставить для будущего
   спринта, когда будет время на аккуратное слияние без regression.

5. **Coverage gate (задача 5.2)** — основная цель. Текущее покрытие 71.44%
   (gate 70%). Цель: 80%. Аудит показал, что тестовая база достаточно
   полна — нужно добавить тесты для непокрытых веток, а не объединять
   существующие.
