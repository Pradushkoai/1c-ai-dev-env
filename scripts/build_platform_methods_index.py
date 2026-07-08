#!/usr/bin/env python3
"""
build_platform_methods_index.py — Построение индекса методов платформы 1С.

Читает распакованные .hbk файлы (HTML) из syntax-helper/, извлекает полную
информацию о методах платформы 1С, сохраняет в SQLite для быстрого поиска.

Поток 1, Этап 1.1-1.2: Исправляет баги B1, B2, B3.

Изменения vs build_syntax_helper_index.py:
  B1: Исправлен AttributeError (syntax_helper_index_md не существует)
  B2: Убран фильтр "Синтаксис:" — извлекает 17907 методов вместо 7131
  B3: Создаёт отдельный индекс ПЛАТФОРМЫ (не путать с УТ11)
  NEW: Вывод в SQLite (15 МБ вместо 55 МБ JSON)
  NEW: Парсинг version_since и version_deprecated
  NEW: Параметр --platform-version
  NEW: 12 полей на метод (вместо 10)

Структура SQLite:
  - platform_versions: метаданные версий платформы
  - methods: полная информация о методах (12 полей)
  - methods_fts: FTS5 виртуальная таблица для полнотекстового поиска
  - Индексы: name_ru, name_en, category

Использование:
  python3 scripts/build_platform_methods_index.py
  python3 scripts/build_platform_methods_index.py --platform-version 8.3.20
  python3 scripts/build_platform_methods_index.py --hbk-file /path/to/shcntx_ru.hbk
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import html as html_module
from datetime import datetime
from pathlib import Path

# Ensure repo root is in sys.path
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.services.path_manager import PathManager

_PATHS = PathManager()

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

# Контексты платформы 1С → машиночитаемые флаги
CONTEXT_MAP = {
    "тонкий клиент": "thin_client",
    "веб-клиент": "web_client",
    "мобильный клиент": "mobile_client",
    "сервер": "server",
    "толстый клиент": "thick_client",
    "внешнее соединение": "external_connection",
    "мобильное приложение (клиент)": "mobile_app_client",
    "мобильное приложение (сервер)": "mobile_app_server",
    "мобильный автономный сервер": "mobile_autonomous_server",
}

# Основные директории с методами платформы (только эти .hbk содержат "Доступность:")
KEY_DIRS = [
    "shcntx_ru",  # Главный синтакс-помощник (методы платформы) — 28782 HTML
    "shlang_ru",  # Язык — 39 HTML
]


# ============================================================================
# УТИЛИТЫ
# ============================================================================


def strip_html(text: str) -> str:
    """Удаляет HTML-теги и декодирует сущности."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_availability(raw: str) -> dict[str, bool]:
    """Парсит строку доступности в 9 булевых флагов.

    Пример:
      "Сервер, толстый клиент, внешнее соединение."
      → {"server": True, "thick_client": True, "external_connection": True, ...}

    """
    result = {v: False for v in CONTEXT_MAP.values()}
    if not raw:
        return result
    raw_lower = raw.lower()
    for ru, en in CONTEXT_MAP.items():
        if ru in raw_lower:
            result[en] = True
    return result


def parse_version_since(html_content: str) -> str:
    """Извлекает версию, с которой метод доступен.

    Примеры:
      "Доступен, начиная с версии 8.0." → "8.0"
      "Доступен, начиная с версии 8.3.18." → "8.3.18"

    """
    m = re.search(r"Доступен, начиная с версии\s+([\d.]+)", html_content)
    return m.group(1) if m else ""


def parse_version_deprecated(html_content: str) -> str:
    """Извлекает версию, с которой метод устарел.

    Примеры:
      "Не рекомендуется использовать, начиная с версии 8.3.21." → "8.3.21"

    """
    m = re.search(
        r"(?:Не рекомендуется использовать|устаревш|deprecated).*?версии\s+([\d.]+)",
        html_content,
        re.IGNORECASE,
    )
    return m.group(1) if m else ""


# ============================================================================
# ПАРСЕР HTML
# ============================================================================


def extract_method_info(html_content: str, file_name: str) -> dict | None:
    """Извлекает полную информацию о методе из HTML-страницы.

    Возвращает dict с 12 полями или None если файл не содержит метод.

    Поля:
      - title, name_ru, name_en, category
      - version_since, version_deprecated
      - syntax, params (list), returns
      - description, availability_raw, availability (dict)
      - example, see_also (list), source_file

    B2: Убран фильтр "Синтаксис:" — теперь извлекает свойства и перечисления тоже.
    Фильтр: только V8SH_chapter (признак страницы справочника платформы).
    """
    # B2 FIX: проверяем только V8SH_chapter (не требуем "Синтаксис:")
    # Свойства (Метаданные) и перечисления (УровеньЖурналаРегистрации)
    # не имеют "Синтаксис:", но имеют "Доступность:" и V8SH_chapter
    if "V8SH_chapter" not in html_content and "V8SH_pagetitle" not in html_content:
        return None

    info = {
        "file": file_name,
        "title": "",
        "name_ru": "",
        "name_en": "",
        "category": "",
        "version_since": "",
        "version_deprecated": "",
        "syntax": "",
        "params": [],
        "returns": "",
        "description": "",
        "availability_raw": "",
        "availability": {},
        "example": "",
        "see_also": [],
        "source_file": file_name,
    }

    # Заголовок страницы
    m = re.search(r'<h1[^>]*class="V8SH_pagetitle"[^>]*>(.+?)</h1>', html_content, re.DOTALL)
    if m:
        info["title"] = strip_html(m.group(1))
        title = info["title"]
        # Заголовок вида "Глобальный контекст.ЗаписьЖурналаРегистрации (Global context.WriteLogEvent)"
        if "(" in title and ")" in title:
            ru_part = title[: title.rfind("(")].strip()
            en_part = title[title.rfind("(") + 1 : title.rfind(")")].strip()
            # Последний сегмент после точки — имя метода
            if "." in ru_part:
                info["category"] = ru_part.rsplit(".", 1)[0]
                info["name_ru"] = ru_part.rsplit(".", 1)[1]
            else:
                info["name_ru"] = ru_part
            if "." in en_part:
                info["name_en"] = en_part.rsplit(".", 1)[1]
            else:
                info["name_en"] = en_part
        else:
            info["name_ru"] = title

    # Заголовок секции (имя метода без контекста)
    m = re.search(r'<p class="V8SH_heading">(.+?)</p>', html_content, re.DOTALL)
    if m:
        heading = strip_html(m.group(1))
        if not info["name_ru"]:
            info["name_ru"] = heading

    # Категория (контекст)
    m = re.search(r'<p class="V8SH_title">(.+?)</p>', html_content, re.DOTALL)
    if m:
        info["category"] = strip_html(m.group(1))

    # Версия, начиная с которой доступен
    info["version_since"] = parse_version_since(html_content)

    # Версия, с которой устарел (deprecated)
    info["version_deprecated"] = parse_version_deprecated(html_content)

    # Синтаксис (может отсутствовать для свойств и перечислений — это OK)
    m = re.search(
        r'<p class="V8SH_chapter">Синтаксис:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["syntax"] = strip_html(m.group(1))

    # Параметры
    params_section = re.search(
        r'<p class="V8SH_chapter">Параметры:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if params_section:
        params_html = params_section.group(1)
        param_matches = re.findall(
            r'<div class="V8SH_rubric">\s*<p[^>]*>&lt;([^>]+)&gt;\s*\(([^)]+)\)</div>(.*?)(?=<div class="V8SH_rubric">|<p class="V8SH_chapter">|<HR>)',
            params_html,
            re.DOTALL,
        )
        for name, req, desc in param_matches:
            info["params"].append(
                {
                    "name": name.strip(),
                    "required": req.strip(),
                    "description": strip_html(desc)[:500],
                }
            )

    # Возвращаемое значение
    m = re.search(
        r'<p class="V8SH_chapter">Возвращаемое значение:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["returns"] = strip_html(m.group(1))[:500]

    # Описание
    m = re.search(
        r'<p class="V8SH_chapter">Описание:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["description"] = strip_html(m.group(1))[:1000]

    # Доступность — два формата:
    # 1. <p class="V8SH_chapter">Доступность:</p><p>...</p> (для методов)
    # 2. Доступность: ... (в тексте, для перечислений и свойств)
    m = re.search(
        r'<p class="V8SH_chapter">Доступность:\s*</p>\s*<p>([^<]+)</p>',
        html_content,
        re.DOTALL,
    )
    if not m:
        # Альтернативный паттерн — для перечислений и свойств
        m = re.search(
            r"Доступность:\s*([^<\n]+(?:\.[^<\n]*|[^<\n]*))",
            html_content,
        )
    if m:
        avail_text = m.group(1).strip()
        # Очищаем от возможных HTML-тегов
        avail_text = strip_html(avail_text)
        # Берём только первое предложение (до точки)
        avail_text = avail_text.split(".")[0] + "." if "." in avail_text else avail_text
        info["availability_raw"] = avail_text
        info["availability"] = parse_availability(info["availability_raw"])

    # Пример
    m = re.search(
        r'<p class="V8SH_chapter">Пример:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["example"] = strip_html(m.group(1))[:500]

    # См. также
    see_also_matches = re.findall(r'<a href="v8help://[^"]+">([^<]+)</a>', html_content)
    info["see_also"] = list(set(see_also_matches))[:10]

    # Если нет ни имени, ни категории — пропускаем
    if not info["name_ru"] and not info["name_en"] and not info["category"]:
        return None

    return info


# ============================================================================
# SQLITE
# ============================================================================


def create_db(db_path: Path, platform_version: str, hbk_hash: str, hbk_date: str) -> sqlite3.Connection:
    """Создаёт SQLite базу с таблицами и индексами."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Таблица версий платформы
    c.execute("""
        CREATE TABLE IF NOT EXISTS platform_versions (
            version TEXT PRIMARY KEY,
            source_hbk TEXT,
            source_hbk_hash TEXT,
            source_hbk_date TEXT,
            total_methods INTEGER DEFAULT 0,
            methods_with_availability INTEGER DEFAULT 0,
            methods_with_version_since INTEGER DEFAULT 0,
            deprecated_methods INTEGER DEFAULT 0,
            built_at TEXT
        )
    """)

    # Таблица методов
    c.execute("""
        CREATE TABLE IF NOT EXISTS methods (
            id INTEGER PRIMARY KEY,
            version TEXT NOT NULL,
            title TEXT,
            name_ru TEXT,
            name_en TEXT,
            category TEXT,
            version_since TEXT,
            version_deprecated TEXT,
            syntax TEXT,
            params_json TEXT,
            returns TEXT,
            description TEXT,
            availability_raw TEXT,
            availability_json TEXT,
            example TEXT,
            see_also_json TEXT,
            source_file TEXT,
            FOREIGN KEY (version) REFERENCES platform_versions(version)
        )
    """)

    # Индексы для быстрого поиска
    c.execute("CREATE INDEX IF NOT EXISTS idx_methods_name_ru ON methods(name_ru, version)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_methods_name_en ON methods(name_en, version)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_methods_category ON methods(category, version)")

    # FTS5 для полнотекстового поиска (unicode61 для русского языка)
    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS methods_fts USING fts5(
            name_ru,
            name_en,
            description,
            syntax,
            content='methods',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
    """)

    # Записываем версию платформы
    c.execute(
        "INSERT OR REPLACE INTO platform_versions (version, source_hbk, source_hbk_hash, source_hbk_date, built_at) VALUES (?, ?, ?, ?, ?)",
        (platform_version, "shcntx_ru.hbk", hbk_hash, hbk_date, datetime.now().isoformat()),
    )

    conn.commit()
    return conn


def save_method_to_db(conn: sqlite3.Connection, method_id: int, version: str, info: dict) -> None:
    """Сохраняет метод в SQLite."""
    c = conn.cursor()

    params_json = json.dumps(info.get("params", []), ensure_ascii=False)
    availability_json = json.dumps(info.get("availability", {}), ensure_ascii=False)
    see_also_json = json.dumps(info.get("see_also", []), ensure_ascii=False)

    c.execute(
        """INSERT INTO methods (
            id, version, title, name_ru, name_en, category,
            version_since, version_deprecated,
            syntax, params_json, returns, description,
            availability_raw, availability_json,
            example, see_also_json, source_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            method_id,
            version,
            info.get("title", ""),
            info.get("name_ru", ""),
            info.get("name_en", ""),
            info.get("category", ""),
            info.get("version_since", ""),
            info.get("version_deprecated", ""),
            info.get("syntax", ""),
            params_json,
            info.get("returns", ""),
            info.get("description", ""),
            info.get("availability_raw", ""),
            availability_json,
            info.get("example", ""),
            see_also_json,
            info.get("source_file", ""),
        ),
    )

    # FTS5 индексация
    c.execute(
        "INSERT INTO methods_fts (rowid, name_ru, name_en, description, syntax) VALUES (?, ?, ?, ?, ?)",
        (
            method_id,
            info.get("name_ru", ""),
            info.get("name_en", ""),
            info.get("description", ""),
            info.get("syntax", ""),
        ),
    )


def update_version_stats(conn: sqlite3.Connection, version: str, stats: dict) -> None:
    """Обновляет статистику по версии."""
    c = conn.cursor()
    c.execute(
        """UPDATE platform_versions SET
            total_methods = ?,
            methods_with_availability = ?,
            methods_with_version_since = ?,
            deprecated_methods = ?
        WHERE version = ?""",
        (
            stats["total"],
            stats["with_availability"],
            stats["with_version_since"],
            stats["deprecated"],
            version,
        ),
    )
    conn.commit()


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def is_method_file(file_path: Path) -> bool:
    """Проверяет, является ли файл описанием метода/свойства/перечисления.

    B2 FIX: убран фильтр "Синтаксис:".
    Теперь: только не служебные файлы (не 0.html, 1.html, etc.)
    """
    name = os.path.basename(file_path)
    if not name.endswith(".html"):
        return False
    # Пропускаем служебные файлы (0.html, 1.html, _CONTENTS_*.html, ___categories__.html)
    if name in ("0.html", "1.html"):
        return False
    if re.match(r"^\d+\.html$", name):
        return False
    if name.startswith("_CONTENTS_"):
        return False
    if "___categories__" in name:
        return False
    return True


def compute_hbk_hash(hbk_path: Path) -> str:
    """Вычисляет SHA256 хеш .hbk файла."""
    h = hashlib.sha256()
    with open(hbk_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def get_hbk_date(hbk_path: Path) -> str:
    """Возвращает дату модификации .hbk файла."""
    import datetime as dt

    mtime = os.path.getmtime(hbk_path)
    return dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="Построение индекса методов платформы 1С")
    parser.add_argument(
        "--platform-version",
        default="8.3.20",
        help="Версия платформы 1С (по умолчанию: 8.3.20)",
    )
    parser.add_argument(
        "--hbk-dir",
        type=Path,
        default=None,
        help="Директория с распакованными .hbk (по умолчанию: derived/platform/syntax-helper/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Путь к SQLite базе (по умолчанию: derived/platform/versions/<version>/platform-methods.db)",
    )
    args = parser.parse_args()

    platform_version = args.platform_version

    # Определяем пути
    hbk_dir = args.hbk_dir or _PATHS.syntax_helper_dir
    if args.output:
        db_path = args.output
    else:
        versions_dir = _PATHS.derived_platform_dir / "versions"
        db_path = versions_dir / platform_version / "platform-methods.db"

    # Проверяем наличие .hbk файлов
    if not hbk_dir.exists():
        print(f"❌ Директория .hbk не найдена: {hbk_dir}")
        print("   Сначала распакуйте .hbk файлы через scripts/hbk_extractor.py")
        sys.exit(1)

    # Проверяем наличие shcntx_ru
    shcntx_dir = hbk_dir / "shcntx_ru"
    if not shcntx_dir.exists():
        print(f"❌ Не найдена директория shcntx_ru в {hbk_dir}")
        print("   Нужен файл shcntx_ru.hbk (главный справочник платформы)")
        sys.exit(1)

    # Вычисляем хеш исходного .hbk
    hbk_source = _PATHS.hbk_dir / "shcntx_ru.hbk"
    if hbk_source.exists():
        hbk_hash = compute_hbk_hash(hbk_source)
        hbk_date = get_hbk_date(hbk_source)
    else:
        hbk_hash = "unknown"
        hbk_date = "unknown"

    print(f"Платформа 1С версии: {platform_version}")
    print(f"Источник .hbk: {hbk_dir}")
    print(f"Хеш .hbk: {hbk_hash}")
    print(f"Дата .hbk: {hbk_date}")
    print(f"Выходная БД: {db_path}")
    print()

    # Создаём SQLite базу
    conn = create_db(db_path, platform_version, hbk_hash, hbk_date)

    # Сканируем HTML файлы
    all_methods: list[dict] = []
    stats = {
        "total": 0,
        "with_availability": 0,
        "with_version_since": 0,
        "deprecated": 0,
    }

    for subdir_name in KEY_DIRS:
        subdir_path = hbk_dir / subdir_name
        if not subdir_path.exists():
            continue

        print(f"Обработка {subdir_name}...")
        files = list(subdir_path.glob("*.html"))
        print(f"  HTML файлов: {len(files)}")

        methods_in_subdir = 0
        for i, f in enumerate(files):
            if i % 5000 == 0 and i > 0:
                print(f"  Прогресс: {i}/{len(files)}")

            if not is_method_file(f):
                continue

            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()

                # B2 FIX: проверяем только V8SH_chapter или V8SH_pagetitle
                # (не требуем "Синтаксис:" — свойства и перечисления тоже нужны)
                if "V8SH_chapter" not in content and "V8SH_pagetitle" not in content:
                    continue

                info = extract_method_info(content, str(f.relative_to(hbk_dir)))
                if info and (info["name_ru"] or info["name_en"]):
                    info["source_dir"] = subdir_name
                    all_methods.append(info)
                    methods_in_subdir += 1

                    if info.get("availability_raw"):
                        stats["with_availability"] += 1
                    if info.get("version_since"):
                        stats["with_version_since"] += 1
                    if info.get("version_deprecated"):
                        stats["deprecated"] += 1

            except Exception as e:
                print(f"  ⚠️ Ошибка в {f.name}: {e}")
                continue

        print(f"  Найдено методов: {methods_in_subdir}")

    stats["total"] = len(all_methods)
    print(f"\n=== Всего методов: {stats['total']} ===")
    print(f"  С доступностью: {stats['with_availability']}")
    print(f"  С версией: {stats['with_version_since']}")
    print(f"  Устаревших: {stats['deprecated']}")

    # Сохраняем в SQLite
    print(f"\nСохраняю в SQLite: {db_path}...")
    for method_id, info in enumerate(all_methods, 1):
        save_method_to_db(conn, method_id, platform_version, info)

    update_version_stats(conn, platform_version, stats)
    conn.commit()
    conn.close()

    db_size = os.path.getsize(db_path)
    print(f"✅ Готово! Размер БД: {db_size // 1024} КБ ({db_size / 1024 / 1024:.1f} МБ)")

    # Создаём manifest.json
    manifest_path = db_path.parent / "manifest.json"
    manifest = {
        "platform_version": platform_version,
        "source_hbk": "shcntx_ru.hbk",
        "source_hbk_hash": hbk_hash,
        "source_hbk_date": hbk_date,
        "total_methods": stats["total"],
        "methods_with_availability": stats["with_availability"],
        "methods_with_version_since": stats["with_version_since"],
        "deprecated_methods": stats["deprecated"],
        "built_at": datetime.now().isoformat(),
        "builder_version": "1.0",
        "db_path": str(db_path),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"📋 Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
