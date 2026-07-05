"""
search.py — CLI команды для поиска и графа вызовов.

P2.1: вынесено из cli.py.
Команды: search, search-code, call-graph
"""

from __future__ import annotations

import argparse
import sys

from src.project import Project


def cmd_search(project: Project, args: argparse.Namespace) -> None:
    """Семантический поиск по методам 1С (BM25/TF-IDF авто)."""
    from src.services.search_bm25 import detect_index_version, search_auto

    index_path = project.paths.fast_search_index
    if not index_path.exists():
        print("❌ Индекс не найден. Запустите: python3 scripts/fast_search_1c.py build")
        sys.exit(1)

    version = detect_index_version(index_path)
    algo_name = "BM25+триграммы (v2)" if version == 2 else "TF-IDF (v1, legacy)"

    results = search_auto(index_path, args.query, args.limit)

    print(f'Поиск: "{args.query}"')
    print(f"Алгоритм: {algo_name}")
    print(f"Найдено: {len(results)} результатов")
    print()
    for rank, r in enumerate(results, 1):
        print(f"{rank}. [{r['score']:.3f}] {r['name_ru']} ({r['name_en']})")
        print(f"   Контекст: {r['context']}")
        print(f"   Синтаксис: {r['syntax']}")
        if r["description"]:
            print(f"   Описание: {r['description']}")
        print()


def cmd_search_code(project: Project, args: argparse.Namespace) -> None:
    """Поиск по коду конфигурации (BM25 по 115 666 методов)."""
    from src.services.search_code import search_code

    config_name = args.config
    if not config_name:
        print("❌ Укажите конфигурацию: 1c-ai search-code 'запрос' --config ut11")
        sys.exit(1)

    # Проверяем, что конфигурация существует
    configs = {c.name for c in project.list_configs()}
    if config_name not in configs:
        print(f"❌ Конфигурация '{config_name}' не найдена. Доступные: {', '.join(configs)}")
        sys.exit(1)

    results = search_code(config_name, args.query, args.limit, project.paths)

    print(f'Поиск по коду: "{args.query}"')
    print(f"Конфигурация: {config_name}")
    print(f"Найдено: {len(results)} результатов")
    print()
    for rank, r in enumerate(results, 1):
        print(f"{rank}. [{r['score']:.3f}] {r['module']}.{r['name']}")
        print(f"   Тип: {r['type']}")
        if r["signature"]:
            print(f"   Сигнатура: {r['signature']}")
        if r["description"]:
            print(f"   Описание: {r['description'][:120]}")
        print()


def cmd_call_graph(project: Project, args: argparse.Namespace) -> None:
    """Граф вызовов методов конфигурации."""
    import json as json_mod

    from src.services.call_graph import build_call_graph

    config_name = args.config
    configs = {c.name for c in project.list_configs()}
    if config_name not in configs:
        print(f"❌ Конфигурация '{config_name}' не найдена. Доступные: {', '.join(configs)}")
        sys.exit(1)

    graph = build_call_graph(config_name, project.paths)

    if args.action == "stats":
        stats = graph.get_stats()
        print(f"Граф вызовов: {config_name}")
        print(f"  Рёбер (вызовов): {stats['total_edges']}")
        print(f"  Узлов (методов): {stats['total_nodes']}")
        print(f"  Уникальных вызывающих: {stats['unique_callers']}")
        print(f"  Уникальных вызываемых: {stats['unique_callees']}")

    elif args.action == "callers":
        module = args.module
        method = args.method
        callers = graph.get_callers(module, method)
        if callers:
            print(f"Кто вызывает {module}.{method}():")
            for c in callers:
                print(f"  {c['module']}.{c['method']}()  [{c['file']}:{c['line']}]")
        else:
            print(f"Никто не вызывает {module}.{method}()")

    elif args.action == "callees":
        module = args.module
        method = args.method
        callees = graph.get_callees(module, method)
        if callees:
            print(f"Кого вызывает {module}.{method}():")
            for c in callees:
                print(f"  → {c['module']}.{c['method']}()  [{c['file']}:{c['line']}]")
        else:
            print(f"{module}.{method}() никого не вызывает")

    elif args.action == "dead-code":
        # Загружаем export methods из api-reference
        api_json = project.paths.config_api_reference_json(config_name)
        export_methods = []
        if api_json.exists():
            with open(api_json, encoding="utf-8") as f:
                modules = json_mod.load(f)
            for m in modules:
                for method in m.get("methods", []):
                    export_methods.append((m["name"], method["name"]))
        dead = graph.find_dead_code(export_methods)
        if dead:
            print(f"Мёртвый код ({len(dead)} из {len(export_methods)} экспортных методов):")
            for mod, meth in dead:
                print(f"  {mod}.{meth}()")
        else:
            print("Мёртвый код не найден — все экспортные методы вызываются")

    elif args.action == "cycles":
        cycles = graph.find_cycles()
        if cycles:
            print(f"Циклические зависимости ({len(cycles)}):")
            for cycle in cycles:
                print(f"  {' → '.join(cycle)}")
        else:
            print("Циклов не найдено")

    elif args.action == "json":
        print(json_mod.dumps(graph.to_dict(), ensure_ascii=False, indent=2))
