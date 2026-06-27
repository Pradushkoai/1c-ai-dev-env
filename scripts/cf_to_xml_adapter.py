#!/usr/bin/env python3
"""
cf_to_xml_adapter.py — Адаптер для построения API-справочника из .cf файлов.

Конвертирует структуру v8unpack (из cf_extractor) в формат, совместимый с
build_api_reference.py (ожидает XML выгрузку Конфигуратора).

Структура v8unpack:
  extracted/1/UUID          — метаданные объекта (структура значений 1С)
  extracted/1/UUID.0/text   — BSL модуль объекта

Конвертированная структура (совместимая с build_api_reference):
  output/CommonModules/<Имя>/
  output/CommonModules/<Имя>.xml      — метаданные в XML формате
  output/CommonModules/<Имя>/Ext/Module.bsl — BSL код

Использование:
    python3 cf_to_xml_adapter.py <extracted_cf_dir> <output_dir>

    # Затем запускаем build_api_reference:
    python3 build_api_reference.py --config <name> --config-dir <output_dir> \\
        --output-md api-reference.md --output-json api-reference.json --title "Title"
"""
from __future__ import annotations

import sys
from pathlib import Path

# Добавляем scripts/ в path
sys.path.insert(0, str(Path(__file__).parent))
from v8_metadata_parser import V8MetadataParser, V8Object


# Свойства CommonModule в формате 1С (для генерации XML)
# Основано на анализе реальных .cf файлов
COMMON_MODULE_PROPS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo>
  <CommonModule>
    <Properties>
      <Name>{name}</Name>
      <Synonym>
        <item>
          <content>{synonym}</content>
        </item>
      </Synonym>
      <Comment>{comment}</Comment>
      <Server>{server}</Server>
      <ClientManagedApplication>{client_managed}</ClientManagedApplication>
      <ClientOrdinaryApplication>{client_ordinary}</ClientOrdinaryApplication>
      <ServerCall>{server_call}</ServerCall>
      <Global>{global}</Global>
      <Privileged>{privileged}</Privileged>
      <ExternalConnection>{external_connection}</ExternalConnection>
      <ReturnValuesReuse>{return_values_reuse}</ReturnValuesReuse>
    </Properties>
  </CommonModule>
</ConfigDumpInfo>"""


def detect_module_properties(metadata_content: str) -> dict:
    """
    Определяет свойства CommonModule из метаданных.
    Возвращает dict с boolean полями.
    """
    # В формате v8unpack свойства хранятся как числа 0/1
    # После имени и синонима идёт последовательность свойств
    # Формат: ...,0,ServerCall,Global,Privileged,ExternalConnection,...

    # По умолчанию все false
    props = {
        'server': 'false',
        'client_managed': 'false',
        'client_ordinary': 'false',
        'server_call': 'false',
        'global': 'false',
        'privileged': 'false',
        'external_connection': 'false',
        'return_values_reuse': 'false',
    }

    # Парсим свойства из метаданных
    # Ищем паттерн: после имени и синонима идёт "",0,0,UUID,0,
    # Затем: ServerCall(0/1),Global(0/1),Privileged(0/1),ExternalConnection(0/1)

    import re
    # Найдём последовательность чисел после синонима
    # Формат: {1,"ru","Синоним"},"",0,0,UUID,0,ServerCall,Global,...
    # Или: {1,"ru","Синоним"},"",0,0,UUID,0,X,Y,...

    # Найдём паттерн с UUID и свойствами после
    props_match = re.search(
        r'\{1,"ru","[^"]*"\},"[^"]*",\d+,\d+,'
        r'[0-9a-f-]{36},\d+'
        r',(\d+),(\d+),(\d+),(\d+)',
        metadata_content,
        re.IGNORECASE
    )
    if props_match:
        # props_match.groups() = (server_call, global, privileged, external_connection)
        # Но порядок может отличаться — проверим по реальным данным
        props['server_call'] = 'true' if props_match.group(1) == '1' else 'false'
        props['global'] = 'true' if props_match.group(2) == '1' else 'false'
        props['privileged'] = 'true' if props_match.group(3) == '1' else 'false'
        props['external_connection'] = 'true' if props_match.group(4) == '1' else 'false'

    # Server и ClientManaged обычно true для серверных модулей
    # Определим по наличию ServerCall
    if props['server_call'] == 'true':
        props['server'] = 'true'
        props['client_managed'] = 'true'

    return props


def convert_cf_to_xml_format(extracted_dir: Path, output_dir: Path) -> int:
    """
    Конвертирует структуру v8unpack в формат, совместимый с build_api_reference.

    Args:
        extracted_dir: Папка с распакованным .cf (через cf_extractor)
        output_dir: Куда положить конвертированную структуру

    Returns:
        Количество конвертированных CommonModules
    """
    parser = V8MetadataParser(extracted_dir)
    common_modules = parser.get_common_modules()

    # Создаём папку CommonModules
    cm_dir = output_dir / 'CommonModules'
    cm_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    for obj in common_modules:
        if not obj.name:
            continue

        # Безопасное имя (заменяем недопустимые символы)
        safe_name = obj.name.replace('/', '_').replace('\\', '_').replace(':', '_')

        # Создаём папку модуля
        module_dir = cm_dir / safe_name / 'Ext'
        module_dir.mkdir(parents=True, exist_ok=True)

        # Генерируем XML метаданных
        props = detect_module_properties(obj.raw_metadata + obj.name)
        # Дополняем свойства из raw_metadata
        full_metadata = obj.raw_metadata
        props_full = detect_module_properties(full_metadata)

        xml_content = COMMON_MODULE_PROPS_TEMPLATE.format(
            name=obj.name,
            synonym=obj.synonym or obj.name,
            comment=obj.comment or '',
            server=props_full['server'],
            client_managed=props_full['client_managed'],
            client_ordinary=props_full['client_ordinary'],
            server_call=props_full['server_call'],
            **{'global': props_full['global']},
            privileged=props_full['privileged'],
            external_connection=props_full['external_connection'],
            return_values_reuse=props_full['return_values_reuse'],
        )

        # Сохраняем XML
        xml_path = cm_dir / f'{safe_name}.xml'
        xml_path.write_text(xml_content, encoding='utf-8')

        # Сохраняем BSL код (если есть)
        if 'ObjectModule' in obj.bsl_modules:
            bsl_path = module_dir / 'Module.bsl'
            bsl_path.write_text(obj.bsl_modules['ObjectModule'], encoding='utf-8')
            converted += 1
        else:
            # Создаём пустой .bsl чтобы build_api_reference не падал
            bsl_path = module_dir / 'Module.bsl'
            bsl_path.write_text('', encoding='utf-8')

    return converted


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 cf_to_xml_adapter.py <extracted_cf_dir> <output_dir>")
        print()
        print("Пример:")
        print("  python3 cf_to_xml_adapter.py /tmp/edo3_full /tmp/edo3_xml")
        print()
        print("Затем запустите build_api_reference:")
        print("  python3 build_api_reference.py --config edo3 --config-dir /tmp/edo3_xml \\")
        print("    --output-md api-reference.md --output-json api-reference.json --title 'ЭДО3'")
        sys.exit(1)

    extracted_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not extracted_dir.exists():
        print(f"❌ Папка не найдена: {extracted_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Конвертация: {extracted_dir}")
    print(f"В: {output_dir}")

    count = convert_cf_to_xml_format(extracted_dir, output_dir)
    print(f"\n✅ Конвертировано CommonModules: {count}")
    print(f"   Каталог: {output_dir / 'CommonModules'}")


if __name__ == "__main__":
    main()
