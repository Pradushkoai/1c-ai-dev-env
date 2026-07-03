"""
tools.py — CLI команды для DSL, CFE, СКД, графа зависимостей, OpenSpec, EPF, session.

P2.1: вынесено из cli.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.project import Project


def cmd_epf_factory(project: Project, args: argparse.Namespace) -> None:
    """Полный цикл создания внешней обработки 1С (.epf) из шаблонов.

    Подход:
        1. Шаблоны ExternalDataProcessor.json / Form.json / Form.id.json /
           Form.elem.json (извлечены из реального EPF через v8unpack)
        2. Подстановка name, synonym, новых UUID (обработка + форма + file)
        3. Запись BSL-модуля формы
        4. Проверка BSL через BSL LS (опционально)
        5. Сборка .epf через v8unpack
        6. Проверка round-trip: распаковка и сравнение BSL-модуля
    """
    from src.services.epf_factory import EpfFactory

    factory = EpfFactory()

    if args.epf_command == "templates":
        templates = factory.list_templates()
        print("Шаблоны epf-factory:")
        for k, v in templates.items():
            print(f"  {k:20s}  {v}")
        return

    if args.epf_command == "create":
        from pathlib import Path as PathMod

        bsl_path = PathMod(args.bsl)
        if not bsl_path.exists():
            print(f"❌ BSL-файл не найден: {bsl_path}")
            sys.exit(2)
        bsl_code = bsl_path.read_text(encoding="utf-8")

        result = factory.create_epf(
            name=args.name,
            synonym=args.synonym,
            bsl_code=bsl_code,
            output_epf=args.output,
            form_name=args.form_name,
            form_spec=args.form_spec,
            save_sources=args.save_sources,
            skip_bsl_validation=args.skip_bsl_validation,
        )

        if not result.ok:
            print(f"❌ Ошибка: {result.error}")
            sys.exit(1)

        print(f"✅ EPF создан: {result.epf_path}")
        print(f"   Размер: {result.size_bytes} байт ({result.size_bytes / 1024:.1f} КБ)")
        print(f"   Имя:    {result.name}")
        print(f"   Синоним: {result.synonym}")
        print(f"   UUID обработки: {result.proc_uuid}")
        print(f"   UUID формы:     {result.form_uuid}")
        print(f"   BSL-модуль: {result.bsl_lines} строк")
        if not args.skip_bsl_validation:
            print(f"   BSL LS: {result.bsl_errors} errors, {result.bsl_warnings} warnings")
        print(f"   Round-trip: {'✅ OK' if result.round_trip_ok else '❌ FAIL'}")
        if result.work_dir:
            print(f"   Исходники сохранены: {result.work_dir}")


# ============================================================================
# DSL — JSON DSL → XML компиляторы
# ============================================================================


def cmd_dsl(project: Project, args: argparse.Namespace) -> None:
    """JSON DSL → XML компиляторы для 1С."""
    from src.services.dsl_compiler import DslCompiler

    compiler = DslCompiler()

    if args.dsl_command == "meta":
        # Compile metadata object
        import json as json_mod

        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_meta(definition, args.output_dir)
        print(f"✅ {result.object_type}.{result.object_name}")
        print(f"   XML: {result.xml_path}")
        if result.module_paths:
            print(f"   Modules: {len(result.module_paths)}")
            for p in result.module_paths:
                print(f"     • {p}")
        if result.registered_in_config:
            print("   Registered in Configuration.xml: ✅")
        if result.warnings:
            for w in result.warnings:
                print(f"   ⚠️ {w}")

    elif args.dsl_command == "form":
        import json as json_mod

        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_form(definition, args.output_path)
        print(f"✅ Form: {result.object_name}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "skd":
        import json as json_mod

        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_skd(definition, args.output_path)
        print(f"✅ SKD: {result.object_name}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "mxl":
        import json as json_mod

        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_mxl(definition, args.output_path)
        print(f"✅ MXL: {result.object_name}")
        print(f"   XML: {result.xml_path}")
        print(f"   XML: {result.xml_path}")

    elif args.dsl_command == "role":
        import json as json_mod

        if args.json_file:
            with open(args.json_file, encoding="utf-8") as f:
                definition = json_mod.load(f)
        elif args.json_string:
            definition = json_mod.loads(args.json_string)
        else:
            print("❌ Укажите --json-file или --json-string")
            sys.exit(2)

        result = compiler.compile_role(definition, args.output_dir)
        print(f"✅ Role: {result.object_name}")
        print(f"   Metadata: {result.xml_path}")
        if result.module_paths:
            print(f"   Rights.xml: {result.module_paths[0]}")


# ============================================================================
# CFE — работа с расширениями конфигураций
# ============================================================================


def cmd_cfe(project: Project, args: argparse.Namespace) -> None:
    """Работа с расширениями конфигураций 1С (CFE)."""
    from typing import Any

    from src.services.cfe_manager import CfeManager

    manager = CfeManager()

    if args.cfe_command == "borrow":
        result: Any = manager.borrow_object(
            Path(args.extension_path),
            Path(args.config_path),
            args.object_ref,
        )
        print(f"✅ Заимствован: {result.object_ref}")
        print(f"   XML созданы: {len(result.xml_created)}")
        for p in result.xml_created:
            print(f"     • {p}")
        if result.registered_in_config:
            print("   Регистрация в Configuration.xml: ✅")
        for w in result.warnings:
            print(f"   ⚠️ {w}")

    elif args.cfe_command == "patch":
        result = manager.patch_method(
            Path(args.extension_path),
            args.module_path,
            args.method_name,
            args.interceptor_type,
            args.context,
            args.is_function,
        )
        print(f"✅ Перехватчик: {result.interceptor_type} {result.method_name}")
        print(f"   BSL: {result.bsl_file}")

    elif args.cfe_command == "diff":
        result = manager.diff(
            Path(args.extension_path),
            Path(args.config_path),
        )
        print("=== CFE Diff ===")
        print(f"Расширение: {result.extension_path}")
        print(f"Конфигурация: {result.config_path}")
        print()
        print(f"Заимствованные объекты: {len(result.borrowed_objects)}")
        for obj in result.borrowed_objects:
            status = "✅" if obj["found_in_config"] else "⚠️"
            mod = "+" if obj["has_modifications"] else " "
            print(f"  {status} {obj['object_ref']} {mod}")
        print()
        print(f"Методы перехвата: {len(result.patch_methods)}")
        for patch in result.patch_methods:
            print(f"  • {patch['interceptor_type']:25} {patch['method_name']}  ({patch['module_path']})")
        if result.not_in_config:
            print()
            print(f"⚠️ Не найдены в конфигурации: {len(result.not_in_config)}")
            for ref in result.not_in_config:
                print(f"  • {ref}")


# ============================================================================
# SKD Trace — трассировка поля СКД
# ============================================================================


def cmd_skd_trace(project: Project, args: argparse.Namespace) -> None:
    """Трассировка поля СКД через всю цепочку."""
    import sys as sys_mod

    sys_mod.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from skd_parser import trace_field

    schema_path = Path(args.template_path)
    if not schema_path.exists():
        print(f"❌ Файл не найден: {schema_path}")
        sys.exit(2)

    result = trace_field(schema_path, args.field_name)
    if "error" in result:
        print(f"❌ {result['error']}")
        if "available_fields" in result:
            print(f"\nДоступные поля ({len(result['available_fields'])}):")
            for p in result["available_fields"][:20]:
                print(f"  • {p}")
        sys.exit(1)

    print(result["trace_text"])


# Добавляем в main() обработку новых команд


# ============================================================================
# DEPGRAPH — граф зависимостей метаданных
# ============================================================================


def cmd_depgraph(project: Project, args: argparse.Namespace) -> None:
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


# ============================================================================
# OPENSPEC — Specification-Driven Development
# ============================================================================


def cmd_openspec(project: Project, args: argparse.Namespace) -> None:
    """OpenSpec — управление изменениями."""
    from src.services.openspec_manager import OpenSpecManager

    osm = OpenSpecManager(project_root=project.paths.root)

    if args.openspec_command == "init":
        osm.init_project(args.project_name or "1C AI Dev Environment")
        print(f"✅ OpenSpec инициализирован: {project.paths.root / 'openspec'}")

    elif args.openspec_command == "proposal":
        tasks = args.tasks.split(",") if args.tasks else []
        files = args.files.split(",") if args.files else []
        change = osm.create_proposal(
            change_id=args.change_id,
            title=args.title,
            context=args.context or "",
            approach=args.approach or "",
            tasks=tasks,
            files=files,
        )
        print(f"✅ Proposal создан: {change.change_id}")
        print(f"   Title: {change.title}")
        print(f"   Tasks: {len(change.tasks)}")
        print(f"   Путь: {project.paths.root / 'openspec' / 'changes' / change.change_id}")

    elif args.openspec_command == "list":
        changes = osm.list_changes(include_archived=args.archived)
        if not changes:
            print("Нет changes.")
            return
        print(f"{'ID':<30} {'Title':<40} {'Status':<15} {'Progress':<10}")
        print("-" * 95)
        for c in changes:
            archived = " (arch)" if c["archived"] else ""
            print(f"{c['change_id']:<30} {c['title']:<40} {c['status']:<15} {c['progress']:<10}{archived}")

    elif args.openspec_command == "update":
        completed = None
        if args.completed:
            completed = True
        elif args.not_completed:
            completed = False
        result = osm.update_task(args.change_id, args.task_index, completed, args.notes or "")
        if result:
            print(f"✅ Задача {args.task_index} обновлена в '{args.change_id}'")
        else:
            print(f"❌ Не удалось обновить задачу {args.task_index} в '{args.change_id}'")

    elif args.openspec_command == "archive":
        result = osm.archive(args.change_id)
        if result:
            print(f"✅ Change '{args.change_id}' архивирован")
        else:
            print(f"❌ Не удалось архивировать '{args.change_id}'")

    elif args.openspec_command == "validate":
        errors = osm.validate(args.change_id)
        if not errors:
            print(f"✅ Change '{args.change_id}' валиден")
        else:
            print(f"❌ Ошибки в '{args.change_id}':")
            for e in errors:
                print(f"  • {e}")


# ============================================================================
# SESSION — управление контекстом AI-сессий
# ============================================================================


def cmd_session(project: Project, args: argparse.Namespace) -> None:
    """Управление контекстом AI-сессий."""
    from src.services.session_manager import SessionManager

    sm = SessionManager(project_root=project.paths.root)

    if args.session_command == "save":
        completed = args.completed.split(",") if args.completed else []
        pending = args.pending.split(",") if args.pending else []
        files = args.modified.split(",") if args.modified else []
        decisions = args.decisions.split(",") if args.decisions else []
        path = sm.save(
            current_task=args.task or "",
            completed=completed,
            pending=pending,
            next_action=args.next_action or "",
            key_decisions=decisions,
            modified_files=files,
            context_summary=args.summary or "",
        )
        print(f"✅ Сессия сохранена: {path}")

    elif args.session_command == "restore":
        state = sm.restore()
        if not state:
            print("Нет сохранённой сессии.")
            return
        print(f"📅 Сессия от {state.date}")
        print(f"\n📋 Задача: {state.current_task}")
        if state.completed:
            print(f"\n✅ Выполнено ({len(state.completed)}):")
            for item in state.completed:
                print(f"  • {item}")
        if state.pending:
            print(f"\n⏳ Осталось ({len(state.pending)}):")
            for item in state.pending:
                print(f"  • {item}")
        if state.next_action:
            print(f"\n➡️ Следующий шаг: {state.next_action}")
        if state.key_decisions:
            print(f"\n🎯 Решения ({len(state.key_decisions)}):")
            for d in state.key_decisions:
                print(f"  • {d}")
        if state.modified_files:
            print(f"\n📁 Изменено файлов: {len(state.modified_files)}")

    elif args.session_command == "retro":
        print(sm.retro())

    elif args.session_command == "clear":
        if sm.clear():
            print("✅ Сессия очищена")
        else:
            print("Нет сохранённой сессии для очистки")


# ============================================================================
# INSPECT — единый анализ объектов 1С (как у конкурента)
# ============================================================================
