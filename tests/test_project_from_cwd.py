"""
Тесты для Project.from_cwd() — classmethod для авто-обнаружения корня проекта.

Связано с задачей P0.1: до фикса run_sarif_scan.py вызывал несуществующий метод
Project.from_cwd() и SARIF-отчёт всегда был пустым.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.project import Project


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture
def fake_project_root(tmp_path: Path) -> Path:
    """Создаёт минимальный макет корня проекта с маркером paths.env."""
    (tmp_path / "paths.env").write_text("# fake paths.env\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "1c-ai-dev-env"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Удаляем ONEC_AI_DEV_ENV_ROOT чтобы не влило на тесты."""
    monkeypatch.delenv("ONEC_AI_DEV_ENV_ROOT", raising=False)
    return monkeypatch


# ============================================================================
# Тесты — позитивные сценарии
# ============================================================================


class TestFromCwdDetectsRoot:
    """from_cwd должен находить корень проекта по маркерам."""

    def test_finds_root_via_paths_env(
        self, isolated_env, fake_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Маркер paths.env в стартовой директории — корень найден сразу."""
        monkeypatch.chdir(fake_project_root)
        project = Project.from_cwd()
        assert project.paths.root == fake_project_root

    def test_finds_root_via_pyproject_only(self, isolated_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Если есть только pyproject.toml — это тоже валидный маркер."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        project = Project.from_cwd()
        assert project.paths.root == tmp_path

    def test_finds_root_from_nested_directory(
        self, isolated_env, fake_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Поиск идёт вверх: запуск из src/services/ находит корень."""
        nested = fake_project_root / "src" / "services" / "deep"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        project = Project.from_cwd()
        assert project.paths.root == fake_project_root

    def test_explicit_start_argument_overrides_cwd(
        self, isolated_env, fake_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Параметр start имеет приоритет над Path.cwd()."""
        nested = fake_project_root / "subdir"
        nested.mkdir()
        # chdir в /tmp (точно не корень проекта)
        monkeypatch.chdir(Path("/tmp"))
        project = Project.from_cwd(start=nested)
        assert project.paths.root == fake_project_root

    def test_env_var_overrides_auto_detection(self, fake_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ONEC_AI_DEV_ENV_ROOT имеет высший приоритет."""
        # chdir в /tmp (точно не корень проекта), но env указывает на реальный корень
        monkeypatch.chdir(Path("/tmp"))
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(fake_project_root))
        project = Project.from_cwd()
        assert project.paths.root == fake_project_root.resolve()


# ============================================================================
# Тесты — негативные сценарии
# ============================================================================


class TestFromCwdRaisesWhenRootNotFound:
    """from_cwd должен ЯВНО падать, если корень не найден — это лучше,
    чем молча вернуть cwd и получить пустой SARIF (корень бага P0.1)."""

    def test_raises_in_dir_without_markers(self, isolated_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """В /tmp без маркеров — FileNotFoundError."""
        # /tmp может содержать случайные файлы, используем tmp_path без маркеров
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        with pytest.raises(FileNotFoundError, match="Project root not found"):
            Project.from_cwd()

    def test_raises_with_explicit_start_without_markers(self, isolated_env, tmp_path: Path) -> None:
        """Явный start без маркеров — тоже FileNotFoundError."""
        empty_dir = tmp_path / "no_markers"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="none of"):
            Project.from_cwd(start=empty_dir)

    def test_env_var_pointing_to_nonexistent_dir_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ONEC_AI_DEV_ENV_ROOT указывает на несуществующий путь — FileNotFoundError."""
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(tmp_path / "does_not_exist"))
        with pytest.raises(FileNotFoundError, match="non-existent dir"):
            Project.from_cwd()

    def test_error_message_lists_markers(self, isolated_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Сообщение об ошибке упоминает все маркеры — помогает отладке."""
        empty_dir = tmp_path / "empty2"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        with pytest.raises(FileNotFoundError) as exc_info:
            Project.from_cwd()
        msg = str(exc_info.value)
        assert "paths.env" in msg
        assert "pyproject.toml" in msg
        assert "manifest.json" in msg


# ============================================================================
# Тесты — интеграция с run_sarif_scan.py
# ============================================================================


class TestRunSarifScanIntegration:
    """Интеграционный тест: run_sarif_scan.py должен успешно создать Project
    через from_cwd() и не упасть с AttributeError."""

    def test_run_sarif_scan_initializes_project(self, isolated_env, tmp_path: Path) -> None:
        """run_sarif_scan.py через subprocess — Project.from_cwd() не падает,
        SARIF генерируется без AttributeError."""
        import json
        import subprocess
        import sys

        out_sarif = tmp_path / "out.sarif"
        repo_root = Path(__file__).parent.parent
        # Запускаем с пустым списком файлов — это путь, который раньше падал
        result = subprocess.run(
            [sys.executable, "scripts/run_sarif_scan.py", "", str(out_sarif)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"run_sarif_scan.py failed: stderr={result.stderr}\nstdout={result.stdout}"
        assert out_sarif.exists(), "SARIF file was not created"
        # SARIF должен быть валидным JSON 2.1.0
        data = json.loads(out_sarif.read_text(encoding="utf-8"))
        assert data["version"] == "2.1.0"
        assert "runs" in data
        assert len(data["runs"]) >= 1
