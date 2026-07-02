#!/usr/bin/env python3
"""
fork_all_repos.py — Форкает все репозитории из manifest.json на аккаунт пользователя.

Использование:
  python3 fork_all_repos.py --token <GITHUB_PAT>

После форка обновляет manifest.json — заменяет URL на форки.

Стратегия:
  1. Форкаем каждый репозиторий через GitHub API
  2. Обновляем manifest.json — URL → github.com/<USER>/<NAME>
  3. При install.sh клонируем из наших форков (не оригиналов)
  4. Если оригинал обновился — можем синхронизировать форк через GitHub API
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
MANIFEST = PROJECT_ROOT / "setup" / "manifest.json"


def fork_repo(token, owner, repo, user):
    """Форкнуть репозиторий через GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    resp = requests.post(url, headers=headers)

    if resp.status_code == 202:
        # Accepted — форк создаётся асинхронно
        data = resp.json()
        return True, f"https://github.com/{user}/{repo}.git"
    elif resp.status_code == 409:
        # Already exists
        return True, f"https://github.com/{user}/{repo}.git"
    else:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def main():
    parser = argparse.ArgumentParser(description="Форк всех репозиториев из manifest.json")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token")
    parser.add_argument("--user", default=None, help="GitHub username (авто-определение если не указан)")
    parser.add_argument("--update-manifest", action="store_true", help="Обновить manifest.json после форка")
    args = parser.parse_args()

    token = args.token

    # Определяем пользователя
    if not args.user:
        resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if resp.status_code != 200:
            print(f"❌ Не удалось определить пользователя: {resp.text[:200]}")
            sys.exit(1)
        user = resp.json()["login"]
        print(f"GitHub пользователь: {user}")
    else:
        user = args.user

    # Загружаем manifest
    with open(MANIFEST) as f:
        manifest = json.load(f)

    repos = manifest["git_repositories"]
    print(f"Репозиториев к форку: {len(repos)}")
    print()

    # Форкаем
    forked = 0
    failed = 0
    updated_urls = []

    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        url = repo["url"]

        # Парсим owner/repo из URL
        # https://github.com/OWNER/REPO.git
        parts = url.replace("https://github.com/", "").replace(".git", "").split("/")
        if len(parts) < 2:
            print(f"  [{i}/{len(repos)}] ⚠️  {name}: не удалось распарсить URL {url}")
            updated_urls.append((name, url))  # оставляем оригинал
            continue

        owner = parts[0]
        repo_name = parts[1]

        print(f"  [{i}/{len(repos)}] Форк {owner}/{repo_name} → {user}/{repo_name}...", end=" ", flush=True)

        success, result = fork_repo(token, owner, repo_name, user)

        if success:
            print("✅")
            fork_url = f"https://github.com/{user}/{repo_name}.git"
            updated_urls.append((name, fork_url))
            forked += 1
        else:
            print(f"❌ {result}")
            updated_urls.append((name, url))  # оставляем оригинал
            failed += 1

        # Небольшая пауза чтобы не попасть под rate limit
        time.sleep(1)

    print("\n=== ИТОГ ===")
    print(f"  ✅ Форкнуто: {forked}")
    print(f"  ❌ Ошибок: {failed}")

    if args.update_manifest:
        print("\nОбновляю manifest.json...")

        # Обновляем URL
        url_map = {name: url for name, url in updated_urls}
        for repo in repos:
            if repo["name"] in url_map:
                repo["url"] = url_map[repo["name"]]

        # Добавляем метаданные
        manifest["forks"] = {
            "user": user,
            "forked_at": time.strftime("%Y-%m-%d"),
            "count": forked,
        }

        with open(MANIFEST, "w") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"✅ manifest.json обновлён — URL указывают на форки {user}")

        # Выводим новые URL
        print("\nНовые URL в manifest:")
        for repo in repos:
            print(f"  {repo['name']:<35} → {repo['url']}")


if __name__ == "__main__":
    main()
