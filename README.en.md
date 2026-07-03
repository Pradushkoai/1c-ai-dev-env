# 1C AI Development Environment

> **Universal 1C development environment with AI assistant**: parsing and analysis of 1C metadata from XML exports, 45 MCP tools for IDE/LLM, 11 BSL code analyzers (150+ rules), JSON DSL → XML compilers (5 object types), CFE extension support, metadata dependency graph, SKD tracing, generation of processors/reports/templates/roles, **creating .epf external processors from scratch without 1C**, SARIF for GitHub Code Scanning.

[![Version](https://img.shields.io/badge/version-5.4.0-brightgreen.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)
[![Tests](https://img.shields.io/badge/tests-passing-success.svg)](#tests)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-45-blue.svg)](#connecting-to-ide--llm-via-mcp)
[![CLI Commands](https://img.shields.io/badge/CLI%20commands-19-success.svg)](#cli-commands)

**Languages:** [Русский](README.md) | **English**

---

## 🤖 AI agents: read AGENTS.md

**If you are an AI agent (Codex, Cursor, Claude) — start with [`AGENTS.md`](AGENTS.md).**

AGENTS.md is a compact set of rules (170 lines) that you need to know before
each working session. The rules are born from real incidents, not theoretical
reasoning. Contains:

- **Agent workflow** (4 stages: rules → graph → documentation → code)
- **Infrastructure rules** (BSL LS, v8unpack, mobile application)
- **Process rules** (before EPF build, after changes, critical files)
- **Architectural rules** (DRY, locality, BSL module structure)
- **Technical rules** (processor names, list form, queries, commits)
- **Antipatterns** (8 "DO NOT" items)
- **Incident history** (5 incidents → 5 rules)

Extended description: [`docs/AGENTS_MD.md`](docs/AGENTS_MD.md).

---

## What's inside

### BSL code analysis (11 analyzers, 150+ rules)

| Component | Rules | What it checks |
|-----------|-------|----------------|
| **security_auditor** | 15 | SQL injections, Execute(), hardcoded passwords, COM, RLS, path traversal |
| **check_1c_standards** | 56 | Code style, names, line length, queries, client-server |
| **transaction_checker** | 6 | Unbalanced transactions, without Try/Catch, interactive |
| **query_analyzer** | 10 | SELECT *, LIKE %, functions in WHERE, JOIN without ON |
| **code_metrics** | 10 | LOC, cyclomatic/cognitive complexity, God Object, health score |
| **architecture_analyzer** | 12 | Dependency cycles, dead code, layering, regions |
| **form_quality_checker** | 9 | Empty/overloaded forms, buttons without commands |
| **skd_quality_checker** | 9 | SKD without parameters, empty queries, overload |
| **check_metadata_standards** | 18 | 1C metadata XML |
| **code_validator** | — | BSL/XML syntax, structure, regions |
| **BSL Language Server** | 187 | External Java analyzer (v1.0.1) |

### 1C metadata parsing

| Component | What it does |
|-----------|--------------|
| **metadata_extractor** | Unified parser for 35 object types from XML export |
| **api-reference** | BSL modules with export methods |
| **skd_parser** | SKD schema parsing + trace mode (field tracing) |
| **form_analyzer** | Full form analysis: elements, DataPath, events |
| **cf_extractor** | Own .cf parser without v8unpack |
| **call_graph** | BSL method call graph |
| **dependency_graph** | Metadata dependency graph (networkx) |

### Code generation (JSON DSL → XML)

| Compiler | What it generates | Objects |
|----------|-------------------|---------|
| **MetaCompiler** | 1C metadata | 23 types (Catalog, Document, Enum, etc.) |
| **FormCompiler** | Managed forms (Form.xml) | — |
| **SkdCompiler** | SKD schemas (DataCompositionSchema) | — |
| **MxlCompiler** | MXL templates (print forms) | — |
| **RoleCompiler** | 1C roles (Rights.xml) | — |

### CFE extension support

| Operation | What it does |
|-----------|--------------|
| **cfe_borrow** | Object borrowing (ObjectBelonging=Adopted) |
| **cfe_patch_method** | Generate &Before/&After/&ModificationAndControl |
| **cfe_diff** | Extension analysis: what's borrowed, what's intercepted |

---

## Quick start

### Installation

```bash
# 1. Clone
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# 2. Install Python package
pip install -e ".[dev,mcp]"

# 3. Install BSL LS (optional, for analyze_bsl)
bash install.sh --target /path/to/project

# 4. Verify environment
1c-ai validate
```

### Installation via Docker

```bash
docker compose build cli
docker compose run --rm cli validate
docker compose up mcp-server
docker compose run --rm tests
```

### Add 1C configuration

```bash
# From Configurator ZIP export
1c-ai config add --name ut11 --zip ut11.zip --title "UT 11"
1c-ai config build --name ut11

# → Builds 5 indexes:
#   - unified-metadata-index.json (35 object types)
#   - api-reference.json (BSL modules + methods)
#   - skd-index.json (SKD schemas)
#   - form-index.json (forms + elements)
#   - dependency-graph.json (dependency graph)
```

---

## CLI commands

```bash
# Configuration management
1c-ai config list                          # list configurations
1c-ai config add --name X --zip X.zip      # add from ZIP
1c-ai config build --name X                # build indexes

# BSL code analysis
1c-ai standards module.bsl                 # 56 1C standard rules
1c-ai bsl analyze module.bsl               # BSL LS (187 diagnostics)
1c-ai solve check module.bsl --level full  # all 7 analyzers

# Search
1c-ai search "find element by code"        # BM25/hybrid search
1c-ai search-code "create order" --config ut11  # search in config code

# JSON DSL → XML compilers
1c-ai dsl meta --json-file catalog.json --output-dir /path/to/config
1c-ai dsl form --json-file form.json --output-path Form.xml

# External processors (.epf)
1c-ai epf-factory create --name "MyProcessor" --bsl module.bsl --output MyProcessor.epf
```

---

## Connecting to IDE / LLM via MCP

The project includes an MCP server with 45 tools for Cursor / Claude Desktop / VS Code / JetBrains.

### Setup

**Cursor / Claude Desktop** — add to `mcp.json`:

```json
{
  "mcpServers": {
    "1c-ai": {
      "command": "1c-ai-mcp",
      "args": []
    }
  }
}
```

**VS Code / JetBrains** — via stdio:

```bash
1c-ai mcp serve
```

### MCP tool categories

| Category | Tools | Purpose |
|----------|-------|---------|
| **Configurations** | list_configs, data_status | Configuration management |
| **Search** | search_1c_methods, search_code | BM25/hybrid search |
| **BSL analysis** | analyze_bsl, check_standards, audit_security, etc. | 11 analyzers |
| **Metadata** | get_object_structure, get_skd_schema, get_form_structure, etc. | Parsing and structure |
| **Quality** | check_form_quality, check_skd_quality, diff_configs | Quality checks |
| **Generation** | generate_processing, generate_report, build_epf, etc. | Code generation |
| **Context** | solve_context, solve_check | TaskProcessor (7 sources + 7 analyzers) |
| **Knowledge base** | get_knowledge | Patterns, antipatterns |
| **DSL compilers** | dsl_compile_meta, dsl_compile_form, etc. | JSON → XML |
| **CFE** | cfe_borrow, cfe_patch_method, cfe_diff | Extensions |
| **SKD** | skd_trace | Field tracing |
| **Dependency graph** | build_dependency_graph, dependency_query | networkx graph |
| **OpenSpec** | openspec_proposal, openspec_list, etc. | SDD |
| **Inspect** | inspect | Unified object analysis |

---

## Testing

```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=70

# Property-based tests (hypothesis)
python -m pytest tests/test_property.py -v --hypothesis-show-statistics

# Snapshot tests (update if needed)
python -m pytest tests/test_mcp_tools_snapshot.py --snapshot-update
```

---

## CI/CD

| Workflow | What it does |
|----------|--------------|
| `ci.yml` — lint | ruff check + format + mypy (strict, blocking) |
| `ci.yml` — version-check | Version consistency check |
| `ci.yml` — test | pytest (unit + integration + e2e + benchmarks) |
| `ci.yml` — coverage | pytest --cov=src --cov-fail-under=70 |
| `ci.yml` — complexity | radon cc (blocking, baseline 14) |
| `code-scanning.yml` | SARIF → GitHub Code Scanning |
| `dependency-hygiene.yml` | pip-audit + safety + license check (weekly) |
| `mutation-testing.yml` | mutmut weekly (non-blocking) |
| `backup-mirror.yml` | GitLab mirror + git bundle backup |

---

## Documentation

| Section | Where |
|---------|-------|
| XML specifications | `docs/1c-xml-specs/` — 19 files, 13K lines |
| Architecture | `docs/ARCHITECTURE.md` |
| API | `docs/API.md` |
| MCP integration | `docs/MCP_INTEGRATION.md` |
| Vector search | `docs/VECTOR_SEARCH.md` |
| Metrics | `docs/METRICS.md` |
| Snapshot testing | `docs/SNAPSHOT_TESTING.md` |
| Backup strategy | `docs/BACKUP_STRATEGY.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |
| Knowledge base | `knowledge_base/` — patterns, antipatterns, best practices |
| Changelog | `CHANGELOG.md` |

---

## Technologies

| Component | Technology |
|-----------|------------|
| Main language | Python 3.10+ |
| BSL Language Server | Java 17+ (v1.0.1, 187 diagnostics) |
| MCP SDK | Python mcp |
| Dependency graph | networkx |
| Structured logging | structlog |
| Linting | ruff + mypy (strict) |
| Testing | pytest + hypothesis + pytest-benchmark + pytest-snapshot |
| Containerization | Docker (multi-stage) + docker-compose |
| CI/CD | GitHub Actions (complexity + coverage + mypy + SARIF + backup) |
| Metrics | prometheus-client (optional, extras [metrics]) |
| Vector search | fastembed + Qdrant (optional, extras [rag]) |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgments

- [1c-ai-development-kit](https://github.com/Arman-Kudaibergenov/1c-ai-development-kit) — for JSON DSL specifications and 1C XML format documentation
- [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) — for BSL static analysis
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) — for Model Context Protocol
