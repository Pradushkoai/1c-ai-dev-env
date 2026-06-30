# 1C XML Specifications

Полная документация по XML-форматам 1С:Предприятие 8.3 — 18 файлов, ~16 000 строк.

## Источник

Спецификации скопированы из проекта 1c-ai-development-kit (MIT License, © Arman-Kudaibergenov).
Благодарность автору за уникальную работу по документированию XML-форматов 1С.

## Содержание

### Спецификации XML-форматов 1С (12 файлов)

- 1c-config-objects-spec.md — Все типы объектов метаданных (1801 строк)
- 1c-configuration-spec.md — Configuration.xml, ConfigDumpInfo (992)
- 1c-dcs-spec.md — Схема компоновки данных СКД/DCS (987)
- 1c-epf-spec.md — Внешние обработки EPF (785)
- 1c-erf-spec.md — Внешние отчёты ERF (628)
- 1c-extension-spec.md — Расширения CFE: ObjectBelonging, декораторы (962)
- 1c-form-spec.md — Управляемые формы Form.xml (1184)
- 1c-help-spec.md — Встроенная справка (151)
- 1c-role-spec.md — Роли и права Rights.xml, RLS (845)
- 1c-spreadsheet-spec.md — Табличные документы MXL (449)
- 1c-subsystem-spec.md — Подсистемы, группы команд (1022)
- 1c-specs-index.md — Единый индекс

### Спецификации JSON DSL (5 файлов)

- meta-dsl-spec.md — JSON DSL для метаданных, 23 типа (1085)
- form-dsl-spec.md — JSON DSL для форм (462)
- skd-dsl-spec.md — JSON DSL для СКД (790)
- mxl-dsl-spec.md — JSON DSL для MXL-макетов (160)
- role-dsl-spec.md — JSON DSL для ролей (112)

### Дополнительно

- build-spec.md — Сборка EPF/ERF/CF/CFE (357)

## Использование

Эти спецификации используются:
1. AI-ассистентами через MCP tool get_1c_xml_spec() — для точной структуры XML
2. Разработчиками как справочник по XML-форматам 1С
3. JSON DSL компиляторами (src/services/dsl_compiler.py) — как референс

## Лицензия

MIT License (как и весь проект).
