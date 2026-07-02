"""
Тесты для P1.9: @lru_cache для загрузки BM25-индекса.

До фикса: search_bm25() каждый раз перечитывал JSON-индекс с диска
(~50-200мс на 100K методов). При серии повторных поисков это давало
x10-x100 замедление.

После фикса: загрузка вынесена в _load_index_cached с @lru_cache(maxsize=8).
Первый вызов медленный, последующие — <1мс (cache hit).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.services.search_bm25 import (
    _load_index,
    _load_index_cached,
    build_index_bm25,
    search_bm25,
)


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture
def bm25_index(tmp_path: Path) -> Path:
    """Создаёт реальный BM25-индекс для тестов кэширования."""
    methods_json = tmp_path / "methods.json"
    methods_json.write_text(
        json.dumps(
            [
                {
                    "name_ru": "Найти",
                    "name_en": "Find",
                    "context": "Справочник",
                    "syntax": "Найти(Код)",
                    "description": "Поиск по коду",
                    "returns": "Ссылка",
                },
                {
                    "name_ru": "Запрос",
                    "name_en": "Query",
                    "context": "База",
                    "syntax": "Запрос.Выполнить()",
                    "description": "Выполнить запрос",
                    "returns": "Результат",
                },
            ]
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "index.json"
    build_index_bm25(methods_json, index_path)
    return index_path


@pytest.fixture(autouse=True)
def clear_cache():
    """Очищаем кэш перед каждым тестом — изоляция."""
    _load_index_cached.cache_clear()
    yield
    _load_index_cached.cache_clear()


# ============================================================================
# Тесты — кэширование работает
# ============================================================================


class TestLruCacheBasics:
    """Базовая функциональность @lru_cache для _load_index_cached."""

    def test_load_returns_same_dict_for_same_path(self, bm25_index: Path) -> None:
        """Повторные вызовы с тем же path возвращают ОДИН И ТОТ ЖЕ объект (is)."""
        idx1 = _load_index_cached(bm25_index)
        idx2 = _load_index_cached(bm25_index)
        # lru_cache гарантирует идентичность объекта при cache hit
        assert idx1 is idx2, "Cache hit должен возвращать тот же объект (identity)"

    def test_cache_info_shows_hits(self, bm25_index: Path) -> None:
        """cache_info() показывает growing hits после повторных вызовов."""
        _load_index_cached(bm25_index)
        _load_index_cached(bm25_index)
        _load_index_cached(bm25_index)
        info = _load_index_cached.cache_info()
        assert info.hits >= 2, f"Expected >=2 hits, got {info.hits}"
        assert info.misses == 1, f"Expected 1 miss, got {info.misses}"

    def test_cache_clear_resets(self, bm25_index: Path) -> None:
        """cache_clear() полностью очищает кэш."""
        _load_index_cached(bm25_index)
        assert _load_index_cached.cache_info().currsize == 1
        _load_index_cached.cache_clear()
        assert _load_index_cached.cache_info().currsize == 0
        # После clear следующий вызов — miss
        _load_index_cached(bm25_index)
        info = _load_index_cached.cache_info()
        assert info.misses == 1
        assert info.hits == 0

    def test_different_paths_cached_separately(
        self, bm25_index: Path, tmp_path: Path
    ) -> None:
        """Разные index_path — разные записи в кэше."""
        # Создаём второй индекс
        methods2 = tmp_path / "methods2.json"
        methods2.write_text(
            json.dumps(
                [
                    {
                        "name_ru": "Добавить",
                        "name_en": "Add",
                        "context": "Список",
                        "syntax": "Добавить()",
                        "description": "Добавить элемент",
                        "returns": "",
                    }
                ]
            ),
            encoding="utf-8",
        )
        index2 = tmp_path / "index2.json"
        build_index_bm25(methods2, index2)

        idx1 = _load_index_cached(bm25_index)
        idx2 = _load_index_cached(index2)
        assert idx1 is not idx2
        assert _load_index_cached.cache_info().currsize == 2

    def test_maxsize_is_8(self) -> None:
        """lru_cache должен иметь maxsize=8 (multi-config scenario)."""
        info = _load_index_cached.cache_info()
        assert info.maxsize == 8, (
            f"Expected maxsize=8 (for multi-config), got {info.maxsize}"
        )


# ============================================================================
# Тесты — search_bm25 использует кэш
# ============================================================================


class TestSearchBm25UsesCache:
    """search_bm25 должен использовать кэшированную загрузку."""

    def test_repeated_search_uses_cache(self, bm25_index: Path) -> None:
        """Повторные search_bm25 с тем же index_path не перечитывают файл."""
        search_bm25(bm25_index, "Поиск")
        search_bm25(bm25_index, "Запрос")
        search_bm25(bm25_index, "Добавить")
        info = _load_index_cached.cache_info()
        # 3 search → 1 miss + 2 hits
        assert info.hits >= 2, f"Expected >=2 cache hits, got {info.hits}"
        assert info.misses == 1, f"Expected 1 miss, got {info.misses}"

    def test_search_results_correct_with_cache(self, bm25_index: Path) -> None:
        """Кэш не должен влиять на корректность результатов поиска."""
        results1 = search_bm25(bm25_index, "Найти")
        # Очищаем кэш и снова ищем — результаты должны быть идентичны
        _load_index_cached.cache_clear()
        results2 = search_bm25(bm25_index, "Найти")
        assert results1 == results2, "Cache must not affect search correctness"

    def test_search_returns_results_after_cache_clear(
        self, bm25_index: Path
    ) -> None:
        """После cache_clear() поиск продолжает работать корректно."""
        search_bm25(bm25_index, "Запрос")
        _load_index_cached.cache_clear()
        results = search_bm25(bm25_index, "Запрос")
        assert len(results) > 0
        assert any("Запрос" in r.get("name_ru", "") for r in results)


# ============================================================================
# Тесты — производительность (бенчмарк)
# ============================================================================


class TestCachePerformance:
    """Бенчмарк: cache hit должен быть значительно быстрее cache miss."""

    def test_cache_hit_much_faster_than_miss(self, bm25_index: Path) -> None:
        """Второй вызов _load_index_cached должен быть минимум в 5x быстрее первого.

        На реальном индексе 100K методов это x50-x100. На маленьком тестовом
        индексе ставим консервативный порог x5.
        """
        # Первый вызов — cache miss (читает файл)
        t0 = time.perf_counter()
        _load_index_cached(bm25_index)
        miss_time = time.perf_counter() - t0

        # Второй вызов — cache hit
        t0 = time.perf_counter()
        _load_index_cached(bm25_index)
        hit_time = time.perf_counter() - t0

        # На маленьком тестовом индексе разница может быть небольшой,
        # но всё равно должна быть заметной.
        # Пропускаем проверку если miss_time < 10мкс (слишком быстро для измерения).
        if miss_time < 1e-5:
            pytest.skip("Test index too small for reliable timing")

        ratio = miss_time / max(hit_time, 1e-9)
        assert ratio >= 5.0, (
            f"Cache hit should be >=5x faster than miss. "
            f"miss={miss_time * 1e6:.1f}μs, hit={hit_time * 1e6:.3f}μs, ratio={ratio:.1f}x"
        )

    def test_repeated_search_does_not_re_read_file(
        self, bm25_index: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При cache hit файл НЕ должен открываться повторно.

        Мокаем builtins.open и считаем вызовы.
        """
        import builtins

        real_open = builtins.open
        open_calls: list[str] = []

        def counting_open(file, *args, **kwargs):
            if hasattr(file, "name") and "index" in str(file):
                open_calls.append(str(file))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", counting_open)

        # Первый search — открывает файл (через json.load внутри _load_index)
        search_bm25(bm25_index, "Поиск")
        # Подсчитываем opening calls для index_path
        first_calls = sum(1 for c in open_calls if str(bm25_index) in c)

        # Очищаем список вызовов
        open_calls.clear()

        # Второй, третий, четвёртый search — должны использовать cache
        search_bm25(bm25_index, "Запрос")
        search_bm25(bm25_index, "Добавить")
        search_bm25(bm25_index, "Найти")

        cached_calls = sum(1 for c in open_calls if str(bm25_index) in c)

        assert first_calls >= 1, "First search should open the file"
        assert cached_calls == 0, (
            f"Subsequent searches must NOT open the file (cache hit). "
            f"Got {cached_calls} open() calls for index_path."
        )


# ============================================================================
# Тесты — инвалидация кэша
# ============================================================================


class TestCacheInvalidation:
    """After rebuild index нужно инвалидировать кэш."""

    def test_cache_clear_forces_re_read(self, bm25_index: Path) -> None:
        """После cache_clear() следующий search перечитывает файл."""
        search_bm25(bm25_index, "Поиск")
        info_before = _load_index_cached.cache_info()
        assert info_before.currsize == 1

        _load_index_cached.cache_clear()
        assert _load_index_cached.cache_info().currsize == 0

        # Следующий search — miss
        search_bm25(bm25_index, "Запрос")
        info_after = _load_index_cached.cache_info()
        assert info_after.misses == 1
        assert info_after.hits == 0

    def test_index_rebuild_after_cache_clear(self, tmp_path: Path) -> None:
        """После rebuild index + cache_clear() новый индекс подхватывается."""
        # Создаём начальный индекс
        methods1 = tmp_path / "methods.json"
        methods1.write_text(
            json.dumps(
                [
                    {
                        "name_ru": "СтарыйМетод",
                        "name_en": "OldMethod",
                        "context": "",
                        "syntax": "",
                        "description": "старый",
                        "returns": "",
                    }
                ]
            ),
            encoding="utf-8",
        )
        index_path = tmp_path / "index.json"
        build_index_bm25(methods1, index_path)

        # Первый search находит только старый метод
        results1 = search_bm25(index_path, "Старый")
        assert any("Старый" in r["name_ru"] for r in results1)

        # Перестраиваем индекс с новым методом
        methods2 = tmp_path / "methods.json"
        methods2.write_text(
            json.dumps(
                [
                    {
                        "name_ru": "СтарыйМетод",
                        "name_en": "OldMethod",
                        "context": "",
                        "syntax": "",
                        "description": "старый",
                        "returns": "",
                    },
                    {
                        "name_ru": "НовыйМетод",
                        "name_en": "NewMethod",
                        "context": "",
                        "syntax": "",
                        "description": "новый",
                        "returns": "",
                    },
                ]
            ),
            encoding="utf-8",
        )
        build_index_bm25(methods2, index_path)

        # БЕЗ cache_clear — кэш возвращает старый индекс (новый метод не найден)
        results_without_clear = search_bm25(index_path, "Новый")
        assert not any("Новый" in r["name_ru"] for r in results_without_clear), (
            "Without cache_clear, stale cache is used"
        )

        # ПОСЛЕ cache_clear — новый индекс подхвачен
        _load_index_cached.cache_clear()
        results_with_clear = search_bm25(index_path, "Новый")
        assert any("Новый" in r["name_ru"] for r in results_with_clear), (
            "After cache_clear, rebuilt index must be used"
        )


# ============================================================================
# Тесты — public API
# ============================================================================


class TestPublicApi:
    """Публичный API для инвалидации кэша должен быть доступен."""

    def test_load_index_cached_exposed(self) -> None:
        """Модуль должен экспортировать _load_index_cached для ручной инвалидации."""
        from src.services.search_bm25 import _load_index_cached

        assert hasattr(_load_index_cached, "cache_clear")
        assert hasattr(_load_index_cached, "cache_info")

    def test_load_index_function_exists(self) -> None:
        """Базовая функция _load_index доступна (без кэша) — для тестирования."""
        from src.services.search_bm25 import _load_index

        assert callable(_load_index)
