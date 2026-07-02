"""
OpenSpecManager — облегчённая версия OpenSpec (Specification-Driven Development).

Позаимствовано из 1c-ai-development-kit (skills openspec-proposal, openspec-apply,
openspec-archive). Реализовано как Python-модуль без внешних CLI зависимостей.

Методология управления изменениями:
1. proposal — что меняем, зачем, влияние
2. design — архитектурные решения
3. tasks — упорядоченный чеклист атомарных задач
4. spec deltas — изменения в спецификациях (ADDED|MODIFIED|REMOVED Requirements)

Структура:
    openspec/
    ├── project.md           — описание проекта
    ├── AGENTS.md            — соглашения (опционально)
    ├── changes/             — активные изменения
    │   └── <change-id>/
    │       ├── proposal.md
    │       ├── design.md    (опционально)
    │       ├── tasks.md
    │       └── specs/
    │           └── <capability>/
    │               └── spec.md
    ├── specs/               — утверждённые спецификации
    └── archive/             — архивные (завершённые) изменения

Жизненный цикл:
    proposal → approve → apply (по tasks.md) → archive

Пример:
    from src.services.openspec_manager import OpenSpecManager

    osm = OpenSpecManager(project_root=Path('.'))
    change = osm.create_proposal(
        change_id="add-cfe-support",
        title="Добавить поддержку CFE расширений",
        context="У нас нет работы с расширениями. Половина проектов использует CFE.",
        approach="Реализовать CfeManager с borrow/patch/diff операциями",
        files=["src/services/cfe_manager.py", "tests/test_cfe_manager.py"],
        tasks=[
            "Создать CfeManager класс",
            "Реализовать borrow_object (ObjectBelonging=Adopted)",
            "Реализовать patch_method (&Перед/&После/&ИзменениеИКонтроль)",
            "Реализовать diff (анализ расширения)",
            "Написать тесты (минимум 20)",
        ],
    )
    # Выполняем задачи, обновляем status
    osm.update_task("add-cfe-support", 0, completed=True)
    osm.archive("add-cfe-support")  # после завершения
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Task:
    """Атомарная задача в change."""

    description: str
    completed: bool = False
    notes: str = ""

    def to_markdown(self, index: int) -> str:
        checkbox = "[x]" if self.completed else "[ ]"
        notes = f"  — {self.notes}" if self.notes else ""
        return f"{index}. {checkbox} {self.description}{notes}"

    @classmethod
    def from_markdown(cls, line: str) -> Task | None:
        """Парсит строку '1. [x] Описание' или '1. [ ] Описание'."""
        m = re.match(r"\d+\.\s+\[([x ])\]\s+(.+?)(?:\s+—\s+(.+))?$", line)
        if not m:
            return None
        return cls(
            description=m.group(2).strip(),
            completed=m.group(1).lower() == "x",
            notes=m.group(3) or "",
        )


@dataclass
class SpecDelta:
    """Изменение в спецификации (ADDED|MODIFIED|REMOVED)."""

    action: str  # ADDED | MODIFIED | REMOVED
    capability: str  # например "cfe-management"
    requirement: str
    scenario: str = ""

    def to_markdown(self) -> str:
        lines = [f"## {self.action} Requirements", ""]
        lines.append(f"### Requirement: {self.requirement}")
        lines.append("")
        if self.scenario:
            lines.append(f"#### Scenario: {self.scenario}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class Change:
    """OpenSpec change — предложение изменения."""

    change_id: str
    title: str = ""
    context: str = ""
    environment: str = ""
    compatibility: str = ""
    approach: str = ""
    files: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    spec_deltas: list[SpecDelta] = field(default_factory=list)
    created_at: str = ""
    status: str = "proposed"  # proposed | approved | in_progress | completed | archived

    def to_proposal_markdown(self) -> str:
        """Markdown для proposal.md."""
        lines = [f"# SDD: {self.title}", ""]
        lines.append(f"**Change ID:** `{self.change_id}`")
        lines.append(f"**Status:** {self.status}")
        if self.created_at:
            lines.append(f"**Created:** {self.created_at}")
        lines.append("")

        lines.append("## Context")
        lines.append(self.context or "(не указан)")
        lines.append("")

        if self.environment:
            lines.append("## Environment")
            lines.append(self.environment)
            lines.append("")

        if self.compatibility:
            lines.append("## Compatibility")
            lines.append(self.compatibility)
            lines.append("")

        lines.append("## Approach")
        lines.append(self.approach or "(не указан)")
        lines.append("")

        if self.files:
            lines.append("## Files")
            for f in self.files:
                lines.append(f"- `{f}`")
            lines.append("")

        if self.spec_deltas:
            lines.append("## Spec Deltas")
            for delta in self.spec_deltas:
                lines.append(delta.to_markdown())
                lines.append("")

        return "\n".join(lines)

    def to_tasks_markdown(self) -> str:
        """Markdown для tasks.md."""
        lines = [f"# Tasks: {self.change_id}", ""]
        lines.append(f"**Status:** {self.status}")
        lines.append("")

        completed = sum(1 for t in self.tasks if t.completed)
        total = len(self.tasks)
        lines.append(f"**Progress:** {completed}/{total}")
        lines.append("")

        if self.tasks:
            lines.append("## Atomic Tasks")
            lines.append("")
            for i, task in enumerate(self.tasks, 1):
                lines.append(task.to_markdown(i))
            lines.append("")

        return "\n".join(lines)

    def to_design_markdown(self) -> str:
        """Markdown для design.md (шаблон)."""
        return f"""# Design: {self.title}

## Архитектурные решения

(Описать ключевые архитектурные решения и их обоснование)

## Альтернативы рассмотренные

(Какие альтернативы рассматривались и почему отвергнуты)

## Влияние на существующий код

(Что изменится в существующем коде)

## Тестирование

(Как будет тестироваться изменение)

## Change ID: `{self.change_id}`
"""


class OpenSpecManager:
    """Управление OpenSpec changes — создание, обновление, архивирование."""

    def __init__(self, project_root: Path):
        self._root = Path(project_root)
        self._openspec_dir = self._root / "openspec"
        self._changes_dir = self._openspec_dir / "changes"
        self._specs_dir = self._openspec_dir / "specs"
        self._archive_dir = self._openspec_dir / "archive"

    def init_project(
        self,
        project_name: str = "",
        description: str = "",
    ) -> Path:
        """Инициализировать openspec/ структуру.

        Создаёт:
        - openspec/project.md
        - openspec/changes/
        - openspec/specs/
        - openspec/archive/
        """
        self._changes_dir.mkdir(parents=True, exist_ok=True)
        self._specs_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        project_md = self._openspec_dir / "project.md"
        if not project_md.exists():
            project_md.write_text(
                f"# Project: {project_name or '1C AI Dev Environment'}\n\n"
                f"{description or 'OpenSpec specifications for the project.'}\n\n"
                f"## Capabilities\n\n"
                f"(Список capabilities будет добавляться по мере создания specs)\n",
                encoding="utf-8",
            )

        return self._openspec_dir

    def create_proposal(
        self,
        change_id: str,
        title: str,
        context: str = "",
        approach: str = "",
        environment: str = "",
        compatibility: str = "",
        files: list[str] | None = None,
        tasks: list[str] | None = None,
        spec_deltas: list[SpecDelta] | None = None,
        design: bool = False,
    ) -> Change:
        """Создать новый change (proposal).

        Создаёт структуру openspec/changes/<change-id>/ с:
        - proposal.md
        - tasks.md
        - design.md (если design=True)
        - specs/<capability>/spec.md (если есть spec_deltas)

        Args:
            change_id: уникальный ID (глагол-существительное, например "add-cfe-support")
            title: заголовок изменения
            context: зачем нужно изменение
            approach: как будем делать
            files: список затрагиваемых файлов
            tasks: список атомарных задач
            spec_deltas: изменения в спецификациях
            design: создавать ли design.md
        """
        # Валидация change_id — только строчные буквы, цифры, дефисы
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", change_id):
            raise ValueError(
                f"Неверный change_id: '{change_id}'. "
                "Должен быть в формате глагол-существительное (например: add-cfe-support)"
            )

        change_dir = self._changes_dir / change_id
        if change_dir.exists():
            raise FileExistsError(f"Change '{change_id}' уже существует: {change_dir}")

        change_dir.mkdir(parents=True, exist_ok=True)

        change = Change(
            change_id=change_id,
            title=title,
            context=context,
            approach=approach,
            environment=environment,
            compatibility=compatibility,
            files=files or [],
            tasks=[Task(description=t) for t in (tasks or [])],
            spec_deltas=spec_deltas or [],
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            status="proposed",
        )

        # proposal.md
        (change_dir / "proposal.md").write_text(
            change.to_proposal_markdown(),
            encoding="utf-8",
        )

        # tasks.md
        (change_dir / "tasks.md").write_text(
            change.to_tasks_markdown(),
            encoding="utf-8",
        )

        # design.md (опционально)
        if design:
            (change_dir / "design.md").write_text(
                change.to_design_markdown(),
                encoding="utf-8",
            )

        # spec deltas
        if change.spec_deltas:
            specs_dir = change_dir / "specs"
            specs_dir.mkdir(exist_ok=True)
            # Группируем по capability
            by_capability: dict[str, list[SpecDelta]] = {}
            for delta in change.spec_deltas:
                by_capability.setdefault(delta.capability, []).append(delta)
            for cap, deltas in by_capability.items():
                cap_dir = specs_dir / cap
                cap_dir.mkdir(parents=True, exist_ok=True)
                content = f"# Spec: {cap}\n\n"
                for delta in deltas:
                    content += delta.to_markdown() + "\n"
                (cap_dir / "spec.md").write_text(content, encoding="utf-8")

        return change

    def load_change(self, change_id: str) -> Change | None:
        """Загрузить существующий change из файловой системы."""
        change_dir = self._changes_dir / change_id
        if not change_dir.exists():
            return None

        # Парсим proposal.md
        proposal_path = change_dir / "proposal.md"
        if not proposal_path.exists():
            return None

        proposal = proposal_path.read_text(encoding="utf-8")

        # Извлекаем метаданные
        title_match = re.search(r"^# SDD:\s+(.+)$", proposal, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else change_id

        status_match = re.search(r"\*\*Status:\*\*\s+(\w+)", proposal)
        status = status_match.group(1) if status_match else "proposed"

        created_match = re.search(r"\*\*Created:\*\*\s+(.+)$", proposal, re.MULTILINE)
        created_at = created_match.group(1).strip() if created_match else ""

        # Извлекаем секции
        context = self._extract_section(proposal, "Context")
        approach = self._extract_section(proposal, "Approach")
        environment = self._extract_section(proposal, "Environment")
        compatibility = self._extract_section(proposal, "Compatibility")

        # Files
        files: list[str] = []
        files_section = self._extract_section(proposal, "Files")
        if files_section:
            for line in files_section.split("\n"):
                m = re.match(r"-\s+`(.+)`", line)
                if m:
                    files.append(m.group(1))

        # Парсим tasks.md
        tasks: list[Task] = []
        tasks_path = change_dir / "tasks.md"
        if tasks_path.exists():
            tasks_content = tasks_path.read_text(encoding="utf-8")
            for line in tasks_content.split("\n"):
                task = Task.from_markdown(line)
                if task:
                    tasks.append(task)

        return Change(
            change_id=change_id,
            title=title,
            context=context,
            approach=approach,
            environment=environment,
            compatibility=compatibility,
            files=files,
            tasks=tasks,
            created_at=created_at,
            status=status,
        )

    @staticmethod
    def _extract_section(markdown: str, section_name: str) -> str:
        """Извлечь содержимое секции ## SectionName."""
        pattern = rf"## {section_name}\s*\n(.+?)(?=\n## |\Z)"
        m = re.search(pattern, markdown, re.DOTALL)
        if m:
            return m.group(1).strip()
        return ""

    def update_task(
        self,
        change_id: str,
        task_index: int,
        completed: bool | None = None,
        notes: str = "",
    ) -> bool:
        """Обновить статус задачи.

        Args:
            change_id: ID изменения
            task_index: индекс задачи (0-based)
            completed: True/None (None = переключить)
            notes: заметки к задаче

        Returns:
            True если задача обновлена
        """
        change = self.load_change(change_id)
        if not change or task_index >= len(change.tasks):
            return False

        task = change.tasks[task_index]
        if completed is None:
            task.completed = not task.completed
        else:
            task.completed = completed
        if notes:
            task.notes = notes

        # Пересохраняем tasks.md
        change_dir = self._changes_dir / change_id
        (change_dir / "tasks.md").write_text(
            change.to_tasks_markdown(),
            encoding="utf-8",
        )

        # Если все задачи выполнены — меняем статус
        if all(t.completed for t in change.tasks):
            change.status = "completed"
            self._update_status(change_id, "completed")

        return True

    def update_status(self, change_id: str, status: str) -> bool:
        """Обновить статус change (public API)."""
        return self._update_status(change_id, status)

    def _update_status(self, change_id: str, status: str) -> bool:
        """Внутренний метод обновления статуса."""
        change = self.load_change(change_id)
        if not change:
            return False

        change.status = status
        change_dir = self._changes_dir / change_id

        # Переписываем proposal.md с новым статусом
        (change_dir / "proposal.md").write_text(
            change.to_proposal_markdown(),
            encoding="utf-8",
        )

        # Обновляем tasks.md
        (change_dir / "tasks.md").write_text(
            change.to_tasks_markdown(),
            encoding="utf-8",
        )

        return True

    def archive(self, change_id: str) -> bool:
        """Архивировать завершённый change.

        Перемещает openspec/changes/<id>/ → openspec/archive/<id>/
        """
        change_dir = self._changes_dir / change_id
        if not change_dir.exists():
            return False

        self._archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self._archive_dir / change_id

        if archive_path.exists():
            return False  # уже заархивирован

        change_dir.rename(archive_path)
        return True

    def list_changes(self, include_archived: bool = False) -> list[dict]:
        """Список всех changes.

        Args:
            include_archived: включать архивные

        Returns:
            [{"change_id": "...", "title": "...", "status": "...", "progress": "3/5"}, ...]
        """
        result = []

        # Активные changes
        if self._changes_dir.exists():
            for d in sorted(self._changes_dir.iterdir()):
                if d.is_dir():
                    change = self.load_change(d.name)
                    if change:
                        completed = sum(1 for t in change.tasks if t.completed)
                        total = len(change.tasks)
                        result.append(
                            {
                                "change_id": change.change_id,
                                "title": change.title,
                                "status": change.status,
                                "progress": f"{completed}/{total}",
                                "archived": False,
                            }
                        )

        # Архивные
        if include_archived and self._archive_dir.exists():
            for d in sorted(self._archive_dir.iterdir()):
                if d.is_dir():
                    result.append(
                        {
                            "change_id": d.name,
                            "title": "(архив)",
                            "status": "archived",
                            "progress": "-",
                            "archived": True,
                        }
                    )

        return result

    def validate(self, change_id: str) -> list[str]:
        """Валидация структуры change.

        Возвращает список ошибок (пустой если всё ок).
        """
        errors: list[str] = []
        change_dir = self._changes_dir / change_id
        if not change_dir.exists():
            return [f"Change '{change_id}' не найден"]

        # proposal.md обязателен
        if not (change_dir / "proposal.md").exists():
            errors.append("proposal.md отсутствует")

        # tasks.md обязателен
        if not (change_dir / "tasks.md").exists():
            errors.append("tasks.md отсутствует")

        # Парсим change
        change = self.load_change(change_id)
        if change:
            if not change.title or change.title == "(не указан)":
                errors.append("title не указан в proposal.md")
            if not change.context or change.context == "(не указан)":
                errors.append("context не указан в proposal.md")
            if not change.approach or change.approach == "(не указан)":
                errors.append("approach не указан в proposal.md")
            if not change.tasks:
                errors.append("tasks пуст — должно быть хотя бы одна задача")
            # Каждый spec delta должен иметь scenario
            for delta in change.spec_deltas:
                if not delta.scenario:
                    errors.append(f"spec delta '{delta.requirement}' не имеет scenario")

        return errors

    def exists(self) -> bool:
        """Проверить инициализирован ли openspec."""
        return self._openspec_dir.exists()
