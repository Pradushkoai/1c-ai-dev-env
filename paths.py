#!/usr/bin/env python3
"""
paths.py — Единый источник путей для всех Python-скриптов.

4 слоя архитектуры:
  data/      — исходные данные (от пользователя)
  derived/   — производные (генерируются скриптами)
  tools/     — инструменты (клонируются/устанавливаются)
  runtime/   — файлы работы ассистента
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем paths.env из runtime/
PROJECT_ROOT = Path(__file__).parent.parent.resolve() if Path(__file__).parent.name == 'runtime' else Path(__file__).parent.resolve()
ENV_FILE = PROJECT_ROOT / 'runtime' / 'paths.env'

if not ENV_FILE.exists():
    ENV_FILE = PROJECT_ROOT / 'paths.env'

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    for candidate in [
        Path('/home/z/my-project/runtime/paths.env'),
        Path('/home/z/my-project/paths.env'),
        Path.cwd() / 'runtime' / 'paths.env',
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            break


def _get(key, default=''):
    value = os.getenv(key, default)
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
    """Все пути проекта. 4 слоя архитектуры."""

    # === Базовый ===
    project_root: str = _get('PROJECT_ROOT', str(PROJECT_ROOT))

    # === СЛОЙ 1: data/ — ИСХОДНЫЕ ДАННЫЕ ===
    data_dir: str = _get('DATA_DIR', f'{project_root}/data')
    configs_dir: str = _get('CONFIGS_DIR', f'{data_dir}/configs')
    archives_dir: str = _get('ARCHIVES_DIR', f'{data_dir}/archives')
    hbk_dir: str = _get('HBK_DIR', f'{data_dir}/hbk')

    config_ut11: str = _get('CONFIG_UT11', f'{configs_dir}/ut11')
    config_priemka: str = _get('CONFIG_PRIEMKA', f'{configs_dir}/priemka')

    # === СЛОЙ 2: derived/ — ПРОИЗВОДНЫЕ ===
    derived_dir: str = _get('DERIVED_DIR', f'{project_root}/derived')
    derived_configs: str = _get('DERIVED_CONFIGS', f'{derived_dir}/configs')
    derived_platform: str = _get('DERIVED_PLATFORM', f'{derived_dir}/platform')

    syntax_helper_dir: str = _get('SYNTAX_HELPER_DIR', f'{derived_platform}/syntax-helper')
    syntax_helper_index_json: str = _get('SYNTAX_HELPER_INDEX_JSON', f'{derived_platform}/syntax-helper-index.json')
    syntax_helper_index_md: str = _get('SYNTAX_HELPER_INDEX_MD', f'{derived_platform}/syntax-helper-index.md')
    fast_search_index: str = _get('FAST_SEARCH_INDEX', f'{derived_platform}/fast-search-index.json')

    # === СЛОЙ 3: tools/ — ИНСТРУМЕНТЫ ===
    tools_dir: str = _get('TOOLS_DIR', f'{project_root}/tools')
    repos_dir: str = _get('REPOS_DIR', f'{tools_dir}/repos')
    bsl_ls_binary: str = _get('BSL_LS_BINARY', f'{os.path.expanduser("~")}/.local/bin/bsl-language-server')
    bsl_ls_config: str = _get('BSL_LS_CONFIG', f'{project_root}/runtime/.bsl-language-server.json')

    # === СЛОЙ 4: runtime/ — ФАЙЛЫ РАБОТЫ ===
    runtime_dir: str = _get('RUNTIME_DIR', f'{project_root}/runtime')
    session_resume: str = _get('SESSION_RESUME', f'{runtime_dir}/session-resume.md')
    project_context: str = _get('PROJECT_CONTEXT', f'{runtime_dir}/project-context.md')
    soul_md: str = _get('SOUL_MD', f'{runtime_dir}/soul.md')
    user_profile: str = _get('USER_PROFILE', f'{runtime_dir}/user-profile.md')
    worklog: str = _get('WORKLOG', f'{runtime_dir}/worklog.md')
    config_registry: str = _get('CONFIG_REGISTRY', f'{runtime_dir}/config-registry.json')

    # === Learning loop ===
    learned_skills_dir: str = _get('LEARNED_SKILLS_DIR', f'{project_root}/learned-skills')

    # === Временные ===
    tmp_dir: str = _get('TMP_DIR', '/tmp/bsl_tmp')
    baseline_dir: str = _get('BASELINE_DIR', '/tmp/bsl_baseline')

    # === Setup ===
    setup_dir: str = _get('SETUP_DIR', f'{project_root}/setup')
    setup_scripts: str = _get('SETUP_SCRIPTS', f'{setup_dir}/scripts')
    scripts_dir: str = _get('SCRIPTS_DIR', f'{project_root}/scripts')

    # === Методы ===

    @classmethod
    def get_config_path(cls, name):
        """Путь к конфигурации по имени."""
        # Сначала из env
        env_key = f'CONFIG_{name.upper()}'
        if env_key in os.environ:
            return _get(env_key)
        # Потом из registry
        import json
        if os.path.exists(cls.config_registry):
            with open(cls.config_registry) as f:
                registry = json.load(f)
            cfg = registry.get('configs', {}).get(name, {})
            path = cfg.get('path')
            if path:
                return os.path.join(cls.project_root, path) if not os.path.isabs(path) else path
        # Fallback
        mapping = {'ut11': cls.config_ut11, 'priemka': cls.config_priemka}
        return mapping.get(name.lower(), '')

    @classmethod
    def get_derived_config_dir(cls, name):
        """Путь к производным индексам конфигурации."""
        return os.path.join(cls.derived_configs, name)

    @classmethod
    def get_api_reference(cls, config_name):
        """Пути к API-справочнику конфигурации."""
        d = cls.get_derived_config_dir(config_name)
        return (os.path.join(d, 'api-reference.json'), os.path.join(d, 'api-reference.md'))

    @classmethod
    def get_config_index(cls, config_name):
        """Путь к индексу метаданных конфигурации."""
        return os.path.join(cls.get_derived_config_dir(config_name), 'index.md')

    @classmethod
    def print_all(cls):
        """Вывести все пути."""
        print("=== Paths (4-layer architecture) ===")
        for attr in sorted(dir(cls)):
            if attr.startswith('_'):
                continue
            val = getattr(cls, attr)
            if isinstance(val, str) and not callable(val):
                exists = '✅' if os.path.exists(val) else '❌'
                print(f"  {exists} {attr} = {val}")

    @classmethod
    def validate(cls):
        """Проверить критичные пути."""
        critical = [
            ('project_root', cls.project_root),
            ('data_dir', cls.data_dir),
            ('configs_dir', cls.configs_dir),
            ('derived_dir', cls.derived_dir),
            ('tools_dir', cls.tools_dir),
            ('runtime_dir', cls.runtime_dir),
            ('bsl_ls_binary', cls.bsl_ls_binary),
            ('config_registry', cls.config_registry),
        ]
        all_ok = True
        print("=== Validate ===")
        for name, path in critical:
            exists = os.path.exists(path)
            icon = '✅' if exists else '❌'
            print(f"  {icon} {name}: {path}")
            if not exists:
                all_ok = False
        return all_ok


PATHS = Paths()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'validate':
        ok = PATHS.validate()
        sys.exit(0 if ok else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'list':
        PATHS.print_all()
    else:
        print("Использование: python3 paths.py [validate|list]")
