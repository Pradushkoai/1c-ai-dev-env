"""
S8.10 (2026-07-06): Тесты для code sandbox.

Проверяет:
- validate_python_code: forbidden imports, builtins, dunder
- validate_bsl_code: security_auditor integration + patterns
- execute_python_safely: timeout, validation, output capture
- Audit logging
- CLI
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.code_sandbox import (
    FORBIDDEN_BSL_PATTERNS,
    FORBIDDEN_BUILTINS,
    FORBIDDEN_PYTHON_IMPORTS,
    ExecutionResult,
    ValidationResult,
    execute_python_safely,
    validate_bsl_code,
    validate_bsl_safely,
    validate_python_code,
)


# ============================================================================
# Python validation
# ============================================================================


class TestValidatePythonCode:
    """Тесты validate_python_code."""

    def test_safe_code_passes(self) -> None:
        code = "x = 1 + 2\nprint(x)"
        result = validate_python_code(code)
        assert result.is_safe
        assert result.language == "python"
        assert not result.violations

    def test_empty_code_passes(self) -> None:
        result = validate_python_code("")
        assert result.is_safe

    @pytest.mark.parametrize("module", [
        "os", "sys", "subprocess", "shutil", "ctypes",
        "socket", "http", "urllib", "requests",
        "pickle", "marshal", "importlib",
    ])
    def test_forbidden_imports_blocked(self, module: str) -> None:
        code = f"import {module}"
        result = validate_python_code(code)
        assert not result.is_safe
        assert any(module in v for v in result.violations)

    def test_forbidden_from_import_blocked(self) -> None:
        code = "from os import path"
        result = validate_python_code(code)
        assert not result.is_safe

    @pytest.mark.parametrize("builtin", ["exec", "eval", "open", "input", "globals"])
    def test_forbidden_builtins_blocked(self, builtin: str) -> None:
        code = f"result = {builtin}('test')"
        result = validate_python_code(code)
        assert not result.is_safe

    def test_syntax_error_blocked(self) -> None:
        code = "def f(:\n  pass"
        result = validate_python_code(code)
        assert not result.is_safe
        assert any("SyntaxError" in v for v in result.violations)

    def test_safe_modules_allowed(self) -> None:
        code = "import math\nimport json\nimport re\nprint(math.pi)"
        result = validate_python_code(code)
        assert result.is_safe

    def test_dunder_access_warns(self) -> None:
        code = "x = obj.__class__"
        result = validate_python_code(code)
        # Dunder access is warning, not violation
        assert result.is_safe   # still safe, just warned
        assert any("__class__" in w for w in result.warnings)

    def test_checks_performed(self) -> None:
        result = validate_python_code("x = 1")
        assert "ast_parse" in result.checks_performed
        assert "imports" in result.checks_performed
        assert "builtins" in result.checks_performed


# ============================================================================
# BSL validation
# ============================================================================


class TestValidateBslCode:
    """Тесты validate_bsl_code."""

    def test_safe_bsl_passes(self) -> None:
        code = "Процедура Тест()\nСообщить(\"hi\");\nКонецПроцедуры"
        result = validate_bsl_code(code)
        assert result.is_safe
        assert result.language == "bsl"

    def test_vypolnit_blocked(self) -> None:
        code = "Выполнить(ДинамическийКод);"
        result = validate_bsl_code(code)
        assert not result.is_safe

    def test_vychislit_blocked(self) -> None:
        code = "Результат = Вычислить(Выражение);"
        result = validate_bsl_code(code)
        assert not result.is_safe

    def test_zapustit_prilozhenie_blocked(self) -> None:
        code = "ЗапуститьПриложение(Путь);"
        result = validate_bsl_code(code)
        assert not result.is_safe

    def test_com_object_blocked(self) -> None:
        code = 'Shell = Новый COMОбъект("WScript.Shell");'
        result = validate_bsl_code(code)
        assert not result.is_safe

    def test_sql_injection_blocked(self) -> None:
        code = 'Запрос.Текст = "ВЫБРАТЬ * ИЗ " + Таблица;'
        result = validate_bsl_code(code)
        assert not result.is_safe

    def test_comment_ignored(self) -> None:
        code = "// Выполнить(Код) — закомментировано"
        result = validate_bsl_code(code)
        # Comments should not trigger violations
        assert result.is_safe

    def test_validate_bsl_safely_returns_result(self) -> None:
        result = validate_bsl_safely("Сообщить(\"test\");")
        assert isinstance(result, ValidationResult)
        assert result.language == "bsl"


# ============================================================================
# Python execution in sandbox
# ============================================================================


class TestExecutePythonSafely:
    """Тесты execute_python_safely."""

    def test_simple_print_executes(self) -> None:
        result = execute_python_safely("print('hello sandbox')", timeout=5)
        assert result.success
        assert "hello sandbox" in result.output

    def test_math_executes(self) -> None:
        code = "import math\nprint(math.pi)"
        result = execute_python_safely(code, timeout=5)
        assert result.success
        assert "3.14" in result.output

    def test_forbidden_code_blocked(self) -> None:
        code = "import os\nos.listdir('/')"
        result = execute_python_safely(code, timeout=5)
        assert not result.success
        # Validation should block it before execution
        assert "validation" in result.error.lower() or "forbidden" in result.error.lower()

    def test_timeout_enforced(self) -> None:
        # Infinite loop with allowed operations
        code = "while True:\n  pass"
        result = execute_python_safely(code, timeout=3)
        assert not result.success
        assert result.timed_out

    def test_output_captured(self) -> None:
        code = "print('line1')\nprint('line2')"
        result = execute_python_safely(code, timeout=5)
        assert "line1" in result.output
        assert "line2" in result.output

    def test_error_captured(self) -> None:
        code = "raise ValueError('test error')"
        result = execute_python_safely(code, timeout=5)
        assert not result.success
        assert "test error" in result.error

    def test_duration_recorded(self) -> None:
        result = execute_python_safely("print('x')", timeout=5)
        assert result.duration_sec > 0
        assert result.duration_sec < 5

    def test_exec_builtin_blocked(self) -> None:
        code = "exec('print(1)')"
        result = execute_python_safely(code, timeout=5)
        assert not result.success

    def test_eval_builtin_blocked(self) -> None:
        code = "x = eval('1+1')"
        result = execute_python_safely(code, timeout=5)
        assert not result.success

    def test_open_blocked(self) -> None:
        code = "f = open('/etc/passwd')\nprint(f.read())"
        result = execute_python_safely(code, timeout=5)
        assert not result.success


# ============================================================================
# Configuration
# ============================================================================


class TestSandboxConfig:
    def test_forbidden_python_imports_listed(self) -> None:
        assert "os" in FORBIDDEN_PYTHON_IMPORTS
        assert "subprocess" in FORBIDDEN_PYTHON_IMPORTS
        assert "socket" in FORBIDDEN_PYTHON_IMPORTS
        assert "pickle" in FORBIDDEN_PYTHON_IMPORTS

    def test_forbidden_builtins_listed(self) -> None:
        assert "exec" in FORBIDDEN_BUILTINS
        assert "eval" in FORBIDDEN_BUILTINS
        assert "open" in FORBIDDEN_BUILTINS
        assert "__import__" in FORBIDDEN_BUILTINS

    def test_forbidden_bsl_patterns_listed(self) -> None:
        assert len(FORBIDDEN_BSL_PATTERNS) >= 5
        patterns = [p for p, _ in FORBIDDEN_BSL_PATTERNS]
        assert any("Выполнить" in p for p in patterns)
        assert any("Вычислить" in p for p in patterns)

    def test_code_sandbox_module_exists(self) -> None:
        from src.services.code_sandbox import execute_python_safely
        assert callable(execute_python_safely)


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_python_code(self) -> None:
        result = execute_python_safely("", timeout=5)
        assert result.success

    def test_very_long_code_handled(self) -> None:
        # 10K lines of safe code
        code = "\n".join(["x = 1"] * 10_000)
        result = validate_python_code(code)
        assert result.is_safe

    def test_unicode_in_code(self) -> None:
        code = "x = 'Привет мир 1С'"
        result = validate_python_code(code)
        assert result.is_safe

    def test_nested_forbidden_import(self) -> None:
        # from package.subpackage import module — top-level package checked
        code = "from os.path import join"
        result = validate_python_code(code)
        assert not result.is_safe
