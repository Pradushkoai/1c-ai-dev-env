# 1C AI Development Environment

> Среда для разработки на 1С с ИИ-ассистентом: синтакс-помощник, API-справочники, анализ кода, генерация объектов через JSON DSL.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# 2. Установить (интерактивно — спросит про .hbk и ZIP конфигурации)
bash install.sh

# 3. Проверить
python3 -m src.cli validate
python3 -m src.cli config list

# 4. Работать
python3 -m src.cli search "найти элемент по коду"
python3 -m src.cli bsl analyze data/configs/<name>/path/to/file.bsl
```

### Добавить конфигурацию

```bash
python3 -m src.cli config add --name ut11 --zip /path/to/ut11.zip --title "УТ 11"
# → Распакует в data/configs/ut11/
# → Построит derived/configs/ut11/index.md (индекс метаданных)
# → Построит derived/configs/ut11/api-reference.md (API-справочник)
```

### Программно (Python)

```python
from src.project import Project

project = Project()
project.config_manager.add_from_zip("erp", Path("erp.zip"), "1С:ERP")
project.config_manager.build("erp")
result = project.bsl_analyzer.analyze(Path("file.bsl"))
```

---

## Требования

| Зависимость | Версия | Зачем |
|-------------|--------|-------|
| Python | 3.10+ | Скрипты, поиск, индексация |
| Java | 17+ | BSL Language Server |
| git | любая | Клонирование репозиториев |
| unzip | любая | Распаковка ZIP и `.hbk` |

**Обязательные Python-зависимости** (`requirements.txt`):
```
v8unpack>=1.2.6
python-dotenv>=1.0.0
```

**Опциональные** (для RAG с нейросетевыми embeddings — `requirements-optional.txt`):
```
fastembed>=0.8.0
qdrant-client>=1.0.0
```

---

## Архитектура

4-слойная модель: `data/` → `derived/` → `tools/` → `runtime/`

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Команды

```bash
# Конфигурации
python3 -m src.cli config list                              # список
python3 -m src.cli config add --name X --zip Y              # добавить из ZIP
python3 -m src.cli config build --name X                    # индексы
python3 -m src.cli config build-all                         # все индексы

# Поиск
python3 -m src.cli search "найти элемент по коду"           # TF-IDF поиск

# Анализ .bsl
python3 -m src.cli bsl analyze <path>                       # полный анализ
python3 -m src.cli bsl baseline <path>                      # сохранить baseline
python3 -m src.cli bsl diff <path>                          # только новые ошибки

# Проверка
python3 -m src.cli validate                                 # проверить пути
```

---

## Инструменты

| Инструмент | Что даёт |
|------------|----------|
| [BSL Language Server](https://github.com/1c-syntax/bsl-language-server) v1.0.1 | Анализ `.bsl` кода (187 диагностик, `--diff` режим) |
| [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) | 94 скила: JSON DSL для метаданных, форм, расширений |
| [EDT-MCP](https://github.com/DitriXNew/EDT-MCP) | 168 проверок качества кода |
| [ai_rules_1c](https://github.com/comol/ai_rules_1c) | 28 правил разработки + 13 ролей |
| v8unpack | Распаковка `.cf`/`.cfe` без платформы 1С |
| TF-IDF Search | Семантический поиск по методам 1С (2 сек, без GPU) |
| hbk_extractor | Распаковка `.hbk` синтакс-помощника 1С |

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Содействие

См. [CONTRIBUTING.md](CONTRIBUTING.md)
