# Query Intelligence — инструмент для работы с языком запросов 1С

**Версия:** 1.0  
**Дата:** July 2026  
**Статус:** Production-ready (все фазы реализованы)

---

## Обзор

Query Intelligence — единый инструмент для **генерации, понимания, валидации и оптимизации** запросов 1С. Работает в двух режимах:

- **MCP** — 5 tools для LLM-агентов (Cursor, Claude, VS Code)
- **CLI** — 6 команд для разработчиков

Всё работает **офлайн** — по выгрузке конфигурации (XML+BSL), без подключения к живой базе 1С.

---

## Возможности

### Генерация запросов по описанию
Опишите задачу на русском → получите готовый текст запроса с параметрами и объяснением.

### Понимание запросов
Передайте текст запроса → получите человекочитаемое описание (таблицы, поля, фильтры, группировки, агрегаты).

### Валидация запросов
Проверка запроса по метаданным конфигурации — существование таблиц, полей, доступность виртуальных таблиц.

### Оптимизация запросов
18 правил оптимизации с ссылками на паттерны knowledge base.

### SDBL AST парсер
Настоящий AST-парсер языка запросов 1С через ANTLR4 (SDBL грамматика от 1c-syntax).

---

## MCP Tools (5 шт.)

| Tool | Описание |
|------|----------|
| `generate_query` | Генерация запроса по описанию задачи |
| `explain_query` | Человекочитаемое объяснение запроса |
| `optimize_query` | Предложения по оптимизации (18 правил) |
| `query_templates` | Список 15 шаблонов в 6 категориях |
| `query_workflow` | Мета-tool: generate→validate→optimize в одном вызове |

**Существующие tools (не изменились):**
- `validate_query_static` — статическая валидация по метаданным
- `analyze_queries` — анализ запросов в BSL файле (10 эвристик)

**Итого MCP tools:** 51

### Пример: query_workflow

```json
// Вызов
{
    "task": "продажи по месяцам за последний год",
    "config_name": "ut11"
}

// Результат
{
    "generated_query": {
        "text": "ВЫБРАТЬ МЕСЯЦ(Рег.Период) КАК Период, Рег.Номенклатура, СУММА(Рег.Сумма) КАК Сумма ...",
        "parameters": ["ДатаНачала", "ДатаКонца"],
        "explanation": "Шаблон: sales_by_period — Продажи по периодам..."
    },
    "validation": {"valid": true, "total_errors": 0},
    "optimization": {"total_issues": 0, "total_suggestions": 0},
    "explanation": {"summary": "Вычисляет SUM(Рег.Сумма)..."},
    "bsl_code": "Функция ВыполнитьЗапрос() Экспорт\n    Запрос = Новый Запрос; ...",
    "workflow_steps": ["generate_query → OK", "validate_query_static → OK", "optimize_query → OK"]
}
```

---

## CLI Команды (6 шт.)

```bash
# Генерация запроса по описанию
1c-ai query gen "продажи по месяцам за последний год" --config ut11
1c-ai query gen "топ-10 клиентов по выручке" --output result.bsl

# Объяснение запроса
1c-ai query explain --text "ВЫБРАТЬ Рег.Номенклатура, СУММА(Рег.Выручка) ..."
1c-ai query explain --file query.bsl --config ut11

# Валидация запроса (non-zero exit для CI)
1c-ai query validate --text "ВЫБРАТЬ ..." --config ut11

# Оптимизация запроса
1c-ai query optimize --text "ВЫБРАТЬ * ИЗ Справочник.Т ГДЕ Т.А = &А ИЛИ Т.Б = &Б"
1c-ai query optimize --file query.bsl

# Анализ запросов в BSL файле
1c-ai query analyze --file module.bsl

# Список шаблонов
1c-ai query templates --list
1c-ai query templates --category virtual_tables
```

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Query Intelligence Engine                         │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  SDBLParser     │  │  QueryGenerator  │  │  QueryValidator    │ │
│  │  (ANTLR4 AST)   │  │  (15 шаблонов)   │  │  (статический)     │ │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬──────────┘ │
│           │                    │                      │            │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  QueryExplainer │  │  QueryOptimizer  │  │  QueryAnalyzer     │ │
│  │  (объяснение)   │  │  (18 правил)     │  │  (10 эвристик)     │ │
│  └─────────────────┘  └──────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         │                                          │
         ▼                                          ▼
┌─────────────────────┐                  ┌─────────────────────────┐
│   MCP (5 tools)     │                  │   CLI (6 команд)        │
│   + 2 existing      │                  │                         │
└─────────────────────┘                  └─────────────────────────┘
```

### SDBL AST Parser (Phase A.0)
- ANTLR4 грамматика SDBL от 1c-syntax (LGPL-3.0)
- 519 строк парсер + 289 строк лексер
- Python target сгенерирован через `antlr-4.13.1-complete.jar`
- Полная поддержка SDBL: GROUPING SETS, INDEX BY, FOR UPDATE, EMPTYTABLE

### QueryGenerator (Phase B)
- 15 шаблонов в 6 категориях
- Анализ описания задачи (период, группировка, агрегаты, фильтр, топ-N)
- Автопоиск объектов в метаданных
- Валидация через SDBL

### QueryExplainer + QueryOptimizer (Phase C)
- Explainer: summary, tables, fields, filters, grouping, joins, aggregates
- Optimizer: 18 правил (10 базовых + 8 производительности)
- Каждое предложение ссылается на паттерн knowledge base

### Knowledge Base
- 15 паттернов оптимизации (было 5)
- 10 антипаттернов (новое)
- Связь правил анализатора с паттернами

---

## Установка

### Базовая установка (без SDBL AST)
```bash
pip install -e ".[mcp]"
```

### Полная установка (с SDBL AST парсером)
```bash
pip install -e ".[mcp,query,ast]"
```

### Проверка
```bash
1c-ai query templates --list
1c-ai query gen "продажи по месяцам"
```

---

## Источники

| Компонент | Источник | Лицензия |
|-----------|----------|----------|
| SDBL грамматика | [1c-syntax/bsl-parser](https://github.com/1c-syntax/bsl-parser) | LGPL-3.0 |
| tree-sitter-bsl | [alkoleft/tree-sitter-bsl](https://github.com/alkoleft/tree-sitter-bsl) | Apache 2.0 |
| ANTLR4 Python | [antlr.org](https://www.antlr.org/) | BSD-3-Clause |
| Knowledge base | ours | MIT |

---

## Интеграция с BSL Language Server

Проект совместим с [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) от 1c-syntax:
- 15 готовых query diagnostics доступны через BSL LS
- Claude Code plugin: `1c-syntax/claude-code-bsl-lsp`
- Наши паттерны knowledge base связаны с правилами BSL LS

---

## Метрики

| Метрика | Значение |
|---------|----------|
| MCP tools для запросов | 7 (5 новых + 2 существующих) |
| CLI команд для запросов | 6 |
| Шаблонов запросов | 15 |
| Паттернов knowledge base | 15 + 10 антипаттернов |
| Правил валидации | 12 статических + 10 эвристик |
| Правил оптимизации | 18 (10 базовых + 8 производительности) |
| SDBL AST | полная поддержка через ANTLR4 |
| End-to-end workflow | да (query_workflow мета-tool) |
| Генерация по описанию | да |
