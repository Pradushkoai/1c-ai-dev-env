# Security Audit (S5)

> Security hardening для 1c-ai-dev-env.
> S5 (план v3: Post-v6.0 Strategic Roadmap).

## Обзор

S5 добавляет security infrastructure для будущего production-ready
использования (до перехода из Beta в Production-Ready — см.
[ROADMAP.md](../ROADMAP.md#критерии-перехода-beta--production-ready)):
- Input validation для всех 45 MCP tools
- Rate limiting через env var
- Security audit документация

## Threat Model

### Атаки

| Угроза | Вектор | Митигация |
|--------|--------|-----------|
| **Path traversal** | file_path с `../` | `_security.py: resolve_path_within_project()` |
| **Injection (SQL/Command)** | BSL код с `Выполнить()` | `security_auditor` (15 правил) |
| **DoS через MCP** | Множественные вызовы tools | Rate limiting (`MCP_RATE_LIMIT` env var) |
| **Invalid input** | Неверные типы/пустые параметры | `input_validation.py: validate_input()` |
| **Hardcoded secrets** | Пароли/токены в коде | `security_auditor` правило + `.gitignore` |
| **Dependency CVE** | Уязвимые зависимости | `pip-audit` + `safety` (P1.7) |

## Input Validation

### src/services/input_validation.py

```python
from src.services.input_validation import validate_input

is_valid, error = validate_input(
    "search_1c_methods",
    {"query": "найти", "limit": 5},
    required_params=["query"],
)
if not is_valid:
    return error  # 400 Bad Request
```

Проверки:
- Required parameters присутствуют и не None
- String parameters не пустые
- Type checking (query=str, limit=int, file_path=str, ...)
- limit > 0 и limit <= 1000

### Rate Limiting

```bash
# Установить лимит 50 вызовов в минуту (default: 100)
export MCP_RATE_LIMIT=50

# Отключить rate limiting
export MCP_RATE_LIMIT=0
```

Rate limiting работает per-tool: каждый MCP tool имеет отдельный счётчик.
Окно: 60 секунд.

## Path Traversal Protection

### src/mcpserver/handlers/_security.py

Уже реализовано в P0.2:
- `resolve_path_within_project()`: проверяет что path внутри project root
- `is_path_within_project()`: быстрая проверка
- Использует `os.path.realpath()` для раскрытия `..` и симлинков
- Тесты: `tests/test_path_traversal_protection.py`

## Security Auditor

### scripts/security_auditor.py (15 правил)

- SQL-инъекции
- `Выполнить()` с пользовательским вводом
- Хардкод паролей/токенов
- COM-объекты
- RLS (Row Level Security)
- Path traversal в BSL
- Небезопасная десериализация

## CI/CD Security

### .github/workflows/dependency-hygiene.yml (P1.7)

- `pip-audit --strict`: CVE scan (blocking)
- `safety scan`: vulnerability check (non-blocking, baseline)
- `pip-licenses`: license compatibility (blocking: GPL/AGPL/LGPL)

## Roadmap

- **S5 (этот документ):** Input validation + rate limiting + audit ✅
- **Future:** SSO/SAML (после появления команды)
- **Future:** Formal security audit (third-party)
- **Future:** Penetration testing
