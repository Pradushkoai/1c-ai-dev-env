#!/usr/bin/env python3
"""
Построение индекса синтакс-помощника 1С.
Читает распакованные .hbk файлы (HTML), извлекает информацию о методах,
создаёт syntax-helper-index.md для быстрого поиска.

Структура индекса:
1. Сводная статистика
2. Все методы по алфавиту (русскоязычные и англоязычные)
3. Методы по категориям (Глобальный контекст, Справочники, Документы, и т.д.)
"""

import html
import json
import os
import re

# Пути из PathManager (P2.15: paths.py удалён как dead code)
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.path_manager import PathManager

_PATHS = PathManager()
SH_DIR = _PATHS.syntax_helper_dir
OUTPUT_INDEX = _PATHS.syntax_helper_index_md
OUTPUT_JSON = _PATHS.syntax_helper_index_json

# Основные директории с методами
KEY_DIRS = [
    "shcntx_ru",  # Главный синтакс-помощник (методы)
    "shlang_ru",  # Язык
    "shquery_ru",  # Запросы
    "shclang_ru",  # Англоязычная версия языка
]


def strip_html(text):
    """Удаляет HTML-теги и декодирует сущности."""
    # Удаляем скрипты и стили
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    # Удаляем теги
    text = re.sub(r"<[^>]+>", " ", text)
    # Декодируем HTML-сущности
    text = html.unescape(text)
    # Нормализуем пробелы
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_method_info(html_content, file_name):
    """
    Извлекает информацию о методе из HTML-страницы.
    Возвращает dict с полями: name, eng_name, context, syntax, params, returns, description, availability, version.
    """
    info = {
        "file": file_name,
        "title": "",
        "name_ru": "",
        "name_en": "",
        "context": "",
        "syntax": "",
        "params": [],
        "returns": "",
        "description": "",
        "availability": "",
        "version": "",
        "example": "",
        "see_also": [],
    }

    # Заголовок страницы
    m = re.search(r'<h1[^>]*class="V8SH_pagetitle"[^>]*>(.+?)</h1>', html_content, re.DOTALL)
    if m:
        info["title"] = strip_html(m.group(1))
        # Заголовок вида "СправочникМенеджер.<Имя справочника>.НайтиПоКоду (CatalogManager.<Catalog name>.FindByCode)"
        # Извлекаем русское и английское имя
        title = info["title"]
        if "(" in title and ")" in title:
            ru_part = title[: title.rfind("(")].strip()
            en_part = title[title.rfind("(") + 1 : title.rfind(")")].strip()
            # Последний сегмент после точки — имя метода
            if "." in ru_part:
                info["context"] = ru_part.rsplit(".", 1)[0]
                info["name_ru"] = ru_part.rsplit(".", 1)[1]
            else:
                info["name_ru"] = ru_part
            if "." in en_part:
                info["name_en"] = en_part.rsplit(".", 1)[1]
            else:
                info["name_en"] = en_part
        else:
            info["name_ru"] = title

    # Заголовок секции
    m = re.search(r'<p class="V8SH_heading">(.+?)</p>', html_content, re.DOTALL)
    if m:
        heading = strip_html(m.group(1))
        if not info["name_ru"]:
            info["name_ru"] = heading

    # Контекст
    m = re.search(r'<p class="V8SH_title">(.+?)</p>', html_content, re.DOTALL)
    if m:
        info["context"] = strip_html(m.group(1))

    # Синтаксис
    m = re.search(
        r'<p class="V8SH_chapter">Синтаксис:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["syntax"] = strip_html(m.group(1))

    # Параметры — извлекаем список
    params_section = re.search(
        r'<p class="V8SH_chapter">Параметры:</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if params_section:
        params_html = params_section.group(1)
        # Каждый параметр: <div class="V8SH_rubric"> <p...>&lt;Имя&gt; (обязательный/необязательный)</div>описание
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
                    "description": strip_html(desc)[:300],
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
        info["description"] = strip_html(m.group(1))[:500]

    # Доступность
    m = re.search(
        r'<p class="V8SH_chapter">Доступность:\s*</p>(.+?)(?:<p class="V8SH_chapter">|<p class="V8SH_versionInfo">|<HR>)',
        html_content,
        re.DOTALL,
    )
    if m:
        info["availability"] = strip_html(m.group(1))[:300]

    # Версия
    m = re.search(r'<p class="V8SH_versionInfo">(.+?)</p>', html_content, re.DOTALL)
    if m:
        info["version"] = strip_html(m.group(1))

    # См. также
    see_also_matches = re.findall(r'<a href="v8help://[^"]+">([^<]+)</a>', html_content)
    info["see_also"] = list(set(see_also_matches))[:10]  # только первые 10 уникальных

    return info


def is_method_file(file_path):
    """Проверяет, содержит ли файл описание метода (по наличию V8SH_chapter и Синтаксис:)."""
    # Метод-файлы обычно содержат "methods" в пути или "Синтаксис:" в содержимом
    name = os.path.basename(file_path)
    if not name.endswith(".html"):
        return False
    # Пропускаем служебные файлы
    return not (name in ("0.html", "1.html") or re.match(r"^\d+\.html$", name))


def main():
    print(f"Сканирование {SH_DIR}...")

    all_methods = []
    stats = defaultdict(int)

    for subdir in KEY_DIRS:
        subdir_path = Path(SH_DIR) / subdir
        if not subdir_path.exists():
            continue

        print(f"\nОбработка {subdir}...")
        files = list(subdir_path.glob("*.html"))
        print(f"  HTML файлов: {len(files)}")

        methods_in_subdir = 0
        for i, f in enumerate(files):
            if i % 5000 == 0:
                print(f"  Прогресс: {i}/{len(files)}")

            if not is_method_file(f):
                continue

            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()

                # Быстрая проверка — это файл метода?
                if "V8SH_chapter" not in content or "Синтаксис:" not in content:
                    continue

                info = extract_method_info(content, str(f.relative_to(SH_DIR)))
                if info["name_ru"] or info["name_en"]:
                    info["source_dir"] = subdir
                    all_methods.append(info)
                    methods_in_subdir += 1
            except Exception:
                continue

        print(f"  Найдено методов: {methods_in_subdir}")
        stats[subdir] = methods_in_subdir

    print(f"\n=== Всего методов: {len(all_methods)} ===")

    # Сохраняем как JSON для быстрого поиска
    print(f"\nСохраняю JSON в {OUTPUT_JSON}...")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_methods, f, ensure_ascii=False, indent=2)
    print(f"  Размер: {os.path.getsize(OUTPUT_JSON) // 1024} КБ")

    # Строим Markdown индекс
    print(f"\nГенерирую Markdown индекс в {OUTPUT_INDEX}...")

    lines = []
    lines.append("# Индекс синтакс-помощника 1С")
    lines.append("")
    lines.append(f"> Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("> Источник: распакованные .hbk файлы из `syntax-helper/`")
    lines.append(f"> Всего методов: **{len(all_methods)}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Статистика
    lines.append("## 1. Статистика по источникам")
    lines.append("")
    lines.append("| Источник | Кол-во методов |")
    lines.append("|----------|---------------|")
    for subdir in KEY_DIRS:
        if stats[subdir]:
            lines.append(f"| `{subdir}` | {stats[subdir]} |")
    lines.append(f"| **ИТОГО** | **{len(all_methods)}** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 2. Группировка по контексту
    by_context = defaultdict(list)
    for m in all_methods:
        ctx = m["context"] or "(без контекста)"
        by_context[ctx].append(m)

    lines.append("## 2. Методы по контексту")
    lines.append("")
    lines.append(f"Всего контекстов: **{len(by_context)}**")
    lines.append("")
    lines.append("| Контекст | Кол-во методов |")
    lines.append("|----------|---------------|")
    for ctx, methods in sorted(by_context.items(), key=lambda x: -len(x[1]))[:50]:
        ctx_short = ctx[:80].replace("|", "\\|")
        lines.append(f"| `{ctx_short}` | {len(methods)} |")
    if len(by_context) > 50:
        lines.append(f"| ... и ещё {len(by_context) - 50} контекстов | — |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 3. Все методы по алфавиту (русскоязычные)
    lines.append("## 3. Все методы по алфавиту")
    lines.append("")
    lines.append("| № | Имя (RU) | Имя (EN) | Контекст | Синтаксис | Файл |")
    lines.append("|---|----------|----------|----------|-----------|------|")

    sorted_methods = sorted(all_methods, key=lambda x: (x["name_ru"] or x["name_en"]).lower())
    for i, m in enumerate(sorted_methods, 1):
        name_ru = (m["name_ru"] or "—").replace("|", "\\|")[:40]
        name_en = (m["name_en"] or "—").replace("|", "\\|")[:40]
        ctx = (m["context"] or "—").replace("|", "\\|")[:50]
        syn = (m["syntax"] or "—").replace("|", "\\|")[:150]
        file_short = m["file"].split("/")[-1][:60]
        lines.append(f"| {i} | `{name_ru}` | `{name_en}` | {ctx} | {syn} | `{file_short}` |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 4. Как пользоваться
    lines.append("## 4. Как пользоваться индексом")
    lines.append("")
    lines.append("### Поиск метода по имени")
    lines.append("```bash")
    lines.append('# Найти все методы, содержащие "Найти" в имени')
    lines.append('grep "Найти" /home/z/my-project/indexes/syntax-helper-index.md | head -20')
    lines.append("")
    lines.append("# Найти метод по английскому имени")
    lines.append('grep "FindByCode" /home/z/my-project/indexes/syntax-helper-index.md')
    lines.append("```")
    lines.append("")
    lines.append("### Получение полной справки по методу")
    lines.append("```bash")
    lines.append("# Открыть HTML-страницу с полным описанием метода")
    lines.append('cat "/home/z/my-project/syntax-helper/shcntx_ru/<файл_метода>.html"')
    lines.append("```")
    lines.append("")
    lines.append("### Программный поиск через JSON")
    lines.append("```python")
    lines.append("import json")
    lines.append('with open("/home/z/my-project/indexes/syntax-helper-index.json") as f:')
    lines.append("    methods = json.load(f)")
    lines.append("")
    lines.append("# Найти все методы глобального контекста")
    lines.append('gc_methods = [m for m in methods if "Глобальный контекст" in m["context"]]')
    lines.append("")
    lines.append("# Найти метод по имени")
    lines.append("for m in methods:")
    lines.append('    if "НайтиПоКоду" in m["name_ru"]:')
    lines.append('        print(m["syntax"])')
    lines.append('        for p in m["params"]:')
    lines.append('            print(f"  {p["name"]} ({p["required"]}): {p["description"][:100]}")')
    lines.append("        break")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 5. Структура данных
    lines.append("## 5. Структура данных в JSON")
    lines.append("")
    lines.append("Каждый метод в `syntax-helper-index.json` содержит:")
    lines.append("")
    lines.append("```json")
    lines.append("{")
    lines.append('  "file": "shcntx_ru/objects_catalog125_..._FindByCode250.html",')
    lines.append('  "source_dir": "shcntx_ru",')
    lines.append(
        '  "title": "СправочникМенеджер.<Имя справочника>.НайтиПоКоду (CatalogManager.<Catalog name>.FindByCode)",'
    )
    lines.append('  "name_ru": "НайтиПоКоду",')
    lines.append('  "name_en": "FindByCode",')
    lines.append('  "context": "СправочникМенеджер.<Имя справочника>",')
    lines.append('  "syntax": "НайтиПоКоду(<Код>, <ПоискПоПолномуКоду>, <Родитель>, <Владелец>)",')
    lines.append('  "params": [')
    lines.append('    {"name": "Код", "required": "обязательный", "description": "Искомый код..."},')
    lines.append("    ...")
    lines.append("  ],")
    lines.append('  "returns": "Тип: СправочникСсылка, Неопределено...",')
    lines.append('  "description": "Осуществляет поиск элемента по его коду.",')
    lines.append('  "availability": "Сервер, толстый клиент, внешнее соединение...",')
    lines.append('  "version": "Доступен, начиная с версии 8.0.",')
    lines.append('  "see_also": ["..."]')
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 6. Источники
    lines.append("## 6. Источники данных")
    lines.append("")
    lines.append("| Файл / директория | Размер | Что содержит |")
    lines.append("|-------------------|--------|--------------|")

    for subdir in KEY_DIRS:
        subdir_path = Path(SH_DIR) / subdir
        if subdir_path.exists():
            size = sum(f.stat().st_size for f in subdir_path.rglob("*") if f.is_file())
            size_str = f"{size / 1024 / 1024:.1f} МБ" if size > 1024 * 1024 else f"{size / 1024:.0f} КБ"
            count = sum(1 for f in subdir_path.rglob("*") if f.is_file())
            lines.append(f"| `syntax-helper/{subdir}/` | {size_str} | {count} файлов |")

    lines.append("| `indexes/syntax-helper-index.md` | этот файл | структурированный индекс |")
    lines.append("| `indexes/syntax-helper-index.json` | JSON | машиночитаемый индекс для программного поиска |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 7. Покрытие
    lines.append("## 7. Что покрывает индекс")
    lines.append("")
    lines.append(
        "✅ **Глобальный контекст** — все функции доступные в любом модуле (СтрНайти, Сообщить, ТекущаяДата, и т.д.)"
    )
    lines.append(
        "✅ **Методы объектов метаданных** — справочников, документов, регистров, и т.д. (НайтиПоКоду, Записать, Проведён, и т.д.)"
    )
    lines.append("✅ **Методы менеджеров** — СправочникМенеджер, ДокументМенеджер, и т.д.")
    lines.append("✅ **Методы форм** — элементы формы, таблицы, и т.д.")
    lines.append("✅ **Методы запросов** — язык запросов 1С")
    lines.append("✅ **Англоязычные синонимы** — каждый метод имеет русское и английское имя")
    lines.append("")
    lines.append("## 8. Ограничения")
    lines.append("")
    lines.append("- Индекс содержит ~методов с распакованных .hbk файлов")
    lines.append("- Если нужно посмотреть полное описание с примером — открывай HTML файл напрямую")
    lines.append("- Ссылки между методами (см. также) сохранены в JSON формате")

    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Размер Markdown: {os.path.getsize(OUTPUT_INDEX) // 1024} КБ")
    print("\n=== ГОТОВО ===")


if __name__ == "__main__":
    main()
