"""
Тесты для GitHubReleases сервиса.
Мокаем subprocess.run чтобы не делать реальные запросы к GitHub API.
"""
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.services.github_releases import GitHubReleases, ReleaseInfo, DEFAULT_RELEASE_TAG


@pytest.fixture
def mock_paths(tmp_path):
    paths = MagicMock()
    paths.root = tmp_path
    return paths


@pytest.fixture
def gh(mock_paths):
    """GitHubReleases с замоканным repo и token."""
    return GitHubReleases(mock_paths, repo="user/repo", token="<TEST_TOKEN>")


# ============ ReleaseInfo ============

class TestReleaseInfo:
    def test_from_api_basic(self):
        data = {
            "tag_name": "data-package",
            "name": "Test Release",
            "html_url": "https://github.com/user/repo/releases/tag/data-package",
            "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
            "assets": [{"name": "package.zip", "size": 1048576}],
            "created_at": "2026-01-01T00:00:00Z",
        }
        info = ReleaseInfo.from_api(data)
        assert info.tag == "data-package"
        assert info.name == "Test Release"
        assert info.url == "https://github.com/user/repo/releases/tag/data-package"
        # upload_url без {?name,label}
        assert "{?name" not in info.upload_url
        assert info.assets == data["assets"]
        assert info.size_mb == 1.0

    def test_from_api_empty(self):
        info = ReleaseInfo.from_api({})
        assert info.tag == ""
        assert info.name == ""
        assert info.assets == []
        assert info.size_mb == 0.0


# ============ is_configured ============

class TestIsConfigured:
    def test_configured(self, gh):
        assert gh.is_configured() is True

    def test_no_token(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="user/repo", token="")
        assert gh.is_configured() is False

    def test_no_repo(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="", token="<YOUR_GITHUB_TOKEN>")
        assert gh.is_configured() is False

    def test_from_env(self, mock_paths):
        with patch.dict('os.environ', {'GITHUB_TOKEN': '<ENV_TOKEN>'}):
            gh = GitHubReleases(mock_paths, repo="user/repo")
            assert gh._token == '<ENV_TOKEN>'


# ============ _detect_repo ============

class TestDetectRepo:
    def test_detect_https(self, mock_paths):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/Pradushkoai/1c-ai-dev-env.git\n",
            )
            gh = GitHubReleases(mock_paths, token="<YOUR_GITHUB_TOKEN>")
            assert gh._repo == "Pradushkoai/1c-ai-dev-env"

    def test_detect_ssh(self, mock_paths):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="git@github.com:Pradushkoai/1c-ai-dev-env.git\n",
            )
            gh = GitHubReleases(mock_paths, token="<YOUR_GITHUB_TOKEN>")
            assert gh._repo == "Pradushkoai/1c-ai-dev-env"

    def test_detect_with_token_in_url(self, mock_paths):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://<YOUR_GITHUB_TOKEN>@github.com/Pradushkoai/1c-ai-dev-env.git\n",
            )
            gh = GitHubReleases(mock_paths, token="<YOUR_GITHUB_TOKEN>")
            assert gh._repo == "Pradushkoai/1c-ai-dev-env"

    def test_detect_failure_returns_empty(self, mock_paths):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            gh = GitHubReleases(mock_paths, token="<YOUR_GITHUB_TOKEN>")
            assert gh._repo == ""


# ============ get_release ============

class TestGetRelease:
    def test_get_existing_release(self, gh):
        # Мокаем curl ответ
        mock_response = json.dumps({
            "tag_name": "data-package",
            "name": "Test",
            "html_url": "https://github.com/user/repo/releases/tag/data-package",
            "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
            "assets": [],
            "created_at": "2026-01-01T00:00:00Z",
        }) + "\n200"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_response, returncode=0)
            release = gh.get_release()

        assert release is not None
        assert release.tag == "data-package"

    def test_get_missing_release(self, gh):
        # 404 — релиз не найден
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='{"message": "Not Found"}\n404', returncode=0)
            release = gh.get_release()
        assert release is None

    def test_not_configured_returns_none(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="", token="")
        assert gh.get_release() is None


# ============ push ============

class TestPush:
    def test_push_not_configured(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="", token="")
        result = gh.push()
        assert result["success"] is False
        assert "GITHUB_TOKEN" in result["error"]

    def test_push_package_missing(self, gh, tmp_path):
        # Пакета нет
        result = gh.push(package_path=tmp_path / "nonexistent.zip")
        assert result["success"] is False
        assert "не найден" in result["error"]

    def test_push_creates_new_release(self, gh, tmp_path):
        # Создадим фейковый пакет
        package = tmp_path / "package.zip"
        package.write_bytes(b"fake zip content")

        # Сначала GET release → 404 (нет)
        # Затем POST /releases → 201 (создан)
        # Затем POST upload → 201 (asset загружен)
        responses = [
            MagicMock(stdout='{"message": "Not Found"}\n404', returncode=0),  # GET release
            MagicMock(stdout=json.dumps({
                "tag_name": "data-package",
                "html_url": "https://github.com/user/repo/releases/tag/data-package",
                "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
                "assets": [],
            }) + "\n201", returncode=0),  # POST create
            MagicMock(stdout=json.dumps({
                "name": "1c-ai-data-package.zip",
                "browser_download_url": "https://github.com/user/repo/releases/download/data-package/1c-ai-data-package.zip",
                "id": 42,
            }) + "\n201", returncode=0),  # POST upload
        ]

        with patch('subprocess.run', side_effect=responses):
            result = gh.push(package_path=package)

        assert result["success"] is True
        assert result["size_mb"] > 0
        assert result["tag"] == "data-package"
        assert "releases/download" in result["asset_url"]

    def test_push_updates_existing_release(self, gh, tmp_path):
        package = tmp_path / "package.zip"
        package.write_bytes(b"updated content")

        # GET release → 200 (есть, с одним asset)
        # DELETE asset → 204
        # POST upload → 201
        responses = [
            MagicMock(stdout=json.dumps({
                "tag_name": "data-package",
                "html_url": "https://github.com/user/repo/releases/tag/data-package",
                "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
                "assets": [{"id": 99, "name": "1c-ai-data-package.zip"}],
            }) + "\n200", returncode=0),
            MagicMock(stdout='\n204', returncode=0),  # DELETE
            MagicMock(stdout=json.dumps({
                "name": "1c-ai-data-package.zip",
                "browser_download_url": "https://github.com/user/repo/releases/download/data-package/1c-ai-data-package.zip",
                "id": 100,
            }) + "\n201", returncode=0),
        ]

        with patch('subprocess.run', side_effect=responses):
            result = gh.push(package_path=package)

        assert result["success"] is True
        assert result["asset_id"] == 100


# ============ pull ============

class TestPull:
    def test_pull_not_configured(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="", token="")
        result = gh.pull()
        assert result["success"] is False

    def test_pull_release_missing(self, gh):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='{"message": "Not Found"}\n404', returncode=0)
            result = gh.pull()
        assert result["success"] is False
        assert "release-push" in result["error"]

    def test_pull_asset_missing(self, gh):
        # Release есть, но asset с таким именем нет
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout=json.dumps({
                "tag_name": "data-package",
                "html_url": "https://github.com/user/repo/releases/tag/data-package",
                "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
                "assets": [{"name": "other.zip"}],
                "created_at": "2026-01-01T00:00:00Z",
            }) + "\n200", returncode=0)
            result = gh.pull()
        assert result["success"] is False
        assert "не найден" in result["error"]

    def test_pull_success(self, gh, tmp_path):
        # GET release → 200, с asset
        # GET asset → скачан
        output_path = tmp_path / "download" / "package.zip"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout=json.dumps({
                "tag_name": "data-package",
                "html_url": "https://github.com/user/repo/releases/tag/data-package",
                "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
                "assets": [{
                    "name": "1c-ai-data-package.zip",
                    "url": "https://api.github.com/repos/user/repo/releases/assets/1",
                    "size": 1024,
                }],
                "created_at": "2026-01-01T00:00:00Z",
            }) + "\n200", returncode=0)

            # Мокаем _download_asset
            with patch.object(gh, '_download_asset', return_value=True) as mock_dl:
                # Создаём файл как будто скачан
                def fake_download(url, path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"fake downloaded content")
                    return True
                mock_dl.side_effect = fake_download

                result = gh.pull(output_path=output_path)

        assert result["success"] is True
        assert result["size_mb"] > 0
        assert output_path.exists()


# ============ status ============

class TestStatus:
    def test_status_not_configured(self, mock_paths):
        gh = GitHubReleases(mock_paths, repo="", token="")
        status = gh.status()
        assert status["configured"] is False
        assert status["token_set"] is False

    def test_status_no_release(self, gh):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='{"message": "Not Found"}\n404', returncode=0)
            status = gh.status()
        assert status["configured"] is True
        assert status["release_exists"] is False

    def test_status_with_release(self, gh):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout=json.dumps({
                "tag_name": "data-package",
                "html_url": "https://github.com/user/repo/releases/tag/data-package",
                "upload_url": "https://uploads.github.com/repos/user/repo/releases/1/assets{?name,label}",
                "assets": [{"name": "1c-ai-data-package.zip", "size": 1048576}],
                "created_at": "2026-01-01T00:00:00Z",
            }) + "\n200", returncode=0)
            status = gh.status()
        assert status["configured"] is True
        assert status["release_exists"] is True
        assert status["release_tag"] == "data-package"
        assert status["asset_size_mb"] == 1.0
        assert status["asset_name"] == "1c-ai-data-package.zip"
