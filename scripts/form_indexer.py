#!/usr/bin/env python3
"""
Индексатор модулей конфигурации 1С — формы, модули объектов, модули менеджеров.

Добавляет обработку:
1. CommonForms/<Имя>/Ext/Form/Module.bsl — общие формы
2. <ТипОбъекта>/<Имя>/Forms/<ИмяФормы>/Ext/Form/Module.bsl — формы объектов
3. <ТипОбъекта>/<Имя>/Ext/ObjectModule.bsl — модули объектов
4. <ТипОбъекта>/<Имя>/Ext/ManagerModule.bsl — модули менеджеров
5. Ext/ManagedApplicationModule.bsl — модуль приложения

Модули добавляются в api-reference.json с соответствующим type.
"""

import os
from pathlib import Path

# Папки типов объектов, где могут быть модули
OBJECT_TYPES_WITH_MODULES = [
    "Documents",
    "Catalogs",
    "DataProcessors",
    "Reports",
    "InformationRegisters",
    "AccumulationRegisters",
    "ChartsOfAccounts",
    "ChartsOfCharacteristicTypes",
    "BusinessProcesses",
    "Tasks",
    "ExchangePlans",
    "FilterCriteria",
    "Enums",
    "Constants",
    "CalculationRegisters",
    "AccountingRegisters",
    "ChartsOfCalculationTypes",
]


def find_all_modules(config_dir):
    """Находит ВСЕ модули в конфигурации.

    Возвращает список: [{name, bsl_path, xml_path, module_type, parent_type, parent_name, form_name, form_elements}]
    """
    modules = []
    config_dir = Path(config_dir)

    # 1. CommonModules — уже обрабатываются build_api_reference, пропускаем

    # 2. CommonForms/<Имя>/Ext/Form/Module.bsl — общие формы
    common_forms_dir = config_dir / "CommonForms"
    if common_forms_dir.exists():
        for item in sorted(common_forms_dir.iterdir()):
            if not item.is_dir():
                continue
            bsl_path = item / "Ext" / "Form" / "Module.bsl"
            xml_path = item / "Ext" / "Form.xml"
            meta_xml = common_forms_dir / f"{item.name}.xml"
            if bsl_path.exists():
                elements = parse_form_xml(str(xml_path if xml_path.exists() else meta_xml if meta_xml.exists() else ""))
                modules.append(
                    {
                        "name": f"Форма.{item.name}",
                        "bsl_path": str(bsl_path),
                        "xml_path": str(xml_path if xml_path.exists() else ""),
                        "module_type": "Форма",
                        "parent_type": "CommonForm",
                        "parent_name": item.name,
                        "form_name": item.name,
                        "form_elements": elements,
                    }
                )

    # 3. Forms внутри объектов + ObjectModule + ManagerModule
    for obj_type in OBJECT_TYPES_WITH_MODULES:
        obj_dir = config_dir / obj_type
        if not obj_dir.exists():
            continue
        for obj_item in sorted(obj_dir.iterdir()):
            if not obj_item.is_dir():
                continue
            safe_name = obj_item.name

            # 3a. ObjectModule.bsl
            obj_module = obj_item / "Ext" / "ObjectModule.bsl"
            if obj_module.exists():
                modules.append(
                    {
                        "name": f"{safe_name}.МодульОбъекта",
                        "bsl_path": str(obj_module),
                        "xml_path": str(obj_item / f"{safe_name}.xml"),
                        "module_type": "МодульОбъекта",
                        "parent_type": obj_type,
                        "parent_name": safe_name,
                        "form_name": "",
                        "form_elements": [],
                    }
                )

            # 3b. ManagerModule.bsl
            mgr_module = obj_item / "Ext" / "ManagerModule.bsl"
            if mgr_module.exists():
                modules.append(
                    {
                        "name": f"{safe_name}.МодульМенеджера",
                        "bsl_path": str(mgr_module),
                        "xml_path": str(obj_item / f"{safe_name}.xml"),
                        "module_type": "МодульМенеджера",
                        "parent_type": obj_type,
                        "parent_name": safe_name,
                        "form_name": "",
                        "form_elements": [],
                    }
                )

            # 3c. Forms/<ИмяФормы>/Ext/Form/Module.bsl
            forms_dir = obj_item / "Forms"
            if forms_dir.exists():
                for form_item in sorted(forms_dir.iterdir()):
                    if not form_item.is_dir():
                        continue
                    bsl_path = form_item / "Ext" / "Form" / "Module.bsl"
                    xml_path = form_item / "Ext" / "Form.xml"
                    if bsl_path.exists():
                        elements = parse_form_xml(str(xml_path if xml_path.exists() else ""))
                        modules.append(
                            {
                                "name": f"{safe_name}.{form_item.name}",
                                "bsl_path": str(bsl_path),
                                "xml_path": str(xml_path if xml_path.exists() else ""),
                                "module_type": "Форма",
                                "parent_type": obj_type,
                                "parent_name": safe_name,
                                "form_name": form_item.name,
                                "form_elements": elements,
                            }
                        )

            # 3d. Ext/Form/Module.bsl (форма обработки, без папки Forms/)
            direct_form_bsl = obj_item / "Ext" / "Form" / "Module.bsl"
            if direct_form_bsl.exists():
                already = any(m["parent_name"] == safe_name and m["module_type"] == "Форма" for m in modules)
                if not already:
                    xml_path = obj_item / "Ext" / "Form.xml"
                    elements = parse_form_xml(str(xml_path if xml_path.exists() else ""))
                    modules.append(
                        {
                            "name": f"{safe_name}.Форма",
                            "bsl_path": str(direct_form_bsl),
                            "xml_path": str(xml_path if xml_path.exists() else ""),
                            "module_type": "Форма",
                            "parent_type": obj_type,
                            "parent_name": safe_name,
                            "form_name": "Форма",
                            "form_elements": elements,
                        }
                    )

            # 3e. Commands/<ИмяКоманды>/Ext/CommandModule.bsl — модули команд объекта
            commands_dir = obj_item / "Commands"
            if commands_dir.exists():
                for cmd_item in sorted(commands_dir.iterdir()):
                    if not cmd_item.is_dir():
                        continue
                    cmd_bsl = cmd_item / "Ext" / "CommandModule.bsl"
                    if cmd_bsl.exists():
                        modules.append(
                            {
                                "name": f"{safe_name}.Команда.{cmd_item.name}",
                                "bsl_path": str(cmd_bsl),
                                "xml_path": str(cmd_item / f"{cmd_item.name}.xml"),
                                "module_type": "МодульКоманды",
                                "parent_type": obj_type,
                                "parent_name": safe_name,
                                "form_name": cmd_item.name,
                                "form_elements": [],
                            }
                        )

    # 4. CommonCommands/<Имя>/Ext/CommandModule.bsl — общие команды
    common_commands_dir = config_dir / "CommonCommands"
    if common_commands_dir.exists():
        for item in sorted(common_commands_dir.iterdir()):
            if not item.is_dir():
                continue
            cmd_bsl = item / "Ext" / "CommandModule.bsl"
            if cmd_bsl.exists():
                modules.append(
                    {
                        "name": f"Команда.{item.name}",
                        "bsl_path": str(cmd_bsl),
                        "xml_path": str(common_commands_dir / f"{item.name}.xml"),
                        "module_type": "МодульКоманды",
                        "parent_type": "CommonCommand",
                        "parent_name": item.name,
                        "form_name": "",
                        "form_elements": [],
                    }
                )

    # 5. ManagedApplicationModule.bsl — модуль приложения
    app_module = config_dir / "Ext" / "ManagedApplicationModule.bsl"
    if app_module.exists():
        modules.append(
            {
                "name": "МодульПриложения",
                "bsl_path": str(app_module),
                "xml_path": "",
                "module_type": "МодульПриложения",
                "parent_type": "Configuration",
                "parent_name": "",
                "form_name": "",
                "form_elements": [],
            }
        )

    # 6. SessionModule.bsl — модуль сеанса (если есть)
    session_module = config_dir / "Ext" / "SessionModule.bsl"
    if session_module.exists():
        modules.append(
            {
                "name": "МодульСеанса",
                "bsl_path": str(session_module),
                "xml_path": "",
                "module_type": "МодульСеанса",
                "parent_type": "Configuration",
                "parent_name": "",
                "form_name": "",
                "form_elements": [],
            }
        )

    # 7. ExternalConnectionModule.bsl — модуль внешнего соединения
    ext_conn_module = config_dir / "Ext" / "ExternalConnectionModule.bsl"
    if ext_conn_module.exists():
        modules.append(
            {
                "name": "МодульВнешнегоСоединения",
                "bsl_path": str(ext_conn_module),
                "xml_path": "",
                "module_type": "МодульВнешнегоСоединения",
                "parent_type": "Configuration",
                "parent_name": "",
                "form_name": "",
                "form_elements": [],
            }
        )

    # 8. OrdinaryApplicationModule.bsl — модуль обычного приложения (legacy)
    ord_app_module = config_dir / "Ext" / "OrdinaryApplicationModule.bsl"
    if ord_app_module.exists():
        modules.append(
            {
                "name": "МодульОбычногоПриложения",
                "bsl_path": str(ord_app_module),
                "xml_path": "",
                "module_type": "МодульОбычногоПриложения",
                "parent_type": "Configuration",
                "parent_name": "",
                "form_name": "",
                "form_elements": [],
            }
        )

    # 9. SubsystemModule.bsl — модули подсистем
    subsystems_dir = config_dir / "Subsystems"
    if subsystems_dir.exists():
        for item in sorted(subsystems_dir.iterdir()):
            if not item.is_dir():
                continue
            sub_bsl = item / "Ext" / "SubsystemModule.bsl"
            if sub_bsl.exists():
                modules.append(
                    {
                        "name": f"Подсистема.{item.name}",
                        "bsl_path": str(sub_bsl),
                        "xml_path": str(subsystems_dir / f"{item.name}.xml"),
                        "module_type": "МодульПодсистемы",
                        "parent_type": "Subsystem",
                        "parent_name": item.name,
                        "form_name": "",
                        "form_elements": [],
                    }
                )

    return modules


def parse_form_xml(xml_path):
    """Парсит XML формы — извлекает элементы формы (кнопки, поля, группы).

    Возвращает: [{name, type, title, data_path, command}]
    """
    if not xml_path or not os.path.exists(xml_path):
        return []

    import xml.etree.ElementTree as ET

    def strip_ns(tag):
        return tag.split("}")[1] if "}" in tag else tag

    elements = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        FORM_TAGS = (
            "InputField",
            "LabelField",
            "Button",
            "UsualGroup",
            "Pages",
            "Page",
            "Table",
            "CheckBox",
            "RadioButton",
            "ProgressBar",
            "Picture",
            "Calendar",
            "Chart",
            "SpreadSheetDocument",
            "TextDocument",
            "HTMLDocument",
            "CommandBar",
            "ContextMenu",
            "AutoCommandBar",
            "ExtendedTooltip",
            "SearchStringAddition",
            "ViewStatusAddition",
            "SearchControlAddition",
        )

        for elem in root.iter():
            tag = strip_ns(elem.tag)
            name = elem.get("name", "")
            if not name:
                continue

            if tag in FORM_TAGS:
                title = ""
                data_path = ""
                command_name = ""

                for child in elem:
                    child_tag = strip_ns(child.tag)
                    if child_tag == "Title" and child.text:
                        title = child.text
                    elif child_tag == "DataPath" and child.text:
                        data_path = child.text
                    elif child_tag == "CommandName" and child.text:
                        command_name = child.text

                elements.append(
                    {
                        "name": name,
                        "type": tag,
                        "title": title,
                        "data_path": data_path,
                        "command": command_name,
                    }
                )
    except Exception:
        pass

    return elements


def add_modules_to_api_reference(config_dir, modules_list, parse_bsl_func):
    """Добавляет все модули (формы, объектов, менеджеров) в список modules_list.

    Args:
        config_dir: Путь к директории конфигурации
        modules_list: Существующий список модулей (изменяется in-place)
        parse_bsl_func: Функция парсинга BSL (parse_module_bsl из build_api_reference)

    Returns:
        Кол-во добавленных модулей
    """
    extra_modules = find_all_modules(config_dir)
    added = 0

    for mod in extra_modules:
        bsl_path = mod["bsl_path"]
        if not os.path.exists(bsl_path):
            continue

        # Парсим BSL модуль
        methods = parse_bsl_func(bsl_path)

        # Определяем категорию
        if mod["module_type"] == "Форма":
            category = "Формы"
        elif mod["module_type"] == "МодульКоманды":
            category = "Команды"
        elif mod["module_type"] == "МодульПодсистемы":
            category = "Подсистемы"
        elif mod["module_type"] in (
            "МодульПриложения",
            "МодульСеанса",
            "МодульВнешнегоСоединения",
            "МодульОбычногоПриложения",
        ):
            category = "Модули конфигурации"
        else:
            category = "Модули объектов"

        modules_list.append(
            {
                "name": mod["name"],
                "synonym": mod.get("form_name", "") or mod["parent_name"],
                "comment": f"{mod['module_type']}: {mod['parent_type']}.{mod['parent_name']}"
                if mod["parent_name"]
                else mod["module_type"],
                "type": mod["module_type"],
                "category": category,
                "properties": {
                    "global": False,
                    "server": mod["module_type"]
                    in ("МодульОбъекта", "МодульМенеджера", "МодульВнешнегоСоединения", "МодульСеанса"),
                    "client_managed": mod["module_type"] in ("Форма", "МодульПриложения", "МодульОбычногоПриложения"),
                    "server_call": False,
                    "privileged": False,
                    "external_connection": mod["module_type"] == "МодульВнешнегоСоединения",
                },
                "methods": methods,
                "methods_count": len(methods),
                "form_elements": mod.get("form_elements", []),
                "form_elements_count": len(mod.get("form_elements", [])),
                "parent_type": mod["parent_type"],
                "parent_name": mod["parent_name"],
                "module_type": mod["module_type"],
            }
        )
        added += 1

    return added


# Backward compat
find_form_modules = find_all_modules
add_forms_to_api_reference = add_modules_to_api_reference


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python3 form_indexer.py <config_dir>")
        sys.exit(1)

    config_dir = sys.argv[1]
    modules = find_all_modules(config_dir)
    print(f"Найдено модулей: {len(modules)}")
    for m in modules:
        print(f"  [{m['module_type']}] {m['name']} ({m['parent_type']}.{m['parent_name']})")
        print(f"    BSL: {m['bsl_path']}")
        if m.get("form_elements"):
            print(f"    Элементов формы: {len(m['form_elements'])}")
            for elem in m["form_elements"][:5]:
                print(f"      {elem['type']}: {elem['name']} — {elem.get('title', '')[:40]}")
        print()
