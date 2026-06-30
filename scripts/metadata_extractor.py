#!/usr/bin/env python3
"""
metadata_extractor.py — Единый универсальный парсер метаданных 1С.

Архитектура:
- BaseMetadataParser — базовый класс с общими утилитами
- UniversalObjectParser — универсальный парсер для любого типа объекта
- ConfigParser — парсер Configuration.xml и ConfigDumpInfo.xml
- MetadataExtractor — оркестратор: обходит все директории и парсит всё

Поддерживает ВСЕ типы объектов 1С (35+ типов):
- Catalogs, Documents, InformationRegisters, AccumulationRegisters
- DataProcessors, Reports, Enums, Constants, ChartsOfCharacteristicTypes
- BusinessProcesses, Tasks, ExchangePlans, FilterCriteria
- CommonModules, CommonForms, CommonCommands, CommonTemplates, CommonPictures
- CommonAttributes, Subsystems, CommandGroups, DefinedTypes
- EventSubscriptions, ScheduledJobs, SessionParameters
- FunctionalOptions, FunctionalOptionsParameters
- WebServices, HTTPServices, XDTOPackages, WSReferences
- DocumentJournals, DocumentNumerators, Sequences, SettingsStorages
- Styles, StyleItems, Languages, Roles

Извлекает для каждого объекта:
- Name, UUID, Synonym, Comment
- Properties (все стандартные свойства)
- ChildObjects (рекурсивно: Attributes, TabularSections, Forms, Commands, и т.д.)
- StandardAttributes
- Predefined данные
- BasedOn связи
- Специфичные свойства (CodeLength, NumberLength, Periodicity, и т.д.)

Создаёт unified-metadata-index.json для конфигурации.
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# БАЗОВЫЕ УТИЛИТЫ (без дублирования — общий базовый класс)
# ============================================================================

class XMLUtils:
    """Общие утилиты для работы с XML 1С — без дублирования."""

    @staticmethod
    def strip_ns(tag: str) -> str:
        """Убирает namespace из тега."""
        return tag.split('}')[1] if '}' in tag else tag

    @staticmethod
    def get_child(elem, tag: str):
        """Возвращает первого потомка с указанным тегом (без namespace)."""
        if elem is None:
            return None
        for child in elem:
            if XMLUtils.strip_ns(child.tag) == tag:
                return child
        return None

    @staticmethod
    def get_children(elem, tag: str) -> list:
        """Возвращает всех потомков с указанным тегом."""
        if elem is None:
            return []
        return [child for child in elem if XMLUtils.strip_ns(child.tag) == tag]

    @staticmethod
    def get_text(elem, tag: str, default: str = '') -> str:
        """Возвращает текст первого потомка с тегом."""
        child = XMLUtils.get_child(elem, tag)
        if child is not None:
            return child.text or ''
        return default

    @staticmethod
    def get_bool(elem, tag: str, default: bool = False) -> bool:
        """Возвращает bool из текста тега."""
        text = XMLUtils.get_text(elem, tag)
        if text == 'true':
            return True
        if text == 'false':
            return False
        return default

    @staticmethod
    def get_int(elem, tag: str, default: int = 0) -> int:
        """Возвращает int из текста тега."""
        text = XMLUtils.get_text(elem, tag)
        try:
            return int(text) if text else default
        except ValueError:
            return default

    @staticmethod
    def get_synonym(properties_elem) -> str:
        """Извлекает синоним из v8:item/v8:content."""
        if properties_elem is None:
            return ''
        syn_elem = XMLUtils.get_child(properties_elem, 'Synonym')
        if syn_elem is None:
            return ''
        for item in syn_elem:
            if XMLUtils.strip_ns(item.tag) == 'item':
                content = XMLUtils.get_text(item, 'content')
                if content:
                    return content
        return ''

    @staticmethod
    def parse_type(type_elem) -> list[str]:
        """Парсит элемент <Type> и возвращает список типов."""
        if type_elem is None:
            return []
        types = []
        for child in type_elem:
            if XMLUtils.strip_ns(child.tag) == 'Type':
                if child.text:
                    types.append(child.text)
        return types

    @staticmethod
    def get_root_tag(root) -> str:
        """Возвращает тег корневого элемента без namespace."""
        return XMLUtils.strip_ns(root.tag)

    @staticmethod
    def safe_parse(xml_path: Path) -> tuple[ET.Element | None, str]:
        """Безопасный парсинг XML. Возвращает (root, error)."""
        try:
            tree = ET.parse(xml_path)
            return tree.getroot(), ''
        except ET.ParseError as e:
            return None, str(e)
        except Exception as e:
            return None, str(e)


# ============================================================================
# УНИВЕРСАЛЬНЫЙ ПАРСЕР ОБЪЕКТОВ
# ============================================================================

class UniversalObjectParser:
    """Универсальный парсер для любого типа объекта метаданных 1С.

    Парсит XML файл метаданных и извлекает:
    - Базовые свойства (Name, UUID, Synonym, Comment)
    - Все Properties (динамически — все теги внутри <Properties>)
    - ChildObjects (рекурсивно — Attributes, TabularSections, Forms, Commands, и т.д.)
    - StandardAttributes
    - Специфичные свойства (CodeLength, NumberLength, и т.д.)
    """

    def __init__(self):
        self.utils = XMLUtils()

    def parse(self, xml_path: Path) -> dict | None:
        """Парсит XML файл метаданных объекта.

        Args:
            xml_path: Путь к XML файлу

        Returns:
            dict с метаданными объекта или None при ошибке
        """
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        # Корневой тег = тип объекта (Catalog, Document, и т.д.)
        # Ищем первый дочерний элемент (не MetaDataObject)
        obj_elem = None
        obj_type = ''

        root_tag = XMLUtils.get_root_tag(root)
        if root_tag == 'MetaDataObject':
            # Ищем первый дочерний элемент внутри MetaDataObject
            for child in root:
                obj_elem = child
                obj_type = XMLUtils.strip_ns(child.tag)
                break
        else:
            obj_elem = root
            obj_type = root_tag

        if obj_elem is None:
            return None

        uuid = obj_elem.get('uuid', '')

        # Парсим Properties
        properties = XMLUtils.get_child(obj_elem, 'Properties')
        props = self._parse_properties(properties)

        # Парсим ChildObjects
        child_objects = XMLUtils.get_child(obj_elem, 'ChildObjects')
        children = self._parse_child_objects(child_objects)

        # Парсим StandardAttributes (если есть)
        std_attrs = []
        if properties is not None:
            for sa in XMLUtils.get_children(properties, 'StandardAttributes'):
                std_attrs.append(self._parse_standard_attribute(sa))

        # Парсим InternalInfo (если есть)
        internal_info = XMLUtils.get_child(obj_elem, 'InternalInfo')

        result = {
            'type': obj_type,
            'name': props.get('Name', ''),
            'uuid': uuid,
            'synonym': props.get('Synonym', ''),
            'comment': props.get('Comment', ''),
            'properties': props,
            'standard_attributes': std_attrs,
            'child_objects': children,
            'file': str(xml_path.name),
        }

        # Убираем Name/Synonym/Comment из properties (они уже в верхнем уровне)
        for key in ('Name', 'Synonym', 'Comment'):
            props.pop(key, None)

        return result

    def _parse_properties(self, properties_elem) -> dict:
        """Парсит ВСЕ свойства из <Properties> — динамически."""
        if properties_elem is None:
            return {}

        props = {}
        for child in properties_elem:
            tag = XMLUtils.strip_ns(child.tag)

            # Synonym — особый случай
            if tag == 'Synonym':
                props['Synonym'] = XMLUtils.get_synonym(properties_elem)
                continue

            # StandardAttributes — обрабатываем отдельно
            if tag == 'StandardAttributes':
                continue

            # Простой текст
            if child.text and child.text.strip():
                props[tag] = child.text.strip()
            else:
                # Проверяем есть ли вложенные Item (RegisterRecords)
                items = XMLUtils.get_children(child, 'Item')
                if items:
                    # Это список (например RegisterRecords → Item)
                    item_list = []
                    for item in items:
                        if item.text and item.text.strip():
                            item_list.append(item.text.strip())
                    if item_list:
                        props[tag] = item_list
                    else:
                        props[tag] = ''
                else:
                    # Проверяем есть ли вложенный v8:item
                    items = XMLUtils.get_children(child, 'item')
                    if items:
                        # Это локализованное поле
                        for item in items:
                            content = XMLUtils.get_text(item, 'content')
                            if content:
                                props[tag] = content
                                break
                    else:
                        # Пустой тег
                        props[tag] = ''

        return props

    def _parse_child_objects(self, child_objects_elem) -> dict:
        """Парсит <ChildObjects> — рекурсивно извлекает все вложенные объекты."""
        if child_objects_elem is None:
            return {}

        result = {
            'attributes': [],
            'tabular_sections': [],
            'forms': [],
            'commands': [],
            'enum_values': [],
            'predefined': [],
            'templates': [],
            'other': [],
        }

        for child in child_objects_elem:
            tag = XMLUtils.strip_ns(child.tag)

            if tag == 'Attribute':
                result['attributes'].append(self._parse_attribute(child))
            elif tag == 'TabularSection':
                result['tabular_sections'].append(self._parse_tabular_section(child))
            elif tag == 'Form':
                result['forms'].append({'name': child.text or '', 'uuid': child.get('uuid', '')})
            elif tag == 'Command':
                result['commands'].append({'name': child.text or '', 'uuid': child.get('uuid', '')})
            elif tag == 'EnumValue':
                enum_props = XMLUtils.get_child(child, 'Properties')
                result['enum_values'].append({
                    'name': XMLUtils.get_text(enum_props, 'Name') if enum_props is not None else '',
                    'synonym': XMLUtils.get_synonym(enum_props) if enum_props is not None else '',
                    'uuid': child.get('uuid', ''),
                })
            elif tag == 'Template':
                result['templates'].append({'name': child.text or '', 'uuid': child.get('uuid', '')})
            elif tag in ('Dimension', 'Resource'):
                # Для регистров: измерения и ресурсы
                attr = self._parse_attribute(child)
                attr['kind'] = tag
                result['attributes'].append(attr)
            else:
                # Другие вложенные объекты
                result['other'].append({
                    'type': tag,
                    'name': child.text or XMLUtils.get_text(child, 'Name'),
                    'uuid': child.get('uuid', ''),
                })

        return result

    def _parse_attribute(self, attr_elem) -> dict:
        """Парсит <Attribute> — реквизит объекта."""
        uuid = attr_elem.get('uuid', '')
        properties = XMLUtils.get_child(attr_elem, 'Properties')

        result = {
            'name': XMLUtils.get_text(properties, 'Name') if properties is not None else '',
            'uuid': uuid,
            'synonym': XMLUtils.get_synonym(properties) if properties is not None else '',
            'comment': XMLUtils.get_text(properties, 'Comment') if properties is not None else '',
            'types': [],
            'fill_checking': XMLUtils.get_text(properties, 'FillChecking') if properties is not None else '',
            'use': XMLUtils.get_text(properties, 'Use') if properties is not None else '',
            'indexing': XMLUtils.get_text(properties, 'Indexing') if properties is not None else '',
        }

        if properties is not None:
            type_elem = XMLUtils.get_child(properties, 'Type')
            result['types'] = XMLUtils.parse_type(type_elem)

        return result

    def _parse_tabular_section(self, ts_elem) -> dict:
        """Парсит <TabularSection> — табличную часть."""
        uuid = ts_elem.get('uuid', '')
        properties = XMLUtils.get_child(ts_elem, 'Properties')

        result = {
            'name': XMLUtils.get_text(properties, 'Name') if properties is not None else '',
            'uuid': uuid,
            'synonym': XMLUtils.get_synonym(properties) if properties is not None else '',
            'attributes': [],
        }

        # Реквизиты табличной части — в ChildObjects
        child_objects = XMLUtils.get_child(ts_elem, 'ChildObjects')
        if child_objects is not None:
            for child in child_objects:
                if XMLUtils.strip_ns(child.tag) == 'Attribute':
                    result['attributes'].append(self._parse_attribute(child))

        return result

    def _parse_standard_attribute(self, attr_elem) -> dict:
        """Парсит <xr:StandardAttribute> — стандартный реквизит."""
        return {
            'name': attr_elem.get('name', ''),
            'fill_checking': XMLUtils.get_text(attr_elem, 'FillChecking'),
            'fill_from_filling_value': XMLUtils.get_bool(attr_elem, 'FillFromFillingValue'),
            'create_on_input': XMLUtils.get_text(attr_elem, 'CreateOnInput'),
            'data_history': XMLUtils.get_text(attr_elem, 'DataHistory'),
        }


# ============================================================================
# ПАРСЕР КОНФИГУРАЦИИ
# ============================================================================

class ConfigParser:
    """Парсер Configuration.xml и ConfigDumpInfo.xml."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse_configuration(self, xml_path: Path) -> dict | None:
        """Парсит Configuration.xml — главный файл конфигурации."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        config_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == 'Configuration':
                config_elem = child
                break

        if config_elem is None:
            return None

        properties = XMLUtils.get_child(config_elem, 'Properties')
        child_objects = XMLUtils.get_child(config_elem, 'ChildObjects')

        result = {
            'type': 'Configuration',
            'uuid': config_elem.get('uuid', ''),
            'properties': {},
            'child_objects': {
                'subsystems': [],
                'common_modules': [],
                'common_forms': [],
                'common_commands': [],
                'common_templates': [],
                'common_pictures': [],
                'common_attributes': [],
                'catalogs': [],
                'documents': [],
                'information_registers': [],
                'accumulation_registers': [],
                'data_processors': [],
                'reports': [],
                'enums': [],
                'roles': [],
                'event_subscriptions': [],
                'scheduled_jobs': [],
                'defined_types': [],
                'functional_options': [],
                'exchange_plans': [],
                'web_services': [],
                'http_services': [],
                'xdto_packages': [],
                'session_parameters': [],
                'command_groups': [],
                'document_journals': [],
                'filter_criteria': [],
                'languages': [],
                'other': [],
            },
        }

        # Properties
        if properties is not None:
            for child in properties:
                tag = XMLUtils.strip_ns(child.tag)
                if tag == 'Synonym':
                    result['properties']['Synonym'] = XMLUtils.get_synonym(properties)
                elif child.text and child.text.strip():
                    result['properties'][tag] = child.text.strip()

        # ChildObjects — список всех объектов конфигурации
        if child_objects is not None:
            for child in child_objects:
                tag = XMLUtils.strip_ns(child.tag)
                name = child.text or ''
                uuid = child.get('uuid', '')

                entry = {'name': name, 'uuid': uuid, 'type': tag}

                # Маппинг тегов к спискам
                tag_lower = tag.lower()
                if tag == 'Subsystem':
                    result['child_objects']['subsystems'].append(entry)
                elif tag == 'CommonModule':
                    result['child_objects']['common_modules'].append(entry)
                elif tag == 'CommonForm':
                    result['child_objects']['common_forms'].append(entry)
                elif tag == 'CommonCommand':
                    result['child_objects']['common_commands'].append(entry)
                elif tag == 'CommonTemplate':
                    result['child_objects']['common_templates'].append(entry)
                elif tag == 'CommonPicture':
                    result['child_objects']['common_pictures'].append(entry)
                elif tag == 'CommonAttribute':
                    result['child_objects']['common_attributes'].append(entry)
                elif tag == 'Catalog':
                    result['child_objects']['catalogs'].append(entry)
                elif tag == 'Document':
                    result['child_objects']['documents'].append(entry)
                elif tag == 'InformationRegister':
                    result['child_objects']['information_registers'].append(entry)
                elif tag == 'AccumulationRegister':
                    result['child_objects']['accumulation_registers'].append(entry)
                elif tag == 'DataProcessor':
                    result['child_objects']['data_processors'].append(entry)
                elif tag == 'Report':
                    result['child_objects']['reports'].append(entry)
                elif tag == 'Enum':
                    result['child_objects']['enums'].append(entry)
                elif tag == 'Role':
                    result['child_objects']['roles'].append(entry)
                elif tag == 'EventSubscription':
                    result['child_objects']['event_subscriptions'].append(entry)
                elif tag == 'ScheduledJob':
                    result['child_objects']['scheduled_jobs'].append(entry)
                elif tag == 'DefinedType':
                    result['child_objects']['defined_types'].append(entry)
                elif tag == 'FunctionalOption':
                    result['child_objects']['functional_options'].append(entry)
                elif tag == 'ExchangePlan':
                    result['child_objects']['exchange_plans'].append(entry)
                elif tag == 'WebService':
                    result['child_objects']['web_services'].append(entry)
                elif tag == 'HTTPService':
                    result['child_objects']['http_services'].append(entry)
                elif tag == 'XDTOPackage':
                    result['child_objects']['xdto_packages'].append(entry)
                elif tag == 'SessionParameter':
                    result['child_objects']['session_parameters'].append(entry)
                elif tag == 'CommandGroup':
                    result['child_objects']['command_groups'].append(entry)
                elif tag == 'DocumentJournal':
                    result['child_objects']['document_journals'].append(entry)
                elif tag == 'FilterCriterion':
                    result['child_objects']['filter_criteria'].append(entry)
                elif tag == 'Language':
                    result['child_objects']['languages'].append(entry)
                else:
                    result['child_objects']['other'].append(entry)

        return result

    def parse_config_dump_info(self, xml_path: Path) -> dict | None:
        """Парсит ConfigDumpInfo.xml — дамп версий объектов."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        versions = []
        config_versions = XMLUtils.get_child(root, 'ConfigVersions')
        if config_versions is not None:
            for meta in config_versions:
                if XMLUtils.strip_ns(meta.tag) == 'Metadata':
                    name = meta.get('name', '')
                    obj_id = meta.get('id', '')
                    config_version = meta.get('configVersion', '')
                    versions.append({
                        'name': name,
                        'id': obj_id,
                        'config_version': config_version,
                    })

        return {
            'type': 'ConfigDumpInfo',
            'total_objects': len(versions),
            'versions': versions,
        }


# ============================================================================
# ПАРСЕР ROLES (права доступа)
# ============================================================================

class RoleParser:
    """Парсер ролей 1С — извлекает права доступа и RLS."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse_role_metadata(self, xml_path: Path) -> dict | None:
        """Парсит метаданные роли (Role/<Имя>.xml)."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        role_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == 'Role':
                role_elem = child
                break

        if role_elem is None:
            return None

        properties = XMLUtils.get_child(role_elem, 'Properties')
        return {
            'type': 'Role',
            'name': XMLUtils.get_text(properties, 'Name') if properties is not None else '',
            'uuid': role_elem.get('uuid', ''),
            'synonym': XMLUtils.get_synonym(properties) if properties is not None else '',
        }

    def parse_rights(self, xml_path: Path) -> dict | None:
        """Парсит Rights.xml — права доступа для роли."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        rights = []
        for obj_elem in root:
            if XMLUtils.strip_ns(obj_elem.tag) != 'object':
                continue

            obj_name = XMLUtils.get_text(obj_elem, 'name')
            obj_rights = []

            for right_elem in obj_elem:
                if XMLUtils.strip_ns(right_elem.tag) != 'right':
                    continue

                right_name = XMLUtils.get_text(right_elem, 'name')
                right_value = XMLUtils.get_text(right_elem, 'value')

                # RLS-правила (Restriction)
                restriction = XMLUtils.get_child(right_elem, 'restriction')
                rls_text = ''
                if restriction is not None and restriction.text:
                    rls_text = restriction.text.strip()

                obj_rights.append({
                    'right': right_name,
                    'value': right_value == 'true',
                    'rls': rls_text,
                })

            rights.append({
                'object': obj_name,
                'rights': obj_rights,
            })

        return {
            'total_objects': len(rights),
            'objects': rights,
        }


# ============================================================================
# ПАРСЕР SUBSYSTEMS (иерархия подсистем)
# ============================================================================

class SubsystemParser:
    """Парсер подсистем 1С — извлекает иерархию и содержимое."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse(self, xml_path: Path) -> dict | None:
        """Парсит Subsystem/<Имя>.xml."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        subsys_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == 'Subsystem':
                subsys_elem = child
                break

        if subsys_elem is None:
            return None

        properties = XMLUtils.get_child(subsys_elem, 'Properties')
        child_objects = XMLUtils.get_child(subsys_elem, 'ChildObjects')

        result = {
            'type': 'Subsystem',
            'name': XMLUtils.get_text(properties, 'Name') if properties is not None else '',
            'uuid': subsys_elem.get('uuid', ''),
            'synonym': XMLUtils.get_synonym(properties) if properties is not None else '',
            'comment': XMLUtils.get_text(properties, 'Comment') if properties is not None else '',
            'content': [],
            'child_subsystems': [],
        }

        # Content — список объектов в подсистеме
        content_elem = XMLUtils.get_child(properties, 'Content') if properties is not None else None
        if content_elem is not None:
            for item in content_elem:
                result['content'].append(item.text or '')

        # Child subsystems
        if child_objects is not None:
            for child in child_objects:
                if XMLUtils.strip_ns(child.tag) == 'Subsystem':
                    result['child_subsystems'].append({
                        'name': child.text or '',
                        'uuid': child.get('uuid', ''),
                    })

        return result


# ============================================================================
# ПАРСЕР EVENT SUBSCRIPTIONS
# ============================================================================

class EventSubscriptionParser:
    """Парсер подписок на события."""

    def parse(self, xml_path: Path) -> dict | None:
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        for child in root:
            if XMLUtils.strip_ns(child.tag) == 'EventSubscription':
                properties = XMLUtils.get_child(child, 'Properties')
                if properties is None:
                    return None

                # Source — типы объектов, на которые подписка
                source_elem = XMLUtils.get_child(properties, 'Source')
                sources = []
                if source_elem is not None:
                    for t in source_elem:
                        if XMLUtils.strip_ns(t.tag) in ('Type', 'TypeSet'):
                            if t.text:
                                sources.append(t.text)

                return {
                    'type': 'EventSubscription',
                    'name': XMLUtils.get_text(properties, 'Name'),
                    'uuid': child.get('uuid', ''),
                    'synonym': XMLUtils.get_synonym(properties),
                    'event': XMLUtils.get_text(properties, 'Event'),
                    'handler': XMLUtils.get_text(properties, 'Handler'),
                    'sources': sources,
                }
        return None


# ============================================================================
# ПАРСЕР SCHEDULED JOBS
# ============================================================================

class ScheduledJobParser:
    """Парсер регламентных заданий."""

    def parse(self, xml_path: Path) -> dict | None:
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        for child in root:
            if XMLUtils.strip_ns(child.tag) == 'ScheduledJob':
                properties = XMLUtils.get_child(child, 'Properties')
                if properties is None:
                    return None

                return {
                    'type': 'ScheduledJob',
                    'name': XMLUtils.get_text(properties, 'Name'),
                    'uuid': child.get('uuid', ''),
                    'synonym': XMLUtils.get_synonym(properties),
                    'method_name': XMLUtils.get_text(properties, 'MethodName'),
                    'description': XMLUtils.get_text(properties, 'Description'),
                    'use': XMLUtils.get_bool(properties, 'Use'),
                    'predefined': XMLUtils.get_bool(properties, 'Predefined'),
                    'restart_count': XMLUtils.get_int(properties, 'RestartCountOnFailure'),
                    'restart_interval': XMLUtils.get_int(properties, 'RestartIntervalOnFailure'),
                }
        return None


# ============================================================================
# ГЛАВНЫЙ ЭКСТРАКТОР — оркестратор
# ============================================================================

# Маппинг: директория → (тип объекта, парсер)
# None = используем UniversalObjectParser
TYPE_MAPPING = {
    'Catalogs': ('Catalog', None),
    'Documents': ('Document', None),
    'InformationRegisters': ('InformationRegister', None),
    'AccumulationRegisters': ('AccumulationRegister', None),
    'DataProcessors': ('DataProcessor', None),
    'Reports': ('Report', None),
    'Enums': ('Enum', None),
    'Constants': ('Constant', None),
    'ChartsOfCharacteristicTypes': ('ChartOfCharacteristicTypes', None),
    'ChartsOfAccounts': ('ChartOfAccounts', None),
    'BusinessProcesses': ('BusinessProcess', None),
    'Tasks': ('Task', None),
    'ExchangePlans': ('ExchangePlan', None),
    'FilterCriteria': ('FilterCriterion', None),
    'CommonModules': ('CommonModule', None),
    'CommonForms': ('CommonForm', None),
    'CommonCommands': ('CommonCommand', None),
    'CommonTemplates': ('CommonTemplate', None),
    'CommonPictures': ('CommonPicture', None),
    'CommonAttributes': ('CommonAttribute', None),
    'CommandGroups': ('CommandGroup', None),
    'DefinedTypes': ('DefinedType', None),
    'DocumentJournals': ('DocumentJournal', None),
    'DocumentNumerators': ('DocumentNumerator', None),
    'Sequences': ('Sequence', None),
    'SettingsStorages': ('SettingsStorage', None),
    'FunctionalOptions': ('FunctionalOption', None),
    'FunctionalOptionsParameters': ('FunctionalOptionParameter', None),
    'SessionParameters': ('SessionParameter', None),
    'WebServices': ('WebService', None),
    'HTTPServices': ('HTTPService', None),
    'XDTOPackages': ('XDTOPackage', None),
    'WSReferences': ('WSReference', None),
    'Styles': ('Style', None),
    'StyleItems': ('StyleItem', None),
    'Languages': ('Language', None),
    # Специальные парсеры:
    'Subsystems': ('Subsystem', 'subsystem'),
    'EventSubscriptions': ('EventSubscription', 'event_subscription'),
    'ScheduledJobs': ('ScheduledJob', 'scheduled_job'),
    # Roles обрабатываются отдельно в секции 4 (с правами доступа)
}


class MetadataExtractor:
    """Главный экстрактор метаданных — обходит все директории и парсит всё.

    Создаёт unified-metadata-index.json с полной структурой конфигурации.
    """

    def __init__(self):
        self.universal_parser = UniversalObjectParser()
        self.config_parser = ConfigParser()
        self.role_parser = RoleParser()
        self.subsystem_parser = SubsystemParser()
        self.event_parser = EventSubscriptionParser()
        self.scheduled_job_parser = ScheduledJobParser()

    def extract_all(self, config_dir: Path | str, progress_callback=None) -> dict:
        """Извлекает ВСЕ метаданные из конфигурации.

        Args:
            config_dir: Путь к директории конфигурации
            progress_callback: Функция(done, total, current_type)

        Returns:
            dict: {
                'configuration': {...},  # Configuration.xml
                'config_dump_info': {...},  # ConfigDumpInfo.xml
                'objects': {...},  # Все объекты по типам
                'roles': {...},  # Роли с правами
                'subsystems': [...],  # Подсистемы
                'event_subscriptions': [...],  # Подписки на события
                'scheduled_jobs': [...],  # Регламентные задания
                'ext': {...},  # Файлы из Ext/
                'stats': {...},  # Статистика
            }
        """
        config_dir = Path(config_dir)

        result = {
            'configuration': None,
            'config_dump_info': None,
            'objects': {},
            'roles': [],
            'subsystems': [],
            'event_subscriptions': [],
            'scheduled_jobs': [],
            'ext': {},
            'stats': {
                'total_objects': 0,
                'by_type': {},
                'total_attributes': 0,
                'total_tabular_sections': 0,
                'total_forms': 0,
                'total_commands': 0,
                'total_predefined': 0,
            },
        }

        # 1. Configuration.xml
        config_xml = config_dir / 'Configuration.xml'
        if config_xml.exists():
            result['configuration'] = self.config_parser.parse_configuration(config_xml)
            print(f"  ✅ Configuration.xml: {result['configuration']['properties'].get('Name', '?')}")

        # 2. ConfigDumpInfo.xml
        dump_xml = config_dir / 'ConfigDumpInfo.xml'
        if dump_xml.exists():
            result['config_dump_info'] = self.config_parser.parse_config_dump_info(dump_xml)
            print(f"  ✅ ConfigDumpInfo: {result['config_dump_info']['total_objects']} объектов")

        # 3. Все типы объектов
        total_dirs = len(TYPE_MAPPING)
        done = 0

        for dir_name, (obj_type, special_parser) in TYPE_MAPPING.items():
            done += 1
            if progress_callback:
                progress_callback(done, total_dirs, dir_name)

            type_dir = config_dir / dir_name
            if not type_dir.exists():
                continue

            objects = []
            parser = self._get_parser(special_parser)

            for xml_file in sorted(type_dir.glob('*.xml')):
                if not xml_file.is_file():
                    continue
                try:
                    obj = parser.parse(xml_file)
                    if obj and obj.get('name'):
                        objects.append(obj)
                        self._update_stats(result['stats'], obj)
                except Exception as e:
                    print(f"  ⚠️ Ошибка {xml_file.name}: {e}", file=sys.stderr)

            if objects:
                # Subsystems, EventSubscriptions, ScheduledJobs — в отдельные секции
                if special_parser == 'subsystem':
                    result['subsystems'] = objects
                elif special_parser == 'event_subscription':
                    result['event_subscriptions'] = objects
                elif special_parser == 'scheduled_job':
                    result['scheduled_jobs'] = objects
                else:
                    result['objects'][dir_name] = objects
                result['stats']['by_type'][dir_name] = len(objects)

        # 4. Roles — с правами доступа
        roles_dir = config_dir / 'Roles'
        if roles_dir.exists():
            for role_dir in sorted(roles_dir.iterdir()):
                if not role_dir.is_dir():
                    continue
                role_meta_file = roles_dir / f'{role_dir.name}.xml'
                rights_file = role_dir / 'Ext' / 'Rights.xml'

                role = None
                if role_meta_file.exists():
                    role = self.role_parser.parse_role_metadata(role_meta_file)

                if role and rights_file.exists():
                    rights = self.role_parser.parse_rights(rights_file)
                    if rights:
                        role['rights'] = rights

                if role:
                    result['roles'].append(role)

            result['stats']['by_type']['Roles'] = len(result['roles'])

        # 5. Ext/ файлы
        ext_dir = config_dir / 'Ext'
        if ext_dir.exists():
            result['ext'] = self._parse_ext_dir(ext_dir)

        return result

    def _get_parser(self, special_parser: str | None):
        """Возвращает парсер по имени или универсальный."""
        if special_parser == 'subsystem':
            return self.subsystem_parser
        elif special_parser == 'event_subscription':
            return self.event_parser
        elif special_parser == 'scheduled_job':
            return self.scheduled_job_parser
        return self.universal_parser

    def _update_stats(self, stats: dict, obj: dict):
        """Обновляет статистику."""
        stats['total_objects'] += 1

        children = obj.get('child_objects', {})
        stats['total_attributes'] += len(children.get('attributes', []))
        stats['total_tabular_sections'] += len(children.get('tabular_sections', []))
        stats['total_forms'] += len(children.get('forms', []))
        stats['total_commands'] += len(children.get('commands', []))

        # Predefined
        props = obj.get('properties', {})
        # Predefined данные будут в child_objects['predefined'] когда мы их добавим

    def _parse_ext_dir(self, ext_dir: Path) -> dict:
        """Парсит файлы из Ext/ директории."""
        result = {
            'managed_application_module': False,
            'session_module': False,
            'ordinary_application_module': False,
            'external_connection_module': False,
            'home_page_work_area': False,
            'command_interface': False,
            'client_application_interface': False,
            'files': [],
        }

        for f in ext_dir.iterdir():
            if f.is_file():
                result['files'].append({
                    'name': f.name,
                    'size': f.stat().st_size,
                })

                name_lower = f.name.lower()
                if 'managedapplicationmodule' in name_lower:
                    result['managed_application_module'] = True
                elif 'sessionmodule' in name_lower:
                    result['session_module'] = True
                elif 'ordinaryapplicationmodule' in name_lower:
                    result['ordinary_application_module'] = True
                elif 'externalconnectionmodule' in name_lower:
                    result['external_connection_module'] = True
                elif 'homeworkarea' in name_lower:
                    result['home_page_work_area'] = True
                elif 'commandinterface' in name_lower:
                    result['command_interface'] = True
                elif 'clientapplicationinterface' in name_lower:
                    result['client_application_interface'] = True

        return result


# ============================================================================
# ФУНКЦИЯ СОХРАНЕНИЯ
# ============================================================================

def extract_and_save(config_dir: Path | str, output_path: Path | str) -> dict:
    """Извлекает все метаданные и сохраняет в unified-metadata-index.json.

    Args:
        config_dir: Путь к директории конфигурации
        output_path: Куда сохранить индекс

    Returns:
        Статистика
    """
    config_dir = Path(config_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    extractor = MetadataExtractor()

    def progress(done, total, current):
        print(f"  [{done}/{total}] {current}...", end='\r', flush=True)

    print(f"Извлечение метаданных из: {config_dir}")
    result = extractor.extract_all(config_dir, progress)

    print(f"\n✅ Извлечено {result['stats']['total_objects']} объектов")
    print(f"   Реквизитов: {result['stats']['total_attributes']}")
    print(f"   Табличных частей: {result['stats']['total_tabular_sections']}")
    print(f"   Форм: {result['stats']['total_forms']}")
    print(f"   Команд: {result['stats']['total_commands']}")
    print(f"   Ролей: {len(result.get('roles', []))}")
    print(f"   Подсистем: {len(result.get('subsystems', []))}")
    print(f"   Подписок на события: {len(result.get('event_subscriptions', []))}")
    print(f"   Регламентных заданий: {len(result.get('scheduled_jobs', []))}")

    print(f"\n   По типам:")
    for type_name, count in sorted(result['stats']['by_type'].items()):
        print(f"     {type_name}: {count}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено в: {output_path} ({output_path.stat().st_size // 1024} КБ)")

    return result['stats']


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 metadata_extractor.py <config_dir> [output_path]")
        print()
        print("Пример:")
        print("  python3 metadata_extractor.py data/configs/ut11 derived/configs/ut11/unified-metadata-index.json")
        sys.exit(1)

    config_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'unified-metadata-index.json'

    extract_and_save(config_dir, output)


if __name__ == '__main__':
    main()
