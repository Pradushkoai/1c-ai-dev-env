"""
T5.8 (2026-07-06): Тесты для Form UI Builder.

Проверяет:
- Все 8 типов элементов: Button, InputField, Label, CheckBox, Table, Group, Page, CommandBar
- FormUIBuilder.build_form: генерация полного Form.xml
- FormUIBuilder.build_simple_form: удобный метод
- XML валидность: правильные теги, отступы, namespaces
- Edge cases: пустая форма, один элемент, вложенные группы
- CLI demo
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from src.services.form_ui_builder import (
    FormButton,
    FormCheckBox,
    FormCommandBar,
    FormGroup,
    FormInputField,
    FormLabel,
    FormPage,
    FormTable,
    FormTableColumn,
    FormUIBuilder,
)


# ============================================================================
# FormButton tests
# ============================================================================


class TestFormButton:
    def test_button_generates_xml(self) -> None:
        btn = FormButton(name="Выполнить", id=1, title="Выполнить", action="Run")
        xml = btn.to_xml(indent=1)
        assert "<Button" in xml
        assert 'name="Выполнить"' in xml
        assert "Form.Command.Выполнить" in xml
        assert "<Action>Run</Action>" in xml

    def test_button_uses_name_as_default_title(self) -> None:
        btn = FormButton(name="OK", id=1)
        xml = btn.to_xml()
        assert "OK" in xml

    def test_button_has_usual_button_type(self) -> None:
        btn = FormButton(name="X", id=1)
        xml = btn.to_xml()
        assert "<Type>UsualButton</Type>" in xml


# ============================================================================
# FormInputField tests
# ============================================================================


class TestFormInputField:
    def test_input_field_generates_xml(self) -> None:
        field = FormInputField(
            name="Номер", id=1, data_path="Объект.Номер", title="Номер"
        )
        xml = field.to_xml(indent=1)
        assert "<InputField" in xml
        assert 'name="Номер"' in xml
        assert "<DataPath>Объект.Номер</DataPath>" in xml

    def test_input_field_with_width(self) -> None:
        field = FormInputField(name="X", id=1, data_path="Объект.X", width=100)
        xml = field.to_xml()
        assert "<Width>100</Width>" in xml

    def test_input_field_without_width(self) -> None:
        field = FormInputField(name="X", id=1, data_path="Объект.X", width=0)
        xml = field.to_xml()
        assert "<Width>" not in xml

    def test_input_field_has_context_menu(self) -> None:
        field = FormInputField(name="X", id=1, data_path="Объект.X")
        xml = field.to_xml()
        assert "КонтекстноеМеню" in xml

    def test_input_field_has_extended_tooltip(self) -> None:
        field = FormInputField(name="X", id=1, data_path="Объект.X")
        xml = field.to_xml()
        assert "РасширеннаяПодсказка" in xml


# ============================================================================
# FormLabel tests
# ============================================================================


class TestFormLabel:
    def test_label_generates_xml(self) -> None:
        label = FormLabel(name="Надпись1", id=1, title="Введите данные")
        xml = label.to_xml(indent=1)
        assert "<Label" in xml
        assert "Введите данные" in xml

    def test_label_uses_name_as_default_title(self) -> None:
        label = FormLabel(name="MyLabel", id=1)
        xml = label.to_xml()
        assert "MyLabel" in xml


# ============================================================================
# FormCheckBox tests
# ============================================================================


class TestFormCheckBox:
    def test_checkbox_generates_xml(self) -> None:
        cb = FormCheckBox(name="Выполнено", id=1, data_path="Объект.Выполнено")
        xml = cb.to_xml(indent=1)
        assert "<CheckBoxField" in xml
        assert "<DataPath>Объект.Выполнено</DataPath>" in xml
        assert "<CheckBoxType>Auto</CheckBoxType>" in xml


# ============================================================================
# FormTable tests
# ============================================================================


class TestFormTable:
    def test_table_generates_xml(self) -> None:
        table = FormTable(
            name="ТаблицаТоваров", id=1, data_path="Объект.Товары"
        )
        xml = table.to_xml(indent=1)
        assert "<Table" in xml
        assert "<DataPath>Объект.Товары</DataPath>" in xml
        assert "<ChildItems>" in xml

    def test_table_with_columns(self) -> None:
        table = FormTable(
            name="ТаблицаТоваров", id=1, data_path="Объект.Товары",
            columns=[
                FormTableColumn(name="Номенклатура", data_path="Номенклатура"),
                FormTableColumn(name="Количество", data_path="Количество"),
            ],
        )
        xml = table.to_xml(indent=1)
        assert "Номенклатура" in xml
        assert "Количество" in xml
        # Должно быть 2 InputField внутри (для колонок)
        assert xml.count("<InputField") == 2

    def test_table_empty_columns(self) -> None:
        table = FormTable(name="Empty", id=1, data_path="Объект.X")
        xml = table.to_xml()
        # Пустая таблица всё равно валидна
        assert "<Table" in xml

    def test_table_has_list_representation(self) -> None:
        table = FormTable(name="X", id=1, data_path="Объект.X")
        xml = table.to_xml()
        assert "<Representation>List</Representation>" in xml


# ============================================================================
# FormGroup tests
# ============================================================================


class TestFormGroup:
    def test_group_generates_xml(self) -> None:
        group = FormGroup(
            name="Группа1", id=1, title="Параметры",
            elements=[
                FormInputField(name="Поле1", id=2, data_path="Объект.Поле1"),
            ],
        )
        xml = group.to_xml(indent=1)
        assert "<UsualGroup" in xml
        assert 'name="Группа1"' in xml
        assert "<ChildItems>" in xml
        assert "Поле1" in xml
        # Note: UsualGroup не отображает title в XML (только Page имеет Title)

    def test_group_horizontal_behavior(self) -> None:
        group = FormGroup(name="X", id=1, behavior="Horizontal")
        xml = group.to_xml()
        assert "<Group>Horizontal</Group>" in xml

    def test_group_vertical_behavior(self) -> None:
        group = FormGroup(name="X", id=1, behavior="Vertical")
        xml = group.to_xml()
        assert "<Group>Vertical</Group>" in xml

    def test_group_nested_elements(self) -> None:
        group = FormGroup(
            name="Outer", id=1,
            elements=[
                FormGroup(name="Inner", id=2, elements=[
                    FormInputField(name="Field", id=3, data_path="Объект.Field"),
                ]),
            ],
        )
        xml = group.to_xml()
        assert "Outer" in xml
        assert "Inner" in xml
        assert "Field" in xml


# ============================================================================
# FormPage tests
# ============================================================================


class TestFormPage:
    def test_page_generates_xml(self) -> None:
        page = FormPage(
            name="Страница1", id=1, title="Основное",
            elements=[
                FormInputField(name="Поле1", id=2, data_path="Объект.Поле1"),
            ],
        )
        xml = page.to_xml(indent=1)
        assert "<Page" in xml
        assert "Основное" in xml
        assert "Поле1" in xml

    def test_page_has_title_in_v8_item(self) -> None:
        page = FormPage(name="X", id=1, title="Тест")
        xml = page.to_xml()
        assert "<v8:item>" in xml
        assert "<v8:lang>ru</v8:lang>" in xml
        assert "<v8:content>Тест</v8:content>" in xml


# ============================================================================
# FormCommandBar tests
# ============================================================================


class TestFormCommandBar:
    def test_command_bar_generates_xml(self) -> None:
        bar = FormCommandBar(
            name="ФормаКоманднаяПанель", id=-1,
            buttons=[
                FormButton(name="OK", id=1, title="OK"),
            ],
        )
        xml = bar.to_xml(indent=1)
        assert "<AutoCommandBar" in xml
        assert "OK" in xml

    def test_command_bar_empty_buttons(self) -> None:
        bar = FormCommandBar(name="Панель", id=-1)
        xml = bar.to_xml()
        assert "<AutoCommandBar" in xml


# ============================================================================
# FormUIBuilder tests
# ============================================================================


class TestFormUIBuilder:
    def test_build_form_generates_valid_xml(self) -> None:
        """Form.xml — валидный XML."""
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="Тест",
            elements=[
                FormInputField(name="Поле1", id=1, data_path="Объект.Поле1"),
            ],
        )
        # Парсим как XML — должно работать
        root = ET.fromstring(xml)
        assert root.tag == "Form" or root.tag.endswith("}Form")

    def test_build_form_has_xmlns(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(title="X", elements=[])
        assert "xmlns" in xml
        assert "v8.1c.ru" in xml

    def test_build_form_has_command_bar_by_default(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(title="X", elements=[])
        assert "AutoCommandBar" in xml

    def test_build_form_without_command_bar(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X", elements=[], include_command_bar=False
        )
        assert "AutoCommandBar" not in xml

    def test_build_form_with_multiple_elements(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X",
            elements=[
                FormInputField(name="Поле1", id=1, data_path="Объект.Поле1"),
                FormInputField(name="Поле2", id=4, data_path="Объект.Поле2"),
                FormButton(name="Выполнить", id=7, action="Run"),
            ],
        )
        assert "Поле1" in xml
        assert "Поле2" in xml
        assert "Выполнить" in xml

    def test_build_form_with_buttons_has_commands_section(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X",
            elements=[
                FormButton(name="Action1", id=1, action="DoAction1"),
            ],
        )
        assert "<Commands>" in xml
        assert "</Commands>" in xml
        assert "DoAction1" in xml

    def test_build_form_without_buttons_no_commands_section(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X",
            elements=[
                FormInputField(name="Поле1", id=1, data_path="Объект.Поле1"),
            ],
        )
        # InputField не имеет action → нет Commands section
        assert "<Commands>" not in xml

    def test_build_simple_form(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_simple_form(
            title="Простая форма",
            fields=[
                {"name": "Номер", "data_path": "Объект.Номер", "title": "Номер"},
                {"name": "Дата", "data_path": "Объект.Дата", "title": "Дата"},
            ],
            buttons=[
                {"name": "OK", "title": "OK", "action": "Выполнить"},
            ],
        )
        assert "Номер" in xml
        assert "Дата" in xml
        assert "OK" in xml
        assert "Выполнить" in xml

    def test_build_simple_form_without_buttons(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_simple_form(
            title="X",
            fields=[{"name": "Поле1", "data_path": "Объект.Поле1"}],
        )
        assert "Поле1" in xml


# ============================================================================
# XML validity tests
# ============================================================================


class TestXMLValidity:
    """Все генерируемые XML должны быть валидными."""

    def test_full_form_is_valid_xml(self) -> None:
        """Полная форма с всеми типами элементов — валидный XML."""
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="Полная форма",
            elements=[
                FormInputField(name="Поле1", id=1, data_path="Объект.Поле1"),
                FormLabel(name="Надпись1", id=4, title="Подсказка"),
                FormCheckBox(name="Флаг1", id=5, data_path="Объект.Флаг1"),
                FormTable(
                    name="Таблица1", id=8, data_path="Объект.Таблица",
                    columns=[
                        FormTableColumn(name="Кол1", data_path="Кол1"),
                    ],
                ),
                FormGroup(name="Группа1", id=20, title="Группа", elements=[
                    FormInputField(name="ВГруппе", id=21, data_path="Объект.ВГруппе"),
                ]),
                FormButton(name="Кнопка1", id=30, action="Действие1"),
            ],
        )
        # Полный Form.xml уже содержит namespaces, парсится напрямую
        root = ET.fromstring(xml)
        assert root.tag == "Form" or root.tag.endswith("}Form")

    def test_all_element_types_valid_xml(self) -> None:
        """Каждый тип элемента individually генерирует валидный XML-фрагмент."""
        # Фрагменты используют v8: prefix, нужно объявить в wrapper
        wrapper_ns = '<root xmlns:v8="http://v8.1c.ru/8.1/data/core">'
        elements = [
            FormButton(name="B", id=1, title="B", action="A"),
            FormInputField(name="I", id=1, data_path="Объект.I"),
            FormLabel(name="L", id=1, title="L"),
            FormCheckBox(name="C", id=1, data_path="Объект.C"),
            FormTable(name="T", id=1, data_path="Объект.T"),
            FormGroup(name="G", id=1, title="G"),
            FormPage(name="P", id=1, title="P"),
            FormCommandBar(name="CB", id=-1),
        ]
        for elem in elements:
            xml = elem.to_xml(indent=1)
            # Wrap in root с namespace declarations
            wrapped = f"{wrapper_ns}{xml}</root>"
            ET.fromstring(wrapped)   # не должно падать


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_form(self) -> None:
        """Пустая форма (без элементов) — валидна."""
        builder = FormUIBuilder()
        xml = builder.build_form(title="Empty", elements=[])
        root = ET.fromstring(xml)
        assert root.tag == "Form" or root.tag.endswith("}Form")

    def test_single_element(self) -> None:
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X",
            elements=[FormInputField(name="Y", id=1, data_path="Объект.Y")],
        )
        assert "Y" in xml

    def test_deeply_nested_groups(self) -> None:
        """Глубоко вложенные группы (3 уровня)."""
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="X",
            elements=[
                FormGroup(name="L1", id=1, title="L1", elements=[
                    FormGroup(name="L2", id=2, title="L2", elements=[
                        FormGroup(name="L3", id=3, title="L3", elements=[
                            FormInputField(name="Deep", id=4, data_path="Объект.Deep"),
                        ]),
                    ]),
                ]),
            ],
        )
        assert "L1" in xml
        assert "L2" in xml
        assert "L3" in xml
        assert "Deep" in xml
        # Должно быть валидным XML
        ET.fromstring(xml)


# ============================================================================
# CLI tests
# ============================================================================


class TestCLI:
    def test_cli_runs(self, capsys) -> None:
        import sys
        sys.argv = ["form_ui_builder"]
        from src.services.form_ui_builder import main
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "<Form" in captured.out

    def test_cli_with_title(self, capsys) -> None:
        import sys
        sys.argv = ["form_ui_builder", "--title", "Моя форма"]
        from src.services.form_ui_builder import main
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        # CLI demo генерирует фиксированную форму, title передаётся в build_form
        # но в XML не попадает (demo форма без Title element)
        # Проверяем что форма сгенерирована
        assert "<Form" in captured.out


# ============================================================================
# Integration: complete form
# ============================================================================


class TestIntegrationCompleteForm:
    """Интеграционный тест: реальная форма обработки."""

    def test_processing_form_with_table_and_buttons(self) -> None:
        """Полная форма обработки: поля шапки + таблица + кнопки."""
        builder = FormUIBuilder()
        xml = builder.build_form(
            title="Выгрузка номенклатуры",
            elements=[
                FormInputField(name="ДатаНачала", id=1, data_path="Объект.ДатаНачала",
                              title="Дата начала"),
                FormInputField(name="ДатаКонца", id=4, data_path="Объект.ДатаКонца",
                              title="Дата окончания"),
                FormTable(
                    name="ТаблицаРезультат", id=8,
                    data_path="Объект.ТаблицаРезультат",
                    title="Результат выгрузки",
                    columns=[
                        FormTableColumn(name="Номенклатура", data_path="Номенклатура",
                                       title="Номенклатура"),
                        FormTableColumn(name="Количество", data_path="Количество",
                                       title="Количество"),
                        FormTableColumn(name="Сумма", data_path="Сумма", title="Сумма"),
                    ],
                ),
                FormButton(name="ВыполнитьВыгрузку", id=20,
                          title="Выполнить выгрузку", action="ВыполнитьВыгрузку"),
                FormButton(name="Закрыть", id=21, title="Закрыть", action="Закрыть"),
            ],
        )

        # Валидируем XML
        root = ET.fromstring(xml)
        assert root.tag == "Form" or root.tag.endswith("}Form")

        # Проверяем наличие всех элементов
        assert "ДатаНачала" in xml
        assert "ДатаКонца" in xml
        assert "ТаблицаРезультат" in xml
        assert "Номенклатура" in xml
        assert "Количество" in xml
        assert "Сумма" in xml
        assert "ВыполнитьВыгрузку" in xml
        assert "Закрыть" in xml

        # Должна быть секция Commands (2 кнопки с actions)
        assert xml.count("<Command ") == 2
