"""
Тесты для P2.15: paths.py удалён как dead code.

До фикса: paths.py (191 строка) присутствовал в репозитории как deprecated
legacy-обёртка над PathManager. Это создавало путаницу — разработчики могли
случайно использовать его в новом коде, и нужно было поддерживать два
источника путей.

После фикса: paths.py удалён, все импорты обновлены на PathManager.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


# ============================================================================
# Тесты — paths.py удалён
# ============================================================================


class TestPathsPyRemoved:
    """paths.py должен быть удалён из репозитория."""

    def test_paths_py_not_in_root(self) -> None:
        """paths.py НЕ должен существовать в корне репозитория."""
        assert not (REPO_ROOT / "paths.py").exists(), "paths.py must be removed (P2.15) — use PathManager instead"

    def test_paths_py_not_in_runtime(self) -> None:
        """paths.py НЕ должен существовать в runtime/."""
        assert not (REPO_ROOT / "runtime" / "paths.py").exists(), "runtime/paths.py must be removed (P2.15)"

    def test_no_paths_module_imports(self) -> None:
        """Ни один Python-файл НЕ должен импортировать paths module.

        Ищем 'from paths import' и 'import paths' во всех .py файлах.
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "-E",
                r"^(from paths|import paths)",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # grep exit code 1 = no matches (что нам и нужно)
        assert result.returncode == 1, f"Found imports of 'paths' module (P2.15 violation):\n{result.stdout}"

    def test_paths_py_not_in_dockerfile(self) -> None:
        """Dockerfile не должен копировать paths.py."""
        dockerfile = REPO_ROOT / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")
        # Не должно быть активной инструкции COPY с paths.py
        import re

        # Ищем COPY ... paths.py ... (не в комментарии)
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "COPY" in stripped and "paths.py" in stripped:
                pytest.fail(f"Dockerfile still copies paths.py: {line}")

    def test_paths_py_not_in_install_sh(self) -> None:
        """install.sh не должен ссылаться на paths.py (кроме комментариев)."""
        install_sh = REPO_ROOT / "install.sh"
        content = install_sh.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Активные команды с paths.py
            if "paths.py" in stripped:
                # Допускаем упоминание в echo-сообщениях, но не в cp/ln
                if any(cmd in stripped for cmd in ("cp ", "ln -sf", "mv ", "rm ")):
                    pytest.fail(f"install.sh line {line_num} still references paths.py: {line}")


# ============================================================================
# Тесты — PathManager работает как замена
# ============================================================================


class TestPathManagerReplacement:
    """PathManager должен предоставлять все пути, которые раньше были в paths.py."""

    def test_path_manager_importable(self) -> None:
        """src.services.path_manager.PathManager должен импортироваться."""
        from src.services.path_manager import PathManager

        assert PathManager is not None

    def test_path_manager_provides_all_key_paths(self) -> None:
        """PathManager предоставляет все ключевые пути."""
        from src.services.path_manager import PathManager

        pm = PathManager()
        # Проверяем основные свойства, которые раньше были в paths.PATHS
        assert hasattr(pm, "root")
        assert hasattr(pm, "data_dir")
        assert hasattr(pm, "derived_dir")
        assert hasattr(pm, "runtime_dir")
        assert hasattr(pm, "syntax_helper_index_json")
        assert hasattr(pm, "fast_search_index")

    def test_scripts_use_path_manager(self) -> None:
        """scripts/build_syntax_helper_index.py и scripts/fast_search_1c.py
        должны использовать PathManager, не paths.py."""
        for script_name in (
            "build_syntax_helper_index.py",
            "fast_search_1c.py",
        ):
            script_path = REPO_ROOT / "scripts" / script_name
            content = script_path.read_text(encoding="utf-8")
            assert "PathManager" in content, f"{script_name} must use PathManager (P2.15)"
            # Не должно быть активного импорта paths
            import re

            active_imports = re.findall(r"^\s*from paths\s+import|^\s*import paths", content, re.MULTILINE)
            assert not active_imports, f"{script_name} still imports paths module: {active_imports}"


# ============================================================================
# Тесты — backward compat (DeprecationWarning больше не нужен)
# ============================================================================


class TestNoDeprecationWarningNeeded:
    """Поскольку paths.py удалён, DeprecationWarning больше не нужен."""

    def test_no_paths_deprecation_warning(self) -> None:
        """При импорте src.services.path_manager не должно быть DeprecationWarning
        про paths.py (он удалён, нечего депрекейтить)."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Ре-импорт
            import importlib

            import src.services.path_manager as pm_module

            importlib.reload(pm_module)
            # Не должно быть warning про paths.py
            paths_warnings = [warning for warning in w if "paths.py" in str(warning.message)]
            assert not paths_warnings, f"Unexpected paths.py deprecation warnings: {paths_warnings}"
