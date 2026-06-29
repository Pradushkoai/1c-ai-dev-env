#!/usr/bin/env python3
"""
code_generator.py — Генератор BSL-кода и XML-метаданных для обработок и отчётов 1С.

Создаёт:
1. Внешние обработки (.epf структура):
   - Module.bsl — модуль объекта
   - Form/Module.bsl — модуль формы
   - Form.xml — метаданные формы
   - Обработка.xml — метаданные обработки

2. Отчёты на СКД (.erf структура):
   - Module.bsl — модуль объекта с СКД-логикой
   - Form/Module.bsl — модуль формы отчёта
   - Template.xml — СКД-схема (DataCompositionSchema)
   - Отчет.xml — метаданные отчёта

Использование:
    from code_generator import generate_processing, generate_report
    generate_processing(name="ВыгрузкаНоменклатуры", synonym="Выгрузка номенклатуры", output_dir="/tmp/my_processing")
    generate_report(name="ОтчетПоПродажам", synonym="Отчёт по продажам", output_dir="/tmp/my_report")
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def _gen_uuid() -> str:
    """Генерирует UUID в формате 1С."""
    return str(uuid.uuid4())


def _gen_type_id() -> str:
    """Генерирует TypeId (короткий UUID для GeneratedType)."""
    return str(uuid.uuid4())


def _load_template(template_name: str) -> str:
    """Загружает шаблон из templates/ директории."""
    # Ищем в нескольких местах
    candidates = [
        Path(__file__).parent.parent / 'templates' / template_name,
        Path(__file__).parent / 'templates' / template_name,
        Path('/home/z/my-project/repo_work/templates') / template_name,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding='utf-8')
    raise FileNotFoundError(f"Template not found: {template_name}")


def _fill_template(template: str, replacements: dict) -> str:
    """Заполняет шаблон значениями."""
    for key, value in replacements.items():
        template = template.replace(f'{{{{{key}}}}}', str(value))
    return template


# ============================================================================
# ГЕНЕРАЦИЯ ОБРАБОТКИ
# ============================================================================

def generate_processing(name: str, synonym: str, output_dir: str,
                         description: str = '', author: str = '') -> dict:
    """Генерирует структуру внешней обработки.

    Args:
        name: Имя обработки (латиница, без пробелов, например "ВыгрузкаНоменклатуры")
        synonym: Синоним (русское название, например "Выгрузка номенклатуры")
        output_dir: Куда сохранить структуру
        description: Описание (опционально)
        author: Автор (опционально)

    Returns:
        dict: {files: [{path, type, size}], stats: {...}}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Генерируем UUID
    obj_uuid = _gen_uuid()
    type_id_1 = _gen_type_id()
    value_id_1 = _gen_uuid()
    type_id_2 = _gen_type_id()
    value_id_2 = _gen_uuid()
    type_id_3 = _gen_type_id()
    value_id_3 = _gen_uuid()

    replacements = {
        'NAME': name,
        'SYNONYM': synonym,
        'UUID': obj_uuid,
        'TYPE_ID_1': type_id_1,
        'VALUE_ID_1': value_id_1,
        'TYPE_ID_2': type_id_2,
        'VALUE_ID_2': value_id_2,
        'TYPE_ID_3': type_id_3,
        'VALUE_ID_3': value_id_3,
    }

    files = []

    # 1. Метаданные обработки (Обработка.xml или корневой файл)
    xml_template = _load_template('xml/data_processor_template.xml')
    xml_content = _fill_template(xml_template, replacements)
    xml_path = output_dir / f'{name}.xml'
    xml_path.write_text(xml_content, encoding='utf-8')
    files.append({'path': str(xml_path), 'type': 'metadata', 'size': len(xml_content)})

    # 2. Модуль объекта (Ext/Module.bsl)
    obj_module_template = _load_template('bsl/processing_object_module.bsl')
    obj_module_content = _fill_template(obj_module_template, replacements)
    obj_module_path = output_dir / 'Ext' / 'Module.bsl'
    obj_module_path.parent.mkdir(parents=True, exist_ok=True)
    obj_module_path.write_text(obj_module_content, encoding='utf-8')
    files.append({'path': str(obj_module_path), 'type': 'bsl_object_module', 'size': len(obj_module_content)})

    # 3. Форма обработки (Forms/Форма/)
    form_dir = output_dir / 'Forms' / 'Форма'
    form_dir.mkdir(parents=True, exist_ok=True)

    # 3a. Модуль формы
    form_module_template = _load_template('bsl/processing_form_module.bsl')
    form_module_content = _fill_template(form_module_template, replacements)
    form_module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
    form_module_path.parent.mkdir(parents=True, exist_ok=True)
    form_module_path.write_text(form_module_content, encoding='utf-8')
    files.append({'path': str(form_module_path), 'type': 'bsl_form_module', 'size': len(form_module_content)})

    # 3b. XML формы (упрощённый)
    form_xml = _generate_form_xml(name, synonym, form_type='processing')
    form_xml_path = form_dir / 'Ext' / 'Form.xml'
    form_xml_path.write_text(form_xml, encoding='utf-8')
    files.append({'path': str(form_xml_path), 'type': 'form_xml', 'size': len(form_xml)})

    # 3c. Метаданные формы
    form_meta_xml = _generate_form_metadata_xml(name, 'Форма')
    form_meta_path = form_dir / 'Форма.xml'
    form_meta_path.write_text(form_meta_xml, encoding='utf-8')
    files.append({'path': str(form_meta_path), 'type': 'form_metadata', 'size': len(form_meta_path.read_bytes())})

    # 4. README
    readme = _generate_readme(name, synonym, description, author, 'processing')
    readme_path = output_dir / 'README.md'
    readme_path.write_text(readme, encoding='utf-8')
    files.append({'path': str(readme_path), 'type': 'readme', 'size': len(readme)})

    return {
        'files': files,
        'stats': {
            'total_files': len(files),
            'bsl_files': sum(1 for f in files if 'bsl' in f['type']),
            'xml_files': sum(1 for f in files if 'xml' in f['type']),
            'object_type': 'DataProcessor',
            'name': name,
            'uuid': obj_uuid,
        },
    }


# ============================================================================
# ГЕНЕРАЦИЯ ОТЧЁТА НА СКД
# ============================================================================

def generate_report(name: str, synonym: str, output_dir: str,
                     description: str = '', author: str = '',
                     data_source: str = '', main_query: str = '') -> dict:
    """Генерирует структуру отчёта на СКД.

    Args:
        name: Имя отчёта (например "ОтчетПоПродажам")
        synonym: Синоним (например "Отчёт по продажам")
        output_dir: Куда сохранить
        description: Описание (опционально)
        author: Автор (опционально)
        data_source: Источник данных (например "Документ.РеализацияТоваровУслуг")
        main_query: Готовый запрос 1С (если пусто — будет шаблонный)

    Returns:
        dict: {files: [...], stats: {...}}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    obj_uuid = _gen_uuid()
    type_id_1 = _gen_type_id()
    value_id_1 = _gen_uuid()
    type_id_2 = _gen_type_id()
    value_id_2 = _gen_uuid()
    type_id_3 = _gen_type_id()
    value_id_3 = _gen_uuid()

    replacements = {
        'NAME': name,
        'SYNONYM': synonym,
        'UUID': obj_uuid,
        'TYPE_ID_1': type_id_1,
        'VALUE_ID_1': value_id_1,
        'TYPE_ID_2': type_id_2,
        'VALUE_ID_2': value_id_2,
        'TYPE_ID_3': type_id_3,
        'VALUE_ID_3': value_id_3,
    }

    files = []

    # 1. Метаданные отчёта
    xml_template = _load_template('xml/report_template.xml')
    xml_content = _fill_template(xml_template, replacements)
    xml_path = output_dir / f'{name}.xml'
    xml_path.write_text(xml_content, encoding='utf-8')
    files.append({'path': str(xml_path), 'type': 'metadata', 'size': len(xml_content)})

    # 2. Модуль объекта отчёта (с СКД-логикой)
    obj_module_template = _load_template('bsl/skd_report_object_module.bsl')
    obj_module_content = _fill_template(obj_module_template, replacements)
    obj_module_path = output_dir / 'Ext' / 'Module.bsl'
    obj_module_path.parent.mkdir(parents=True, exist_ok=True)
    obj_module_path.write_text(obj_module_content, encoding='utf-8')
    files.append({'path': str(obj_module_path), 'type': 'bsl_object_module', 'size': len(obj_module_content)})

    # 3. СКД-схема (Templates/ОсновнаяСхемаКомпоновкиДанных/)
    skd_dir = output_dir / 'Templates' / 'ОсновнаяСхемаКомпоновкиДанных'
    skd_dir.mkdir(parents=True, exist_ok=True)

    skd_xml = _generate_skd_schema_xml(name, synonym, data_source, main_query)
    skd_xml_path = skd_dir / 'Ext' / 'Template.xml'
    skd_xml_path.parent.mkdir(parents=True, exist_ok=True)
    skd_xml_path.write_text(skd_xml, encoding='utf-8')
    files.append({'path': str(skd_xml_path), 'type': 'skd_schema', 'size': len(skd_xml)})

    # Метаданные макета
    skd_meta = _generate_template_metadata_xml('ОсновнаяСхемаКомпоновкиДанных')
    skd_meta_path = skd_dir / 'ОсновнаяСхемаКомпоновкиДанных.xml'
    skd_meta_path.write_text(skd_meta, encoding='utf-8')
    files.append({'path': str(skd_meta_path), 'type': 'template_metadata', 'size': len(skd_meta)})

    # 4. Форма отчёта
    form_dir = output_dir / 'Forms' / 'ФормаОтчета'
    form_dir.mkdir(parents=True, exist_ok=True)

    # 4a. Модуль формы отчёта
    form_module_template = _load_template('bsl/skd_report_form_module.bsl')
    form_module_content = _fill_template(form_module_template, replacements)
    form_module_path = form_dir / 'Ext' / 'Form' / 'Module.bsl'
    form_module_path.parent.mkdir(parents=True, exist_ok=True)
    form_module_path.write_text(form_module_content, encoding='utf-8')
    files.append({'path': str(form_module_path), 'type': 'bsl_form_module', 'size': len(form_module_content)})

    # 4b. XML формы отчёта
    form_xml = _generate_form_xml(name, synonym, form_type='report')
    form_xml_path = form_dir / 'Ext' / 'Form.xml'
    form_xml_path.write_text(form_xml, encoding='utf-8')
    files.append({'path': str(form_xml_path), 'type': 'form_xml', 'size': len(form_xml)})

    # 4c. Метаданные формы
    form_meta_xml = _generate_form_metadata_xml(name, 'ФормаОтчета')
    form_meta_path = form_dir / 'ФормаОтчета.xml'
    form_meta_path.write_text(form_meta_xml, encoding='utf-8')
    files.append({'path': str(form_meta_path), 'type': 'form_metadata', 'size': len(form_meta_path.read_bytes())})

    # 5. README
    readme = _generate_readme(name, synonym, description, author, 'report')
    readme_path = output_dir / 'README.md'
    readme_path.write_text(readme, encoding='utf-8')
    files.append({'path': str(readme_path), 'type': 'readme', 'size': len(readme)})

    return {
        'files': files,
        'stats': {
            'total_files': len(files),
            'bsl_files': sum(1 for f in files if 'bsl' in f['type']),
            'xml_files': sum(1 for f in files if 'xml' in f['type']),
            'object_type': 'Report',
            'name': name,
            'uuid': obj_uuid,
            'has_skd_schema': True,
        },
    }


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ГЕНЕРАТОРЫ
# ============================================================================

def _generate_form_xml(name: str, synonym: str, form_type: str = 'processing') -> str:
    """Генерирует упрощённый Form.xml."""
    if form_type == 'report':
        data_path = 'Результат'
        button_name = 'СформироватьОтчет'
        button_title = 'Сформировать отчёт'
    else:
        data_path = 'Объект'
        button_name = 'ВыполнитьОбработку'
        button_title = 'Выполнить'

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>
\t<ChildItems>
\t\t<Button name="{button_name}" id="1">
\t\t\t<Type>UsualButton</Type>
\t\t\t<CommandName>Form.Command.{button_name}</CommandName>
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{button_title}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<ExtendedTooltip name="{button_name}РасширеннаяПодсказка" id="2"/>
\t\t</Button>
\t</ChildItems>
\t<Commands>
\t\t<Command name="{button_name}" id="1">
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{button_title}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<Action>{button_name}</Action>
\t\t</Command>
\t</Commands>
</Form>'''


def _generate_form_metadata_xml(name: str, form_name: str) -> str:
    """Генерирует метаданные формы (Form.xml на уровне объекта)."""
    form_uuid = _gen_uuid()
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<Form uuid="{form_uuid}">
\t\t<Properties>
\t\t\t<Name>{form_name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{form_name}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment/>
\t\t\t<FormType>Managed</FormType>
\t\t\t<IncludeHelpInContents>false</IncludeHelpInContents>
\t\t\t<UseStandardCommands>true</UseStandardCommands>
\t\t\t<ExtendedPresentation/>
\t\t\t<Explanation/>
\t\t</Properties>
\t</Form>
</MetaDataObject>'''


def _generate_template_metadata_xml(template_name: str) -> str:
    """Генерирует метаданные макета (Template.xml на уровне объекта)."""
    template_uuid = _gen_uuid()
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<Template uuid="{template_uuid}">
\t\t<Properties>
\t\t\t<Name>{template_name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{template_name}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment/>
\t\t\t<TemplateType>DataCompositionSchema</TemplateType>
\t\t</Properties>
\t</Template>
</MetaDataObject>'''


def _generate_skd_schema_xml(name: str, synonym: str, data_source: str = '',
                              main_query: str = '') -> str:
    """Генерирует базовую СКД-схему."""
    if not main_query:
        if data_source:
            main_query = f'''ВЫБРАТЬ
\t*
ИЗ
\t{data_source}'''
        else:
            main_query = '''ВЫБРАТЬ
\t*
ИЗ
\tСправочник.Номенклатура'''

    # Экранируем & в запросе для XML
    main_query_xml = main_query.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
\t<dataSource>
\t\t<name>ИсточникДанных1</name>
\t\t<dataSourceType>Local</dataSourceType>
\t</dataSource>
\t<dataSet xsi:type="DataSetQuery">
\t\t<name>НаборДанных1</name>
\t\t<field xsi:type="DataSetFieldField">
\t\t\t<dataPath>Ссылка</dataPath>
\t\t\t<field>Ссылка</field>
\t\t</field>
\t\t<field xsi:type="DataSetFieldField">
\t\t\t<dataPath>Наименование</dataPath>
\t\t\t<field>Наименование</field>
\t\t</field>
\t\t<dataSource>ИсточникДанных1</dataSource>
\t\t<query>{main_query_xml}</query>
\t</dataSet>
\t<settings>
\t\t<item xsi:type="dcsset:StructureItemGroup">
\t\t\t<group>Ссылка</group>
\t\t\t<selection>
\t\t\t\t<item xsi:type="dcsset:SelectedField">
\t\t\t\t\t<field>Ссылка</field>
\t\t\t\t</item>
\t\t\t\t<item xsi:type="dcsset:SelectedField">
\t\t\t\t\t<field>Наименование</field>
\t\t\t\t</item>
\t\t\t</selection>
\t\t</item>
\t</settings>
</DataCompositionSchema>'''


def _generate_readme(name: str, synonym: str, description: str, author: str,
                      obj_type: str) -> str:
    """Генерирует README.md для обработки/отчёта."""
    type_ru = 'Обработка' if obj_type == 'processing' else 'Отчёт на СКД'

    return f'''# {synonym}

## Информация
- **Тип:** {type_ru}
- **Имя:** {name}
- **Синоним:** {synonym}
- **Автор:** {author or 'не указан'}
- **Дата создания:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}

## Описание
{description or 'Описание не указано.'}

## Структура файлов
- `{name}.xml` — метаданные объекта
- `Ext/Module.bsl` — модуль объекта
- `Forms/Форма/` (или `Forms/ФормаОтчета/`) — форма
  - `Ext/Form/Module.bsl` — модуль формы
  - `Ext/Form.xml` — описание элементов формы
'''

# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 4:
        print("Использование: python3 code_generator.py <type> <name> <synonym> [output_dir]")
        print()
        print("type: processing | report")
        print()
        print("Примеры:")
        print("  python3 code_generator.py processing ВыгрузкаНоменклатуры 'Выгрузка номенклатуры' /tmp/my_processing")
        print("  python3 code_generator.py report ОтчетПоПродажам 'Отчёт по продажам' /tmp/my_report")
        sys.exit(1)

    obj_type = sys.argv[1]
    name = sys.argv[2]
    synonym = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else f'/tmp/{name}'

    if obj_type == 'processing':
        result = generate_processing(name, synonym, output_dir)
    elif obj_type == 'report':
        result = generate_report(name, synonym, output_dir)
    else:
        print(f"❌ Неизвестный тип: {obj_type}")
        sys.exit(1)

    print(f"\n✅ Сгенерировано {result['stats']['total_files']} файлов:")
    for f in result['files']:
        print(f"  [{f['type']}] {f['path']} ({f['size']} байт)")
    print(f"\n📁 Структура сохранена в: {output_dir}")


if __name__ == '__main__':
    main()
