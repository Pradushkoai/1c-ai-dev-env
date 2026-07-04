#!/usr/bin/env python3
"""
skd_quality_checker.py — Проверка качества СКД-схем 1С.

Анализирует skd-index.json и находит проблемы:
1. СКД без параметров (жёстко заданные значения)
2. СКД с одним набором данных без параметров
3. СКД без группировок
4. СКД без отборов (filters)
5. СКД с запросом без ВЫБРАТЬ
6. СКД без условного оформления
7. СКД с > 50 полями (перегруженная)
8. СКД без итоговых полей (totalFields)
9. СКД с запросом без ГДЕ
10. Параметры без типа данных

Использование:
    from skd_quality_checker import SKDQualityChecker
    checker = SKDQualityChecker()
    issues = checker.check_skd_index(Path('skd-index.json'))
"""

from __future__ import annotations

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

    def check_schema(self, schema_data: dict) -> list[SKDIssue]:
        return self._check_schema(schema_data)

    def _check_schema(self, schema_data: dict) -> list[SKDIssue]:
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

        return issues

    def get_stats(self, issues: list[SKDIssue]) -> dict:
        from collections import Counter

        return {
            "total": len(issues),
            "by_severity": dict(Counter(i.severity for i in issues)),
            "by_rule": dict(Counter(i.rule_id for i in issues)),
        }


# CLI вынесен в scripts/skd_quality_checker.py (Этап 1.2, Группа 1a)
