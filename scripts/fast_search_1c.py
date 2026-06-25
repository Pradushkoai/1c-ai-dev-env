#!/usr/bin/env python3
"""
Быстрый семантический поиск по методам 1С (без нейросети).

Тонкая CLI-обёртка над src.services.search.
Логика TF-IDF живёт в едином сервисе, чтобы не дублировать её с cli.py.

Пример:
  python3 fast_search_1c.py build    # построить индекс (1 сек)
  python3 fast_search_1c.py search "найти элемент справочника по коду"
  python3 fast_search_1c.py info
"""

import os
import sys
import json
from pathlib import Path

# Подключаем src/ — там лежит сервис поиска
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fallback на paths.py для совместимости со старыми скриптами
try:
    from src.services.search import build_index as _build_index, search as _search, tokenize as _tokenize
    _HAS_SERVICE = True
except ImportError:
    _HAS_SERVICE = False

# Пути — через PathManager если есть, иначе через paths.py
try:
    from src.services.path_manager import PathManager
    _pm = PathManager()
    METHODS_JSON = _pm.syntax_helper_index_json
    INDEX_FILE = _pm.fast_search_index
except ImportError:
    sys.path.insert(0, str(PROJECT_ROOT / "runtime"))
    from paths import PATHS
    METHODS_JSON = Path(PATHS.syntax_helper_index_json)
    INDEX_FILE = Path(PATHS.fast_search_index)


def build_index():
    """Построить TF-IDF индекс всех методов 1С."""
    if not METHODS_JSON.exists():
        print(f'❌ Нет файла методов: {METHODS_JSON}')
        print('   Сначала запусти: python3 scripts/build_syntax_helper_index.py')
        sys.exit(1)

    print(f'Загружаю методы из {METHODS_JSON}...')
    count = _build_index(METHODS_JSON, INDEX_FILE)
    print(f'✅ Индекс построен: {count} методов')
    print(f'Файл: {INDEX_FILE} ({os.path.getsize(INDEX_FILE) // 1024} КБ)')


def search(query, limit=10):
    """Семантический поиск методов по описанию."""
    if not INDEX_FILE.exists():
        print(f'❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build')
        sys.exit(1)

    results = _search(INDEX_FILE, query, limit=limit)

    print(f'Поиск: "{query}"')
    print(f'Найдено: {len(results)} результатов')
    print()

    for rank, r in enumerate(results, 1):
        print(f'{rank}. [{r["score"]:.3f}] {r["name_ru"]} ({r["name_en"]})')
        print(f'   Контекст: {r["context"]}')
        print(f'   Синтаксис: {r["syntax"]}')
        if r['description']:
            print(f'   Описание: {r["description"]}')
        print()


def info():
    """Показать информацию об индексе."""
    if not INDEX_FILE.exists():
        print(f'❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build')
        return

    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        index = json.load(f)

    print(f'Fast Search индекс:')
    print(f'  Методов: {index["total_methods"]}')
    print(f'  Уникальных токенов: {len(index["idf"])}')
    print(f'  Построен: {index.get("built_at", "?")}')
    print(f'  Файл: {INDEX_FILE} ({os.path.getsize(INDEX_FILE) // 1024} КБ)')


def main():
    if not _HAS_SERVICE:
        print('❌ Не найден src.services.search. Запустите install.sh.')
        sys.exit(1)

    if len(sys.argv) < 2:
        print('Использование:')
        print(f'  python3 {sys.argv[0]} build              — построить индекс')
        print(f'  python3 {sys.argv[0]} search "<запрос>"  — семантический поиск')
        print(f'  python3 {sys.argv[0]} info               — информация об индексе')
        sys.exit(1)

    command = sys.argv[1]

    if command == 'build':
        build_index()
    elif command == 'search':
        if len(sys.argv) < 3:
            print('Укажи запрос: python3 fast_search_1c.py search "найти элемент по коду"')
            sys.exit(1)
        search(sys.argv[2])
    elif command == 'info':
        info()
    else:
        print(f'Неизвестная команда: {command}')
        sys.exit(1)


if __name__ == '__main__':
    main()
