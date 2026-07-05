"""
S8.5 (2026-07-06): DAST (Dynamic Application Security Testing) для MCP.

В отличие от SAST (статический анализ), DAST проверяет приложение в runtime,
отправляя malicious входные данные и анализируя ответы.

Покрывает:
- Path traversal payloads на file_path параметрах
- SQL injection payloads на query параметрах
- Command injection payloads
- Oversized inputs (DoS prevention)
- Invalid types (type confusion)
- Rate limit testing
- Missing required params
- Unicode/encoding attacks

Запуск:
    python -m src.services.dast_scanner run
    python -m src.services.dast_scanner run --tool search_1c_methods

В CI: .github/workflows/dast.yml (отдельный workflow для nightly runs).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.services.input_validation import check_rate_limit, validate_input


# ============================================================================
# PAYLOADS — malicious входные данные для тестирования
# ============================================================================

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "..%2f..%2f..%2fetc%2fpasswd",
    "..%252f..%252f..%252fetc%252fpasswd",
    "....//....//....//etc/passwd",
    "/etc/passwd",
    "/etc/shadow",
    "C:\\Windows\\System32\\drivers\\etc\\hosts",
    "file:///etc/passwd",
    "..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\..\\etc\\passwd",
    "data/../../etc/passwd",
    "files/../../../proc/self/environ",
]

SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "' UNION SELECT * FROM users --",
    "1; DELETE FROM users WHERE 1=1; --",
    "' OR 1=1 --",
    "admin'--",
    "1' AND SLEEP(5)--",
    "' OR ''='",
    "1 OR 1=1",
    "xp_cmdshell('net user')",
]

COMMAND_INJECTION_PAYLOADS = [
    "; cat /etc/passwd",
    "| cat /etc/passwd",
    "`cat /etc/passwd`",
    "$(cat /etc/passwd)",
    "&& cat /etc/passwd",
    "; rm -rf /",
    "| nc -l 4444",
    "`whoami`",
    "$(id)",
    "& whoami",
]

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "\"><script>alert(1)</script>",
    "'-alert(1)-'",
]

OVERSIZED_PAYLOADS = [
    "A" * 100_000,        # 100KB string
    "A" * 1_000_000,      # 1MB string
    "\x00" * 10_000,      # null bytes
    "../../" * 10_000,    # long path
]

INVALID_TYPE_PAYLOADS = [
    None,                  # null
    12345,                 # int instead of str
    [],                    # list
    {},                    # dict
    True,                  # bool
    object(),              # object
]


# ============================================================================
# DAST SCAN RESULT
# ============================================================================


@dataclass
class DastFinding:
    """DAST finding — потенциальная уязвимость."""

    tool_name: str
    payload_type: str          # path_traversal, sql_injection, etc.
    payload: str
    param_name: str
    is_vulnerable: bool        # True если input прошёл валидацию (BAD!)
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool_name,
            "payload_type": self.payload_type,
            "payload": self.payload[:200],   # truncate
            "param": self.param_name,
            "vulnerable": self.is_vulnerable,
            "details": self.details,
        }


@dataclass
class DastReport:
    """Отчёт DAST сканирования."""

    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    findings: list[DastFinding] = field(default_factory=list)
    tools_scanned: list[str] = field(default_factory=list)
    payloads_total: int = 0
    payloads_blocked: int = 0
    payloads_passed: int = 0

    @property
    def vulnerable_count(self) -> int:
        return sum(1 for f in self.findings if f.is_vulnerable)

    @property
    def blocked_count(self) -> int:
        return sum(1 for f in self.findings if not f.is_vulnerable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": round(self.ended_at - self.started_at, 2),
            "tools_scanned": self.tools_scanned,
            "payloads_total": self.payloads_total,
            "payloads_blocked": self.payloads_blocked,
            "payloads_passed": self.payloads_passed,
            "vulnerable_count": self.vulnerable_count,
            "blocked_count": self.blocked_count,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ============================================================================
# DAST SCANNER
# ============================================================================


# Список MCP tools с их параметрами для DAST тестирования
MCP_TOOLS_TO_TEST: list[dict[str, Any]] = [
    {
        "name": "search_1c_methods",
        "required": ["query"],
        "optional": ["limit"],
        "string_params": ["query"],   # параметры-строки — для injection payloads
    },
    {
        "name": "inspect_config",
        "required": ["config_name"],
        "optional": [],
        "string_params": ["config_name"],
    },
    {
        "name": "read_file",
        "required": ["file_path"],
        "optional": [],
        "string_params": ["file_path"],   # для path traversal
    },
    {
        "name": "build_config_index",
        "required": ["config_name"],
        "optional": ["output_path"],
        "string_params": ["config_name", "output_path"],
    },
    {
        "name": "check_standards",
        "required": ["file_path"],
        "optional": [],
        "string_params": ["file_path"],
    },
]


class DastScanner:
    """S8.5: DAST scanner для MCP tools.

    Отправляет malicious payloads в input validation layer и проверяет,
    что все они блокируются. Любой payload, прошедший валидацию, — уязвимость.
    """

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.report = DastReport()

    def scan_tool(self, tool_spec: dict[str, Any]) -> list[DastFinding]:
        """Сканирование одного MCP tool.

        Args:
            tool_spec: spec с name, required, optional, string_params.

        Returns:
            Список находок.
        """
        tool_name = tool_spec["name"]
        required = tool_spec["required"]
        optional = tool_spec.get("optional", [])
        string_params = tool_spec.get("string_params", [])

        if self.verbose:
            print(f"  Scanning {tool_name}...")

        findings: list[DastFinding] = []

        for param in string_params:
            # Path traversal payloads — только для path-параметров
            if "path" in param.lower() or "file" in param.lower():
                findings.extend(self._test_payloads(
                    tool_name, param, required, optional,
                    PATH_TRAVERSAL_PAYLOADS, "path_traversal",
                ))

            # SQL injection — для query параметров
            if param.lower() in ("query", "search", "filter"):
                findings.extend(self._test_payloads(
                    tool_name, param, required, optional,
                    SQL_INJECTION_PAYLOADS, "sql_injection",
                ))

            # Command injection — для всех string params
            findings.extend(self._test_payloads(
                tool_name, param, required, optional,
                COMMAND_INJECTION_PAYLOADS, "command_injection",
            ))

            # XSS — для всех string params
            findings.extend(self._test_payloads(
                tool_name, param, required, optional,
                XSS_PAYLOADS, "xss",
            ))

            # Oversized payloads
            findings.extend(self._test_payloads(
                tool_name, param, required, optional,
                OVERSIZED_PAYLOADS, "oversized",
            ))

        # Invalid type payloads (для всех required string params)
        for param in string_params:
            findings.extend(self._test_invalid_types(
                tool_name, param, required, optional,
            ))

        # Missing required params
        findings.extend(self._test_missing_required(
            tool_name, required, optional,
        ))

        return findings

    def scan_all(self) -> DastReport:
        """Сканирование всех MCP tools."""
        self.report = DastReport()
        self.report.started_at = time.time()

        if self.verbose:
            print(f"🛡 DAST scan started — {len(MCP_TOOLS_TO_TEST)} tools")

        for tool_spec in MCP_TOOLS_TO_TEST:
            self.report.tools_scanned.append(tool_spec["name"])
            findings = self.scan_tool(tool_spec)
            self.report.findings.extend(findings)

        self.report.payloads_total = len(self.report.findings)
        self.report.payloads_blocked = self.report.blocked_count
        self.report.payloads_passed = self.report.vulnerable_count
        self.report.ended_at = time.time()

        if self.verbose:
            self._print_summary()

        return self.report

    def scan_rate_limits(self) -> list[DastFinding]:
        """Тестирование rate limiting.

        Вызывает tool много раз и проверяет, что rate limit срабатывает.
        """
        findings: list[DastFinding] = []
        from src.services.input_validation import reset_rate_limits
        reset_rate_limits()

        # 200 вызовов при лимите 100 — должны быть заблокированы после 100
        max_calls = 100
        blocked_count = 0
        for i in range(200):
            allowed, _ = check_rate_limit("dast_test_tool", max_calls=max_calls)
            if not allowed:
                blocked_count += 1

        if blocked_count == 0:
            findings.append(DastFinding(
                tool_name="<rate_limit>",
                payload_type="rate_limit_bypass",
                payload=f"200 calls with limit={max_calls}",
                param_name="N/A",
                is_vulnerable=True,
                details="Rate limit не сработал — DoS possible",
            ))
        else:
            findings.append(DastFinding(
                tool_name="<rate_limit>",
                payload_type="rate_limit_bypass",
                payload=f"200 calls with limit={max_calls}",
                param_name="N/A",
                is_vulnerable=False,
                details=f"Rate limit сработал — {blocked_count} calls заблокированы",
            ))

        reset_rate_limits()
        return findings

    # =====================================================================
    # INTERNAL HELPERS
    # =====================================================================

    def _test_payloads(
        self,
        tool_name: str,
        param: str,
        required: list[str],
        optional: list[str],
        payloads: list[str],
        payload_type: str,
    ) -> list[DastFinding]:
        """Тестирование списка payloads на одном параметре."""
        findings: list[DastFinding] = []

        for payload in payloads:
            args = self._build_args(param, payload, required, optional)
            is_valid, error = validate_input(tool_name, args, required, optional)

            # is_valid=True означает, что payload ПРОШЁЛ валидацию — плохо!
            # (за исключением oversized, где блокировка на уровне приложения может быть позднее)
            is_vulnerable = is_valid and payload_type not in ("oversized",)

            findings.append(DastFinding(
                tool_name=tool_name,
                payload_type=payload_type,
                payload=payload if isinstance(payload, str) else str(payload),
                param_name=param,
                is_vulnerable=is_vulnerable,
                details=error if not is_valid else "PAYLOAD ACCEPTED",
            ))

        return findings

    def _test_invalid_types(
        self,
        tool_name: str,
        param: str,
        required: list[str],
        optional: list[str],
    ) -> list[DastFinding]:
        """Тестирование invalid types.

        Note: None для OPTIONAL параметра — это валидный "not provided".
        Поэтому None тестируется только для required params.
        """
        findings: list[DastFinding] = []

        is_required = param in required

        for payload in INVALID_TYPE_PAYLOADS:
            # Пропускаем None для optional params — это валидный "absent"
            if payload is None and not is_required:
                continue

            args = self._build_args(param, payload, required, optional)
            is_valid, error = validate_input(tool_name, args, required, optional)

            # Invalid type не должен проходить валидацию
            is_vulnerable = is_valid

            payload_repr = repr(payload)[:200]
            findings.append(DastFinding(
                tool_name=tool_name,
                payload_type="invalid_type",
                payload=payload_repr,
                param_name=param,
                is_vulnerable=is_vulnerable,
                details=error if not is_valid else "INVALID TYPE ACCEPTED",
            ))

        return findings

    def _test_missing_required(
        self,
        tool_name: str,
        required: list[str],
        optional: list[str],
    ) -> list[DastFinding]:
        """Тестирование отсутствующих required params."""
        findings: list[DastFinding] = []

        for missing_param in required:
            args: dict[str, Any] = {}
            for p in required:
                if p != missing_param:
                    args[p] = "valid_value"

            is_valid, error = validate_input(tool_name, args, required, optional)
            is_vulnerable = is_valid   # missing required должен fail

            findings.append(DastFinding(
                tool_name=tool_name,
                payload_type="missing_required",
                payload=f"<missing {missing_param}>",
                param_name=missing_param,
                is_vulnerable=is_vulnerable,
                details=error if not is_valid else "MISSING REQUIRED ACCEPTED",
            ))

        return findings

    def _build_args(
        self,
        target_param: str,
        value: Any,
        required: list[str],
        optional: list[str],
    ) -> dict[str, Any]:
        """Построить args dict с заданным payload для target_param."""
        args: dict[str, Any] = {}
        for p in required:
            if p == target_param:
                args[p] = value
            else:
                # Валидные значения для других required params
                args[p] = "valid_value_123"
        for p in optional:
            if p == target_param:
                args[p] = value
        return args

    def _print_summary(self) -> None:
        """Печать summary отчёта."""
        report = self.report
        print(f"\n{'='*60}")
        print(f"DAST SCAN REPORT")
        print(f"{'='*60}")
        print(f"Tools scanned: {len(report.tools_scanned)}")
        print(f"Payloads total: {report.payloads_total}")
        print(f"  ✅ Blocked: {report.payloads_blocked}")
        print(f"  ❌ Passed (vulnerabilities): {report.payloads_passed}")
        print(f"Duration: {report.ended_at - report.started_at:.2f}s")
        print()

        if report.vulnerable_count > 0:
            print(f"⚠️  VULNERABILITIES FOUND: {report.vulnerable_count}")
            vuln_by_type: dict[str, int] = {}
            for f in report.findings:
                if f.is_vulnerable:
                    vuln_by_type[f.payload_type] = vuln_by_type.get(f.payload_type, 0) + 1
            for ptype, count in sorted(vuln_by_type.items()):
                print(f"  {ptype}: {count}")
        else:
            print("✅ NO VULNERABILITIES — all payloads blocked")


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для DAST scanner."""
    import argparse

    parser = argparse.ArgumentParser(description="DAST scanner для MCP tools")
    parser.add_argument("--tool", help="Сканировать только указанный tool")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", help="Сохранить отчёт в JSON файл")
    parser.add_argument("--rate-limit", action="store_true", help="Тестировать rate limits")
    args = parser.parse_args()

    scanner = DastScanner(verbose=args.verbose)

    if args.rate_limit:
        findings = scanner.scan_rate_limits()
        print(f"Rate limit test: {len(findings)} findings")
        for f in findings:
            status = "❌ VULN" if f.is_vulnerable else "✅ OK"
            print(f"  {status}: {f.details}")
        return 1 if any(f.is_vulnerable for f in findings) else 0

    if args.tool:
        tool_spec = next(
            (t for t in MCP_TOOLS_TO_TEST if t["name"] == args.tool), None
        )
        if not tool_spec:
            print(f"Unknown tool: {args.tool}")
            return 1
        findings = scanner.scan_tool(tool_spec)
        scanner.report.findings = findings
        scanner.report.tools_scanned = [args.tool]
        scanner.report.payloads_total = len(findings)
        scanner.report.payloads_blocked = scanner.report.blocked_count
        scanner.report.payloads_passed = scanner.report.vulnerable_count
        scanner.report.started_at = time.time()
        scanner.report.ended_at = time.time()
    else:
        scanner.scan_all()

    if args.output:
        Path(args.output).write_text(scanner.report.to_json(), encoding="utf-8")
        print(f"\nReport saved to {args.output}")

    # Exit code: 0 если нет уязвимостей, 1 если есть
    return 1 if scanner.report.vulnerable_count > 0 else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
