#!/usr/bin/env python3
"""
Перестроение api-reference для всех 5 конфигураций.
"""

import subprocess
import sys
import time
from pathlib import Path

# Конфигурации для обработки
CONFIGS = [
    {
        "name": "ut11",
        "title": "Управление торговлей 11",
        "config_dir": "/home/z/my-project/repo_work/data/configs/ut11",
    },
    {
        "name": "edo2",
        "title": "ЭДО 2",
        "config_dir": "/home/z/my-project/repo_work/data/configs/edo2",
    },
    {
        "name": "edo3",
        "title": "ЭДО 3",
        "config_dir": "/home/z/my-project/repo_work/data/configs/edo3",
    },
    {
        "name": "unp",
        "title": "УНП",
        "config_dir": "/home/z/my-project/repo_work/data/configs/unp",
    },
    {
        "name": "obhod",
        "title": "Обход",
        "config_dir": "/home/z/my-project/repo_work/data/configs/obhod",
    },
]


def build_config(config):
    """Перестраивает api-reference для одной конфигурации."""
    name = config["name"]
    title = config["title"]
    config_dir = config["config_dir"]

    derived_dir = Path(f"/home/z/my-project/repo_work/derived/configs/{name}")
    derived_dir.mkdir(parents=True, exist_ok=True)

    output_md = derived_dir / "api-reference.md"
    output_json = derived_dir / "api-reference.json"

    print(f"\n{'=' * 60}")
    print(f"Сборка api-reference: {name} ({title})")
    print(f"  config_dir: {config_dir}")
    print(f"  output_json: {output_json}")
    print(f"{'=' * 60}")

    if not Path(config_dir).exists():
        print(f"  ❌ Папка конфигурации не найдена: {config_dir}")
        return None

    start = time.time()
    result = subprocess.run(
        [
            sys.executable,
            "/home/z/my-project/repo_work/scripts/build_api_reference.py",
            "--config",
            name,
            "--config-dir",
            config_dir,
            "--output-md",
            str(output_md),
            "--output-json",
            str(output_json),
            "--title",
            title,
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"  ✅ Успешно за {elapsed:.1f} сек")
        # Show last 15 lines of output
        for line in result.stdout.split("\n")[-15:]:
            print(f"    {line}")
        return output_json
    else:
        print("  ❌ Ошибка:")
        print(f"  stdout: {result.stdout[-500:]}")
        print(f"  stderr: {result.stderr[-500:]}")
        return None


def main():
    print("Перестроение api-reference для всех 5 конфигураций")
    print("=" * 60)

    results = {}
    for config in CONFIGS:
        result = build_config(config)
        results[config["name"]] = result is not None

    print("\n" + "=" * 60)
    print("Итоги:")
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    # Also build code-search-index for each config
    print("\n" + "=" * 60)
    print("Сборка code-search-index...")
    for config in CONFIGS:
        name = config["name"]
        if not results.get(name):
            continue
        print(f"\n--- {name} ---")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "search-code",
                "--rebuild",
                "--config",
                name,
            ],
            cwd="/home/z/my-project/repo_work",
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print("  ✅ code-search-index построен")
            for line in result.stdout.split("\n")[-5:]:
                if line.strip():
                    print(f"    {line}")
        else:
            print("  ❌ Ошибка:")
            print(f"  stderr: {result.stderr[-500:]}")


if __name__ == "__main__":
    main()
