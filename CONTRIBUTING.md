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
3. Коммить с понятными сообщениями
4. Создай PR с описанием изменений

## Стандарты кода

### Python скрипты
- Python 3.10+
- Импортируй `from paths import PATHS` для путей
- Используй argparse для CLI параметров
- Типы — через type hints

### Shell скрипты
- `#!/bin/bash` + `set -e`
- Используй `source paths.env` для путей

### Markdown
- Русский язык (основной)
- Таблицы для структурированных данных
- Emoji для навигации (✅ ❌ ⚠️ 🔴 🟡 🟢)

## Структура проекта

```
setup/           — что коммитится в GitHub
├── scripts/     — рабочие скрипты
├── templates/   — шаблоны runtime файлов
├── configs/     — конфигурационные файлы
├── docs/        — документация
├── .github/     — GitHub templates
├── install.sh   — установщик
├── manifest.json — реестр компонентов
└── requirements.txt
```
