#!/usr/bin/env python3
"""
paths.py — Единый источник путей для всех Python-скриптов.

Читает paths.env из корня проекта.
Все скрипты должны использовать: from paths import PATHS

Пример:
    from paths import PATHS
    json_file = PATHS.syntax_helper_index_json
    config_dir = PATHS.config_ut11
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем paths.env
PROJECT_ROOT = Path(__file__).parent.resolve()
ENV_FILE = PROJECT_ROOT / 'paths.env'

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    # Fallback — пытаемся найти paths.env
    for candidate in [
        Path('/home/z/my-project/paths.env'),
        Path.cwd() / 'paths.env',
        Path.cwd().parent / 'paths.env',
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            break


def _get(key, default=''):
    """Получить значение из env с подстановкой переменных."""
    value = os.getenv(key, default)
    # Подставляем ${VAR} ссылки
    while '${' in value:
        start = value.find('${')
        end = value.find('}', start)
        if end == -1:
            break
        var_name = value[start+2:end]
        var_value = os.getenv(var_name, '')
        value = value[:start] + var_value + value[end+1:]
    return value


class Paths:
    """Все пути проекта. Единый источник истины."""

    # === Базовый ===
    project_root: str = _get('PROJECT_ROOT', str(PROJECT_ROOT))

    # === Данные (конфигурации 1С) ===
    config_ut11: str = _get('CONFIG_UT11_DIR', f'{project_root}/config')
    config_priemka: str = _get('CONFIG_PRIEMKA_DIR', f'{project_root}/config-priemka')
    archives_dir: str = _get('ARCHIVES_DIR', f'{project_root}/archives')
    archive_unp: str = _get('ARCHIVE_UNP', f'{archives_dir}/unp_full.zip')

    # === Справочная информация ===
    syntax_helper_dir: str = _get('SYNTAX_HELPER_DIR', f'{project_root}/syntax-helper')
    syntax_repos_dir: str = _get('SYNTAX_REPOS_DIR', f'{project_root}/syntax')

    # === Индексы ===
    indexes_dir: str = _get('INDEXES_DIR', f'{project_root}/indexes')

    syntax_helper_index_json: str = _get('SYNTAX_HELPER_INDEX_JSON', f'{indexes_dir}/syntax-helper-index.json')
    syntax_helper_index_md: str = _get('SYNTAX_HELPER_INDEX_MD', f'{indexes_dir}/syntax-helper-index.md')
    fast_search_index: str = _get('FAST_SEARCH_INDEX', f'{indexes_dir}/fast-search-index.json')
    ut11_api_reference_json: str = _get('UT11_API_REFERENCE_JSON', f'{indexes_dir}/ut11-api-reference.json')
    ut11_api_reference_md: str = _get('UT11_API_REFERENCE_MD', f'{indexes_dir}/ut11-api-reference.md')
    unp_api_reference_json: str = _get('UNP_API_REFERENCE_JSON', f'{indexes_dir}/unp-api-reference.json')
    unp_api_reference_md: str = _get('UNP_API_REFERENCE_MD', f'{indexes_dir}/unp-api-reference.md')

    # === Инструменты ===
    bsl_ls_binary: str = _get('BSL_LS_BINARY', f'{os.path.expanduser("~")}/.local/bin/bsl-language-server')
    bsl_ls_config: str = _get('BSL_LS_CONFIG', f'{project_root}/.bsl-language-server.json')

    # === Runtime ===
    learned_skills_dir: str = _get('LEARNED_SKILLS_DIR', f'{project_root}/learned-skills')
    tmp_dir: str = _get('TMP_DIR', '/tmp/bsl_tmp')
    baseline_dir: str = _get('BASELINE_DIR', '/tmp/bsl_baseline')

    # === Setup ===
    setup_dir: str = _get('SETUP_DIR', f'{project_root}/setup')
    setup_scripts: str = _get('SETUP_SCRIPTS', f'{setup_dir}/scripts')
    setup_configs: str = _get('SETUP_CONFIGS', f'{setup_dir}/configs')
    setup_templates: str = _get('SETUP_TEMPLATES', f'{setup_dir}/templates')

    # === Скрипты ===
    scripts_dir: str = _get('SCRIPTS_DIR', f'{project_root}/scripts')

    # === Конфигурации (список) ===
    @classmethod
    def get_config_path(cls, name):
        """
        Получить путь к конфигурации по имени.
        Имя: 'ut11', 'priemka', 'unp', и т.д.
        """
        mapping = {
            'ut11': cls.config_ut11,
            'priemka': cls.config_priemka,
            'unp': cls.archive_unp,
        }
        # Также проверяем env: CONFIG_<NAME>
        env_key = f'CONFIG_{name.upper()}'
        if env_key in os.environ:
            return _get(env_key)
        return mapping.get(name.lower(), '')

    @classmethod
    def get_api_reference(cls, config_name):
        """
        Получить путь к API-справочнику конфигурации.
        """
        mapping = {
            'ut11': (cls.ut11_api_reference_json, cls.ut11_api_reference_md),
            'unp': (cls.unp_api_reference_json, cls.unp_api_reference_md),
        }
        return mapping.get(config_name.lower(), (None, None))

    @classmethod
    def print_all(cls):
        """Вывести все пути (для отладки)."""
        print("=== Paths ===")
        for attr in sorted(dir(cls)):
            if attr.startswith('_'):
                continue
            val = getattr(cls, attr)
            if isinstance(val, str) and not callable(val):
                exists = '✅' if os.path.exists(val) else '❌'
                print(f"  {exists} {attr} = {val}")

    @classmethod
    def validate(cls):
        """Проверить что все ключевые пути существуют."""
        critical = [
            ('project_root', cls.project_root),
            ('config_ut11', cls.config_ut11),
            ('syntax_helper_dir', cls.syntax_helper_dir),
            ('indexes_dir', cls.indexes_dir),
            ('bsl_ls_binary', cls.bsl_ls_binary),
        ]
        all_ok = True
        for name, path in critical:
            exists = os.path.exists(path)
            icon = '✅' if exists else '❌'
            print(f"  {icon} {name}: {path}")
            if not exists:
                all_ok = False
        return all_ok


# Singleton
PATHS = Paths()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'validate':
        ok = PATHS.validate()
        sys.exit(0 if ok else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'list':
        PATHS.print_all()
    else:
        print("Использование:")
        print("  python3 paths.py list      — показать все пути")
        print("  python3 paths.py validate  — проверить критичные пути")
