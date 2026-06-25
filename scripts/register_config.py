#!/usr/bin/env python3
"""
register_config.py — Управление конфигурациями 1С в проекте.

Команды:
  list                                    — список всех конфигураций
  add --name <name> --zip <path> --title "Title"  — добавить из ZIP
  register --name <name> --path <path> --title "Title"  — зарегистрировать существующую
  activate --name <name>                  — распаковать из архива
  archive --name <name>                   — запаковать в ZIP и удалить распакованную
  build --name <name>                     — построить все индексы для конфигурации
  build-all                               — построить индексы для всех активных
  remove --name <name>                    — удалить конфигурацию из реестра
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
REGISTRY_FILE = PROJECT_ROOT / 'runtime' / 'config-registry.json'
INDEXES_DIR = PROJECT_ROOT / 'derived' / 'configs'
ARCHIVES_DIR = PROJECT_ROOT / 'data' / 'archives'
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'


def load_registry():
    """Загрузить реестр конфигураций."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"version": "1.0", "configs": {}}


def save_registry(registry):
    """Сохранить реестр."""
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def cmd_list(args):
    """Показать список конфигураций."""
    registry = load_registry()
    configs = registry.get('configs', {})
    
    if not configs:
        print("Нет зарегистрированных конфигураций.")
        return
    
    print(f"{'Имя':<15} {'Версия':<15} {'Статус':<10} {'Объектов':<10} {'Путь':<30}")
    print("-" * 85)
    for name, cfg in sorted(configs.items()):
        print(f"{name:<15} {cfg.get('version', '?'):<15} {cfg.get('status', '?'):<10} "
              f"{cfg.get('objects_count', '?'):<10} {cfg.get('path', cfg.get('archive', '?')):<30}")


def cmd_add(args):
    """Добавить конфигурацию из ZIP."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name in configs:
        print(f"❌ Конфигурация '{args.name}' уже существует. Используй 'remove' сначала.")
        sys.exit(1)
    
    if not os.path.exists(args.zip):
        print(f"❌ ZIP не найден: {args.zip}")
        sys.exit(1)
    
    # Папка для распаковки
    config_dir = str(PROJECT_ROOT / 'data' / 'configs' / args.name)
    os.makedirs(config_dir, exist_ok=True)
    
    # Распаковка
    print(f"Распаковка {args.zip} → {config_dir}...")
    subprocess.run(['unzip', '-q', '-o', args.zip, '-d', config_dir], check=True)
    
    # Читаем свойства из Configuration.xml
    version, vendor = read_config_props(config_dir)
    
    # Считаем объекты
    objects_count = count_objects(config_dir)
    
    # Регистрируем
    configs[args.name] = {
        "name": args.title or args.name,
        "version": version,
        "vendor": vendor,
        "path": f"data/configs/{args.name}",
        "status": "active",
        "objects_count": objects_count,
        "added_at": datetime.now().strftime("%Y-%m-%d"),
    }
    
    save_registry(registry)
    print(f"✅ Конфигурация '{args.name}' добавлена: {args.title}")
    print(f"   Версия: {version}")
    print(f"   Объектов: {objects_count}")
    print(f"   Путь: {config_dir}")
    
    if not args.skip_build:
        print("\nАвтоматическая индексация...")
        build_indexes(args.name, configs[args.name])


def cmd_register(args):
    """Зарегистрировать существующую папку."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name in configs:
        print(f"❌ Конфигурация '{args.name}' уже существует.")
        sys.exit(1)
    
    config_path = args.path
    if not os.path.exists(config_path):
        print(f"❌ Путь не найден: {config_path}")
        sys.exit(1)
    
    version, vendor = read_config_props(config_path)
    objects_count = count_objects(config_path)
    
    configs[args.name] = {
        "name": args.title or args.name,
        "version": version,
        "vendor": vendor,
        "path": args.path if args.path.startswith("data/") or args.path.startswith("/") else f"data/configs/{args.name}",
        "status": "active",
        "objects_count": objects_count,
        "added_at": datetime.now().strftime("%Y-%m-%d"),
    }
    
    save_registry(registry)
    print(f"✅ Конфигурация '{args.name}' зарегистрирована: {args.title}")
    print(f"   Версия: {version}")
    print(f"   Объектов: {objects_count}")
    
    if not args.skip_build:
        print("\nАвтоматическая индексация...")
        build_indexes(args.name, configs[args.name])


def cmd_activate(args):
    """Распаковать конфигурацию из архива."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name not in configs:
        print(f"❌ Конфигурация '{args.name}' не найдена в реестре.")
        sys.exit(1)
    
    cfg = configs[args.name]
    archive_path = cfg.get('archive')
    
    if not archive_path or not os.path.exists(archive_path):
        print(f"❌ Архив не найден: {archive_path}")
        sys.exit(1)
    
    config_dir = str(PROJECT_ROOT / 'data' / 'configs' / args.name)
    os.makedirs(config_dir, exist_ok=True)
    
    print(f"Распаковка {archive_path} → {config_dir}...")
    subprocess.run(['unzip', '-q', '-o', archive_path, '-d', config_dir], check=True)
    
    cfg['path'] = f"config-{args.name}"
    cfg['status'] = 'active'
    save_registry(registry)
    
    print(f"✅ Конфигурация '{args.name}' активирована.")
    
    if not args.skip_build:
        print("\nИндексация...")
        build_indexes(args.name, cfg)


def cmd_archive(args):
    """Запаковать конфигурацию в ZIP и удалить распакованную."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name not in configs:
        print(f"❌ Конфигурация '{args.name}' не найдена.")
        sys.exit(1)
    
    cfg = configs[args.name]
    config_path = cfg.get('path')
    
    if not config_path or not os.path.exists(config_path):
        print(f"❌ Папка не найдена: {config_path}")
        sys.exit(1)
    
    os.makedirs(ARCHIVES_DIR, exist_ok=True)
    archive_path = str(ARCHIVES_DIR / f"{args.name}_full.zip")
    
    print(f"Упаковка {config_path} → {archive_path}...")
    subprocess.run(['zip', '-q', '-r', archive_path, '.'], cwd=config_path, check=True)
    
    # Удаляем распакованную
    shutil.rmtree(config_path)
    
    cfg['archive'] = archive_path
    cfg['path'] = None
    cfg['status'] = 'archived'
    save_registry(registry)
    
    print(f"✅ Конфигурация '{args.name}' архивирована.")


def cmd_build(args):
    """Построить индексы для конфигурации."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name not in configs:
        print(f"❌ Конфигурация '{args.name}' не найдена.")
        sys.exit(1)
    
    build_indexes(args.name, configs[args.name])


def cmd_build_all(args):
    """Построить индексы для всех активных конфигураций."""
    registry = load_registry()
    configs = registry['configs']
    
    for name, cfg in configs.items():
        if cfg.get('status') == 'active':
            print(f"\n{'='*60}")
            print(f"Индексация: {name} ({cfg.get('name', '')})")
            print(f"{'='*60}")
            build_indexes(name, cfg)


def cmd_remove(args):
    """Удалить конфигурацию из реестра."""
    registry = load_registry()
    configs = registry['configs']
    
    if args.name not in configs:
        print(f"❌ Конфигурация '{args.name}' не найдена.")
        sys.exit(1)
    
    del configs[args.name]
    save_registry(registry)
    print(f"✅ Конфигурация '{args.name}' удалена из реестра.")


# === Вспомогательные функции ===

def read_config_props(config_dir):
    """Читает версию и поставщика из Configuration.xml."""
    xml_path = os.path.join(config_dir, 'Configuration.xml')
    if not os.path.exists(xml_path):
        return ('unknown', '')
    
    import xml.etree.ElementTree as ET
    
    def strip_ns(tag):
        return tag.split('}')[1] if '}' in tag else tag
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        cfg = None
        for child in root:
            if strip_ns(child.tag) == 'Configuration':
                cfg = child
                break
        if cfg is None:
            return ('unknown', '')
        
        props = None
        for child in cfg:
            if strip_ns(child.tag) == 'Properties':
                props = child
                break
        if props is None:
            return ('unknown', '')
        
        version = ''
        vendor = ''
        for child in props:
            tag = strip_ns(child.tag)
            if tag == 'Version':
                version = child.text or ''
            elif tag == 'Vendor':
                vendor = child.text or ''
        
        return (version, vendor)
    except Exception:
        return ('unknown', '')


def count_objects(config_dir):
    """Подсчёт объектов по директориям."""
    count = 0
    type_dirs = ['Catalogs', 'Documents', 'Enums', 'Constants', 'CommonModules',
                 'InformationRegisters', 'AccumulationRegisters', 'Reports',
                 'DataProcessors', 'CommonForms', 'CommonTemplates', 'CommonCommands',
                 'CommonPictures', 'Roles', 'Subsystems', 'EventSubscriptions',
                 'ScheduledJobs', 'DefinedTypes', 'FunctionalOptions',
                 'ExchangePlans', 'ChartsOfCharacteristicTypes', 'HTTPServices',
                 'WebServices', 'XDTOPackages', 'FilterCriteria', 'SessionParameters',
                 'CommandGroups', 'SettingsStorages', 'Styles', 'StyleItems',
                 'DocumentJournals', 'DocumentNumerators', 'Sequences',
                 'BusinessProcesses', 'Tasks', 'FunctionalOptionsParameters',
                 'CommonAttributes', 'WSReferences']
    
    for type_dir in type_dirs:
        path = os.path.join(config_dir, type_dir)
        if os.path.isdir(path):
            for item in os.listdir(path):
                if os.path.isdir(os.path.join(path, item)):
                    count += 1
    
    return count


def build_indexes(name, cfg):
    """Построить все индексы для конфигурации."""
    config_path = cfg.get('path')
    if not config_path or not os.path.exists(config_path):
        print(f"  ⚠️ Папка не найдена: {config_path}")
        return
    
    full_path = str(PROJECT_ROOT / config_path) if not os.path.isabs(config_path) else config_path
    os.makedirs(INDEXES_DIR, exist_ok=True)
    
    # 1. Индекс метаданных
    import os as _os
    derived_dir = str(PROJECT_ROOT / 'derived' / 'configs' / name)
    _os.makedirs(derived_dir, exist_ok=True)
    index_md = _os.path.join(derived_dir, 'index.md')
    print(f"\n  📊 Индекс метаданных → {index_md}")
    script = str(SCRIPTS_DIR / 'build_config_index_generic.py')
    result = subprocess.run(
        ['python3', script, full_path, index_md, cfg.get('name', name)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"     ✅ Готово")
    else:
        print(f"     ❌ Ошибка: {result.stderr[:200]}")
    
    # 2. API справочник (если есть CommonModules)
    common_modules = os.path.join(full_path, 'CommonModules')
    if os.path.isdir(common_modules):
        api_md = _os.path.join(derived_dir, 'api-reference.md')
        api_json = _os.path.join(derived_dir, 'api-reference.json')
        print(f"\n  📚 API справочник → {api_md}")
        script = str(SCRIPTS_DIR / 'build_api_reference.py')
        if os.path.exists(script):
            result = subprocess.run(
                ['python3', script, '--config', name, '--config-dir', full_path,
                 '--output-md', api_md, '--output-json', api_json,
                 '--title', cfg.get('name', name)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"     ✅ Готово")
            else:
                print(f"     ❌ Ошибка: {result.stderr[:200]}")
        else:
            print(f"     ⚠️ build_api_reference.py не найден")
    
    # Обновляем реестр
    registry = load_registry()
    if name in registry['configs']:
        if os.path.exists(index_md):
            registry['configs'][name]['index_file'] = f'derived/configs/{name}/index.md'
        if os.path.isdir(common_modules) and os.path.exists(api_md if 'api_md' in dir() else ''):
            registry['configs'][name]['api_reference'] = f'derived/configs/{name}/api-reference.md'
        save_registry(registry)


def main():
    parser = argparse.ArgumentParser(description='Управление конфигурациями 1С')
    subparsers = parser.add_subparsers(dest='command')
    
    # list
    subparsers.add_parser('list', help='Список конфигураций')
    
    # add
    p_add = subparsers.add_parser('add', help='Добавить из ZIP')
    p_add.add_argument('--name', required=True)
    p_add.add_argument('--zip', required=True)
    p_add.add_argument('--title', default='')
    p_add.add_argument('--skip-build', action='store_true')
    
    # register
    p_reg = subparsers.add_parser('register', help='Зарегистрировать существующую папку')
    p_reg.add_argument('--name', required=True)
    p_reg.add_argument('--path', required=True)
    p_reg.add_argument('--title', default='')
    p_reg.add_argument('--skip-build', action='store_true')
    
    # activate
    p_act = subparsers.add_parser('activate', help='Распаковать из архива')
    p_act.add_argument('--name', required=True)
    p_act.add_argument('--skip-build', action='store_true')
    
    # archive
    p_arch = subparsers.add_parser('archive', help='Запаковать в ZIP')
    p_arch.add_argument('--name', required=True)
    
    # build
    p_build = subparsers.add_parser('build', help='Построить индексы')
    p_build.add_argument('--name', required=True)
    
    # build-all
    subparsers.add_parser('build-all', help='Индексы для всех активных')
    
    # remove
    p_rm = subparsers.add_parser('remove', help='Удалить из реестра')
    p_rm.add_argument('--name', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'list':
        cmd_list(args)
    elif args.command == 'add':
        cmd_add(args)
    elif args.command == 'register':
        cmd_register(args)
    elif args.command == 'activate':
        cmd_activate(args)
    elif args.command == 'archive':
        cmd_archive(args)
    elif args.command == 'build':
        cmd_build(args)
    elif args.command == 'build-all':
        cmd_build_all(args)
    elif args.command == 'remove':
        cmd_remove(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
