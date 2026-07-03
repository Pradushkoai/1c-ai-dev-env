"""
S3: Enterprise features — audit log + RBAC.

Audit log: расширенное логирование через structlog в отдельный audit.log.
RBAC: роли для MCP tools через env var MCP_ROLE (viewer/developer/admin).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Роли для RBAC
ROLE_VIEWER = "viewer"
ROLE_DEVELOPER = "developer"
ROLE_ADMIN = "admin"

# Права по ролям: какие MCP tools доступны
ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_VIEWER: {
        "list_configs",
        "data_status",
        "search_1c_methods",
        "search_code",
        "get_api_reference",
        "get_object_structure",
        "get_skd_schema",
        "get_form_structure",
        "get_form_elements",
        "call_graph",
        "get_knowledge",
        "inspect",
        "build_dependency_graph",
        "dependency_query",
        "skd_trace",
    },
    ROLE_DEVELOPER: {
        # viewer + development tools
        "list_configs",
        "data_status",
        "search_1c_methods",
        "search_code",
        "get_api_reference",
        "get_object_structure",
        "get_skd_schema",
        "get_form_structure",
        "get_form_elements",
        "call_graph",
        "get_knowledge",
        "inspect",
        "build_dependency_graph",
        "dependency_query",
        "skd_trace",
        "analyze_bsl",
        "check_standards",
        "audit_security",
        "get_code_metrics",
        "check_transactions",
        "analyze_architecture",
        "analyze_queries",
        "check_form_quality",
        "check_skd_quality",
        "diff_configs",
        "solve_context",
        "solve_check",
        "generate_processing",
        "generate_report",
        "build_epf",
        "validate_generated",
        "epf_factory_create",
        "epf_factory_templates",
        "dsl_compile_meta",
        "dsl_compile_form",
        "dsl_compile_skd",
        "dsl_compile_mxl",
        "dsl_compile_role",
        "cfe_borrow",
        "cfe_patch_method",
        "cfe_diff",
        "openspec_proposal",
        "openspec_list",
        "openspec_update_task",
        "openspec_archive",
    },
    ROLE_ADMIN: {
        # all 45 tools
        "*",
    },
}


def get_current_role() -> str:
    """Получить текущую роль из env var MCP_ROLE.

    Returns:
        'viewer', 'developer', или 'admin' (default: 'admin').
    """
    return os.environ.get("MCP_ROLE", ROLE_ADMIN)


def has_permission(tool_name: str, role: str | None = None) -> bool:
    """Проверить, есть ли у роли право на tool.

    Args:
        tool_name: Имя MCP tool.
        role: Роль (если None — берётся из env var).

    Returns:
        True если tool доступен для роли.
    """
    if role is None:
        role = get_current_role()

    permissions = ROLE_PERMISSIONS.get(role, set())
    if "*" in permissions:
        return True  # admin: все tools
    return tool_name in permissions


def filter_tools_by_role(tool_names: list[str], role: str | None = None) -> list[str]:
    """Отфильтровать список tools по роли.

    Args:
        tool_names: Список имён tools.
        role: Роль (если None — из env var).

    Returns:
        Отфильтрованный список tools, доступных для роли.
    """
    if role is None:
        role = get_current_role()

    permissions = ROLE_PERMISSIONS.get(role, set())
    if "*" in permissions:
        return tool_names  # admin: все tools
    return [t for t in tool_names if t in permissions]


class AuditLogger:
    """Audit logger для enterprise (S3).

    Записывает все вызовы MCP tools в отдельный audit.log файл
    для compliance и security анализа.
    """

    def __init__(self, log_path: Path | None = None) -> None:
        """Инициализация audit logger.

        Args:
            log_path: Путь к audit.log файлу.
                Если None — audit logging отключён.
        """
        self._log_path = log_path
        self._logger: logging.Logger | None = None

        if log_path:
            self._setup_logger(log_path)

    def _setup_logger(self, log_path: Path) -> None:
        """Настроить отдельный logger для audit."""
        log_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("audit")
        self._logger.setLevel(logging.INFO)

        # File handler
        handler = logging.FileHandler(str(log_path), encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        self._logger.addHandler(handler)
        self._logger.propagate = False

    def log_tool_call(
        self,
        tool_name: str,
        namespace: str = "default",
        role: str = "admin",
        arguments: dict[str, Any] | None = None,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Записать вызов MCP tool в audit log.

        Args:
            tool_name: Имя MCP tool.
            namespace: Namespace команды.
            role: Роль пользователя.
            arguments: Аргументы вызова (без sensitive данных).
            success: Успешен ли вызов.
            error: Сообщение об ошибке (если есть).
        """
        if not self._logger:
            return  # audit logging отключён

        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "namespace": namespace,
            "role": role,
            "success": success,
        }
        if arguments:
            # Маскируем потенциально sensitive данные
            safe_args: dict[str, Any] = {}
            for key, value in arguments.items():
                if key.lower() in ("token", "password", "secret", "api_key"):
                    safe_args[key] = "***"
                else:
                    safe_args[key] = str(value)[:200]  # ограничиваем длину
            entry["arguments"] = safe_args
        if error:
            entry["error"] = error[:500]

        self._logger.info(json.dumps(entry, ensure_ascii=False))

    def is_enabled(self) -> bool:
        """Проверить, включён ли audit logging."""
        return self._logger is not None
