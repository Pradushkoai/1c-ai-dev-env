#!/usr/bin/env python3
"""
Построение индекса конфигурации 1С.
Универсальная версия — работает с любой выгрузкой конфигурации:
- Configuration.xml (свойства конфигурации)
- ConfigDumpInfo.xml (дамп метаданных)
- Опционально: поддиректории с .xml объектами (Catalogs/, Documents/, и т.д.)

Использование:
  python3 build_config_index_generic.py <config_dir> <output_index> <config_name>

Пример:
  python3 build_config_index_generic.py /home/z/my-project/config-priemka /home/z/my-project/config-priemka-index.md "Приемка товаров"
"""

import xml.etree.ElementTree as ET
from collections import defaultdict, OrderedDict
import os
import re
import sys
from datetime import datetime


def strip_ns(tag):
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def get_child(elem, tag):
    if elem is None:
        return None
    for child in elem:
        if strip_ns(child.tag) == tag:
            return child
    return None


def get_text(elem, tag, default=''):
    child = get_child(elem, tag)
    if child is not None:
        return child.text or ''
    return default


def get_synonym_text(parent, tag='Synonym'):
    elem = get_child(parent, tag)
    if elem is None:
        return ''
    if elem.text and elem.text.strip():
        return elem.text.strip()
    for item in elem:
        if strip_ns(item.tag) == 'item':
            content = get_text(item, 'content')
            if content:
                return content
    return ''


def get_type_description(type_elem):
    """
    Извлекает описание типа из элемента <Type>.
    Возвращает строковое описание (например, 'xs:string', 'CatalogRef.Номенклатура', 'xs:decimal(10,2)').
    """
    if type_elem is None:
        return ''
    
    types = []
    for child in type_elem:
        tag = strip_ns(child.tag)
        if tag == 'Type':
            # v8:Type
            text = (child.text or '').strip()
            if text:
                types.append(text)
    
    # Дополнительные свойства типа
    type_qualifiers = []
    number_qualifiers = get_child(type_elem, 'NumberQualifiers')
    if number_qualifiers is not None:
        precision = get_text(number_qualifiers, 'Precision')
        scale = get_text(number_qualifiers, 'Scale')
        if precision:
            type_qualifiers.append(f'({precision},{scale or "0"})')
    
    string_qualifiers = get_child(type_elem, 'StringQualifiers')
    if string_qualifiers is not None:
        length = get_text(string_qualifiers, 'Length')
        if length:
            type_qualifiers.append(f'[{length}]')
    
    result = ', '.join(types) if types else ''
    if type_qualifiers:
        result += ' ' + ' '.join(type_qualifiers)
    return result


# === ПАРСИНГ Configuration.xml ===

METADATA_TYPES = OrderedDict([
    ('Subsystem', ('Подсистемы', 'Subsystems')),
    ('CommonModule', ('Общие модули', 'CommonModules')),
    ('SessionParameter', ('Параметры сеанса', 'SessionParameters')),
    ('Role', ('Роли', 'Roles')),
    ('CommonTemplate', ('Общие макеты', 'CommonTemplates')),
    ('CommonPicture', ('Общие картинки', 'CommonPictures')),
    ('CommonForm', ('Общие формы', 'CommonForms')),
    ('CommonCommand', ('Общие команды', 'CommonCommands')),
    ('CommandGroup', ('Группы команд', 'CommandGroups')),
    ('CommonAttribute', ('Общие реквизиты', 'CommonAttributes')),
    ('FilterCriterion', ('Критерии отбора', 'FilterCriteria')),
    ('EventSubscription', ('Подписки на события', 'EventSubscriptions')),
    ('ScheduledJob', ('Регламентные задания', 'ScheduledJobs')),
    ('DefinedType', ('Определяемые типы', 'DefinedTypes')),
    ('Constant', ('Константы', 'Constants')),
    ('Catalog', ('Справочники', 'Catalogs')),
    ('Document', ('Документы', 'Documents')),
    ('DocumentJournal', ('Журналы документов', 'DocumentJournals')),
    ('DocumentNumerator', ('Нумераторы документов', 'DocumentNumerators')),
    ('Sequence', ('Последовательности', 'Sequences')),
    ('Enum', ('Перечисления', 'Enums')),
    ('Report', ('Отчеты', 'Reports')),
    ('DataProcessor', ('Обработки', 'DataProcessors')),
    ('InformationRegister', ('Регистры сведений', 'InformationRegisters')),
    ('AccumulationRegister', ('Регистры накопления', 'AccumulationRegisters')),
    ('AccountingRegister', ('Регистры бухгалтерии', 'AccountingRegisters')),
    ('CalculationRegister', ('Регистры расчета', 'CalculationRegisters')),
    ('ChartOfCharacteristicTypes', ('Планы видов характеристик', 'ChartsOfCharacteristicTypes')),
    ('ChartOfAccounts', ('Планы счетов', 'ChartsOfAccounts')),
    ('ChartOfCalculationTypes', ('Планы видов расчета', 'ChartsOfCalculationTypes')),
    ('ExchangePlan', ('Планы обмена', 'ExchangePlans')),
    ('BusinessProcess', ('Бизнес-процессы', 'BusinessProcesses')),
    ('Task', ('Задачи', 'Tasks')),
    ('FunctionalOption', ('Функциональные опции', 'FunctionalOptions')),
    ('FunctionalOptionsParameter', ('Параметры функциональных опций', 'FunctionalOptionsParameters')),
    ('HTTPService', ('HTTP-сервисы', 'HTTPServices')),
    ('WebService', ('Web-сервисы', 'WebServices')),
    ('WSReference', ('WS-ссылки', 'WSReferences')),
    ('XDTOPackage', ('XDTO-пакеты', 'XTDPackages')),
    ('SettingsStorage', ('Хранилища настроек', 'SettingsStorages')),
    ('Style', ('Стили', 'Styles')),
    ('StyleItem', ('Элементы стилей', 'StyleItems')),
    ('Language', ('Языки', 'Languages')),
])

# Маппинг имени типа ( singular -> множественное в директориях)
TYPE_TO_DIR = {
    'Catalog': 'Catalogs',
    'Document': 'Documents',
    'InformationRegister': 'InformationRegisters',
    'AccumulationRegister': 'AccumulationRegisters',
    'Enum': 'Enums',
    'CommonModule': 'CommonModules',
    'CommonForm': 'CommonForms',
    'CommonTemplate': 'CommonTemplates',
    'CommonPicture': 'CommonPictures',
    'CommonCommand': 'CommonCommands',
    'Subsystem': 'Subsystems',
    'Constant': 'Constants',
    'DataProcessor': 'DataProcessors',
    'Report': 'Reports',
    'Role': 'Roles',
    'SessionParameter': 'SessionParameters',
    'DefinedType': 'DefinedTypes',
    'EventSubscription': 'EventSubscriptions',
    'ScheduledJob': 'ScheduledJobs',
    'FilterCriterion': 'FilterCriteria',
    'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes',
    'ExchangePlan': 'ExchangePlans',
    'BusinessProcess': 'BusinessProcesses',
    'Task': 'Tasks',
    'FunctionalOption': 'FunctionalOptions',
    'HTTPService': 'HTTPServices',
    'WebService': 'WebServices',
    'Style': 'Styles',
    'StyleItem': 'StyleItems',
}


def parse_configuration_xml(configuration_path):
    """
    Парсит Configuration.xml.
    Возвращает: properties dict + list of subsystem names
    """
    if not os.path.exists(configuration_path):
        return {}, []
    
    tree = ET.parse(configuration_path)
    root = tree.getroot()
    
    cfg = get_child(root, 'Configuration')
    if cfg is None:
        return {}, []
    
    # === Properties ===
    props = {}
    props_elem = get_child(cfg, 'Properties')
    if props_elem is not None:
        simple_fields = [
            'Name', 'Comment', 'NamePrefix', 'Version', 'Vendor',
            'ConfigurationExtensionCompatibilityMode',
            'DefaultRunMode', 'ScriptVariant', 'DefaultLanguage',
            'DataLockControlMode', 'ObjectAutonumerationMode',
            'ModalityUseMode', 'SynchronousPlatformExtensionAndAddInCallUseMode',
            'InterfaceCompatibilityMode', 'DatabaseTablespacesUseMode',
            'CompatibilityMode', 'MainClientApplicationWindowMode',
            'DefaultInterface', 'DefaultStyle', 'DefaultConstantsForm',
            'DefaultReportForm', 'DefaultReportVariantForm', 'DefaultReportSettingsForm',
            'DefaultDynamicListSettingsForm', 'DefaultSearchForm',
            'CommonSettingsStorage', 'ReportsUserSettingsStorage',
            'ReportsVariantsStorage', 'FormDataSettingsStorage',
            'DynamicListsUserSettingsStorage', 'URLExternalDataStorage',
            'ConfigurationInformationAddress', 'VendorInformationAddress',
            'UpdateCatalogAddress', 'DefaultReportAppearanceTemplate',
            'IncludeHelpInContents',
            'UseManagedFormInOrdinaryApplication',
            'UseOrdinaryFormInManagedApplication',
        ]
        for f in simple_fields:
            value = get_text(props_elem, f)
            if value:
                props[f] = value
        
        syn = get_synonym_text(props_elem, 'Synonym')
        if syn:
            props['Synonym'] = syn
        
        up = get_child(props_elem, 'UsePurposes')
        if up is not None:
            purposes = []
            for p in up:
                p_tag = strip_ns(p.tag)
                if 'PersonalComputer' in p_tag or 'PlatformApplication' in p_tag:
                    purposes.append('Приложение для ПК')
                elif 'MobileDevice' in p_tag or 'MobilePlatformApplication' in p_tag:
                    purposes.append('Мобильное приложение')
                elif 'GroupApplication' in p_tag:
                    purposes.append('Групповое приложение')
                elif 'StandaloneApplication' in p_tag:
                    purposes.append('Автономное приложение')
            if purposes:
                props['UsePurposes'] = ', '.join(purposes)
        
        dr = get_child(props_elem, 'DefaultRoles')
        if dr is not None:
            roles = []
            for r in dr:
                tag = strip_ns(r.tag)
                if tag == 'Role':
                    roles.append(r.text or '')
            if roles:
                props['DefaultRoles'] = ', '.join(roles)
        
        for f in ('BriefInformation', 'DetailedInformation', 'Copyright'):
            v = get_synonym_text(props_elem, f)
            if v:
                props[f] = v
    
    # === ChildObjects ===
    subsystems = []
    
    child_objects = get_child(cfg, 'ChildObjects')
    if child_objects is not None:
        for obj in child_objects:
            obj_tag = strip_ns(obj.tag)
            if obj_tag == 'Subsystem':
                if obj.text and obj.text.strip():
                    subsystems.append(obj.text.strip())
    
    return props, subsystems


def parse_dumpinfo(dumpinfo_path):
    """
    Парсит ConfigDumpInfo.xml.
    Возвращает dict: type_singular -> {obj_name: {...}}
    """
    TYPE_PREFIXES = set(TYPE_TO_DIR.keys())
    
    objects = defaultdict(lambda: defaultdict(lambda: {
        'name': '',
        'uuid': '',
        'fields': [],
        'modules': [],
        'forms': [],
        'templates': [],
        'commands': [],
        'predefined': [],
        'has_help': False,
    }))
    
    if not os.path.exists(dumpinfo_path):
        return objects
    
    for event, elem in ET.iterparse(dumpinfo_path, events=('end',)):
        tag = strip_ns(elem.tag)
        if tag != 'Metadata':
            elem.clear()
            continue
        
        name_attr = elem.get('name', '')
        if not name_attr:
            elem.clear()
            continue
        
        parts = name_attr.split('.')
        if len(parts) < 2:
            elem.clear()
            continue
        
        type_prefix = parts[0]
        obj_name = parts[1]
        suffix = '.'.join(parts[2:]) if len(parts) > 2 else None
        
        if type_prefix not in TYPE_PREFIXES:
            elem.clear()
            continue
        
        obj = objects[type_prefix][obj_name]
        obj['name'] = obj_name
        
        if suffix is None:
            obj['uuid'] = elem.get('id', '')
        else:
            if suffix == 'Help':
                obj['has_help'] = True
            elif suffix.startswith('Form.'):
                form_name = suffix[5:].split('.')[0]  # только часть до первой точки
                if form_name and form_name not in obj['forms']:
                    obj['forms'].append(form_name)
            elif suffix.startswith('Template.'):
                tpl_name = suffix[9:].split('.')[0]
                if tpl_name and tpl_name not in obj['templates']:
                    obj['templates'].append(tpl_name)
            elif suffix.startswith('Command.'):
                cmd_name = suffix[8:].split('.')[0]
                if cmd_name and cmd_name not in obj['commands']:
                    obj['commands'].append(cmd_name)
            elif suffix.startswith('Predefined.'):
                obj['predefined'].append(suffix[11:])
            elif suffix in ('ObjectModule', 'ManagerModule', 'RecordSetModule',
                          'ValueManagerModule', 'FormModule', 'CommandModule',
                          'Linked Attribute'):
                obj['modules'].append(suffix)
            elif '.' in suffix:
                field_parts = suffix.split('.')
                if len(field_parts) >= 2:
                    field_type = field_parts[0]
                    field_name = field_parts[1]
                    field_subname = field_parts[2] if len(field_parts) > 2 else None
                    
                    if field_type in ('Resource', 'Dimension', 'Attribute'):
                        obj['fields'].append({
                            'type': field_type,
                            'name': field_name,
                            'subname': field_subname,
                            'data_type': '',  # будет заполнено из .xml объекта
                        })
                    elif field_type == 'TabularSection':
                        if not field_subname:
                            obj['fields'].append({
                                'type': 'TabularSection',
                                'name': field_name,
                                'subname': None,
                                'data_type': '',
                            })
                    elif field_type == 'EnumValues':
                        obj['predefined'].append(field_name)
        
        elem.clear()
    
    return objects


def enrich_from_xml_files(config_dir, objects):
    """
    Дополняет информацию об объектах из отдельных .xml файлов.
    Извлекает: синонимы, типы данных реквизитов, владельцев, иерархию, формы, табличные части.
    """
    for type_singular, objs in objects.items():
        dir_name = TYPE_TO_DIR.get(type_singular)
        if not dir_name:
            continue
        
        type_dir = os.path.join(config_dir, dir_name)
        if not os.path.isdir(type_dir):
            continue
        
        for obj_name, obj in objs.items():
            obj_xml_path = os.path.join(type_dir, obj_name + '.xml')
            if not os.path.exists(obj_xml_path):
                continue
            
            try:
                tree = ET.parse(obj_xml_path)
                root = tree.getroot()
                
                # Найти корневой элемент объекта (Catalog, Document, и т.д.)
                obj_elem = None
                for child in root:
                    tag = strip_ns(child.tag)
                    if tag in (type_singular, 'MetaDataObject'):
                        if tag == type_singular:
                            obj_elem = child
                            break
                
                if obj_elem is None:
                    # Попробуем искать внутри MetaDataObject
                    mdo = get_child(root, 'MetaDataObject')
                    if mdo is not None:
                        obj_elem = get_child(mdo, type_singular)
                
                if obj_elem is None:
                    continue
                
                # Свойства
                props_elem = get_child(obj_elem, 'Properties')
                if props_elem is not None:
                    # Синоним
                    syn = get_synonym_text(props_elem, 'Synonym')
                    if syn:
                        obj['synonym'] = syn
                    
                    # Комментарий
                    comment = get_text(props_elem, 'Comment')
                    if comment:
                        obj['comment'] = comment
                    
                    # Дополнительные свойства (для справочников)
                    if type_singular == 'Catalog':
                        obj['hierarchical'] = get_text(props_elem, 'Hierarchical')
                        obj['code_length'] = get_text(props_elem, 'CodeLength')
                        obj['description_length'] = get_text(props_elem, 'DescriptionLength')
                        obj['code_type'] = get_text(props_elem, 'CodeType')
                        obj['level_count'] = get_text(props_elem, 'LevelCount')
                        obj['owners'] = []
                        owners_elem = get_child(props_elem, 'Owners')
                        if owners_elem is not None:
                            for o in owners_elem:
                                tag = strip_ns(o.tag)
                                if tag == 'Catalog':
                                    obj['owners'].append(o.text or '')
                    
                    # Для документов
                    if type_singular == 'Document':
                        obj['number_type'] = get_text(props_elem, 'NumberType')
                        obj['number_length'] = get_text(props_elem, 'NumberLength')
                        obj['periodicity'] = get_text(props_elem, 'Periodicity')
                    
                    # Для регистров
                    if type_singular in ('InformationRegister', 'AccumulationRegister',
                                         'AccountingRegister', 'CalculationRegister'):
                        obj['write_on_write'] = get_text(props_elem, 'WriteOnWrite')
                        obj['recording_periodicity'] = get_text(props_elem, 'RecordingPeriodicity')
                        obj['register_records'] = get_text(props_elem, 'RegisterRecords')
                        # Регистратор
                        registrars_elem = get_child(props_elem, 'RecordResources')
                        if registrars_elem is not None:
                            obj['registrars'] = [r.text or '' for r in registrars_elem
                                                if strip_ns(r.tag) in ('Document', 'DataProcessor', 'Report')]
                
                # Дочерние объекты (реквизиты с типами, табличные части, формы)
                child_objects_elem = get_child(obj_elem, 'ChildObjects')
                if child_objects_elem is not None:
                    for child in child_objects_elem:
                        child_tag = strip_ns(child.tag)
                        
                        if child_tag == 'Attribute':
                            # Свойства (Name, Synonym, Type) лежат внутри <Properties>
                            attr_props = get_child(child, 'Properties')
                            if attr_props is None:
                                attr_props = child  # fallback
                            attr_name = get_text(attr_props, 'Name')
                            attr_syn = get_synonym_text(attr_props, 'Synonym')
                            type_elem = get_child(attr_props, 'Type')
                            type_desc = get_type_description(type_elem)
                            
                            # Найдём это поле в obj['fields'] и обновим
                            for f in obj['fields']:
                                if f['type'] == 'Attribute' and f['name'] == attr_name:
                                    f['data_type'] = type_desc
                                    f['synonym'] = attr_syn
                                    break
                            else:
                                # Не нашли в dumpinfo — добавим
                                obj['fields'].append({
                                    'type': 'Attribute',
                                    'name': attr_name,
                                    'subname': None,
                                    'data_type': type_desc,
                                    'synonym': attr_syn,
                                })
                        
                        elif child_tag == 'TabularSection':
                            # Свойства (Name, Synonym) внутри <Properties>
                            ts_props = get_child(child, 'Properties')
                            if ts_props is None:
                                ts_props = child
                            ts_name = get_text(ts_props, 'Name')
                            ts_syn = get_synonym_text(ts_props, 'Synonym')
                            # Реквизиты табличной части
                            ts_attrs = []
                            ts_co = get_child(child, 'ChildObjects')
                            if ts_co is not None:
                                for sub in ts_co:
                                    sub_tag = strip_ns(sub.tag)
                                    if sub_tag == 'Attribute':
                                        sub_props = get_child(sub, 'Properties')
                                        if sub_props is None:
                                            sub_props = sub
                                        sub_name = get_text(sub_props, 'Name')
                                        sub_syn = get_synonym_text(sub_props, 'Synonym')
                                        type_elem = get_child(sub_props, 'Type')
                                        type_desc = get_type_description(type_elem)
                                        ts_attrs.append({
                                            'name': sub_name,
                                            'synonym': sub_syn,
                                            'data_type': type_desc,
                                        })
                            
                            # Найдём или добавим табличную часть
                            for f in obj['fields']:
                                if f['type'] == 'TabularSection' and f['name'] == ts_name:
                                    f['synonym'] = ts_syn
                                    f['attributes'] = ts_attrs
                                    break
                            else:
                                obj['fields'].append({
                                    'type': 'TabularSection',
                                    'name': ts_name,
                                    'subname': None,
                                    'data_type': '',
                                    'synonym': ts_syn,
                                    'attributes': ts_attrs,
                                })
                        
                        elif child_tag == 'Form':
                            form_props = get_child(child, 'Properties')
                            if form_props is None:
                                form_props = child
                            form_name = get_text(form_props, 'Name')
                            if form_name and form_name not in obj['forms']:
                                obj['forms'].append(form_name)
                        
                        elif child_tag == 'Template':
                            tpl_props = get_child(child, 'Properties')
                            if tpl_props is None:
                                tpl_props = child
                            tpl_name = get_text(tpl_props, 'Name')
                            if tpl_name and tpl_name not in obj['templates']:
                                obj['templates'].append(tpl_name)
                        
                        elif child_tag == 'Command':
                            cmd_props = get_child(child, 'Properties')
                            if cmd_props is None:
                                cmd_props = child
                            cmd_name = get_text(cmd_props, 'Name')
                            if cmd_name and cmd_name not in obj['commands']:
                                obj['commands'].append(cmd_name)
            
            except ET.ParseError as e:
                # Пропускаем файлы с ошибками
                continue


def build_index(config_dir, output_index, config_name):
    """Главная функция построения индекса."""
    configuration_path = os.path.join(config_dir, 'Configuration.xml')
    dumpinfo_path = os.path.join(config_dir, 'ConfigDumpInfo.xml')
    
    print(f'Config dir: {config_dir}')
    print(f'Config name: {config_name}')
    print()
    
    print('Parsing Configuration.xml...')
    cfg_props, subsystems = parse_configuration_xml(configuration_path)
    print(f'  Properties: {len(cfg_props)}')
    print(f'  Subsystems: {len(subsystems)}')
    
    print('Parsing ConfigDumpInfo.xml...')
    objects = parse_dumpinfo(dumpinfo_path)
    total = sum(len(v) for v in objects.values())
    print(f'  Total objects: {total}')
    
    # Дополняем из отдельных .xml файлов (если есть)
    has_xml_files = any(os.path.isdir(os.path.join(config_dir, d))
                       for d in TYPE_TO_DIR.values())
    if has_xml_files:
        print('Enriching from individual .xml files...')
        enrich_from_xml_files(config_dir, objects)
        print('  Done.')
    
    # === ГЕНЕРАЦИЯ ИНДЕКСА ===
    print('\nGenerating index...')
    
    lines = []
    lines.append(f'# Индекс конфигурации: {config_name}')
    lines.append('')
    lines.append(f'> Сгенерировано: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 1. Свойства конфигурации
    lines.append('## 1. Свойства конфигурации')
    lines.append('')
    lines.append('| Свойство | Значение |')
    lines.append('|----------|----------|')
    
    prop_labels = [
        ('Name', 'Имя'),
        ('Synonym', 'Синоним'),
        ('Version', 'Версия'),
        ('Vendor', 'Поставщик'),
        ('Comment', 'Комментарий'),
        ('NamePrefix', 'Префикс имени'),
        ('ConfigurationExtensionCompatibilityMode', 'Режим совместимости расширений'),
        ('CompatibilityMode', 'Режим совместимости платформы'),
        ('DefaultRunMode', 'Режим запуска по умолчанию'),
        ('InterfaceCompatibilityMode', 'Режим интерфейса'),
        ('DefaultLanguage', 'Язык по умолчанию'),
        ('ScriptVariant', 'Вариант встроенного языка'),
        ('DataLockControlMode', 'Режим блокировки данных'),
        ('ObjectAutonumerationMode', 'Автонумерация объектов'),
        ('ModalityUseMode', 'Использование модальности'),
        ('SynchronousPlatformExtensionAndAddInCallUseMode', 'Синхронные вызовы расширений/внеш. компонент'),
        ('MainClientApplicationWindowMode', 'Режим главного окна клиента'),
        ('UsePurposes', 'Назначения'),
        ('DefaultRoles', 'Роли по умолчанию'),
        ('IncludeHelpInContents', 'Включать помощь в содержание'),
        ('UseManagedFormInOrdinaryApplication', 'Управ. формы в обычном приложении'),
        ('UseOrdinaryFormInManagedApplication', 'Обычные формы в управляемом приложении'),
        ('DefaultReportForm', 'Форма отчета по умолчанию'),
        ('DefaultReportVariantForm', 'Форма варианта отчета'),
        ('BriefInformation', 'Краткая информация'),
        ('DetailedInformation', 'Подробная информация'),
        ('Copyright', 'Авторские права'),
    ]
    
    for key, label in prop_labels:
        if key in cfg_props:
            val = cfg_props[key].replace('|', '\\|')
            lines.append(f'| **{label}** | {val} |')
    
    lines.append('')
    lines.append(f'**Всего объектов метаданных:** {total}')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 2. Сводная таблица по типам
    lines.append('## 2. Состав метаданных по типам')
    lines.append('')
    lines.append('| Тип | Количество |')
    lines.append('|-----|------------|')
    
    for type_singular, (ru_name, type_plural) in METADATA_TYPES.items():
        objs = objects.get(type_singular, {})
        if objs:
            lines.append(f'| {ru_name} | {len(objs)} |')
    
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 3. Подсистемы
    lines.append('## 3. Подсистемы')
    lines.append('')
    if subsystems:
        lines.append(f'Всего подсистем: **{len(subsystems)}**')
        lines.append('')
        lines.append('| № | Имя |')
        lines.append('|---|-----|')
        for i, name in enumerate(subsystems, 1):
            lines.append(f'| {i} | `{name}` |')
    else:
        lines.append('Подсистемы не найдены.')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    # 4. Детальные таблицы
    lines.append('## 4. Объекты метаданных')
    lines.append('')
    
    def short_list(items, n=10):
        if not items:
            return '—'
        out = ', '.join(items[:n])
        if len(items) > n:
            out += f' (+{len(items)-n})'
        return out
    
    for type_singular, (ru_name, type_plural) in METADATA_TYPES.items():
        objs = objects.get(type_singular, {})
        if not objs:
            continue
        
        lines.append(f'### {ru_name} (`{type_plural}`) — {len(objs)} шт.')
        lines.append('')
        
        sorted_objs = sorted(objs.values(), key=lambda x: x['name'])
        
        if type_singular in ('AccumulationRegister', 'InformationRegister',
                            'AccountingRegister', 'CalculationRegister'):
            lines.append('| Имя | Синоним | Измерения | Ресурсы | Реквизиты | Модули | Формы |')
            lines.append('|-----|---------|-----------|---------|-----------|--------|-------|')
            for obj in sorted_objs:
                dims = [f for f in obj['fields'] if f['type'] == 'Dimension']
                res = [f for f in obj['fields'] if f['type'] == 'Resource']
                attrs = [f for f in obj['fields'] if f['type'] == 'Attribute']
                
                def fmt_fields(items, with_type=True, n=5):
                    if not items:
                        return '—'
                    out_list = []
                    for it in items[:n]:
                        name = it['name']
                        dt = it.get('data_type', '')
                        if dt and with_type:
                            out_list.append(f'{name} ({dt})')
                        else:
                            out_list.append(name)
                    out = ', '.join(out_list)
                    if len(items) > n:
                        out += f' (+{len(items)-n})'
                    return out
                
                modules_str = short_list(obj['modules']) if obj['modules'] else '—'
                forms_str = short_list(obj['forms'], 3) if obj['forms'] else '—'
                dims_str = fmt_fields(dims)
                res_str = fmt_fields(res)
                attrs_str = fmt_fields(attrs, n=3)
                
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} | {dims_str} | {res_str} | {attrs_str} | {modules_str} | {forms_str} |')
        
        elif type_singular == 'Catalog':
            lines.append('| Имя | Синоним | Длина кода | Длина наименования | Иерархия | Владельцы | Реквизиты (с типами) | Табличные части | Модули | Формы |')
            lines.append('|-----|---------|------------|--------------------|----------|-----------|-----------------------|-----------------|--------|-------|')
            for obj in sorted_objs:
                attrs = [f for f in obj['fields'] if f['type'] == 'Attribute']
                tabs = [f for f in obj['fields'] if f['type'] == 'TabularSection']
                
                def fmt_attrs_with_types(items, n=5):
                    if not items:
                        return '—'
                    out_list = []
                    for it in items[:n]:
                        name = it['name']
                        dt = it.get('data_type', '')
                        if dt:
                            out_list.append(f'{name} ({dt})')
                        else:
                            out_list.append(name)
                    out = ', '.join(out_list)
                    if len(items) > n:
                        out += f' (+{len(items)-n})'
                    return out
                
                modules_str = short_list(obj['modules']) if obj['modules'] else '—'
                forms_str = short_list(obj['forms'], 3) if obj['forms'] else '—'
                attrs_str = fmt_attrs_with_types(attrs)
                tabs_str = short_list([t['name'] for t in tabs], 3)
                
                syn = obj.get('synonym', '').replace('|', '\\|')
                hier = 'да' if obj.get('hierarchical') == 'true' else 'нет'
                code_len = obj.get('code_length', '—')
                desc_len = obj.get('description_length', '—')
                owners = ', '.join(obj.get('owners', [])) or '—'
                
                lines.append(f'| `{obj["name"]}` | {syn} | {code_len} | {desc_len} | {hier} | {owners} | {attrs_str} | {tabs_str} | {modules_str} | {forms_str} |')
                
                # Если есть табличные части — покажем их состав
                for tab in tabs:
                    tab_syn = tab.get('synonym', '')
                    tab_attrs = tab.get('attributes', [])
                    if tab_attrs:
                        tab_attrs_str = ', '.join(f'{a["name"]} ({a["data_type"]})' for a in tab_attrs[:5])
                        if len(tab_attrs) > 5:
                            tab_attrs_str += f' (+{len(tab_attrs)-5})'
                        lines.append(f'   ↳ ТЧ **{tab["name"]}** ({tab_syn}): {tab_attrs_str}')
        
        elif type_singular == 'Document':
            lines.append('| Имя | Синоним | Тип номера | Реквизиты (с типами) | Табличные части | Модули | Формы |')
            lines.append('|-----|---------|------------|----------------------|-----------------|--------|-------|')
            for obj in sorted_objs:
                attrs = [f for f in obj['fields'] if f['type'] == 'Attribute']
                tabs = [f for f in obj['fields'] if f['type'] == 'TabularSection']
                
                def fmt_attrs_with_types(items, n=5):
                    if not items:
                        return '—'
                    out_list = []
                    for it in items[:n]:
                        name = it['name']
                        dt = it.get('data_type', '')
                        if dt:
                            out_list.append(f'{name} ({dt})')
                        else:
                            out_list.append(name)
                    out = ', '.join(out_list)
                    if len(items) > n:
                        out += f' (+{len(items)-n})'
                    return out
                
                modules_str = short_list(obj['modules']) if obj['modules'] else '—'
                forms_str = short_list(obj['forms'], 3) if obj['forms'] else '—'
                attrs_str = fmt_attrs_with_types(attrs)
                tabs_str = short_list([t['name'] for t in tabs], 3)
                
                syn = obj.get('synonym', '').replace('|', '\\|')
                num_type = obj.get('number_type', '—')
                
                lines.append(f'| `{obj["name"]}` | {syn} | {num_type} | {attrs_str} | {tabs_str} | {modules_str} | {forms_str} |')
                
                for tab in tabs:
                    tab_syn = tab.get('synonym', '')
                    tab_attrs = tab.get('attributes', [])
                    if tab_attrs:
                        tab_attrs_str = ', '.join(f'{a["name"]} ({a["data_type"]})' for a in tab_attrs[:5])
                        if len(tab_attrs) > 5:
                            tab_attrs_str += f' (+{len(tab_attrs)-5})'
                        lines.append(f'   ↳ ТЧ **{tab["name"]}** ({tab_syn}): {tab_attrs_str}')
        
        elif type_singular == 'Enum':
            lines.append('| Имя | Синоним | Значения |')
            lines.append('|-----|---------|----------|')
            for obj in sorted_objs:
                vals = obj['predefined']
                vals_str = ', '.join(vals[:10])
                if len(vals) > 10:
                    vals_str += f' (+{len(vals)-10})'
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} | {vals_str or "—"} |')
        
        elif type_singular == 'CommonModule':
            lines.append('| Имя | Синоним |')
            lines.append('|-----|---------|')
            for obj in sorted_objs:
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} |')
        
        elif type_singular in ('Report', 'DataProcessor'):
            lines.append('| Имя | Синоним | Модули | Формы | Макеты |')
            lines.append('|-----|---------|--------|-------|--------|')
            for obj in sorted_objs:
                modules_str = short_list(obj['modules']) if obj['modules'] else '—'
                forms_str = short_list(obj['forms'], 3) if obj['forms'] else '—'
                templates_str = short_list(obj['templates'], 2) if obj['templates'] else '—'
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} | {modules_str} | {forms_str} | {templates_str} |')
        
        elif type_singular == 'Constant':
            lines.append('| Имя | Синоним |')
            lines.append('|-----|---------|')
            for obj in sorted_objs:
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} |')
        
        elif type_singular == 'CommonForm':
            lines.append('| Имя | Синоним |')
            lines.append('|-----|---------|')
            for obj in sorted_objs:
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} |')
        
        elif type_singular == 'CommonTemplate':
            lines.append('| Имя | Синоним |')
            lines.append('|-----|---------|')
            for obj in sorted_objs:
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} |')
        
        elif type_singular == 'Subsystem':
            lines.append('| Имя |')
            lines.append('|-----|')
            for obj in sorted_objs:
                lines.append(f'| `{obj["name"]}` |')
        
        else:
            lines.append('| Имя | Синоним | Модули | Формы |')
            lines.append('|-----|---------|--------|-------|')
            for obj in sorted_objs:
                modules_str = short_list(obj['modules']) if obj['modules'] else '—'
                forms_str = short_list(obj['forms'], 3) if obj['forms'] else '—'
                syn = obj.get('synonym', '').replace('|', '\\|')
                lines.append(f'| `{obj["name"]}` | {syn} | {modules_str} | {forms_str} |')
        
        lines.append('')
    
    lines.append('---')
    lines.append('')
    
    # 5. Структура директории
    lines.append('## 5. Структура выгрузки конфигурации')
    lines.append('')
    lines.append('```')
    lines.append(f'{config_dir}/')
    
    # Перечислить директории
    subdirs = sorted([d for d in os.listdir(config_dir)
                     if os.path.isdir(os.path.join(config_dir, d)) and not d.startswith('.')])
    for d in subdirs:
        d_path = os.path.join(config_dir, d)
        file_count = sum(1 for f in os.listdir(d_path)
                        if os.path.isfile(os.path.join(d_path, f)))
        lines.append(f'├── {d}/ ({file_count} файлов)')
    
    # Корневые XML
    if os.path.exists(configuration_path):
        lines.append(f'├── Configuration.xml ({os.path.getsize(configuration_path) // 1024} КБ)')
    if os.path.exists(dumpinfo_path):
        lines.append(f'└── ConfigDumpInfo.xml ({os.path.getsize(dumpinfo_path) // 1024} КБ)')
    lines.append('```')
    lines.append('')
    
    # 6. Как пользоваться
    lines.append('## 6. Как пользоваться индексом')
    lines.append('')
    lines.append('1. **Поиск объекта** — `Ctrl+F` по имени объекта')
    lines.append('2. **Уточнение деталей** — для каждого объекта можно открыть его .xml файл ')
    lines.append('   в соответствующей директории (например, `Catalogs/Номенклатура.xml`)')
    lines.append('3. **Чтение кода модулей** — `.bsl` файлы в поддиректориях объектов')
    lines.append('   (например, `Catalogs/Номенклатура/Ext/ManagerModule.bsl`)')
    lines.append('')
    lines.append('## 7. Ограничения')
    lines.append('')
    if has_xml_files:
        lines.append('Эта выгрузка — **полная** (в файлы), поэтому включает:')
        lines.append('- ✅ Свойства конфигурации')
        lines.append('- ✅ Метаданные всех объектов (реквизиты, типы данных)')
        lines.append('- ✅ Синонимы объектов')
        lines.append('- ✅ Состав форм, макетов, команд')
        lines.append('- ✅ Исходный код модулей (.bsl файлы)')
        lines.append('- ✅ Описания форм (в .xml файлах форм)')
    else:
        lines.append('Эта выгрузка — **сокращённая** (только Configuration.xml + ConfigDumpInfo.xml):')
        lines.append('- ✅ Свойства конфигурации')
        lines.append('- ✅ Метаданные объектов (имена, состав)')
        lines.append('- ❌ Типы данных реквизитов')
        lines.append('- ❌ Синонимы объектов')
        lines.append('- ❌ Содержимое модулей и форм')
    
    with open(output_index, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f'Index saved: {output_index}')
    print(f'Index size: {os.path.getsize(output_index) / 1024:.1f} KB')
    
    return cfg_props, subsystems, objects, total


def main():
    if len(sys.argv) < 4:
        print('Usage: python3 build_config_index_generic.py <config_dir> <output_index> <config_name>')
        print()
        print('Example:')
        print('  python3 build_config_index_generic.py /home/z/my-project/config-priemka \\')
        print('       /home/z/my-project/config-priemka-index.md "Приемка товаров"')
        sys.exit(1)
    
    config_dir = sys.argv[1]
    output_index = sys.argv[2]
    config_name = sys.argv[3]
    
    build_index(config_dir, output_index, config_name)


if __name__ == '__main__':
    main()
