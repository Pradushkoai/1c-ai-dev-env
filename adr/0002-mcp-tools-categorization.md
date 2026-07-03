# ADR-0002: Категоризация 45 MCP tools

**Дата:** 2026-07-03
**Статус:** Accepted

## Контекст
mcp_server.py разросся до 1245 строк. 45 MCP tools определены как
types.Tool литералы внутри list_tools handler. Это нарушает SRP и
усложняет поддержку.

## Рассмотренные варианты
1. **Оставить в mcp_server.py** — всё в одном файле
   - Pros: просто найти
   - Cons: God Object, сложно тестировать, нарушение SRP
2. **Разделить по категориям в src/mcpserver/tools/** — 8 модулей
   - Pros: SRP, модульность, легко тестировать
   - Cons: больше файлов
3. **JSON конфиг** — вынести в config файл
   - Pros: декларативно
   - Cons: потеря type safety, сложнее валидация

## Решение
Вариант 2. Создан src/mcpserver/tools/ пакет:
- 8 модулей по категориям: search, analyzers, metadata, generate,
  dsl_cfe, quality, context, misc
- tool_definitions.py: get_all_tool_definitions() возвращает list[types.Tool]
- __init__.py: get_all_descriptions() для _get_tools_description()
- mcp_server.py: 139 строк (было 1245), тонкая обёртка

## Последствия
- mcp_server.py: 1245 → 139 строк (цель <300 превышена)
- Каждая категория независимо тестируется
- snapshot тесты проверяют контракт 45 tools
- Добавление нового tool: добавить в соответствующий модуль категории
