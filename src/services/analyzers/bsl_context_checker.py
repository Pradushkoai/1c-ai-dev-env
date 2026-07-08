"""
bsl_context_checker.py — Проверка доступности методов платформы в целевом контексте.

Поток 3, Этап 3c: Анализатор BSL-кода на доступность методов.

Использует:
  - PlatformMethodsIndex (SQLite) — справочник методов платформы 1С
  - bsl_tree_sitter.extract_calls_with_types — извлечение вызовов с type inference

Проверяет:
  - CTX001: Метод недоступен в целевом контексте (ERROR)
  - CTX002: Метод устарел (deprecated) — WARNING
  - CTX003: Метод требует более новую версию платформы — ERROR

B6: Реализует Analyzer Protocol — регистрируется через get_default_analyzers()
    и также добавляется в task_processor.check() напрямую.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..platform_methods_index import PlatformMethodsIndex


# ============================================================================
# ДАННЫЕ
# ============================================================================


@dataclass
class ContextViolation:
    """Нарушение доступности метода."""

    rule_id: str
    severity: str  # error | warning
    line: int
    message: str
    method_name: str = ""
    available_in: str = ""
    recommendation: str = ""


# ============================================================================
# КОНТРОЛЛЕР КОНТЕКСТА
# ============================================================================


class BslContextChecker:
    """Анализатор доступности методов платформы 1С в целевом контексте.

    B6: Реализует Analyzer Protocol (source, min_level, check_file).
    B10: Использует type inference для разрешения коллизий имён методов.
    """

    source = "bsl_context_checker"
    min_level = "standard"

    # Глобальные свойства контекста, доступные только на сервере
    # (проверяются отдельно — через точку, а не как вызовы методов)
    _GLOBAL_CONTEXT_PROPS = frozenset({
        "Метаданные", "Metadata",
        "ПараметрыСеанса", "SessionParameters",
        "РабочаяДата", "WorkingDate",
        "Документы", "Documents",
        "Справочники", "Catalogs",
        "РегистрыНакопления", "AccumulationRegisters",
        "РегистрыСведений", "InformationRegisters",
        "Перечисления", "Enums",
        "ПланыСчетов", "ChartsOfAccounts",
        "ПланыОбмена", "ExchangePlans",
        "ПланыВидовРасчета", "ChartsOfCalculationTypes",
        "ПланыВидовХарактеристик", "ChartsOfCharacteristicTypes",
        "Константы", "Constants",
        "Обработки", "DataProcessors",
        "Отчеты", "Reports",
    })

    def __init__(self, paths: Any = None):
        """Инициализация.

        Args:
            paths: PathManager (для определения путей к индексу).
                   Если None — используется PathManager по умолчанию.
        """
        if paths is None:
            from ..path_manager import PathManager
            paths = PathManager()
        self._paths = paths
        self._index: PlatformMethodsIndex | None = None

    def _get_index(self) -> PlatformMethodsIndex | None:
        """Ленивая загрузка индекса платформы."""
        if self._index is not None:
            return self._index
        try:
            idx = PlatformMethodsIndex(paths=self._paths)
            if idx.is_available():
                self._index = idx
                return idx
        except Exception:
            pass
        return None

    def detect_context(self, code: str) -> list[str]:
        """Определить целевой контекст по содержимому BSL-кода.

        Эвристики:
          - &НаКлиенте → thin_client, mobile_client
          - &НаСервере → server
          - Асинх Функция → thin_client (т.к. Асинх только на клиенте)
          - Новый("AddIn. → mobile_client (внешние компоненты)
          - Если ничего не найдено → server (по умолчанию для общих модулей)

        Returns:
            Список контекстов: ['thin_client'], ['server'], ['thin_client', 'mobile_client'], etc.
        """
        has_client = bool(re.search(r"&НаКлиенте", code, re.IGNORECASE))
        has_server = bool(re.search(r"&НаСервере|&НаСервереБезКонтекста", code, re.IGNORECASE))
        has_async = bool(re.search(r"\bАсинх\s+(Процедура|Функция)", code, re.IGNORECASE))

        if has_client and not has_server:
            # Клиентский модуль
            return ["thin_client", "web_client", "mobile_client"]
        if has_server and not has_client:
            # Серверный модуль
            return ["server"]
        if has_async:
            # Асинх — только клиент (BSL-ASYNC-003)
            return ["thin_client", "web_client", "mobile_client"]
        # По умолчанию — проверяем для всех контекстов
        return ["server", "thin_client", "web_client", "mobile_client"]

    def check_file(self, file_path: Path) -> list[ContextViolation]:
        """Проверить BSL файл на доступность методов.

        Реализует Analyzer Protocol (source, min_level, check_file).
        """
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []

        return self.check_code(content)

    def check_code(self, code: str, target_context: list[str] | None = None) -> list[ContextViolation]:
        """Проверить BSL код на доступность методов.

        Args:
            code: BSL код
            target_context: Целевой контекст (если None — автоопределение)

        Returns:
            Список нарушений.
        """
        idx = self._get_index()
        if idx is None:
            return []  # индекс недоступен — не можем проверять

        if target_context is None:
            target_context = self.detect_context(code)

        violations: list[ContextViolation] = []

        # B10: Извлечь вызовы с type inference
        try:
            from ..bsl_tree_sitter import extract_calls_with_types
            calls = extract_calls_with_types(code)
        except ImportError:
            # tree-sitter не доступен — используем regex fallback
            calls = self._extract_calls_regex(code)

        # B10 FIX: Также проверяем глобальные свойства контекста
        # (Метаданные, ПараметрыСеанса, etc.) — они не извлекаются
        # как вызовы методов, а как обращения через точку
        global_context_props = self._find_global_context_props(code)
        for prop_name, line_num in global_context_props:
            # Создаём псевдо-call для проверки
            from ..bsl_tree_sitter import BslMethodCall
            calls.append(BslMethodCall(
                name=prop_name,
                object_var="",
                line=line_num,
                resolved_type="",
            ))

        # Список методов, которые мы знаем — проверяем их
        # (глобальные методы и методы через переменные с известным типом)
        for call in calls:
            # Пропускаем вызовы через переменные с неизвестным типом
            # (не можем определить доступность)
            if call.object_var and not call.resolved_type:
                # Но проверяем если object_var — глобальное свойство контекста
                # (Метаданные, ПараметрыСеанса, etc.)
                if call.object_var in self._GLOBAL_CONTEXT_PROPS:
                    # Это обращение к глобальному свойству (например Метаданные.Справочники)
                    # Проверяем само свойство
                    method = idx.get_method(call.object_var)
                    if method:
                        import json
                        avail_json = method.get("availability_json", "{}")
                        try:
                            availability = json.loads(avail_json)
                        except Exception:
                            availability = {}
                        available_in_any = any(availability.get(ctx, False) for ctx in target_context)
                        if not available_in_any:
                            avail_raw = method.get("availability_raw", "неизвестно")
                            violations.append(
                                ContextViolation(
                                    rule_id="CTX001",
                                    severity="error",
                                    line=call.line,
                                    method_name=call.object_var,
                                    available_in=avail_raw,
                                    message=(
                                        f"Свойство '{call.object_var}' недоступно в контексте "
                                        f"({', '.join(target_context)}). "
                                        f"Доступно: {avail_raw}"
                                    ),
                                    recommendation="Передайте обращение на сервер через серверный вызов",
                                )
                            )
                continue

            method_name = call.name

            # Определяем object_type для разрешения коллизий
            object_type = call.resolved_type if call.resolved_type else ""

            # Проверяем доступность
            method = None
            if object_type:
                method = idx.get_method_in_context(method_name, object_type)
            else:
                method = idx.get_method(method_name)

            if method is None:
                # Метод не найден в справочнике — пропускаем
                # (может быть методом конфигурации, а не платформы)
                continue

            # CTX001: Проверка доступности в контексте
            import json
            avail_json = method.get("availability_json", "{}")
            try:
                availability = json.loads(avail_json)
            except Exception:
                availability = {}

            available_in_any = any(availability.get(ctx, False) for ctx in target_context)

            if not available_in_any:
                avail_raw = method.get("availability_raw", "неизвестно")
                violations.append(
                    ContextViolation(
                        rule_id="CTX001",
                        severity="error",
                        line=call.line,
                        method_name=method_name,
                        available_in=avail_raw,
                        message=(
                            f"Метод '{method_name}' недоступен в контексте "
                            f"({', '.join(target_context)}). "
                            f"Доступен: {avail_raw}"
                        ),
                        recommendation=self._get_recommendation(method_name, target_context, idx),
                    )
                )

            # CTX002: Проверка deprecated
            version_deprecated = method.get("version_deprecated", "")
            if version_deprecated:
                violations.append(
                    ContextViolation(
                        rule_id="CTX002",
                        severity="warning",
                        line=call.line,
                        method_name=method_name,
                        message=(
                            f"Метод '{method_name}' устарел (deprecated с версии "
                            f"{version_deprecated}). Рекомендуется использовать альтернативу."
                        ),
                    )
                )

        return violations

    def _find_global_context_props(self, code: str) -> list[tuple[str, int]]:
        """Найти обращения к глобальным свойствам контекста.

        B10 FIX: Метаданные, ПараметрыСеанса, etc. — это не методы, а свойства.
        Они не извлекаются extract_calls_with_types, но их нужно проверять.

        Returns:
            Список (property_name, line_num)
        """
        result: list[tuple[str, int]] = []
        for line_num, line in enumerate(code.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            for prop in self._GLOBAL_CONTEXT_PROPS:
                # Ищем: Метаданные. (с точкой после)
                pattern = rf"\b{re.escape(prop)}\s*\."
                if re.search(pattern, stripped):
                    result.append((prop, line_num))
                    # Не break — может быть несколько свойств на строке
                    # (например: Метаданные.Справочники.Найти)
        return result

    def _extract_calls_regex(self, code: str) -> list:
        """Fallback: извлечение вызовов через regex (без type inference)."""
        from ..bsl_tree_sitter import BslMethodCall

        calls: list[BslMethodCall] = []
        seen: set[tuple[str, str]] = set()

        for line_num, line in enumerate(code.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue

            # Объект.Метод(
            for m in re.finditer(r"(\w+)\.(\w+)\s*\(", stripped):
                obj, name = m.group(1), m.group(2)
                key = (obj, name)
                if key not in seen:
                    seen.add(key)
                    calls.append(BslMethodCall(name=name, object_var=obj, line=line_num))

            # Глобальный Метод(
            for m in re.finditer(r"(?<![\w.])([А-Яа-я]\w*)\s*\(", stripped):
                name = m.group(1)
                key = ("", name)
                if key not in seen:
                    seen.add(key)
                    calls.append(BslMethodCall(name=name, object_var="", line=line_num))

        return calls

    def _get_recommendation(
        self, method_name: str, target_context: list[str], idx: PlatformMethodsIndex
    ) -> str:
        """Получить рекомендацию по альтернативе."""
        alt = idx.find_alternative(method_name, target_context)
        if alt:
            return f"Альтернатива: {alt.get('name_ru', '?')} ({alt.get('category', '?')})"
        return "Передайте операцию на сервер через серверный вызов"

    def get_stats(self, violations: list[ContextViolation]) -> dict[str, Any]:
        """Статистика по нарушениям."""
        from collections import Counter

        by_severity = Counter(v.severity for v in violations)
        by_rule = Counter(v.rule_id for v in violations)
        return {
            "total": len(violations),
            "by_severity": dict(by_severity),
            "by_rule": dict(by_rule),
        }
