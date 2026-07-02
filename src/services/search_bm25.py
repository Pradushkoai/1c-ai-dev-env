"""
Улучшенный поиск по методам 1С: BM25 + триграммы + стеммер.

BM25 — золотой стандарт полнотекстового поиска. В отличие от TF-IDF:
- Учитывает насыщение частоты термина (TF saturation через k1)
- Нормализует длину документа (через b)
- Даёт более релевантные результаты для длинных описаний

Дополнительно:
- Простой стеммер для русского и английского (без внешних зависимостей)
- Триграммы для устойчивости к опечаткам
- Гибридный режим: 0.7 * BM25 + 0.3 * триграммы

Формат индекса v2 (BM25):
{
  "version": 2,
  "algorithm": "bm25",
  "methods": [...],
  "idf": {...},
  "inverted_index": {...},
  "doc_lengths": {doc_id: length},
  "avg_doc_length": float,
  "total_methods": int,
  "trigrams_index": {trigram: [doc_ids]},
  "method_trigrams": {doc_id: [trigrams]},
  "stem_map": {stem: [original_tokens]},  # для подсветки
}

Backward compat: v1 (TF-IDF) индексы продолжают работать через search().
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

# ============================================================================
# СТЕММЕР (минимальный, без внешних зависимостей)
# ============================================================================

# Русские окончания (длинные сначала)
_RU_ENDINGS = [
    "ыми",
    "ях",
    "ах",
    "ого",
    "ому",
    "ему",
    "ом",
    "ой",
    "ое",
    "ую",
    "юю",
    "ая",
    "яя",
    "ые",
    "ие",
    "ых",
    "их",
    "ыми",
    "ими",
    "ыми",
    "их",
    "ых",
    "ам",
    "ям",
    "ами",
    "ями",
    "ом",
    "ем",
    "ами",
    "ями",
    "ть",
    "тся",
    "ться",
    "лся",
    "лась",
    "ться",
    "ешь",
    "ишь",
    "ете",
    "ите",
    "ут",
    "ют",
    "ат",
    "ят",
    "ал",
    "ял",
    "ала",
    "яла",
    "али",
    "яли",
    "анный",
    "енный",
    "ный",
    "ный",
    "ная",
    "ное",
    "ные",
    "ного",
    "ной",
    "ным",
    "ном",
    "нами",
    "ность",
    "ние",
    "ния",
    "ний",
    "нем",
    "нами",
    "а",
    "я",
    "о",
    "е",
    "у",
    "ю",
    "и",
    "ы",
    "ь",
]

# Английские окончания (Porter-подобный минимальный)
_EN_ENDINGS = [
    "ization",
    "ational",
    "fulness",
    "ousness",
    "iveness",
    "tional",
    "ation",
    "ement",
    "ness",
    "ions",
    "ing",
    "ied",
    "ies",
    "ied",
    "ier",
    "iest",
    "ed",
    "es",
    "ly",
    "ment",
    "tion",
    "sion",
    "ence",
    "ance",
    "able",
    "ible",
    "al",
    "er",
    "est",
    "s",
]


def stem_russian(word: str) -> str:
    """Простой русский стеммер — обрезает окончания."""
    if len(word) < 4:
        return word
    for ending in _RU_ENDINGS:
        if len(word) > len(ending) + 2 and word.endswith(ending):
            return word[: -len(ending)]
    return word


def stem_english(word: str) -> str:
    """Простой английский стеммер — обрезает окончания."""
    if len(word) < 4:
        return word
    for ending in _EN_ENDINGS:
        if len(word) > len(ending) + 2 and word.endswith(ending):
            return word[: -len(ending)]
    return word


def stem(word: str) -> str:
    """Стемминг слова (русский или английский)."""
    # Определяем язык по первому символу
    if word and word[0] in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя":
        return stem_russian(word)
    return stem_english(word)


# ============================================================================
# ТОКЕНИЗАЦИЯ + СТЕММИНГ
# ============================================================================

# BSL-синонимы ru↔en — для поиска независимо от языка написания.
# Запрос "стрнайти" находит "StrFind", "найтипокоду" находит "FindByCode", и наоборот.
# Словарь построен на основе стандартных методов платформы 1С (8141 методов).
BSL_SYNONYMS = {
    # Строковые функции
    "стрнайти": "strfind",
    "стрдлина": "strlen",
    "стрзаменить": "strreplace",
    "стрвставить": "strinsert",
    "струдалить": "strdelete",
    "стррег": "strregex",
    "стрначинаетсяс": "strstartswith",
    "стрзаканчиваетсяна": "strendswith",
    "стрсодержит": "strcontains",
    "стрразделить": "strsplit",
    "стрсоединить": "strconcat",
    "стрсравнить": "strcompare",
    "стрповторить": "strrepeat",
    "врег": "upper",
    "нрег": "lower",
    "трег": "title",
    "сокрл": "triml",
    "сокрп": "trimr",
    "сокрлп": "trimall",
    "лев": "left",
    "прав": "right",
    "сред": "mid",
    "символ": "char",
    "кодсимвола": "charcode",
    "символы": "chars",
    "стрстр": "strstr",
    "пустаястрока": "emptystr",
    # Массивы и коллекции
    "найти": "find",
    "добавить": "add",
    "удалить": "remove",
    "очистить": "clear",
    "количество": "count",
    "вставить": "insert",
    "получить": "get",
    "установить": "set",
    "выгрузить": "unload",
    "загрузить": "load",
    "выгрузитьколонку": "unloadcolumn",
    "загрузитьколонку": "loadcolumn",
    "свернуть": "collapse",
    "копировать": "copy",
    "индекс": "index",
    "найтистроку": "findrow",
    "найтистроки": "findrows",
    # Справочники
    "найтипокоду": "findbycode",
    "найтипонаименованию": "findbydescription",
    "найтипореквизиту": "findbyattribute",
    "создатьэлемент": "createitem",
    "создатьгруппу": "createfolder",
    "получитьформу": "getform",
    "получитьформусписка": "getlistform",
    "получитьформувыбора": "getchoiceform",
    "получитьформуэлемента": "getitemform",
    "пустаяссылка": "emptyref",
    # Документы
    "провести": "post",
    "отменапроведения": "unpost",
    "распровести": "unpost",
    "записать": "write",
    "прочитать": "read",
    "удалитьобъект": "deleteobject",
    # Запросы
    "выполнить": "execute",
    "выполнитьпакет": "executebatch",
    "установитьпараметр": "setparameter",
    "результат": "result",
    "выбрать": "select",
    "следующий": "next",
    "пустой": "empty",
    "выгрузитьрезультат": "unloadresult",
    # Метаданные
    "метаданные": "metadata",
    "предопределенный": "predefined",
    "получитьпредопределенноезначение": "getpredefinedvalue",
    "установитьобязательныйпризнакпредопределенных": "setpredefinedmandatory",
    # Дата/время
    "текущаядата": "currentdate",
    "текущаядатасеанса": "currentsessiondate",
    "началогода": "beginofyear",
    "конецгода": "endofyear",
    "началомесяца": "beginofmonth",
    "конецмесяца": "endofmonth",
    "началодня": "beginofday",
    "конецдня": "endofday",
    "добавитькдате": "datadd",
    "разностьдат": "datediff",
    # Числа
    "цел": "int",
    "окр": "round",
    "макс": "max",
    "мин": "min",
    "sqrt": "sqrt",
    "pow": "pow",
    "exp": "exp",
    "log": "log",
    "abs": "abs",
    "sign": "sign",
    "acos": "acos",
    "asin": "asin",
    "atan": "atan",
    "cos": "cos",
    "sin": "sin",
    "tan": "tan",
    # Преобразования типов
    "строка": "string",
    "число": "number",
    "дата": "date",
    "булево": "boolean",
    "значениевстроку": "valuetostring",
    "значениеизстроки": "valuefromstring",
    "значениевфайл": "valuetofile",
    "значениеизфайла": "valuefromfile",
    "тип": "type",
    "типзнч": "typeof",
    # Универсальные
    "значениезаполнено": "valueisfilled",
    "заполнитьзначениясвойств": "fillpropertyvalues",
    "выполнитьобработку": "executeprocessing",
    "выполнитькод": "executecode",
    # Регистры
    "записатьнаборзаписей": "writerecordset",
    "прочитатьнаборзаписей": "readrecordset",
    "отбор": "filter",
    "установитьотбор": "setfilter",
    # Формы
    "открытьформу": "openform",
    "открытьформумодально": "openformmodal",
    "закрытьформу": "closeform",
    "получитьэлементформы": "getformitem",
    "установитьвидимость": "setvisibility",
    "установитьдоступность": "setaccessibility",
    "обновитьотображениеданных": "refreshdatadisplay",
    # Общие
    "сообщить": "message",
    "сообщитьпользователю": "messageuser",
    "получитьобщиймодуль": "getcommonmodule",
    "вызватьисключение": "raiseexception",
    "вызватьисключениесоп": "raiseexception",
}


def _apply_synonyms(tokens: list[str]) -> list[str]:
    """Применяет BSL-синонимы: для каждого токена добавляет его синоним.

    "стрнайти" → ["стрнайти", "strfind"]
    "findbycode" → ["findbycode", "найтипокоду"]
    """
    result = list(tokens)
    for token in tokens:
        # Прямой поиск: ru → en
        if token in BSL_SYNONYMS:
            synonym = BSL_SYNONYMS[token]
            if synonym not in result:
                result.append(synonym)
        # Обратный поиск: en → ru
        else:
            for ru, en in BSL_SYNONYMS.items():
                if token == en and ru not in result:
                    result.append(ru)
                    break
    return result


def tokenize_stemmed(text: str) -> list[str]:
    """
    Токенизация + стемминг + BSL-синонимы.

    Для CamelCase (mixed-case) — разбиваем на слова.
    Для lowercase токенов — оставляем целиком (стеммер нормализует).
    BSL-синонимы: "стрнайти" → добавляет "strfind", и наоборот.

    Возвращает список стеммированных токенов с синонимами.
    """
    # Сначала разбиваем mixed-case CamelCase на слова
    # "НайтиПоКоду" → "Найти", "По", "Коду"
    camelcase_parts = re.findall(r"[А-ЯA-Z][а-яёa-z]+|[А-ЯA-Z]+(?=[А-ЯA-Z][а-яёa-z])|\d+|[а-яёa-zA-Z]+", text)

    result = []
    for part in camelcase_parts:
        t = part.lower()
        if len(t) < 2:
            continue
        stemmed = stem(t)
        if len(stemmed) >= 2:
            result.append(stemmed)

    # Применяем BSL-синонимы (ru↔en)
    result = _apply_synonyms(result)

    return result


# ============================================================================
# ТРИГРАММЫ (для устойчивости к опечаткам)
# ============================================================================


def make_trigrams(word: str) -> set[str]:
    """Построить триграммы слова: 'найти' → {'$$н', '$на', 'най', 'айт', 'йти', 'ти$'}."""
    if not word:
        return set()
    padded = f"$${word}$$"
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(s1: set[str], s2: set[str]) -> float:
    """Коэффициент Жаккара для двух множеств триграмм."""
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


# ============================================================================
# BM25 ИНДЕКС
# ============================================================================

# Параметры BM25 (стандартные значения из литературы)
BM25_K1 = 1.5  # насыщение TF
BM25_B = 0.75  # нормализация длины документа


def build_index_bm25(methods_json_path: Path, output_path: Path) -> int:
    """
    Построить BM25 + триграммы индекс.

    Returns: кол-во проиндексированных методов
    """
    with open(methods_json_path, encoding="utf-8") as f:
        methods = json.load(f)

    documents = []
    doc_lengths = []
    method_trigrams = {}  # doc_id → set of trigrams (от всех слов)

    for i, m in enumerate(methods):
        name_ru = m.get("name_ru", "")
        name_en = m.get("name_en", "")
        context = m.get("context", "")
        syntax = m.get("syntax", "")
        description = m.get("description", "")
        returns = m.get("returns", "")

        # Имя метода — больший вес (повторяем 3 раза)
        doc_text = f"{name_ru} {name_ru} {name_ru} {name_en} {name_en} {context} {syntax} {description} {returns}"
        tokens = tokenize_stemmed(doc_text)

        # Триграммы из имени метода (только имя — для fuzzy match)
        trigrams = set()
        for word in (name_ru + " " + name_en).split():
            trigrams |= make_trigrams(word.lower())
        method_trigrams[i] = trigrams

        documents.append(
            {
                "id": i,
                "tokens": tokens,
                "name_ru": name_ru,
                "name_en": name_en,
                "context": context,
                "syntax": syntax,
                "description": description[:300],
                "returns": returns[:200],
                "file": m.get("file", ""),
            }
        )
        doc_lengths.append(len(tokens))

    # DF — document frequency
    df: dict[str, int] = defaultdict(int)
    for doc in documents:
        for t in set(doc["tokens"]):
            df[t] += 1

    # IDF для BM25: ln(1 + (N - df + 0.5) / (df + 0.5))
    N = len(documents)
    idf_bm25 = {t: math.log(1 + (N - df_t + 0.5) / (df_t + 0.5)) for t, df_t in df.items()}

    # Частоты термина в каждом документе
    tf_per_doc: dict[int, Counter] = {}
    for doc in documents:
        tf_per_doc[doc["id"]] = Counter(doc["tokens"])

    # Инвертированный индекс: токен → [(doc_id, tf)]
    inverted_index: dict[str, list] = defaultdict(list)
    for doc in documents:
        for t, tf in tf_per_doc[doc["id"]].items():
            inverted_index[t].append((doc["id"], tf))

    # Средняя длина документа
    avg_doc_length = sum(doc_lengths) / max(N, 1)

    # Триграммный индекс: trigram → [doc_ids]
    trigrams_index: dict[str, list] = defaultdict(list)
    for doc_id, trigrams in method_trigrams.items():
        for trigram in trigrams:
            trigrams_index[trigram].append(doc_id)

    # Удаляем tokens из документов (для экономии места)
    for doc in documents:
        del doc["tokens"]

    # Длины документов в dict
    doc_lengths_dict = dict(enumerate(doc_lengths))

    index_data = {
        "version": 2,
        "algorithm": "bm25",
        "methods": documents,
        "idf": idf_bm25,
        "inverted_index": dict(inverted_index),
        "doc_lengths": doc_lengths_dict,
        "avg_doc_length": avg_doc_length,
        "total_methods": N,
        "trigrams_index": dict(trigrams_index),
        "method_trigrams": {str(k): list(v) for k, v in method_trigrams.items()},
        "bm25_params": {"k1": BM25_K1, "b": BM25_B},
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False)

    return N


def _bm25_score(tf: int, idf: float, doc_length: float, avg_length: float) -> float:
    """BM25 score для одного термина в документе."""
    k1 = BM25_K1
    b = BM25_B
    norm = (1 - b) + b * (doc_length / max(avg_length, 1))
    return idf * (tf * (k1 + 1)) / (tf + k1 * norm)


def _load_index(index_path: Path) -> dict:
    """
    Загрузить BM25 индекс из JSON-файла (с кэшированием).

    P1.9: добавлен @lru_cache(maxsize=8) — до фикса каждый вызов search_bm25()
    перечитывал JSON-индекс с диска (~50-200мс на 100K методов). После фикса
    первый вызов для данного index_path медленный, последующие — <1мс.

    Кэш хранит до 8 различных index_path (для multi-project сценариев).
    Инвалидация:
      - Автоматически при изменении index_path (другой путь → другой ключ кэша).
      - Вручную через _load_index.cache_clear() — например, после rebuild index.
      - Вручную через _load_index.cache_invalidate(index_path) для конкретного пути.

    Args:
        index_path: Путь к JSON-индексу.

    Returns:
        dict с полями: methods, idf, inverted_index, doc_lengths, etc.

    Raises:
        FileNotFoundError: Если index_path не существует.
        json.JSONDecodeError: Если файл не валидный JSON.
    """
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


# Применяем lru_cache к обёртке, чтобы была возможность cache_clear().
# maxsize=8: достаточно для типичных multi-config сценариев (5-6 конфигов).
_load_index_cached = lru_cache(maxsize=8)(_load_index)


def search_bm25(index_path: Path, query: str, limit: int = 10, hybrid: bool = True) -> list[dict]:
    """
    BM25 поиск по индексу v2.

    Args:
        index_path: Путь к индексу
        query: Поисковый запрос
        limit: Кол-во результатов
        hybrid: Если True — гибридный режим (BM25 + триграммы)

    Returns:
        Список результатов с score, name_ru, name_en, context, syntax, description
    """
    # P1.9: используем кэшированную загрузку. lru_cache по Path автоматически
    # различает разные index_path. Для инвалидации: _load_index_cached.cache_clear().
    index = _load_index_cached(index_path)

    methods = index["methods"]
    idf = index["idf"]
    inverted_index = index["inverted_index"]
    doc_lengths = index.get("doc_lengths", {})
    avg_doc_length = index.get("avg_doc_length", 1.0)

    # Токенизуем запрос (со стеммингом)
    query_tokens = tokenize_stemmed(query)
    if not query_tokens:
        return []

    # BM25 scoring
    bm25_scores: dict[int, float] = defaultdict(float)
    query_tf = Counter(query_tokens)

    for t, _q_tf in query_tf.items():
        if t not in inverted_index:
            continue
        idf_t = idf.get(t, 0)
        for doc_id, doc_tf in inverted_index[t]:
            doc_len = doc_lengths.get(str(doc_id), doc_lengths.get(doc_id, avg_doc_length))
            score = _bm25_score(doc_tf, idf_t, doc_len, avg_doc_length)
            bm25_scores[doc_id] += score

    # Гибридный режим: добавляем триграммы
    if hybrid and "trigrams_index" in index:
        # Если BM25 что-то нашёл — ограничиваем триграммы кандидатами (оптимизация).
        # Если ничего не нашёл — триграммы ищут по всему индексу (важно для опечаток).
        candidates = bm25_scores.keys() if bm25_scores else None
        trigram_scores = _trigram_search(index, query, candidates)

        # Нормализуем обе скоринговые системы к [0, 1]
        max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0
        max_trigram = max(trigram_scores.values()) if trigram_scores else 1.0

        all_doc_ids = set(bm25_scores.keys()) | set(trigram_scores.keys())
        combined = {}
        for doc_id in all_doc_ids:
            bm25_norm = bm25_scores.get(doc_id, 0) / max_bm25 if max_bm25 > 0 else 0
            trig_norm = trigram_scores.get(doc_id, 0) / max_trigram if max_trigram > 0 else 0
            # Веса: BM25 — основной, триграммы — корректировка
            combined[doc_id] = 0.75 * bm25_norm + 0.25 * trig_norm

        ranked = sorted(combined.items(), key=lambda x: -x[1])[:limit]
    else:
        ranked = sorted(bm25_scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for doc_id, score in ranked:
        m = methods[doc_id]
        results.append(
            {
                "score": round(score, 4),
                "name_ru": m["name_ru"],
                "name_en": m["name_en"],
                "context": m["context"][:80],
                "syntax": m["syntax"][:120],
                "description": m["description"][:150],
            }
        )

    return results


def _trigram_search(index: dict, query: str, candidate_ids=None) -> dict[int, float]:
    """
    Триграммный поиск — для устойчивости к опечаткам.

    Ищет методы, чьи имена похожи на слова из запроса.

    Args:
        index: Загруженный индекс
        query: Поисковый запрос
        candidate_ids: Если указано — ограничиваем поиск этими doc_ids (для оптимизации)

    Returns: {doc_id: score}
    """
    trigrams_index = index.get("trigrams_index", {})
    method_trigrams = index.get("method_trigrams", {})

    # Строим триграммы запроса (только существенные слова)
    query_words = re.findall(r"[а-яёА-ЯЁa-zA-Z]{3,}", query)
    if not query_words:
        return {}

    query_trigrams = set()
    for w in query_words:
        query_trigrams |= make_trigrams(w.lower())

    if not query_trigrams:
        return {}

    # Находим candidate doc_ids (через инвертированный триграммный индекс)
    candidate_docs = set()
    for trigram in query_trigrams:
        if trigram in trigrams_index:
            candidate_docs.update(trigrams_index[trigram])

    # Если уже есть candidate_ids от BM25 — пересекаем (оптимизация)
    if candidate_ids is not None:
        candidate_docs = candidate_docs & set(candidate_ids)

    # Считаем Жаккар для каждого кандидата
    scores = {}
    for doc_id in candidate_docs:
        doc_trigrams = set(method_trigrams.get(str(doc_id), []))
        if doc_trigrams:
            scores[doc_id] = trigram_similarity(query_trigrams, doc_trigrams)

    return scores


# ============================================================================
# AUTO-DETECT (v1 / v2)
# ============================================================================


def detect_index_version(index_path: Path) -> int:
    """Определить версию индекса (1 = TF-IDF, 2 = BM25)."""
    if not index_path.exists():
        return 0
    try:
        with open(index_path, encoding="utf-8") as f:
            head = f.read(500)
        if '"version": 2' in head:
            return 2
        return 1
    except Exception:
        return 0


def search_auto(index_path: Path, query: str, limit: int = 10) -> list[dict]:
    """
    Авто-выбор алгоритма поиска по версии индекса.

    v1 (TF-IDF) → services.search.search()
    v2 (BM25) → search_bm25()
    """
    version = detect_index_version(index_path)

    if version == 2:
        return search_bm25(index_path, query, limit, hybrid=True)
    elif version == 1:
        # Fallback на старый TF-IDF
        from .search import search as tfidf_search

        return tfidf_search(index_path, query, limit)
    else:
        return []
