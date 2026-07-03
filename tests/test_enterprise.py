"""
S3: Тесты для Enterprise features — audit log + RBAC.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.enterprise import (
    AuditLogger,
    ROLE_ADMIN,
    ROLE_DEVELOPER,
    ROLE_VIEWER,
    filter_tools_by_role,
    get_current_role,
    has_permission,
)


# ============================================================================
# Тесты — RBAC
# ============================================================================


class TestRBAC:
    """Проверка RBAC (Role-Based Access Control)."""

    def test_get_current_role_default_admin(self) -> None:
        """Default role — admin (обратная совместимость)."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_current_role() == ROLE_ADMIN

    def test_get_current_role_from_env(self) -> None:
        """MCP_ROLE env var устанавливает роль."""
        with patch.dict(os.environ, {"MCP_ROLE": "viewer"}):
            assert get_current_role() == ROLE_VIEWER

    def test_admin_has_all_tools(self) -> None:
        """Admin имеет доступ ко всем tools."""
        assert has_permission("search_1c_methods", ROLE_ADMIN) is True
        assert has_permission("analyze_bsl", ROLE_ADMIN) is True
        assert has_permission("epf_factory_create", ROLE_ADMIN) is True

    def test_viewer_has_read_only_tools(self) -> None:
        """Viewer имеет доступ только к read-only tools."""
        assert has_permission("list_configs", ROLE_VIEWER) is True
        assert has_permission("search_1c_methods", ROLE_VIEWER) is True
        assert has_permission("get_object_structure", ROLE_VIEWER) is True

    def test_viewer_no_write_tools(self) -> None:
        """Viewer НЕ имеет доступа к write tools."""
        assert has_permission("analyze_bsl", ROLE_VIEWER) is False
        assert has_permission("generate_processing", ROLE_VIEWER) is False
        assert has_permission("epf_factory_create", ROLE_VIEWER) is False
        assert has_permission("cfe_borrow", ROLE_VIEWER) is False

    def test_developer_has_dev_tools(self) -> None:
        """Developer имеет доступ к development tools."""
        assert has_permission("analyze_bsl", ROLE_DEVELOPER) is True
        assert has_permission("check_standards", ROLE_DEVELOPER) is True
        assert has_permission("generate_processing", ROLE_DEVELOPER) is True
        assert has_permission("epf_factory_create", ROLE_DEVELOPER) is True

    def test_developer_has_viewer_tools(self) -> None:
        """Developer имеет доступ к viewer tools."""
        assert has_permission("list_configs", ROLE_DEVELOPER) is True
        assert has_permission("search_1c_methods", ROLE_DEVELOPER) is True

    def test_filter_tools_by_role_admin(self) -> None:
        """filter_tools_by_role для admin — все tools."""
        tools = ["search", "analyze_bsl", "generate_processing"]
        filtered = filter_tools_by_role(tools, ROLE_ADMIN)
        assert filtered == tools

    def test_filter_tools_by_role_viewer(self) -> None:
        """filter_tools_by_role для viewer — только read-only."""
        tools = ["list_configs", "analyze_bsl", "search_1c_methods", "generate_processing"]
        filtered = filter_tools_by_role(tools, ROLE_VIEWER)
        assert "list_configs" in filtered
        assert "search_1c_methods" in filtered
        assert "analyze_bsl" not in filtered
        assert "generate_processing" not in filtered

    def test_filter_tools_by_role_developer(self) -> None:
        """filter_tools_by_role для developer — viewer + dev tools."""
        tools = ["list_configs", "analyze_bsl", "search_1c_methods"]
        filtered = filter_tools_by_role(tools, ROLE_DEVELOPER)
        assert len(filtered) == 3  # все доступны developer


# ============================================================================
# Тесты — AuditLogger
# ============================================================================


class TestAuditLogger:
    """Проверка AuditLogger."""

    def test_init_without_path(self) -> None:
        """AuditLogger без path — audit отключён."""
        audit = AuditLogger()
        assert audit.is_enabled() is False

    def test_init_with_path(self, tmp_path: Path) -> None:
        """AuditLogger с path — audit включён."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)
        assert audit.is_enabled() is True
        assert log_path.parent.exists()

    def test_log_tool_call_writes_to_file(self, tmp_path: Path) -> None:
        """log_tool_call записывает в audit.log."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)

        audit.log_tool_call(
            tool_name="search_1c_methods",
            namespace="team_a",
            role="viewer",
            arguments={"query": "test"},
            success=True,
        )

        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "search_1c_methods" in content
        assert "team_a" in content
        assert "viewer" in content

    def test_log_tool_call_with_error(self, tmp_path: Path) -> None:
        """log_tool_call записывает ошибки."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)

        audit.log_tool_call(
            tool_name="analyze_bsl",
            success=False,
            error="File not found",
        )

        content = log_path.read_text(encoding="utf-8")
        assert "File not found" in content

    def test_log_tool_call_masks_sensitive(self, tmp_path: Path) -> None:
        """log_tool_call маскирует sensitive данные."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)

        audit.log_tool_call(
            tool_name="search",
            arguments={"query": "test", "token": "secret123", "password": "mypassword123"},
        )

        content = log_path.read_text(encoding="utf-8")
        assert "secret123" not in content
        assert "mypassword123" not in content
        assert "***" in content

    def test_log_tool_call_disabled_without_path(self) -> None:
        """log_tool_call без path — no-op (не raise)."""
        audit = AuditLogger()
        audit.log_tool_call(tool_name="search")  # не должно raise

    def test_log_tool_call_truncates_long_args(self, tmp_path: Path) -> None:
        """log_tool_call обрезает длинные значения аргументов."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)

        long_value = "x" * 500
        audit.log_tool_call(
            tool_name="search",
            arguments={"query": long_value},
        )

        content = log_path.read_text(encoding="utf-8")
        # Значение должно быть обрезано до 200 символов
        assert long_value not in content
        assert "xxx" in content[:300]  # первые 200 символов присутствуют

    def test_log_tool_call_json_format(self, tmp_path: Path) -> None:
        """log_tool_call пишет JSON в audit.log."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger(log_path=log_path)

        audit.log_tool_call(
            tool_name="search",
            namespace="default",
            role="admin",
            arguments={"query": "test"},
        )

        content = log_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # Каждая строка должна быть валидным JSON (после timestamp)
        for line in lines:
            # Формат: timestamp | {json}
            parts = line.split(" | ", 1)
            if len(parts) == 2:
                data = json.loads(parts[1])
                assert "tool" in data
                assert "timestamp" in data
