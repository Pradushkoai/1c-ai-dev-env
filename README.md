# 1C AI Development Environment

> Среда разработки 1С с ИИ-ассистентом: синтакс-помощник, API справочники, анализ кода, генерация объектов через JSON DSL

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Java 17+](https://img.shields.io/badge/Java-17+-orange.svg)](https://openjdk.org/)
[![BSL LS 1.0.1](https://img.shields.io/badge/BSL%20LS-1.0.1-green.svg)](https://github.com/1c-syntax/bsl-language-server)

## Возможности

- **8 141 методов** платформы 1С (синтакс-помощник из .hbk)
- **API справочники** типовых конфигураций (УТ11: 16 654 метода, УНП: 53 085)
- **BSL Language Server** v1.0.1 — анализ .bsl кода с diff-режимом
- **94 скила** (JSON DSL для метаданных, форм, расширений)
- **355 проверок** кода (187 BSL LS + 168 EDT-MCP)
- **TF-IDF поиск** по методам 1С (2 секунды, без нейросети)
- **v8unpack** — распаковка .cf/.cfe без платформы 1С
- **Role-switching protocol** — 4 роли: Архитектор → Программист → Ревьюер → Документатор
- **Learning loop** — авто-создание skills из опыта

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env/setup

# 2. Установить
./install.sh
# install.sh спросит про .hbk и ZIP конфигурации

# 3. Работать
python3 scripts/register_config.py list
python3 scripts/fast_search_1c.py search "найти по коду"
scripts/bsl-analyze.sh data/configs/<name>/path/to/file.bsl
```

## Требования

| Зависимость | Версия | Зачем |
|-------------|--------|-------|
| Python | 3.10+ | Скрипты, поиск, индексация |
| Java | 17+ | BSL Language Server |
| git | any | Клонирование репозиториев |
| unzip | any | Распаковка ZIP и .hbk |

## Структура

См. [ARCHITECTURE.md](docs/ARCHITECTURE.md) — 4-слойная модель (data → derived → tools → runtime).

## Команды

```bash
# Управление конфигурациями
python3 scripts/register_config.py list                    # список
python3 scripts/register_config.py add --name X --zip Y    # добавить
python3 scripts/register_config.py build --name X           # индексы
python3 scripts/register_config.py build-all                # все индексы

# Поиск
python3 scripts/fast_search_1c.py search "найти элемент по коду"
grep "ИмяМетода" derived/configs/<name>/api-reference.md

# Анализ .bsl
scripts/bsl-analyze.sh <path>
scripts/bsl-analyze.sh --baseline <path>  # сохранить baseline
scripts/bsl-analyze.sh --diff <path>      # только новые ошибки

# Создание объектов (JSON DSL)
python3 tools/repos/claude-code-skills-1c/skills/1c-meta-compile/scripts/meta-compile.py \
  -JsonPath /tmp/catalog.json -OutputDir data/configs/<name>
```

## Форки

Все 16 внешних репозиториев форкнуты в `github.com/Pradushkoai/*` для устойчивости к удалению.

## Лицензия

MIT — см. [LICENSE](LICENSE)

## Содействие

См. [CONTRIBUTING.md](CONTRIBUTING.md)
