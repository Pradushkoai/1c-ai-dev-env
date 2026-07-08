#!/usr/bin/env python3
"""
data_exchange_checker.py — Проверка обмена данными в BSL коде 1С.

Анализирует .bsl файлы на соблюдение стандартов обмена данными:
1. DX001: ПередЗаписью без проверки ОбменДанными.Загрузка (#std773)
2. DX002: ПриЗаписи без проверки ОбменДанными.Загрузка (#std773)
3. DX003: ПередУдалением без проверки ОбменДанными.Загрузка (#std773)
4. DX004: Обращение через точку в логике регистрации изменений (#std701)
5. DX005: Логика регистрации не в ПередЗаписью/ПередУдалением (#std701)
6. DX006: Подписка на событие без проверки ОбменДанными.Загрузка (#std773)
7. DX007: Захардкоженный путь файла обмена (#std542)
8. DX008: Использование AdditionalInfo в EnterpriseData-обмене (#std771)
9. DX009: ЗначениеИзСтрокиВнутр для обмена между конфигурациями
10. DX010: Бизнес-логика в обработчике без Возврат при ОбменДанными.Загрузка (#std773)

Источники стандартов:
- https://v8std.ru/std/773/ — ОбменДанными.Загрузка
- https://v8std.ru/std/701/ — Разработка планов обмена с отборами
- https://v8std.ru/std/771/ — Формат EnterpriseData
- https://v8std.ru/std/542/ — Доступ к файловой системе

Использование:
    from data_exchange_checker import DataExchangeChecker
    checker = DataExchangeChecker()
    issues = checker.check_file(Path('Module.bsl'))
"""

from __future__ import annotations
from typing import Any

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DataExchangeIssue:
    """Нарушение стандартов обмена данными."""

    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    line: int
    message: str
    code_snippet: str = ""
    recommendation: str = ""


@dataclass
class DataExchangeRule:
    """Правило проверки обмена данными."""

    rule_id: str
    name: str
    severity: str
    description: str
    recommendation: str


# ============================================================================
# ПРАВИЛА ОБМЕНА ДАННЫМИ
# ============================================================================

DATA_EXCHANGE_RULES = [
    DataExchangeRule(
        rule_id="DX001",
        name="ПередЗаписью без проверки ОбменДанными.Загрузка (#std773)",
        severity="HIGH",
        description="Обработчик ПередЗаписью не проверяет ОбменДанными.Загрузка — бизнес-логика сработает при загрузке обмена.",
        recommendation=(
            "В начале ПередЗаписью добавьте: Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли; "
            "См. https://v8std.ru/std/773/ — #std773"
        ),
    ),
    DataExchangeRule(
        rule_id="DX002",
        name="ПриЗаписи без проверки ОбменДанными.Загрузка (#std773)",
        severity="HIGH",
        description="Обработчик ПриЗаписи не проверяет ОбменДанными.Загрузка — бизнес-логика сработает при загрузке обмена.",
        recommendation=(
            "В начале ПриЗаписи добавьте: Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли; "
            "См. https://v8std.ru/std/773/ — #std773"
        ),
    ),
    DataExchangeRule(
        rule_id="DX003",
        name="ПередУдалением без проверки ОбменДанными.Загрузка (#std773)",
        severity="HIGH",
        description="Обработчик ПередУдалением не проверяет ОбменДанными.Загрузка — регистрация удаления сработает при загрузке.",
        recommendation=(
            "В начале ПередУдалением добавьте: Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли; "
            "См. https://v8std.ru/std/773/ — #std773"
        ),
    ),
    DataExchangeRule(
        rule_id="DX004",
        name="Обращение через точку в логике регистрации (#std701)",
        severity="HIGH",
        description="В логике регистрации изменений (ПланыОбмена.ЗарегистрироватьИзменения) есть обращение через точку — неявное соединение, снижает производительность обмена.",
        recommendation=(
            "Таблицы обмена должны быть самодостаточны. Не обращайтесь через точку к связанным таблицам. "
            "См. https://v8std.ru/std/701/ — #std701"
        ),
    ),
    DataExchangeRule(
        rule_id="DX005",
        name="ПланыОбмена.ЗарегистрироватьИзменения вне ПередЗаписью/ПередУдалением (#std701)",
        severity="MEDIUM",
        description="Регистрация изменений вне обработчиков ПередЗаписью/ПередУдалением — нарушение стандарта.",
        recommendation=(
            "Логику регистрации переносите в ПередЗаписью/ПередУдалением. "
            "См. https://v8std.ru/std/701/ — #std701"
        ),
    ),
    DataExchangeRule(
        rule_id="DX006",
        name="Подписка на событие без проверки ОбменДанными.Загрузка (#std773)",
        severity="HIGH",
        description="Обработчик подписки на событие не проверяет ОбменДанными.Загрузка.",
        recommendation=(
            "В начале обработчика подписки добавьте проверку ОбменДанными.Загрузка. "
            "См. https://v8std.ru/std/773/ — #std773"
        ),
    ),
    DataExchangeRule(
        rule_id="DX007",
        name="Захардкоженный путь файла обмена (#std542)",
        severity="MEDIUM",
        description="Путь к файлу обмена захардкожен — небезопасно и непереносимо.",
        recommendation=(
            "Используйте ПолучитьИмяВременногоФайла() для временных файлов или "
            "КаталогВременныхФайлов(). Запрещены абсолютные пути. "
            "См. https://v8std.ru/std/542/ — #std542"
        ),
    ),
    DataExchangeRule(
        rule_id="DX008",
        name="Использование AdditionalInfo в EnterpriseData (#std771)",
        severity="MEDIUM",
        description="Использование AdditionalInfo в типовом обмене через EnterpriseData — нарушение стандарта.",
        recommendation=(
            "Не используйте AdditionalInfo. Расширяйте формат согласованными изменениями. "
            "См. https://v8std.ru/std/771/ — #std771"
        ),
    ),
    DataExchangeRule(
        rule_id="DX009",
        name="ЗначениеИзСтрокиВнутр для обмена между конфигурациями",
        severity="MEDIUM",
        description="ЗначениеИзСтрокиВнутр() / ЗначениеВСтрокуВнутр() — внутренний формат, только между базами одной конфигурации.",
        recommendation=(
            "Для обмена между разными конфигурациями используйте EnterpriseData (#std771) "
            "или XML/XDTO-сериализацию."
        ),
    ),
    DataExchangeRule(
        rule_id="DX010",
        name="Бизнес-логика в обработчике без Возврат при ОбменДанными.Загрузка (#std773)",
        severity="HIGH",
        description="Бизнес-логика в обработчике записи, но нет Возврат при ОбменДанными.Загрузка.",
        recommendation=(
            "Проверка должна быть: Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли; "
            "в самом начале обработчика. "
            "См. https://v8std.ru/std/773/ — #std773"
        ),
    ),
]


# ============================================================================
# CHECKER ОБМЕНА ДАННЫМИ
# ============================================================================


class DataExchangeChecker:
    """Проверка обмена данными в BSL коде 1С."""

    # Обработчики, требующие проверки ОбменДанными.Загрузка (#std773)
    HANDLERS_REQUIRE_EXCHANGE_CHECK = {
        "ПередЗаписью": "DX001",
        "ПриЗаписи": "DX002",
        "ПередУдалением": "DX003",
    }

    def __init__(self):
        self.rules = {r.rule_id: r for r in DATA_EXCHANGE_RULES}

    def check_file(self, file_path: Path) -> list[DataExchangeIssue]:
        """Проверка одного BSL файла.

        Args:
            file_path: Путь к .bsl файлу

        Returns:
            Список нарушений
        """
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []

        return self.check_code(content, str(file_path))

    def check_code(self, code: str, file_path: str = "") -> list[DataExchangeIssue]:
        """Проверка BSL кода.

        Args:
            code: BSL код
            file_path: Путь к файлу (для контекста)

        Returns:
            Список нарушений
        """
        violations: list[DataExchangeIssue] = []
        lines = code.split("\n")

        # Разбиваем код на процедуры/функции
        procedures = self._split_procedures(lines)

        for proc in procedures:
            # DX001-DX003: Проверка обработчиков на ОбменДанными.Загрузка
            violations.extend(self._check_handler_exchange_check(proc, lines))

            # DX004: Обращение через точку в логике регистрации
            violations.extend(self._check_dot_access_in_registration(proc, lines))

            # DX005: Регистрация вне ПередЗаписью/ПередУдалением
            violations.extend(self._check_registration_outside_handlers(proc, lines))

            # DX006: Подписки на события без проверки
            violations.extend(self._check_subscription_no_check(proc, lines))

        # Построчные проверки
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Пропускаем комментарии
            if stripped.startswith("//"):
                continue

            # DX007: Захардкоженный путь файла обмена
            violations.extend(self._check_hardcoded_path(lines, i, stripped, file_path))

            # DX008: AdditionalInfo в EnterpriseData
            violations.extend(self._check_additional_info(lines, i, stripped, file_path))

            # DX009: ЗначениеИзСтрокиВнутр для обмена
            violations.extend(self._check_internal_serialization(lines, i, stripped, file_path))

        return violations

    def check_path(self, dir_path: Path) -> list[DataExchangeIssue]:
        """Проверка всех BSL файлов в директории."""
        violations = []
        for bsl_file in sorted(dir_path.rglob("*.bsl")):
            violations.extend(self.check_file(bsl_file))
        return violations

    def get_stats(self, violations: list[DataExchangeIssue]) -> dict[str, Any]:
        """Возвращает статистику по нарушениям."""
        from collections import Counter

        by_severity = Counter(v.severity for v in violations)
        by_rule = Counter(v.rule_id for v in violations)
        return {
            "total_violations": len(violations),
            "by_severity": dict[str, Any](by_severity),
            "by_rule": dict[str, Any](by_rule),
            "critical_count": by_severity.get("CRITICAL", 0),
            "high_count": by_severity.get("HIGH", 0),
            "medium_count": by_severity.get("MEDIUM", 0),
            "low_count": by_severity.get("LOW", 0),
        }

    # =====================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =====================================================================

    @dataclass
    class _Procedure:
        """Информация о процедуре/функции."""
        name: str
        start_line: int  # 1-indexed
        end_line: int  # 1-indexed
        is_export: bool = False
        body_lines: list[str] = None

    def _split_procedures(self, lines: list[str]) -> list[_Procedure]:
        """Разбивает код на процедуры/функции."""
        procedures: list[DataExchangeChecker._Procedure] = []
        current_proc: DataExchangeChecker._Procedure | None = None

        proc_pattern = re.compile(
            r"^\s*(Процедура|Procedure|Функция|Function)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)",
            re.IGNORECASE,
        )
        end_pattern = re.compile(
            r"^\s*(КонецПроцедуры|EndProcedure|КонецФункции|EndFunction)",
            re.IGNORECASE,
        )

        for i, line in enumerate(lines, 1):
            if current_proc is None:
                m = proc_pattern.match(line)
                if m:
                    current_proc = self._Procedure(
                        name=m.group(2),
                        start_line=i,
                        end_line=0,
                        is_export="Экспорт" in line or "Export" in line,
                        body_lines=[],
                    )
            else:
                current_proc.body_lines.append(line)
                if end_pattern.match(line):
                    current_proc.end_line = i
                    procedures.append(current_proc)
                    current_proc = None

        # Если файл закончился, а процедура нет — добавим
        if current_proc is not None:
            current_proc.end_line = len(lines)
            procedures.append(current_proc)

        return procedures

    def _check_handler_exchange_check(
        self, proc: _Procedure, lines: list[str]
    ) -> list[DataExchangeIssue]:
        """DX001-DX003: Проверка обработчиков на ОбменДанными.Загрузка."""
        violations = []

        # Определяем, является ли процедура обработчиком
        rule_id = None
        for handler_name, rid in self.HANDLERS_REQUIRE_EXCHANGE_CHECK.items():
            if proc.name.lower() == handler_name.lower():
                rule_id = rid
                break

        if rule_id is None:
            return violations

        # Проверяем первые 10 строк тела — есть ли проверка ОбменДанными.Загрузка
        # с Возврат
        check_lines = proc.body_lines[:10]
        full_body_start = "\n".join(check_lines)

        has_exchange_check = (
            "ОбменДанными.Загрузка" in full_body_start
            and "Возврат" in full_body_start
        )

        if not has_exchange_check:
            violations.append(
                DataExchangeIssue(
                    rule_id=rule_id,
                    severity=self.rules[rule_id].severity,
                    line=proc.start_line,
                    message=(
                        f"{proc.name} без проверки ОбменДанными.Загрузка "
                        f"({self.rules[rule_id].name})"
                    ),
                    code_snippet=lines[proc.start_line - 1][:120],
                    recommendation=self.rules[rule_id].recommendation,
                )
            )

        return violations

    def _check_dot_access_in_registration(
        self, proc: _Procedure, lines: list[str]
    ) -> list[DataExchangeIssue]:
        """DX004: Обращение через точку в логике регистрации изменений."""
        violations = []

        # Ищем в теле процедуры вызовы ПланыОбмена.ЗарегистрироватьИзменения
        for i, line in enumerate(proc.body_lines, proc.start_line + 1):
            if "ЗарегистрироватьИзменения" not in line and "УдалитьРегистрациюИзменений" not in line:
                continue

            # Ищем обращения через точку в аргументах
            # Пример: ПланыОбмена.ЗарегистрироватьИзменения(Узел, ЭтотОбъект.Контрагент.Организация)
            # Извлекаем аргументы после (
            m = re.search(
                r"(ЗарегистрироватьИзменения|УдалитьРегистрациюИзменений)\s*\(([^)]*)\)",
                line,
            )
            if not m:
                continue

            args = m.group(2)
            # Если есть две+ точки подряд в одном аргументе — это разыменование
            # через точку. Пример: ЭтотОбъект.Контрагент.Организация (2 точки)
            # Это нарушает #std701 — неявное соединение с связанной таблицей.
            tokens = re.split(r"[,\s]+", args)
            for token in tokens:
                if not token:
                    continue
                # Считаем точки
                dot_count = token.count(".")
                # ЭтотОбъект.Поле (1 точка) — это нормальное обращение к полю объекта
                # ЭтотОбъект.Поле.Подполе (2+ точки) — это разыменование через точку
                # Ссылка.Поле (1 точка) — это разыменование ссылки (тоже нарушение #std701)
                # Любой токен с 2+ точками — нарушение
                # Токен с 1 точкой, не начинающийся с "ЭтотОбъект." или "ЭтотОбъект." —
                # тоже разыменование (Ссылка.Поле)
                is_self_object_field = token.startswith("ЭтотОбъект.")
                if dot_count >= 2:
                    violations.append(
                        DataExchangeIssue(
                            rule_id="DX004",
                            severity=self.rules["DX004"].severity,
                            line=i,
                            message=(
                                f"Разыменование '{token}' в регистрации изменений "
                                f"(#std701): {line.strip()[:80]}"
                            ),
                            code_snippet=line.strip()[:120],
                            recommendation=self.rules["DX004"].recommendation,
                        )
                    )
                    break  # одно срабатывание на строку
                elif dot_count == 1 and not is_self_object_field:
                    # Ссылка.Поле — разыменование ссылки
                    violations.append(
                        DataExchangeIssue(
                            rule_id="DX004",
                            severity=self.rules["DX004"].severity,
                            line=i,
                            message=(
                                f"Разыменование ссылки '{token}' в регистрации изменений "
                                f"(#std701): {line.strip()[:80]}"
                            ),
                            code_snippet=line.strip()[:120],
                            recommendation=self.rules["DX004"].recommendation,
                        )
                    )
                    break

        return violations

    def _check_registration_outside_handlers(
        self, proc: _Procedure, lines: list[str]
    ) -> list[DataExchangeIssue]:
        """DX005: Регистрация вне ПередЗаписью/ПередУдалением."""
        violations = []

        # Если процедура не ПередЗаписью/ПередУдалением, но вызывает регистрацию
        handler_names_lower = {"передзаписью", "передудалением"}
        if proc.name.lower() in handler_names_lower:
            return violations

        # Также исключаем процедуры, которые явно предназначены для обмена
        # (содержат в имени "Обмен" или "Регистрация")
        name_lower = proc.name.lower()
        if "обмен" in name_lower or "регистраци" in name_lower:
            return violations

        for i, line in enumerate(proc.body_lines, proc.start_line + 1):
            if "ЗарегистрироватьИзменения" in line:
                violations.append(
                    DataExchangeIssue(
                        rule_id="DX005",
                        severity=self.rules["DX005"].severity,
                        line=i,
                        message=(
                            f"ПланыОбмена.ЗарегистрироватьИзменения вне "
                            f"ПередЗаписью/ПередУдалением (#std701): {line.strip()[:80]}"
                        ),
                        code_snippet=line.strip()[:120],
                        recommendation=self.rules["DX005"].recommendation,
                    )
                )
                break  # одно срабатывание на процедуру

        return violations

    def _check_subscription_no_check(
        self, proc: _Procedure, lines: list[str]
    ) -> list[DataExchangeIssue]:
        """DX006: Подписка на событие без проверки ОбменДанными.Загрузка.

        Эвристика: процедура экспортная, в общем модуле, имя содержит типичные
        слова подписок ("ПередЗаписью", "ПриЗаписи", "ПередУдалением").
        """
        violations = []

        # Только если процедура экспортная и имя содержит ключевые слова
        if not proc.is_export:
            return violations

        name_lower = proc.name.lower()
        # Типичные имена обработчиков подписок
        subscription_patterns = [
            "передзаписью", "призаписи", "передудалением",
            "обработкапроведения", "обработкаудаления",
            "передзаписьюдокумента", "призаписидокумента",
        ]
        is_subscription = any(p in name_lower for p in subscription_patterns)
        if not is_subscription:
            return violations

        # Если это обработчик объекта в модуле объекта — он уже покрыт DX001-DX003
        # Подписки обычно в общих модулях — проверим всё тело
        full_body = "\n".join(proc.body_lines)
        if "ОбменДанными.Загрузка" not in full_body:
            violations.append(
                DataExchangeIssue(
                    rule_id="DX006",
                    severity=self.rules["DX006"].severity,
                    line=proc.start_line,
                    message=(
                        f"Подписка на событие {proc.name} без проверки "
                        f"ОбменДанными.Загрузка (#std773)"
                    ),
                    code_snippet=lines[proc.start_line - 1][:120],
                    recommendation=self.rules["DX006"].recommendation,
                )
            )

        return violations

    def _check_hardcoded_path(
        self, lines, line_num, stripped, file_path
    ) -> list[DataExchangeIssue]:
        """DX007: Захардкоженный путь файла обмена."""
        violations = []

        # Если в строке есть запись/чтение файла с захардкоженным путём
        # и контекст — обмен (message, exchange, обмен, сообщение)
        file_ops = [
            "ЗаписьXML.ОткрытьФайл",
            "ЧтениеXML.ОткрытьФайл",
            "КопироватьФайл",
            "ПереместитьФайл",
        ]
        is_file_op = any(op in stripped for op in file_ops)
        if not is_file_op:
            return violations

        # Проверяем захардкоженный путь (строка с : или /)
        # Форматы: "C:\...", "/var/...", "\\server\..."
        if re.search(r'"[A-Za-z]:[\\/]', stripped) or re.search(r'"[/\\][A-Za-z]', stripped):
            # Если путь — это ПолучитьИмяВременногоФайла, то нормально
            if "ПолучитьИмяВременногоФайла" in stripped:
                return violations

            violations.append(
                DataExchangeIssue(
                    rule_id="DX007",
                    severity=self.rules["DX007"].severity,
                    line=line_num,
                    message=f"Захардкоженный путь файла обмена (#std542): {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["DX007"].recommendation,
                )
            )

        return violations

    def _check_additional_info(
        self, lines, line_num, stripped, file_path
    ) -> list[DataExchangeIssue]:
        """DX008: Использование AdditionalInfo в EnterpriseData."""
        violations = []

        # Ищем AdditionalInfo в коде
        if "AdditionalInfo" in stripped or "ДополнительноеСвойство" in stripped:
            # Проверяем контекст — связан ли с EnterpriseData
            # Смотрим 3 строки вокруг
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 2)
            context = "\n".join(lines[start:end])
            if (
                "EnterpriseData" in context
                or "ОбменДанными" in context
                or "Пакет" in context
            ):
                violations.append(
                    DataExchangeIssue(
                        rule_id="DX008",
                        severity=self.rules["DX008"].severity,
                        line=line_num,
                        message=f"AdditionalInfo в EnterpriseData-обмене (#std771): {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["DX008"].recommendation,
                    )
                )

        return violations

    def _check_internal_serialization(
        self, lines, line_num, stripped, file_path
    ) -> list[DataExchangeIssue]:
        """DX009: ЗначениеИзСтрокиВнутр для обмена."""
        violations = []

        # Если ЗначениеИзСтрокиВнутр или ЗначениеВСтрокуВнутр в контексте обмена
        if "ЗначениеИзСтрокиВнутр" in stripped or "ЗначениеВСтрокуВнутр" in stripped:
            # Проверяем контекст
            start = max(0, line_num - 3)
            context = "\n".join(lines[start:line_num])
            exchange_context = (
                "ОбменДанными" in context
                or "Сообщение" in context
                or "Узел" in context
                or "ПланыОбмена" in context
            )
            if exchange_context:
                violations.append(
                    DataExchangeIssue(
                        rule_id="DX009",
                        severity=self.rules["DX009"].severity,
                        line=line_num,
                        message=(
                            f"ЗначениеИзСтрокиВнутр для обмена — используйте EnterpriseData "
                            f"или XML/XDTO: {stripped[:80]}"
                        ),
                        code_snippet=stripped[:120],
                        recommendation=self.rules["DX009"].recommendation,
                    )
                )

        return violations


# ============================================================================
# CLI
# ============================================================================


# CLI вынесен в scripts/data_exchange_checker.py
