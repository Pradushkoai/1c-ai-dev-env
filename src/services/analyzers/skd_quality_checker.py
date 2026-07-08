#!/usr/bin/env python3
"""
skd_quality_checker.py — Проверка качества СКД-схем 1С.

Анализирует skd-index.json и находит проблемы:
1. SKD001: СКД без параметров (жёстко заданные значения)
2. SKD002: СКД без группировок
3. SKD003: СКД без отборов (filters)
4. SKD004: СКД без итоговых полей (totalFields)
5. SKD005: СКД с > 50 полями (перегруженная)
6. SKD006: СКД с запросом без ГДЕ
7. SKD007: Параметры без типа данных
8. SKD008: СКД без условного оформления
9. SKD009: СКД с пустым запросом
10. SKD010: СКД без источника данных

Усилено по стандартам v8std.ru / ITS:
11. SKD011: Поля периодов без стандартных имён (#std672)
12. SKD012: Вариант с именем «Основной» (#std674)
13. SKD013: Запрос с РАЗЛИЧНЫЕ/СГРУППИРОВАТЬ ПО в динамическом списке (#std732)
14. SKD014: Группировка более 3 уровней вложенности (#std676)
15. SKD015: Иерархический список с РаскрыватьВсеУровни (#std489)

Источники стандартов:
- https://v8std.ru/std/672/ — поля периодов
- https://v8std.ru/std/674/ — заголовок отчёта (варианты)
- https://v8std.ru/std/732/ — запросы в динамических списках
- https://v8std.ru/std/676/ — отчёты вида «таблица», «список»
- https://v8std.ru/std/489/ — ограничения динамических списков

Использование:
    from skd_quality_checker import SKDQualityChecker
    checker = SKDQualityChecker()
    issues = checker.check_skd_index(Path('skd-index.json'))
"""

from __future__ import annotations
from typing import Any

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SKDIssue:
    rule_id: str
    severity: str
    schema_name: str
    parent_name: str
    message: str
    recommendation: str = ""


class SKDQualityChecker:
    """Проверка качества СКД-схем."""

    MAX_FIELDS = 50

    def check_skd_index(self, index_path: Path) -> list[SKDIssue]:
        try:
            with open(index_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        issues = []
        for schema in data.get("schemas", []):
            issues.extend(self._check_schema(schema))
        return issues

    def check_schema(self, schema_data: dict[str, Any]) -> list[SKDIssue]:
        return self._check_schema(schema_data)

    def _check_schema(self, schema_data: dict[str, Any]) -> list[SKDIssue]:
        issues = []
        name = schema_data.get("name", "")
        parent_name = schema_data.get("parent_name", "")
        schema = schema_data.get("schema", {})

        data_sets = schema.get("data_sets", [])
        parameters = schema.get("parameters", [])
        total_fields = schema.get("total_fields", [])
        filters = schema.get("filters", [])
        calculated_fields = schema.get("calculated_fields", [])

        # SKD001: СКД без параметров
        if not parameters:
            # Проверяем, есть ли в запросе &Параметры
            has_params_in_query = False
            for ds in data_sets:
                query = ds.get("query", "")
                if "&" in query:
                    has_params_in_query = True
                    break

            if not has_params_in_query:
                issues.append(
                    SKDIssue(
                        rule_id="SKD001",
                        severity="MEDIUM",
                        schema_name=name,
                        parent_name=parent_name,
                        message="СКД без параметров — отчёт не настраиваемый",
                        recommendation="Добавьте параметры для фильтрации данных (Период, Контрагент, и т.д.)",
                    )
                )

        # SKD002: СКД без группировок (не настроен вывод)
        settings = schema.get("settings", {})
        groupings = settings.get("groupings", []) if isinstance(settings, dict) else []
        # Проверяем в settings — может быть в разных форматах
        has_groupings = False
        if isinstance(settings, dict):
            for key, val in settings.items():
                if "group" in key.lower() and val:
                    has_groupings = True
                    break

        # SKD003: СКД без отборов
        if not filters:
            issues.append(
                SKDIssue(
                    rule_id="SKD003",
                    severity="LOW",
                    schema_name=name,
                    parent_name=parent_name,
                    message="СКД без отборов — пользователь не может фильтровать данные",
                    recommendation="Добавьте отборы для ключевых полей",
                )
            )

        # SKD004: СКД без итоговых полей
        if not total_fields and data_sets:
            issues.append(
                SKDIssue(
                    rule_id="SKD004",
                    severity="LOW",
                    schema_name=name,
                    parent_name=parent_name,
                    message="СКД без итоговых полей — нет подсчёта сумм/количеств",
                    recommendation="Добавьте итоговые поля (Сумма, Количество) для числовых данных",
                )
            )

        # SKD005: СКД с > 50 полями
        total_fields_count = sum(len(ds.get("fields", [])) for ds in data_sets)
        if total_fields_count > self.MAX_FIELDS:
            issues.append(
                SKDIssue(
                    rule_id="SKD005",
                    severity="MEDIUM",
                    schema_name=name,
                    parent_name=parent_name,
                    message=f"Перегруженная СКД: {total_fields_count} полей (рекомендуется < {self.MAX_FIELDS})",
                    recommendation="Разделите отчёт на несколько или удалите ненужные поля",
                )
            )

        # SKD006: Запрос без ГДЕ
        for ds in data_sets:
            query = ds.get("query", "")
            if query and "ИЗ" in query.upper() and "ГДЕ" not in query.upper() and "WHERE" not in query.upper():
                issues.append(
                    SKDIssue(
                        rule_id="SKD006",
                        severity="MEDIUM",
                        schema_name=name,
                        parent_name=parent_name,
                        message="Запрос СКД без ГДЕ — выбираются все строки",
                        recommendation="Добавьте условие ГДЕ или параметры для ограничения выборки",
                    )
                )
                break

        # SKD007: Параметры без типа
        for param in parameters:
            types = param.get("types", [])
            if not types:
                issues.append(
                    SKDIssue(
                        rule_id="SKD007",
                        severity="MEDIUM",
                        schema_name=name,
                        parent_name=parent_name,
                        message=f'Параметр "{param.get("name", "?")}" без типа данных',
                        recommendation="Укажите тип данных для параметра",
                    )
                )
                break

        # SKD008: СКД без условного оформления
        conditional = schema.get("conditionalAppearance", [])
        if not conditional and total_fields:
            issues.append(
                SKDIssue(
                    rule_id="SKD008",
                    severity="LOW",
                    schema_name=name,
                    parent_name=parent_name,
                    message="СКД без условного оформления — нет выделения важных данных",
                    recommendation="Добавьте условное оформление для выделения критических значений",
                )
            )

        # SKD009: СКД с пустым запросом
        for ds in data_sets:
            query = ds.get("query", "")
            if not query or not query.strip():
                issues.append(
                    SKDIssue(
                        rule_id="SKD009",
                        severity="HIGH",
                        schema_name=name,
                        parent_name=parent_name,
                        message="СКД с пустым запросом — отчёт не будет работать",
                        recommendation="Заполните запрос для набора данных",
                    )
                )
                break

        # SKD010: СКД без источника данных
        data_sources = schema.get("data_sources", [])
        if not data_sources:
            issues.append(
                SKDIssue(
                    rule_id="SKD010",
                    severity="HIGH",
                    schema_name=name,
                    parent_name=parent_name,
                    message="СКД без источника данных",
                    recommendation="Добавьте источник данных (Local или Remote)",
                )
            )

        # ====================================================================
        # Усиление по стандартам v8std.ru / ITS
        # ====================================================================

        # SKD011: Поля периодов без стандартных имён (#std672)
        # Стандарт: Период.Год, Период.Квартал, Период.Месяц, Период.День, Период.Час
        # https://v8std.ru/std/672/
        STANDARD_PERIOD_FIELDS = {
            "Период.Год", "Период.Квартал", "Период.Месяц", "Период.Декада",
            "Период.Неделя", "Период.День", "Период.Час", "Период.Минута",
            "Период.Секунда",
        }
        for ds in data_sets:
            for field in ds.get("fields", []):
                field_name = field.get("name", "") or field.get("dataPath", "")
                field_lower = field_name.lower() if isinstance(field_name, str) else ""
                # Если поле похоже на период (содержит "период" в имени)
                if "период" in field_lower and field_name not in STANDARD_PERIOD_FIELDS:
                    # Проверяем, что это не стандартное имя
                    if not any(field_name == sp for sp in STANDARD_PERIOD_FIELDS):
                        issues.append(
                            SKDIssue(
                                rule_id="SKD011",
                                severity="LOW",
                                schema_name=name,
                                parent_name=parent_name,
                                message=(
                                    f'Поле периода "{field_name}" не использует стандартное имя '
                                    f"(должно быть Период.Год/Квартал/Месяц/День/Час)"
                                ),
                                recommendation=(
                                    "Используйте стандартные имена полей периодов по #std672: "
                                    "Период.Год, Период.Квартал, Период.Месяц, Период.День. "
                                    "См. https://v8std.ru/std/672/"
                                ),
                            )
                        )
                        break  # одно предупреждение на набор
            else:
                continue
            break

        # SKD012: Вариант с именем «Основной» (#std674)
        # https://v8std.ru/std/674/
        variants = schema.get("variants", [])
        if not variants and isinstance(schema_data, dict):
            # Может быть в корневом элементе
            variants = schema_data.get("variants", [])
        for variant in variants:
            variant_name = (
                variant.get("name", "")
                or variant.get("presentation", "")
                or variant.get("title", "")
            )
            if isinstance(variant_name, str):
                variant_name_norm = variant_name.strip().lower()
                if variant_name_norm in {"основной", "основная", "default", "main"}:
                    issues.append(
                        SKDIssue(
                            rule_id="SKD012",
                            severity="MEDIUM",
                            schema_name=name,
                            parent_name=parent_name,
                            message=(
                                f'Вариант "{variant_name}" назван "Основной" — название '
                                "не раскрывает смысл отчёта"
                            ),
                            recommendation=(
                                "Дайте варианту осмысленное имя по #std674 (например, "
                                "'Анализ продаж по клиентам'). Запрещено называть вариант "
                                "'Основной'. См. https://v8std.ru/std/674/"
                            ),
                        )
                    )
                    break

        # SKD013: Запрос с РАЗЛИЧНЫЕ/СГРУППИРОВАТЬ ПО в динамическом списке (#std732)
        # https://v8std.ru/std/732/
        is_dynamic_list = (
            schema_data.get("is_dynamic_list", False)
            or schema_data.get("dynamic_list", False)
            or "dynamic" in str(schema_data.get("description", "")).lower()
        )
        if is_dynamic_list:
            for ds in data_sets:
                query = ds.get("query", "") or ""
                query_upper = query.upper()
                if "РАЗЛИЧНЫЕ" in query_upper or "DISTINCT" in query_upper:
                    issues.append(
                        SKDIssue(
                            rule_id="SKD013",
                            severity="HIGH",
                            schema_name=name,
                            parent_name=parent_name,
                            message=(
                                "Динамический список использует РАЗЛИЧНЫЕ — "
                                "блокирует динамическое считывание (#std732)"
                            ),
                            recommendation=(
                                "Уберите РАЗЛИЧНЫЕ из запроса динамического списка. "
                                "По #std732 не использовать РАЗЛИЧНЫЕ и СГРУППИРОВАТЬ ПО. "
                                "См. https://v8std.ru/std/732/"
                            ),
                        )
                    )
                    break
                if "СГРУППИРОВАТЬ ПО" in query_upper or "GROUP BY" in query_upper:
                    issues.append(
                        SKDIssue(
                            rule_id="SKD013",
                            severity="HIGH",
                            schema_name=name,
                            parent_name=parent_name,
                            message=(
                                "Динамический список использует СГРУППИРОВАТЬ ПО — "
                                "блокирует динамическое считывание (#std732)"
                            ),
                            recommendation=(
                                "Уберите СГРУППИРОВАТЬ ПО из запроса динамического списка, "
                                "перенесите расчёты в регистр сведений. "
                                "См. https://v8std.ru/std/732/"
                            ),
                        )
                    )
                    break

        # SKD014: Группировка более 3 уровней вложенности (#std676)
        # https://v8std.ru/std/676/
        if isinstance(settings, dict):
            groupings = (
                settings.get("groupings", [])
                or settings.get("groupItems", [])
                or settings.get("item", [])
            )
            # Сам список groupings = уровень 1; _max_grouping_nesting считает
            # глубину вложенности, поэтому +1 для учета верхнего уровня
            max_nesting = self._max_grouping_nesting(groupings) + 1 if groupings else 0
            if max_nesting > 3:
                issues.append(
                    SKDIssue(
                        rule_id="SKD014",
                        severity="MEDIUM",
                        schema_name=name,
                        parent_name=parent_name,
                        message=(
                            f"Группировка имеет {max_nesting} уровней вложенности "
                            f"(рекомендуется ≤ 3)"
                        ),
                        recommendation=(
                            "По #std676 уровней вложенности группировок должно быть "
                            "не более 3. Разделите отчёт на несколько вариантов. "
                            "См. https://v8std.ru/std/676/"
                        ),
                    )
                )

        # SKD015: Иерархический список с РаскрыватьВсеУровни (#std489)
        # https://v8std.ru/std/489/
        if is_dynamic_list:
            initial_tree_view = (
                schema_data.get("initial_tree_view", "")
                or schema_data.get("initialTreeView", "")
                or ""
            )
            if isinstance(initial_tree_view, str):
                tv_lower = initial_tree_view.lower()
                if "раскрыватьвсеуровни" in tv_lower or "expandall" in tv_lower:
                    issues.append(
                        SKDIssue(
                            rule_id="SKD015",
                            severity="HIGH",
                            schema_name=name,
                            parent_name=parent_name,
                            message=(
                                "Иерархический список с НачальноеОтображениеДерева = "
                                "РаскрыватьВсеУровни — критично снижает скорость (#std489)"
                            ),
                            recommendation=(
                                "Используйте НеРаскрывать или РаскрыватьВерхнийУровень. "
                                "См. https://v8std.ru/std/489/"
                            ),
                        )
                    )

        return issues

    @staticmethod
    def _max_grouping_nesting(groupings: Any, depth: int = 0) -> int:
        """Вычисляет максимальную вложенность группировок."""
        if not isinstance(groupings, list):
            return depth
        if not groupings:
            return depth
        max_child = depth
        for g in groupings:
            if isinstance(g, dict):
                # Ищем вложенные группировки
                for key in ("items", "childItems", "children", "groupings", "subgroups"):
                    nested = g.get(key)
                    if nested:
                        child_depth = SKDQualityChecker._max_grouping_nesting(nested, depth + 1)
                        max_child = max(max_child, child_depth)
            elif isinstance(g, list):
                child_depth = SKDQualityChecker._max_grouping_nesting(g, depth + 1)
                max_child = max(max_child, child_depth)
        return max_child

    def get_stats(self, issues: list[SKDIssue]) -> dict[str, Any]:
        from collections import Counter

        return {
            "total": len(issues),
            "by_severity": dict[str, Any](Counter(i.severity for i in issues)),
            "by_rule": dict[str, Any](Counter(i.rule_id for i in issues)),
        }


# CLI вынесен в scripts/skd_quality_checker.py (Этап 1.2, Группа 1a)
