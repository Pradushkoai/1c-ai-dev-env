"""
S1: Тесты для SaaS-подготовки (billing stub + namespace isolation).

Проверяет:
1. BillingStub: record_usage, get_usage_report, get_all_reports, save/load
2. SAAS_ARCHITECTURE.md существует
3. Namespace isolation через MCP_NAMESPACE env var
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from experimental.services.billing_stub import BillingStub, UsageRecord

REPO_ROOT = Path(__file__).parent.parent.parent  # experimental/tests/ -> experimental/ -> repo root


# ============================================================================
# Тесты — BillingStub
# ============================================================================


class TestBillingStubBasic:
    """Базовая проверка BillingStub."""

    def test_init(self) -> None:
        """BillingStub инициализируется."""
        billing = BillingStub()
        assert billing is not None

    def test_record_usage_default_namespace(self) -> None:
        """record_usage использует 'default' namespace если не указан."""
        billing = BillingStub()
        billing.record_usage(tool="search_1c_methods")

        report = billing.get_usage_report()
        assert report["namespace"] == "default"
        assert report["total_calls"] == 1
        assert "search_1c_methods" in report["tools"]

    def test_record_usage_custom_namespace(self) -> None:
        """record_usage с custom namespace."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="analyze_bsl")

        report = billing.get_usage_report("team_a")
        assert report["namespace"] == "team_a"
        assert report["total_calls"] == 1

    def test_record_usage_multiple_calls(self) -> None:
        """record_usage накапливает calls."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search", calls=5)
        billing.record_usage(namespace="team_a", tool="search", calls=3)

        report = billing.get_usage_report("team_a")
        assert report["total_calls"] == 8
        assert report["tools"]["search"]["calls"] == 8

    def test_record_usage_multiple_tools(self) -> None:
        """record_usage разделяет tools."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search")
        billing.record_usage(namespace="team_a", tool="analyze_bsl")

        report = billing.get_usage_report("team_a")
        assert report["total_calls"] == 2
        assert len(report["tools"]) == 2

    def test_record_usage_last_used_set(self) -> None:
        """record_usage устанавливает last_used."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search")

        report = billing.get_usage_report("team_a")
        assert report["tools"]["search"]["last_used"] != ""


class TestBillingStubReports:
    """Проверка отчётов."""

    def test_get_usage_report_empty(self) -> None:
        """get_usage_report для несуществующего namespace → пустой отчёт."""
        billing = BillingStub()
        report = billing.get_usage_report("nonexistent")
        assert report["namespace"] == "nonexistent"
        assert report["total_calls"] == 0
        assert report["tools"] == {}

    def test_get_all_reports(self) -> None:
        """get_all_reports возвращает все namespaces."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search")
        billing.record_usage(namespace="team_b", tool="analyze")

        reports = billing.get_all_reports()
        assert len(reports) >= 2
        namespaces = [r["namespace"] for r in reports]
        assert "team_a" in namespaces
        assert "team_b" in namespaces


class TestBillingStubPersistence:
    """Проверка save/load."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """save + load восстанавливает usage."""
        storage = tmp_path / "billing.json"

        billing1 = BillingStub(storage_path=storage)
        billing1.record_usage(namespace="team_a", tool="search", calls=10)
        billing1.save()

        assert storage.exists()

        billing2 = BillingStub(storage_path=storage)
        report = billing2.get_usage_report("team_a")
        assert report["total_calls"] == 10
        assert report["tools"]["search"]["calls"] == 10

    def test_save_without_storage_path(self) -> None:
        """save без storage_path — no-op."""
        billing = BillingStub()
        billing.record_usage(tool="search")
        billing.save()  # не должно raise

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """load несуществующего файла — пустой billing."""
        storage = tmp_path / "nonexistent.json"
        billing = BillingStub(storage_path=storage)
        assert billing.get_usage_report()["total_calls"] == 0


class TestBillingStubReset:
    """Проверка reset."""

    def test_reset_specific_namespace(self) -> None:
        """reset для конкретного namespace."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search")
        billing.record_usage(namespace="team_b", tool="search")

        billing.reset("team_a")
        assert billing.get_usage_report("team_a")["total_calls"] == 0
        assert billing.get_usage_report("team_b")["total_calls"] == 1

    def test_reset_all(self) -> None:
        """reset всех namespaces."""
        billing = BillingStub()
        billing.record_usage(namespace="team_a", tool="search")
        billing.record_usage(namespace="team_b", tool="search")

        billing.reset()
        assert billing.get_all_reports() == []


class TestBillingStubEnvVar:
    """Проверка MCP_NAMESPACE env var."""

    def test_env_var_namespace(self) -> None:
        """MCP_NAMESPACE env var используется как default namespace."""
        with patch.dict(os.environ, {"MCP_NAMESPACE": "env_team"}):
            billing = BillingStub()
            billing.record_usage(tool="search")

            report = billing.get_usage_report()
            assert report["namespace"] == "env_team"


# ============================================================================
# Тесты — SaaS архитектура документация
# ============================================================================


class TestSaasArchitectureDocs:
    """Проверка docs/SAAS_ARCHITECTURE.md."""

    def test_saas_docs_exist(self) -> None:
        """docs/SAAS_ARCHITECTURE.md существует."""
        path = REPO_ROOT / "docs" / "SAAS_ARCHITECTURE.md"
        assert path.exists(), "docs/SAAS_ARCHITECTURE.md must exist (S1)"

    def test_saas_docs_has_levels(self) -> None:
        """SAAS_ARCHITECTURE описывает уровни масштабирования."""
        content = (REPO_ROOT / "docs" / "SAAS_ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "Level 1" in content or "Уровень 1" in content
        assert "Level 2" in content or "Уровень 2" in content

    def test_saas_docs_has_namespace_isolation(self) -> None:
        """SAAS_ARCHITECTURE описывает namespace isolation."""
        content = (REPO_ROOT / "docs" / "SAAS_ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "namespace" in content.lower()
        assert "MCP_NAMESPACE" in content

    def test_saas_docs_has_billing_stub(self) -> None:
        """SAAS_ARCHITECTURE описывает billing stub."""
        content = (REPO_ROOT / "docs" / "SAAS_ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "billing" in content.lower()

    def test_saas_docs_has_docker_compose(self) -> None:
        """SAAS_ARCHITECTURE описывает Docker Compose multi-config."""
        content = (REPO_ROOT / "docs" / "SAAS_ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "docker" in content.lower()
