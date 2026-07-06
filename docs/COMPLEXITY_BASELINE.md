# Complexity Baseline (P0.3)

> Baseline цикломатической сложности кода. Создано при стартовой реализации P0.3.
> CI gate блокирует появление новых функций с complexity > C.

## Метрики

- **radon cc** — цикломатическая сложность
- **Уровни:** A (1-5) < B (6-10) < C (11-15) < D (16-20) < E (21-25) < F (26+)
- **Budget:** функции ≤ C (15), методы ≤ B (10)
- **CI gate:** `radon cc src/ -n C` — показывает функции с complexity ≥ C

## Baseline (3 июля 2026, v5.4.0)

### Функции с complexity ≥ F (26+) — критические, требуют рефакторинга

| Файл | Функция | Complexity |
|------|---------|------------|
| cli.py | cmd_data | F (52) |

### Функции с complexity E (21-25)

| Файл | Функция | Complexity |
|------|---------|------------|
| cli_commands/solve.py | _solve_check | E (36) |
| cli_commands/solve.py | _solve_context | E (34) |
| cli_commands/inspect.py | _inspect_skd | E (39) |

### Функции с complexity D (16-20)

| Файл | Функция | Complexity |
|------|---------|------------|
| cli.py | main | D (27) |
| cli_commands/tools.py | cmd_depgraph | D (29) |
| cli_commands/tools.py | cmd_dsl | D (22) |
| cli_commands/tools.py | cmd_openspec | D (22) |
| cli_commands/tools.py | cmd_session | D (22) |
| cli_commands/inspect.py | _inspect_role | D (30) |
| cli_commands/inspect.py | _inspect_meta | D (24) |
| cli_commands/inspect.py | _inspect_subsystem | D (21) |

### Функции с complexity C (11-15) — допустимый максимум

| Файл | Функция | Complexity |
|------|---------|------------|
| metrics.py | MetricsCollector.get_stats | C (13) |
| cli_commands/search.py | cmd_call_graph | C (20) |
| cli_commands/tools.py | cmd_cfe | C (13) |
| cli_commands/config.py | cmd_config_build | C (20) |
| cli_commands/solve.py | cmd_backup | C (11) |
| cli_commands/inspect.py | _inspect_cf | C (19) |
| cli_commands/inspect.py | cmd_inspect | C (17) |
| cli_commands/inspect.py | _inspect_mxl | C (12) |
| dsl/_common.py | _make_type_element | C (14) |
| dsl/_common.py | _parse_attribute | C (11) |
| services/dependency_graph.py | DependencyGraph._scan_register_recorders | C (13) |
| services/form_elem_builder.py | _build_pattern | C (12) |
| services/form_elem_builder.py | build_form_elem | C (11) |
| services/cfe_manager.py | CfeManager._path_to_module_path | C (13) |
| services/cfe_manager.py | CfeManager.borrow_object | C (12) |
| services/cfe_manager.py | CfeManager._analyze_borrowed_object | C (12) |
| services/cfe_manager.py | CfeManager._register_in_config | C (11) |
| services/knowledge_base.py | KnowledgeBase.search | C (13) |
| services/search_bm25.py | search_bm25 | C (14) |
| services/search_bm25.py | build_index_bm25 | C (13) |
| services/epf_factory.py | EpfFactory._patch_ext_proc_json | C (17) |
| services/epf_factory.py | EpfFactory._build_epf | C (12) |
| services/epf_factory.py | validate_bsl | C (11) |
| services/search_code.py | _build_index_for_config | C (12) |
| services/openspec_manager.py | OpenSpecManager.validate | C (14) |
| services/openspec_manager.py | OpenSpecManager.create_proposal | C (12) |
| services/openspec_manager.py | OpenSpecManager.load_change | C (12) |
| services/openspec_manager.py | OpenSpecManager.list_changes | C (11) |
| services/data_package.py | DataPackage.save | C (14) |
| services/config_builder.py | ConfigBuilder.build | C (20) |

## Strategy

1. **CI gate (blocking):** `radon cc src/ -n D` — блокирует новые функции с complexity ≥ D
2. **Existing D/E/F:** технический долг, рефакторинг по мере возможности
3. **Цель v6.0:** 0 функций с complexity ≥ E, ≤ 5 функций с complexity D

## Mutation Testing (mutmut)

- **Baseline:** будет измерен после завершения P0.3 setup
- **CI:** weekly job (non-blocking), цель mutation score ≥ 60% к v6.0
- **Scope:** src/services/ (бизнес-логика)
