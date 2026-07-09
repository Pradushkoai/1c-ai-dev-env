"""
depgraph_cmd.py — CLI команда для графа зависимостей метаданных.

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.project import Project


def cmd_depgraph(project: Project, args: object) -> None:
    """Граф зависимостей метаданных 1С (networkx, без Neo4j)."""
    from typing import Any

    from src.services.dependency_graph import DependencyGraph

    if args.depgraph_command == "build":
        dg = DependencyGraph()
        build_result = dg.build_from_metadata_index(args.name, project.paths)
        print(f"✅ Граф зависимостей: {build_result.config_name}")
        print(f"   Узлов: {len(build_result.nodes)}")
        print(f"   Рёбер: {len(build_result.edges)}")
        if build_result.warnings:
            for w in build_result.warnings:
                print(f"   ⚠️ {w}")
        # Сохраняем в файл
        output = args.output or f"derived/configs/{args.name}/dependency-graph.json"
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = project.paths.root / output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import json as json_mod

        out_path.write_text(
            json_mod.dumps(dg.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"   Сохранено: {out_path}")

    elif args.depgraph_command == "query":
        dg = DependencyGraph()
        dg.build_from_metadata_index(args.name, project.paths)

        if args.query_type == "what_depends_on":
            query_result: Any = dg.what_depends_on(args.object)
            print(f"=== Что зависит от {args.object} ===")
            for r in query_result:
                print(f"  ← {r['source']} ({r['relation']}) {r['detail']}")
            print(f"\nИтого: {len(query_result)} зависимых")

        elif args.query_type == "dependencies_of":
            query_result = dg.dependencies_of(args.object)
            print(f"=== На что ссылается {args.object} ===")
            for r in query_result:
                print(f"  → {r['target']} ({r['relation']}) {r['detail']}")
            print(f"\nИтого: {len(query_result)} зависимостей")

        elif args.query_type == "transitive_dependencies":
            query_result = dg.transitive_dependencies(args.object)
            print(f"=== Транзитивные зависимости {args.object} ===")
            for r in query_result:
                print(f"  → {r}")
            print(f"\nИтого: {len(query_result)}")

        elif args.query_type == "transitive_dependents":
            query_result = dg.transitive_dependents(args.object)
            print(f"=== Кто зависит от {args.object} (транзитивно) ===")
            for r in query_result:
                print(f"  ← {r}")
            print(f"\nИтого: {len(query_result)}")

        elif args.query_type == "find_cycles":
            query_result = dg.find_cycles()
            print("=== Циклические зависимости ===")
            for i, cycle in enumerate(query_result, 1):
                print(f"  {i}. {' → '.join(cycle)}")
            print(f"\nИтого: {len(query_result)} циклов")

        elif args.query_type == "find_unused_objects":
            query_result = dg.find_unused_objects()
            print("=== Мёртвый код (на кого не ссылаются) ===")
            for r in query_result:
                print(f"  • {r}")
            print(f"\nИтого: {len(query_result)} объектов")

        elif args.query_type == "find_root_objects":
            query_result = dg.find_root_objects()
            print("=== Корневые объекты (на них ссылаются, сами ни на кого) ===")
            for r in query_result:
                print(f"  • {r}")
            print(f"\nИтого: {len(query_result)} объектов")

        elif args.query_type == "shortest_path":
            if not args.target:
                print("❌ Укажите --target")
                sys.exit(2)
            query_result = dg.shortest_path(args.object, args.target)
            if query_result:
                print(f"=== Кратчайший путь {args.object} → {args.target} ===")
                print(f"  {' → '.join(query_result)}")
            else:
                print(f"❌ Путь не найден: {args.object} → {args.target}")

        elif args.query_type == "stats":
            stats = dg.get_stats()
            print("=== Статистика графа ===")
            for k, v in stats.items():
                print(f"  {k}: {v}")

    elif args.depgraph_command == "validate":
        """Проверить что граф DAG (нет циклов)."""
        dg = DependencyGraph()
        dg.build_from_metadata_index(args.name, project.paths)
        stats = dg.get_stats()
        if stats["is_dag"]:
            print("✅ Граф — DAG (нет циклов)")
        else:
            print(f"❌ Граф содержит циклы: {stats['cycles']}")
            cycles = dg.find_cycles()
            for i, cycle in enumerate(cycles, 1):
                print(f"  {i}. {' → '.join(cycle)}")
