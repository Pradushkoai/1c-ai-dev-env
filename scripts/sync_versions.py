#!/usr/bin/env python3
"""
sync_versions.py — Синхронизация версий во всех файлах.

Запускается после merge release-please PR, чтобы гарантировать что
manifest.json, README.md и .release-please-manifest.json синхронны.

Использование:
    python3 scripts/sync_versions.py

Exit codes:
    0 — версии уже синхронны или успешно синхронизированы
    1 — ошибка (версия не найдена)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def get_pyproject_version() -> str:
    """Получить версию из pyproject.toml (источник истины)."""
    import tomllib

    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def sync_manifest_json(version: str) -> bool:
    """Синхронизировать version в manifest.json."""
    path = Path("manifest.json")
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data.get("version", "")
    if old != version:
        data["version"] = version
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  manifest.json: {old} → {version}")
        return True
    return False


def sync_readme_badge(version: str) -> bool:
    """Синхронизировать version-X.Y.Z в README.md badge."""
    path = Path("README.md")
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    # Pattern: version-X.Y.Z в badge URL
    new_content = re.sub(r"version-\d+\.\d+\.\d+", f"version-{version}", content)
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        print(f"  README.md badge: → version-{version}")
        return True
    return False


def sync_release_please_manifest(version: str) -> bool:
    """Синхронизировать .release-please-manifest.json."""
    path = Path(".release-please-manifest.json")
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data.get(".", "")
    if old != version:
        data["."] = version
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"  .release-please-manifest.json: {old} → {version}")
        return True
    return False


def main() -> int:
    print("=== Синхронизация версий ===")
    version = get_pyproject_version()
    print(f"Источник истины: pyproject.toml = {version}")

    changed = False
    changed |= sync_manifest_json(version)
    changed |= sync_readme_badge(version)
    changed |= sync_release_please_manifest(version)

    if changed:
        print("\n✅ Версии синхронизированы")
    else:
        print("\n✅ Версии уже синхронны")

    # Финальная проверка
    m = json.load(open("manifest.json"))["version"]
    r = re.search(r"version-(\d+\.\d+\.\d+)", open("README.md").read())
    r = r.group(1) if r else ""
    rp = json.load(open(".release-please-manifest.json"))["."]

    if m != version or r != version or rp != version:
        print(f"❌ Рассинхрон: pyproject={version}, manifest={m}, readme={r}, rp={rp}")
        return 1

    print(f"✅ Все версии = {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
