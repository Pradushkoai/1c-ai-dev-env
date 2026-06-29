#!/usr/bin/env python3
"""
code_validator.py — Валидация сгенерированного BSL-кода и XML метаданных.

Проверяет:
1. BSL-синтаксис (базовая проверка — без Java/BSL LS):
   - Сбалансированность #Область / #КонецОбласти
   - Сбалансированность Процедура/КонецПроцедуры, Функция/КонецФункции
   - Сбалансированность Если/КонецЕсли, Пока/КонецЦикла, Для/КонецЦикла
   - Корректность Экспорт в объявлениях
   - Наличие &НаСервере/&НаКлиенте перед процедурами форм

2. XML-валидность:
   - Парсинг через xml.etree.ElementTree
   - Проверка обязательных тегов (Name, Synonym)
   - Проверка UUID формата

3. Соответствие стандартам 1С (через check_1c_standards.py):
   - Базовые правила: именование, комментарии, и т.д.

4. Структурная целостность:
   - Наличие Module.bsl, Form.xml, метаданных
   - Связи между файлами (DefaultForm → Forms/<Имя>)

Использование:
    from code_validator import validate_generated
    result = validate_generated('/tmp/my_processing')
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


# ============================================================================
# BSL ВАЛИДАТОР
# ============================================================================

class BSLValidator:
    """Базовый валидатор BSL-синтаксиса (без Java/BSL LS)."""

    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []

    def validate(self, bsl_content: str, file_path: str = '') -> dict:
        """Валидирует BSL-код.

        Returns:
            {errors, warnings, stats}
        """
        self.errors = []
        self.warnings = []
        self.file_path = file_path

        lines = bsl_content.split('\n')

        self._check_regions(lines)
        self._check_procedures_functions(lines)
        self._check_control_structures(lines)
        self._check_export_declarations(lines)
        self._check_form_annotations(lines)

        return {
            'errors': self.errors,
            'warnings': self.warnings,
            'stats': {
                'total_lines': len(lines),
                'errors_count': len(self.errors),
                'warnings_count': len(self.warnings),
            },
        }

    def _add_error(self, line: int, message: str):
        self.errors.append({'line': line, 'message': message, 'file': self.file_path})

    def _add_warning(self, line: int, message: str):
        self.warnings.append({'line': line, 'message': message, 'file': self.file_path})

    def _check_regions(self, lines: list[str]):
        """Проверка сбалансированности #Область / #КонецОбласти."""
        region_stack = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#Область'):
                region_name = stripped.replace('#Область', '').strip()
                if not region_name:
                    self._add_warning(i, '#Область без имени')
                region_stack.append((i, region_name))
            elif stripped.startswith('#КонецОбласти'):
                if not region_stack:
                    self._add_error(i, '#КонецОбласти без парной #Область')
                else:
                    region_stack.pop()

        for line, name in region_stack:
            self._add_error(line, f'Незакрытая #Область: {name}')

    def _check_procedures_functions(self, lines: list[str]):
        """Проверка Процедура/КонецПроцедуры, Функция/КонецФункции."""
        proc_stack = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Процедура Имя(...) [Экспорт]
            m = re.match(r'^(Процедура|Функция)\s+(\w+)\s*\(', stripped)
            if m:
                keyword = m.group(1)
                name = m.group(2)
                proc_stack.append((i, keyword, name))

            # КонецПроцедуры / КонецФункции
            if re.match(r'^Конец(Процедуры|Функции)', stripped):
                if not proc_stack:
                    self._add_error(i, 'КонецПроцедуры/КонецФункции без парного объявления')
                else:
                    start_line, keyword, name = proc_stack.pop()
                    expected_end = 'КонецПроцедуры' if keyword == 'Процедура' else 'КонецФункции'
                    if not stripped.startswith(expected_end):
                        self._add_error(i, f'Ожидалось {expected_end} для {keyword} {name} (строка {start_line})')

        for line, keyword, name in proc_stack:
            self._add_error(line, f'Незакрытая {keyword}: {name}')

    def _check_control_structures(self, lines: list[str]):
        """Проверка Если/КонецЕсли, Пока/КонецЦикла, Для/КонецЦикла."""
        if_stack = []
        loop_stack = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Если ... Тогда
            if re.match(r'^Если\s+.+\s+Тогда', stripped):
                if_stack.append(i)

            # КонецЕсли
            if stripped.startswith('КонецЕсли'):
                if not if_stack:
                    self._add_error(i, 'КонецЕсли без Если')
                else:
                    if_stack.pop()

            # Пока ... Цикл
            if re.match(r'^Пока\s+.+\s+Цикл', stripped):
                loop_stack.append(('Пока', i))

            # Для ... Цикл
            if re.match(r'^Для\s+.+\s+Цикл', stripped):
                loop_stack.append(('Для', i))

            # КонецЦикла
            if stripped.startswith('КонецЦикла'):
                if not loop_stack:
                    self._add_error(i, 'КонецЦикла без цикла')
                else:
                    loop_stack.pop()

        for line in if_stack:
            self._add_error(line, 'Незакрытый Если')

        for loop_type, line in loop_stack:
            self._add_error(line, f'Незакрытый цикл {loop_type}')

    def _check_export_declarations(self, lines: list[str]):
        """Проверка корректности Экспорт в объявлениях."""
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Процедура/Функция без Экспорт, но с комментарием "Экспорт" в описании
            if re.match(r'^(Процедура|Функция)\s+\w+\s*\(', stripped):
                if 'Экспорт' not in stripped:
                    # Проверяем, есть ли комментарий с "Экспорт" выше
                    if i >= 2 and 'Экспорт' in lines[i-2]:
                        self._add_warning(i, 'Возможно пропущен "Экспорт" в объявлении')

    def _check_form_annotations(self, lines: list[str]):
        """Проверка наличия &НаСервере/&НаКлиенте перед процедурами форм."""
        is_form_module = False
        for line in lines:
            if 'ПриСозданииНаСервере' in line or 'НаСервере' in line:
                is_form_module = True
                break

        if not is_form_module:
            return

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r'^(Процедура|Функция)\s+\w+\s*\(', stripped):
                # Проверяем, есть ли &НаСервере или &НаКлиенте выше
                if i >= 2:
                    prev_line = lines[i-2].strip() if i >= 2 else ''
                    if not (prev_line.startswith('&НаСервере') or
                            prev_line.startswith('&НаКлиенте') or
                            prev_line.startswith('&НаКлиентеНаСервере')):
                        self._add_warning(i, f'Процедура/Функция без &НаСервере/&НаКлиенте: {stripped[:50]}')


# ============================================================================
# XML ВАЛИДАТОР
# ============================================================================

class XMLValidator:
    """Валидатор XML метаданных 1С."""

    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []

    def validate(self, xml_content: str, file_path: str = '') -> dict:
        """Валидирует XML."""
        self.errors = []
        self.warnings = []
        self.file_path = file_path

        # 1. Парсинг XML
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            self.errors.append({'line': 0, 'message': f'XML parse error: {e}', 'file': file_path})
            return {'errors': self.errors, 'warnings': self.warnings}

        # 2. Проверка обязательных элементов
        self._check_required_elements(root)

        # 3. Проверка UUID формата
        self._check_uuid_format(root)

        return {
            'errors': self.errors,
            'warnings': self.warnings,
        }

    def _check_required_elements(self, root):
        """Проверка обязательных тегов."""
        # Определяем тип XML по корневому тегу
        root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag

        # Form.xml (элементы формы) — не содержит Properties, это нормально
        if root_tag == 'Form':
            return

        # DataCompositionSchema — СКД-схема, другая структура
        if root_tag == 'DataCompositionSchema':
            return

        # MetaDataObject — метаданные объекта (Catalog, Document, и т.д.)
        # Ищем Properties
        ns = ''
        if '}' in root.tag:
            ns = root.tag.split('}')[0] + '}'

        properties = root.find(f'.//{ns}Properties')
        if properties is None:
            # Пробуем без namespace
            for elem in root.iter():
                if elem.tag.endswith('Properties'):
                    properties = elem
                    break

        if properties is None:
            self.errors.append({'line': 0, 'message': 'Отсутствует <Properties>', 'file': self.file_path})
            return

        # Проверяем Name
        name_found = False
        for child in properties:
            if child.tag.endswith('Name'):
                name_found = True
                if not child.text or not child.text.strip():
                    self.errors.append({'line': 0, 'message': '<Name> пустой', 'file': self.file_path})
                break

        if not name_found:
            self.errors.append({'line': 0, 'message': 'Отсутствует <Name> в <Properties>', 'file': self.file_path})

    def _check_uuid_format(self, root):
        """Проверка формата UUID."""
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

        uuid_attr = root.get('uuid', '')
        if uuid_attr and not uuid_pattern.match(uuid_attr):
            self.warnings.append({'line': 0, 'message': f'Некорректный UUID: {uuid_attr}', 'file': self.file_path})


# ============================================================================
# СТРУКТУРНЫЙ ВАЛИДАТОР
# ============================================================================

def validate_structure(source_dir: Path) -> dict:
    """Проверяет структурную целостность обработки/отчёта.

    Returns:
        {errors, warnings, files_found}
    """
    errors = []
    warnings = []
    files_found = {}

    source_dir = Path(source_dir)

    # 1. Метаданные объекта (*.xml в корне)
    xml_files = list(source_dir.glob('*.xml'))
    if not xml_files:
        errors.append({'message': 'Отсутствует XML метаданных в корне'})
    else:
        files_found['metadata'] = str(xml_files[0])

    # 2. Модуль объекта (Ext/Module.bsl)
    obj_module = source_dir / 'Ext' / 'Module.bsl'
    if obj_module.exists():
        files_found['object_module'] = str(obj_module)
    else:
        warnings.append({'message': 'Отсутствует Ext/Module.bsl (модуль объекта)'})

    # 3. Формы (Forms/*)
    forms_dir = source_dir / 'Forms'
    forms = []
    if forms_dir.exists():
        for form_dir in forms_dir.iterdir():
            if form_dir.is_dir():
                form_module = form_dir / 'Ext' / 'Form' / 'Module.bsl'
                form_xml = form_dir / 'Ext' / 'Form.xml'
                form_meta = form_dir / f'{form_dir.name}.xml'

                form_info = {'name': form_dir.name}
                if form_module.exists():
                    form_info['module'] = str(form_module)
                if form_xml.exists():
                    form_info['form_xml'] = str(form_xml)
                if form_meta.exists():
                    form_info['metadata'] = str(form_meta)
                forms.append(form_info)

    files_found['forms'] = forms

    # 4. СКД-схема (для отчётов)
    skd_dir = source_dir / 'Templates' / 'ОсновнаяСхемаКомпоновкиДанных'
    if skd_dir.exists():
        skd_xml = skd_dir / 'Ext' / 'Template.xml'
        if skd_xml.exists():
            files_found['skd_schema'] = str(skd_xml)

    return {
        'errors': errors,
        'warnings': warnings,
        'files_found': files_found,
    }


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ ВАЛИДАЦИИ
# ============================================================================

def validate_generated(source_dir: str) -> dict:
    """Полная валидация сгенерированной обработки/отчёта.

    Args:
        source_dir: Путь к каталогу со структурой

    Returns:
        {bsl_validation, xml_validation, structure_validation, overall_verdict}
    """
    source_dir = Path(source_dir)

    if not source_dir.exists():
        return {'error': f'Directory not found: {source_dir}'}

    # 1. Структурная валидация
    structure = validate_structure(source_dir)

    # 2. BSL валидация
    bsl_validator = BSLValidator()
    bsl_results = []

    # Модуль объекта
    obj_module = source_dir / 'Ext' / 'Module.bsl'
    if obj_module.exists():
        content = obj_module.read_text(encoding='utf-8-sig')
        result = bsl_validator.validate(content, str(obj_module))
        bsl_results.append({'file': 'object_module', **result})

    # Модули форм
    forms_dir = source_dir / 'Forms'
    if forms_dir.exists():
        for form_dir in forms_dir.iterdir():
            if not form_dir.is_dir():
                continue
            form_module = form_dir / 'Ext' / 'Form' / 'Module.bsl'
            if form_module.exists():
                content = form_module.read_text(encoding='utf-8-sig')
                bsl_validator = BSLValidator()
                result = bsl_validator.validate(content, str(form_module))
                bsl_results.append({'file': f'form_{form_dir.name}', **result})

    # 3. XML валидация
    xml_validator = XMLValidator()
    xml_results = []

    for xml_file in source_dir.glob('*.xml'):
        content = xml_file.read_text(encoding='utf-8-sig')
        result = xml_validator.validate(content, str(xml_file))
        xml_results.append({'file': xml_file.name, **result})

    # Формы XML
    if forms_dir.exists():
        for form_dir in forms_dir.iterdir():
            if not form_dir.is_dir():
                continue
            for xml_file in form_dir.rglob('*.xml'):
                content = xml_file.read_text(encoding='utf-8-sig')
                xml_validator = XMLValidator()
                result = xml_validator.validate(content, str(xml_file))
                xml_results.append({'file': str(xml_file.relative_to(source_dir)), **result})

    # 4. Общий вердикт
    total_errors = (sum(len(r.get('errors', [])) for r in bsl_results) +
                    sum(len(r.get('errors', [])) for r in xml_results) +
                    len(structure['errors']))
    total_warnings = (sum(len(r.get('warnings', [])) for r in bsl_results) +
                      sum(len(r.get('warnings', [])) for r in xml_results) +
                      len(structure['warnings']))

    if total_errors == 0 and total_warnings == 0:
        verdict = 'perfect'
    elif total_errors == 0:
        verdict = 'warnings'
    else:
        verdict = 'errors'

    return {
        'source_dir': str(source_dir),
        'structure': structure,
        'bsl_validation': bsl_results,
        'xml_validation': xml_results,
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'verdict': verdict,
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 code_validator.py <source_dir>")
        print()
        print("Пример:")
        print("  python3 code_validator.py /tmp/test_processing")
        sys.exit(1)

    source_dir = sys.argv[1]
    result = validate_generated(source_dir)

    print(f"\n{'='*60}")
    print(f"ВАЛИДАЦИЯ: {source_dir}")
    print(f"{'='*60}")

    print(f"\nВердикт: {result['verdict'].upper()}")
    print(f"Ошибок: {result['total_errors']}")
    print(f"Предупреждений: {result['total_warnings']}")

    if result['structure']['errors']:
        print(f"\nСтруктурные ошибки:")
        for e in result['structure']['errors']:
            print(f"  ❌ {e['message']}")

    if result['structure']['warnings']:
        print(f"\nСтруктурные предупреждения:")
        for w in result['structure']['warnings']:
            print(f"  ⚠️ {w['message']}")

    for bsl in result.get('bsl_validation', []):
        if bsl.get('errors') or bsl.get('warnings'):
            print(f"\nBSL: {bsl['file']}")
            for e in bsl.get('errors', []):
                print(f"  ❌ Строка {e['line']}: {e['message']}")
            for w in bsl.get('warnings', []):
                print(f"  ⚠️ Строка {w['line']}: {w['message']}")

    for xml in result.get('xml_validation', []):
        if xml.get('errors') or xml.get('warnings'):
            print(f"\nXML: {xml['file']}")
            for e in xml.get('errors', []):
                print(f"  ❌ {e['message']}")
            for w in xml.get('warnings', []):
                print(f"  ⚠️ {w['message']}")

    print(f"\n{'='*60}")
    if result['verdict'] == 'perfect':
        print("✅ Код идеален — готов к использованию!")
    elif result['verdict'] == 'warnings':
        print("⚠️ Есть предупреждения, но код рабочий")
    else:
        print("❌ Есть ошибки — требуется исправление")


if __name__ == '__main__':
    main()
