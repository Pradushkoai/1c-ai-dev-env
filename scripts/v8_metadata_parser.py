#!/usr/bin/env python3
"""
v8_metadata_parser.py — Парсер метаданных 1С из формата v8unpack.

Формат v8unpack (после распаковки .cf):
- UUID (без расширения) — метаданные объекта в формате структуры значений 1С
  Пример: {1,{19,UUID1,UUID2,{0,{3,{1,0,UUID3},"Имя",{1,"ru","Синоним"},...}}}}
- UUID.0/, UUID.1/, UUID.2/ — папки с данными объекта
- UUID.N/info — короткая структура с типом
- UUID.N/text — BSL модуль (код объекта)

Типы объектов 1С (по порядку в ChildObjects):
  1=Подсистема, 2=Style, 3=StyleItem, 4=CommonModule, 5=CommonForm,
  6=CommonPicture, 7=CommonCommand, 8=CommandGroup, 9=CommonTemplate,
  10=CommonAttribute, 11=SessionParameter, 12=Role, 13=CommonTemplate,
  14=ExchangePlan, 15=FilterCriterion, 16=Subsystem,
  17=Catalog, 18=Document, 19=InformationRegister, 20=AccumulationRegister,
  21=DocumentJournal, 22=Enum, 23=Report, 24=DataProcessor,
  25=ChartOfCharacteristicTypes, 26=ChartOfAccounts, 27=AccountingRegister,
  28=CalculationRegister, 29=BusinessProcess, 30=Task, 31=Constant,
  32=DefinedType, 33=EventSubscription, 34=ScheduledJob,
  35=FunctionalOption, 36=FunctionalOptionParameter, 37=HTTPService,
  38=WebService, 39=XDTOPackage, 40=WSReference

Использование:
    from v8_metadata_parser import V8MetadataParser
    parser = V8MetadataParser('/tmp/edo3_full')
    objects = parser.parse_all()
    for obj in objects:
        print(f"{obj.type_name}: {obj.name}")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Маппинг типов объектов 1С (по коду из формата v8unpack)
# Основано на стандарте 1С и анализе реальных .cf файлов
TYPE_MAP = {
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
    50: 'Form',  # форма внутри объекта
    59: 'Language',
}


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


class V8MetadataParser:
    """Парсер метаданных 1С из распакованного .cf (формат v8unpack)."""

    def __init__(self, extracted_dir: Path | str):
        self.dir = Path(extracted_dir)
        # Ищем папку с контейнером 1 (объекты метаданных)
        # Структура: extracted_dir/1/UUID, extracted_dir/1/UUID.0/, и т.д.
        self.objects_dir = self.dir / '1'
        if not self.objects_dir.exists():
            # Альтернативная структура — объекты в корне
            self.objects_dir = self.dir
        # Кэш: UUID -> список папок UUID.N
        self._modules_cache: dict[str, list[Path]] = {}
        self._build_modules_cache()

    def _build_modules_cache(self) -> None:
        """Строит кэш: UUID -> список папок UUID.N с BSL модулями."""
        if not self.objects_dir.exists():
            return
        for p in self.objects_dir.iterdir():
            name = p.name
            # Ищем папки вида UUID.N
            if '.' in name and p.is_dir():
                uuid = name.split('.')[0]
                self._modules_cache.setdefault(uuid, []).append(p)

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

        # Извлекаем тип объекта: {1,{TYPE,... (с возможными переносами строк)
        type_match = re.search(r'\{1,\s*\{(\d+),', content)
        if not type_match:
            return None

        type_code = int(type_match.group(1))
        type_name = TYPE_MAP.get(type_code, f'Unknown_{type_code}')

        # Извлекаем UUID объекта: {1,0,UUID,"Имя",...}
        # Формат: {3,{1,0,UUID},"Имя",...}
        uuid_match = re.search(r'\{1,0,([0-9a-f-]{36})\}', content, re.IGNORECASE)
        obj_uuid = uuid_match.group(1) if uuid_match else metadata_path.stem

        # Извлекаем имя: ,"Имя",
        # Имя идёт после UUID в кавычках
        name_match = re.search(r'\{1,0,[0-9a-f-]{36}\},"([^"]+)"', content, re.IGNORECASE)
        name = name_match.group(1) if name_match else ''

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
                            '0': 'ObjectModule',
                            '1': 'ManagerModule',
                            '2': 'FormModule',
                        }.get(module_num, f'Module_{module_num}')
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
        print("  python3 v8_metadata_parser.py /tmp/edo3_full")
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
