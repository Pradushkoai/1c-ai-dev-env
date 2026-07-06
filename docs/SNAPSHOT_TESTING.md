# Snapshot Testing (P1.6)

> Snapshot тесты для стабильности контракта MCP tools.
> Добавлено в P1.6 (план v2 Solo Edition).

## Обзор

Snapshot тесты гарантируют, что контракт 45 MCP tools не меняется без
явного обновления snapshot. Это «автоматический ревьюер контракта»:
любое изменение в именах, описаниях или inputSchema tools приведёт к
падению теста.

## Что проверяют snapshot тесты

| Snapshot | Что фиксирует |
|----------|---------------|
| `tool_names.json` | Имена всех 45 tools (отсортированные) |
| `tool_count.txt` | Количество tools (45) |
| `tool_descriptions.json` | Описания всех tools (name → description) |
| `tool_input_schemas.json` | inputSchema всех tools |
| `static_descriptions.json` | Статические описания (_get_tools_description) |
| `static_descriptions_names.json` | Имена из статических описаний |
| `static_descriptions_required_params.json` | required_params для каждого tool |

## Запуск тестов

```bash
# Обычный прогон (проверка, что snapshot не изменились)
pytest tests/test_mcp_tools_snapshot.py -v

# Обновить snapshot (при намеренном изменении контракта)
pytest tests/test_mcp_tools_snapshot.py --snapshot-update

# Полный прогон всех тестов
pytest tests/ --cov=src --cov-fail-under=70
```

## Когда обновлять snapshot

Обновляйте snapshot ТОЛЬКО при намеренном изменении контракта MCP tools:
1. Добавление нового tool
2. Удаление tool
3. Изменение описания tool
4. Изменение inputSchema (новый параметр, изменённый тип)

**Никогда не обновляйте snapshot случайно** — это скроет breaking change.

### Процесс обновления

```bash
# 1. Внесите изменения в tools
# 2. Запустите тесты — они упадут
pytest tests/test_mcp_tools_snapshot.py

# 3. Проверьте diff (что изменилось)
git diff tests/snapshots/

# 4. Если изменения осознанные — обновите snapshot
pytest tests/test_mcp_tools_snapshot.py --snapshot-update

# 5. Закоммитьте изменения с описанием
git add tests/snapshots/ src/mcpserver/tools/
git commit -m "feat(P1.X): добавлен tool X (snapshot обновлён)"
```

## Структура snapshot файлов

```
tests/snapshots/test_mcp_tools_snapshot/
├── test_tool_names_snapshot/
│   └── tool_names.json
├── test_tool_count_snapshot/
│   └── tool_count.txt
├── test_tool_descriptions_snapshot/
│   └── tool_descriptions.json
├── test_tool_input_schemas_snapshot/
│   └── tool_input_schemas.json
├── test_static_descriptions_snapshot/
│   └── static_descriptions.json
├── test_static_descriptions_names_snapshot/
│   └── static_descriptions_names.json
└── test_static_descriptions_required_params_snapshot/
    └── static_descriptions_required_params.json
```

## Контрактные тесты (не snapshot)

Помимо snapshot тестов, есть контрактные тесты в `TestToolContractSync`:
- `test_same_tool_names_in_static_and_handler` — синхронизация static и handler
- `test_descriptions_not_empty` — все описания непустые
- `test_input_schema_has_type_object` — все inputSchema имеют type='object'
- `test_input_schema_has_properties` — все inputSchema имеют properties

Эти тесты проверяют инварианты, а не конкретные значения.

## Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| pytest-snapshot | >=0.9,<1.0 | Snapshot testing framework |

## CI Integration

Snapshot тесты запускаются в общем CI job `test`. При падении:
1. CI показывает diff между snapshot и фактическим значением
2. Если изменение осознанное — обновите snapshot локально
3. Закоммитьте обновлённый snapshot вместе с изменениями

**Важно:** CI НЕ обновляет snapshot автоматически — это осознанное действие разработчика.
