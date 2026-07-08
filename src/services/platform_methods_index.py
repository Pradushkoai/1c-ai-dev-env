"""
platform_methods_index.py — Сервис для работы с индексом методов платформы 1С.

Поток 1, Этап 1.3: Минимальная версия для task_processor.
Полная версия (с type inference, check_bsl_context) — в Потоке 3.

Использует SQLite базу platform-methods.db с FTS5 для полнотекстового поиска.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .path_manager import PathManager


class PlatformMethodsIndex:
    """Сервис для поиска методов платформы 1С в SQLite базе.

    Минимальная версия (Поток 1):
    - search() — FTS5 поиск по имени/описанию
    - get_method() — получение метода по имени (O(1))
    - is_available() — проверка существования индекса

    Полная версия (Поток 3, будет расширена):
    - is_available_in() — проверка доступности в контексте
    - get_methods_by_name() — все методы с этим именем (коллизии)
    - find_alternative() — альтернатива для недоступного метода
    """

    def __init__(self, platform_version: str | None = None, paths: PathManager | None = None):
        """Инициализация.

        Args:
            platform_version: Версия платформы (например "8.3.20").
                              Если None — берётся из env 1C_AI_PLATFORM_VERSION или "8.3.20".
            paths: PathManager для определения путей.
        """
        import os

        self.platform_version = platform_version or os.environ.get("1C_AI_PLATFORM_VERSION", "8.3.20")
        self._paths = paths or PathManager()
        self._db_path = self._get_db_path()
        self._conn: sqlite3.Connection | None = None

    def _get_db_path(self) -> Path:
        """Путь к SQLite базе для текущей версии платформы."""
        return self._paths.derived_platform_dir / "versions" / self.platform_version / "platform-methods.db"

    def _get_conn(self) -> sqlite3.Connection | None:
        """Ленивое подключение к SQLite."""
        if self._conn is not None:
            return self._conn
        if not self._db_path.exists():
            return None
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def is_available(self) -> bool:
        """Проверка, что индекс платформы доступен."""
        return self._db_path.exists()

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """FTS5 поиск методов по имени/описанию.

        Args:
            query: Поисковый запрос (русское или английское имя, или ключевое слово)
            limit: Максимум результатов

        Returns:
            Список словарей с полями: name_ru, name_en, category, syntax,
            description, availability_raw, score
        """
        conn = self._get_conn()
        if conn is None:
            return []

        # Экранируем спецсимволы FTS5
        safe_query = query.replace('"', '""').strip()
        if not safe_query:
            return []

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.name_ru, m.name_en, m.category, m.syntax,
                       m.description, m.availability_raw, m.version_since,
                       bm25(methods_fts) as score
                FROM methods_fts fts
                JOIN methods m ON m.id = fts.rowid
                WHERE methods_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (f'"{safe_query}"', limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "name_ru": row["name_ru"] or "",
                        "name_en": row["name_en"] or "",
                        "category": row["category"] or "",
                        "syntax": row["syntax"] or "",
                        "description": row["description"] or "",
                        "availability_raw": row["availability_raw"] or "",
                        "version_since": row["version_since"] or "",
                        "score": -row["score"] if row["score"] else 0.0,
                    }
                )
            return results
        except Exception:
            # FTS5 может не сработать на сложных запросах — fallback на LIKE
            return self._search_like(query, limit)

    def _search_like(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fallback поиск через LIKE (если FTS5 не сработал)."""
        conn = self._get_conn()
        if conn is None:
            return []

        try:
            cursor = conn.cursor()
            pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT name_ru, name_en, category, syntax,
                       description, availability_raw, version_since
                FROM methods
                WHERE name_ru LIKE ? OR name_en LIKE ? OR description LIKE ?
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "name_ru": row["name_ru"] or "",
                        "name_en": row["name_en"] or "",
                        "category": row["category"] or "",
                        "syntax": row["syntax"] or "",
                        "description": row["description"] or "",
                        "availability_raw": row["availability_raw"] or "",
                        "version_since": row["version_since"] or "",
                        "score": 1.0,
                    }
                )
            return results
        except Exception:
            return []

    def get_method(self, name: str) -> dict[str, Any] | None:
        """Получить полную информацию о методе по имени.

        Поиск по русскому или английскому имени (O(1) по индексу).

        Args:
            name: Имя метода (русское или английское)

        Returns:
            Словарь с полной информацией или None если не найден
        """
        conn = self._get_conn()
        if conn is None:
            return None

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM methods
            WHERE name_ru = ? OR name_en = ?
            LIMIT 1
            """,
            (name, name),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        result = dict(row)
        # Парсим JSON поля
        if result.get("params_json"):
            try:
                result["params"] = json.loads(result["params_json"])
            except Exception:
                result["params"] = []
        if result.get("availability_json"):
            try:
                result["availability"] = json.loads(result["availability_json"])
            except Exception:
                result["availability"] = {}
        if result.get("see_also_json"):
            try:
                result["see_also"] = json.loads(result["see_also_json"])
            except Exception:
                result["see_also"] = []
        return result

    def list_versions(self) -> list[str]:
        """Список доступных версий платформы."""
        versions_dir = self._paths.derived_platform_dir / "versions"
        if not versions_dir.exists():
            return []
        return sorted(
            d.name
            for d in versions_dir.iterdir()
            if d.is_dir() and (d / "platform-methods.db").exists()
        )

    def close(self) -> None:
        """Закрыть подключение к БД."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
