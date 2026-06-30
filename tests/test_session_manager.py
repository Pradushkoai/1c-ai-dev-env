"""
Тесты для SessionManager — управление контекстом AI-сессий.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.services.session_manager import SessionManager, SessionState


@pytest.fixture
def setup(tmp_path):
    """Project root + SessionManager."""
    return SessionManager(project_root=tmp_path), tmp_path


# ─────────────────────────────────────────────

def test_save_creates_markdown(setup):
    """save() создаёт session-notes.md."""
    sm, tmp = setup
    path = sm.save(
        current_task="Реализация CFE",
        completed=["borrow", "patch"],
        pending=["diff"],
    )
    assert path.exists()
    assert path == tmp / "session-notes.md"


def test_save_creates_json_state(setup):
    """save() создаёт runtime/session-state.json."""
    sm, tmp = setup
    sm.save(current_task="Task X")
    state_path = tmp / "runtime" / "session-state.json"
    assert state_path.exists()


def test_save_restore_roundtrip(setup):
    """save() → restore() возвращает те же данные."""
    sm, tmp = setup
    sm.save(
        current_task="Тест задачи",
        completed=["шаг 1", "шаг 2"],
        pending=["шаг 3"],
        next_action="Начать с шага 3",
        key_decisions=["Использовать Python", "Не использовать PowerShell"],
        modified_files=["src/cli.py", "tests/test.py"],
        context_summary="Краткое описание контекста",
    )

    state = sm.restore()
    assert state is not None
    assert state.current_task == "Тест задачи"
    assert state.completed == ["шаг 1", "шаг 2"]
    assert state.pending == ["шаг 3"]
    assert state.next_action == "Начать с шага 3"
    assert len(state.key_decisions) == 2
    assert len(state.modified_files) == 2
    assert state.context_summary == "Краткое описание контекста"


def test_restore_no_session_returns_none(setup):
    """restore() без сохранённой сессии → None."""
    sm, tmp = setup
    assert sm.restore() is None


def test_restore_invalid_json_returns_none(setup):
    """restore() с битым JSON → None."""
    sm, tmp = setup
    state_path = tmp / "runtime" / "session-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{invalid json", encoding="utf-8")
    assert sm.restore() is None


def test_markdown_has_sections(setup):
    """Markdown содержит ключевые секции."""
    sm, tmp = setup
    sm.save(
        current_task="Задача",
        completed=["пункт 1"],
        pending=["пункт 2"],
        next_action="Действие",
        key_decisions=["Решение"],
        modified_files=["file.py"],
    )

    md = (tmp / "session-notes.md").read_text(encoding="utf-8")
    assert "# Session Notes" in md
    assert "## Current Task" in md
    assert "## Completed" in md
    assert "## Pending" in md
    assert "## Next Action" in md
    assert "## Key Decisions" in md
    assert "## Modified Files" in md


def test_retro_returns_summary(setup):
    """retro() возвращает ретроспективу."""
    sm, tmp = setup
    sm.save(
        current_task="Тест",
        completed=["a", "b", "c"],
        pending=["d"],
        key_decisions=["Решение 1"],
    )
    retro = sm.retro()
    assert "Ретроспектива" in retro
    assert "Тест" in retro
    assert "Выполнено: 3" in retro
    assert "Осталось: 1" in retro


def test_retro_no_session(setup):
    """retro() без сессии — сообщение."""
    sm, tmp = setup
    retro = sm.retro()
    assert "Нет сохранённой сессии" in retro


def test_clear_removes_files(setup):
    """clear() удаляет файлы сессии."""
    sm, tmp = setup
    sm.save(current_task="X")
    assert sm.exists()

    cleared = sm.clear()
    assert cleared is True
    assert not sm.exists()
    assert not (tmp / "session-notes.md").exists()
    assert not (tmp / "runtime" / "session-state.json").exists()


def test_clear_no_session_returns_false(setup):
    """clear() без сессии → False."""
    sm, tmp = setup
    assert sm.clear() is False


def test_exists_true_after_save(setup):
    """exists() True после save()."""
    sm, tmp = setup
    sm.save(current_task="X")
    assert sm.exists() is True


def test_exists_false_initially(setup):
    """exists() False без save()."""
    sm, tmp = setup
    assert sm.exists() is False


def test_save_with_warnings(setup):
    """save() с warnings."""
    sm, tmp = setup
    sm.save(
        current_task="X",
        warnings=["Внимание 1", "Внимание 2"],
    )

    state = sm.restore()
    assert state.warnings == ["Внимание 1", "Внимание 2"]

    md = (tmp / "session-notes.md").read_text(encoding="utf-8")
    assert "## Warnings" in md
    assert "Внимание 1" in md


def test_save_empty_lists(setup):
    """save() с пустыми списками."""
    sm, tmp = setup
    sm.save(current_task="X")

    state = sm.restore()
    assert state.completed == []
    assert state.pending == []
    assert state.key_decisions == []
    assert state.modified_files == []


def test_session_state_to_markdown():
    """SessionState.to_markdown() без SessionManager."""
    state = SessionState(
        date="2026-01-01",
        current_task="Задача",
        completed=["a"],
        pending=["b"],
        next_action="Действие",
    )
    md = state.to_markdown()
    assert "2026-01-01" in md
    assert "Задача" in md
    assert "- a" in md
    assert "- b" in md


def test_session_state_from_dict():
    """SessionState.from_dict() работает."""
    state = SessionState.from_dict({
        "date": "2026-01-01",
        "current_task": "T",
        "completed": ["x"],
    })
    assert state.date == "2026-01-01"
    assert state.current_task == "T"
    assert state.completed == ["x"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
