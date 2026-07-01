#!/usr/bin/env python3
"""
Генератор Form.elem.empty.json со статическим реквизитом ТаблицаСписка.

Конфигурация «Обход» — мобильное приложение. В нём невозможно программное
создание ДинамическийСписок, и компилятор не видит реквизиты, созданные
через ИзменитьРеквизиты() в runtime.

Решение: объявить реквизит ТаблицаСписка (тип ТаблицаЗначений) статически
в Form.elem.json. Это позволяет обращаться к нему напрямую как
`ТаблицаСписка.Добавить()` в BSL-коде без ошибок компиляции.

Структура raw взята из шаблона Form.elem.template.json (реквизит ПорядокОбхода).
"""
import json
from pathlib import Path

# Идентификатор типа "ТаблицаЗначений" во внутреннем формате 1С
# (взят из Form.elem.template.json, реквизит ПорядокОбхода)
VALUETABLE_TYPE_UUID = "acf6192e-81ca-46ef-93a6-5a6968b78663"


def make_column(name: str, synonym: str, col_id: int, pattern: list) -> dict:
    """Создать описание колонки для ValueTable.

    Args:
        name: Имя колонки
        synonym: Синоним (заголовок)
        col_id: ID колонки (1, 2, 3, ...)
        pattern: Pattern типа данных, например:
            - ["\"D\""] — Дата
            - ["\"B\""] — Булево
            - ["\"S\"", "50", "1"] — Строка(50)
    """
    return {
        "name": name,
        "id": str(col_id),
        "raw": [
            "5",                  # тип элемента: колонка
            str(col_id),          # ID колонки
            "0",
            f'"{name}"',          # имя (в кавычках 1С)
            ["1", "1", ["\"ru\"", f'"{synonym}"']],
            ["\"Pattern\"", pattern],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", "0"],
            "0"
        ]
    }


def make_valuetable_rekvizit(name: str, synonym: str, prop_id: int, columns: list) -> dict:
    """Создать описание реквизита-ТаблицыЗначений с колонками.

    Структура raw идентична ПорядокОбхода из Form.elem.template.json.
    """
    return {
        "name": name,
        "id": str(prop_id),
        "raw": [
            "9",                       # тип: реквизит
            [str(prop_id)],            # ID
            "0",
            f'"{name}"',               # имя
            ["1", "1", ["\"ru\"", f'"{synonym}"']],
            ["\"Pattern\"", ["\"#\"", VALUETABLE_TYPE_UUID]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", "0"],
            ["0", "0"],
            "0",
            "0",
            "0",
            "отдельно",
            ["0", "0"],
            ["0", "0"]
        ],
        "child": columns
    }


def make_objekt_rekvizit(prop_id: int = 1) -> dict:
    """Реквизит 'Объект' — обязателен для формы внешней обработки."""
    return {
        "name": "Объект",
        "id": str(prop_id),
        "raw": [
            "9",
            [str(prop_id)],
            "0",
            "\"Объект\"",
            ["1", "0"],
            ["\"Pattern\"", ["\"#\"", "Родитель"]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", ["0", ["\"B\"", "1"], "0"]],
            ["0", "0"],
            ["0", "0"],
            "1", "0", "0", "0",
            ["0", "0"],
            ["0", "0"]
        ]
    }


def build_form_elem_with_table() -> dict:
    """Собрать Form.elem.json с реквизитами Объект + ТаблицаСписка.

    Колонки ТаблицаСписка соответствуют полям выборки из запроса
    документа ГрафикИВыполнениеОбхода.
    """
    columns = [
        make_column("Дата",                  "Дата",                       1, ["\"D\""]),
        make_column("Номер",                 "Номер",                      2, ["\"S\"", "50", "1"]),
        make_column("ОтветственныйЗаОбход",  "Ответственный за обход",     3, ["\"S\"", "150", "1"]),
        make_column("ВремяСтарта",           "Время старта",               4, ["\"D\""]),
        make_column("ВремяОкончания",        "Время окончания",            5, ["\"D\""]),
        make_column("УведомленияСформированы", "Уведомления сформированы", 6, ["\"B\""]),
        make_column("ВсеМеткиОтсканированы", "Все метки отсканированы",    7, ["\"B\""]),
        make_column("ОтправленоНаСервер",    "Отправлено на сервер",       8, ["\"B\""]),
    ]

    table_prop = make_valuetable_rekvizit("ТаблицаСписка", "Список обходов", 2, columns)

    return {
        "params": None,
        "props": [
            make_objekt_rekvizit(1),
            table_prop,
        ],
        "commands": [],
        "tree": [],
        "data": {}
    }


def main():
    out = Path("/home/z/my-project/repo_work/templates/epf_factory/Form.elem.empty.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    data = build_form_elem_with_table()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Шаблон обновлён: {out}")
    print(f"   Размер: {out.stat().st_size} байт")
    print(f"   Реквизитов: {len(data['props'])}")
    for p in data['props']:
        cols = len(p.get('child', []))
        print(f"   - {p['name']} (id={p['id']}, колонок={cols})")


if __name__ == "__main__":
    main()
