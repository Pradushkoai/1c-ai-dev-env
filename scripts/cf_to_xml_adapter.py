#!/usr/bin/env python3
"""
cf_to_xml_adapter.py — Конвертер распакованного .cf в формат XML выгрузки.

Конвертирует структуру v8unpack (из cf_extractor) в формат, полностью
совместимый с инструментами, ожидающими XML выгрузку Конфигуратора:
- build_api_reference.py (CommonModules)
- build_config_index_generic.py (Configuration.xml + ConfigDumpInfo.xml)
- check_metadata_standards.py (все XML объекты)
- ConfigManager._read_config_props (Configuration.xml)
- ConfigManager._count_objects (Catalogs/, Documents/, и т.д.)

Создаёт:
  output/Configuration.xml         — свойства конфигурации
  output/ConfigDumpInfo.xml        — дамп метаданных
  output/CommonModules/<Имя>.xml   — метаданные общих модулей
  output/CommonModules/<Имя>/Ext/Module.bsl — BSL код
  output/Catalogs/<Имя>.xml        — метаданные справочников
  output/Documents/<Имя>.xml       — метаданные документов
  output/...                       — другие типы объектов

Использование:
    python3 cf_to_xml_adapter.py <extracted_cf_dir> <output_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

# Добавляем scripts/ в path
sys.path.insert(0, str(Path(__file__).parent))
from v8_metadata_parser import V8MetadataParser, V8Object, TYPE_MAP


# Маппинг: тип_объекта → имя_папки_в_XML_выгрузке
TYPE_TO_DIR = {
    'CommonModule': 'CommonModules',
    'Catalog': 'Catalogs',
    'Document': 'Documents',
    'InformationRegister': 'InformationRegisters',
    'AccumulationRegister': 'AccumulationRegisters',
    'Enum': 'Enums',
    'Report': 'Reports',
    'DataProcessor': 'DataProcessors',
    'Constant': 'Constants',
    'CommonForm': 'CommonForms',
    'CommonCommand': 'CommonCommands',
    'CommonPicture': 'CommonPictures',
    'CommonTemplate': 'CommonTemplates',
    'CommonAttribute': 'CommonAttributes',
    'Subsystem': 'Subsystems',
    'ExchangePlan': 'ExchangePlans',
    'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes',
    'ChartOfAccounts': 'ChartsOfAccounts',
    'AccountingRegister': 'AccountingRegisters',
    'CalculationRegister': 'CalculationRegisters',
    'BusinessProcess': 'BusinessProcesses',
    'Task': 'Tasks',
    'DefinedType': 'DefinedTypes',
    'EventSubscription': 'EventSubscriptions',
    'ScheduledJob': 'ScheduledJobs',
    'FunctionalOption': 'FunctionalOptions',
    'FunctionalOptionParameter': 'FunctionalOptionsParameters',
    'HTTPService': 'HTTPServices',
    'WebService': 'WebServices',
    'XDTOPackage': 'XDTOPackages',
    'FilterCriterion': 'FilterCriteria',
    'SessionParameter': 'SessionParameters',
    'Role': 'Roles',
    'CommandGroup': 'CommandGroups',
    'Style': 'Styles',
    'StyleItem': 'StyleItems',
    'WSReference': 'WSReferences',
}

# XML шаблон для Configuration.xml
CONFIGURATION_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
        <Configuration uuid="{uuid}">
                <Properties>
                        <Name>{name}</Name>
                        <Synonym>
                                <v8:item>
                                        <v8:lang>ru</v8:lang>
                                        <v8:content>{synonym}</v8:content>
                                </v8:item>
                        </Synonym>
                        <Comment>{comment}</Comment>
                        <NamePrefix>{name_prefix}</NamePrefix>
                        <ConfigurationExtensionCompatibilityMode>Version8_3_24</ConfigurationExtensionCompatibilityMode>
                        <DefaultRunMode>ManagedApplication</DefaultRunMode>
                        <ScriptVariant>Russian</ScriptVariant>
                        <Vendor>{vendor}</Vendor>
                        <Version>{version}</Version>
                </Properties>
                <ChildObjects>
{child_objects}
                </ChildObjects>
        </Configuration>
</MetaDataObject>"""

# XML шаблон для объекта метаданных (универсальный)
OBJECT_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
        <{type} uuid="{uuid}">
                <Properties>
                        <Name>{name}</Name>
                        <Synonym>
                                <v8:item>
                                        <v8:lang>ru</v8:lang>
                                        <v8:content>{synonym}</v8:content>
                                </v8:item>
                        </Synonym>
                        <Comment>{comment}</Comment>
{extra_props}
                </Properties>
        </{type}>
</MetaDataObject>"""

# Дополнительные свойства для CommonModule
COMMON_MODULE_PROPS = """                       <Server>{server}</Server>
                        <ServerCall>{server_call}</ServerCall>
                        <ClientManagedApplication>{client_managed}</ClientManagedApplication>
                        <Global>{global}</Global>
                        <Privileged>{privileged}</Privileged>"""

# Дополнительные свойства для Catalog
CATALOG_PROPS = """                     <Hierarchical>false</Hierarchical>
                        <HierarchyType>HierarchyFoldersAndItems</HierarchyType>
                        <CodeLength>11</CodeLength>
                        <DescriptionLength>100</DescriptionLength>
                        <CheckUnique>true</CheckUnique>"""

# Дополнительные свойства для Document
DOCUMENT_PROPS = """                    <NumberLength>11</NumberLength>
                        <CheckUnique>true</CheckUnique>"""


def detect_module_properties(metadata_content: str) -> dict:
    """Определяет свойства CommonModule из метаданных."""
    import re
    props = {
        'server': 'false', 'client_managed': 'false',
        'server_call': 'false', 'global': 'false',
        'privileged': 'false', 'external_connection': 'false',
        'return_values_reuse': 'false',
    }
    props_match = re.search(
        r'\{1,"ru","[^"]*"\},"[^"]*",\d+,\d+,'
        r'[0-9a-f-]{36},\d+'
        r',(\d+),(\d+),(\d+),(\d+)',
        metadata_content, re.IGNORECASE
    )
    if props_match:
        props['server_call'] = 'true' if props_match.group(1) == '1' else 'false'
        props['global'] = 'true' if props_match.group(2) == '1' else 'false'
        props['privileged'] = 'true' if props_match.group(3) == '1' else 'false'
        props['external_connection'] = 'true' if props_match.group(4) == '1' else 'false'
    if props['server_call'] == 'true':
        props['server'] = 'true'
        props['client_managed'] = 'true'
    return props


def _get_extra_props(obj: V8Object) -> str:
    """Возвращает дополнительные XML свойства в зависимости от типа объекта."""
    if obj.type_name == 'CommonModule':
        props = detect_module_properties(obj.raw_metadata)
        return COMMON_MODULE_PROPS.format(
            server=props['server'],
            server_call=props['server_call'],
            client_managed=props['client_managed'],
            **{'global': props['global']},
            privileged=props['privileged'],
        )
    elif obj.type_name == 'Catalog':
        return CATALOG_PROPS
    elif obj.type_name == 'Document':
        return DOCUMENT_PROPS
    return ""


def _generate_config_xml(objects: list[V8Object], title: str) -> str:
    """Генерирует Configuration.xml из списка объектов."""
    # Группируем объекты по типу для ChildObjects
    child_lines = []
    for obj in objects:
        if not obj.name:
            continue
        # Формат: <Type>Name</Type>
        child_lines.append(f"\t\t\t<{obj.type_name}>{obj.name}</{obj.type_name}>")
    
    child_objects = "\n".join(child_lines)
    
    return CONFIGURATION_XML_TEMPLATE.format(
        uuid="00000000-0000-0000-0000-000000000000",
        name=title or "Конфигурация",
        synonym=title or "Конфигурация",
        comment="",
        name_prefix="",
        vendor="",
        version="1.0",
        child_objects=child_objects,
    )


def _generate_config_dump_info(objects: list[V8Object]) -> str:
    """Генерирует ConfigDumpInfo.xml из списка объектов."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" format="Hierarchical" version="2.18">')
    lines.append('\t<ConfigVersions>')
    
    for obj in objects:
        if not obj.name:
            continue
        # Маппинг типа в путь метаданных
        type_prefix = obj.type_name
        lines.append(f'\t\t<Metadata name="{type_prefix}.{obj.name}" id="{obj.uuid}" configVersion="0000000000000000000000000000000000000000">')
        # Добавляем BSL модули если есть
        for mod_name in obj.bsl_modules:
            lines.append(f'\t\t\t<Metadata name="{type_prefix}.{obj.name}.Module" id="{obj.uuid}.0" configVersion="0000000000000000000000000000000000000000"/>')
        lines.append('\t\t</Metadata>')
    
    lines.append('\t</ConfigVersions>')
    lines.append('</ConfigDumpInfo>')
    return "\n".join(lines)


def _generate_object_xml(obj: V8Object) -> str:
    """Генерирует XML для объекта метаданных."""
    extra = _get_extra_props(obj)
    return OBJECT_XML_TEMPLATE.format(
        type=obj.type_name,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym or obj.name,
        comment=obj.comment or "",
        extra_props=extra,
    )


def convert_cf_to_xml_format(extracted_dir: Path, output_dir: Path) -> int:
    """
    Конвертирует структуру v8unpack в формат XML выгрузки Конфигуратора.
    
    Создаёт:
    - Configuration.xml — свойства конфигурации
    - ConfigDumpInfo.xml — дамп метаданных
    - CommonModules/<Имя>.xml + Ext/Module.bsl
    - Catalogs/<Имя>.xml, Documents/<Имя>.xml, и т.д.
    
    Args:
        extracted_dir: Папка с распакованным .cf (через cf_extractor)
        output_dir: Куда положить конвертированную структуру

    Returns:
        Количество конвертированных объектов
    """
    parser = V8MetadataParser(extracted_dir)
    objects = parser.parse_all()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Создаём Configuration.xml
    config_xml = _generate_config_xml(objects, extracted_dir.name)
    (output_dir / "Configuration.xml").write_text(config_xml, encoding="utf-8")
    
    # 2. Создаём ConfigDumpInfo.xml
    dump_info = _generate_config_dump_info(objects)
    (output_dir / "ConfigDumpInfo.xml").write_text(dump_info, encoding="utf-8")
    
    # 3. Конвертируем все объекты метаданных
    converted = 0
    for obj in objects:
        if not obj.name:
            continue
        
        # Определяем папку назначения
        dir_name = TYPE_TO_DIR.get(obj.type_name)
        if not dir_name:
            continue  # неизвестный тип — пропускаем
        
        type_dir = output_dir / dir_name
        type_dir.mkdir(parents=True, exist_ok=True)
        
        # Безопасное имя
        safe_name = obj.name.replace('/', '_').replace('\\', '_').replace(':', '_')
        
        # Генерируем и сохраняем XML
        xml_content = _generate_object_xml(obj)
        xml_path = type_dir / f"{safe_name}.xml"
        xml_path.write_text(xml_content, encoding="utf-8")
        
        # Сохраняем BSL модули (для CommonModules — Ext/Module.bsl)
        if obj.bsl_modules:
            if obj.type_name == 'CommonModule':
                module_dir = type_dir / safe_name / 'Ext'
                module_dir.mkdir(parents=True, exist_ok=True)
                bsl_path = module_dir / 'Module.bsl'
                # Prefer 'Module' key (was 'ObjectModule' before v2 fix)
                preferred_keys = ['Module', 'ObjectModule', 'ManagerModule']
                written = False
                for key in preferred_keys:
                    if key in obj.bsl_modules and obj.bsl_modules[key].strip():
                        bsl_path.write_text(obj.bsl_modules[key], encoding="utf-8")
                        written = True
                        break
                if not written:
                    # Fallback — первый доступный модуль
                    for mod_code in obj.bsl_modules.values():
                        if mod_code.strip():
                            bsl_path.write_text(mod_code, encoding="utf-8")
                            written = True
                            break
                if not written:
                    bsl_path.write_text('', encoding="utf-8")
            elif obj.type_name in ('Catalog', 'Document', 'InformationRegister', 
                                    'AccumulationRegister', 'Report', 'DataProcessor',
                                    'ChartOfCharacteristicTypes', 'ChartOfAccounts',
                                    'AccountingRegister', 'CalculationRegister',
                                    'BusinessProcess', 'Task', 'ExchangePlan',
                                    'Enum', 'Constant', 'FilterCriterion'):
                # Для объектов с модулями — Ext/ObjectModule.bsl, Ext/ManagerModule.bsl
                obj_dir = type_dir / safe_name / 'Ext'
                obj_dir.mkdir(parents=True, exist_ok=True)
                if 'ObjectModule' in obj.bsl_modules:
                    (obj_dir / 'ObjectModule.bsl').write_text(
                        obj.bsl_modules['ObjectModule'], encoding="utf-8")
                if 'ManagerModule' in obj.bsl_modules:
                    (obj_dir / 'ManagerModule.bsl').write_text(
                        obj.bsl_modules['ManagerModule'], encoding="utf-8")
                # Fallback: если есть только 'Module' (для некоторых объектов)
                if 'Module' in obj.bsl_modules and not (obj_dir / 'ObjectModule.bsl').exists():
                    (obj_dir / 'ObjectModule.bsl').write_text(
                        obj.bsl_modules['Module'], encoding="utf-8")
        
        converted += 1
    
    return converted


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 cf_to_xml_adapter.py <extracted_cf_dir> <output_dir>")
        print()
        print("Пример:")
        print("  python3 cf_to_xml_adapter.py /tmp/edo3_full /tmp/edo3_xml")
        sys.exit(1)

    extracted_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not extracted_dir.exists():
        print(f"❌ Папка не найдена: {extracted_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Конвертация: {extracted_dir}")
    print(f"В: {output_dir}")

    count = convert_cf_to_xml_format(extracted_dir, output_dir)
    print(f"\n✅ Конвертировано объектов: {count}")
    print(f"   Configuration.xml: создан")
    print(f"   ConfigDumpInfo.xml: создан")
    print(f"   Каталог: {output_dir}")


if __name__ == "__main__":
    main()
