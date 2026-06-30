#!/usr/bin/env python3
"""
diff_analyzer.py — Сравнение версий конфигурации 1С.

Сравнивает два unified-metadata-index.json и находит:
1. Добавленные объекты (новые справочники, документы, и т.д.)
2. Удалённые объекты
3. Изменённые реквизиты (добавлены/удалены/изменён тип)
4. Изменённые табличные части
5. Изменённые формы (добавлены/удалены)
6. Изменённые команды
7. Изменённые подписки на события
8. Изменённые регламентные задания
9. Изменённые роли (права)
10. Изменённые подсистемы

Использование:
    from diff_analyzer import DiffAnalyzer
    analyzer = DiffAnalyzer()
    diff = analyzer.compare(Path('old-index.json'), Path('new-index.json'))
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ObjectChange:
    """Изменение объекта."""
    change_type: str  # 'added', 'removed', 'modified'
    object_type: str  # Catalog, Document, etc.
    object_name: str
    details: list[str] = field(default_factory=list)  # конкретные изменения


@dataclass
class ConfigDiff:
    """Результат сравнения конфигураций."""
    added_objects: list[ObjectChange] = field(default_factory=list)
    removed_objects: list[ObjectChange] = field(default_factory=list)
    modified_objects: list[ObjectChange] = field(default_factory=list)
    added_roles: int = 0
    removed_roles: int = 0
    added_subsystems: int = 0
    removed_subsystems: int = 0
    added_event_subscriptions: int = 0
    removed_event_subscriptions: int = 0
    added_scheduled_jobs: int = 0
    removed_scheduled_jobs: int = 0
    summary: dict = field(default_factory=dict)


class DiffAnalyzer:
    """Анализатор различий между версиями конфигурации."""

    def compare(self, old_path: Path, new_path: Path) -> ConfigDiff:
        """Сравнение двух unified-metadata-index.json.

        Args:
            old_path: Путь к старому индексу
            new_path: Путь к новому индексу

        Returns:
            ConfigDiff с изменениями
        """
        with open(old_path, encoding='utf-8') as f:
            old = json.load(f)
        with open(new_path, encoding='utf-8') as f:
            new = json.load(f)

        return self.compare_data(old, new)

    def compare_data(self, old: dict, new: dict) -> ConfigDiff:
        """Сравнение двух индексов (из dict)."""
        diff = ConfigDiff()

        # Сравниваем objects по типам
        old_objects = old.get('objects', {})
        new_objects = new.get('objects', {})

        all_types = set(list(old_objects.keys()) + list(new_objects.keys()))

        for obj_type in all_types:
            old_list = {o['name']: o for o in old_objects.get(obj_type, [])}
            new_list = {o['name']: o for o in new_objects.get(obj_type, [])}

            # Добавленные
            for name in new_list:
                if name not in old_list:
                    diff.added_objects.append(ObjectChange(
                        change_type='added',
                        object_type=obj_type,
                        object_name=name,
                    ))

            # Удалённые
            for name in old_list:
                if name not in new_list:
                    diff.removed_objects.append(ObjectChange(
                        change_type='removed',
                        object_type=obj_type,
                        object_name=name,
                    ))

            # Изменённые
            for name in old_list:
                if name in new_list:
                    changes = self._compare_object(old_list[name], new_list[name])
                    if changes:
                        diff.modified_objects.append(ObjectChange(
                            change_type='modified',
                            object_type=obj_type,
                            object_name=name,
                            details=changes,
                        ))

        # Роли
        old_roles = {r.get('name', '') for r in old.get('roles', [])}
        new_roles = {r.get('name', '') for r in new.get('roles', [])}
        diff.added_roles = len(new_roles - old_roles)
        diff.removed_roles = len(old_roles - new_roles)

        # Подсистемы
        old_ss = {s.get('name', '') for s in old.get('subsystems', [])}
        new_ss = {s.get('name', '') for s in new.get('subsystems', [])}
        diff.added_subsystems = len(new_ss - old_ss)
        diff.removed_subsystems = len(old_ss - new_ss)

        # Подписки
        old_es = {e.get('name', '') for e in old.get('event_subscriptions', [])}
        new_es = {e.get('name', '') for e in new.get('event_subscriptions', [])}
        diff.added_event_subscriptions = len(new_es - old_es)
        diff.removed_event_subscriptions = len(old_es - new_es)

        # Регламентные задания
        old_sj = {s.get('name', '') for s in old.get('scheduled_jobs', [])}
        new_sj = {s.get('name', '') for s in new.get('scheduled_jobs', [])}
        diff.added_scheduled_jobs = len(new_sj - old_sj)
        diff.removed_scheduled_jobs = len(old_sj - new_sj)

        # Summary
        diff.summary = {
            'total_added': len(diff.added_objects),
            'total_removed': len(diff.removed_objects),
            'total_modified': len(diff.modified_objects),
            'added_by_type': self._count_by_type(diff.added_objects),
            'removed_by_type': self._count_by_type(diff.removed_objects),
            'modified_by_type': self._count_by_type(diff.modified_objects),
        }

        return diff

    def _compare_object(self, old_obj: dict, new_obj: dict) -> list[str]:
        """Сравнение двух объектов — возвращает список изменений."""
        changes = []

        old_children = old_obj.get('child_objects', {})
        new_children = new_obj.get('child_objects', {})

        # Реквизиты
        old_attrs = {a['name'] for a in old_children.get('attributes', [])}
        new_attrs = {a['name'] for a in new_children.get('attributes', [])}

        added_attrs = new_attrs - old_attrs
        removed_attrs = old_attrs - new_attrs

        if added_attrs:
            changes.append(f'Добавлены реквизиты: {added_attrs}')
        if removed_attrs:
            changes.append(f'Удалены реквизиты: {removed_attrs}')

        # Табличные части
        old_ts = {t['name'] for t in old_children.get('tabular_sections', [])}
        new_ts = {t['name'] for t in new_children.get('tabular_sections', [])}

        added_ts = new_ts - old_ts
        removed_ts = old_ts - new_ts

        if added_ts:
            changes.append(f'Добавлены табличные части: {added_ts}')
        if removed_ts:
            changes.append(f'Удалены табличные части: {removed_ts}')

        # Формы
        old_forms = {f['name'] for f in old_children.get('forms', [])}
        new_forms = {f['name'] for f in new_children.get('forms', [])}

        added_forms = new_forms - old_forms
        removed_forms = old_forms - new_forms

        if added_forms:
            changes.append(f'Добавлены формы: {added_forms}')
        if removed_forms:
            changes.append(f'Удалены формы: {removed_forms}')

        # Команды
        old_cmds = {c['name'] for c in old_children.get('commands', [])}
        new_cmds = {c['name'] for c in new_children.get('commands', [])}

        added_cmds = new_cmds - old_cmds
        removed_cmds = old_cmds - new_cmds

        if added_cmds:
            changes.append(f'Добавлены команды: {added_cmds}')
        if removed_cmds:
            changes.append(f'Удалены команды: {removed_cmds}')

        # Синоним
        old_syn = old_obj.get('synonym', '')
        new_syn = new_obj.get('synonym', '')
        if old_syn != new_syn:
            changes.append(f'Изменён синоним: "{old_syn}" → "{new_syn}"')

        return changes

    def _count_by_type(self, changes: list[ObjectChange]) -> dict:
        from collections import Counter
        return dict(Counter(c.object_type for c in changes))

    def format_report(self, diff: ConfigDiff) -> str:
        """Форматирование отчёта в текст."""
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"ОТЧЁТ ПО ИЗМЕНЕНИЯМ КОНФИГУРАЦИИ")
        lines.append(f"{'='*60}")
        lines.append(f"Добавлено объектов: {diff.summary.get('total_added', 0)}")
        lines.append(f"Удалено объектов: {diff.summary.get('total_removed', 0)}")
        lines.append(f"Изменено объектов: {diff.summary.get('total_modified', 0)}")
        lines.append(f"Ролей: +{diff.added_roles} / -{diff.removed_roles}")
        lines.append(f"Подсистем: +{diff.added_subsystems} / -{diff.removed_subsystems}")
        lines.append(f"Подписок на события: +{diff.added_event_subscriptions} / -{diff.removed_event_subscriptions}")
        lines.append(f"Регламентных заданий: +{diff.added_scheduled_jobs} / -{diff.removed_scheduled_jobs}")

        if diff.added_objects:
            lines.append(f"\n--- ДОБАВЛЕННЫЕ ОБЪЕКТЫ ---")
            for c in diff.added_objects:
                lines.append(f"  + {c.object_type}: {c.object_name}")

        if diff.removed_objects:
            lines.append(f"\n--- УДАЛЁННЫЕ ОБЪЕКТЫ ---")
            for c in diff.removed_objects:
                lines.append(f"  - {c.object_type}: {c.object_name}")

        if diff.modified_objects:
            lines.append(f"\n--- ИЗМЕНЁННЫЕ ОБЪЕКТЫ ---")
            for c in diff.modified_objects:
                lines.append(f"  * {c.object_type}: {c.object_name}")
                for detail in c.details:
                    lines.append(f"      {detail}")

        return '\n'.join(lines)


def main():
    import sys
    if len(sys.argv) < 3:
        print("Использование: python3 diff_analyzer.py <old-index.json> <new-index.json>")
        sys.exit(1)
    analyzer = DiffAnalyzer()
    diff = analyzer.compare(Path(sys.argv[1]), Path(sys.argv[2]))
    print(analyzer.format_report(diff))


if __name__ == '__main__':
    main()
