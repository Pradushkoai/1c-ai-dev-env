# C4 Architecture Diagram — 1c-ai-dev-env

**Уровень:** Context + Container  
**Дата:** July 2026 (Phase 4.1 of refactoring)  
**Стандарт:** C4 model (Simon Brown)

---

## Level 1: Context

Внешние системы и пользователи, взаимодействующие с 1c-ai-dev-env.

```
                          ┌──────────────────────┐
                          │   1С:Предприятие 8   │
                          │   (источник .cf/.cfe)│
                          └──────────┬───────────┘
                                     │
                                     │ Выгрузка в файлы
                                     │ (XML + BSL)
                                     ▼
┌─────────────────┐         ┌──────────────────────┐         ┌──────────────────┐
│                 │         │                      │         │                  │
│   Разработчик   │◄───────►│   1c-ai-dev-env      │◄───────►│  BSL Language    │
│   (1С dev)      │  MCP    │   (MCP server)       │  subprocess│  Server (Java)│
│                 │         │                      │         │                  │
└─────────────────┘         └──────────┬───────────┘         └──────────────────┘
                                       │
                                       │ IDE integration
                                       ▼
                            ┌──────────────────────┐
                            │  Cursor / Claude /   │
                            │  VS Code / JetBrains │
                            │  (MCP clients)       │
                            └──────────────────────┘
```

### Внешние системы

| Система | Тип взаимодействия | Назначение |
|---------|-------------------|------------|
| **1С:Предприятие 8** | Файловая система (.cf/.cfe выгрузки) | Источник конфигураций для анализа |
| **Cursor / Claude / VS Code** | MCP protocol (stdio) | LLM-агенты вызывают 46 MCP tools |
| **BSL Language Server** | subprocess + WebSocket | 187 диагностик BSL кода |
| **tree-sitter-bsl** | Python library (опционально) | AST парсинг BSL |
| **v8unpack** | Python library (через git) | Распаковка .cf/.cfe контейнеров |
| **Ollama** (опционально) | HTTP API | Векторный поиск для RAG |

---

## Level 2: Container

Внутренние модули 1c-ai-dev-env. После Phase 2 refactoring — 3-слойная архитектура.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          src/core/  (ЯДРО)                              │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  core/metadata/ │  │  core/search/   │  │  core/analyzers/        │ │
│  │                 │  │                 │  │                         │ │
│  │ • XML parser    │  │ • BM25 index    │  │ • BSL tree-sitter AST   │ │
│  │ • Metadata      │  │ • Hybrid search │  │ • Security auditor      │ │
│  │   extractor     │  │ • CamelCase     │  │ • Standards checker     │ │
│  │ • Type resolver │  │   tokenizer     │  │ • Static query validator│ │
│  │ • Standard      │  │ • Trigrams      │  │ • Transaction checker   │ │
│  │   attributes    │  │                 │  │ • Architecture analyzer │ │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────────┘ │
│           │                    │                      │                │
│           └────────────────────┼──────────────────────┘                │
│                                ▼                                       │
│                    ┌───────────────────────┐                           │
│                    │   core/mcp/           │                           │
│                    │                       │                           │
│                    │ • MCP server          │                           │
│                    │ • 46 tool definitions │                           │
│                    │ • 8 handler modules   │                           │
│                    │ • Tool dispatcher     │                           │
│                    └───────────┬───────────┘                           │
└────────────────────────────────┼───────────────────────────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
┌─────────────────────────────┐   ┌─────────────────────────────────────┐
│      src/adapters/          │   │         src/services/               │
│  (Адаптеры внешних зав-ей)  │   │       (Периферия, плагины)          │
│                             │   │                                     │
│  ┌─────────────────────┐    │   │  ┌──────────────┐ ┌──────────────┐ │
│  │ bsl_ls.py           │    │   │  │ epf_factory/ │ │ cfe/         │ │
│  │ (BSL LS Java wrap)  │    │   │  │ (.epf create)│ │ (extensions) │ │
│  └─────────────────────┘    │   │  └──────────────┘ └──────────────┘ │
│  ┌─────────────────────┐    │   │  ┌──────────────┐ ┌──────────────┐ │
│  │ tree_sitter.py      │    │   │  │ dsl/         │ │ rag/         │ │
│  │ (AST parser)        │    │   │  │ (5 compilers)│ │ (Ollama)     │ │
│  └─────────────────────┘    │   │  └──────────────┘ └──────────────┘ │
│  ┌─────────────────────┐    │   │  ┌──────────────┐ ┌──────────────┐ │
│  │ v8unpack.py         │    │   │  │ openspec/    │ │ knowledge/   │ │
│  │ (.cf unpack)        │    │   │  │ (spec-driven)│ │ (patterns)   │ │
│  └─────────────────────┘    │   │  └──────────────┘ └──────────────┘ │
└─────────────────────────────┘   └─────────────────────────────────────┘
```

### Зависимости между слоями

| Слой | Зависит от | Не зависит от |
|------|------------|---------------|
| `core/` | `adapters/` (через Protocol), `services/` (через re-export) | IDE, MCP clients |
| `services/` | `core/`, `adapters/` | IDE, MCP clients |
| `adapters/` | внешние библиотеки (tree-sitter, v8unpack, BSL LS) | `core/`, `services/` |

### Protocol-контракты (Phase 2)

Каждый слой имеет явные interface через `typing.Protocol`:

| Слой | Protocol | Реализации |
|------|----------|------------|
| `core/metadata/` | `MetadataParser`, `MetadataExtractorProtocol`, `TypeResolver` | `UniversalObjectParser`, `MetadataExtractor` |
| `core/search/` | `Searcher`, `Tokenizer` | `BM25Index`, `HybridSearcher`, `CamelCaseTokenizer` |
| `core/analyzers/` | `BslAnalyzer`, `BslParser`, `QueryValidator` | `AstAnalyzer`, `SecurityAuditor`, `BslTreeSitterParser`, `StaticQueryValidator` |
| `core/mcp/` | `McpTool`, `McpServer` | `create_mcp_server()`, 46 tools |
| `adapters/` | `BslLsAdapter`, `V8UnpackAdapter`, `TreeSitterAdapter` | `BSLAnalyzer`, `CFExtractor`, `BslTreeSitterParser` |

---

## Level 3: Component (ключевые модули)

### core/mcp/ — MCP server

```
core/mcp/
├── server.py              # create_mcp_server(), run_mcp_server()
├── tools/
│   └── tool_definitions.py # 46 types.Tool + generator for descriptions
└── handlers/              # 8 файлов + 2 domain aggregates
    ├── __init__.py        # ALL_HANDLERS registry
    ├── config_search.py   # list_configs, search_1c_methods, search_code, call_graph
    ├── inspect_data.py    # inspect, data_status
    ├── analyzers.py       # analyze_bsl, check_standards, solve_context, solve_check
    ├── quality.py         # audit_security, get_code_metrics, validate_query_static
    ├── generate.py        # generate_processing, generate_report, build_epf
    ├── dsl_cfe.py         # dsl_compile_*, cfe_*
    ├── structure.py       # get_object_structure, get_skd_schema, get_form_structure
    ├── misc.py            # openspec_*, dependency_query
    ├── config.py          # domain aggregate (config_search + inspect_data)
    └── analyze.py         # domain aggregate (analyzers + quality)
```

### core/analyzers/ — Анализаторы

```
core/analyzers/
├── bsl_tree_sitter.py    # AST парсер (tree-sitter-bsl, Apache 2.0)
├── ast_analyzer.py       # 20 AST-правил
├── ast_analyzers_extended.py
├── security_auditor.py   # 15 правил SEC001-SEC015
├── query_analyzer.py     # 12 правил анализа запросов
├── query_parser.py       # Парсер запросов 1С (русские + английские keywords)
├── query_validator_static.py # P1.5: статическая валидация без live базы
├── transaction_checker.py
├── architecture_analyzer.py
├── code_metrics.py
├── bsl_ls_rules.py       # BSL LS wrapper (187 диагностик)
└── standards/            # 56 правил стандартов 1С
    ├── style.py
    ├── client_server.py
    ├── architecture.py
    ├── queries.py
    └── misc.py
```

### services/ — Периферия

```
services/
├── epf_factory.py        # Создание .epf без 1С
├── cfe_manager.py        # CFE: borrow, patch, diff
├── dsl_compiler.py       # 5 DSL компиляторов
├── rag_pipeline.py       # RAG с Ollama (опционально)
├── openspec_manager.py   # Specification-Driven Development
├── knowledge_base.py     # Patterns + antipatterns
├── call_graph_model.py   # Phase 3.4: модель графа
├── call_graph_parser.py  # Phase 3.4: BSL парсеры
├── call_graph_builder.py # Phase 3.4: оркестратор
└── ...                   # другие сервисы
```

---

## Data Flow (пример: analyze_bsl)

```
User (LLM agent) calls MCP tool 'analyze_bsl' with file_path='/path/module.bsl'
    │
    ▼
core/mcp/server.py:call_tool(name='analyze_bsl', arguments)
    │
    ▼
core/mcp/handlers/analyzers.py:handle_analyze_bsl(project, arguments)
    │
    ├─► adapters/bsl_ls.py: BSLAnalyzer.analyze(Path(file_path))
    │       │
    │       ▼
    │   BSL Language Server (Java subprocess)
    │       │
    │       ▼
    │   187 diagnostics (JSON)
    │
    ▼
Response: list[TextContent] with JSON {total, by_code, diagnostics}
    │
    ▼
LLM agent receives result, suggests fixes
```

## Data Flow (пример: validate_query_static — P1.5)

```
User (LLM agent) calls MCP tool 'validate_query_static' with query='ВЫБРАТЬ ...'
    │
    ▼
core/mcp/handlers/quality.py:handle_validate_query_static(project, arguments)
    │
    ├─► Load metadata index from derived/configs/<name>/unified-metadata-index.json
    │
    ├─► core/analyzers/query_validator_static.py: StaticQueryValidator.validate(query)
    │       │
    │       ├─► query_parser.py: QueryParser.parse(query) → ParsedBatch
    │       │
    │       ├─► For each table: check existence in metadata index
    │       │
    │       ├─► For each field: check existence in dimensions/resources/attributes
    │       │
    │       ├─► For virtual tables: check RegisterType (Остатки only for Balance)
    │       │
    │       └─► For aggregates: check type compatibility (СУММА expects number)
    │
    ▼
Response: {valid, total_errors, total_warnings, issues[]}
```

---

## Принципы архитектуры

1. **Слои зависят только внутрь** — `core/` не зависит от `services/`, `services/` не зависит от `adapters/` (на уровне Protocol).
2. **Protocol-контракты** — каждый слой имеет явные interface через `typing.Protocol`.
3. **Backward compat** — все старые пути импорта работают через re-export (Phase 2 strategy).
4. **Single source of truth** — `tool_definitions.py` имеет один список tools, `get_all_descriptions()` генерируется (Phase 3.3).
5. **SRP** — `call_graph` разделён на model/parser/builder (Phase 3.4).

## Что НЕ показано на диаграмме

- `scripts/` — 39 утилит (CI checks, build utilities, анализаторы). Не часть runtime, запускаются отдельно.
- `tests/` — 1595+ тестов (mutation, fuzzing, snapshot, property-based).
- `docs/` — 12 XML спецификаций, ADR (10 после Phase 4.2), knowledge base.
- `data/`, `derived/`, `runtime/` — данные пользователя (не часть кода).
