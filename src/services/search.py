"""
Семантический TF-IDF поиск по методам 1С.
Единая реализация — используется и в CLI, и в скриптах.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional


def tokenize(text: str) -> list[str]:
    """Токенизация текста — разбиваем на слова, нормализуем."""
    tokens = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', text.lower())
    result = []
    for t in tokens:
        result.append(t)
        # CamelCase разбиение: НайтиПоКоду → найти, по, коду
        parts = re.findall(r'[А-ЯA-Z]?[а-яёa-z]+|[А-ЯA-Z]+(?=[А-ЯA-Z][а-яёa-z])|\d+', t)
        if len(parts) > 1:
            result.extend(p.lower() for p in parts)
    return result


def build_index(methods_json_path: Path, output_path: Path) -> int:
    """
    Построить TF-IDF индекс.

    Args:
        methods_json_path: Путь к syntax-helper-index.json
        output_path: Куда сохранить индекс

    Returns:
        Кол-во проиндексированных методов
    """
    with open(methods_json_path, 'r', encoding='utf-8') as f:
        methods = json.load(f)

    # Подготовим документы
    documents = []
    for i, m in enumerate(methods):
        name_ru = m.get('name_ru', '')
        name_en = m.get('name_en', '')
        context = m.get('context', '')
        syntax = m.get('syntax', '')
        description = m.get('description', '')
        returns = m.get('returns', '')

        # Имя метода — больший вес (повторяем)
        doc_text = f'{name_ru} {name_ru} {name_en} {name_en} {context} {syntax} {description} {returns}'
        tokens = tokenize(doc_text)

        documents.append({
            'id': i,
            'tokens': tokens,
            'name_ru': name_ru,
            'name_en': name_en,
            'context': context,
            'syntax': syntax,
            'description': description[:300],
            'returns': returns[:200],
            'file': m.get('file', ''),
        })

    # DF — document frequency
    df: dict[str, int] = defaultdict(int)
    for doc in documents:
        for t in set(doc['tokens']):
            df[t] += 1

    # IDF
    N = len(documents)
    idf = {t: math.log(N / df_t) for t, df_t in df.items()}

    # TF-IDF векторы
    for doc in documents:
        tf = Counter(doc['tokens'])
        doc['tfidf'] = {t: tf_t * idf.get(t, 0) for t, tf_t in tf.items()}
        norm = math.sqrt(sum(w ** 2 for w in doc['tfidf'].values()))
        if norm > 0:
            doc['tfidf'] = {t: w / norm for t, w in doc['tfidf'].items()}

    # Инвертированный индекс
    inverted_index: dict[str, list] = defaultdict(list)
    for doc in documents:
        for t, w in doc['tfidf'].items():
            inverted_index[t].append((doc['id'], w))

    # Сохраняем
    for doc in documents:
        del doc['tokens']

    index_data = {
        'methods': documents,
        'idf': idf,
        'inverted_index': dict(inverted_index),
        'total_methods': len(documents),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False)

    return len(documents)


def search(index_path: Path, query: str, limit: int = 10) -> list[dict]:
    """
    Семантический поиск.

    Args:
        index_path: Путь к fast-search-index.json
        query: Поисковый запрос
        limit: Кол-во результатов

    Returns:
        Список результатов с score, name_ru, name_en, context, syntax, description
    """
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)

    methods = index['methods']
    idf = index['idf']
    inverted_index = index['inverted_index']

    # Токенизуем запрос
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # TF-IDF для запроса
    query_tf = Counter(query_tokens)
    query_tfidf = {t: tf * idf.get(t, 0) for t, tf in query_tf.items() if t in idf}

    norm = math.sqrt(sum(w ** 2 for w in query_tfidf.values()))
    if norm > 0:
        query_tfidf = {t: w / norm for t, w in query_tfidf.items()}

    # Косинусное сходство
    scores: dict[int, float] = defaultdict(float)
    for t, q_weight in query_tfidf.items():
        if t in inverted_index:
            for doc_id, doc_weight in inverted_index[t]:
                scores[doc_id] += q_weight * doc_weight

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for doc_id, score in ranked:
        m = methods[doc_id]
        results.append({
            'score': score,
            'name_ru': m['name_ru'],
            'name_en': m['name_en'],
            'context': m['context'][:80],
            'syntax': m['syntax'][:120],
            'description': m['description'][:150],
        })

    return results
