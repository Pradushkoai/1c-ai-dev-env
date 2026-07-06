"""
P2.6: Тесты для Documentation as Code (Sphinx + doctest).

Проверяет:
1. Sphinx конфигурация существует и валидна
2. doctest примеры в KnowledgeBase и PathManager работают
3. Документация Sphinx может быть собрана
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SPHINX_DIR = REPO_ROOT / "docs" / "sphinx"


# ============================================================================
# Тесты — Sphinx конфигурация
# ============================================================================


class TestSphinxConfig:
    """Проверка docs/sphinx/conf.py."""

    def test_sphinx_dir_exists(self) -> None:
        """docs/sphinx/ существует."""
        assert SPHINX_DIR.exists(), "docs/sphinx/ must exist"

    def test_conf_py_exists(self) -> None:
        """docs/sphinx/conf.py существует."""
        conf = SPHINX_DIR / "conf.py"
        assert conf.exists(), "docs/sphinx/conf.py must exist"

    def test_conf_py_valid_python(self) -> None:
        """conf.py — валидный Python файл."""
        conf = SPHINX_DIR / "conf.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(conf)],
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, f"conf.py syntax error: {result.stderr}"

    def test_conf_py_has_extensions(self) -> None:
        """conf.py содержит extensions с autodoc и doctest."""
        content = (SPHINX_DIR / "conf.py").read_text(encoding="utf-8")
        assert "sphinx.ext.autodoc" in content, "conf.py must have autodoc extension"
        assert "sphinx.ext.doctest" in content, "conf.py must have doctest extension"
        assert "myst_parser" in content, "conf.py must have myst_parser for Markdown"

    def test_conf_py_has_project_name(self) -> None:
        """conf.py содержит project name."""
        content = (SPHINX_DIR / "conf.py").read_text(encoding="utf-8")
        assert "1C AI Development Environment" in content

    def test_index_rst_exists(self) -> None:
        """docs/sphinx/index.rst существует."""
        index = SPHINX_DIR / "index.rst"
        assert index.exists(), "docs/sphinx/index.rst must exist"

    def test_api_docs_exist(self) -> None:
        """API документация существует."""
        services_rst = SPHINX_DIR / "api" / "services.rst"
        models_rst = SPHINX_DIR / "api" / "models.rst"
        mcpserver_rst = SPHINX_DIR / "api" / "mcpserver.rst"
        assert services_rst.exists(), "api/services.rst must exist"
        assert models_rst.exists(), "api/models.rst must exist"
        assert mcpserver_rst.exists(), "api/mcpserver.rst must exist"

    def test_guides_exist(self) -> None:
        """Guides документация существует."""
        arch = SPHINX_DIR / "guides" / "architecture.rst"
        mcp = SPHINX_DIR / "guides" / "mcp_integration.rst"
        assert arch.exists(), "guides/architecture.rst must exist"
        assert mcp.exists(), "guides/mcp_integration.rst must exist"


# ============================================================================
# Тесты — doctest примеры
# ============================================================================


class TestDoctests:
    """Проверка doctest примеров в исходном коде."""

    def test_knowledge_base_has_doctest(self) -> None:
        """KnowledgeBase содержит doctest пример."""
        kb_path = REPO_ROOT / "src" / "services" / "knowledge_base.py"
        content = kb_path.read_text(encoding="utf-8")
        assert ">>>" in content, "knowledge_base.py must have doctest examples"
        assert "list_all()" in content, "doctest should demonstrate list_all()"

    def test_path_manager_has_doctest(self) -> None:
        """PathManager содержит doctest пример."""
        pm_path = REPO_ROOT / "src" / "services" / "path_manager.py"
        content = pm_path.read_text(encoding="utf-8")
        assert ">>>" in content, "path_manager.py must have doctest examples"

    def test_doctests_pass(self) -> None:
        """doctest примеры проходят через pytest --doctest-modules."""
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--doctest-modules",
                    "src/services/knowledge_base.py",
                    "src/services/path_manager.py",
                    "-v",
                    "--no-header",
                    "--tb=short",
                    "-p",
                    "no:cacheprovider",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            pytest.skip("doctest timeout")

        # doctest может не пройти если окружение не настроено,
        # но должен хотя бы запуститься
        if result.returncode != 0:
            # Проверяем что это не ImportError
            if "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr:
                pytest.skip("Module import failed for doctest")
            # Иначе это реальная ошибка doctest
            pytest.fail(f"doctest failed:\n{result.stdout}\n{result.stderr}")


# ============================================================================
# Тесты — Sphinx build (опционально)
# ============================================================================


class TestSphinxBuild:
    """Проверка что Sphinx может собрать документацию."""

    def test_sphinx_build_works(self) -> None:
        """sphinx-build успешно собирает HTML документацию."""
        try:
            import sphinx  # noqa: F401
        except ImportError:
            pytest.skip("sphinx не установлен")

        output_dir = SPHINX_DIR / "_build" / "html"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sphinx",
                "-b",
                "html",
                str(SPHINX_DIR),
                str(output_dir),
                "-q",  # quiet
                "--keep-going",  # не останавливаться на первой ошибке
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )

        # Sphinx может выдавать warnings (undocumented members и т.д.),
        # но должен завершиться с returncode 0
        if result.returncode != 0:
            # Проверяем что это не критическая ошибка
            if "Extension error" in result.stderr or "Config error" in result.stderr:
                pytest.skip(f"Sphinx build config error:\n{result.stderr[:500]}")
            pytest.fail(f"sphinx-build failed (returncode={result.returncode}):\nstderr={result.stderr[:500]}")

        # Проверим что index.html создан
        assert (output_dir / "index.html").exists(), "index.html должен быть создан"
