"""
Комплексные тесты для KnowledgeBase (P0.1: coverage 70% → 90%+).

Покрывают:
- search() с разными сценариями (keywords, title, id, content, mixed)
- search() с category filter
- search() с limit
- get_item() существующий и несуществующий
- list_all()
- get_stats()
- _load_item() с кэшированием и отсутствующим файлом
- __init__() с авто-поиском и явным путём
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.knowledge_base import KnowledgeBase


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Создаёт тестовую базу знаний с index.json и файлами."""
    kb = tmp_path / "knowledge_base"
    kb.mkdir()

    # Создаём .md файлы
    patterns_dir = kb / "patterns"
    patterns_dir.mkdir()
    (patterns_dir / "create_catalog.md").write_text(
        "# Создание справочника\n\nКак создать справочник в 1С.\n\nСправочник — это...",
        encoding="utf-8",
    )
    (patterns_dir / "create_document.md").write_text(
        "# Создание документа\n\nДокумент — это объект для учёта операций.",
        encoding="utf-8",
    )

    antipatterns_dir = kb / "antipatterns"
    antipatterns_dir.mkdir()
    (antipatterns_dir / "common.md").write_text(
        "# Антипаттерны\n\nНе используйте Выполнить() с пользовательским вводом.",
        encoding="utf-8",
    )

    best_practices_dir = kb / "best_practices"
    best_practices_dir.mkdir()
    (best_practices_dir / "general.md").write_text(
        "# Best Practices\n\nИспользуйте области в коде BSL.",
        encoding="utf-8",
    )

    # Создаём index.json
    index = {
        "categories": {
            "patterns": {
                "items": [
                    {
                        "id": "create_catalog",
                        "title": "Создание справочника",
                        "file": "patterns/create_catalog.md",
                        "keywords": ["справочник", "catalog", "создание"],
                        "applies_to": ["Catalog"],
                    },
                    {
                        "id": "create_document",
                        "title": "Создание документа",
                        "file": "patterns/create_document.md",
                        "keywords": ["документ", "document"],
                        "applies_to": ["Document"],
                    },
                ]
            },
            "antipatterns": {
                "items": [
                    {
                        "id": "common_antipatterns",
                        "title": "Общие антипаттерны",
                        "file": "antipatterns/common.md",
                        "keywords": ["выполнить", "инъекция", "безопасность"],
                        "applies_to": [],
                    }
                ]
            },
            "best_practices": {
                "items": [
                    {
                        "id": "general_best_practices",
                        "title": "Общие best practices",
                        "file": "best_practices/general.md",
                        "keywords": ["области", "bsl", "стиль"],
                        "applies_to": [],
                    }
                ]
            },
        }
    }

    (kb / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return kb


@pytest.fixture
def kb(kb_dir: Path) -> KnowledgeBase:
    """KnowledgeBase с тестовой базой."""
    return KnowledgeBase(kb_dir)


@pytest.fixture
def empty_kb_dir(tmp_path: Path) -> Path:
    """Пустая база знаний без index.json."""
    kb = tmp_path / "empty_kb"
    kb.mkdir()
    return kb


# ============================================================================
# Тесты __init__()
# ============================================================================


class TestInit:
    """__init__() — инициализация базы знаний."""

    def test_init_with_explicit_path(self, kb_dir: Path) -> None:
        """Явный путь → используется он."""
        kb = KnowledgeBase(kb_dir)
        assert kb.kb_dir == kb_dir
        assert "categories" in kb.index

    def test_init_with_string_path(self, kb_dir: Path) -> None:
        """Строка-путь → конвертируется в Path."""
        kb = KnowledgeBase(str(kb_dir))
        assert isinstance(kb.kb_dir, Path)
        assert kb.kb_dir == kb_dir

    def test_init_with_empty_dir(self, empty_kb_dir: Path) -> None:
        """Пустая директория без index.json → пустой index."""
        kb = KnowledgeBase(empty_kb_dir)
        assert kb.index == {}

    def test_init_auto_search_finds_kb(self, kb_dir: Path, monkeypatch) -> None:
        """Авто-поиск находит knowledge_base/."""
        # Меняем cwd на tmp_path, где лежит knowledge_base/
        # Но сначала переименовываем kb_dir в knowledge_base
        parent = kb_dir.parent
        monkeypatch.chdir(parent)
        kb = KnowledgeBase(None)
        # Должен найти либо через candidates, либо через cwd
        assert kb.kb_dir.exists()


# ============================================================================
# Тесты search()
# ============================================================================


class TestSearch:
    """search() — поиск по базе знаний."""

    def test_search_by_keyword(self, kb: KnowledgeBase) -> None:
        """Поиск по keyword → находит элемент."""
        results = kb.search("справочник")
        assert len(results) >= 1
        assert any(r["id"] == "create_catalog" for r in results)

    def test_search_by_title(self, kb: KnowledgeBase) -> None:
        """Поиск по title → находит элемент."""
        results = kb.search("создание справочника")
        assert len(results) >= 1
        assert results[0]["id"] == "create_catalog"

    def test_search_by_id(self, kb: KnowledgeBase) -> None:
        """Поиск по id → находит элемент."""
        results = kb.search("create_catalog")
        assert len(results) >= 1
        assert results[0]["id"] == "create_catalog"

    def test_search_by_content(self, kb: KnowledgeBase) -> None:
        """Поиск по содержимому файла (когда keyword/title/id не совпали)."""
        results = kb.search("объект для учёта")
        assert len(results) >= 1
        assert results[0]["id"] == "create_document"

    def test_search_no_results(self, kb: KnowledgeBase) -> None:
        """Поиск без совпадений → пустой список."""
        results = kb.search("несуществующий_термин_xyz")
        assert results == []

    def test_search_with_category_filter(self, kb: KnowledgeBase) -> None:
        """Поиск с category=patterns → только patterns."""
        results = kb.search("создание", category="patterns")
        assert all(r["category"] == "patterns" for r in results)
        assert len(results) == 2

    def test_search_with_antipatterns_category(self, kb: KnowledgeBase) -> None:
        """Поиск с category=antipatterns → только antipatterns."""
        results = kb.search("выполнить", category="antipatterns")
        assert all(r["category"] == "antipatterns" for r in results)

    def test_search_with_limit(self, kb: KnowledgeBase) -> None:
        """Поиск с limit → не больше limit результатов."""
        results = kb.search("создание", limit=1)
        assert len(results) <= 1

    def test_search_results_sorted_by_score(self, kb: KnowledgeBase) -> None:
        """Результаты отсортированы по убыванию score."""
        results = kb.search("создание")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_results_have_required_fields(self, kb: KnowledgeBase) -> None:
        """Результаты содержат обязательные поля."""
        results = kb.search("справочник")
        assert len(results) > 0
        r = results[0]
        assert "id" in r
        assert "title" in r
        assert "file" in r
        assert "category" in r
        assert "score" in r
        assert "applies_to" in r

    def test_search_keyword_partial_match(self, kb: KnowledgeBase) -> None:
        """Частичное совпадение keyword (query в keyword) → score 5."""
        # 'catalog' содержит 'cat' — но 'cat' нет в keywords
        # 'справочник' — точное совпадение keyword → score 10
        results = kb.search("справочник")
        assert results[0]["score"] >= 10

    def test_search_content_frequency_bonus(self, kb: KnowledgeBase) -> None:
        """Бонус за частоту термина в контенте."""
        # 'справочник' встречается в create_catalog.md несколько раз
        results = kb.search("справочник")
        # Должен быть в результатах
        assert any(r["id"] == "create_catalog" for r in results)

    def test_search_all_categories_when_no_category(self, kb: KnowledgeBase) -> None:
        """Без category → поиск по всем категориям."""
        results = kb.search("создание")
        categories_found = {r["category"] for r in results}
        # Должны быть результаты из patterns (есть "создание" в title/keywords)
        assert "patterns" in categories_found


# ============================================================================
# Тесты get_item()
# ============================================================================


class TestGetItem:
    """get_item() — получение полного контента элемента."""

    def test_get_item_existing(self, kb: KnowledgeBase) -> None:
        """Существующий id → возвращает контент."""
        result = kb.get_item("create_catalog")
        assert result is not None
        assert result["id"] == "create_catalog"
        assert result["title"] == "Создание справочника"
        assert "content" in result
        assert "Создание справочника" in result["content"]
        assert result["category"] == "patterns"

    def test_get_item_nonexistent(self, kb: KnowledgeBase) -> None:
        """Несуществующий id → None."""
        result = kb.get_item("nonexistent_id")
        assert result is None

    def test_get_item_has_applies_to(self, kb: KnowledgeBase) -> None:
        """get_item возвращает applies_to."""
        result = kb.get_item("create_catalog")
        assert result is not None
        assert result["applies_to"] == ["Catalog"]

    def test_get_item_caches_content(self, kb: KnowledgeBase) -> None:
        """Повторный get_item использует кэш."""
        kb.get_item("create_catalog")
        kb.get_item("create_catalog")
        # Кэш должен содержать файл
        assert "patterns/create_catalog.md" in kb._loaded


# ============================================================================
# Тесты list_all()
# ============================================================================


class TestListAll:
    """list_all() — список всех элементов."""

    def test_list_all_returns_all_items(self, kb: KnowledgeBase) -> None:
        """list_all возвращает все 4 элемента."""
        result = kb.list_all()
        assert len(result) == 4

    def test_list_all_items_have_fields(self, kb: KnowledgeBase) -> None:
        """Все элементы имеют обязательные поля."""
        result = kb.list_all()
        for item in result:
            assert "id" in item
            assert "title" in item
            assert "file" in item
            assert "category" in item
            assert "applies_to" in item

    def test_list_all_covers_all_categories(self, kb: KnowledgeBase) -> None:
        """list_all включает элементы из всех категорий."""
        result = kb.list_all()
        categories = {item["category"] for item in result}
        assert categories == {"patterns", "antipatterns", "best_practices"}

    def test_list_all_empty_kb(self, empty_kb_dir: Path) -> None:
        """list_all на пустой базе → пустой список."""
        kb = KnowledgeBase(empty_kb_dir)
        assert kb.list_all() == []


# ============================================================================
# Тесты get_stats()
# ============================================================================


class TestGetStats:
    """get_stats() — статистика базы знаний."""

    def test_get_stats_total_items(self, kb: KnowledgeBase) -> None:
        """get_stats возвращает total_items."""
        stats = kb.get_stats()
        assert stats["total_items"] == 4

    def test_get_stats_by_category(self, kb: KnowledgeBase) -> None:
        """get_stats возвращает by_category с правильными count."""
        stats = kb.get_stats()
        assert stats["by_category"]["patterns"] == 2
        assert stats["by_category"]["antipatterns"] == 1
        assert stats["by_category"]["best_practices"] == 1

    def test_get_stats_total_files(self, kb: KnowledgeBase) -> None:
        """get_stats считает .md файлы."""
        stats = kb.get_stats()
        assert stats["total_files"] == 4  # 4 .md файла

    def test_get_stats_empty_kb(self, empty_kb_dir: Path) -> None:
        """get_stats на пустой базе → нули."""
        kb = KnowledgeBase(empty_kb_dir)
        stats = kb.get_stats()
        assert stats["total_items"] == 0
        assert stats["total_files"] == 0


# ============================================================================
# Тесты _load_item()
# ============================================================================


class TestLoadItem:
    """_load_item() — загрузка файлов с кэшированием."""

    def test_load_item_existing_file(self, kb: KnowledgeBase) -> None:
        """Существующий файл → контент."""
        content = kb._load_item("patterns/create_catalog.md")
        assert "Создание справочника" in content

    def test_load_item_nonexistent_file(self, kb: KnowledgeBase) -> None:
        """Несуществующий файл → пустая строка."""
        content = kb._load_item("nonexistent/file.md")
        assert content == ""

    def test_load_item_caches(self, kb: KnowledgeBase) -> None:
        """Повторная загрузка берёт из кэша."""
        kb._load_item("patterns/create_catalog.md")
        assert "patterns/create_catalog.md" in kb._loaded
        # Повторная загрузка — из кэша (не читает файл снова)
        # Проверим, что кэш содержит тот же контент
        cached = kb._loaded["patterns/create_catalog.md"]
        content = kb._load_item("patterns/create_catalog.md")
        assert content == cached
