"""
SessionManager — управление контекстом AI-сессий.

Сохранение/восстановление состояния сессии между запусками.
Позаимствовано из 1c-ai-development-kit (skills session-save, session-restore, session-retro).

Использование:
    from src.services.session_manager import SessionManager

    sm = SessionManager(project_root=Path('.'))
    sm.save(current_task='Реализация CFE', completed=['borrow', 'patch'], pending=['diff'])
    state = sm.restore()  # при следующем запуске
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SessionState:
    """Состояние сессии для сохранения между запусками."""
    date: str = ""
    current_task: str = ""
    completed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    next_action: str = ""
    key_decisions: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    context_summary: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SessionState:
        return cls(
            date=d.get("date", ""),
            current_task=d.get("current_task", ""),
            completed=d.get("completed", []),
            pending=d.get("pending", []),
            next_action=d.get("next_action", ""),
            key_decisions=d.get("key_decisions", []),
            modified_files=d.get("modified_files", []),
            context_summary=d.get("context_summary", ""),
            warnings=d.get("warnings", []),
        )

    def to_markdown(self) -> str:
        """Прочитать состояние как Markdown (для session-notes.md)."""
        lines = [
            f"# Session Notes — {self.date}",
            "",
            "## Current Task",
            self.current_task or "(не указана)",
            "",
            "## Completed",
        ]
        if self.completed:
            for item in self.completed:
                lines.append(f"- {item}")
        else:
            lines.append("(пусто)")
        lines.append("")

        lines.append("## Pending")
        if self.pending:
            for item in self.pending:
                lines.append(f"- {item}")
        else:
            lines.append("(пусто)")
        lines.append("")

        lines.append("## Next Action")
        lines.append(self.next_action or "(не указано)")
        lines.append("")

        lines.append("## Key Decisions")
        if self.key_decisions:
            for d in self.key_decisions:
                lines.append(f"- {d}")
        else:
            lines.append("(пусто)")
        lines.append("")

        lines.append("## Modified Files")
        if self.modified_files:
            for f in self.modified_files:
                lines.append(f"- {f}")
        else:
            lines.append("(пусто)")
        lines.append("")

        if self.context_summary:
            lines.append("## Context Summary")
            lines.append(self.context_summary)
            lines.append("")

        if self.warnings:
            lines.append("## Warnings")
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        return "\n".join(lines)


class SessionManager:
    """Управление сохранением/восстановлением AI-сессий."""

    def __init__(self, project_root: Path):
        self._project_root = Path(project_root)
        self._notes_path = self._project_root / "session-notes.md"
        self._state_path = self._project_root / "runtime" / "session-state.json"

    def save(
        self,
        current_task: str = "",
        completed: list[str] | None = None,
        pending: list[str] | None = None,
        next_action: str = "",
        key_decisions: list[str] | None = None,
        modified_files: list[str] | None = None,
        context_summary: str = "",
        warnings: list[str] | None = None,
    ) -> Path:
        """Сохранить состояние сессии.

        Записывает 2 файла:
        - session-notes.md (Markdown, для человека)
        - runtime/session-state.json (JSON, для программного восстановления)
        """
        state = SessionState(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            current_task=current_task,
            completed=completed or [],
            pending=pending or [],
            next_action=next_action,
            key_decisions=key_decisions or [],
            modified_files=modified_files or [],
            context_summary=context_summary,
            warnings=warnings or [],
        )

        # Markdown
        self._notes_path.write_text(
            state.to_markdown(),
            encoding="utf-8",
        )

        # JSON
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return self._notes_path

    def restore(self) -> SessionState | None:
        """Восстановить состояние сессии.

        Возвращает None если нет сохранённой сессии.
        """
        if not self._state_path.exists():
            return None

        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return SessionState.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def retro(self) -> str:
        """Ретроспектива сессии — краткая сводка для отчёта."""
        state = self.restore()
        if not state:
            return "Нет сохранённой сессии для ретроспективы."

        lines = [
            f"📊 Ретроспектива сессии от {state.date}",
            "=" * 50,
            "",
            f"Задача: {state.current_task}",
            f"Выполнено: {len(state.completed)} пунктов",
            f"Осталось: {len(state.pending)} пунктов",
            f"Изменено файлов: {len(state.modified_files)}",
            f"Решений принято: {len(state.key_decisions)}",
        ]

        if state.completed:
            lines.append("")
            lines.append("✅ Выполнено:")
            for item in state.completed:
                lines.append(f"  • {item}")

        if state.pending:
            lines.append("")
            lines.append("⏳ Осталось:")
            for item in state.pending:
                lines.append(f"  • {item}")

        if state.key_decisions:
            lines.append("")
            lines.append("🎯 Ключевые решения:")
            for d in state.key_decisions:
                lines.append(f"  • {d}")

        if state.next_action:
            lines.append("")
            lines.append(f"➡️ Следующий шаг: {state.next_action}")

        return "\n".join(lines)

    def clear(self) -> bool:
        """Очистить сохранённую сессию."""
        cleared = False
        if self._notes_path.exists():
            self._notes_path.unlink()
            cleared = True
        if self._state_path.exists():
            self._state_path.unlink()
            cleared = True
        return cleared

    def exists(self) -> bool:
        """Проверить есть ли сохранённая сессия."""
        return self._state_path.exists()
