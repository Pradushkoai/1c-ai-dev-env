#!/usr/bin/env python3
"""
improved_cf_adapter.py — Улучшенный конвертер распакованного .cf в формат XML выгрузки.

Извлекает ВСЕ типы модулей:
1. CommonModules (Module.bsl) — из UUID.0/text (контейнер)
2. ObjectModule (ObjectModule.bsl) — из UUID.0/text (контейнер) для объектов
3. ManagerModule (ManagerModule.bsl) — из UUID.2 (прямой текст) для объектов
4. Form modules — BSL встроен ВНУТРЬ данных формы (UUID.0 как текст)
5. CommonCommands (CommandModule.bsl) — из UUID.2 (прямой текст)
6. Subsystem CommandInterface — из UUID.1/text (контейнер)
7. Form XML metadata — извлекается из данных формы (формат {3,...})

Использование:
    python3 improved_cf_adapter.py <extracted_cf_dir> <output_dir>
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

# Добавляем scripts/ в path (из репо и из текущей папки)
sys.path.insert(0, "/home/z/my-project/repo_work/scripts")
sys.path.insert(0, str(Path(__file__).parent))
from cf_extractor import V8_SIGNATURE, V8_SIGNATURE_64, V8Container
from v8_metadata_parser import TYPE_MAP_V1, TYPE_MAP_V2

# Маппинг: тип_объекта → имя_папки_в_XML_выгрузке
TYPE_TO_DIR = {
    "CommonModule": "CommonModules",
    "Catalog": "Catalogs",
    "Document": "Documents",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "Enum": "Enums",
    "Report": "Reports",
    "DataProcessor": "DataProcessors",
    "Constant": "Constants",
    "CommonForm": "CommonForms",
    "CommonCommand": "CommonCommands",
    "CommonPicture": "CommonPictures",
    "CommonTemplate": "CommonTemplates",
    "CommonAttribute": "CommonAttributes",
    "Subsystem": "Subsystems",
    "ExchangePlan": "ExchangePlans",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfAccounts": "ChartsOfAccounts",
    "AccountingRegister": "AccountingRegisters",
    "CalculationRegister": "CalculationRegisters",
    "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks",
    "DefinedType": "DefinedTypes",
    "EventSubscription": "EventSubscriptions",
    "ScheduledJob": "ScheduledJobs",
    "FunctionalOption": "FunctionalOptions",
    "FunctionalOptionParameter": "FunctionalOptionsParameters",
    "HTTPService": "HTTPServices",
    "WebService": "WebServices",
    "XDTOPackage": "XDTOPackages",
    "FilterCriterion": "FilterCriteria",
    "SessionParameter": "SessionParameters",
    "Role": "Roles",
    "CommandGroup": "CommandGroups",
    "Style": "Styles",
    "StyleItem": "StyleItems",
    "WSReference": "WSReferences",
    "Form": "Forms",  # для вложенных форм
}


def safe_name(name: str) -> str:
    """Безопасное имя для файловой системы."""
    return name.replace("/", "_").replace("\\", "_").replace(":", "_").replace('"', "")


def detect_type_by_content(content: str, type_code: int) -> str:
    """Определяет тип объекта по коду и содержимому.

    В современной кодировке .cf (8.3.24+) коды типов могут быть сдвинуты.
    Дополнительная эвристика по содержимому.
    """
    # Type 1 — может быть CommonForm или Constant
    # CommonForm: {1,{1,{0,{12,{1,{0,0,UUID},"Name",...
    # Constant: {1,{1,{2,{1,{0,0,UUID},"Name",...
    # Subsystem: {1,{1,{3,... (другой формат)
    if type_code == 1:
        if re.search(r"\{1,\s*\{1,\s*\{0,\s*\{12,", content):
            return "CommonForm"
        if re.search(r"\{1,\s*\{1,\s*\{2,", content):
            return "Constant"
        return "CommonForm"  # default for type 1

    # Type 2 — CommonTemplate (с подтипами 0-7)
    if type_code == 2:
        return "CommonTemplate"

    # Type 3 — CommonPicture (StyleItem в V2 — неверно)
    if type_code == 3:
        return "CommonPicture"

    # Type 29 — Subsystem (не BusinessProcess!)
    if type_code == 29:
        return "Subsystem"

    # Type 6 — CommonPicture
    if type_code == 6:
        return "CommonPicture"

    # Type 14 — FunctionalOption
    if type_code == 14:
        return "FunctionalOption"

    # Современный формат
    if type_code in TYPE_MAP_V2:
        return TYPE_MAP_V2[type_code]
    # Классический формат
    if type_code in TYPE_MAP_V1:
        return TYPE_MAP_V1[type_code]
    return f"Unknown_{type_code}"


def detect_inner_type(content: str) -> str | None:
    """Для объектов с вложенной структурой (CommonCommand, Form и т.д.)
    определяет внутренний тип по содержимому.

    CommonCommand имеет формат: {1,{2,{1,{2,UUID,UUID},{7,...}}}}
    Form имеет формат: {1,{0,{12,{1,{0,0,UUID},"Name",...}}}}
    """
    # Ищем CommonCommand: паттерн {7, прямо внутри
    if re.search(r"\{1,\s*\{2,\s*\{1,\s*\{2,[0-9a-f-]+,[0-9a-f-]+\}\s*,\s*\{7,", content):
        return "CommonCommand"
    return None


def extract_name_and_uuid(content: str) -> tuple[str, str]:
    """Извлекает имя и UUID из метаданных объекта.

    Поддерживает два паттерна:
    - {1,0,UUID},"Name" — стандартный
    - {0,0,UUID},"Name" — альтернативный (для форм и CommonCommand)
    """
    # Сначала пробуем {1,0,UUID},"Name"
    m = re.search(r'\{1,0,([0-9a-f-]{36})\},"([^"]+)"', content, re.IGNORECASE)
    if m:
        return m.group(2), m.group(1)
    # Альтернативный паттерн {0,0,UUID},"Name"
    m = re.search(r'\{0,0,([0-9a-f-]{36})\},"([^"]+)"', content, re.IGNORECASE)
    if m:
        return m.group(2), m.group(1)
    return "", ""


def extract_synonym(content: str) -> str:
    """Извлекает синоним {1,"ru","Синоним"}."""
    m = re.search(r'\{1,"ru","([^"]*)"\}', content)
    return m.group(1) if m else ""


def read_decompressed(file_data: bytes) -> bytes:
    """Распаковывает данные, если они сжаты."""
    try:
        return zlib.decompress(file_data, -15)
    except zlib.error:
        return file_data


def is_v8_container(data: bytes) -> bool:
    """Проверяет, является ли data контейнером 1С."""
    return data[:4] == V8_SIGNATURE or data[:8] == V8_SIGNATURE_64


def read_text_from_container(container_data: bytes) -> str:
    """Читает текст из контейнера с info+text структурой.

    Возвращает содержимое файла 'text' (распакованное).
    """
    if not is_v8_container(container_data):
        return ""
    try:
        nested = V8Container(container_data, 0)
        nested.read()
        if "text" in nested.files:
            text_data = nested.files["text"]
            return read_decompressed(text_data).decode("utf-8-sig", errors="replace")
    except Exception:
        pass
    return ""


def extract_bsl_from_form_data(form_data_text: str) -> str:
    """
    Извлекает BSL модуль из данных формы (формат {3,{42,...},...,"<BSL>"}).

    BSL код встроен как строковое значение в формате 1C:
    "код" где "" = escape для "
    """
    # Ищем BSL код по ключевым словам
    bsl_keywords = ["#Область", "Процедура", "Функция", "&НаСервере", "&НаКлиенте", "#Если"]

    for pattern in bsl_keywords:
        pos = form_data_text.find(pattern)
        if pos < 0:
            continue

        # Идём назад — ищем открывающую кавычку
        quote_start = form_data_text.rfind('"', 0, pos)
        if quote_start < 0:
            continue

        # Проверяем что перед " есть , или } (значение в структуре)
        if quote_start == 0:
            continue
        before_quote = form_data_text[quote_start - 1]
        if before_quote not in (",", "}", "{"):
            continue

        # Идём вперёд — ищем закрывающую кавычку (с учётом escape "")
        i = pos
        while i < len(form_data_text):
            next_quote = form_data_text.find('"', i)
            if next_quote < 0:
                break

            # Проверяем escape ""
            if next_quote + 1 < len(form_data_text) and form_data_text[next_quote + 1] == '"':
                i = next_quote + 2
                continue

            # Проверяем что после " идёт , или } или \n
            after = form_data_text[next_quote + 1] if next_quote + 1 < len(form_data_text) else ""
            if after in (",", "}", "\n", "\r"):
                bsl_code = form_data_text[quote_start + 1 : next_quote]
                # Unescape: "" → "
                bsl_code = bsl_code.replace('""', '"')
                return bsl_code

            i = next_quote + 1

    return ""


def extract_form_xml_metadata(form_data_text: str, form_name: str) -> str:
    """
    Генерирует упрощённый XML метаданных формы из данных формы {3,...}.
    """
    # Извлекаем элементы формы (кнопки, поля и т.д.)
    elements = []

    # Ищем элементы по паттернам
    form_tags = [
        ("InputField", "InputField"),
        ("LabelField", "LabelField"),
        ("Button", "Button"),
        ("UsualGroup", "UsualGroup"),
        ("Pages", "Pages"),
        ("Page", "Page"),
        ("Table", "Table"),
        ("CheckBox", "CheckBox"),
        ("RadioButton", "RadioButton"),
        ("ProgressBar", "ProgressBar"),
        ("Picture", "Picture"),
        ("Calendar", "Calendar"),
        ("Chart", "Chart"),
        ("SpreadSheetDocument", "SpreadSheetDocument"),
        ("TextDocument", "TextDocument"),
        ("HTMLDocument", "HTMLDocument"),
        ("CommandBar", "CommandBar"),
        ("ContextMenu", "ContextMenu"),
        ("AutoCommandBar", "AutoCommandBar"),
        ("ExtendedTooltip", "ExtendedTooltip"),
    ]

    # Ищем имена элементов — паттерн ,"ИмяЭлемента",
    # (упрощённая экстракция)
    name_pattern = re.compile(r',\s*"([A-Za-zА-Яа-я0-9_]+)"\s*,\s*\{1\s*,', re.UNICODE)
    for m in name_pattern.finditer(form_data_text):
        name = m.group(1)
        if name and len(name) < 100:  # фильтруем мусор
            elements.append({"name": name, "type": "Element"})

    # Генерируем XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">',
        "\t<Items>",
    ]
    for elem in elements[:200]:  # ограничиваем количество
        xml_lines.append(f'\t\t<Item name="{elem["name"]}"/>')
    xml_lines.append("\t</Items>")
    xml_lines.append("</Form>")
    return "\n".join(xml_lines)


def generate_object_xml(
    obj_type: str, uuid: str, name: str, synonym: str, comment: str = "", extra_props: str = ""
) -> str:
    """Генерирует XML для объекта метаданных."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<{obj_type} uuid="{uuid}">
\t\t<Properties>
\t\t\t<Name>{name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{synonym or name}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment>{comment}</Comment>
{extra_props}
\t\t</Properties>
\t</{obj_type}>
</MetaDataObject>"""


def generate_configuration_xml(title: str, child_objects: list) -> str:
    """Генерирует Configuration.xml."""
    child_lines = []
    for obj_type, obj_name in child_objects:
        if obj_name:
            child_lines.append(f"\t\t\t<{obj_type}>{obj_name}</{obj_type}>")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<Configuration uuid="00000000-0000-0000-0000-000000000000">
\t\t<Properties>
\t\t\t<Name>{title}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{title}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment></Comment>
\t\t\t<NamePrefix></NamePrefix>
\t\t\t<ConfigurationExtensionCompatibilityMode>Version8_3_24</ConfigurationExtensionCompatibilityMode>
\t\t\t<DefaultRunMode>ManagedApplication</DefaultRunMode>
\t\t\t<ScriptVariant>Russian</ScriptVariant>
\t\t\t<Vendor></Vendor>
\t\t\t<Version>1.0</Version>
\t\t</Properties>
\t\t<ChildObjects>
{chr(10).join(child_lines)}
\t\t</ChildObjects>
\t</Configuration>
</MetaDataObject>"""


def generate_config_dump_info(objects: list) -> str:
    """Генерирует ConfigDumpInfo.xml."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        '<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" format="Hierarchical" version="2.18">'
    )
    lines.append("\t<ConfigVersions>")

    for obj_type, obj_name, obj_uuid in objects:
        if not obj_name:
            continue
        lines.append(
            f'\t\t<Metadata name="{obj_type}.{obj_name}" id="{obj_uuid}" configVersion="0000000000000000000000000000000000000000"/>'
        )

    lines.append("\t</ConfigVersions>")
    lines.append("</ConfigDumpInfo>")
    return "\n".join(lines)


# Типы объектов, у которых есть ObjectModule и ManagerModule
OBJECT_TYPES_WITH_MODULES = {
    "Catalog",
    "Document",
    "DataProcessor",
    "Report",
    "InformationRegister",
    "AccumulationRegister",
    "ChartsOfAccounts",
    "ChartOfAccounts",
    "ChartsOfCharacteristicTypes",
    "ChartOfCharacteristicTypes",
    "BusinessProcess",
    "Task",
    "ExchangePlan",
    "Enum",
    "CalculationRegister",
    "AccountingRegister",
    "ChartOfCalculationTypes",
    "FilterCriterion",
    "Constant",
}


def convert_cf_to_xml_format(extracted_dir: Path, output_dir: Path, progress_callback=None) -> dict:
    """
    Конвертирует структуру v8unpack в формат XML выгрузки Конфигуратора.

    Возвращает статистику конвертации.
    """
    extracted_dir = Path(extracted_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Контейнер 1 содержит все объекты метаданных
    objects_dir = extracted_dir / "1"
    if not objects_dir.exists():
        objects_dir = extracted_dir  # альтернативная структура

    # Загружаем контейнер 1 напрямую из .cf файла (более надёжно)
    # Но если уже распаковано — используем файлы

    # Читаем все файлы UUID (без расширения) — это метаданные объектов
    stats = {
        "common_modules": 0,
        "object_modules": 0,
        "manager_modules": 0,
        "common_forms": 0,
        "object_forms": 0,
        "common_commands": 0,
        "subsystems": 0,
        "command_interfaces": 0,
        "other_objects": 0,
        "total_bsl_modules": 0,
    }

    child_objects = []  # для Configuration.xml
    dump_objects = []  # для ConfigDumpInfo.xml

    # Собираем все UUID файлов (метаданные без расширения)
    all_files = {}
    for p in sorted(objects_dir.iterdir()):
        name = p.name
        if "." in name:
            continue
        if not p.is_file():
            continue
        if name in ("version", "versions", "root"):
            continue
        if not re.match(r"^[0-9a-f]{8}-", name, re.IGNORECASE):
            continue
        all_files[name] = p

    print(f"  Найдено файлов метаданных: {len(all_files)}")

    # Карта: UUID → путь к файлу (для быстрого поиска подфайлов)
    uuid_files = set(all_files.keys())

    processed = 0
    for uuid, meta_path in all_files.items():
        processed += 1
        if progress_callback and processed % 1000 == 0:
            progress_callback(processed, len(all_files))

        try:
            content = meta_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue

        # Извлекаем тип объекта
        type_match = re.match(r"\s*\{1,\s*\{(\d+),", content)
        if not type_match:
            continue
        type_code = int(type_match.group(1))
        type_name = detect_type_by_content(content, type_code)

        # Для CommonCommand — проверяем внутренний тип
        inner_type = detect_inner_type(content)
        if inner_type:
            type_name = inner_type

        # Извлекаем имя и UUID
        name, obj_uuid = extract_name_and_uuid(content)
        if not name:
            continue

        synonym = extract_synonym(content)
        safe = safe_name(name)

        # Определяем папку назначения
        dir_name = TYPE_TO_DIR.get(type_name)
        if not dir_name:
            stats["other_objects"] += 1
            continue

        type_dir = output_dir / dir_name
        type_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем XML метаданных объекта
        xml_content = generate_object_xml(type_name, obj_uuid, name, synonym)
        (type_dir / f"{safe}.xml").write_text(xml_content, encoding="utf-8")

        child_objects.append((type_name, name))
        dump_objects.append((type_name, name, obj_uuid))

        # ===================================================================
        # ИЗВЛЕЧЕНИЕ МОДУЛЕЙ
        # ===================================================================

        # 1. CommonModule — модуль в UUID.0/text (контейнер)
        if type_name == "CommonModule":
            module_bsl = _read_bsl_module(objects_dir, uuid, "0")
            if module_bsl:
                module_dir = type_dir / safe / "Ext"
                module_dir.mkdir(parents=True, exist_ok=True)
                (module_dir / "Module.bsl").write_text(module_bsl, encoding="utf-8")
                stats["common_modules"] += 1
                stats["total_bsl_modules"] += 1

        # 2. Объекты с ObjectModule и ManagerModule
        elif type_name in OBJECT_TYPES_WITH_MODULES:
            obj_dir = type_dir / safe / "Ext"
            obj_dir.mkdir(parents=True, exist_ok=True)

            # ObjectModule — в UUID.0/text (контейнер)
            obj_module = _read_bsl_module(objects_dir, uuid, "0")
            if obj_module:
                (obj_dir / "ObjectModule.bsl").write_text(obj_module, encoding="utf-8")
                stats["object_modules"] += 1
                stats["total_bsl_modules"] += 1

            # ManagerModule — в UUID.2 (прямой текст или контейнер)
            mgr_module = _read_bsl_module(objects_dir, uuid, "2")
            if mgr_module:
                (obj_dir / "ManagerModule.bsl").write_text(mgr_module, encoding="utf-8")
                stats["manager_modules"] += 1
                stats["total_bsl_modules"] += 1

        # 3. CommonForm — BSL встроен в данные формы (UUID.0 как текст)
        elif type_name == "CommonForm":
            form_data_text = _read_direct_text(objects_dir, uuid, "0")
            if form_data_text:
                # Извлекаем BSL модуль из данных формы
                bsl_code = extract_bsl_from_form_data(form_data_text)

                form_dir = type_dir / safe / "Ext" / "Form"
                form_dir.mkdir(parents=True, exist_ok=True)

                if bsl_code:
                    (form_dir / "Module.bsl").write_text(bsl_code, encoding="utf-8")
                    stats["total_bsl_modules"] += 1

                # Сохраняем упрощённый XML формы
                form_xml = extract_form_xml_metadata(form_data_text, name)
                (type_dir / safe / "Ext" / "Form.xml").write_text(form_xml, encoding="utf-8")

                stats["common_forms"] += 1

        # 4. CommonCommand — модуль в UUID.2 (прямой текст)
        elif type_name == "CommonCommand":
            cmd_module = _read_bsl_module(objects_dir, uuid, "2")
            if cmd_module:
                cmd_dir = type_dir / safe / "Ext"
                cmd_dir.mkdir(parents=True, exist_ok=True)
                (cmd_dir / "CommandModule.bsl").write_text(cmd_module, encoding="utf-8")
                stats["common_commands"] += 1
                stats["total_bsl_modules"] += 1

        # 5. Subsystem — CommandInterface в UUID.1/text (контейнер)
        elif type_name == "Subsystem":
            # CommandInterface — это текст из контейнера UUID.1
            # (если .1 — это контейнер с info+text, и text не пустой)
            ci_text = _read_module_text(objects_dir, uuid, "1")
            if ci_text and ci_text.strip() and len(ci_text.strip()) > 3:
                ci_dir = type_dir / safe / "Ext"
                ci_dir.mkdir(parents=True, exist_ok=True)
                # Сохраняем как CommandInterface.xml
                ci_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<CommandInterface xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">\n<!-- Original v8unpack format preserved -->\n{ci_text}\n</CommandInterface>'
                (ci_dir / "CommandInterface.xml").write_text(ci_xml, encoding="utf-8")
                stats["command_interfaces"] += 1

            # Также извлекаем модуль подсистемы если есть (UUID.2)
            sub_module = _read_bsl_module(objects_dir, uuid, "2")
            if sub_module:
                sub_dir = type_dir / safe / "Ext"
                sub_dir.mkdir(parents=True, exist_ok=True)
                (sub_dir / "SubsystemModule.bsl").write_text(sub_module, encoding="utf-8")
                stats["total_bsl_modules"] += 1

            stats["subsystems"] += 1

        # 6. Form (вложенная форма объекта, type 0) — извлекаем как форму родительского объекта
        elif type_name == "Form":
            # Это вложенная форма — обрабатываем ниже отдельно
            pass

    # ===================================================================
    # ОБРАБОТКА ВЛОЖЕННЫХ ФОРМ (тип 0)
    # ===================================================================
    # Формы типа 0 — это формы объектов (Catalog.Form, Document.Form, и т.д.)
    # Они ссылаются на родительский объект через метаданные

    forms_processed = _extract_nested_forms(objects_dir, output_dir, all_files, stats)

    # ===================================================================
    # СОЗДАЁМ Configuration.xml и ConfigDumpInfo.xml
    # ===================================================================

    config_xml = generate_configuration_xml(extracted_dir.name, child_objects)
    (output_dir / "Configuration.xml").write_text(config_xml, encoding="utf-8")

    dump_xml = generate_config_dump_info(dump_objects)
    (output_dir / "ConfigDumpInfo.xml").write_text(dump_xml, encoding="utf-8")

    return stats


def _read_module_text(objects_dir: Path, uuid: str, suffix: str) -> str:
    """Читает BSL модуль из UUID.<suffix>.

    Поддерживает два формата:
    1. Контейнер с info+text — файл UUID.<suffix> является директорией с text внутри
    2. Прямой текст — файл UUID.<suffix> является текстовым файлом с BSL кодом
    """
    base_path = objects_dir / f"{uuid}.{suffix}"

    # Вариант 1: это директория (контейнер распакован)
    if base_path.is_dir():
        text_file = base_path / "text"
        if text_file.exists():
            try:
                return text_file.read_text(encoding="utf-8-sig", errors="replace")
            except Exception:
                return ""

    # Вариант 2: это файл — может быть прямым BSL или контейнером
    if base_path.is_file():
        try:
            raw = base_path.read_bytes()
        except Exception:
            return ""

        # Пробуем распаковать
        decomp = read_decompressed(raw)

        # Проверяем, является ли это контейнером
        if is_v8_container(decomp):
            return read_text_from_container(decomp)

        # Иначе — это прямой текст
        try:
            text = decomp.decode("utf-8-sig", errors="replace")
            return text
        except Exception:
            return ""

    return ""


def _read_bsl_module(objects_dir: Path, uuid: str, suffix: str) -> str:
    """Читает только BSL модуль (не метаданные) из UUID.<suffix>.

    Возвращает пустую строку, если файл не содержит BSL кода.
    """
    text = _read_module_text(objects_dir, uuid, suffix)
    if not text:
        return ""

    stripped = text.lstrip()
    # Проверяем, что это BSL (начинается с типичных BSL конструкций)
    if (
        stripped.startswith("#Если")
        or stripped.startswith("#Область")
        or stripped.startswith("Процедура")
        or stripped.startswith("Функция")
        or stripped.startswith("Перем")
        or stripped.startswith("//")
        or "&НаСервере" in stripped[:200]
        or "&НаКлиенте" in stripped[:200]
        or "#НаКлиентеНаСервере" in stripped[:200]
        or "#НаСервере" in stripped[:200]
    ):
        return text

    # Если это похоже на metadata (формат {1,...} или {3,...}) — не BSL
    if stripped.startswith("{"):
        return ""

    return text


def _read_direct_text(objects_dir: Path, uuid: str, suffix: str) -> str:
    """Читает прямой текст из файла UUID.<suffix> (не контейнер)."""
    base_path = objects_dir / f"{uuid}.{suffix}"

    if base_path.is_file():
        try:
            raw = base_path.read_bytes()
            decomp = read_decompressed(raw)
            return decomp.decode("utf-8-sig", errors="replace")
        except Exception:
            return ""

    return ""


def _extract_nested_forms(objects_dir: Path, output_dir: Path, all_files: dict, stats: dict) -> int:
    """Извлекает вложенные формы (тип 0) и привязывает их к родительским объектам."""
    forms_count = 0

    # Строим карту UUID → тип, имя для всех объектов
    objects_map = {}  # uuid → (type_name, name)
    for uuid, meta_path in all_files.items():
        try:
            content = meta_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        type_match = re.match(r"\s*\{1,\s*\{(\d+),", content)
        if not type_match:
            continue
        type_code = int(type_match.group(1))
        type_name = detect_type_by_content(content, type_code)
        inner_type = detect_inner_type(content)
        if inner_type:
            type_name = inner_type
        name, obj_uuid = extract_name_and_uuid(content)
        if name:
            objects_map[uuid] = (type_name, name)

    # Ищем все формы (тип 0)
    for uuid, meta_path in all_files.items():
        try:
            content = meta_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        type_match = re.match(r"\s*\{1,\s*\{(\d+),", content)
        if not type_match:
            continue
        type_code = int(type_match.group(1))
        if type_code != 0:  # только Form
            continue

        # Извлекаем имя формы
        name, form_uuid = extract_name_and_uuid(content)
        if not name:
            continue

        # Ищем родительский объект
        # Форма содержит ссылку на родителя в метаданных
        # Формат: {1,{0,{<parent_type_code>,{1,{0,0,<parent_uuid>},...
        parent_match = re.search(
            r"\{1,\s*\{0,\s*\{(\d+),\s*\{1,\s*\{0,\s*0,\s*([0-9a-f-]{36})\}", content, re.IGNORECASE
        )
        if not parent_match:
            continue

        parent_type_code = int(parent_match.group(1))
        parent_uuid = parent_match.group(2)
        parent_type_name = detect_type_by_content(content, parent_type_code)

        # Ищем имя родителя в карте
        if parent_uuid not in objects_map:
            continue

        parent_type, parent_name = objects_map[parent_uuid]
        # Используем тип родителя из карты (более точный)
        if parent_type and parent_type != "Unknown_0":
            parent_type_name = parent_type

        parent_dir_name = TYPE_TO_DIR.get(parent_type_name)
        if not parent_dir_name:
            continue

        # Извлекаем BSL из данных формы
        form_data_text = _read_direct_text(objects_dir, uuid, "0")
        if not form_data_text:
            continue

        bsl_code = extract_bsl_from_form_data(form_data_text)

        # Сохраняем форму в папку родительского объекта
        safe_parent = safe_name(parent_name)
        safe_form = safe_name(name)

        if parent_type_name == "CommonForm":
            # Уже обработано как CommonForm
            continue

        form_dir = output_dir / parent_dir_name / safe_parent / "Forms" / safe_form / "Ext" / "Form"
        form_dir.mkdir(parents=True, exist_ok=True)

        if bsl_code:
            (form_dir / "Module.bsl").write_text(bsl_code, encoding="utf-8")
            stats["total_bsl_modules"] += 1

        # Сохраняем XML формы
        form_xml = extract_form_xml_metadata(form_data_text, name)
        (output_dir / parent_dir_name / safe_parent / "Forms" / safe_form / "Ext" / "Form.xml").write_text(
            form_xml, encoding="utf-8"
        )

        # Сохраняем метаданные формы
        (output_dir / parent_dir_name / safe_parent / "Forms" / f"{safe_form}.xml").write_text(
            generate_object_xml("Form", form_uuid, name, ""), encoding="utf-8"
        )

        stats["object_forms"] += 1
        forms_count += 1

    return forms_count


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 improved_cf_adapter.py <extracted_cf_dir> <output_dir>")
        print()
        print("Пример:")
        print("  python3 improved_cf_adapter.py /tmp/ut11_full /tmp/ut11_xml")
        sys.exit(1)

    extracted_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not extracted_dir.exists():
        print(f"❌ Папка не найдена: {extracted_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Конвертация: {extracted_dir}")
    print(f"В: {output_dir}")

    def progress(done, total):
        print(f"  Обработано {done}/{total} объектов...")

    stats = convert_cf_to_xml_format(extracted_dir, output_dir, progress)

    print("\n✅ Конвертация завершена!")
    print(f"   CommonModules: {stats['common_modules']}")
    print(f"   ObjectModules: {stats['object_modules']}")
    print(f"   ManagerModules: {stats['manager_modules']}")
    print(f"   CommonForms: {stats['common_forms']}")
    print(f"   Object Forms (вложенные): {stats['object_forms']}")
    print(f"   CommonCommands: {stats['common_commands']}")
    print(f"   Subsystems: {stats['subsystems']}")
    print(f"   CommandInterfaces: {stats['command_interfaces']}")
    print(f"   Other objects: {stats['other_objects']}")
    print(f"   Всего BSL модулей: {stats['total_bsl_modules']}")
    print(f"   Каталог: {output_dir}")


if __name__ == "__main__":
    main()
