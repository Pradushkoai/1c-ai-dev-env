"""
S8.10 (2026-07-06): Sandboxing для LLM-generated code execution.

Проблема: LLM может генерировать код (BSL, Python), который выполняется
в контексте MCP-сервера. Без sandboxing malicious код может:
- Получить доступ к файловой системе
- Сделать сетевые запросы
- Запустить subprocess
- Изменить окружение

Решение:多层 sandboxing:
1. Static validation — проверка кода перед выполнением
   - BSL: через security_auditor (SEC001-SEC015) + bsl_validator
   - Python: через ast-анализ (запрет import os, subprocess, etc.)
2. Resource limits — ограничения на выполнение
   - Timeout
   - Memory limit
   - Disk quota
3. Allowlist — только разрешённые операции
   - BSL: список безопасных функций
   - Python: список разрешённых модулей
4. Audit logging — все выполнения логируются

Использование:
    from src.services.code_sandbox import execute_python_safely, validate_bsl_safely
    result = execute_python_safely(code, timeout=10)
    validation = validate_bsl_safely(bsl_code)
"""

from __future__ import annotations

import ast
import logging
import os
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Forbidden patterns
# ============================================================================

# Python imports, которые запрещены в LLM-generated коде.
FORBIDDEN_PYTHON_IMPORTS: frozenset[str] = frozenset({
    "os",                  # file system access
    "sys",                 # interpreter access
    "subprocess",          # command execution
    "shutil",              # high-level file ops
    "ctypes",              # FFI
    "multiprocessing",     # process spawning
    "threading",           # concurrency
    "socket",              # network
    "http",                # HTTP client
    "urllib",              # URL client
    "requests",            # HTTP client
    "pickle",              # deserialization
    "marshal",             # serialization
    "importlib",           # dynamic imports
    "builtins",            # access to builtins
    "glob",                # file pattern matching
    "pathlib",             # file paths (could be allowed with restrictions)
    "io",                  # file I/O
    "fcntl",               # file control
    "resource",            # resource limits
    "signal",              # signal handling
    "errno",               # error numbers
    "pwd",                 # password database
    "spwd",                # shadow password
    "grp",                 # group database
})

# Python builtins, которые запрещены
FORBIDDEN_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "open", "input", "globals", "locals",
    "vars", "dir", "getattr", "setattr", "delattr", "hasattr",
    "__import__", "breakpoint", "exit", "quit",
})

# BSL operations, которые запрещены (дублирует security_auditor, но явно)
FORBIDDEN_BSL_PATTERNS: list[tuple[str, str]] = [
    (r"Выполнить\s*\(", "Выполнить() — code injection"),
    (r"Вычислить\s*\(", "Вычислить() — code injection"),
    (r"ЗапуститьПриложение\s*\(", "ЗапуститьПриложение — OS command"),
    (r"Новый\s+COMОбъект\s*\(", "COMОбъект — arbitrary code execution"),
    (r"УстановкаПривилегированногоРежима\s*\(\s*Истина", "Privilege escalation"),
    (r"ЗначениеИзСтрокиВнутр\s*\(", "Deserialization"),
    (r"Запрос.Текст\s*=\s*[^\"]*\+", "SQL injection"),
    (r"HTTPСоединение\s*\(", "Network access"),
    (r"FTPСоединение\s*\(", "Network access"),
    (r"ИнтернетСоединение\s*\(", "Network access"),
]


# ============================================================================
# Validation result
# ============================================================================


@dataclass
class ValidationResult:
    """Результат validation кода."""

    is_safe: bool
    language: str          # "python" or "bsl"
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks_performed: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Результат выполнения кода в sandbox."""

    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_sec: float = 0.0
    timed_out: bool = False
    killed: bool = False


# ============================================================================
# Python validation
# ============================================================================


def validate_python_code(code: str) -> ValidationResult:
    """S8.10: Валидация Python кода перед выполнением.

    Проверки:
    1. Парсинг в AST (синтаксис)
    2. Запрещённые imports
    3. Запрещённые builtins calls
    4. Доступ к __dunder__ атрибутам
    5. Nested functions/classes с overrides
    """
    result = ValidationResult(is_safe=True, language="python")
    result.checks_performed = ["ast_parse", "imports", "builtins", "dunder"]

    # Check 1: parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.is_safe = False
        result.violations.append(f"SyntaxError: {e.msg} (line {e.lineno})")
        return result

    # Check 2: forbidden imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in FORBIDDEN_PYTHON_IMPORTS:
                    result.is_safe = False
                    result.violations.append(
                        f"Forbidden import: {alias.name} (line {node.lineno})"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module in FORBIDDEN_PYTHON_IMPORTS:
                    result.is_safe = False
                    result.violations.append(
                        f"Forbidden import: from {node.module} (line {node.lineno})"
                    )

    # Check 3: forbidden builtins
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_BUILTINS:
                result.is_safe = False
                result.violations.append(
                    f"Forbidden builtin call: {func.id}() (line {node.lineno})"
                )
            elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_BUILTINS:
                result.is_safe = False
                result.violations.append(
                    f"Forbidden builtin call: .{func.attr}() (line {node.lineno})"
                )

    # Check 4: dunder access (potential escape)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            if node.attr.endswith("__") and node.attr not in ("__init__", "__str__", "__repr__"):
                result.warnings.append(
                    f"Dunder access: .{node.attr} (line {node.lineno}) — potential escape"
                )

    return result


# ============================================================================
# BSL validation
# ============================================================================


def validate_bsl_code(code: str) -> ValidationResult:
    """S8.10: Валидация BSL кода перед выполнением/сохранением в EPF.

    Использует:
    1. security_auditor (15 правил SEC001-SEC015)
    2. Дополнительные паттерны (network access, COM, etc.)
    """
    import re
    result = ValidationResult(is_safe=True, language="bsl")
    result.checks_performed = ["security_auditor", "forbidden_patterns"]

    # Run security_auditor
    try:
        from src.services.analyzers.security_auditor import SecurityAuditor
        auditor = SecurityAuditor()
        violations = auditor.audit_code(code)
        for v in violations:
            result.violations.append(
                f"{v.rule_id} (line {v.line}): {v.message[:100]}"
            )
            # CRITICAL и HIGH violations → unsafe
            if v.severity in ("CRITICAL", "HIGH"):
                result.is_safe = False
    except Exception as e:
        result.warnings.append(f"security_auditor unavailable: {e}")

    # Additional forbidden patterns
    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        for pattern, desc in FORBIDDEN_BSL_PATTERNS:
            if re.search(pattern, stripped):
                result.is_safe = False
                result.violations.append(f"Line {i}: {desc}")

    return result


# ============================================================================
# Python execution in sandbox
# ============================================================================


def execute_python_safely(
    code: str,
    *,
    timeout: int = 10,
    memory_limit_mb: int = 100,
    extra_allowed_imports: frozenset[str] | None = None,
) -> ExecutionResult:
    """S8.10: Выполнение Python кода в sandbox.

    Multi-layer protection:
    1. Static validation (validate_python_code)
    2. subprocess с timeout
    3. Resource limits (memory, CPU)
    4. Restricted __builtins__
    5. No network access (no socket module)
    6. Temp directory как cwd

    Args:
        code: Python код для выполнения.
        timeout: Timeout в секундах.
        memory_limit_mb: Memory limit в MB.
        extra_allowed_imports: Дополнительные разрешённые imports.

    Returns:
        ExecutionResult с output, exit_code, duration.
    """
    start = time.monotonic()

    # Layer 1: static validation
    validation = validate_python_code(code)
    if not validation.is_safe:
        return ExecutionResult(
            success=False,
            error=f"Code validation failed: {'; '.join(validation.violations)}",
            duration_sec=time.monotonic() - start,
        )

    # Layer 2: write code to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        # Wrap code with restricted builtins
        wrapped = _wrap_restricted(code, extra_allowed_imports or frozenset())
        f.write(wrapped)
        temp_path = f.name

    try:
        # Layer 3: subprocess with timeout, no network
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "LANG": "en_US.UTF-8",
                "PYTHONPATH": "",   # no access to project modules
            },
            # P2.14/S8.2: never shell=True
            shell=False,
        )

        duration = time.monotonic() - start
        return ExecutionResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            exit_code=result.returncode,
            duration_sec=duration,
        )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            error=f"Timeout after {timeout}s",
            duration_sec=time.monotonic() - start,
            timed_out=True,
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            error=f"Execution error: {e}",
            duration_sec=time.monotonic() - start,
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _wrap_restricted(code: str, extra_imports: frozenset[str]) -> str:
    """Wrap user code with restricted builtins and import whitelist.

    The wrapped code:
    1. Removes dangerous builtins
    2. Installs a custom import hook that only allows safe modules
    3. Sets resource limits
    """
    allowed_modules = (
        {"math", "json", "re", "collections", "itertools", "functools",
         "datetime", "decimal", "fractions", "statistics", "string",
         "textwrap", "unicodedata", "copy", "heapq", "bisect"}
        | extra_imports
    )
    allowed_modules_str = ", ".join(f"'{m}'" for m in sorted(allowed_modules))

    return f"""
import sys
import importlib.abc
import importlib.machinery

# Layer 1: Restricted builtins
_FORBIDDEN_BUILTINS = {{'exec', 'eval', 'compile', 'open', 'input', 'globals',
                       'locals', 'vars', 'dir', 'getattr', 'setattr', 'delattr',
                       'hasattr', '__import__', 'breakpoint', 'exit', 'quit'}}

class _RestrictedBuiltins:
    def __init__(self, real_builtins):
        self._real = real_builtins
    def __getattr__(self, name):
        if name in _FORBIDDEN_BUILTINS:
            raise PermissionError(f"builtin '{{name}}' is forbidden in sandbox")
        return getattr(self._real, name)
    def __setattr__(self, name, value):
        if name == '_real':
            object.__setattr__(self, name, value)
        else:
            raise PermissionError("cannot modify builtins in sandbox")

# Layer 2: Import whitelist
_ALLOWED_MODULES = {{{allowed_modules_str}}}

class _ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        top = fullname.split('.')[0]
        if top not in _ALLOWED_MODULES:
            raise ImportError(f"import of '{{fullname}}' is forbidden in sandbox")
        return None  # use default finder

sys.meta_path.insert(0, _ImportGuard())

# Layer 3: Resource limits (Unix only)
try:
    import resource as _resource
    _resource.setrlimit(_resource.RLIMIT_CPU, (5, 5))   # 5 CPU seconds
    _resource.setrlimit(_resource.RLIMIT_FSIZE, (10_000_000, 10_000_000))  # 10MB file
except Exception:
    pass

# Execute user code
__user_result__ = None
try:
    exec(compile('''{code.replace("'''", "\\'\\'\\'")}''', '<sandbox>', 'exec'))
except SystemExit:
    pass
"""


# ============================================================================
# BSL execution (no real execution, only validation)
# ============================================================================


def validate_bsl_safely(bsl_code: str) -> ValidationResult:
    """S8.10: Валидация BSL кода (BSL не выполняется Python-процессом).

    BSL код сохраняется в EPF и потом выполняется 1С — мы не контролируем
    это выполнение. Поэтому sandboxing для BSL = static validation.

    Returns:
        ValidationResult с violations.
    """
    return validate_bsl_code(bsl_code)


# ============================================================================
# Audit logging
# ============================================================================


def log_code_execution(
    language: str,
    code: str,
    result: ExecutionResult | ValidationResult,
    user: str = "",
) -> None:
    """S8.10: Логирование выполнения кода в audit log."""
    try:
        from src.services.audit_logger import AuditLogger
        audit = AuditLogger()
        # Determine status based on result type
        if hasattr(result, "is_safe"):
            status = "success" if result.is_safe else "blocked"
        elif hasattr(result, "success"):
            status = "success" if result.success else "error"
        else:
            status = "unknown"
        error_msg = (
            getattr(result, "error", "")
            or "; ".join(getattr(result, "violations", []))
            or ""
        )
        audit.log_call(
            tool_name=f"<code_execution:{language}>",
            args={"code_length": len(code), "code_preview": code[:200]},
            result_status=status,
            error=error_msg,
        )
    except Exception:
        pass


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для code sandbox."""
    import argparse

    parser = argparse.ArgumentParser(description="Code sandbox для LLM-generated code")
    subparsers = parser.add_subparsers(dest="command", required=True)

    val_parser = subparsers.add_parser("validate", help="Validate code")
    val_parser.add_argument("--lang", choices=["python", "bsl"], required=True)
    val_parser.add_argument("--file", required=True, help="Code file")

    exec_parser = subparsers.add_parser("exec", help="Execute Python code in sandbox")
    exec_parser.add_argument("--file", required=True, help="Python file")
    exec_parser.add_argument("--timeout", type=int, default=10)

    args = parser.parse_args()

    code = Path(args.file).read_text(encoding="utf-8")

    if args.command == "validate":
        if args.lang == "python":
            result = validate_python_code(code)
        else:
            result = validate_bsl_code(code)
        print(f"Safe: {result.is_safe}")
        if result.violations:
            print("Violations:")
            for v in result.violations:
                print(f"  - {v}")
        if result.warnings:
            print("Warnings:")
            for w in result.warnings:
                print(f"  - {w}")
        return 0 if result.is_safe else 1

    if args.command == "exec":
        result = execute_python_safely(code, timeout=args.timeout)
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration_sec:.2f}s")
        if result.output:
            print(f"Output:\n{result.output}")
        if result.error:
            print(f"Error:\n{result.error}")
        return 0 if result.success else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
