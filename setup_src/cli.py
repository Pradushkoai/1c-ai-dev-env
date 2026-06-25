"""
Единый CLI для всех команд проекта.

Usage:
    python3 -m src.cli config list
    python3 -m src.cli config add --name ut11 --zip ut11.zip --title "УТ 11"
    python3 -m src.cli config build --name ut11
    python3 -m src.cli config build-all
    python3 -m src.cli bsl analyze <path>
    python3 -m src.cli bsl baseline <path>
    python3 -m src.cli bsl diff <path>
    python3 -m src.cli validate
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import Project


def cmd_config_list(project: Project, args):
    configs = project.list_configs()
    if not configs:
        print("Нет конфигураций.")
        return
    print(f"{'Имя':<15} {'Версия':<15} {'Статус':<10} {'Объектов':<10} {'Путь'}")
    print("-" * 80)
    for c in configs:
        path = str(c.path) if c.path else (str(c.archive) if c.archive else "—")
        print(f"{c.name:<15} {c.version:<15} {c.status:<10} {c.objects_count:<10} {path}")


def cmd_config_add(project: Project, args):
    config = project.config_manager.add_from_zip(args.name, Path(args.zip), args.title)
    print(f"✅ Добавлена: {config.name} v{config.version} ({config.objects_count} объектов)")
    if not args.skip_build:
        print("Индексация...")
        report = project.config_manager.build(args.name)
        print(f"  Индекс: {'✅' if report['index'] else '❌'}")
        print(f"  API:    {'✅' if report['api'] else '—'}")


def cmd_config_build(project: Project, args):
    report = project.config_manager.build(args.name)
    print(f"✅ {args.name}: index={'✅' if report['index'] else '❌'} api={'✅' if report['api'] else '—'}")


def cmd_config_build_all(project: Project, args):
    results = project.config_manager.build_all()
    for r in results:
        print(f"✅ {r['name']}: index={'✅' if r['index'] else '❌'} api={'✅' if r['api'] else '—'}")


def cmd_bsl_analyze(project: Project, args):
    result = project.bsl_analyzer.analyze(Path(args.path))
    print(f"Всего: {result.total}")
    for code, count in sorted(result.by_code.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:4d}  {code}")


def cmd_bsl_baseline(project: Project, args):
    result = project.bsl_analyzer.save_baseline(Path(args.path))
    print(f"✅ Baseline: {result.total} диагностик")


def cmd_bsl_diff(project: Project, args):
    diff = project.bsl_analyzer.diff(Path(args.path))
    print(f"\n🆕 НОВЫЕ ({len(diff.new)}):")
    for d in diff.new[:20]:
        print(f"  + {d['code']} (строка {d['line']}): {d['message']}")
    print(f"\n✅ ИСПРАВЛЕННЫЕ ({len(diff.fixed)}):")
    for d in diff.fixed[:10]:
        print(f"  - {d['key']}")


def cmd_validate(project: Project, args):
    checks = project.validate()
    all_ok = True
    for name, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {name}")
        if not ok:
            all_ok = False
    sys.exit(0 if all_ok else 1)


def cmd_search(project: Project, args):
    """Семантический поиск по методам 1С (TF-IDF)."""
    import json, math, re
    from collections import Counter

    index_path = project.paths.fast_search_index
    if not index_path.exists():
        print("❌ Индекс не найден. Запустите: python3 scripts/fast_search_1c.py build")
        sys.exit(1)

    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)

    methods = index['methods']
    idf = index['idf']
    inverted_index = index['inverted_index']

    def tokenize(text):
        tokens = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', text.lower())
        result = []
        for t in tokens:
            result.append(t)
            parts = re.findall(r'[А-ЯA-Z]?[а-яёa-z]+|\d+', t)
            if len(parts) > 1:
                result.extend(p.lower() for p in parts)
        return result

    query_tokens = tokenize(args.query)
    if not query_tokens:
        print("Пустой запрос")
        return

    query_tf = Counter(query_tokens)
    query_tfidf = {}
    for t, tf in query_tf.items():
        if t in idf:
            query_tfidf[t] = tf * idf[t]

    norm = math.sqrt(sum(w**2 for w in query_tfidf.values()))
    if norm > 0:
        query_tfidf = {t: w / norm for t, w in query_tfidf.items()}

    scores = {}
    for t, q_weight in query_tfidf.items():
        if t in inverted_index:
            for doc_id, doc_weight in inverted_index[t]:
                scores[doc_id] = scores.get(doc_id, 0) + q_weight * doc_weight

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:args.limit]

    print(f'Поиск: "{args.query}"')
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


def main():
    parser = argparse.ArgumentParser(
        prog="src.cli",
        description="1C AI Development Environment CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # config
    p_cfg = sub.add_parser("config", help="Управление конфигурациями")
    cfg_sub = p_cfg.add_subparsers(dest="config_command", required=True)

    cfg_sub.add_parser("list", help="Список")

    p_add = cfg_sub.add_parser("add", help="Добавить из ZIP")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--zip", required=True)
    p_add.add_argument("--title", default="")
    p_add.add_argument("--skip-build", action="store_true")

    p_build = cfg_sub.add_parser("build", help="Индексы для одной")
    p_build.add_argument("--name", required=True)

    cfg_sub.add_parser("build-all", help="Индексы для всех")

    # bsl
    p_bsl = sub.add_parser("bsl", help="Анализ .bsl")
    bsl_sub = p_bsl.add_subparsers(dest="bsl_command", required=True)

    p_a = bsl_sub.add_parser("analyze", help="Анализ")
    p_a.add_argument("path")

    p_b = bsl_sub.add_parser("baseline", help="Сохранить baseline")
    p_b.add_argument("path")

    p_d = bsl_sub.add_parser("diff", help="Только новые ошибки")
    p_d.add_argument("path")

    # validate
    sub.add_parser("validate", help="Проверить окружение")

    # search
    p_search = sub.add_parser("search", help="Семантический поиск методов 1С")
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument("--limit", type=int, default=10, help="Кол-во результатов")

    args = parser.parse_args()
    project = Project()

    if args.command == "config":
        if args.config_command == "list":
            cmd_config_list(project, args)
        elif args.config_command == "add":
            cmd_config_add(project, args)
        elif args.config_command == "build":
            cmd_config_build(project, args)
        elif args.config_command == "build-all":
            cmd_config_build_all(project, args)
    elif args.command == "bsl":
        if args.bsl_command == "analyze":
            cmd_bsl_analyze(project, args)
        elif args.bsl_command == "baseline":
            cmd_bsl_baseline(project, args)
        elif args.bsl_command == "diff":
            cmd_bsl_diff(project, args)
    elif args.command == "validate":
        cmd_validate(project, args)
    elif args.command == "search":
        cmd_search(project, args)


if __name__ == "__main__":
    main()
