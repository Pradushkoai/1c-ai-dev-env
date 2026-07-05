"""
tools.py — Re-export CLI команд из декомпозированных модулей.

F1.6 (2026-07-05): вынесено 7 команд из tools.py (531 LOC) в отдельные файлы.
Этот файл сохраняет backward compat: from cli_commands.tools import cmd_dsl, etc.

Оригинальные 531 LOC → 7 файлов:
  - epf_factory_cmd.py (76 LOC)
  - dsl_cmd.py (110 LOC)
  - cfe_cmd.py (66 LOC)
  - skd_trace_cmd.py (35 LOC)
  - depgraph_cmd.py (105 LOC)
  - openspec_cmd.py (68 LOC)
  - session_cmd.py (62 LOC)
"""

from __future__ import annotations

# F1.6: Re-export для backward compat
from .cfe_cmd import cmd_cfe
from .depgraph_cmd import cmd_depgraph
from .dsl_cmd import cmd_dsl
from .epf_factory_cmd import cmd_epf_factory
from .openspec_cmd import cmd_openspec
from .session_cmd import cmd_session
from .skd_trace_cmd import cmd_skd_trace

__all__ = [
    "cmd_cfe",
    "cmd_depgraph",
    "cmd_dsl",
    "cmd_epf_factory",
    "cmd_openspec",
    "cmd_session",
    "cmd_skd_trace",
]
