"""
Тесты для OpenSpecManager — Specification-Driven Development.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.services.openspec_manager import (
    OpenSpecManager, Change, Task, SpecDelta,
)


@pytest.fixture
def setup(tmp_path):
    """Project root + OpenSpecManager."""
    return OpenSpecManager(project_root=tmp_path), tmp_path


# ─────────────────────────────────────────────
# TestTask
# ─────────────────────────────────────────────

class TestTask:
    """Тесты модели Task."""

    def test_to_markdown_completed(self):
        task = Task(description="Сделать X", completed=True)
        md = task.to_markdown(1)
        assert "[x]" in md
        assert "Сделать X" in md

    def test_to_markdown_not_completed(self):
        task = Task(description="Сделать X", completed=False)
        md = task.to_markdown(1)
        assert "[ ]" in md

    def test_to_markdown_with_notes(self):
        task = Task(description="X", completed=True, notes="Сделано в коммите abc")
        md = task.to_markdown(1)
        assert "Сделано в коммите abc" in md

    def test_from_markdown_completed(self):
        task = Task.from_markdown("1. [x] Описание задачи")
        assert task is not None
        assert task.completed is True
        assert task.description == "Описание задачи"

    def test_from_markdown_not_completed(self):
        task = Task.from_markdown("1. [ ] Описание задачи")
        assert task is not None
        assert task.completed is False

    def test_from_markdown_with_notes(self):
        task = Task.from_markdown("1. [x] Описание  — заметка")
        assert task is not None
        assert task.notes == "заметка"

    def test_from_markdown_invalid(self):
        assert Task.from_markdown("not a task line") is None
        assert Task.from_markdown("") is None


# ─────────────────────────────────────────────
# TestSpecDelta
# ─────────────────────────────────────────────

class TestSpecDelta:
    """Тесты модели SpecDelta."""

    def test_to_markdown_added(self):
        delta = SpecDelta(
            action="ADDED",
            capability="cfe",
            requirement="CFE Support",
            scenario="When user borrows object",
        )
        md = delta.to_markdown()
        assert "## ADDED Requirements" in md
        assert "### Requirement: CFE Support" in md
        assert "#### Scenario: When user borrows object" in md

    def test_to_markdown_modified(self):
        delta = SpecDelta(action="MODIFIED", capability="x", requirement="Y")
        md = delta.to_markdown()
        assert "## MODIFIED Requirements" in md

    def test_to_markdown_removed(self):
        delta = SpecDelta(action="REMOVED", capability="x", requirement="Y")
        md = delta.to_markdown()
        assert "## REMOVED Requirements" in md


# ─────────────────────────────────────────────
# TestChange
# ─────────────────────────────────────────────

class TestChange:
    """Тесты модели Change."""

    def test_to_proposal_markdown_has_sections(self):
        change = Change(
            change_id="test-1",
            title="Test Change",
            context="Контекст",
            approach="Подход",
        )
        md = change.to_proposal_markdown()
        assert "# SDD: Test Change" in md
        assert "## Context" in md
        assert "## Approach" in md
        assert "**Change ID:**" in md
        assert "**Status:**" in md

    def test_to_tasks_markdown_has_progress(self):
        change = Change(
            change_id="test-1",
            tasks=[
                Task("Задача 1", completed=True),
                Task("Задача 2", completed=False),
            ],
        )
        md = change.to_tasks_markdown()
        assert "**Progress:** 1/2" in md
        assert "[x] Задача 1" in md
        assert "[ ] Задача 2" in md

    def test_to_design_markdown_template(self):
        change = Change(change_id="test-1", title="T")
        md = change.to_design_markdown()
        assert "# Design: T" in md
        assert "Архитектурные решения" in md


# ─────────────────────────────────────────────
# TestOpenSpecManager
# ─────────────────────────────────────────────

class TestOpenSpecManagerInit:
    """Тесты инициализации."""

    def test_init_project_creates_structure(self, setup):
        osm, tmp = setup
        result = osm.init_project("My Project", "Description")

        assert result.exists()
        assert (tmp / "openspec" / "project.md").exists()
        assert (tmp / "openspec" / "changes").is_dir()
        assert (tmp / "openspec" / "specs").is_dir()
        assert (tmp / "openspec" / "archive").is_dir()

    def test_init_project_creates_project_md(self, setup):
        osm, tmp = setup
        osm.init_project("Test Project", "My description")
        project_md = (tmp / "openspec" / "project.md").read_text(encoding="utf-8")
        assert "Test Project" in project_md
        assert "My description" in project_md

    def test_init_project_idempotent(self, setup):
        osm, tmp = setup
        osm.init_project("Project 1")
        # Второй вызов не должен перезаписывать project.md
        osm.init_project("Project 2")
        project_md = (tmp / "openspec" / "project.md").read_text(encoding="utf-8")
        assert "Project 1" in project_md  # не перезаписан

    def test_exists_false_initially(self, setup):
        osm, tmp = setup
        assert osm.exists() is False

    def test_exists_true_after_init(self, setup):
        osm, tmp = setup
        osm.init_project()
        assert osm.exists() is True


# ─────────────────────────────────────────────

class TestCreateProposal:
    """Тесты создания proposal."""

    def test_create_proposal_basic(self, setup):
        osm, tmp = setup
        change = osm.create_proposal(
            change_id="add-feature-x",
            title="Add Feature X",
            context="Нужно для Y",
            approach="Реализовать через Z",
        )

        assert change.change_id == "add-feature-x"
        assert change.title == "Add Feature X"
        # Файлы созданы
        change_dir = tmp / "openspec" / "changes" / "add-feature-x"
        assert (change_dir / "proposal.md").exists()
        assert (change_dir / "tasks.md").exists()

    def test_create_proposal_with_tasks(self, setup):
        osm, tmp = setup
        change = osm.create_proposal(
            change_id="test-tasks",
            title="T",
            tasks=["Задача 1", "Задача 2", "Задача 3"],
        )

        assert len(change.tasks) == 3
        assert all(not t.completed for t in change.tasks)

        # tasks.md содержит задачи
        tasks_md = (tmp / "openspec" / "changes" / "test-tasks" / "tasks.md").read_text(encoding="utf-8")
        assert "Задача 1" in tasks_md
        assert "Задача 3" in tasks_md

    def test_create_proposal_with_files(self, setup):
        osm, tmp = setup
        change = osm.create_proposal(
            change_id="test-files",
            title="T",
            files=["src/foo.py", "tests/test_foo.py"],
        )

        proposal_md = (tmp / "openspec" / "changes" / "test-files" / "proposal.md").read_text(encoding="utf-8")
        assert "src/foo.py" in proposal_md
        assert "tests/test_foo.py" in proposal_md

    def test_create_proposal_with_design(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="test-design",
            title="T",
            design=True,
        )
        assert (tmp / "openspec" / "changes" / "test-design" / "design.md").exists()

    def test_create_proposal_with_spec_deltas(self, setup):
        osm, tmp = setup
        delta = SpecDelta(
            action="ADDED",
            capability="cfe",
            requirement="CFE Borrow",
            scenario="When borrowing object",
        )
        osm.create_proposal(
            change_id="test-deltas",
            title="T",
            spec_deltas=[delta],
        )

        spec_path = tmp / "openspec" / "changes" / "test-deltas" / "specs" / "cfe" / "spec.md"
        assert spec_path.exists()
        content = spec_path.read_text(encoding="utf-8")
        assert "ADDED" in content
        assert "CFE Borrow" in content

    def test_create_proposal_invalid_id_raises(self, setup):
        osm, tmp = setup
        with pytest.raises(ValueError):
            osm.create_proposal(
                change_id="Invalid_ID!",  # заглавные и подчёркивания недопустимы
                title="T",
            )

    def test_create_proposal_duplicate_raises(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="dup-1", title="T")
        with pytest.raises(FileExistsError):
            osm.create_proposal(change_id="dup-1", title="T2")


# ─────────────────────────────────────────────

class TestLoadChange:
    """Тесты загрузки change."""

    def test_load_change_returns_data(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="load-test",
            title="Load Test",
            context="Context here",
            approach="Approach here",
            tasks=["Task 1", "Task 2"],
        )

        loaded = osm.load_change("load-test")
        assert loaded is not None
        assert loaded.change_id == "load-test"
        assert loaded.title == "Load Test"
        assert "Context here" in loaded.context
        assert "Approach here" in loaded.approach
        assert len(loaded.tasks) == 2

    def test_load_change_not_found(self, setup):
        osm, tmp = setup
        assert osm.load_change("missing") is None

    def test_load_change_preserves_task_status(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="status-test",
            title="T",
            tasks=["Task 1", "Task 2"],
        )
        # Отметим первую задачу выполненной
        osm.update_task("status-test", 0, completed=True)

        # Загружаем — статус должен сохраниться
        loaded = osm.load_change("status-test")
        assert loaded.tasks[0].completed is True
        assert loaded.tasks[1].completed is False


# ─────────────────────────────────────────────

class TestUpdateTask:
    """Тесты обновления задач."""

    def test_update_task_complete(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="upd-test",
            title="T",
            tasks=["Task 1", "Task 2"],
        )

        result = osm.update_task("upd-test", 0, completed=True)
        assert result is True

        loaded = osm.load_change("upd-test")
        assert loaded.tasks[0].completed is True
        assert loaded.tasks[1].completed is False

    def test_update_task_toggle(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="toggle-test",
            title="T",
            tasks=["Task 1"],
        )
        # Toggle: False → True
        osm.update_task("toggle-test", 0)
        loaded = osm.load_change("toggle-test")
        assert loaded.tasks[0].completed is True

        # Toggle: True → False
        osm.update_task("toggle-test", 0)
        loaded = osm.load_change("toggle-test")
        assert loaded.tasks[0].completed is False

    def test_update_task_with_notes(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="notes-test",
            title="T",
            tasks=["Task 1"],
        )
        osm.update_task("notes-test", 0, completed=True, notes="Done in commit abc")

        loaded = osm.load_change("notes-test")
        assert loaded.tasks[0].notes == "Done in commit abc"

    def test_update_task_all_completed_changes_status(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="status-change",
            title="T",
            tasks=["T1", "T2"],
        )

        # Отметим все задачи
        osm.update_task("status-change", 0, completed=True)
        osm.update_task("status-change", 1, completed=True)

        loaded = osm.load_change("status-change")
        assert loaded.status == "completed"

    def test_update_task_invalid_index(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="idx-test", title="T", tasks=["T1"])
        # Индекс 5 — вне диапазона
        assert osm.update_task("idx-test", 5, completed=True) is False

    def test_update_task_missing_change(self, setup):
        osm, tmp = setup
        assert osm.update_task("missing", 0, completed=True) is False


# ─────────────────────────────────────────────

class TestArchive:
    """Тесты архивирования."""

    def test_archive_moves_to_archive_dir(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="arch-test", title="T")

        result = osm.archive("arch-test")
        assert result is True

        # Должен быть перемещён в archive/
        assert not (tmp / "openspec" / "changes" / "arch-test").exists()
        assert (tmp / "openspec" / "archive" / "arch-test").exists()

    def test_archive_missing_change(self, setup):
        osm, tmp = setup
        assert osm.archive("missing") is False

    def test_archive_already_archived(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="arch-dup", title="T")
        osm.archive("arch-dup")
        # Повторное архивирование — False
        assert osm.archive("arch-dup") is False


# ─────────────────────────────────────────────

class TestListChanges:
    """Тесты списка changes."""

    def test_list_empty(self, setup):
        osm, tmp = setup
        osm.init_project()
        assert osm.list_changes() == []

    def test_list_active_changes(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="ch-1", title="Change 1", tasks=["T1", "T2"])
        osm.create_proposal(change_id="ch-2", title="Change 2", tasks=["T1"])

        changes = osm.list_changes()
        assert len(changes) == 2
        ids = {c["change_id"] for c in changes}
        assert ids == {"ch-1", "ch-2"}

    def test_list_includes_progress(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="prog-1", title="T", tasks=["T1", "T2", "T3"])
        osm.update_task("prog-1", 0, completed=True)

        changes = osm.list_changes()
        ch = next(c for c in changes if c["change_id"] == "prog-1")
        assert ch["progress"] == "1/3"

    def test_list_include_archived(self, setup):
        osm, tmp = setup
        osm.create_proposal(change_id="ch-1", title="T")
        osm.archive("ch-1")

        # Без include_archived — не показывает
        changes = osm.list_changes()
        assert len(changes) == 0

        # С include_archived — показывает
        changes = osm.list_changes(include_archived=True)
        assert len(changes) == 1
        assert changes[0]["archived"] is True


# ─────────────────────────────────────────────

class TestValidate:
    """Тесты валидации."""

    def test_validate_valid_change(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="valid-1",
            title="T",
            context="C",
            approach="A",
            tasks=["T1"],
        )
        errors = osm.validate("valid-1")
        assert errors == []

    def test_validate_missing_proposal(self, setup):
        osm, tmp = setup
        # Создаём директорию без proposal.md
        change_dir = tmp / "openspec" / "changes" / "broken"
        change_dir.mkdir(parents=True)

        errors = osm.validate("broken")
        assert any("proposal.md" in e for e in errors)

    def test_validate_missing_change(self, setup):
        osm, tmp = setup
        errors = osm.validate("missing")
        assert any("не найден" in e for e in errors)

    def test_validate_empty_context(self, setup):
        osm, tmp = setup
        osm.create_proposal(
            change_id="no-ctx",
            title="T",
            # context не указан
            tasks=["T1"],
        )
        errors = osm.validate("no-ctx")
        assert any("context" in e for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
