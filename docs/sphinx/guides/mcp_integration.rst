MCP Integration
================

Connecting to IDE / LLM via MCP
-------------------------------

The project includes an MCP server with 45 tools for Cursor / Claude Desktop / VS Code / JetBrains.

Setup
~~~~~

**Cursor / Claude Desktop** — add to ``mcp.json``::

    {
      "mcpServers": {
        "1c-ai": {
          "command": "1c-ai-mcp",
          "args": []
        }
      }
    }

**VS Code / JetBrains** — via stdio::

    1c-ai mcp serve

MCP Tool Categories
~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - Category
     - Count
     - Purpose
   * - Configurations
     - 2
     - list_configs, data_status
   * - Search
     - 2
     - search_1c_methods, search_code (BM25/hybrid)
   * - BSL analysis
     - 7
     - analyze_bsl, check_standards, audit_security, etc.
   * - Metadata
     - 6
     - get_object_structure, get_skd_schema, get_form_structure, etc.
   * - Quality
     - 3
     - check_form_quality, check_skd_quality, diff_configs
   * - Generation
     - 4
     - generate_processing, generate_report, build_epf, validate_generated
   * - Context
     - 2
     - solve_context, solve_check (TaskProcessor)
   * - Knowledge base
     - 1
     - get_knowledge (patterns, antipatterns)
   * - DSL compilers
     - 5
     - dsl_compile_meta, dsl_compile_form, dsl_compile_skd, dsl_compile_mxl, dsl_compile_role
   * - CFE
     - 3
     - cfe_borrow, cfe_patch_method, cfe_diff
   * - SKD + Graph
     - 3
     - skd_trace, build_dependency_graph, dependency_query
   * - OpenSpec + Inspect + EPF
     - 5
     - openspec_proposal, openspec_list, inspect, epf_factory_create, etc.

Principles
~~~~~~~~~~

- **Read-only**: MCP server only reads prepared indexes. Loading/indexing via CLI.
- **CLI = admin**: data management (add, delete, index, backup).
- **MCP = analytics**: search, verify, context gathering.
- **Any MCP client**: not tied to specific IDE.
- **Session isolation**: each MCP server launch creates new ``Project()``.
