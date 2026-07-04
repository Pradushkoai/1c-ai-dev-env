# Demo Configuration

> Этап 7.1: минимальная конфигурация 1С для тестирования 1c-ai-dev-env.

Минимальная конфигурация для проверки работы 1c-ai-dev-env без
установленной 1С:Предприятие. Содержит:
- 1 справочник (Товары) с 2 реквизитами (Артикул, Цена)
- 1 документ (ПриходТовара) с табличной частью (Товары)

## Quickstart (5 команд от git clone до inspect)

```bash
# 1. Клонировать и установить
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env
pip install -e ".[dev,mcp]"

# 2. Добавить demo-конфигурацию
1c-ai config add --name demo --dir demo --title "Демо конфигурация"

# 3. Построить индексы
1c-ai config build --name demo

# 4. Проверить — inspect метаданных
1c-ai inspect meta demo/Catalogs/Товары/Товары.xml

# 5. Проверить BSL-анализатор
1c-ai standards templates/bsl/processing_form_module.bsl
```

## Структура demo/

```
demo/
├── Configuration.xml          — метаданные конфигурации
├── Catalogs/
│   └── Товары/
│       └── Товары.xml         — справочник Товары (Артикул, Цена)
└── Documents/
    └── ПриходТовара/
        └── ПриходТовара.xml   — документ ПриходТовара (таб. часть Товары)
```

## Что можно делать с demo

```bash
# Inspect конфигурации
1c-ai inspect cf demo/Configuration.xml

# Inspect справочника
1c-ai inspect meta demo/Catalogs/Товары/Товары.xml

# Поиск по метаданным
1c-ai search-code "Товары" --config demo

# BSL анализ
1c-ai solve check templates/bsl/processing_form_module.bsl --level standard

# DSL компиляция (создать новый справочник из JSON)
1c-ai dsl meta --json-file examples/catalog_example.json --output-dir /tmp/output

# Сравнение конфигураций (diff)
1c-ai inspect depgraph demo/ --name demo
```

## Smoke-тест

```bash
# Проверить, что demo работает
python3 -m pytest tests/test_smoke.py::TestSmokePathManager -v
```

## Примечания

- Demo-конфигурация минимальна (2 объекта) — для тестирования API
- Для реальных задач используйте полную выгрузку (УТ11, БСП, и т.д.)
- Demo не содержит CommonModules, Forms, Subsystems — только Catalog + Document
- Добавьте demo-конфигурацию через `1c-ai config add --name demo --dir demo`
