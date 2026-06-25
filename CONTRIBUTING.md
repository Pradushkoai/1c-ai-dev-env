# Contributing to 1C AI Development Environment

Спасибо за интерес к проекту! Любой вклад приветствуется.

## Как внести вклад

### Сообщение об ошибке
1. Проверь существующие issues — возможно уже есть
2. Создай новый issue с шаблоном (описание, шаги, ожидание, реальность)

### Предложение улучшения
1. Создай issue с меткой `enhancement`
2. Опиши что улучшить и зачем

### Pull Request
1. Fork репозитория
2. Создай ветку: `git checkout -b feature/my-feature`
3. **Запусти тесты локально** (см. ниже) — все должны проходить
4. Если добавляешь новый функционал — добавь тесты
5. Коммить с понятными сообщениями
6. Создай PR с описанием изменений

## Разработка

### Установка окружения

```bash
git clone https://github.com/Pradushkoai/1c-ai-dev-env.git
cd 1c-ai-dev-env

# Установка пакета (editable mode + dev-зависимости, включая pytest)
pip install -e ".[dev]"

# Или полная установка через install.sh (клонирует git-репозитории, BSL LS, и т.д.)
bash install.sh --non-interactive
```

### Запуск тестов

```bash
# Все тесты
python3 -m pytest tests/ -v

# Конкретный модуль
python3 -m pytest tests/test_config_manager.py -v

# С покрытием (если установлен pytest-cov)
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

Тесты **не требуют** Java/BSL LS/внешних скриптов — все внешние вызовы замокированы через `unittest.mock.patch`. Полный прогон занимает <1 секунды.

После `pip install -e .` пакет `src` доступен для импорта без sys.path хаков.

### Что покрывают тесты

| Файл | Что тестирует |
|------|--------------|
| `test_path_manager.py` | Поиск paths.env вверх, 4 слоя архитектуры, env-подстановка |
| `test_config_manager.py` | add_from_zip (success/duplicate/not_found/bad_zip), build с mock subprocess, archive/activate цикл |
| `test_bsl_analyzer.py` | Парсинг BSL LS JSON, персистентность baseline между вызовами CLI |
| `test_fast_search.py` | TF-IDF: tokenize (CamelCase, mixed), build_index + search, limit |
| `test_configuration.py` | Configuration model: from_dict, to_dict, is_active, common_modules_dir |
| `test_hbk_extractor_full.py` | parse_hbk_file на синтетическом .hbk, extract_file_data (deflate/store) |
| `test_build_api_reference.py` | Парсинг .bsl (Процедура/Функция Экспорт), parse_comment_block, parse_module_xml |
| `test_hbk_extractor.py` | Базовая проверка PK-сигнатуры |

### Добавление новых тестов

1. Создай `tests/test_<module>.py`
2. Используй `tmp_path` fixture для временных файлов — не пиши в `/tmp` напрямую
3. Мокай внешние вызовы через `unittest.mock.patch`:
   ```python
   from unittest.mock import patch, MagicMock
   with patch("src.services.config_manager.subprocess.run") as mock_run:
       mock_run.return_value = MagicMock(returncode=0)
       # твой код
   ```
4. Импортируй через `from src.<module> import <name>` (после `pip install -e .`)

## Стандарты кода

### Python скрипты
- Python 3.10+
- **Используй `PathManager`** из `src.services.path_manager` — НЕ `paths.py` (он deprecated)
- Типы — через type hints (`from __future__ import annotations` для | None синтаксиса)
- Для CLI — argparse, единая точка входа `python3 -m src.cli`
- Для нового кода — `logging` вместо `print` для диагностических сообщений

### Shell скрипты
- `#!/bin/bash` + `set -e`
- Используй `source paths.env` для путей в shell

### Markdown
- Русский язык (основной)
- Таблицы для структурированных данных
- Emoji для навигации (✅ ❌ ⚠️ 🔴 🟡 🟢)

## Структура проекта

```
setup/                — что коммитится в GitHub
├── src/             — OOP-пакет (models/, services/, project.py, cli.py)
├── scripts/          — standalone-скрипты (build_api_reference, hbk_extractor, ...)
├── tests/            — pytest-тесты (50+ тестов)
├── templates/        — шаблоны runtime файлов
├── docs/             — документация (ARCHITECTURE.md)
├── .github/          — CI + issue/PR templates
├── install.sh        — установщик
├── pyproject.toml    — упаковка пакета + 1c-ai CLI entry point
├── manifest.json     — реестр компонентов
├── requirements.txt           — обязательные Python-зависимости
├── requirements-optional.txt  — опциональные (RAG с embeddings)
└── requirements-dev.txt       — для разработки (pytest)
```

После `pip install -e .` пакет `src/` доступен для импорта через `from src.services...`, а команда `1c-ai` доступна глобально.

## CI

GitHub Actions (`.github/workflows/ci.yml`) запускается на каждый push/PR:
1. Установка зависимостей (`requirements.txt` + `requirements-dev.txt`)
2. Проверка синтаксиса всех Python файлов (`py_compile`)
3. Запуск `pytest tests/`

PR не может быть смёрджен, если CI красный.
