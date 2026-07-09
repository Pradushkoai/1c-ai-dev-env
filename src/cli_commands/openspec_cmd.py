"""
openspec_cmd.py — CLI команда для OpenSpec (Specification-Driven Development).

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

from src.project import Project


def cmd_openspec(project: Project, args: object) -> None:
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
