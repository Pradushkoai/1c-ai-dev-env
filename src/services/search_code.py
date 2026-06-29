"""
Поиск по коду конфигураций — BM25 по 115 666 методов.

Использует api-reference.json (уже готовые индексы) для поиска
экспортных методов конфигураций по имени, описанию, сигнатуре.

Пример:
    from src.services.search_code import search_code, build_code_index
    build_code_index("ut11")           # построить индекс (1-2 сек)
    results = search_code("ut11", "создать заказ")  # поиск
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .path_manager import PathManager
from .search_bm25 import tokenize_stemmed, BM25_K1, BM25_B


def _build_index_for_config(config_name: str, paths: PathManager) -> dict | None:
    """Построить BM25 индекс по методам одной конфигурации."""
    api_json = paths.config_api_reference_json(config_name)
    if not api_json.exists():
        return None

    with open(api_json, 'r', encoding='utf-8') as f:
        modules = json.load(f)

    documents = []
    doc_lengths = []

    for mod in modules:
        mod_name = mod.get('name', '')
        for method in mod.get('methods', []):
            method_name = method.get('name', '')
            method_type = method.get('type', '')
            signature = method.get('signature', '')
            description = method.get('description', '')
            returns = method.get('returns', '')

            # Документ = имя метода (×3 вес) + сигнатура + описание + возвращаемое
            doc_text = f'{method_name} {method_name} {method_name} {signature} {description} {returns}'
            tokens = tokenize_stemmed(doc_text)

            documents.append({
                'tokens': tokens,
                'module': mod_name,
                'name': method_name,
                'type': method_type,
                'signature': signature[:150],
                'description': description[:200],
                'returns': returns[:100],
            })
            doc_lengths.append(len(tokens))

    if not documents:
        return None

    # DF — document frequency
    df: dict[str, int] = defaultdict(int)
    for doc in documents:
        for t in set(doc['tokens']):
            df[t] += 1

    # IDF для BM25
    N = len(documents)
    idf_bm25 = {t: math.log(1 + (N - df_t + 0.5) / (df_t + 0.5)) for t, df_t in df.items()}

    # TF per doc
    tf_per_doc = [Counter(doc['tokens']) for doc in documents]

    # Инвертированный индекс
    inverted_index: dict[str, list] = defaultdict(list)
    for i, tf in enumerate(tf_per_doc):
        for t, tf_val in tf.items():
            inverted_index[t].append((i, tf_val))

    # Удаляем tokens
    for doc in documents:
        del doc['tokens']

    avg_doc_length = sum(doc_lengths) / max(N, 1)

    return {
        'version': 2,
        'algorithm': 'bm25_code',
        'config': config_name,
        'documents': documents,
        'idf': idf_bm25,
        'inverted_index': dict(inverted_index),
        'doc_lengths': {i: length for i, length in enumerate(doc_lengths)},
        'avg_doc_length': avg_doc_length,
        'total_methods': N,
    }


def _bm25_score(tf: int, idf: float, doc_length: float, avg_length: float) -> float:
    """BM25 score для одного термина."""
    norm = (1 - BM25_B) + BM25_B * (doc_length / max(avg_length, 1))
    return idf * (tf * (BM25_K1 + 1)) / (tf + BM25_K1 * norm)


def search_code(config_name: str, query: str, limit: int = 10, paths: PathManager | None = None) -> list[dict[str, Any]]:
    """
    BM25 поиск по методам конфигурации.

    Args:
        config_name: Имя конфигурации (ut11, edo2, edo3, unp)
        query: Поисковый запрос
        limit: Кол-во результатов
        paths: PathManager (если None — создаётся)

    Returns:
        [{score, module, name, type, signature, description, returns}]
    """
    if paths is None:
        paths = PathManager()

    # Проверяем кэш индекса
    index_path = paths.config_derived_dir(config_name) / 'code-search-index.json'

    if not index_path.exists():
        # Строим индекс
        index_data = _build_index_for_config(config_name, paths)
        if index_data is None:
            return []
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False)
    else:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)

    documents = index_data['documents']
    idf = index_data['idf']
    inverted_index = index_data['inverted_index']
    doc_lengths = index_data.get('doc_lengths', {})
    avg_doc_length = index_data.get('avg_doc_length', 1.0)

    # Токенизуем запрос
    query_tokens = tokenize_stemmed(query)
    if not query_tokens:
        return []

    # BM25 scoring
    bm25_scores: dict[int, float] = defaultdict(float)
    query_tf = Counter(query_tokens)

    for t, q_tf in query_tf.items():
        if t not in inverted_index:
            continue
        idf_t = idf.get(t, 0)
        for doc_id, doc_tf in inverted_index[t]:
            doc_len = doc_lengths.get(str(doc_id), doc_lengths.get(doc_id, avg_doc_length))
            score = _bm25_score(doc_tf, idf_t, doc_len, avg_doc_length)
            bm25_scores[doc_id] += score

    ranked = sorted(bm25_scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for doc_id, score in ranked:
        m = documents[doc_id]
        results.append({
            'score': round(score, 4),
            'module': m['module'],
            'name': m['name'],
            'type': m['type'],
            'signature': m['signature'],
            'description': m['description'],
            'returns': m['returns'],
        })

    return results
