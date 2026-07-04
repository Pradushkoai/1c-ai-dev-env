#!/usr/bin/env python3
"""
Быстрый семантический поиск по методам 1С (без нейросети).

Тонкая CLI-обёртка над src.services.search (TF-IDF) и src.services.search_bm25 (BM25+триграммы).
По умолчанию используется BM25 (v2) — даёт более релевантные результаты.

Поддерживаемые алгоритмы:
  bm25   (по умолчанию) — BM25 + триграммы + стеммер. Версия индекса v2.
  tfidf  (legacy)       — TF-IDF с косинусным сходством. Версия индекса v1.
  hybrid                — то же что bm25, но явно включает триграммы.

Пример:
  python3 fast_search_1c.py build              # построить BM25 индекс (по умолчанию)
  python3 fast_search_1c.py build --algo tfidf # построить TF-IDF индекс (legacy)
  python3 fast_search_1c.py search "найти элемент справочника по коду"
  python3 fast_search_1c.py search "найти элемент по коду" --limit 5
  python3 fast_search_1c.py info               # информация об индексе
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Этап 1.2, Группа 4: sys.path.insert удалён — после pip install -e . не нужен.
# Fallback на paths.py для совместимости со старыми скриптами
try:
    from src.services.search import build_index as _build_tfidf
    from src.services.search import search as _search_tfidf
    from src.services.search import tokenize as _tokenize
    from src.services.search_bm25 import (
        build_index_bm25 as _build_bm25,
    )
    from src.services.search_bm25 import (
        detect_index_version as _detect_version,
    )
    from src.services.search_bm25 import (
        search_auto as _search_auto,
    )
    from src.services.search_bm25 import (
        search_bm25 as _search_bm25,
    )

    _HAS_SERVICE = True
except ImportError:
    _HAS_SERVICE = False

# Пути — через PathManager (P2.15: paths.py удалён как dead code)
from src.services.path_manager import PathManager

_pm = PathManager()
METHODS_JSON = _pm.syntax_helper_index_json
INDEX_FILE = _pm.fast_search_index


def build_index(algo: str = "bm25") -> None:
    """Построить индекс всех методов 1С."""
    if not METHODS_JSON.exists():
        print(f"❌ Нет файла методов: {METHODS_JSON}")
        print("   Сначала запустите: python3 scripts/build_syntax_helper_index.py")
        sys.exit(1)

    print(f"Загружаю методы из {METHODS_JSON}...")
    print(f"Алгоритм: {algo}")

    t0 = time.time()
    if algo == "tfidf":
        count = _build_tfidf(METHODS_JSON, INDEX_FILE)
    else:
        # bm25 / hybrid — обе используют BM25 индекс
        count = _build_bm25(METHODS_JSON, INDEX_FILE)
    t1 = time.time()

    size_kb = os.path.getsize(INDEX_FILE) // 1024
    print(f"✅ Индекс построен: {count} методов за {t1 - t0:.1f} сек")
    print(f"   Файл: {INDEX_FILE} ({size_kb} КБ)")
    if algo != "tfidf":
        print("   Версия индекса: v2 (BM25 + триграммы + стеммер)")
        print("   Гибридный поиск: BM25 (0.75) + триграммы (0.25)")
    else:
        print("   Версия индекса: v1 (TF-IDF, legacy)")


def search(query: str, limit: int = 10, algo: str = "auto") -> None:
    """Семантический поиск методов по описанию."""
    if not INDEX_FILE.exists():
        print(f"❌ Индекс не найден. Сначала запустите: python3 {sys.argv[0]} build")
        sys.exit(1)

    # Авто-определение алгоритма по версии индекса
    if algo == "auto":
        version = _detect_version(INDEX_FILE)
        if version == 2:
            results = _search_bm25(INDEX_FILE, query, limit, hybrid=True)
            algo_used = "bm25+hybrid"
        elif version == 1:
            results = _search_tfidf(INDEX_FILE, query, limit)
            algo_used = "tfidf (legacy)"
        else:
            print("❌ Не удалось определить версию индекса. Перестройте индекс.")
            sys.exit(1)
    elif algo == "bm25":
        results = _search_bm25(INDEX_FILE, query, limit, hybrid=True)
        algo_used = "bm25+hybrid"
    elif algo == "tfidf":
        results = _search_tfidf(INDEX_FILE, query, limit)
        algo_used = "tfidf"
    else:
        results = _search_auto(INDEX_FILE, query, limit)
        algo_used = "auto"

    print(f'Поиск: "{query}"')
    print(f"Алгоритм: {algo_used}")
    print(f"Найдено: {len(results)} результатов")
    print()

    for rank, r in enumerate(results, 1):
        print(f"{rank}. [{r['score']:.3f}] {r['name_ru']} ({r['name_en']})")
        print(f"   Контекст: {r['context']}")
        print(f"   Синтаксис: {r['syntax']}")
        if r["description"]:
            print(f"   Описание: {r['description']}")
        print()


def info() -> None:
    """Показать информацию об индексе."""
    if not INDEX_FILE.exists():
        print(f"❌ Индекс не найден. Сначала запустите: python3 {sys.argv[0]} build")
        return

    with open(INDEX_FILE, encoding="utf-8") as f:
        index = json.load(f)

    version = index.get("version", 1)
    algorithm = index.get("algorithm", "tfidf" if version == 1 else "bm25")

    print("Fast Search индекс:")
    print(f"  Версия:     v{version}")
    print(f"  Алгоритм:   {algorithm}")
    print(f"  Методов:    {index['total_methods']}")
    print(f"  Уникальных токенов: {len(index['idf'])}")

    if version == 2:
        bm25_params = index.get("bm25_params", {})
        print(f"  BM25 k1:    {bm25_params.get('k1', '?')}")
        print(f"  BM25 b:     {bm25_params.get('b', '?')}")
        print(f"  Триграмм:   {len(index.get('trigrams_index', {}))}")
        print(f"  Avg doc len: {index.get('avg_doc_length', 0):.1f} токенов")

    print(f"  Файл: {INDEX_FILE} ({os.path.getsize(INDEX_FILE) // 1024} КБ)")


def main() -> None:
    if not _HAS_SERVICE:
        print("❌ Не найдены сервисы поиска. Запустите install.sh.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="fast_search_1c.py",
        description="Семантический поиск по методам платформы 1С",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Построить индекс")
    p_build.add_argument(
        "--algo", choices=["bm25", "tfidf"], default="bm25", help="Алгоритм индексации (по умолчанию bm25)"
    )

    p_search = sub.add_parser("search", help="Поиск по запросу")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--limit", type=int, default=10, help="Кол-во результатов")
    p_search.add_argument(
        "--algo",
        choices=["auto", "bm25", "tfidf"],
        default="auto",
        help="Алгоритм поиска (по умолчанию auto — по версии индекса)",
    )

    sub.add_parser("info", help="Информация об индексе")

    args = parser.parse_args()

    if args.command == "build":
        build_index(algo=args.algo)
    elif args.command == "search":
        search(args.query, limit=args.limit, algo=args.algo)
    elif args.command == "info":
        info()


if __name__ == "__main__":
    main()
