# Примеры использования MCP в IDE

> Этап 7.3: 5 типовых сценариев использования 1c-ai-dev-env через MCP.

## Настройка MCP

### Cursor / Claude Desktop

Добавьте в `mcp.json`:

```json
{
  "mcpServers": {
    "1c-ai": {
      "command": "1c-ai-mcp",
      "args": []
    }
  }
}
```

### VS Code / JetBrains

```bash
1c-ai mcp serve
```

---

## Сценарий 1: Анализ чужой конфигурации

**Задача:** Понять структуру незнакомой 1С-конфигурации.

**Шаги:**

1. Добавьте конфигурацию:
```bash
1c-ai config add --name ut11 --zip ut11.zip --title "УТ 11"
1c-ai config build --name ut11
```

2. В IDE вызовите MCP tools:

```
> list_configs
  → [{"name": "ut11", "title": "УТ 11", "active": true}]

> inspect cf /path/to/Configuration.xml
  → {"name": "УправлениеТорговлей", "version": "11.5.0", ...}

> get_object_structure --config_name ut11
  → {"Catalogs": 45, "Documents": 120, "InformationRegisters": 30, ...}
```

3. Найдите конкретный объект:

```
> search_code "ПриходТовара" --config ut11
  → [{"name": "Документ.ПриходТовара", "module": "ObjectModule", ...}]
```

**Результат:** Вы видите структуру конфигурации, количество объектов по типам,
можете найти любой объект по имени.

---

## Сценарий 2: Поиск антипаттернов

**Задача:** Найти проблемные места в BSL-коде.

**Шаги:**

1. Проверьте файл через все анализаторы:

```
> solve_check --file_path /path/to/module.bsl --level full
  → {
    "analyzers_run": ["check_1c_standards", "security_auditor", ...],
    "violations": [
      {"rule_id": "no-vypolnit", "severity": "error", "line": 42, ...},
      {"rule_id": "no-hardcoded-credentials", "severity": "error", ...},
      {"rule_id": "no-yo-in-code", "severity": "warning", ...}
    ]
  }
```

2. Проверьте безопасность отдельно:

```
> audit_security --file_path /path/to/module.bsl
  → {"critical_count": 2, "high_count": 3, "violations": [...]}
```

3. Проверьте архитектуру:

```
> analyze_architecture --config_dir /path/to/config
  → {"total_issues": 15, "by_severity": {"error": 3, "warning": 12}}
```

**Результат:** Вы нашли все антипаттерны, уязвимости и архитектурные проблемы.
Каждое нарушение содержит rule_id, severity, line, message.

---

## Сценарий 3: Генерация EPF

**Задача:** Создать внешнюю обработку .epf без установленной 1С.

**Шаги:**

1. Создайте BSL-модуль формы:

```bsl
#Область ПрограммныйИнтерфейс
#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
    // Добавьте код инициализации формы
КонецПроцедуры

#КонецОбласти
```

2. Сгенерируйте EPF через MCP:

```
> epf_factory_create
    --name "МояОбработка"
    --synonym "Моя обработка"
    --bsl_code "#Область ПрограммныйИнтерфейс..."
    --output_path /tmp/МояОбработка.epf
  → {
    "ok": true,
    "epf_path": "/tmp/МояОбработка.epf",
    "size_bytes": 12345,
    "proc_uuid": "abc-123",
    "round_trip_ok": true
  }
```

3. Проверьте BSL-код перед сборкой:

```
> validate_generated --source_dir /tmp/processing_src
  → {"verdict": "perfect", "total_errors": 0, "total_warnings": 0}
```

**Результат:** Готовый .epf файл с валидным BSL-кодом, новый UUID,
round-trip проверка пройдена.

---

## Сценарий 4: CFE diff

**Задача:** Понять, что расширение меняет в основной конфигурации.

**Шаги:**

1. Создайте diff расширения:

```
> cfe_diff --extension_path /path/to/ext --config_path /path/to/cfg
  → {
    "borrowed_objects": [
      {"type": "Catalog", "name": "Контрагенты", "adopted": true},
      {"type": "Document", "name": "РеализацияТоваровУслуг", "adopted": true}
    ],
    "patch_methods": [
      {"module": "Catalog.Контрагенты.ObjectModule", "method": "ПриЗаписи",
       "interceptor": "Before"},
      {"module": "Document.РеализацияТоваровУслуг.ObjectModule",
       "method": "ОбработкаПроведения", "interceptor": "After"}
    ]
  }
```

2. Создайте новый патч метода:

```
> cfe_patch_method
    --extension_path /path/to/ext
    --module_path "Catalog.Контрагенты.ObjectModule"
    --method_name "ПриЗаписи"
    --interceptor_type Before
  → {"bsl_file": ".../Module.bsl", "bsl_content": "&Перед..."}
```

**Результат:** Вы видите, какие объекты заимствованы, какие методы перехвачены,
можете добавить новый патч.

---

## Сценарий 5: СКД-трассировка

**Задача:** Понять, откуда берётся поле в отчёте на СКД.

**Шаги:**

1. Найдите СКД-схему:

```
> get_skd_schema --config_name ut11
  → [{"name": "ОтчетПоПродажам", "path": ".../Template.xml"}]
```

2. Трассируйте поле:

```
> skd_trace --template_path /path/to/Template.xml --name "Сумма"
  → {
    "field": "Сумма",
    "source": "РегистрНакопления.Продажи.Сумма",
    "path": ["DataSets[0].Fields[3]", "TotalFields[1]"],
    "filter_used": true
  }
```

**Результат:** Вы видите полную цепочку: поле "Сумма" берётся из регистра
накопления "Продажи", используется в наборе данных и итогах.

---

## Доступные MCP tools (45)

| Категория | Tools | Назначение |
|-----------|-------|------------|
| Конфигурации | list_configs, data_status | Управление конфигурациями |
| Поиск | search_1c_methods, search_code | BM25 поиск |
| BSL анализ | analyze_bsl, check_standards, audit_security, ... | 11 анализаторов |
| Метаданные | get_object_structure, get_skd_schema, ... | Парсинг метаданных |
| Качество | check_form_quality, diff_configs | Проверка качества |
| Генерация | generate_processing, build_epf, validate_generated | Кодогенерация |
| DSL | dsl_compile_meta, dsl_compile_form, ... | JSON -> XML |
| CFE | cfe_borrow, cfe_patch_method, cfe_diff | Расширения |
| Inspect | inspect | Единый анализ объектов |

Полный список: `1c-ai mcp tools` или [docs/MCP_INTEGRATION.md](MCP_INTEGRATION.md)

---

## Советы

1. **Начните с demo** — используйте `demo/` конфигурацию для первых шагов
2. **Используйте solve_context** — собирает контекст из 7 источников для LLM
3. **Проверяйте перед коммитом** — `solve_check --level standard` на .bsl файлах
4. **SARIF для CI** — `solve_check --sarif out.sarif` для GitHub Code Scanning
5. **Smoke-тесты** — `pytest -m smoke` для быстрой проверки (< 3 сек)
