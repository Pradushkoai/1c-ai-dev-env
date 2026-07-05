"""
T5.8 (2026-07-06): Form Element Builder — высокоуровневые UI элементы формы.

Существующий form_elem_builder.py генерирует Form.elem.json (внутренний формат
v8unpack для реквизитов). Этот модуль добавляет генерацию UI элементов формы
(Form.xml) — кнопки, поля ввода, таблицы, группы.

Элементы:
1. FormButton — кнопка с действием
2. FormInputField — поле ввода с привязкой к реквизиту
3. FormLabel — надпись
4. FormGroup — группа элементов (с заголовком)
5. FormTable — таблица на форме с колонками
6. FormCheckBox — флажок
7. FormRadioButton — переключатель
8. FormCommandBar — командная панель
9. FormPage — страница (закладка)

Каждый элемент генерирует XML-фрагмент для Form.xml (managed form).

Использование:
    from src.services.form_ui_builder import FormUIBuilder

    builder = FormUIBuilder()
    form_xml = builder.build_form(
        title="Моя форма",
        elements=[
            FormInputField(name="Номер", data_path="Объект.Номер"),
            FormButton(name="Выполнить", action="ВыполнитьОбработку"),
            FormGroup(name="Группа1", title="Параметры", elements=[
                FormInputField(name="Дата", data_path="Объект.Дата"),
            ]),
        ]
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ============================================================================
# Base element
# ============================================================================


@dataclass
class FormElement:
    """Базовый класс для элементов формы."""

    name: str
    id: int = 0   # назначается автоматически

    def to_xml(self, indent: int = 1) -> str:
        """Сгенерировать XML-фрагмент элемента.

        Args:
            indent: Уровень отступа (1 = один таб).

        Returns:
            XML-строка с отступами.
        """
        raise NotImplementedError

    @staticmethod
    def _indent(level: int) -> str:
        return "\t" * level


# ============================================================================
# Concrete elements
# ============================================================================


@dataclass
class FormButton(FormElement):
    """Кнопка формы."""

    title: str = ""
    action: str = ""
    command_name: str = ""      # если задано, используется Form.Command.<command_name>
    type: str = "UsualButton"   # UsualButton, CommandBarButton, etc.

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        title = self.title or self.name
        action = self.action or self.name
        cmd_ref = self.command_name or self.name
        return (
            f'{tab}<Button name="{self.name}" id="{self.id}">\n'
            f'{tab}\t<Type>{self.type}</Type>\n'
            f'{tab}\t<CommandName>Form.Command.{cmd_ref}</CommandName>\n'
            f'{tab}\t<Title>\n'
            f'{tab}\t\t<v8:item>\n'
            f'{tab}\t\t\t<v8:lang>ru</v8:lang>\n'
            f'{tab}\t\t\t<v8:content>{title}</v8:content>\n'
            f'{tab}\t\t</v8:item>\n'
            f'{tab}\t</Title>\n'
            f'{tab}\t<Action>{action}</Action>\n'
            f'{tab}</Button>'
        )


@dataclass
class FormInputField(FormElement):
    """Поле ввода с привязкой к реквизиту."""

    data_path: str = ""           # например, "Объект.Номер"
    title: str = ""
    input_type: str = "InputField"   # InputField, LabelField, PictureField
    width: int = 0                 # 0 = auto
    format_string: str = ""        # для чисел/дат

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        lines = [
            f'{tab}<InputField name="{self.name}" id="{self.id}">',
            f'{tab}\t<DataPath>{self.data_path}</DataPath>',
            f'{tab}\t<ContextMenu name="{self.name}КонтекстноеМеню" id="{self.id + 1}"/>',
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 2}"/>',
        ]
        if self.width > 0:
            lines.append(f'{tab}\t<Width>{self.width}</Width>')
        if self.format_string:
            lines.append(f'{tab}\t<Format><v8:item>'
                        f'<v8:lang>ru</v8:lang>'
                        f'<v8:content>{self.format_string}</v8:content>'
                        f'</v8:item></Format>')
        lines.append(f'{tab}</InputField>')
        return "\n".join(lines)


@dataclass
class FormLabel(FormElement):
    """Надпись (статичный текст)."""

    title: str = ""

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        return (
            f'{tab}<Label name="{self.name}" id="{self.id}">\n'
            f'{tab}\t<Title>\n'
            f'{tab}\t\t<v8:item>\n'
            f'{tab}\t\t\t<v8:lang>ru</v8:lang>\n'
            f'{tab}\t\t\t<v8:content>{self.title or self.name}</v8:content>\n'
            f'{tab}\t\t</v8:item>\n'
            f'{tab}\t</Title>\n'
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 1}"/>\n'
            f'{tab}</Label>'
        )


@dataclass
class FormCheckBox(FormElement):
    """Флажок."""

    data_path: str = ""
    title: str = ""

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        return (
            f'{tab}<CheckBoxField name="{self.name}" id="{self.id}">\n'
            f'{tab}\t<DataPath>{self.data_path}</DataPath>\n'
            f'{tab}\t<CheckBoxType>Auto</CheckBoxType>\n'
            f'{tab}\t<ContextMenu name="{self.name}КонтекстноеМеню" id="{self.id + 1}"/>\n'
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 2}"/>\n'
            f'{tab}</CheckBoxField>'
        )


@dataclass
class FormTable(FormElement):
    """Таблица на форме с колонками."""

    data_path: str = ""
    title: str = ""
    columns: list[FormTableColumn] = field(default_factory=list)

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        lines = [
            f'{tab}<Table name="{self.name}" id="{self.id}">',
            f'{tab}\t<Representation>List</Representation>',
            f'{tab}\t<DataPath>{self.data_path}</DataPath>',
            f'{tab}\t<RowSelectionMode>Row</RowSelectionMode>',
            f'{tab}\t<AutoAddIncomplete>false</AutoAddIncomplete>',
            f'{tab}\t<AutoFill>false</AutoFill>',
            f'{tab}\t<ChildItems>',
        ]
        col_id = self.id + 10
        for col in self.columns:
            col.id = col_id
            lines.append(col.to_xml(indent + 2))
            col_id += 10
        lines.append(f'{tab}\t</ChildItems>')
        lines.append(f'{tab}</Table>')
        return "\n".join(lines)


@dataclass
class FormTableColumn:
    """Колонка таблицы формы."""

    name: str
    data_path: str = ""
    title: str = ""
    id: int = 0

    def to_xml(self, indent: int = 1) -> str:
        tab = "\t" * indent
        return (
            f'{tab}<InputField name="{self.name}" id="{self.id}">\n'
            f'{tab}\t<DataPath>{self.data_path}</DataPath>\n'
            f'{tab}\t<EditMode>EnterOnInput</EditMode>\n'
            f'{tab}\t<ContextMenu name="{self.name}КонтекстноеМеню" id="{self.id + 1}"/>\n'
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 2}"/>\n'
            f'{tab}</InputField>'
        )


@dataclass
class FormGroup(FormElement):
    """Группа элементов с заголовком."""

    title: str = ""
    group_type: str = "UsualGroup"   # UsualGroup, PageGroup, Pages
    behavior: str = "Horizontal"     # Horizontal, Vertical
    elements: list[FormElement] = field(default_factory=list)

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        lines = [
            f'{tab}<{self.group_type} name="{self.name}" id="{self.id}">',
            f'{tab}\t<Group>{self.behavior}</Group>',
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 1}"/>',
            f'{tab}\t<ChildItems>',
        ]
        for elem in self.elements:
            lines.append(elem.to_xml(indent + 2))
        lines.append(f'{tab}\t</ChildItems>')
        lines.append(f'{tab}</{self.group_type}>')
        return "\n".join(lines)


@dataclass
class FormPage(FormElement):
    """Страница (закладка) в многостраничной форме."""

    title: str = ""
    elements: list[FormElement] = field(default_factory=list)

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        lines = [
            f'{tab}<Page name="{self.name}" id="{self.id}">',
            f'{tab}\t<Title>',
            f'{tab}\t\t<v8:item>',
            f'{tab}\t\t\t<v8:lang>ru</v8:lang>',
            f'{tab}\t\t\t<v8:content>{self.title or self.name}</v8:content>',
            f'{tab}\t\t</v8:item>',
            f'{tab}\t</Title>',
            f'{tab}\t<ExtendedTooltip name="{self.name}РасширеннаяПодсказка" id="{self.id + 1}"/>',
            f'{tab}\t<ChildItems>',
        ]
        for elem in self.elements:
            lines.append(elem.to_xml(indent + 2))
        lines.append(f'{tab}\t</ChildItems>')
        lines.append(f'{tab}</Page>')
        return "\n".join(lines)


@dataclass
class FormCommandBar(FormElement):
    """Командная панель с кнопками."""

    buttons: list[FormButton] = field(default_factory=list)

    def to_xml(self, indent: int = 1) -> str:
        tab = self._indent(indent)
        lines = [
            f'{tab}<AutoCommandBar name="{self.name}" id="{self.id}">',
            f'{tab}\t<ChildItems>',
        ]
        for btn in self.buttons:
            lines.append(btn.to_xml(indent + 2))
        lines.append(f'{tab}\t</ChildItems>')
        lines.append(f'{tab}</AutoCommandBar>')
        return "\n".join(lines)


# Type alias для любого элемента формы
FormElementUnion = (
    "FormButton | FormInputField | FormLabel | FormCheckBox | "
    "FormTable | FormGroup | FormPage | FormCommandBar"
)


# ============================================================================
# Builder
# ============================================================================


class FormUIBuilder:
    """T5.8: Builder для генерации Form.xml (managed form).

    Принимает список элементов формы и генерирует полный XML-документ,
    готовый для использования в EPF.
    """

    # XML namespaces (стандартные для 1С managed forms)
    XMLNS = (
        'xmlns="http://v8.1c.ru/8.3/xcf/logform" '
        'xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
        'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
        'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
        'xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
        'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
        'version="2.18"'
    )

    def build_form(
        self,
        title: str,
        elements: list[FormElement],
        *,
        form_type: str = "Managed",
        include_command_bar: bool = True,
    ) -> str:
        """Сгенерировать полный Form.xml.

        Args:
            title: Заголовок формы.
            elements: Список элементов (кнопки, поля, группы, таблицы).
            form_type: Тип формы (Managed — управляемая).
            include_command_bar: Добавлять ли автокомандную панель.

        Returns:
            Полный XML-документ Form.xml как строка.
        """
        # Assign IDs sequentially
        next_id = 1
        if include_command_bar:
            next_id = -1   # AutoCommandBar имеет id=-1

        for i, elem in enumerate(elements, start=1):
            if include_command_bar and i == 1:
                # Первый элемент после command bar
                elem.id = 1
            else:
                elem.id = next_id + i if not include_command_bar else i

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<Form {self.XMLNS}>',
        ]

        if include_command_bar:
            lines.append('\t<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>')

        # Title
        lines.append('\t<ChildItems>')

        for elem in elements:
            lines.append(elem.to_xml(indent=2))

        lines.append('\t</ChildItems>')

        # Commands (если есть кнопки с actions)
        buttons_with_actions = [
            e for e in elements if isinstance(e, FormButton) and e.action
        ]
        if buttons_with_actions:
            lines.append('\t<Commands>')
            for btn in buttons_with_actions:
                title = btn.title or btn.name
                lines.extend([
                    f'\t\t<Command name="{btn.name}" id="{btn.id + 100}">',
                    '\t\t\t<Title>',
                    '\t\t\t\t<v8:item>',
                    '\t\t\t\t\t<v8:lang>ru</v8:lang>',
                    f'\t\t\t\t\t<v8:content>{title}</v8:content>',
                    '\t\t\t\t</v8:item>',
                    '\t\t\t</Title>',
                    f'\t\t\t<Action>{btn.action}</Action>',
                    '\t\t</Command>',
                ])
            lines.append('\t</Commands>')

        lines.append('</Form>')
        return "\n".join(lines)

    def build_simple_form(
        self,
        title: str,
        fields: list[dict[str, str]],
        buttons: list[dict[str, str]] | None = None,
    ) -> str:
        """Удобный метод для простой формы с полями и кнопками.

        Args:
            title: Заголовок формы.
            fields: Список {"name", "data_path", "title"}.
            buttons: Список {"name", "title", "action"}.

        Returns:
            Form.xml как строка.
        """
        elements: list[FormElement] = []

        for f in fields:
            elements.append(FormInputField(
                name=f["name"],
                data_path=f.get("data_path", f["name"]),
                title=f.get("title", f["name"]),
            ))

        for b in (buttons or []):
            elements.append(FormButton(
                name=b["name"],
                title=b.get("title", b["name"]),
                action=b.get("action", b["name"]),
            ))

        return self.build_form(title=title, elements=elements)


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для form UI builder (демо)."""
    import argparse

    parser = argparse.ArgumentParser(description="Form UI Builder demo")
    parser.add_argument("--title", default="Демо форма")
    args = parser.parse_args()

    builder = FormUIBuilder()
    form_xml = builder.build_form(
        title=args.title,
        elements=[
            FormInputField(name="Номер", data_path="Объект.Номер", title="Номер"),
            FormInputField(name="Дата", data_path="Объект.Дата", title="Дата"),
            FormCheckBox(name="Выполнено", data_path="Объект.Выполнено", title="Выполнено"),
            FormGroup(name="ГруппаКнопок", title="Действия", elements=[
                FormButton(name="Выполнить", title="Выполнить", action="ВыполнитьОбработку"),
                FormButton(name="Закрыть", title="Закрыть", action="Закрыть"),
            ]),
        ],
    )
    print(form_xml)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
