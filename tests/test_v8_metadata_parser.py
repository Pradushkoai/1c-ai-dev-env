"""
Тесты для v8_metadata_parser.py.
Проверяем парсинг метаданных 1С из формата v8unpack.

Используются коды типов современного формата .cf (8.3.24+):
- Code 12 = CommonModule (не 4 как в классике)
- Code 20 = Catalog (не 17)
- Code 40 = Document (не 18)
- Code 19 = InformationRegister
- Code 17 = DataProcessor
- Code 18 = Report
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from v8_metadata_parser import V8MetadataParser, V8Object, TYPE_MAP, TYPE_MAP_V2


# ============================================================================
# ФИКСТУРЫ ДЛЯ СОЗДАНИЯ СИНТЕТИЧЕСКИХ ДАННЫХ
# ============================================================================

@pytest.fixture
def sample_cf_structure(tmp_path):
    """Создаёт синтетическую структуру распакованного .cf (современный формат V2)."""
    # Структура: tmp_path/1/UUID (метаданные) + tmp_path/1/UUID.0/text (BSL)

    # CommonModule (тип 12 в V2)
    cm_uuid = '48659b94-ace8-45f4-a043-6b2731ec6925'
    cm_dir = tmp_path / '1'
    cm_dir.mkdir(parents=True)

    # Метаданные объекта
    (cm_dir / cm_uuid).write_text(
        f'{{1,\n{{12,uuid1,uuid2,\n{{0,\n{{3,\n{{1,0,{cm_uuid}}},"TestModule",\n'
        '{{1,"ru","Тестовый модуль"}},"",0,0,00000000-0000-0000-0000-000000000000,0}}}}}}',
        encoding='utf-8-sig'
    )

    # BSL модуль (Module — для CommonModule это UUID.0/text)
    bsl_dir = cm_dir / f'{cm_uuid}.0'
    bsl_dir.mkdir()
    (bsl_dir / 'text').write_text(
        '// Тестовый модуль\nФункция Тест() Экспорт\n    Возврат 1;\nКонецФункции',
        encoding='utf-8-sig'
    )

    # Catalog (тип 20 в V2)
    cat_uuid = '12345678-1234-1234-1234-123456789012'
    (cm_dir / cat_uuid).write_text(
        f'{{1,\n{{20,uuid3,uuid4,\n{{0,\n{{3,\n{{1,0,{cat_uuid}}},"Товары",\n'
        '{{1,"ru","Товары"}},"",0,0,00000000-0000-0000-0000-000000000000,0}}}}}}',
        encoding='utf-8-sig'
    )

    return tmp_path


@pytest.fixture
def sample_cf_structure_v1(tmp_path):
    """Создаёт синтетическую структуру классического формата .cf (V1, старые коды)."""
    cm_uuid = '48659b94-ace8-45f4-a043-6b2731ec6925'
    cm_dir = tmp_path / '1'
    cm_dir.mkdir(parents=True)

    # CommonModule (тип 4 в V1 — классический формат)
    (cm_dir / cm_uuid).write_text(
        f'{{1,\n{{4,uuid1,uuid2,\n{{0,\n{{3,\n{{1,0,{cm_uuid}}},"TestModule",\n'
        '{{1,"ru","Тестовый модуль"}},"",0,0,00000000-0000-0000-0000-000000000000,0}}}}}}',
        encoding='utf-8-sig'
    )

    return tmp_path


# ============================================================================
# ТЕСТЫ TYPE_MAP
# ============================================================================

def test_type_map_has_common_types_v2():
    """TYPE_MAP (V2) содержит основные типы объектов 1С с правильными кодами."""
    assert TYPE_MAP_V2[12] == 'CommonModule'
    assert TYPE_MAP_V2[20] == 'Catalog'
    assert TYPE_MAP_V2[40] == 'Document'
    assert TYPE_MAP_V2[19] == 'InformationRegister'
    assert TYPE_MAP_V2[17] == 'DataProcessor'
    assert TYPE_MAP_V2[18] == 'Report'


def test_type_map_v1_has_classic_codes():
    """TYPE_MAP_V1 содержит классические коды для старых .cf файлов."""
    from v8_metadata_parser import TYPE_MAP_V1
    assert TYPE_MAP_V1[4] == 'CommonModule'
    assert TYPE_MAP_V1[17] == 'Catalog'
    assert TYPE_MAP_V1[18] == 'Document'


# ============================================================================
# ТЕСТЫ ПАРСИНГА (V2 формат)
# ============================================================================

def test_parser_initialization(sample_cf_structure):
    """V8MetadataParser корректно инициализируется."""
    parser = V8MetadataParser(sample_cf_structure)
    assert parser.objects_dir.exists()
    assert parser.objects_dir.name == '1'
    # Кэш должен содержать UUID с BSL модулем
    assert '48659b94-ace8-45f4-a043-6b2731ec6925' in parser._modules_cache


def test_parse_all(sample_cf_structure):
    """parse_all возвращает все объекты метаданных."""
    parser = V8MetadataParser(sample_cf_structure)
    objects = parser.parse_all()

    assert len(objects) == 2  # CommonModule + Catalog

    # Проверим что оба типа найдены
    type_names = [obj.type_name for obj in objects]
    assert 'CommonModule' in type_names
    assert 'Catalog' in type_names


def test_parse_common_module(sample_cf_structure):
    """Парсинг CommonModule — имя, синоним, BSL модуль."""
    parser = V8MetadataParser(sample_cf_structure)
    objects = parser.parse_all()

    cm = next(obj for obj in objects if obj.type_name == 'CommonModule')

    assert cm.uuid == '48659b94-ace8-45f4-a043-6b2731ec6925'
    assert cm.type_code == 12
    assert cm.name == 'TestModule'
    assert cm.synonym == 'Тестовый модуль'
    # В V2 формате UUID.0/text → 'Module' (не 'ObjectModule')
    assert 'Module' in cm.bsl_modules
    assert 'Тест' in cm.bsl_modules['Module']


def test_parse_catalog(sample_cf_structure):
    """Парсинг Catalog — имя, синоним."""
    parser = V8MetadataParser(sample_cf_structure)
    objects = parser.parse_all()

    cat = next(obj for obj in objects if obj.type_name == 'Catalog')

    assert cat.uuid == '12345678-1234-1234-1234-123456789012'
    assert cat.type_code == 20
    assert cat.name == 'Товары'
    assert cat.synonym == 'Товары'


def test_get_common_modules(sample_cf_structure):
    """get_common_modules возвращает только общие модули."""
    parser = V8MetadataParser(sample_cf_structure)
    cms = parser.get_common_modules()

    assert len(cms) == 1
    assert cms[0].type_name == 'CommonModule'
    assert cms[0].name == 'TestModule'


def test_get_objects_by_type(sample_cf_structure):
    """get_objects_by_type фильтрует по типу."""
    parser = V8MetadataParser(sample_cf_structure)

    catalogs = parser.get_objects_by_type('Catalog')
    assert len(catalogs) == 1
    assert catalogs[0].name == 'Товары'

    reports = parser.get_objects_by_type('Report')
    assert len(reports) == 0


def test_get_stats(sample_cf_structure):
    """get_stats возвращает корректную статистику."""
    parser = V8MetadataParser(sample_cf_structure)
    stats = parser.get_stats()

    assert stats['total_objects'] == 2
    assert stats['total_bsl_modules'] == 1  # только у CommonModule
    assert 'CommonModule' in stats['by_type']
    assert stats['by_type']['CommonModule'] == 1


def test_bsl_modules_extraction(sample_cf_structure):
    """BSL модули извлекаются правильно."""
    parser = V8MetadataParser(sample_cf_structure)
    objects = parser.parse_all()

    cm = next(obj for obj in objects if obj.type_name == 'CommonModule')

    # В V2 UUID.0/text → 'Module' (основной модуль CommonModule)
    assert 'Module' in cm.bsl_modules
    code = cm.bsl_modules['Module']
    assert 'Функция Тест' in code
    assert 'Экспорт' in code


def test_parse_object_without_bsl(sample_cf_structure):
    """Объект без BSL модуля парсится корректно."""
    parser = V8MetadataParser(sample_cf_structure)
    objects = parser.parse_all()

    # Catalog не имеет BSL модуля в нашей фикстуре
    cat = next(obj for obj in objects if obj.type_name == 'Catalog')
    assert cat.bsl_modules == {}


def test_parse_skips_service_files(tmp_path):
    """Служебные файлы (version, versions, root) пропускаются."""
    (tmp_path / '1').mkdir()
    (tmp_path / '1' / 'version').write_text('test', encoding='utf-8')
    (tmp_path / '1' / 'versions').write_text('test', encoding='utf-8')
    (tmp_path / '1' / 'root').write_text('test', encoding='utf-8')

    parser = V8MetadataParser(tmp_path)
    objects = parser.parse_all()

    assert len(objects) == 0


def test_parse_handles_invalid_metadata(tmp_path):
    """Невалидные метаданные пропускаются."""
    (tmp_path / '1').mkdir()
    # Файл без паттерна {1,{N, в начале
    (tmp_path / '1' / 'bad-uuid-1234').write_text(
        'not a valid metadata',
        encoding='utf-8'
    )

    parser = V8MetadataParser(tmp_path)
    objects = parser.parse_all()

    assert len(objects) == 0


def test_parser_with_nonexistent_dir(tmp_path):
    """Парсер работает с несуществующей директорией."""
    parser = V8MetadataParser(tmp_path / 'nonexistent')
    objects = parser.parse_all()
    assert objects == []


def test_unknown_type_code(tmp_path):
    """Неизвестный тип кода получает имя Unknown_N."""
    (tmp_path / '1').mkdir()
    uuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    (tmp_path / '1' / uuid).write_text(
        f'{{1,\n{{999,uuid1,uuid2,\n{{0,\n{{3,\n{{1,0,{uuid}}},"Test",\n'
        '{{1,"ru","Тест"}}}}}}}}',
        encoding='utf-8-sig'
    )

    parser = V8MetadataParser(tmp_path)
    objects = parser.parse_all()

    assert len(objects) == 1
    assert objects[0].type_name == 'Unknown_999'


def test_skips_objects_without_name(tmp_path):
    """Объекты без имени (sub-объекты) пропускаются."""
    (tmp_path / '1').mkdir()
    uuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    # Файл с тип кодом, но без имени
    (tmp_path / '1' / uuid).write_text(
        '{1,\n{12,uuid1,uuid2,\n{0,\n{3,\n{0,0}}}}}',
        encoding='utf-8-sig'
    )

    parser = V8MetadataParser(tmp_path)
    objects = parser.parse_all()

    assert len(objects) == 0  # пропущен, т.к. нет имени


def test_alternative_name_pattern(tmp_path):
    """Альтернативный паттерн имени {0,0,UUID},"Name" (FunctionalOption/Constant)."""
    (tmp_path / '1').mkdir()
    uuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    (tmp_path / '1' / uuid).write_text(
        f'{{1,\n{{14,\n{{27,\n{{2,\n{{1,\n{{0,0,{uuid}}},"ИспользоватьЧтоТо",\n'
        '{{1,"ru","Использовать что-то"}}}}}}}}}}',
        encoding='utf-8-sig'
    )

    parser = V8MetadataParser(tmp_path)
    objects = parser.parse_all()

    assert len(objects) == 1
    assert objects[0].name == 'ИспользоватьЧтоТо'
    assert objects[0].type_name == 'FunctionalOption'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
