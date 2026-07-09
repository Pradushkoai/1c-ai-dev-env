"""
src/services/analyzers/sdbl/ — SDBL (Structured Database Language) парсер.

Phase A.0 of Query Intelligence plan: настоящий AST-парсер языка запросов 1С.

Подмодули:
- antlr/             — исходные ANTLR4 грамматики (.g4) от 1c-syntax (LGPL-3.0)
- generated/         — сгенерированный Python код из .g4 файлов

Лицензия: LGPL-3.0-or-later для .g4 и сгенерированного кода.
"""

from __future__ import annotations
