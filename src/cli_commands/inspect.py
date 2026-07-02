"""
inspect.py — CLI команды для inspect и вспомогательные функции.

P2.1: вынесено из cli.py.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from src.project import Project


def cmd_inspect(project: Project, args: argparse.Namespace) -> None:
    """Единый inspect — анализ объектов 1С с режимами.

    Аналог /inspect из 1c-ai-development-kit — объединяет:
    - cf-info (обзор конфигурации)
    - meta-info (объект метаданных)
    - form-info (форма)
    - skd-info (СКД с режимом trace)
    - mxl-info (MXL макет)
    - role-info (роль)
    - subsystem-info (подсистема)
    - depgraph-info (граф зависимостей)
    """

    target = args.target
    mode = args.mode
    path = Path(args.path)

    if not path.exists():
        print(f"❌ Файл/каталог не найден: {path}")
        sys.exit(2)

    if target == "cf":
        # Обзор конфигурации (Configuration.xml)
        _inspect_cf(path, mode)

    elif target == "meta":
        # Объект метаданных
        _inspect_meta(path, mode, args.name)

    elif target == "form":
        # Форма
        _inspect_form(path, mode)

    elif target == "skd":
        # СКД (с trace mode)
        if mode == "trace":
            if not args.name:
                print("❌ Для trace mode укажите --name <поле>")
                sys.exit(2)
            import sys as sys_mod

            sys_mod.path.insert(0, str(project.paths.scripts_dir))
            from skd_parser import trace_field

            result = trace_field(path, args.name)
            if "error" in result:
                print(f"❌ {result['error']}")
                if "available_fields" in result:
                    print(f"\nДоступные поля ({len(result['available_fields'])}):")
                    for p in result["available_fields"][:20]:
                        print(f"  • {p}")
            else:
                print(result["trace_text"])
        else:
            _inspect_skd(path, mode)

    elif target == "mxl":
        _inspect_mxl(path, mode)

    elif target == "role":
        _inspect_role(path, mode)

    elif target == "subsystem":
        _inspect_subsystem(path, mode)

    elif target == "depgraph":
        # Граф зависимостей
        from src.services.dependency_graph import DependencyGraph

        config_name = args.name
        if not config_name:
            print("❌ Для depgraph укажите --name <config_name>")
            sys.exit(2)
        dg = DependencyGraph()
        result = dg.build_from_metadata_index(config_name, project.paths)
        print(f"=== Граф зависимостей: {result.config_name} ===")
        print(f"Узлов: {len(result.nodes)}")
        print(f"Рёбер: {len(result.edges)}")
        stats = dg.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

    else:
        print(f"❌ Неизвестный target: {target}")
        print("Доступные: cf, meta, form, skd, mxl, role, subsystem, depgraph")
        sys.exit(2)


def _inspect_cf(config_path: Path, mode: str) -> None:
    """Обзор конфигурации."""

    if config_path.is_dir():
        config_path = config_path / "Configuration.xml"
    if not config_path.exists():
        print(f"❌ Configuration.xml не найден: {config_path}")
        return

    tree = ET.parse(config_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Configuration.xml имеет root <MetaDataObject> или <Configuration>
    # Ищем Properties внутри
    config = root
    config_type = _strip_ns(root.tag)

    if config_type == "MetaDataObject":
        # Ищем Configuration внутри MetaDataObject
        for child in root:
            if _strip_ns(child.tag) == "Configuration":
                config = child
                break

    props = None
    for elem in config:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    print("=== Configuration ===")
    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects — счётчики по типам
    child_objects = None
    for elem in config:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        print("\n=== Объекты по типам ===")
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")


def _inspect_meta(meta_path: Path, mode: str, name: str | None = None) -> None:
    """Обзор объекта метаданных."""

    if meta_path.is_dir():
        # В 1С выгрузке структура: Catalogs/<Name>/<Name>.xml ИЛИ Catalogs/<Name>.xml
        # Если передали директорию — ищем .xml рядом (на уровень выше)
        obj_name = meta_path.name  # например "Контрагенты"
        candidate = meta_path.parent / f"{obj_name}.xml"
        if candidate.exists():
            meta_path = candidate
        else:
            # Ищем внутри директории
            if name:
                candidate = meta_path / f"{name}.xml"
                if candidate.exists():
                    meta_path = candidate
            if meta_path.is_dir():
                # Берём первый .xml внутри
                xmls = list(meta_path.glob("*.xml"))
                if xmls:
                    meta_path = xmls[0]

    if not meta_path.exists():
        print(f"❌ Файл не найден: {meta_path}")
        return

    tree = ET.parse(meta_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Реальные файлы 1С имеют обёртку <MetaDataObject><Catalog>...</Catalog></MetaDataObject>
    obj_elem = root
    obj_type = _strip_ns(root.tag)

    if obj_type == "MetaDataObject":
        # Ищем первый дочерний элемент (Catalog, Document, и т.д.)
        for child in root:
            child_tag = _strip_ns(child.tag)
            if child_tag not in ("ConfigDumpInfo",):
                obj_elem = child
                obj_type = child_tag
                break

    print(f"=== {obj_type} ===")

    # Properties — внутри объекта
    props = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects
    child_objects = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        print("\n=== Дочерние объекты ===")
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")


def _inspect_form(form_path: Path, mode: str) -> None:
    """Обзор формы."""

    tree = ET.parse(form_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print("=== Form ===")

    # Считаем элементы
    item_counts: dict[str, int] = {}
    for elem in root.iter():
        tag = _strip_ns(elem.tag)
        if tag in (
            "InputField",
            "Button",
            "Group",
            "Label",
            "Table",
            "Pages",
            "Page",
            "CheckBox",
            "RadioButton",
            "Hyperlink",
            "ProgressBar",
            "TextDocField",
            "SpreadSheetDocField",
            "Picture",
            "CalendarField",
            "TrackBar",
            "CommandBar",
            "UsualGroup",
        ):
            item_counts[tag] = item_counts.get(tag, 0) + 1

    print("Элементы:")
    for t, count in sorted(item_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")


def _inspect_skd(skd_path: Path, mode: str) -> None:
    """Обзор СКД."""

    if skd_path.is_dir():
        candidate = skd_path / "Ext" / "Template.xml"
        if candidate.exists():
            skd_path = candidate

    tree = ET.parse(skd_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print("=== СКД ===")

    # DataSets
    data_sets = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "dataSet":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "name":
                    name_elem = child
                    break
            data_sets.append(name_elem.text if name_elem is not None else "?")

    print(f"Наборов данных: {len(data_sets)}")
    for ds in data_sets:
        print(f"  • {ds}")

    # Parameters — ищем в dataParameters (реальные параметры СКД)
    # Формат: dataParameters → item → parameter (с именем параметра)
    params = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "dataParameters":
            for item in elem:
                if _strip_ns(item.tag) == "item":
                    for child in item:
                        if _strip_ns(child.tag) == "parameter" and child.text:
                            params.append(child.text)
            break

    # Fallback: если dataParameters пустой, ищем parameter с name
    if not params:
        for elem in root.iter():
            if _strip_ns(elem.tag) == "parameter":
                name_elem = None
                for child in elem:
                    if _strip_ns(child.tag) == "name":
                        name_elem = child
                        break
                if name_elem is not None and name_elem.text:
                    params.append(name_elem.text)

    print(f"\nПараметров: {len(params)}")
    for p in params[:20]:
        print(f"  • {p}")
    if len(params) > 20:
        print(f"  ... и ещё {len(params) - 20}")

    # Calculated fields
    calc_fields = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "calculatedField":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "dataPath":
                    name_elem = child
                    break
            calc_fields.append(name_elem.text if name_elem is not None else "?")

    if calc_fields:
        print(f"\nВычисляемых полей: {len(calc_fields)}")
        for cf in calc_fields:
            print(f"  • {cf}")

    # Total fields (resources)
    totals = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "totalField":
            name_elem = None
            for child in elem:
                if _strip_ns(child.tag) == "dataPath":
                    name_elem = child
                    break
            totals.append(name_elem.text if name_elem is not None else "?")

    if totals:
        print(f"\nИтоговых полей (ресурсов): {len(totals)}")
        for t in totals:
            print(f"  • {t}")


def _inspect_mxl(mxl_path: Path, mode: str) -> None:
    """Обзор MXL макета."""

    if mxl_path.is_dir():
        candidate = mxl_path / "Ext" / "Template.xml"
        if candidate.exists():
            mxl_path = candidate

    tree = ET.parse(mxl_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print("=== MXL Макет ===")

    # Areas
    areas = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "area":
            name = elem.get("name", "?")
            areas.append(name)

    print(f"Областей: {len(areas)}")
    for a in areas:
        print(f"  • {a}")

    # Columns
    cols = 0
    for elem in root.iter():
        if _strip_ns(elem.tag) == "column":
            cols += 1
    print(f"\nКолонок: {cols}")

    # Parameters
    params = []
    for elem in root.iter():
        if _strip_ns(elem.tag) == "parameter":
            name = elem.get("name", "?")
            params.append(name)
    if params:
        print(f"Параметров: {len(params)}")
        for p in params[:20]:
            print(f"  • {p}")


def _inspect_role(role_path: Path, mode: str) -> None:
    """Обзор роли."""

    if role_path.is_dir():
        candidate = role_path / "Ext" / "Rights.xml"
        if candidate.exists():
            role_path = candidate
        else:
            obj_name = role_path.name
            candidate = role_path.parent / f"{obj_name}.xml"
            if candidate.exists():
                role_path = candidate
            else:
                xmls = list(role_path.glob("*.xml"))
                if xmls:
                    role_path = xmls[0]

    if not role_path.exists():
        print(f"❌ Файл не найден: {role_path}")
        return

    tree = ET.parse(role_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    print("=== Role ===")

    # Реальный формат Rights.xml: <object><name>...</name><right><name>View</name><value>true</value></right></object>
    # Ищем все <object> (с маленькой буквы) или <Object>
    objects = []
    for elem in root.iter():
        tag = _strip_ns(elem.tag).lower()
        if tag == "object":
            obj_name = ""
            rights = []
            for child in elem:
                ctag = _strip_ns(child.tag).lower()
                if ctag == "name" and child.text:
                    obj_name = child.text.strip()
                elif ctag == "right":
                    right_name = ""
                    right_value = ""
                    for sub in child:
                        st = _strip_ns(sub.tag).lower()
                        if st == "name" and sub.text:
                            right_name = sub.text.strip()
                        elif st == "value" and sub.text:
                            right_value = sub.text.strip()
                    if right_value == "true":
                        rights.append(right_name)
            if obj_name:
                objects.append((obj_name, rights))

    if objects:
        print(f"Объектов с правами: {len(objects)}")
        for name, rights in objects[:20]:
            print(f"  • {name}: {', '.join(rights) if rights else '(нет прав)'}")
        if len(objects) > 20:
            print(f"  ... и ещё {len(objects) - 20}")
    else:
        # Возможно это файл метаданных роли (Role.xml), не Rights.xml
        print("(Rights.xml не найден — это файл метаданных роли)")
        props = None
        for elem in root.iter():
            if _strip_ns(elem.tag) == "Properties":
                props = elem
                break
        if props is not None:
            for prop in props:
                tag = _strip_ns(prop.tag)
                text = (prop.text or "").strip()
                if text and len(text) < 100:
                    print(f"  {tag}: {text}")


def _inspect_subsystem(subsystem_path: Path, mode: str) -> None:
    """Обзор подсистемы."""

    if subsystem_path.is_dir():
        obj_name = subsystem_path.name
        candidate = subsystem_path.parent / f"{obj_name}.xml"
        if candidate.exists():
            subsystem_path = candidate
        else:
            xmls = list(subsystem_path.glob("*.xml"))
            if xmls:
                subsystem_path = xmls[0]

    if not subsystem_path.exists():
        print(f"❌ Файл не найден: {subsystem_path}")
        return

    tree = ET.parse(subsystem_path)
    root = tree.getroot()

    def _strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # Поддержка обёртки MetaDataObject
    obj_elem = root
    if _strip_ns(root.tag) == "MetaDataObject":
        for child in root:
            if _strip_ns(child.tag) not in ("ConfigDumpInfo",):
                obj_elem = child
                break

    print("=== Subsystem ===")

    # Properties
    props = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "Properties":
            props = elem
            break

    if props is not None:
        for prop in props:
            tag = _strip_ns(prop.tag)
            text = (prop.text or "").strip()
            if text and len(text) < 100:
                print(f"  {tag}: {text}")

    # ChildObjects (content)
    child_objects = None
    for elem in obj_elem:
        if _strip_ns(elem.tag) == "ChildObjects":
            child_objects = elem
            break

    if child_objects is not None and len(child_objects) > 0:
        print("\n=== Содержимое ===")
        type_counts: dict[str, int] = {}
        for child in child_objects:
            tag = _strip_ns(child.tag)
            type_counts[tag] = type_counts.get(tag, 0) + 1
        for t, count in sorted(type_counts.items()):
            print(f"  {t}: {count}")
