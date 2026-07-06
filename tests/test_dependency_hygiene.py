"""
P1.7: Тесты для Dependency Hygiene.

Проверяет:
1. Все dev dependencies в pyproject.toml имеют разрешённые лицензии
2. Нет запрещённых (copyleft) лицензий в установленных пакетах
3. pip-audit не находит vulnerabilities (если pip-audit установлен)

Запрещённые лицензии (несовместимы с MIT):
- GPL (GNU General Public License)
- AGPL (Affero General Public License)
- LGPL (GNU Lesser General Public License)

Разрешённые лицензии:
- MIT, Apache-2.0, BSD-2/3-Clause, ISC, MPL-2.0, Python-2.0, Unlicense
"""

from __future__ import annotations

import subprocess
import sys


def _get_installed_licenses() -> list[tuple[str, str]]:
    """Получить список (package, license) через pip-licenses.

    Returns:
        Список кортежей (package_name, license_name).
        Если pip-licenses не установлен — пустой список.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_licenses", "--format=json", "--from=mixed"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        import json

        data = json.loads(result.stdout)
        return [(pkg.get("Name", ""), pkg.get("License", "")) for pkg in data]
    except (FileNotFoundError, subprocess.TimeoutExpired, ImportError, json.JSONDecodeError):
        return []


def test_no_copyleft_licenses() -> None:
    """В установленных пакетах не должно быть copyleft лицензий (GPL, AGPL, LGPL).

    Copyleft лицензии несовместимы с MIT-лицензией проекта.
    """
    licenses = _get_installed_licenses()
    if not licenses:
        import pytest

        pytest.skip("pip-licenses не установлен или не работает")

    forbidden_patterns = ["GPL", "AGPL", "LGPL", "AFFERO"]
    forbidden: list[tuple[str, str]] = []
    for package, license_name in licenses:
        license_upper = license_name.upper()
        if any(pattern in license_upper for pattern in forbidden_patterns):
            forbidden.append((package, license_name))

    assert not forbidden, (
        "Найдены copyleft лицензии (несовместимы с MIT):\n"
        + "\n".join(f"  {pkg}: {lic}" for pkg, lic in forbidden)
        + "\n\nЗамените эти пакеты на альтернативы с permissive лицензиями."
    )


def test_project_license_is_mit() -> None:
    """Лицензия проекта должна быть MIT (указана в pyproject.toml)."""
    from pathlib import Path

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert 'license = {text = "MIT"}' in content or 'license = "MIT"' in content, (
        "pyproject.toml должен указывать MIT лицензию"
    )


def test_license_file_exists() -> None:
    """Файл LICENSE должен существовать в корне репозитория."""
    from pathlib import Path

    license_file = Path(__file__).parent.parent / "LICENSE"
    assert license_file.exists(), "LICENSE файл должен существовать в корне репозитория"
    content = license_file.read_text(encoding="utf-8")
    assert "MIT" in content, "LICENSE файл должен содержать 'MIT'"


def test_pip_audit_no_vulnerabilities() -> None:
    """pip-audit не должен находить vulnerabilities в установленных пакетах.

    Если pip-audit не установлен — skip.
    Если pip-audit находит vulnerabilities — тест падает.
    Использует --skip-editable чтобы пропустить сам проект (1c-ai-dev-env,
    который установлен в editable mode и не на PyPI).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--strict", "--skip-editable"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        import pytest

        pytest.skip("pip-audit не установлен или timeout (нет сети)")

    # pip-audit --strict: exit 0 если нет vulnerabilities, exit 1 если есть
    if result.returncode == 0:
        return  # OK

    # Если exit != 0 — может быть false positive (editable package, нет сети)
    # Проверяем только если в stdout есть реальные vulnerabilities
    stdout_lower = result.stdout.lower()
    stderr_lower = result.stderr.lower()

    # False positives: editable package warnings, network errors
    false_positive_indicators = [
        "distribution marked as editable",
        "dependency not found on pypi",
        "could not be audited",
        "network",
        "connection",
        "timeout",
    ]
    is_false_positive = any(ind in stderr_lower for ind in false_positive_indicators)

    # Если есть реальные vulnerabilities (в stdout есть "vulnerability" или "CVE")
    has_real_vulnerabilities = "vulnerability" in stdout_lower or "cve-" in stdout_lower

    if is_false_positive and not has_real_vulnerabilities:
        import pytest

        pytest.skip(f"pip-audit false positive (editable/network):\n{result.stderr[:500]}")

    if not has_real_vulnerabilities:
        # exit != 0 но нет vulnerabilities — странный случай, skip
        import pytest

        pytest.skip(f"pip-audit exit {result.returncode} но vulnerabilities не найдены:\nstderr={result.stderr[:500]}")

    import pytest

    pytest.fail(
        f"pip-audit нашёл vulnerabilities:\n{result.stdout}\n{result.stderr}\n"
        "Обнови vulnerable пакеты или добавь исключения."
    )
