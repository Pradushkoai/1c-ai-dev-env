# SaaS Architecture (S1)

> Архитектурная готовность к масштабированию: от solo до multi-tenant.
> S1 (план v3: Post-v6.0 Strategic Roadmap), адаптация v1 P3.1.

## Обзор

Проект 1c-ai-dev-env изначально спроектирован для solo-использования: один
разработчик, один Project instance, один набор индексов. S1 подготавливает
архитектуру к масштабированию без переписывания ядра.

**Принцип:** "technology-level preparation" — архитектура, интерфейсы, протоколы.
"Product-level" аспекты (billing, SLA, marketing) откладываются до появления команды.

## Уровни масштабирования

### Уровень 1: Solo (текущий, v6.0.0)

```
1 разработчик → 1 Project → 1 набор конфигураций → 1 MCP сервер
```

- PathManager: один root, один набор индексов
- ConfigRegistry: один JSON файл (runtime/config-registry.json)
- MCP сервер: один процесс, stdio transport

### Уровень 2: Multi-config (S1, v7.0)

```
1 разработчик → 1 Project → N конфигураций 1С → 1 MCP сервер
```

- PathManager: namespace isolation через prefix (team_a/, team_b/)
- ConfigRegistry: namespace-aware (каждая команда видит только свои конфиги)
- Docker Compose: несколько конфигураций в одном контейнере
- MCP сервер: один процесс, но namespace изоляция в tools

### Уровень 3: Multi-tenant (future, post-v7.0)

```
N команд → N Projects → N наборов конфигураций → N MCP серверов (или 1 с routing)
```

- PathManager: namespace = tenant_id
- ConfigRegistry: per-tenant registry files
- MCP сервер: HTTP transport (вместо stdio), routing по tenant_id
- Auth: API keys / OIDC (после появления команды)
- Billing: Stripe/YooKassa integration (future)

## Namespace Isolation

### Концепция

Каждая конфигурация 1С привязана к namespace (default: "default"):

```
data/configs/{namespace}/{config_name}/
derived/configs/{namespace}/{config_name}/
runtime/registry/{namespace}.json
```

### PathManager изменения

```python
# Текущее (solo):
pm = PathManager(project_root)
pm.config_path("ut11")  # → data/configs/ut11/

# S1 (multi-config с namespace):
pm = PathManager(project_root, namespace="team_a")
pm.config_path("ut11")  # → data/configs/team_a/ut11/
```

### Конфигурация

Namespace задаётся через env var:
```bash
export MCP_NAMESPACE=team_a
```

Default: "default" (обратная совместимость с solo).

## Docker Compose Multi-config

### docker-compose.yml (обновлённый)

```yaml
services:
  mcp-server:
    build: .
    environment:
      - MCP_NAMESPACE=default
      - MCP_METRICS_PORT=8001
    volumes:
      - ./data:/app/data
      - ./derived:/app/derived
      - ./runtime:/app/runtime

  # Дополнительный контейнер для другой команды
  mcp-server-team-b:
    build: .
    environment:
      - MCP_NAMESPACE=team_b
      - MCP_METRICS_PORT=8002
    volumes:
      - ./data:/app/data
      - ./derived:/app/derived
      - ./runtime:/app/runtime
```

Каждый контейнер видит одни и те же data/derived директории, но через
namespace isolation получает доступ только к своим конфигурациям.

## Billing Stub

### experimental/services/billing_stub.py

> ⚠️ Модуль перенесён в `experimental/` (Этап 0.1, ADR-0006).
> Не поддерживается до выполнения критериев Beta → Production-Ready.

Заглушка для будущей интеграции с billing системами (Stripe, YooKassa).

```python
# Только для локальной проверки, не в production
from experimental.services.billing_stub import BillingStub

billing = BillingStub()
billing.record_usage(namespace="team_a", tool="search_1c_methods", calls=10)
report = billing.get_usage_report(namespace="team_a")
# → {namespace: "team_a", total_calls: 10, tools: {...}}
```

**Не реализует:**
- Реальную оплату (Stripe/YooKassa API)
- Webhooks
- Инвойисы
- Подписки

**Реализует:**
- Учёт usage (calls per namespace per tool)
- Простой JSON отчёт
- Заглушка для будущей интеграции

## Roadmap

- **S1 (этот документ):** Архитектура + namespace isolation + billing stub ✅
- **Future (Level 3):** HTTP transport для MCP, multi-tenant routing, auth
- **Future:** Stripe/YooKassa integration
- **Future:** Per-tenant rate limiting
- **Future:** Per-tenant metrics (Prometheus labels)
