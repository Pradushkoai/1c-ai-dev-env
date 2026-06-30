#!/usr/bin/env python3
"""pre-commit hook: проверка консистентности версий."""
import sys
import re
import json
import configparser
from pathlib import Path


def check_versions():
    """Проверяет что версии совпадают во всех файлах."""
    errors = []

    # manifest.json
    manifest = Path('manifest.json')
    if manifest.exists():
        manifest_ver = json.load(manifest.open())['version']
    else:
        return ['manifest.json not found']

    # pyproject.toml (TOML format, not INI — используем regex)
    pyproject = Path('pyproject.toml')
    if pyproject.exists():
        content = pyproject.read_text()
        m = re.search(r'version\s*=\s*"([^"]+)"', content)
        pyproject_ver = m.group(1) if m else 'not found'
    else:
        return ['pyproject.toml not found']

    # README.md badge
    readme = Path('README.md')
    if readme.exists():
        m = re.search(r'version-([0-9.]+)', readme.read_text())
        readme_ver = m.group(1) if m else 'not found'
    else:
        readme_ver = 'README.md not found'

    # CHANGELOG.md (первая запись)
    changelog = Path('CHANGELOG.md')
    changelog_ver = 'not found'
    if changelog.exists():
        m = re.search(r'##\s*\[([0-9.]+)\]', changelog.read_text())
        changelog_ver = m.group(1) if m else 'not found'

    # Проверка
    if manifest_ver != pyproject_ver:
        errors.append(f'Version mismatch: manifest={manifest_ver} vs pyproject={pyproject_ver}')

    if manifest_ver != readme_ver:
        errors.append(f'Version mismatch: manifest={manifest_ver} vs README badge={readme_ver}')

    if manifest_ver != changelog_ver:
        errors.append(f'Version mismatch: manifest={manifest_ver} vs CHANGELOG={changelog_ver}')

    return errors


if __name__ == '__main__':
    errors = check_versions()
    if errors:
        for e in errors:
            print(f'❌ {e}', file=sys.stderr)
        sys.exit(1)
    else:
        # Получаем версию для вывода
        manifest_ver = json.load(open('manifest.json'))['version']
        print(f'✅ Versions consistent: {manifest_ver}')
        sys.exit(0)
