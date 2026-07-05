"""
session_cmd.py — CLI команда для управления контекстом AI-сессий.

F1.6 (2026-07-05): вынесено из cli_commands/tools.py.
"""

from __future__ import annotations

from src.project import Project


def cmd_session(project: Project, args: object) -> None:
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
