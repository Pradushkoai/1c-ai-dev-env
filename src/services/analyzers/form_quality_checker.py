#!/usr/bin/env python3
"""
form_quality_checker.py — Проверка качества форм 1С.

Анализирует form-index.json и находит проблемы:
1. Формы без элементов (пустые формы)
2. Перегруженные формы (> 100 элементов)
3. Элементы без DataPath (не привязаны к данным)
4. Формы без событий (нет обработчиков)
5. Дублирующие имена элементов
6. Таблицы без колонок
7. Кнопки без CommandName
8. Слишком глубокая вложенность (> 5 уровней)
9. Формы с > 10 кнопками (перегруженный UI)
10. Скрытые элементы (Visible=false)

Использование:
    from form_quality_checker import FormQualityChecker
    checker = FormQualityChecker()
    issues = checker.check_form_index(Path('form-index.json'))
"""

from __future__ import annotations
from typing import Any

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FormQualityIssue:
    rule_id: str
    severity: str
    form_name: str
    parent_name: str
    message: str
    recommendation: str = ""


class FormQualityChecker:
    """Проверка качества форм 1С."""

    MAX_ELEMENTS = 100
    MAX_BUTTONS = 10
    MAX_NESTING = 5

    def check_form_index(self, index_path: Path) -> list[FormQualityIssue]:
        """Проверка form-index.json."""
        try:
            with open(index_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        issues = []
        for form_data in data.get("forms", []):
            issues.extend(self._check_form(form_data))

        return issues

    def check_form(self, form_data: dict[str, Any]) -> list[FormQualityIssue]:
        """Проверка одной формы."""
        return self._check_form(form_data)

    def _check_form(self, form_data: dict[str, Any]) -> list[FormQualityIssue]:
        issues = []
        form_name = form_data.get("name", "")
        parent_name = form_data.get("parent_name", "")
        form = form_data.get("form", {})

        element_count = form.get("element_count", 0)
        items = form.get("items", [])

        # FQ001: Пустая форма (0 элементов)
        if element_count == 0 and not items:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ001",
                    severity="LOW",
                    form_name=form_name,
                    parent_name=parent_name,
                    message="Форма без элементов — возможно неиспользуемая",
                    recommendation="Проверьте, нужна ли эта форма",
                )
            )

        # FQ002: Перегруженная форма (> 100 элементов)
        if element_count > self.MAX_ELEMENTS:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ002",
                    severity="HIGH",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"Перегруженная форма: {element_count} элементов (рекомендуется < {self.MAX_ELEMENTS})",
                    recommendation="Разбейте форму на несколько страниц или используйте сворачиваемые группы",
                )
            )

        # Рекурсивная проверка элементов
        button_count = [0]
        no_datapath_count = [0]
        no_command_count = [0]
        hidden_count = [0]
        deep_nesting_count = [0]
        names = []

        self._check_items(
            items,
            issues,
            form_name,
            parent_name,
            button_count,
            no_datapath_count,
            no_command_count,
            hidden_count,
            deep_nesting_count,
            names,
            nesting=0,
        )

        # FQ003: Элементы без DataPath
        if no_datapath_count[0] > 5:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ003",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"{no_datapath_count[0]} элементов без DataPath (не привязаны к данным)",
                    recommendation="Проверьте, все ли элементы привязаны к данным через DataPath",
                )
            )

        # FQ004: Кнопки без CommandName
        if no_command_count[0] > 0:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ004",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"{no_command_count[0]} кнопок без CommandName",
                    recommendation="Каждая кнопка должна иметь привязку к команде",
                )
            )

        # FQ005: Слишком много кнопок
        if button_count[0] > self.MAX_BUTTONS:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ005",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"Слишком много кнопок: {button_count[0]} (рекомендуется < {self.MAX_BUTTONS})",
                    recommendation="Сгруппируйте кнопки в подменю или используйте контекстное меню",
                )
            )

        # FQ006: Скрытые элементы
        if hidden_count[0] > 3:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ006",
                    severity="LOW",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"{hidden_count[0]} скрытых элементов (Visible=false)",
                    recommendation="Проверьте, нужны ли скрытые элементы. Возможно их можно удалить",
                )
            )

        # FQ007: Глубокая вложенность
        if deep_nesting_count[0] > 0:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ007",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"{deep_nesting_count[0]} элементов с вложенностью > {self.MAX_NESTING}",
                    recommendation=f"Уменьшите вложенность до {self.MAX_NESTING} уровней",
                )
            )

        # FQ008: Дублирующие имена
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            issues.append(
                FormQualityIssue(
                    rule_id="FQ008",
                    severity="HIGH",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"Дублирующие имена элементов: {set(duplicates)}",
                    recommendation="Имена элементов должны быть уникальными",
                )
            )

        # FQ009: Форма без событий
        events = form.get("events", [])
        if not events and element_count > 5:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ009",
                    severity="LOW",
                    form_name=form_name,
                    parent_name=parent_name,
                    message="Форма без обработчиков событий",
                    recommendation="Проверьте, нужна ли интерактивность форме",
                )
            )

        # ====================================================================
        # KB-EXP-3: Усиление по стандартам v8std.ru / ITS
        # ====================================================================

        # FQ010: Слишком много элементов в командной панели (#std711)
        # https://v8std.ru/std/711/
        cmd_panel_items = form.get("command_panel_items", [])
        if not cmd_panel_items:
            # Альтернативный путь: ищем элементы с типом CommandPanel
            cmd_panel_items = [
                i for i in items if isinstance(i, dict)
                and "CommandPanel" in str(i.get("type", ""))
            ]
        if len(cmd_panel_items) > 15:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ010",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"Слишком много элементов в командной панели ({len(cmd_panel_items)})",
                    recommendation=(
                        "По #std711 элементы должны помещаться без прокрутки при стандартном "
                        "разрешении. См. https://v8std.ru/std/711/"
                    ),
                )
            )

        # FQ011: Элементы без заголовка у таблиц/групп (#std765)
        # https://v8std.ru/std/765/
        for item in items:
            item_type = str(item.get("type", ""))
            if any(t in item_type for t in ("Table", "Group", "Page")):
                title = item.get("title", "") or item.get("header", "")
                if not title and not item.get("titleHidden", False):
                    issues.append(
                        FormQualityIssue(
                            rule_id="FQ011",
                            severity="LOW",
                            form_name=form_name,
                            parent_name=parent_name,
                            message=(
                                f"Элемент '{item.get('name', '?')}' типа {item_type} без заголовка "
                                f"(#std765)"
                            ),
                            recommendation=(
                                "Задавайте заголовки таблицам и группам. Если не нужен — "
                                "явно отключите показ. См. https://v8std.ru/std/765/"
                            ),
                        )
                    )

        # FQ012: Форма со слишком большим количеством реквизитов
        # Большие формы медленно передаются между клиентом и сервером (#std744)
        # https://v8std.ru/std/744/
        attrs = form.get("attributes", [])
        if len(attrs) > 50:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ012",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message=f"Слишком много реквизитов формы ({len(attrs)})",
                    recommendation=(
                        "Большие формы медленно передаются между клиентом и сервером (#std744). "
                        "Разделите на несколько форм или используйте динамический список. "
                        "См. https://v8std.ru/std/744/"
                    ),
                )
            )

        # FQ013: Модальное открытие формы (#std400)
        # https://v8std.ru/std/400/
        # Эвристика: ищем в событиях формы модальные вызовы
        events_str = json.dumps(events, ensure_ascii=False) if events else ""
        modal_patterns = ["ОткрытьМодально", "DoModal", "ОткрытьЗначение("]
        if any(p in events_str for p in modal_patterns):
            issues.append(
                FormQualityIssue(
                    rule_id="FQ013",
                    severity="HIGH",
                    form_name=form_name,
                    parent_name=parent_name,
                    message="Модальное открытие формы (#std400)",
                    recommendation=(
                        "Используйте асинхронные методы: ОткрытьФорму, ПоказатьВопрос, "
                        "ПоказатьПредупреждение. См. https://v8std.ru/std/400/"
                    ),
                )
            )

        # FQ014: Использование Сообщить в обработчике формы (#std418)
        # https://v8std.ru/std/418/
        if "Сообщить(" in events_str:
            issues.append(
                FormQualityIssue(
                    rule_id="FQ014",
                    severity="MEDIUM",
                    form_name=form_name,
                    parent_name=parent_name,
                    message="Использование Сообщить в обработчиках формы (#std418)",
                    recommendation=(
                        "Используйте СообщениеПользователю вместо Сообщить. "
                        "См. https://v8std.ru/std/418/"
                    ),
                )
            )

        return issues

    def _check_items(
        self,
        items,
        issues,
        form_name,
        parent_name,
        button_count,
        no_datapath,
        no_command,
        hidden_count,
        deep_nesting,
        names,
        nesting,
    ):
        """Рекурсивная проверка элементов формы."""
        for item in items:
            item_type = item.get("type", "")
            item_name = item.get("name", "")
            data_path = item.get("data_path", "")
            visible = item.get("visible", True)
            command_name = item.get("command_name", "")

            if item_name:
                names.append(item_name)

            # Подсчёт кнопок
            if item_type == "Button":
                button_count[0] += 1
                if not command_name:
                    no_command[0] += 1

            # Без DataPath (кроме групп, страниц, кнопок)
            if not data_path and item_type not in (
                "UsualGroup",
                "Pages",
                "Page",
                "Button",
                "CommandBar",
                "AutoCommandBar",
                "ExtendedTooltip",
                "ContextMenu",
                "Label",
            ):
                no_datapath[0] += 1

            # Скрытые
            if not visible:
                hidden_count[0] += 1

            # Глубокая вложенность
            if nesting > self.MAX_NESTING:
                deep_nesting[0] += 1

            # Рекурсия
            children = item.get("children", [])
            if children:
                self._check_items(
                    children,
                    issues,
                    form_name,
                    parent_name,
                    button_count,
                    no_datapath,
                    no_command,
                    hidden_count,
                    deep_nesting,
                    names,
                    nesting + 1,
                )

    def get_stats(self, issues: list[FormQualityIssue]) -> dict[str, Any]:
        from collections import Counter

        return {
            "total": len(issues),
            "by_severity": dict[str, Any](Counter(i.severity for i in issues)),
            "by_rule": dict[str, Any](Counter(i.rule_id for i in issues)),
        }


# CLI вынесен в scripts/form_quality_checker.py (Этап 1.2, Группа 1a)
