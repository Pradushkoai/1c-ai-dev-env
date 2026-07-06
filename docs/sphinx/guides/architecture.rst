Architecture
============

4-Layer Architecture
--------------------

The project uses a **4-layer architecture** with clear separation of concerns::

    ┌──────────────────────────────────────────────────┐
    │  data/          SOURCE DATA (from user)          │
    │  ├── configs/   1C configurations (unpacked)     │
    │  └── archives/  ZIP archives                     │
    ├──────────────────────────────────────────────────┤
    │  derived/       DERIVED (generated)               │
    │  ├── configs/   Indexes by configuration         │
    │  └── platform/  1C platform indexes              │
    ├──────────────────────────────────────────────────┤
    │  knowledge_base/  KNOWLEDGE BASE                 │
    │  ├── patterns/      Patterns                     │
    │  ├── antipatterns/  Antipatterns                 │
    │  └── best_practices/ Best practices              │
    ├──────────────────────────────────────────────────┤
    │  runtime/       WORK FILES                       │
    │  ├── config-registry.json  Config registry       │
    │  └── session-state.json    AI session state      │
    └──────────────────────────────────────────────────┘

OOP Layer (src/)
----------------

.. code-block:: text

    src/
    ├── models/                 Configuration as data
    │   ├── configuration.py    Configuration dataclass
    │   ├── config_registry.py  ConfigurationRegistry
    │   └── task.py             TaskContext + CheckResult + Violation
    │
    ├── services/               Business logic (22+ services)
    │   ├── path_manager.py     PathManager (4-layer architecture)
    │   ├── config_manager.py   add/build/validate/freshness
    │   ├── task_processor.py   Unified pipeline for CLI/MCP
    │   ├── dsl_compiler.py     5 JSON → XML compilers
    │   ├── cfe_manager.py      CFE extensions
    │   ├── dependency_graph.py Metadata dependency graph (networkx)
    │   ├── search_hybrid.py    Hybrid BM25 + vector search
    │   ├── metrics.py          Prometheus observability
    │   └── ...
    │
    ├── mcpserver/              MCP server
    │   ├── tools/              Tool definitions (8 categories)
    │   └── handlers/           Tool handlers
    │
    ├── mcp_server.py           MCP server (139 lines, thin wrapper)
    ├── project.py              Project orchestrator
    └── cli.py                  CLI (19 commands)

Key Principles
--------------

1. **Cross-platform** — Python, works on Linux/Mac/Windows
2. **No 1C required** — works with XML export, not 1C:Enterprise
3. **AI-agnostic** — CLI + MCP, works with any AI
4. **Unified business logic** — TaskProcessor used by both CLI and MCP
5. **Testing** — 1400+ tests + property-based (hypothesis) + benchmarks
6. **CI/CD** — complexity + coverage + mypy + SARIF + backup
7. **Structured logging** — structlog (JSON for CI, console for dev)
