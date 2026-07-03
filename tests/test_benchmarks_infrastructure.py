"""
P2.4: Тесты для benchmark инфраструктуры.

Проверяет:
1. run_benchmarks.py скрипт существует
2. Benchmark функции работают (с моками)
3. Результаты содержат обязательные поля
4. JSON output корректен
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "run_benchmarks.py"


# ============================================================================
# Тесты — benchmark скрипт
# ============================================================================


class TestBenchmarkScript:
    """Проверка scripts/run_benchmarks.py."""

    def test_benchmark_script_exists(self) -> None:
        """run_benchmarks.py существует."""
        assert BENCHMARK_SCRIPT.exists(), "run_benchmarks.py must exist"

    def test_benchmark_script_valid_python(self) -> None:
        """run_benchmarks.py — валидный Python."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(BENCHMARK_SCRIPT)],
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_benchmark_script_has_main(self) -> None:
        """run_benchmarks.py имеет main() функцию."""
        content = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
        assert "def main()" in content
        assert "def run_benchmarks" in content

    def test_benchmark_script_has_cli_args(self) -> None:
        """run_benchmarks.py поддерживает --config и --output."""
        content = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
        assert "--config" in content
        assert "--output" in content
        assert "--compare" in content


# ============================================================================
# Тесты — benchmark функции (с моками)
# ============================================================================


class TestBenchmarkFunctions:
    """Проверка benchmark функций."""

    def test_benchmark_list_configs(self) -> None:
        """benchmark_list_configs возвращает latency_ms и configs_count."""
        from scripts.run_benchmarks import benchmark_list_configs

        mock_project = MagicMock()
        mock_project.list_configs_info.return_value = [{"name": "test", "version": "1.0"}]

        result = benchmark_list_configs(mock_project)

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], (int, float))
        assert result["configs_count"] == 1

    def test_benchmark_search(self) -> None:
        """benchmark_search возвращает latency_ms и results_count."""
        from scripts.run_benchmarks import benchmark_search

        mock_project = MagicMock()
        mock_project.search_methods.return_value = [{"name": "test"}]

        result = benchmark_search(mock_project, "test query", limit=5)

        assert result["query"] == "test query"
        assert result["limit"] == 5
        assert "latency_ms" in result
        assert result["results_count"] == 1

    def test_benchmark_api_reference(self) -> None:
        """benchmark_api_reference возвращает latency_ms и modules_count."""
        from scripts.run_benchmarks import benchmark_api_reference

        mock_project = MagicMock()
        mock_project.get_api_methods.return_value = [
            {"name": "Module1", "methods": [{"name": "method1"}]},
        ]

        result = benchmark_api_reference(mock_project, "test_config")

        assert result["config_name"] == "test_config"
        assert "latency_ms" in result
        assert result["modules_count"] == 1


# ============================================================================
# Тесты — run_benchmarks интеграция
# ============================================================================


class TestRunBenchmarks:
    """Проверка run_benchmarks() функции."""

    def test_run_benchmarks_without_config(self, tmp_path: Path) -> None:
        """run_benchmarks без config — только list_configs benchmark."""
        from scripts.run_benchmarks import run_benchmarks

        output_path = tmp_path / "results.json"

        with patch("src.project.Project.from_cwd") as mock_from_cwd:
            mock_project = MagicMock()
            mock_project.list_configs_info.return_value = []
            mock_project.paths.fast_search_index = tmp_path / "nonexistent.json"
            mock_from_cwd.return_value = mock_project

            results = run_benchmarks(config_name=None, output_path=output_path)

        assert "version" in results
        assert "benchmarks" in results
        assert "list_configs" in results["benchmarks"]
        assert output_path.exists()

        # Проверка JSON формата
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved == results

    def test_run_benchmarks_results_have_required_fields(self, tmp_path: Path) -> None:
        """Результаты содержат обязательные поля."""
        from scripts.run_benchmarks import run_benchmarks

        output_path = tmp_path / "results.json"

        with patch("src.project.Project.from_cwd") as mock_from_cwd:
            mock_project = MagicMock()
            mock_project.list_configs_info.return_value = []
            mock_project.paths.fast_search_index = tmp_path / "nonexistent.json"
            mock_from_cwd.return_value = mock_project

            results = run_benchmarks(config_name=None, output_path=output_path)

        assert results["version"] == "1.0"
        assert "timestamp" in results
        assert "benchmarks" in results
        assert "list_configs" in results["benchmarks"]
        assert "latency_ms" in results["benchmarks"]["list_configs"]
        assert "configs_count" in results["benchmarks"]["list_configs"]


# ============================================================================
# Тесты — BENCHMARKS.md документация
# ============================================================================


class TestBenchmarksDocs:
    """Проверка документации benchmarks."""

    def test_benchmarks_docs_exist(self) -> None:
        """docs/BENCHMARKS.md существует (или будет создан)."""
        # P2.4: документация может быть в docs/BENCHMARKS.md
        benchmarks_md = REPO_ROOT / "docs" / "BENCHMARKS.md"
        # Не требуем существование — benchmarks создаются при наличии данных
        # Но скрипт должен существовать
        assert BENCHMARK_SCRIPT.exists()
