# 1C AI Development Environment

> Среда для разработки на 1С с ИИ-ассистентом: синтакс-помощник, API-справочники, анализ кода, генерация объектов через JSON DSL.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)

---

## Содержание

- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [Требования](#требования)
- [Архитектура](#архитектура)
- [Команды](#команды)
- [Инструменты](#инструменты)
- [Лицензия](#лицензия)

---

## Что это

Проект превращает чат с ИИ в полноценную среду разработки 1С. Не нужно копировать код туда-сюда — ИИ видит конфигурацию, знает API методов, проверяет код по стандартам.

**Возможности:**

| Что | Сколько |
|-----|---------|
| Методов платформы 1С (синтакс-помощник из `.hbk`) | 8 141 |
| API-методов типовых конфигураций | 16 654 (УТ11) + 53 085 (УНП) |
| Проверок качества кода | 355 (187 BSL LS + 168 EDT-MCP) |
| Скилов для генерации объектов (JSON DSL) | 94 |
| Ролей в role-switching protocol | 4 (Архитектор → Программист → Ревьюер → Документатор) |

---

## Быстрый старт

### Шаг 1. Установить

```bash
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env/setup
./install.sh
```

`install.sh` спросит:
1. **`.hbk` файлы** (синтакс-помощник) — распакует и проиндексирует 8 141 методов
2. **ZIP выгрузку конфигурации** — распакует, зарегистрирует, построит индекс метаданных + API-справочник

### Шаг 2. Проверить

```bash
python3 -m src.cli validate
python3 -m src.cli config list
```

### Шаг 3. Работать

```bash
# Добавить ещё конфигурацию
python3 -m src.cli config add --name erp --zip /path/to/erp.zip --title "1С:ERP"

# Построить индексы
python3 -m src.cli config build --name erp

# Искать метод по описанию
python3 -m src.cli search "найти элемент по коду"

# Анализ .bsl файла
python3 -m src.cli bsl analyze data/configs/priemka/DataProcessors/...

# Анализ с diff (только новые ошибки после редактирования)
python3 -m src.cli bsl baseline data/configs/priemka/...
# ... редактируем ...
python3 -m src.cli bsl diff data/configs/priemka/...
```

### Шаг 4. Программно (Python)

```python
from src.project import Project

project = Project()

# Список конфигураций
for cfg in project.list_configs():
    print(f"{cfg.name}: v{cfg.version}, {cfg.objects_count} объектов")

# Добавить новую
project.config_manager.add_from_zip("erp", Path("erp.zip"), "1С:ERP")
project.config_manager.build("erp")

# Анализ кода
result = project.bsl_analyzer.analyze(Path("file.bsl"))
print(f"Диагностик: {result.total}")
```

---

## Требования

| Зависимость | Версия | Зачем |
|-------------|--------|-------|
| Python | 3.10+ | Скрипты, поиск, индексация |
| Java | 17+ | BSL Language Server |
| git | любая | Клонирование репозиториев |
| unzip | любая | Распаковка ZIP и `.hbk` |

Python-зависимости (`requirements.txt`):
```
v8unpack>=1.2.6
python-dotenv>=1.0.0
fastembed>=0.8.0
qdrant-client>=1.0.0
```

---

## Архитектура

4-слойная модель с чётким разделением ответственности:

```
project/
├── data/              Исходные данные (от пользователя)
│   ├── configs/       Конфигурации 1С (распакованные)
│   ├── archives/      ZIP-архивы
│   └── hbk/           Исходные .hbk файлы
│
├── derived/           Производные (генерируются скриптами)
│   ├── configs/       Индексы по конфигурациям
│   └── platform/      Индексы платформы 1С
│
├── tools/             Инструменты
│   ├── repos/         Git-репозитории (клонируются)
│   └── bsl-ls/        BSL Language Server
│
├── runtime/           Рабочие файлы
│   ├── paths.env      Конфиг путей
│   ├── paths.py       Python-модуль путей
│   └── ...            session-resume, soul, worklog
│
├── src/               ООП-приложение
│   ├── models/        Configuration, ConfigurationRegistry
│   ├── services/      PathManager, ConfigManager, BSLAnalyzer
│   ├── project.py     Project (оркестратор)
│   └── cli.py         Единый CLI
│
└── setup/             Что коммитится в GitHub
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Команды

### Управление конфигурациями

```bash
python3 -m src.cli config list                              # список
python3 -m src.cli config add --name X --zip Y              # добавить из ZIP
python3 -m src.cli config build --name X                    # индексы для одной
python3 -m src.cli config build-all                         # индексы для всех
```

### Поиск

```bash
python3 -m src.cli search "найти элемент по коду"           # семантический поиск
grep "ИмяМетода" derived/configs/<name>/api-reference.md    # grep по API
```

### Анализ .bsl

```bash
python3 -m src.cli bsl analyze <path>                       # полный анализ
python3 -m src.cli bsl baseline <path>                      # сохранить baseline
python3 -m src.cli bsl diff <path>                          # только новые ошибки
```

### Проверка окружения

```bash
python3 -m src.cli validate                                 # проверить пути
```

---

## Инструменты

| Инструмент | Что даёт |
|------------|----------|
| [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) v1.0.1 | Анализ `.bsl` кода (187 диагностик, `--diff` режим) |
| [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) | 94 скила: JSON DSL для метаданных, форм, расширений |
| [EDT-MCP](https://github.com/DitriXNew/EDT-MCP) | 168 проверок качества кода |
| [ai_rules_1c](https://github.com/comol/ai_rules_1c) | 28 правил разработки + 13 ролей субагентов |
| v8unpack | Распаковка `.cf`/`.cfe` без платформы 1С |
| TF-IDF Search | Семантический поиск по 8 141 методам 1С (2 сек, без нейросети) |
| hbk_extractor | Распаковка `.hbk` синтакс-помощника 1С |

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Содействие

См. [CONTRIBUTING.md](CONTRIBUTING.md)
