# Metrics & Observability (P1.5)

> Prometheus метрики для мониторинга MCP tools в production.
> Добавлено в P1.5 (план v2 Solo Edition).

## Обзор

1c-ai-dev-env поддерживает опциональные Prometheus метрики для observability:
- Latency каждого MCP tool
- Error rate по tools
- Usage count (сколько раз вызван tool)
- Количество активных конфигураций
- Размер индексов

## Установка

```bash
# Установить с extras [metrics]
pip install -e ".[metrics]"

# Или отдельно
pip install prometheus-client
```

## Использование

### Запуск MCP сервера с метриками

```bash
# Запуск с /metrics endpoint на порту 8001
MCP_METRICS_PORT=8001 python -m src.cli mcp serve

# Или через 1c-ai CLI
MCP_METRICS_PORT=8001 1c-ai mcp serve
```

Без `MCP_METRICS_PORT` env var — metrics endpoint не запускается (default).

### Prometheus scrape config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: '1c-ai-dev-env'
    static_configs:
      - targets: ['localhost:8001']
    scrape_interval: 15s
```

### Python API

```python
from src.services.metrics import get_metrics, with_metrics

# Получить registry
registry = get_metrics()

# Записать метрики вручную
registry.record_tool_call("search_1c_methods", "success")
registry.record_tool_error("analyze_bsl", "RuntimeError")
registry.observe_latency("search_1c_methods", 0.045)
registry.set_active_configs(3)
registry.set_index_size("metadata", 1024000)

# Получить текст метрик (для /metrics endpoint)
metrics_text = registry.get_metrics_text()

# Декоратор для инструментирования
@with_metrics("my_tool")
async def handle_my_tool(query: str) -> dict:
    return {"result": "..."}
```

## Метрики

| Метрика | Тип | Labels | Описание |
|---------|-----|--------|----------|
| `mcp_tool_calls_total` | Counter | tool_name, status | Всего вызовов MCP tools |
| `mcp_tool_errors_total` | Counter | tool_name, error_type | Всего ошибок по tools |
| `mcp_tool_latency_seconds` | Histogram | tool_name | Латентность MCP tools |
| `mcp_active_configs` | Gauge | — | Количество активных конфигураций |
| `mcp_index_size_bytes` | Gauge | index_type | Размер индексов (metadata, api, skd, forms, platform) |

### Histogram buckets

`mcp_tool_latency_seconds` использует buckets:
`0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0` секунд

## Fallback

Если `prometheus_client` не установлен:
- `get_metrics()` возвращает `NoOpRegistry` (все операции no-op)
- `@with_metrics` работает без накладных расходов
- `maybe_start_metrics_server()` логирует warning, не падает

Проект полностью функционален без `extras [metrics]` — метрики опциональны.

## Grafana Dashboard

Пример Grafana dashboard JSON будет добавлен в `docs/grafana-dashboard.json`
(задача P1.5 roadmap).

### Полезные PromQL запросы

```promql
# Средняя latency по tools (за 5 минут)
rate(mcp_tool_latency_seconds_sum[5m]) / rate(mcp_tool_latency_seconds_count[5m])

# Топ-5 tools по количеству вызовов
topk(5, sum by (tool_name) (rate(mcp_tool_calls_total[1h])))

# Error rate по tools
rate(mcp_tool_errors_total[5m]) / rate(mcp_tool_calls_total[5m])

# P95 latency по tool
histogram_quantile(0.95, rate(mcp_tool_latency_seconds_bucket[5m]))
```

## Зависимости

| Пакет | Версия | Extras |
|-------|--------|--------|
| prometheus-client | >=0.20,<1.0 | [metrics] |

## Roadmap

- **P1.5:** Базовые метрики (этот документ) ✅
- **Future:** Grafana dashboard JSON
- **Future:** OpenTelemetry tracing для distributed tracing
- **Future:** Инструментирование всех 45 MCP tools через @with_metrics
