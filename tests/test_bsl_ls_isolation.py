"""
P2.2: Тесты для BSL LS isolation.

Проверяет:
1. BSL_LS_TIMEOUT, BSL_LS_MAX_RETRIES, BSL_LS_RETRY_DELAYS константы
2. _run_analysis retry логика (mocks)
3. bsl_ls_with_fallback декоратор
4. Timeout handling
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.bsl_analyzer import (
    BSL_LS_MAX_RETRIES,
    BSL_LS_RETRY_DELAYS,
    BSL_LS_TIMEOUT,
    AnalysisResult,
    BSLAnalyzer,
    bsl_ls_with_fallback,
)


# ============================================================================
# Тесты — константы изоляции
# ============================================================================


class TestBSLLSIsolationConstants:
    """P2.2: проверка констант изоляции BSL LS."""

    def test_timeout_is_15_seconds(self) -> None:
        """BSL_LS_TIMEOUT = 15 (увеличено с 10 согласно плану P2.2)."""
        assert BSL_LS_TIMEOUT == 15, f"BSL_LS_TIMEOUT should be 15, got {BSL_LS_TIMEOUT}"

    def test_max_retries_is_3(self) -> None:
        """BSL_LS_MAX_RETRIES = 3."""
        assert BSL_LS_MAX_RETRIES == 3, f"BSL_LS_MAX_RETRIES should be 3, got {BSL_LS_MAX_RETRIES}"

    def test_retry_delays_exponential(self) -> None:
        """BSL_LS_RETRY_DELAYS — exponential backoff [1, 2, 4]."""
        assert BSL_LS_RETRY_DELAYS == [1.0, 2.0, 4.0], (
            f"BSL_LS_RETRY_DELAYS should be [1.0, 2.0, 4.0], got {BSL_LS_RETRY_DELAYS}"
        )
        assert len(BSL_LS_RETRY_DELAYS) >= BSL_LS_MAX_RETRIES - 1, "Should have enough delays for all retries"


# ============================================================================
# Тесты — _run_analysis retry логика
# ============================================================================


class TestRunAnalysisRetry:
    """Проверка retry логики в _run_analysis."""

    def test_run_analysis_success_on_first_try(self, tmp_path: Path) -> None:
        """_run_analysis успешно выполняется с первой попытки."""
        analyzer = BSLAnalyzer(
            binary_path=Path("/fake/bsl-ls"),
            config_path=Path("/fake/config.json"),
            project_root=tmp_path,
        )

        with (
            patch("subprocess.run") as mock_run,
            patch.object(AnalysisResult, "from_json", return_value=AnalysisResult()),
        ):
            result = analyzer._run_analysis(tmp_path / "test.bsl", tmp_path / "output")
            mock_run.assert_called_once()
            assert isinstance(result, AnalysisResult)

    def test_run_analysis_retries_on_timeout(self, tmp_path: Path) -> None:
        """_run_analysis retry при timeout, затем успех."""
        analyzer = BSLAnalyzer(
            binary_path=Path("/fake/bsl-ls"),
            config_path=Path("/fake/config.json"),
            project_root=tmp_path,
        )

        # Первые 2 вызова — timeout, 3-й — успех
        with (
            patch("subprocess.run") as mock_run,
            patch.object(AnalysisResult, "from_json", return_value=AnalysisResult()),
            patch("time.sleep"),
        ):  # не ждём реально
            mock_run.side_effect = [
                subprocess.TimeoutExpired(["cmd"], BSL_LS_TIMEOUT),
                subprocess.TimeoutExpired(["cmd"], BSL_LS_TIMEOUT),
                MagicMock(),  # успех
            ]
            result = analyzer._run_analysis(tmp_path / "test.bsl", tmp_path / "output")
            assert mock_run.call_count == 3
            assert isinstance(result, AnalysisResult)

    def test_run_analysis_fails_after_max_retries(self, tmp_path: Path) -> None:
        """_run_analysis поднимает RuntimeError после BSL_LS_MAX_RETRIES попыток."""
        analyzer = BSLAnalyzer(
            binary_path=Path("/fake/bsl-ls"),
            config_path=Path("/fake/config.json"),
            project_root=tmp_path,
        )

        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = subprocess.TimeoutExpired(["cmd"], BSL_LS_TIMEOUT)
            with pytest.raises(RuntimeError, match="BSL LS failed"):
                analyzer._run_analysis(tmp_path / "test.bsl", tmp_path / "output")
            assert mock_run.call_count == BSL_LS_MAX_RETRIES

    def test_run_analysis_retries_on_called_process_error(self, tmp_path: Path) -> None:
        """_run_analysis retry при CalledProcessError, затем успех."""
        analyzer = BSLAnalyzer(
            binary_path=Path("/fake/bsl-ls"),
            config_path=Path("/fake/config.json"),
            project_root=tmp_path,
        )

        with (
            patch("subprocess.run") as mock_run,
            patch.object(AnalysisResult, "from_json", return_value=AnalysisResult()),
            patch("time.sleep"),
        ):
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, ["cmd"]),
                MagicMock(),  # успех
            ]
            result = analyzer._run_analysis(tmp_path / "test.bsl", tmp_path / "output")
            assert mock_run.call_count == 2
            assert isinstance(result, AnalysisResult)

    def test_run_analysis_uses_correct_timeout(self, tmp_path: Path) -> None:
        """_run_analysis передаёт BSL_LS_TIMEOUT в subprocess.run."""
        analyzer = BSLAnalyzer(
            binary_path=Path("/fake/bsl-ls"),
            config_path=Path("/fake/config.json"),
            project_root=tmp_path,
        )

        with (
            patch("subprocess.run") as mock_run,
            patch.object(AnalysisResult, "from_json", return_value=AnalysisResult()),
        ):
            analyzer._run_analysis(tmp_path / "test.bsl", tmp_path / "output")
            _, kwargs = mock_run.call_args
            assert kwargs.get("timeout") == BSL_LS_TIMEOUT


# ============================================================================
# Тесты — bsl_ls_with_fallback декоратор
# ============================================================================


class TestBSLLSWithFallback:
    """Проверка bsl_ls_with_fallback декоратора."""

    def test_fallback_not_called_on_success(self) -> None:
        """Декоратор НЕ вызывает fallback при успехе."""
        fallback = MagicMock(return_value="fallback_result")

        @bsl_ls_with_fallback(fallback)
        def success_func() -> str:
            return "success"

        result = success_func()
        assert result == "success"
        fallback.assert_not_called()

    def test_fallback_called_on_runtime_error(self) -> None:
        """Декоратор вызывает fallback при RuntimeError."""
        fallback = MagicMock(return_value="fallback_result")

        @bsl_ls_with_fallback(fallback)
        def failing_func() -> str:
            raise RuntimeError("BSL LS failed")

        result = failing_func()
        assert result == "fallback_result"
        fallback.assert_called_once()

    def test_fallback_called_on_timeout(self) -> None:
        """Декоратор вызывает fallback при TimeoutExpired."""
        fallback = MagicMock(return_value="fallback_result")

        @bsl_ls_with_fallback(fallback)
        def failing_func() -> str:
            raise subprocess.TimeoutExpired(["cmd"], 15)

        result = failing_func()
        assert result == "fallback_result"
        fallback.assert_called_once()

    def test_fallback_called_on_file_not_found(self) -> None:
        """Декоратор вызывает fallback при FileNotFoundError."""
        fallback = MagicMock(return_value="fallback_result")

        @bsl_ls_with_fallback(fallback)
        def failing_func() -> str:
            raise FileNotFoundError("BSL LS binary not found")

        result = failing_func()
        assert result == "fallback_result"
        fallback.assert_called_once()

    def test_fallback_returns_empty_result_when_no_fallback(self) -> None:
        """Без fallback_func — возвращает пустой AnalysisResult."""

        @bsl_ls_with_fallback(None)
        def failing_func() -> str:
            raise RuntimeError("BSL LS failed")

        result = failing_func()
        assert isinstance(result, AnalysisResult)
        assert result.total == 0

    def test_fallback_preserves_function_metadata(self) -> None:
        """Декоратор сохраняет __name__ и __doc__."""

        @bsl_ls_with_fallback(None)
        def my_func() -> None:
            """My docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_fallback_passes_args(self) -> None:
        """Декоратор передаёт аргументы в fallback функцию."""
        fallback = MagicMock(return_value="result")

        @bsl_ls_with_fallback(fallback)
        def failing_func(file_path: str, level: str = "standard") -> str:
            raise RuntimeError("failed")

        failing_func("/path/to/file.bsl", level="full")
        fallback.assert_called_once_with("/path/to/file.bsl", level="full")
