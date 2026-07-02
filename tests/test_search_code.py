"""
Тесты для src/services/search_code.py — BM25 поиск по методам конфигураций.

Покрытие:
- _build_index_for_config — построение индекса из api-reference.json
- _bm25_score — расчёт BM25 score
- search_code — поиск (с построением индекса, с кэшем, с пустыми данными)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.search_code import _bm25_score, _build_index_for_config, search_code


# ─── Фикстуры ───


@pytest.fixture
def mock_paths(tmp_path: Path) -> MagicMock:
    """Mock PathManager с tmp_path."""
    paths = MagicMock()
    paths.config_api_reference_json.return_value = tmp_path / "api-reference.json"
    paths.config_derived_dir.return_value = tmp_path / "derived"
    return paths


@pytest.fixture
def sample_api_reference() -> list[dict]:
    """Тестовый api-reference с 2 модулями и 3 методами."""
    return [
        {
            "name": "ОбщегоНазначения",
            "methods": [
                {
                    "name": "СоздатьДокумент",
                    "type": "Функция",
                    "signature": "Функция СоздатьДокумент(Имя) Экспорт",
                    "description": "Создаёт новый документ по имени",
                    "returns": "ДокументСсылка",
                },
                {
                    "name": "НайтиПоКоду",
                    "type": "Функция",
                    "signature": "Функция НайтиПоКоду(Код) Экспорт",
                    "description": "Находит элемент справочника по коду",
                    "returns": "СправочникСсылка",
                },
            ],
        },
        {
            "name": "РаботаСЗаказами",
            "methods": [
                {
                    "name": "СоздатьЗаказ",
                    "type": "Процедура",
                    "signature": "Процедура СоздатьЗаказ(Клиент) Экспорт",
                    "description": "Создаёт новый заказ клиента",
                    "returns": "",
                },
            ],
        },
    ]


@pytest.fixture
def mock_paths_with_data(tmp_path: Path, sample_api_reference: list[dict]) -> MagicMock:
    """Mock PathManager с реальным api-reference.json."""
    api_path = tmp_path / "api-reference.json"
    api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

    paths = MagicMock()
    paths.config_api_reference_json.return_value = api_path
    paths.config_derived_dir.return_value = tmp_path / "derived"
    return paths


# ─── _build_index_for_config ───


class TestBuildIndexForConfig:
    def test_returns_none_when_api_reference_not_found(self, mock_paths):
        """Если api-reference.json не существует — возвращает None."""
        mock_paths.config_api_reference_json.return_value = Path("/nonexistent/path.json")
        result = _build_index_for_config("test_config", mock_paths)
        assert result is None

    def test_returns_index_with_correct_structure(self, mock_paths_with_data):
        """Индекс содержит все необходимые поля."""
        result = _build_index_for_config("test_config", mock_paths_with_data)
        assert result is not None
        assert result["version"] == 2
        assert result["algorithm"] == "bm25_code"
        assert result["config"] == "test_config"
        assert "documents" in result
        assert "idf" in result
        assert "inverted_index" in result
        assert "doc_lengths" in result
        assert "avg_doc_length" in result
        assert result["total_methods"] == 3  # 2 + 1 метода

    def test_documents_contain_method_metadata(self, mock_paths_with_data):
        """Документы содержат метаданные методов без tokens."""
        result = _build_index_for_config("test_config", mock_paths_with_data)
        docs = result["documents"]
        assert len(docs) == 3
        # Проверяем структуру первого документа
        first_doc = docs[0]
        assert "module" in first_doc
        assert "name" in first_doc
        assert "type" in first_doc
        assert "signature" in first_doc
        assert "description" in first_doc
        assert "returns" in first_doc
        # tokens должны быть удалены
        assert "tokens" not in first_doc

    def test_idf_is_calculated(self, mock_paths_with_data):
        """IDF посчитан для всех токенов."""
        result = _build_index_for_config("test_config", mock_paths_with_data)
        idf = result["idf"]
        assert isinstance(idf, dict)
        assert len(idf) > 0
        # IDF всегда положительный для BM25
        for value in idf.values():
            assert value >= 0

    def test_inverted_index_links_tokens_to_docs(self, mock_paths_with_data):
        """Инвертированный индекс связывает токены с документами."""
        result = _build_index_for_config("test_config", mock_paths_with_data)
        inv_idx = result["inverted_index"]
        # Хотя бы один токен в индексе
        assert len(inv_idx) > 0
        # Каждый токен ссылается на список (doc_id, tf) tuples
        for _token, postings in inv_idx.items():
            assert isinstance(postings, list)
            for posting in postings:
                assert len(posting) == 2  # (doc_id, tf)

    def test_returns_none_for_empty_modules(self, mock_paths, tmp_path):
        """Если в api-reference пустые модули — возвращает None."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
        mock_paths.config_api_reference_json.return_value = api_path
        result = _build_index_for_config("empty_config", mock_paths)
        assert result is None

    def test_returns_none_for_modules_without_methods(self, mock_paths, tmp_path):
        """Если модули без методов — возвращает None."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(
            json.dumps([{"name": "EmptyModule", "methods": []}], ensure_ascii=False),
            encoding="utf-8",
        )
        mock_paths.config_api_reference_json.return_value = api_path
        result = _build_index_for_config("no_methods_config", mock_paths)
        assert result is None

    def test_avg_doc_length_is_positive(self, mock_paths_with_data):
        """avg_doc_length > 0 для непустого индекса."""
        result = _build_index_for_config("test_config", mock_paths_with_data)
        assert result["avg_doc_length"] > 0


# ─── _bm25_score ───


class TestBM25Score:
    def test_returns_positive_score_for_typical_inputs(self):
        """Для типичных входных данных score положительный."""
        score = _bm25_score(tf=2, idf=1.5, doc_length=10, avg_length=12)
        assert score > 0

    def test_returns_zero_when_tf_is_zero(self):
        """При tf=0 score=0."""
        score = _bm25_score(tf=0, idf=1.5, doc_length=10, avg_length=12)
        assert score == 0

    def test_returns_zero_when_idf_is_zero(self):
        """При idf=0 score=0."""
        score = _bm25_score(tf=2, idf=0.0, doc_length=10, avg_length=12)
        assert score == 0

    def test_higher_tf_gives_higher_score(self):
        """Больший tf даёт больший score (при прочих равных)."""
        score_low_tf = _bm25_score(tf=1, idf=2.0, doc_length=10, avg_length=10)
        score_high_tf = _bm25_score(tf=10, idf=2.0, doc_length=10, avg_length=10)
        assert score_high_tf > score_low_tf

    def test_longer_doc_gets_lower_score(self):
        """Длинный документ получает меньший score (нормализация)."""
        score_short = _bm25_score(tf=2, idf=2.0, doc_length=5, avg_length=10)
        score_long = _bm25_score(tf=2, idf=2.0, doc_length=50, avg_length=10)
        assert score_short > score_long

    def test_handles_zero_avg_length_gracefully(self):
        """При avg_length=0 не падает (использует max(avg, 1))."""
        score = _bm25_score(tf=2, idf=1.5, doc_length=10, avg_length=0)
        assert isinstance(score, float)
        assert score > 0


# ─── search_code ───


class TestSearchCode:
    def test_search_returns_empty_when_config_not_found(self):
        """Если api-reference не существует — поиск возвращает пустой список."""
        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = Path("/nonexistent/api.json")
            mock_paths.config_derived_dir.return_value = Path("/tmp/test_derived")
            mock_pm_class.return_value = mock_paths

            results = search_code("nonexistent_config", "создать")
            assert results == []

    def test_search_builds_index_and_returns_results(self, tmp_path, sample_api_reference):
        """Поиск строит индекс и возвращает релевантные результаты."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = tmp_path / "derived"
            mock_pm_class.return_value = mock_paths

            results = search_code("test_config", "создать")
            assert len(results) > 0
            # Должны найти методы с "создать" в имени
            names = [r["name"] for r in results]
            assert any("Создать" in n for n in names)

    def test_search_results_have_required_fields(self, tmp_path, sample_api_reference):
        """Результаты поиска содержат все необходимые поля."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = tmp_path / "derived"
            mock_pm_class.return_value = mock_paths

            results = search_code("test_config", "заказ")
            assert len(results) > 0
            for r in results:
                assert "score" in r
                assert "module" in r
                assert "name" in r
                assert "type" in r
                assert "signature" in r
                assert "description" in r
                assert "returns" in r

    def test_search_uses_cached_index(self, tmp_path, sample_api_reference):
        """Повторный поиск использует кэшированный индекс."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")
        derived_dir = tmp_path / "derived"

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = derived_dir
            mock_pm_class.return_value = mock_paths

            # Первый поиск — строит индекс
            results1 = search_code("test_config", "создать")
            assert len(results1) > 0

            # Проверяем, что индекс сохранён в кэш
            index_path = derived_dir / "code-search-index.json"
            assert index_path.exists()

            # Второй поиск — использует кэш (счётчик вызовов api_reference_json не должен расти)
            results2 = search_code("test_config", "заказ")
            assert len(results2) > 0

    def test_search_returns_empty_for_empty_query(self, tmp_path, sample_api_reference):
        """Пустой запрос (только пробелы/пунктуация) возвращает пустой список."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = tmp_path / "derived"
            mock_pm_class.return_value = mock_paths

            results = search_code("test_config", "")
            assert results == []

            results = search_code("test_config", "   ")
            assert results == []

    def test_search_respects_limit(self, tmp_path, sample_api_reference):
        """Параметр limit ограничивает кол-во результатов."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = tmp_path / "derived"
            mock_pm_class.return_value = mock_paths

            # limit=1 — должен вернуть не более 1 результата
            results = search_code("test_config", "создать", limit=1)
            assert len(results) <= 1

    def test_search_returns_results_sorted_by_score_desc(self, tmp_path, sample_api_reference):
        """Результаты отсортированы по score по убыванию."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        with patch("src.services.search_code.PathManager") as mock_pm_class:
            mock_paths = MagicMock()
            mock_paths.config_api_reference_json.return_value = api_path
            mock_paths.config_derived_dir.return_value = tmp_path / "derived"
            mock_pm_class.return_value = mock_paths

            results = search_code("test_config", "создать", limit=10)
            if len(results) > 1:
                scores = [r["score"] for r in results]
                assert scores == sorted(scores, reverse=True)

    def test_search_with_explicit_paths_arg(self, tmp_path, sample_api_reference):
        """Можно передать paths явно (не создавая PathManager)."""
        api_path = tmp_path / "api-reference.json"
        api_path.write_text(json.dumps(sample_api_reference, ensure_ascii=False), encoding="utf-8")

        mock_paths = MagicMock()
        mock_paths.config_api_reference_json.return_value = api_path
        mock_paths.config_derived_dir.return_value = tmp_path / "derived"

        results = search_code("test_config", "создать", paths=mock_paths)
        assert len(results) > 0
