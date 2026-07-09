# Security Threat Model (S8.1)

> D2.1 (2026-07-05): Расширенная threat model для 1c-ai-dev-env.
> OWASP Top 10 + 1С-специфичные угрозы.

## OWASP Top 10 (Web/MCP)

| # | Угроза | Вектор | Митигация | Статус |
|---|--------|--------|-----------|--------|
| A01 | Broken Access Control | MCP tool без auth | Rate limiting (MCP_RATE_LIMIT), path traversal protection | ✅ S8.2, S8.6 |
| A02 | Cryptographic Failures | Secrets in code | detect-secrets, .env.example, .gitignore | ✅ S8.6 |
| A03 | Injection | shell=True, SQL injection in BSL | subprocess audit (0 shell=True), security_auditor SEC001 | ✅ S8.2 |
| A04 | Insecure Design | Missing threat model | This document (S8.1) | ✅ |
| A05 | Security Misconfiguration | Default configs | Config dataclass with validation (F1.3) | ✅ F1.3 |
| A06 | Vulnerable Components | CVE in dependencies | pip-audit + safety in CI, Dependabot | ✅ P1.7 |
| A07 | Auth Failures | Token leakage | Fine-grained PAT, 30-day expiry, .git-credentials in .gitignore | ✅ S8.6 |
| A08 | Data Integrity Failures | Malformed EPF/CF | cf_extractor validation, round-trip checks | ✅ |
| A09 | Logging Failures | Missing audit trail | structlog + trace_id (F1.5), audit log (S8.9) | ✅ F1.5, ⏳ S8.9 |
| A10 | SSRF | Ollama URL | Config validation ollama_url starts with http:// | ✅ F1.3 |

## 1С-специфичные угрозы

| # | Угроза | Вектор | Митигация | Статус |
|---|--------|--------|-----------|--------|
| C01 | Выполнить() с динамическим кодом | BSL code injection | security_auditor SEC002 | ✅ |
| C02 | Вычислить() с динамическим выражением | BSL expression injection | security_auditor SEC003 | ✅ |
| C03 | Хардкод паролей/токенов в BSL | Secrets in BSL code | security_auditor SEC004-SEC006 | ✅ |
| C04 | COM-объекты | Unsafe COM usage | security_auditor SEC007 | ✅ |
| C05 | Привилегированный режим (RLS bypass) | RLS bypass | security_auditor SEC008 | ✅ |
| C06 | ЗапуститьПриложение (OS command) | OS command injection | security_auditor SEC009 | ✅ |
| C07 | Небезопасные файловые операции | Path traversal in BSL | security_auditor SEC010 | ✅ |
| C08 | ИнтернетСоединение без проверки | MITM | security_auditor SEC011 | ✅ |
| C09 | Утечка через чат/логи | Token в сообщении | DEBT-001 (resolved), detect-secrets | ✅ |
| C10 | LLM-generated code execution | AI generates unsafe BSL | Sandboxing (S8.10), BSL validation before compile | ⏳ S8.10 |

## CI/CD угрозы

| # | Угроза | Вектор | Митигация | Статус |
|---|--------|--------|-----------|--------|
| D01 | Workflow file injection | PR with malicious workflow | Token scoped (Workflows: read/write), review required | ✅ DEBT-003 |
| D02 | Supply chain attack | Malicious dependency | pip-audit, safety, SBOM (CycloneDX) | ✅ S8.6, I7.9 |
| D03 | Dependency confusion | Typosquatting package | Hash-locked requirements (S8.11) | ⏳ S8.11 |
| D04 | Secrets in CI logs | Token in workflow output | GitHub Secrets, masked in logs | ✅ S8.6 |
| D05 | Unsigned releases | Tampered release artifacts | Release signature (cosign) — I7.3 | ⏳ I7.3 |

## MCP-специфичные угрозы

| # | Угроза | Вектор | Митигация | Статус |
|---|--------|--------|-----------|--------|
| M01 | Path traversal через MCP tool | file_path with ../ | _security.py resolve_path_within_project | ✅ |
| M02 | Rate limit bypass | Multiple tool calls | MCP_RATE_LIMIT per-tool (input_validation.py) | ✅ |
| M03 | Invalid input crash | Malformed arguments | input_validation.py validate_input | ✅ |
| M04 | DoS через большой файл | Huge XML/BSL file | timeout on subprocess (S8.2) | ✅ S8.2 |
| M05 | Unauthorized MCP access | No auth on stdio | Local-only (P8), stdio transport | ✅ |
