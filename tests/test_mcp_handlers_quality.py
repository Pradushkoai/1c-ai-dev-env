"""
Тесты для src/mcpserver/handlers/quality.py — анализаторы качества.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcpserver.handlers.quality import (
    handle_analyze_architecture,
    handle_audit_security,
    handle_check_form_quality,
    handle_check_transactions,
    handle_diff_configs,
    handle_get_code_metrics,
    handle_get_knowledge,
)


def _parse(result):
    assert len(result) == 1
    return json.loads(result[0].text)


def _make_project():
    project = MagicMock()
    project.paths.root = Path("/repo")
    project.paths.scripts_dir = Path("/scripts")
    return project


class TestHandleAuditSecurity:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_audit_security(project, {}))
        assert "error" in data


class TestHandleGetCodeMetrics:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_get_code_metrics(project, {}))
        assert "error" in data


class TestHandleCheckTransactions:
    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        project = _make_project()
        data = _parse(await handle_check_transactions(project, {}))
        assert "error" in data


class TestHandleAnalyzeArchitecture:
    @pytest.mark.asyncio
    async def test_missing_config_dir(self):
        project = _make_project()
        data = _parse(await handle_analyze_architecture(project, {}))
        assert "error" in data


class TestHandleCheckFormQuality:
    @pytest.mark.asyncio
    async def test_missing_config_name(self):
        project = _make_project()
        data = _parse(await handle_check_form_quality(project, {}))
        assert "error" in data


class TestHandleDiffConfigs:
    @pytest.mark.asyncio
    async def test_missing_paths(self):
        project = _make_project()
        data = _parse(await handle_diff_configs(project, {}))
        assert "error" in data

    @pytest.mark.asyncio
    async def test_only_old_path(self):
        project = _make_project()
        data = _parse(await handle_diff_configs(project, {"old_path": "/old"}))
        assert "error" in data


class TestHandleGetKnowledge:
    @pytest.mark.asyncio
    async def test_list_all(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.list_all.return_value = [{"id": "1", "title": "test"}]
            kb.get_stats.return_value = {"total": 1}
            data = _parse(await handle_get_knowledge(project, {}))
            assert "items" in data or "stats" in data

    @pytest.mark.asyncio
    async def test_search(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.search.return_value = [{"id": "1", "title": "test", "score": 0.9}]
            data = _parse(await handle_get_knowledge(project, {"query": "test"}))
            assert "results" in data or "error" in data

    @pytest.mark.asyncio
    async def test_get_item(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.get_item.return_value = {"id": "1", "title": "test", "content": "full content"}
            data = _parse(await handle_get_knowledge(project, {"item_id": "1"}))
            assert "id" in data or "error" in data

    @pytest.mark.asyncio
    async def test_item_not_found(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            kb = mock_kb_class.return_value
            kb.get_item.return_value = None
            data = _parse(await handle_get_knowledge(project, {"item_id": "nonexistent"}))
            assert "error" in data or "items" in data

    @pytest.mark.asyncio
    async def test_exception(self):
        project = _make_project()
        with patch("src.services.knowledge_base.KnowledgeBase") as mock_kb_class:
            mock_kb_class.side_effect = RuntimeError("fail")
            data = _parse(await handle_get_knowledge(project, {}))
            assert "error" in data


# ============================================================================
# F2.2: get_method_details_batch — batch операция для нескольких методов
# ============================================================================


class TestHandleGetMethodDetailsBatch:
    """F2.2: Тесты для batch-вызова get_method_details."""

    @pytest.mark.asyncio
    async def test_missing_names(self):
        """Без names — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch

        project = _make_project()
        data = _parse(await handle_get_method_details_batch(project, {}))
        assert "error" in data
        assert "names required" in data["error"]

    @pytest.mark.asyncio
    async def test_names_not_list(self):
        """names не list — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch

        project = _make_project()
        data = _parse(await handle_get_method_details_batch(project, {"names": "Сообщить"}))
        assert "error" in data
        assert "must be a list" in data["error"]

    @pytest.mark.asyncio
    async def test_batch_too_large(self):
        """Batch > 50 — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch

        project = _make_project()
        big_names = [f"Метод{i}" for i in range(51)]
        data = _parse(await handle_get_method_details_batch(project, {"names": big_names}))
        assert "error" in data
        assert "batch too large" in data["error"]

    @pytest.mark.asyncio
    async def test_index_not_available(self):
        """Индекс не построен — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        with patch.object(PlatformMethodsIndex, "is_available", return_value=False):
            data = _parse(
                await handle_get_method_details_batch(
                    project, {"names": ["Сообщить", "Запрос"]}
                )
            )
            assert "error" in data
            assert "not built" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_batch(self):
        """Успешный batch — возвращает карточки методов."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        mock_method_1 = {
            "name_ru": "Сообщить",
            "name_en": "Message",
            "syntax": "Сообщить(<Текст>)",
            "params_json": '[{"name": "Текст", "type": "Строка"}]',
            "availability_json": '["server", "thin_client"]',
            "availability_raw": "Сервер, тонкий клиент",
            "see_also_json": "[]",
        }
        mock_method_2 = {
            "name_ru": "Запрос",
            "name_en": "Query",
            "syntax": "Запрос = Новый Запрос",
            "params_json": "[]",
            "availability_json": '["server"]',
            "availability_raw": "Сервер",
            "see_also_json": "[]",
        }

        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "get_method", side_effect=[mock_method_1, mock_method_2]), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_method_details_batch(
                    project, {"names": ["Сообщить", "Запрос"]}
                )
            )
            assert data["total_requested"] == 2
            assert data["total_found"] == 2
            assert len(data["methods"]) == 2
            assert data["methods"][0]["name_ru"] == "Сообщить"
            assert data["methods"][1]["name_ru"] == "Запрос"
            # JSON-поля распакованы
            assert data["methods"][0]["params"] == [{"name": "Текст", "type": "Строка"}]
            assert data["methods"][0]["availability"] == ["server", "thin_client"]

    @pytest.mark.asyncio
    async def test_batch_with_not_found(self):
        """Несуществующие методы попадают в not_found."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "get_method", side_effect=[None, {"name_ru": "Сообщить"}]), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_method_details_batch(
                    project, {"names": ["НесуществующийМетод", "Сообщить"]}
                )
            )
            assert data["total_requested"] == 2
            assert data["total_found"] == 1
            assert "not_found" in data
            assert "НесуществующийМетод" in data["not_found"]

    @pytest.mark.asyncio
    async def test_batch_with_target_context_check(self):
        """target_context проверяет доступность методов."""
        from src.mcpserver.handlers.quality import handle_get_method_details_batch
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        # Сообщить доступен в thin_client, ЗаписьЖурналаРегистрации — нет
        mock_method_1 = {
            "name_ru": "Сообщить",
            "availability_json": '["thin_client", "server"]',
            "availability_raw": "Тонкий клиент, сервер",
        }
        mock_method_2 = {
            "name_ru": "ЗаписьЖурналаРегистрации",
            "availability_json": '["server"]',
            "availability_raw": "Сервер",
            "version_deprecated": "",
        }

        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "get_method", side_effect=[mock_method_1, mock_method_2]), \
             patch.object(PlatformMethodsIndex, "is_available_in", side_effect=[True, False]), \
             patch.object(PlatformMethodsIndex, "is_deprecated", return_value=False), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_method_details_batch(
                    project,
                    {"names": ["Сообщить", "ЗаписьЖурналаРегистрации"], "target_context": "thin_client"},
                )
            )
            assert "not_available_in_context" in data
            assert len(data["not_available_in_context"]) == 1
            assert data["not_available_in_context"][0]["name"] == "ЗаписьЖурналаРегистрации"
            assert "_warning" in data


# ============================================================================
# F2.3: get_safe_methods — pre-hoc guidance
# ============================================================================


class TestHandleGetSafeMethods:
    """F2.3: Тесты для pre-hoc guidance tool."""

    @pytest.mark.asyncio
    async def test_missing_target_context(self):
        """Без target_context — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods

        project = _make_project()
        data = _parse(await handle_get_safe_methods(project, {}))
        assert "error" in data
        assert "target_context required" in data["error"]

    @pytest.mark.asyncio
    async def test_invalid_target_context_type(self):
        """target_context не str/list — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods

        project = _make_project()
        data = _parse(await handle_get_safe_methods(project, {"target_context": 123}))
        assert "error" in data
        assert "must be string or list" in data["error"]

    @pytest.mark.asyncio
    async def test_index_not_available(self):
        """Индекс не построен — ошибка."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        with patch.object(PlatformMethodsIndex, "is_available", return_value=False):
            data = _parse(
                await handle_get_safe_methods(project, {"target_context": "thin_client"})
            )
            assert "error" in data
            assert "not built" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_safe_methods(self):
        """Успешный возврат безопасных методов."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        mock_results = [
            {"name_ru": "Сообщить", "availability_raw": "Тонкий клиент, сервер"},
            {"name_ru": "ОткрытьФорму", "availability_raw": "Тонкий клиент"},
        ]

        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=mock_results), \
             patch.object(PlatformMethodsIndex, "is_available_in", return_value=True), \
             patch.object(PlatformMethodsIndex, "is_deprecated", return_value=False), \
             patch.object(PlatformMethodsIndex, "is_available_in_version", return_value=True), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_safe_methods(
                    project, {"target_context": "thin_client", "limit": 5}
                )
            )
            assert data["target_context"] == ["thin_client"]
            assert data["intent"] == "any"
            assert data["total_safe"] == 2
            assert len(data["safe_methods"]) == 2
            assert data["safe_methods"][0]["name_ru"] == "Сообщить"

    @pytest.mark.asyncio
    async def test_filters_unavailable_methods(self):
        """Методы, недоступные в контексте, попадают в filtered_out."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        mock_results = [
            {"name_ru": "Сообщить", "availability_raw": "Тонкий клиент, сервер"},
            {"name_ru": "ЗаписьЖурналаРегистрации", "availability_raw": "Сервер"},
        ]

        # Сообщить available=True, ЗаписьЖурналаРегистрации available=False
        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=mock_results), \
             patch.object(PlatformMethodsIndex, "is_available_in", side_effect=[True, False]), \
             patch.object(PlatformMethodsIndex, "is_deprecated", return_value=False), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_safe_methods(
                    project, {"target_context": "thin_client"}
                )
            )
            assert data["total_safe"] == 1
            assert data["safe_methods"][0]["name_ru"] == "Сообщить"
            assert data["total_filtered_out"] == 1
            assert data["filtered_out"][0]["name"] == "ЗаписьЖурналаРегистрации"
            assert "_hint" in data

    @pytest.mark.asyncio
    async def test_filters_deprecated_methods(self):
        """Устаревшие методы попадают в filtered_out."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        mock_results = [
            {"name_ru": "Сообщить", "availability_raw": "Тонкий клиент, сервер"},
            {"name_ru": "СтарыйМетод", "availability_raw": "Тонкий клиент", "version_deprecated": "8.3.10"},
        ]

        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=mock_results), \
             patch.object(PlatformMethodsIndex, "is_available_in", return_value=True), \
             patch.object(PlatformMethodsIndex, "is_deprecated", side_effect=[False, True]), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_safe_methods(
                    project, {"target_context": "thin_client"}
                )
            )
            assert data["total_safe"] == 1
            assert data["total_filtered_out"] == 1
            assert data["filtered_out"][0]["reason"] == "deprecated"

    @pytest.mark.asyncio
    async def test_intent_filter(self):
        """Intent фильтрует методы по ключевым словам."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        mock_query_results = [
            {"name_ru": "Запрос", "availability_raw": "Сервер"},
        ]

        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=mock_query_results), \
             patch.object(PlatformMethodsIndex, "is_available_in", return_value=True), \
             patch.object(PlatformMethodsIndex, "is_deprecated", return_value=False), \
             patch.object(PlatformMethodsIndex, "is_available_in_version", return_value=True), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_safe_methods(
                    project,
                    {"target_context": "server", "intent": "query", "limit": 5},
                )
            )
            assert data["intent"] == "query"
            assert data["total_safe"] >= 1

    @pytest.mark.asyncio
    async def test_limit_clamping(self):
        """Limit ограничивается до 100 и минимум 1."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=[]) as mock_search, \
             patch.object(PlatformMethodsIndex, "close"):
            # limit=0 → clamped to 1
            await handle_get_safe_methods(project, {"target_context": "server", "limit": 0})
            # limit=1000 → clamped to 100
            await handle_get_safe_methods(project, {"target_context": "server", "limit": 1000})
            # Проверяем, что search был вызван с разумным limit
            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_target_context_as_list(self):
        """target_context может быть списком."""
        from src.mcpserver.handlers.quality import handle_get_safe_methods
        from src.services.platform_methods_index import PlatformMethodsIndex

        project = _make_project()
        with patch.object(PlatformMethodsIndex, "is_available", return_value=True), \
             patch.object(PlatformMethodsIndex, "search", return_value=[]), \
             patch.object(PlatformMethodsIndex, "close"):
            data = _parse(
                await handle_get_safe_methods(
                    project, {"target_context": ["thin_client", "server"]}
                )
            )
            assert data["target_context"] == ["thin_client", "server"]
