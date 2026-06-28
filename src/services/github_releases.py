"""
GitHub Releases integration — push/pull data package через GitHub Releases.

Решает проблему: диск пересоздаётся между сессиями. DataPackage ZIP можно
загрузить в GitHub Releases (private repo), и при следующей сессии скачать
через 1c-ai data release-pull.

Использует GitHub REST API через curl (не требует gh CLI).

Workflow:
    1. 1c-ai data autosave --include-raw
       → создаёт download/1c-ai-data-package.zip
    2. 1c-ai data release-push
       → загружает ZIP в GitHub Release "data-package"
    3. (новая сессия, диск пересоздан)
    4. 1c-ai data release-pull
       → скачивает ZIP из Release
    5. 1c-ai data autoload
       → восстанавливает данные

Требует:
    - GITHUB_TOKEN в окружении (или ~/.netrc)
    - Репозиторий на GitHub (private рекомендуется — данные User Content)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .path_manager import PathManager


GITHUB_API = "https://api.github.com"
DEFAULT_RELEASE_TAG = "data-package"
DEFAULT_RELEASE_NAME = "1C AI Development Environment — Data Package"
DEFAULT_ASSET_NAME = "1c-ai-data-package.zip"


@dataclass
class ReleaseInfo:
    """Информация о релизе."""
    tag: str
    name: str
    url: str
    upload_url: str
    assets: list[dict]
    created_at: str
    size_mb: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> "ReleaseInfo":
        return cls(
            tag=data.get("tag_name", ""),
            name=data.get("name", ""),
            url=data.get("html_url", ""),
            upload_url=data.get("upload_url", "").split("{")[0],  # remove {?name,label}
            assets=data.get("assets", []),
            created_at=data.get("created_at", ""),
            size_mb=sum(a.get("size", 0) for a in data.get("assets", [])) / 1024 / 1024,
        )


class GitHubReleases:
    """
    Push/pull data package через GitHub Releases (REST API).
    """

    def __init__(self, paths: PathManager, repo: str = "", token: str = ""):
        self._paths = paths
        self._repo = repo or self._detect_repo()
        self._token = token or os.environ.get("GITHUB_TOKEN", "")

    def _detect_repo(self) -> str:
        """Определить repo из git remote origin."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self._paths.root,
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # https://github.com/USER/REPO.git
                if "github.com" in url:
                    # Убираем протокол и auth
                    if "@" in url:
                        url = url.split("@", 1)[1]
                    url = url.replace("https://", "").replace("http://", "").replace("github.com:", "github.com/")
                    url = url.replace("github.com/", "", 1)
                    if url.endswith(".git"):
                        url = url[:-4]
                    return url
        except Exception:
            pass
        return ""

    def _api_call(self, method: str, endpoint: str, data: dict | None = None,
                  accept: str = "application/vnd.github+json") -> tuple[int, dict | str]:
        """Вызвать GitHub API через curl. Возвращает (status_code, response)."""
        url = endpoint if endpoint.startswith("http") else f"{GITHUB_API}{endpoint}"
        cmd = [
            "curl", "-s", "-X", method, url,
            "-H", f"Authorization: Bearer {self._token}",
            "-H", f"Accept: {accept}",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
            "-w", "\\n%{http_code}",  # статус в конце
        ]
        if data is not None:
            cmd.extend(["-H", "Content-Type: application/json",
                        "-d", json.dumps(data)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout.strip()
        # Последняя строка — статус код
        lines = output.rsplit("\n", 1)
        if len(lines) == 2:
            body, status_str = lines
            try:
                status = int(status_str)
            except ValueError:
                return 0, output
        else:
            return 0, output

        try:
            return status, json.loads(body)
        except json.JSONDecodeError:
            return status, body

    def _upload_asset(self, upload_url: str, file_path: Path, asset_name: str) -> tuple[int, dict | str]:
        """Загрузить файл как asset релиза (multipart/form-data через curl)."""
        url = f"{upload_url}?name={asset_name}"
        cmd = [
            "curl", "-s", "-X", "POST", url,
            "-H", f"Authorization: Bearer {self._token}",
            "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
            "-H", "Content-Type: application/zip",
            "--data-binary", f"@{file_path}",
            "-w", "\\n%{http_code}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        output = result.stdout.strip()
        lines = output.rsplit("\n", 1)
        if len(lines) == 2:
            body, status_str = lines
            try:
                status = int(status_str)
            except ValueError:
                return 0, output
        else:
            return 0, output

        try:
            return status, json.loads(body)
        except json.JSONDecodeError:
            return status, body

    def _download_asset(self, asset_url: str, output_path: Path) -> bool:
        """Скачать asset по URL."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "curl", "-sL", "-X", "GET", asset_url,
            "-H", f"Authorization: Bearer {self._token}",
            "-H", "Accept: application/octet-stream",
            "-o", str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        return result.returncode == 0 and output_path.exists()

    # ---- Public API ----

    def is_configured(self) -> bool:
        """Есть ли token и repo?"""
        return bool(self._token) and bool(self._repo)

    def get_release(self, tag: str = DEFAULT_RELEASE_TAG) -> Optional[ReleaseInfo]:
        """Получить информацию о релизе по тегу."""
        if not self.is_configured():
            return None
        status, data = self._api_call("GET", f"/repos/{self._repo}/releases/tags/{tag}")
        if status == 200 and isinstance(data, dict):
            return ReleaseInfo.from_api(data)
        return None

    def list_releases(self) -> list[ReleaseInfo]:
        """Список всех релизов."""
        if not self.is_configured():
            return []
        status, data = self._api_call("GET", f"/repos/{self._repo}/releases")
        if status == 200 and isinstance(data, list):
            return [ReleaseInfo.from_api(r) for r in data]
        return []

    def push(self, package_path: Path | None = None,
             tag: str = DEFAULT_RELEASE_TAG,
             asset_name: str = DEFAULT_ASSET_NAME,
             release_name: str = DEFAULT_RELEASE_NAME,
             body: str = "") -> dict:
        """
        Загрузить data package в GitHub Release.

        Args:
            package_path: Путь к ZIP (по умолчанию download/1c-ai-data-package.zip)
            tag: Тег релиза
            asset_name: Имя файла в релизе
            release_name: Заголовок релиза
            body: Описание релиза

        Returns: {success, release_url, asset_url, size_mb}
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Не настроен GITHUB_TOKEN или repo. Установите GITHUB_TOKEN в окружении.",
            }

        if package_path is None:
            package_path = self._paths.root / "download" / DEFAULT_ASSET_NAME

        if not package_path.exists():
            return {
                "success": False,
                "error": f"Пакет не найден: {package_path}. Сначала: 1c-ai data autosave",
            }

        size_mb = package_path.stat().st_size / 1024 / 1024

        # 1. Найти или создать релиз
        release = self.get_release(tag)
        if release is None:
            # Создать новый
            status, data = self._api_call("POST", f"/repos/{self._repo}/releases", {
                "tag_name": tag,
                "name": release_name,
                "body": body or f"Data package for 1C AI Development Environment\n\nSize: {size_mb:.1f} MB",
                "draft": False,
                "prerelease": False,
                "make_latest": "true",
            })
            if status != 201:
                return {"success": False, "error": f"Не удалось создать release: {status} {data}"}
            release = ReleaseInfo.from_api(data)
        else:
            # Удалить старые assets с тем же именем
            for asset in release.assets:
                if asset.get("name") == asset_name:
                    self._api_call("DELETE", f"/repos/{self._repo}/releases/assets/{asset['id']}")

        # 2. Загрузить asset
        status, data = self._upload_asset(release.upload_url, package_path, asset_name)
        if status not in (201, 202):
            return {"success": False, "error": f"Не удалось загрузить asset: {status} {data}"}

        asset_url = ""
        asset_id = 0
        if isinstance(data, dict):
            asset_url = data.get("browser_download_url", "")
            asset_id = data.get("id", 0)

        return {
            "success": True,
            "release_url": release.url,
            "asset_url": asset_url,
            "asset_id": asset_id,
            "size_mb": size_mb,
            "tag": tag,
        }

    def pull(self, output_path: Path | None = None,
             tag: str = DEFAULT_RELEASE_TAG,
             asset_name: str = DEFAULT_ASSET_NAME) -> dict:
        """
        Скачать data package из GitHub Release.

        Args:
            output_path: Куда сохранить (по умолчанию download/1c-ai-data-package.zip)
            tag: Тег релиза
            asset_name: Имя файла в релизе

        Returns: {success, path, size_mb}
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Не настроен GITHUB_TOKEN или repo.",
            }

        if output_path is None:
            output_path = self._paths.root / "download" / DEFAULT_ASSET_NAME

        release = self.get_release(tag)
        if release is None:
            return {
                "success": False,
                "error": f"Release '{tag}' не найден. Сначала: 1c-ai data release-push",
            }

        # Найти asset
        asset_url = ""
        for asset in release.assets:
            if asset.get("name") == asset_name:
                asset_url = asset.get("url", "")  # API URL для download
                break

        if not asset_url:
            return {
                "success": False,
                "error": f"Asset '{asset_name}' не найден в release '{tag}'",
            }

        ok = self._download_asset(asset_url, output_path)
        if not ok:
            return {"success": False, "error": "Ошибка скачивания"}

        size_mb = output_path.stat().st_size / 1024 / 1024
        return {
            "success": True,
            "path": str(output_path),
            "size_mb": size_mb,
            "tag": tag,
        }

    def status(self) -> dict:
        """Статус GitHub Releases integration."""
        if not self.is_configured():
            return {
                "configured": False,
                "repo": self._repo,
                "token_set": bool(self._token),
            }

        release = self.get_release()
        return {
            "configured": True,
            "repo": self._repo,
            "token_set": True,
            "release_exists": release is not None,
            "release_tag": release.tag if release else None,
            "release_created_at": release.created_at if release else None,
            "release_url": release.url if release else None,
            "asset_size_mb": release.size_mb if release else 0,
            "asset_name": release.assets[0]["name"] if release and release.assets else None,
        }
