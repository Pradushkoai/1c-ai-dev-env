"""
knowledge_base.py — Сервис для работы с базой знаний 1С разработки.

Загружает паттерны, антипаттерны и best practices из knowledge_base/.
Предоставляет поиск по ключевым словам.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeBase:
    """База знаний 1С разработки.

    Examples:
        >>> from pathlib import Path
        >>> import tempfile, json
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     kb_dir = Path(tmp) / "kb"
        ...     kb_dir.mkdir()
        ...     _ = (kb_dir / "index.json").write_text(
        ...         json.dumps({"categories": {"patterns": {"items": [
        ...             {"id": "test", "title": "Test", "file": "test.md",
        ...              "keywords": ["test"]}
        ...         ]}}}), encoding="utf-8")
        ...     kb = KnowledgeBase(kb_dir)
        ...     len(kb.list_all())
        1
    """

    def __init__(self, kb_dir: Path | str | None = None):
        """Инициализация базы знаний.

        Args:
            kb_dir: Путь к knowledge_base/. Если None — ищем автоматически.
        """
        if kb_dir is None:
            # Авто-поиск knowledge_base/
            candidates = [
                Path(__file__).parent.parent / "knowledge_base",
                Path("/home/z/my-project/repo_work/knowledge_base"),
                Path.cwd() / "knowledge_base",
            ]
            for path in candidates:
                if path.exists():
                    kb_dir = path
                    break
            else:
                kb_dir = candidates[0]

        self.kb_dir = Path(kb_dir)
        self.index: dict[str, Any] = {}
        self._loaded: dict[str, str] = {}  # file -> content

        self._load_index()

    def _load_index(self) -> None:
        """Загружает индекс базы знаний."""
        index_path = self.kb_dir / "index.json"
        if index_path.exists():
            with open(index_path, encoding="utf-8") as f:
                self.index = json.load(f)

    def _load_item(self, file_path: str) -> str:
        """Загружает содержимое файла (с кэшированием)."""
        if file_path not in self._loaded:
            full_path = self.kb_dir / file_path
            if full_path.exists():
                self._loaded[file_path] = full_path.read_text(encoding="utf-8")
            else:
                self._loaded[file_path] = ""
        return self._loaded[file_path]

    def search(self, query: str, category: str = None, limit: int = 10) -> list[dict]:
        """Поиск по базе знаний.

        Args:
            query: Поисковый запрос
            category: Категория (patterns, antipatterns, best_practices). Если None — все.
            limit: Максимум результатов

        Returns:
            [{id, title, file, score, snippet}, ...]
        """
        query_lower = query.lower()
        results = []

        categories = [category] if category else ["patterns", "antipatterns", "best_practices"]

        for cat in categories:
            cat_data = self.index.get("categories", {}).get(cat, {})
            for item in cat_data.get("items", []):
                score = 0

                # Поиск по keywords
                for keyword in item.get("keywords", []):
                    if keyword.lower() in query_lower:
                        score += 10
                    elif query_lower in keyword.lower():
                        score += 5

                # Поиск по title
                title = item.get("title", "").lower()
                if query_lower in title:
                    score += 8

                # Поиск по id
                item_id = item.get("id", "").lower()
                if query_lower in item_id:
                    score += 5

                # Поиск по содержимому файла
                if score == 0:
                    content = self._load_item(item.get("file", ""))
                    if content:
                        content_lower = content.lower()
                        if query_lower in content_lower:
                            score += 3
                            # Бонус за частоту
                            score += min(content_lower.count(query_lower) - 1, 5)

                if score > 0:
                    results.append(
                        {
                            "id": item.get("id"),
                            "title": item.get("title"),
                            "file": item.get("file"),
                            "category": cat,
                            "score": score,
                            "applies_to": item.get("applies_to", []),
                        }
                    )

        # Сортировка по релевантности
        results.sort(key=lambda x: -x["score"])

        return results[:limit]

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Возвращает полный контент элемента по ID.

        Args:
            item_id: ID элемента (например, 'create_catalog')

        Returns:
            {id, title, file, category, content} или None
        """
        for cat_name, cat_data in self.index.get("categories", {}).items():
            for item in cat_data.get("items", []):
                if item.get("id") == item_id:
                    content = self._load_item(item.get("file", ""))
                    return {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "file": item.get("file"),
                        "category": cat_name,
                        "applies_to": item.get("applies_to", []),
                        "content": content,
                    }
        return None

    def list_all(self) -> list[dict]:
        """Возвращает список всех элементов базы знаний.

        Returns:
            [{id, title, file, category, applies_to}, ...]
        """
        result = []
        for cat_name, cat_data in self.index.get("categories", {}).items():
            for item in cat_data.get("items", []):
                result.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "file": item.get("file"),
                        "category": cat_name,
                        "applies_to": item.get("applies_to", []),
                    }
                )
        return result

    def get_stats(self) -> dict[str, Any]:
        """Возвращает статистику базы знаний."""
        stats: dict[str, Any] = {
            "total_items": 0,
            "by_category": {},
            "total_files": 0,
        }
        for cat_name, cat_data in self.index.get("categories", {}).items():
            count = len(cat_data.get("items", []))
            stats["by_category"][cat_name] = count
            stats["total_items"] += count

        # Считаем .md файлы
        if self.kb_dir.exists():
            stats["total_files"] = len(list(self.kb_dir.rglob("*.md")))

        return stats
