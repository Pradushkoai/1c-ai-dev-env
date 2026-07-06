"""
Тесты для src.services.cfe.cli — CLI helpers для CFE операций.

Этап 5.2: добавлены тесты для поднятия coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.cfe.cli import borrow_object_cli, diff_cli, patch_method_cli
from src.services.cfe.result import BorrowResult, CfeDiffResult, PatchMethodResult


class TestBorrowObjectCli:
    """Тесты borrow_object_cli."""

    @patch("src.services.cfe_manager.CfeManager")
    def test_creates_manager_and_calls_borrow(self, mock_manager_cls):
        """borrow_object_cli создаёт CfeManager и вызывает borrow_object."""
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager
        expected_result = BorrowResult(
            object_ref="Catalog.Тест",
            object_type="Catalog",
            object_name="Тест",
        )
        mock_manager.borrow_object.return_value = expected_result

        result = borrow_object_cli("/ext", "/cfg", "Catalog.Тест")

        mock_manager_cls.assert_called_once()
        mock_manager.borrow_object.assert_called_once_with(
            Path("/ext"), Path("/cfg"), "Catalog.Тест"
        )
        assert result is expected_result
        assert result.object_ref == "Catalog.Тест"


class TestPatchMethodCli:
    """Тесты patch_method_cli."""

    @patch("src.services.cfe_manager.CfeManager")
    def test_calls_patch_method_with_defaults(self, mock_manager_cls):
        """patch_method_cli вызывает patch_method с параметрами по умолчанию."""
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager
        expected_result = PatchMethodResult(
            module_path="Catalog.Тест.ObjectModule",
            method_name="ПриЗаписи",
            interceptor_type="Before",
        )
        mock_manager.patch_method.return_value = expected_result

        result = patch_method_cli("/ext", "Catalog.Тест.ObjectModule", "ПриЗаписи", "Before")

        mock_manager.patch_method.assert_called_once_with(
            Path("/ext"),
            "Catalog.Тест.ObjectModule",
            "ПриЗаписи",
            "Before",
            "НаСервере",
            False,
        )
        assert result is expected_result

    @patch("src.services.cfe_manager.CfeManager")
    def test_calls_patch_method_with_custom_params(self, mock_manager_cls):
        """patch_method_cli с кастомными context и is_function."""
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager
        mock_manager.patch_method.return_value = PatchMethodResult(
            module_path="M",
            method_name="m",
            interceptor_type="After",
        )

        patch_method_cli(
            "/ext", "M", "m", "After", context="НаКлиенте", is_function=True
        )

        mock_manager.patch_method.assert_called_once_with(
            Path("/ext"), "M", "m", "After", "НаКлиенте", True
        )


class TestDiffCli:
    """Тесты diff_cli."""

    @patch("src.services.cfe_manager.CfeManager")
    def test_creates_manager_and_calls_diff(self, mock_manager_cls):
        """diff_cli создаёт CfeManager и вызывает diff."""
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager
        expected_result = CfeDiffResult(
            extension_path=Path("/ext"),
            config_path=Path("/cfg"),
        )
        mock_manager.diff.return_value = expected_result

        result = diff_cli("/ext", "/cfg")

        mock_manager_cls.assert_called_once()
        mock_manager.diff.assert_called_once_with(Path("/ext"), Path("/cfg"))
        assert result is expected_result
