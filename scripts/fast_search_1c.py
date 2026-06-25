#!/usr/bin/env python3
"""
Быстрый семантический поиск по методам 1С (без нейросети).

Использует TF-IDF + косинусное сходство на основе токенов.
Работает за секунды, не требует загрузки моделей.

Пример:
  python3 fast_search_1c.py build    # построить индекс (1 сек)
  python3 fast_search_1c.py search "найти элемент справочника по коду"
"""

import json
import os
import os
import sys
import re
import math
from collections import defaultdict, Counter
from datetime import datetime

# Пути из единого конфига
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import PATHS
METHODS_JSON = PATHS.syntax_helper_index_json
INDEX_FILE = PATHS.fast_search_index


def tokenize(text):
    """Токенизация текста — разбиваем на слова, нормализуем."""
    # Удаляем пунктуацию, разделяем по словам
    tokens = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', text.lower())
    # Также добавим CamelCase разбиение
    result = []
    for t in tokens:
        result.append(t)
        # Разбиваем CamelCase: НайтиПоКоду → найти, по, коду
        parts = re.findall(r'[А-ЯA-Z]?[а-яёa-z]+|[А-ЯA-Z]+(?=[А-ЯA-Z][а-яёa-z])|\d+', t)
        if len(parts) > 1:
            result.extend(p.lower() for p in parts)
    return result


def build_index():
    """Построить TF-IDF индекс всех методов 1С."""
    print(f'Загружаю методы из {METHODS_JSON}...')
    with open(METHODS_JSON, 'r', encoding='utf-8') as f:
        methods = json.load(f)
    print(f'Загружено {len(methods)} методов')

    # Подготовим документы для индексации
    documents = []
    for i, m in enumerate(methods):
        name_ru = m.get('name_ru', '')
        name_en = m.get('name_en', '')
        context = m.get('context', '')
        syntax = m.get('syntax', '')
        description = m.get('description', '')
        returns = m.get('returns', '')
        
        # Объединяем всё в один текстовый документ
 # даём больший вес имени метода (повторяем)
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

    # Построим инвертированный индекс и IDF
    print('Строю TF-IDF индекс...')
    
    # DF — document frequency для каждого токена
    df = defaultdict(int)
    for doc in documents:
        unique_tokens = set(doc['tokens'])
        for t in unique_tokens:
            df[t] += 1
    
    # IDF
    N = len(documents)
    idf = {t: math.log(N / df_t) for t, df_t in df.items()}
    
    # TF-IDF векторы (как словарь token → weight)
    for doc in documents:
        tf = Counter(doc['tokens'])
        doc['tfidf'] = {t: tf_t * idf.get(t, 0) for t, tf_t in tf.items()}
        # Нормализуем (L2)
        norm = math.sqrt(sum(w**2 for w in doc['tfidf'].values()))
        if norm > 0:
            doc['tfidf'] = {t: w / norm for t, w in doc['tfidf'].items()}
    
    # Инвертированный индекс: token → список (doc_id, weight)
    inverted_index = defaultdict(list)
    for doc in documents:
        for t, w in doc['tfidf'].items():
            inverted_index[t].append((doc['id'], w))
    
    # Сохраняем индекс
    print('Сохраняю индекс...')
    
    # Убираем tokens (они больше не нужны)
    for doc in documents:
        del doc['tokens']
    
    index_data = {
        'methods': documents,
        'idf': idf,
        'inverted_index': dict(inverted_index),
        'total_methods': len(documents),
        'built_at': datetime.now().isoformat(),
    }
    
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False)
    
    print(f'✅ Индекс построен: {len(documents)} методов')
    print(f'Уникальных токенов: {len(idf)}')
    print(f'Файл: {INDEX_FILE} ({os.path.getsize(INDEX_FILE) // 1024} КБ)')


def search(query, limit=10):
    """Семантический поиск методов по описанию."""
    if not os.path.exists(INDEX_FILE):
        print(f'❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build')
        sys.exit(1)
    
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    methods = index['methods']
    idf = index['idf']
    inverted_index = index['inverted_index']
    
    # Токенизуем запрос
    query_tokens = tokenize(query)
    if not query_tokens:
        print('Пустой запрос')
        return
    
    # TF-IDF для запроса
    query_tf = Counter(query_tokens)
    query_tfidf = {}
    for t, tf in query_tf.items():
        if t in idf:
            query_tfidf[t] = tf * idf[t]
    
    # Нормализуем запрос
    norm = math.sqrt(sum(w**2 for w in query_tfidf.values()))
    if norm > 0:
        query_tfidf = {t: w / norm for t, w in query_tfidf.items()}
    
    # Косинусное сходство — через инвертированный индекс
    scores = defaultdict(float)
    for t, q_weight in query_tfidf.items():
        if t in inverted_index:
            for doc_id, doc_weight in inverted_index[t]:
                scores[doc_id] += q_weight * doc_weight
    
    # Сортируем
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
    
    print(f'Поиск: "{query}"')
    print(f'Найдено: {len(ranked)} результатов (из {len(methods)} методов)')
    print()
    
    for rank, (doc_id, score) in enumerate(ranked, 1):
        m = methods[doc_id]
        name_ru = m['name_ru']
        name_en = m['name_en']
        context = m['context'][:80]
        syntax = m['syntax'][:120]
        desc = m['description'][:150]
        
        print(f'{rank}. [{score:.3f}] {name_ru} ({name_en})')
        print(f'   Контекст: {context}')
        print(f'   Синтаксис: {syntax}')
        if desc:
            print(f'   Описание: {desc}')
        print()


def info():
    """Показать информацию об индексе."""
    if not os.path.exists(INDEX_FILE):
        print(f'❌ Индекс не найден. Сначала запусти: python3 {sys.argv[0]} build')
        return
    
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    print(f'Fast Search индекс:')
    print(f'  Методов: {index["total_methods"]}')
    print(f'  Уникальных токенов: {len(index["idf"])}')
    print(f'  Построен: {index["built_at"]}')
    print(f'  Файл: {INDEX_FILE} ({os.path.getsize(INDEX_FILE) // 1024} КБ)')


def main():
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
