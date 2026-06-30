# API Documentation

## Programmatic Usage (Python)

### Project — главный оркестратор

```python
from src.project import Project

project = Project()

# Конфигурации
configs = project.list_configs_info()           # список всех
info = project.get_config_info("ut11")           # информация об одной
methods = project.get_api_methods("ut11", "ОбщегоНазначения")  # методы модуля

# Поиск
results = project.search_methods("найти элемент по коду", limit=5)
# → [{score, name_ru, name_en, syntax, description, context}]

# Анализ BSL
result = project.bsl_analyzer.analyze(Path("module.bsl"))
# → AnalysisResult(total=5, diagnostics=[...], by_code={...})

# Граф вызовов
from src.services.call_graph import build_call_graph
graph = build_call_graph("ut11", project.paths)
callers = graph.get_callers("ОбменДокументы", "ВыполнитьОбмен")
callees = graph.get_callees("ОбменДокументы", "ВыполнитьОбмен")
```

### ConfigManager — управление конфигурациями

```python
from src.services.config_manager import ConfigManager
from src.services.path_manager import PathManager

cm = ConfigManager(PathManager())

# Добавить из ZIP
cm.add_from_zip("ut11", Path("ut11.zip"), "УТ 11")

# Добавить из .cf
cm.add_from_cf("erp", Path("erp.cf"), "1С:ERP")

# Зарегистрировать существующую папку
cm.register_existing("ut11", Path("data/configs/ut11"), "УТ 11")

# Построить все 4 индекса
report = cm.build("ut11")
# → {"name": "ut11", "metadata": True, "api": True, "skd": True, "forms": True}

# Построить для всех
reports = cm.build_all()

# Удалить
cm.remove("ut11")
```

### MetadataExtractor — парсинг метаданных

```python
from metadata_extractor import MetadataExtractor, UniversalObjectParser, ConfigParser

# Полное извлечение
extractor = MetadataExtractor()
result = extractor.extract_all(Path("data/configs/ut11"))
# → {configuration, config_dump_info, objects, roles, subsystems,
#    event_subscriptions, scheduled_jobs, ext, stats}

# Парсинг одного объекта
parser = UniversalObjectParser()
obj = parser.parse(Path("Catalogs/Номенклатура.xml"))
# → {type: "Catalog", name: "Номенклатура", uuid: "...",
#    properties: {...}, child_objects: {attributes, tabular_sections, forms, commands}}

# Парсинг Configuration.xml
config_parser = ConfigParser()
config = config_parser.parse_configuration(Path("Configuration.xml"))
```

### SecurityAuditor — аудит безопасности

```python
from security_auditor import SecurityAuditor

auditor = SecurityAuditor()
violations = auditor.audit_file(Path("module.bsl"))
# → [SecurityViolation(rule_id='SEC001', severity='CRITICAL', line=42, ...)]

stats = auditor.get_stats(violations)
# → {total: 5, by_severity: {CRITICAL: 2, HIGH: 1, MEDIUM: 2}, by_rule: {...}}
```

### CodeMetricsAnalyzer — метрики кода

```python
from code_metrics import CodeMetricsAnalyzer

analyzer = CodeMetricsAnalyzer()
metrics = analyzer.analyze_file(Path("module.bsl"))
# → CodeMetrics(total_lines=100, code_lines=80, methods=[...],
#    total_cyclomatic=15, health_score=85.0, is_god_object=False, ...)

# Анализ директории
results = analyzer.analyze_path(Path("data/configs/ut11/CommonModules"))
summary = analyzer.get_summary(results)
```

### CodeGenerator — генерация кода

```python
from code_generator import generate_processing, generate_report

# Генерация обработки
result = generate_processing(
    name="ВыгрузкаНоменклатуры",
    synonym="Выгрузка номенклатуры",
    output_dir="/tmp/my_processing",
    description="Выгрузка номенклатуры в Excel",
    author="Иван Иванов",
)
# → {files: [...], stats: {total_files: 6, bsl_files: 2, ...}}

# Генерация отчёта на СКД
result = generate_report(
    name="ОтчетПоПродажам",
    synonym="Отчёт по продажам",
    output_dir="/tmp/my_report",
    data_source="Документ.РеализацияТоваровУслуг",
)
```

### KnowledgeBase — база знаний

```python
from src.services.knowledge_base import KnowledgeBase

kb = KnowledgeBase()
results = kb.search("справочник")
# → [{id: "create_catalog", title: "Создание справочника", score: 18, ...}]

item = kb.get_item("create_catalog")
# → {id, title, content: "...", category: "patterns"}
```

### MCP Server — программный запуск

```python
import asyncio
from src.mcp_server import run_mcp_server

asyncio.run(run_mcp_server())
```
