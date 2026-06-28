#!/usr/bin/env python3
"""
v8_metadata_parser.py — Парсер метаданных 1С из формата v8unpack.

Поддерживает два формата .cf:
1. Классический (8.2 и ранее) — коды типов как в стандарте 1С
2. Современный (8.3.24+) — коды типов сдвинуты, добавлены новые типы

Для определения типа объекта используется:
- Прямой код типа из метаданных (если он в TYPE_MAP_V2)
- Эвристика по содержимому метаданных (CodeLength, NumberLength, и т.д.)
- Fallback на TYPE_MAP_V1 (классические коды)

Формат v8unpack (после распаковки .cf):
- UUID (без расширения) — метаданные объекта в формате структуры значений 1С
- UUID.0/ — папка с BSL модулем (info + text)
- UUID.1/ — папка с дополнительными модулями (формы, и т.д.)
- UUID.2/ — папка с дополнительными модулями

Типы объектов 1С (кодировка v2, современный формат):
  1=Subsystem, 2=CommonTemplate, 3=StyleItem, 4=CommonTemplate,
  5=CommonForm, 6=CommonPicture, 7=CommonCommand, 8=CommandGroup,
  10=CommonAttribute, 11=SessionParameter, 12=CommonModule, 13=Role,
  14=ExchangePlan, 15=FilterCriterion, 16=Subsystem,
  17=DataProcessor, 18=Report, 19=InformationRegister, 20=Catalog,
  21=Subsystem, 22=Subsystem, 23=?, 24=?,
  25=ChartOfCharacteristicTypes, 26=ChartOfAccounts, 27=AccountingRegister,
  28=AccumulationRegister, 29=BusinessProcess, 30=Task, 31=Constant,
  32=DefinedType, 33=InformationRegister, 34=ScheduledJob,
  35=FunctionalOption, 36=FunctionalOptionParameter, 37=HTTPService,
  38=WebService, 39=XDTOPackage, 40=Document, 50=Form,
  56=Catalog, 57=Catalog, 59=Language, 67=Subsystem

Использование:
    from v8_metadata_parser import V8MetadataParser
    parser = V8MetadataParser('/tmp/ut11_full')
    objects = parser.parse_all()
    for obj in objects:
        print(f"{obj.type_name}: {obj.name}")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================================
# КАРТА КОДОВ ТИПОВ — современный формат .cf (1С 8.3.24+)
# ============================================================================
# Установлена на основе анализа реальных .cf файлов (УТ11, УНП, ЭДО)
# В современной кодировке:
# - Code 12 = CommonModule (а не Role как в классике!)
# - Code 17 = DataProcessor (а не Catalog)
# - Code 20 = Catalog
# - Code 40 = Document
# - Code 56, 57 = Catalog (подтипы)
# - Code 19, 33 = InformationRegister (два подтипа)
# - Code 14 = FunctionalOption (имена "Использовать...")
TYPE_MAP_V2 = {
    0: 'Form',  # форма внутри объекта (sub-object, обычно пропускается)
    1: 'Subsystem',
    2: 'CommonTemplate',
    3: 'StyleItem',
    4: 'CommonTemplate',
    5: 'CommonForm',
    6: 'CommonPicture',
    7: 'CommonCommand',
    8: 'CommandGroup',
    9: 'CommonTemplate',
    10: 'CommonAttribute',
    11: 'SessionParameter',
    12: 'CommonModule',  # ВАЖНО: в новом формате это CommonModule!
    13: 'Role',
    14: 'FunctionalOption',  # Имена "Использовать..." — это FunctionalOption
    15: 'FilterCriterion',
    16: 'Constant',  # Константы
    17: 'DataProcessor',
    18: 'Report',
    19: 'InformationRegister',
    20: 'Catalog',
    21: 'Subsystem',
    22: 'Subsystem',
    23: 'CommonTemplate',
    24: 'CommonAttribute',
    25: 'ChartOfCharacteristicTypes',
    26: 'ChartOfAccounts',
    27: 'AccountingRegister',
    28: 'AccumulationRegister',
    29: 'BusinessProcess',
    30: 'Task',
    31: 'Constant',
    32: 'DefinedType',
    33: 'InformationRegister',
    34: 'ScheduledJob',
    35: 'FunctionalOption',
    36: 'FunctionalOptionParameter',
    37: 'HTTPService',
    38: 'WebService',
    39: 'XDTOPackage',
    40: 'Document',
    50: 'Form',
    52: 'Constant',
    53: 'CommonTemplate',
    54: 'DefinedType',
    56: 'Catalog',
    57: 'Catalog',
    59: 'Language',
    67: 'Subsystem',
}

# Классическая карта (для старых .cf файлов)
TYPE_MAP_V1 = {
    1: 'Subsystem',
    2: 'Style',
    3: 'StyleItem',
    4: 'CommonModule',
    5: 'CommonForm',
    6: 'CommonPicture',
    7: 'CommonCommand',
    8: 'CommandGroup',
    9: 'CommonTemplate',
    10: 'CommonAttribute',
    11: 'SessionParameter',
    12: 'Role',
    13: 'CommonTemplate',
    14: 'ExchangePlan',
    15: 'FilterCriterion',
    16: 'Subsystem',
    17: 'Catalog',
    18: 'Document',
    19: 'InformationRegister',
    20: 'AccumulationRegister',
    21: 'DocumentJournal',
    22: 'Enum',
    23: 'Report',
    24: 'DataProcessor',
    25: 'ChartOfCharacteristicTypes',
    26: 'ChartOfAccounts',
    27: 'AccountingRegister',
    28: 'CalculationRegister',
    29: 'BusinessProcess',
    30: 'Task',
    31: 'Constant',
    32: 'DefinedType',
    33: 'EventSubscription',
    34: 'ScheduledJob',
    35: 'FunctionalOption',
    36: 'FunctionalOptionParameter',
    37: 'HTTPService',
    38: 'WebService',
    39: 'XDTOPackage',
    40: 'WSReference',
    50: 'Form',
    59: 'Language',
}

# Обратная совместимость
TYPE_MAP = TYPE_MAP_V2


@dataclass
class V8Object:
    """Один объект метаданных 1С."""
    uuid: str
    type_code: int
    type_name: str
    name: str = ''
    synonym: str = ''
    comment: str = ''
    bsl_modules: dict[str, str] = field(default_factory=dict)  # имя_модуля -> код
    raw_metadata: str = ''


# ============================================================================
# ЭВРИСТИКА — определение типа по содержимому метаданных
# ============================================================================
# Надёжный способ определить тип: в метаданных есть характерные поля
# - Catalog: содержит CodeLength (число) и DescriptionLength (число)
# - Document: содержит NumberLength (число)
# - InformationRegister: структура вида {0,0},...,1,0,0,0
# - CommonModule: короткая структура с {1,0,UUID},1,...,1,0,0,0
# - Subsystem: длинная структура с ChildObjects

def detect_type_by_content(content: str, type_code: int) -> str:
    """
    Определить тип объекта по коду типа.
    
    В современном формате .cf (8.3.24+) коды типов сдвинуты.
    Используем TYPE_MAP_V2 (новый формат), затем TYPE_MAP_V1 (классический).
    
    Args:
        content: Содержимое файла метаданных (для будущих эвристик)
        type_code: Код типа из {1,{N,...
    
    Returns: Имя типа (Catalog, Document, InformationRegister, etc.)
    """
    # Сначала проверим V2 карту (новый формат)
    if type_code in TYPE_MAP_V2:
        return TYPE_MAP_V2[type_code]
    
    # Fallback на V1 (классический формат)
    if type_code in TYPE_MAP_V1:
        return TYPE_MAP_V1[type_code]
    
    return f'Unknown_{type_code}'


class V8MetadataParser:
    """Парсер метаданных 1С из распакованного .cf (формат v8unpack)."""

    def __init__(self, extracted_dir: Path | str):
        self.dir = Path(extracted_dir)
        # Ищем папку с контейнером 1 (объекты метаданных)
        self.objects_dir = self.dir / '1'
        if not self.objects_dir.exists():
            # Альтернативная структура — объекты в корне
            self.objects_dir = self.dir
        # Кэш: UUID -> список папок UUID.N с BSL модулями
        self._modules_cache: dict[str, list[Path]] = {}
        self._build_modules_cache()

    def _build_modules_cache(self) -> None:
        """Строит кэш: UUID -> список папок UUID.N с BSL модулями."""
        if not self.objects_dir.exists():
            return
        for p in self.objects_dir.iterdir():
            name = p.name
            # Ищем папки вида UUID.N (N - число)
            if '.' in name and p.is_dir():
                uuid_part = name.split('.')[0]
                self._modules_cache.setdefault(uuid_part, []).append(p)

    def parse_all(self) -> list[V8Object]:
        """Парсит все объекты метаданных из распакованного .cf."""
        if not self.objects_dir.exists():
            return []

        objects = []
        # Ищем все файлы без расширения (метаданные объектов)
        for p in sorted(self.objects_dir.iterdir()):
            name = p.name
            # Пропускаем файлы с расширением (UUID.0, UUID.1 и т.д.)
            if '.' in name:
                continue
            if not p.is_file():
                continue
            # Пропускаем служебные файлы
            if name in ('version', 'versions', 'root'):
                continue

            obj = self._parse_object(p)
            if obj:
                objects.append(obj)

        return objects

    def _parse_object(self, metadata_path: Path) -> Optional[V8Object]:
        """Парсит один объект метаданных."""
        try:
            content = metadata_path.read_text(encoding='utf-8-sig', errors='replace')
        except Exception:
            return None

        # Извлекаем тип объекта ТОЛЬКО из начала файла: {1,\n{N,...
        # Используем re.match (а не search) чтобы избежать ложных срабатываний
        # на sub-объектах внутри метаданных
        type_match = re.match(r'\s*\{1,\s*\{(\d+),', content)
        if not type_match:
            return None

        type_code = int(type_match.group(1))
        type_name = detect_type_by_content(content, type_code)

        # Извлекаем UUID и имя объекта.
        # В современном формате .cf есть два паттерна:
        # 1. {1,0,UUID},"Name" — стандартный (CommonModule, Catalog, Document, ...)
        # 2. {0,0,UUID},"Name" — альтернативный (FunctionalOption, Constant, ...)
        obj_uuid = metadata_path.stem
        name = ''

        # Пытаемся сначала паттерн {1,0,UUID},"Name"
        name_match = re.search(r'\{1,0,([0-9a-f-]{36})\},"([^"]+)"', content, re.IGNORECASE)
        if name_match:
            obj_uuid = name_match.group(1)
            name = name_match.group(2)
        else:
            # Альтернативный паттерн {0,0,UUID},"Name"
            name_match = re.search(r'\{0,0,([0-9a-f-]{36})\},"([^"]+)"', content, re.IGNORECASE)
            if name_match:
                obj_uuid = name_match.group(1)
                name = name_match.group(2)

        # Пропускаем объекты без имени — это sub-объекты (формы, команды, и т.д.)
        if not name:
            return None

        # Извлекаем синоним: {1,"ru","Синоним"}
        synonym_match = re.search(r'\{1,"ru","([^"]*)"\}', content)
        synonym = synonym_match.group(1) if synonym_match else ''

        # Извлекаем BSL модули из папок UUID.N/text
        bsl_modules = self._extract_bsl_modules(metadata_path.stem)

        return V8Object(
            uuid=obj_uuid,
            type_code=type_code,
            type_name=type_name,
            name=name,
            synonym=synonym,
            bsl_modules=bsl_modules,
            raw_metadata=content[:500],  # первые 500 символов для отладки
        )

    def _extract_bsl_modules(self, uuid: str) -> dict[str, str]:
        """Извлекает BSL модули из папок UUID.N/text (использует кэш)."""
        modules = {}
        # Используем кэш вместо обхода директории
        for p in self._modules_cache.get(uuid, []):
            text_file = p / 'text'
            if text_file.exists():
                try:
                    code = text_file.read_text(encoding='utf-8-sig', errors='replace')
                    if code.strip():  # не пустой
                        module_num = p.name.split('.')[-1]
                        module_name = {
                            '0': 'Module',  # для CommonModule — это основной модуль
                            '1': 'ObjectModule',
                            '2': 'ManagerModule',
                            '3': 'FormModule',
                        }.get(module_num, f'Module_{module_num}')
                        # Если модуль с таким именем уже есть — добавляем суффикс
                        if module_name in modules:
                            module_name = f'{module_name}_{module_num}'
                        modules[module_name] = code
                except Exception:
                    pass
        return modules

    def get_common_modules(self) -> list[V8Object]:
        """Возвращает только общие модули (CommonModule)."""
        return [obj for obj in self.parse_all() if obj.type_name == 'CommonModule']

    def get_objects_by_type(self, type_name: str) -> list[V8Object]:
        """Возвращает объекты указанного типа."""
        return [obj for obj in self.parse_all() if obj.type_name == type_name]

    def get_stats(self) -> dict:
        """Возвращает статистику по объектам."""
        objects = self.parse_all()
        from collections import Counter
        type_counts = Counter(obj.type_name for obj in objects)
        total_modules = sum(len(obj.bsl_modules) for obj in objects)
        return {
            'total_objects': len(objects),
            'total_bsl_modules': total_modules,
            'by_type': dict(type_counts.most_common()),
        }


def main():
    import sys
    if len(sys.argv) < 2:
        print("Использование: python3 v8_metadata_parser.py <extracted_cf_dir>")
        print()
        print("Пример:")
        print("  python3 v8_metadata_parser.py /tmp/ut11_full")
        sys.exit(1)

    parser = V8MetadataParser(sys.argv[1])
    stats = parser.get_stats()

    print(f"=== Статистика ===")
    print(f"Всего объектов: {stats['total_objects']}")
    print(f"BSL модулей: {stats['total_bsl_modules']}")
    print()
    print(f"=== По типам ===")
    for type_name, count in stats['by_type'].items():
        print(f"  {type_name:30}: {count}")

    print()
    print(f"=== CommonModules (первые 10) ===")
    common_modules = parser.get_common_modules()
    for obj in common_modules[:10]:
        modules = ', '.join(obj.bsl_modules.keys()) if obj.bsl_modules else 'нет модулей'
        print(f"  {obj.name:40} ({modules})")


if __name__ == "__main__":
    main()
