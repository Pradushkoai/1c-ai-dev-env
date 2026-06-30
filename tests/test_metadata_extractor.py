#!/usr/bin/env python3
"""Тесты для metadata_extractor.py — единого парсера метаданных 1С."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Добавляем scripts/ в path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from metadata_extractor import (
    XMLUtils, UniversalObjectParser, ConfigParser, RoleParser,
    SubsystemParser, EventSubscriptionParser, ScheduledJobParser,
    MetadataExtractor, TYPE_MAPPING,
)


# ============================================================================
# ТЕСТЫ XMLUtils
# ============================================================================

class TestXMLUtils:
    """Тесты утилит XML."""

    def test_strip_ns(self):
        assert XMLUtils.strip_ns('{http://v8.1c.ru/8.3/MDClasses}Catalog') == 'Catalog'
        assert XMLUtils.strip_ns('Catalog') == 'Catalog'
        assert XMLUtils.strip_ns('') == ''

    def test_get_child(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><Name>Test</Name><Other>Val</Other></root>')
        child = XMLUtils.get_child(root, 'Name')
        assert child is not None
        assert child.text == 'Test'

    def test_get_child_not_found(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><Name>Test</Name></root>')
        assert XMLUtils.get_child(root, 'Missing') is None

    def test_get_text(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><Name>Test</Name></root>')
        assert XMLUtils.get_text(root, 'Name') == 'Test'
        assert XMLUtils.get_text(root, 'Missing', 'default') == 'default'

    def test_get_bool(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><Flag>true</Flag></root>')
        assert XMLUtils.get_bool(root, 'Flag') is True
        root2 = ET.fromstring('<root><Flag>false</Flag></root>')
        assert XMLUtils.get_bool(root2, 'Flag') is False

    def test_get_int(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><Num>42</Num></root>')
        assert XMLUtils.get_int(root, 'Num') == 42

    def test_parse_type(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<Type><Type>xs:string</Type><Type>cfg:CatalogRef.Номенклатура</Type></Type>')
        types = XMLUtils.parse_type(root)
        assert len(types) == 2
        assert 'xs:string' in types
        assert 'cfg:CatalogRef.Номенклатура' in types

    def test_safe_parse_valid(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('<?xml version="1.0"?><root><child>test</child></root>')
            f.flush()
            root, error = XMLUtils.safe_parse(Path(f.name))
            assert root is not None
            assert error == ''
            os.unlink(f.name)

    def test_safe_parse_invalid(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('not xml')
            f.flush()
            root, error = XMLUtils.safe_parse(Path(f.name))
            assert root is None
            assert error != ''
            os.unlink(f.name)


# ============================================================================
# ТЕСТЫ UniversalObjectParser
# ============================================================================

class TestUniversalObjectParser:
    """Тесты универсального парсера объектов."""

    def setup_method(self):
        self.parser = UniversalObjectParser()

    def _create_xml(self, content: str) -> Path:
        """Создаёт временный XML файл."""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8')
        f.write(content)
        f.flush()
        return Path(f.name)

    def test_parse_catalog(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <Catalog uuid="12345678-1234-1234-1234-123456789012">
        <Properties>
            <Name>ТестовыйСправочник</Name>
            <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Тестовый справочник</v8:content></v8:item></Synonym>
            <Comment>Тест</Comment>
            <Hierarchical>false</Hierarchical>
            <CodeLength>11</CodeLength>
        </Properties>
        <ChildObjects>
            <Attribute uuid="aaa">
                <Properties>
                    <Name>Реквизит1</Name>
                    <Type><v8:Type>xs:string</v8:Type></Type>
                </Properties>
            </Attribute>
            <Form>ФормаЭлемента</Form>
        </ChildObjects>
    </Catalog>
</MetaDataObject>'''
        path = self._create_xml(xml)
        result = self.parser.parse(path)
        os.unlink(path)

        assert result is not None
        assert result['type'] == 'Catalog'
        assert result['name'] == 'ТестовыйСправочник'
        assert result['uuid'] == '12345678-1234-1234-1234-123456789012'
        assert result['synonym'] == 'Тестовый справочник'
        assert result['properties']['Hierarchical'] == 'false'
        assert result['properties']['CodeLength'] == '11'
        assert len(result['child_objects']['attributes']) == 1
        assert result['child_objects']['attributes'][0]['name'] == 'Реквизит1'
        assert result['child_objects']['attributes'][0]['types'] == ['xs:string']
        assert len(result['child_objects']['forms']) == 1
        assert result['child_objects']['forms'][0]['name'] == 'ФормаЭлемента'

    def test_parse_document(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <Document uuid="doc-uuid">
        <Properties>
            <Name>ТестовыйДокумент</Name>
            <NumberLength>11</NumberLength>
        </Properties>
        <ChildObjects>
            <TabularSection uuid="ts1">
                <Properties><Name>Товары</Name></Properties>
                <ChildObjects>
                    <Attribute uuid="attr1">
                        <Properties><Name>Номенклатура</Name></Properties>
                    </Attribute>
                </ChildObjects>
            </TabularSection>
        </ChildObjects>
    </Document>
</MetaDataObject>'''
        path = self._create_xml(xml)
        result = self.parser.parse(path)
        os.unlink(path)

        assert result['type'] == 'Document'
        assert result['name'] == 'ТестовыйДокумент'
        assert result['properties']['NumberLength'] == '11'
        assert len(result['child_objects']['tabular_sections']) == 1
        ts = result['child_objects']['tabular_sections'][0]
        assert ts['name'] == 'Товары'
        assert len(ts['attributes']) == 1
        assert ts['attributes'][0]['name'] == 'Номенклатура'

    def test_parse_enum(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <Enum uuid="enum-uuid">
        <Properties>
            <Name>СтатусыДокумента</Name>
        </Properties>
        <ChildObjects>
            <EnumValue uuid="v1"><Properties><Name>Создан</Name></Properties></EnumValue>
            <EnumValue uuid="v2"><Properties><Name>Проведен</Name></Properties></EnumValue>
        </ChildObjects>
    </Enum>
</MetaDataObject>'''
        path = self._create_xml(xml)
        result = self.parser.parse(path)
        os.unlink(path)

        assert result['type'] == 'Enum'
        assert len(result['child_objects']['enum_values']) == 2
        assert result['child_objects']['enum_values'][0]['name'] == 'Создан'

    def test_parse_invalid_xml(self):
        path = self._create_xml('not xml')
        result = self.parser.parse(path)
        os.unlink(path)
        assert result is None

    def test_parse_empty_file(self):
        path = self._create_xml('<?xml version="1.0"?><empty/>')
        result = self.parser.parse(path)
        os.unlink(path)
        # empty root — нет дочерних элементов
        assert result is None or 'type' in result


# ============================================================================
# ТЕСТЫ ConfigParser
# ============================================================================

class TestConfigParser:
    """Тесты парсера Configuration.xml."""

    def setup_method(self):
        self.parser = ConfigParser()

    def test_parse_configuration(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <Configuration uuid="config-uuid">
        <Properties>
            <Name>УправлениеТорговлей</Name>
            <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Управление торговлей</v8:content></v8:item></Synonym>
            <Version>11.3.4</Version>
            <Vendor>Тест</Vendor>
        </Properties>
        <ChildObjects>
            <Subsystem>Продажи</Subsystem>
            <Catalog>Номенклатура</Catalog>
            <Document>ЗаказКлиента</Document>
            <CommonModule>ОбщегоНазначения</CommonModule>
        </ChildObjects>
    </Configuration>
</MetaDataObject>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse_configuration(Path(f.name))
            os.unlink(f.name)

        assert result is not None
        assert result['type'] == 'Configuration'
        assert result['properties']['Name'] == 'УправлениеТорговлей'
        assert result['properties']['Version'] == '11.3.4'
        assert len(result['child_objects']['subsystems']) == 1
        assert len(result['child_objects']['catalogs']) == 1
        assert len(result['child_objects']['documents']) == 1
        assert len(result['child_objects']['common_modules']) == 1

    def test_parse_config_dump_info(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
    <ConfigVersions>
        <Metadata name="Catalog.Номенклатура" id="123" configVersion="abc"/>
        <Metadata name="Document.Заказ" id="456" configVersion="def"/>
    </ConfigVersions>
</ConfigDumpInfo>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse_config_dump_info(Path(f.name))
            os.unlink(f.name)

        assert result is not None
        assert result['total_objects'] == 2
        assert result['versions'][0]['name'] == 'Catalog.Номенклатура'


# ============================================================================
# ТЕСТЫ RoleParser
# ============================================================================

class TestRoleParser:
    """Тесты парсера ролей."""

    def setup_method(self):
        self.parser = RoleParser()

    def test_parse_role_metadata(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <Role uuid="role-uuid">
        <Properties>
            <Name>ПолныеПрава</Name>
            <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Полные права</v8:content></v8:item></Synonym>
        </Properties>
    </Role>
</MetaDataObject>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse_role_metadata(Path(f.name))
            os.unlink(f.name)

        assert result['name'] == 'ПолныеПрава'
        assert result['synonym'] == 'Полные права'

    def test_parse_rights(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles">
    <object>
        <name>Catalog.Номенклатура</name>
        <right><name>Read</name><value>true</value></right>
        <right><name>Update</name><value>false</value></right>
    </object>
</Rights>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse_rights(Path(f.name))
            os.unlink(f.name)

        assert result['total_objects'] == 1
        obj = result['objects'][0]
        assert obj['object'] == 'Catalog.Номенклатура'
        assert obj['rights'][0]['right'] == 'Read'
        assert obj['rights'][0]['value'] is True
        assert obj['rights'][1]['right'] == 'Update'
        assert obj['rights'][1]['value'] is False


# ============================================================================
# ТЕСТЫ EventSubscriptionParser
# ============================================================================

class TestEventSubscriptionParser:
    """Тесты парсера подписок на события."""

    def setup_method(self):
        self.parser = EventSubscriptionParser()

    def test_parse(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <EventSubscription uuid="es-uuid">
        <Properties>
            <Name>ОбработкаЗаписи</Name>
            <Event>BeforeWrite</Event>
            <Handler>CommonModule.Обработчики.ПередЗаписью</Handler>
            <Source>
                <v8:TypeSet>cfg:DocumentObject</v8:TypeSet>
            </Source>
        </Properties>
    </EventSubscription>
</MetaDataObject>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse(Path(f.name))
            os.unlink(f.name)

        assert result['name'] == 'ОбработкаЗаписи'
        assert result['event'] == 'BeforeWrite'
        assert result['handler'] == 'CommonModule.Обработчики.ПередЗаписью'
        assert len(result['sources']) == 1


# ============================================================================
# ТЕСТЫ ScheduledJobParser
# ============================================================================

class TestScheduledJobParser:
    """Тесты парсера регламентных заданий."""

    def setup_method(self):
        self.parser = ScheduledJobParser()

    def test_parse(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
    <ScheduledJob uuid="sj-uuid">
        <Properties>
            <Name>НочноеОбновление</Name>
            <MethodName>CommonModule.Обновление.Выполнить</MethodName>
            <Use>true</Use>
            <RestartCountOnFailure>3</RestartCountOnFailure>
        </Properties>
    </ScheduledJob>
</MetaDataObject>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse(Path(f.name))
            os.unlink(f.name)

        assert result['name'] == 'НочноеОбновление'
        assert result['method_name'] == 'CommonModule.Обновление.Выполнить'
        assert result['use'] is True
        assert result['restart_count'] == 3


# ============================================================================
# ТЕСТЫ SubsystemParser
# ============================================================================

class TestSubsystemParser:
    """Тесты парсера подсистем."""

    def setup_method(self):
        self.parser = SubsystemParser()

    def test_parse(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">
    <Subsystem uuid="ss-uuid">
        <Properties>
            <Name>Продажи</Name>
            <Content>
                <xr:Item>Catalog.Контрагенты</xr:Item>
                <xr:Item>Document.ЗаказКлиента</xr:Item>
            </Content>
        </Properties>
        <ChildObjects>
            <Subsystem>ОптовыеПродажи</Subsystem>
        </ChildObjects>
    </Subsystem>
</MetaDataObject>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml)
            f.flush()
            result = self.parser.parse(Path(f.name))
            os.unlink(f.name)

        assert result['name'] == 'Продажи'
        assert len(result['content']) == 2
        assert len(result['child_subsystems']) == 1


# ============================================================================
# ТЕСТЫ TYPE_MAPPING
# ============================================================================

class TestTypeMapping:
    """Тесты маппинга типов."""

    def test_all_important_types_covered(self):
        """Проверяем что все важные типы покрыты."""
        important = [
            'Catalogs', 'Documents', 'InformationRegisters', 'AccumulationRegisters',
            'DataProcessors', 'Reports', 'Enums', 'Constants',
            'CommonModules', 'CommonForms', 'CommonCommands', 'CommonTemplates',
            'Subsystems', 'EventSubscriptions', 'ScheduledJobs',
            'DefinedTypes', 'FunctionalOptions', 'ExchangePlans',
            'WebServices', 'HTTPServices', 'XDTOPackages', 'SessionParameters',
        ]
        for t in important:
            assert t in TYPE_MAPPING, f'{t} не покрыт в TYPE_MAPPING'

    def test_special_parsers_configured(self):
        """Проверяем что специальные парсеры настроены."""
        assert TYPE_MAPPING['Subsystems'][1] == 'subsystem'
        assert TYPE_MAPPING['EventSubscriptions'][1] == 'event_subscription'
        assert TYPE_MAPPING['ScheduledJobs'][1] == 'scheduled_job'


# ============================================================================
# ИНТЕГРАЦИОННЫЙ ТЕСТ (на реальных данных)
# ============================================================================

class TestIntegrationRealData:
    """Интеграционный тест на реальных данных УТ11."""

    UT11_DIR = Path('/home/z/my-project/repo_work/data/configs/ut11')

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_extract_all_produces_valid_index(self):
        """Проверяем что экстрактор создаёт валидный индекс."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        # Configuration
        assert result['configuration'] is not None
        assert result['configuration']['properties']['Name'] == 'УправлениеТорговлей'

        # Objects
        assert 'Catalogs' in result['objects']
        assert len(result['objects']['Catalogs']) > 100  # УТ11 имеет 385 справочников

        # Roles
        assert len(result['roles']) > 100

        # Subsystems
        assert len(result['subsystems']) > 10

        # EventSubscriptions
        assert len(result['event_subscriptions']) > 50

        # ScheduledJobs
        assert len(result['scheduled_jobs']) > 50

        # Stats
        assert result['stats']['total_objects'] > 1000
        assert result['stats']['total_attributes'] > 5000

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_event_subscriptions_have_handlers(self):
        """Подписки на события должны иметь handler."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        for es in result['event_subscriptions'][:5]:
            assert es.get('handler'), f'EventSubscription {es["name"]} без handler'
            assert es.get('event'), f'EventSubscription {es["name"]} без event'

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_scheduled_jobs_have_methods(self):
        """Регламентные задания должны иметь method_name."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        for sj in result['scheduled_jobs'][:5]:
            assert sj.get('method_name'), f'ScheduledJob {sj["name"]} без method_name'

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_roles_have_rights(self):
        """Роли должны иметь права доступа."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        # Хотя бы одна роль должна иметь rights
        roles_with_rights = [r for r in result['roles'] if r.get('rights')]
        assert len(roles_with_rights) > 0

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_catalogs_have_attributes(self):
        """Справочники должны иметь реквизиты."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        cats_with_attrs = [c for c in result['objects']['Catalogs']
                          if len(c.get('child_objects', {}).get('attributes', [])) > 0]
        assert len(cats_with_attrs) > 50  # Большинство справочников имеют реквизиты

    @pytest.mark.skipif(not UT11_DIR.exists(), reason='UT11 data not available')
    def test_ext_files_detected(self):
        """Ext/ файлы должны быть обнаружены."""
        extractor = MetadataExtractor()
        result = extractor.extract_all(self.UT11_DIR)

        assert result['ext']['managed_application_module'] is True
        assert result['ext']['session_module'] is True
