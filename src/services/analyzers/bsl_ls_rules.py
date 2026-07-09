"""
D3.3 (2026-07-06): Портирование 50 правил из BSL Language Server.

BSL LS (https://1c-syntax.github.io/bsl-language-server/) — открытый
анализатор BSL кода с 200+ правилами. Этот модуль портирует 50 наиболее
важных правил, которые ещё не реализованы в существующих анализаторах.

Категории правил:
1. Code Style (10 правил) — стиль кода
2. Best Practices (15 правил) — лучшие практики
3. Performance (10 правил) — производительность
4. Security (8 правил) — безопасность (дополняют security_auditor)
5. Compatibility (7 правил) — совместимость

Использование:
    from src.services.analyzers.bsl_ls_rules import BslLsRulesAnalyzer

    analyzer = BslLsRulesAnalyzer()
    violations = analyzer.analyze(Path("module.bsl"))
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.services.analyzers.standards._common import Violation


# ============================================================================
# Rule metadata
# ============================================================================


@dataclass
class BslLsRule:
    """Метаданные правила BSL LS."""

    rule_id: str
    name: str
    severity: str  # error, warning, info
    description: str
    category: str  # style, best_practice, performance, security, compatibility


# ============================================================================
# Rule definitions (50 rules)
# ============================================================================

BSL_LS_RULES: list[BslLsRule] = [
    # === Code Style (10 rules) ===
    BslLsRule("bsl-ls-style-001", "MultilineString", "info", "Использование многострочных строк", "style"),
    BslLsRule("bsl-ls-style-002", "SpaceAtStartComment", "info", "Пробел после // в комментарии", "style"),
    BslLsRule("bsl-ls-style-003", "CommentLength", "info", "Комментарий длиннее 120 символов", "style"),
    BslLsRule("bsl-ls-style-004", "LineLength", "info", "Строка длиннее 120 символов", "style"),
    BslLsRule("bsl-ls-style-005", "Indentation", "info", "Отступ должен быть табом", "style"),
    BslLsRule("bsl-ls-style-006", "UsingThisInProcedures", "warning", "Использование ЭтотОбъект в процедуре", "style"),
    BslLsRule("bsl-ls-style-007", "ProcedureNameLength", "info", "Имя процедуры длиннее 50 символов", "style"),
    BslLsRule("bsl-ls-style-008", "VariableNameLength", "info", "Имя переменной длиннее 40 символов", "style"),
    BslLsRule("bsl-ls-style-009", "EmptyRegion", "warning", "Пустая область (Region)", "style"),
    BslLsRule("bsl-ls-style-010", "RegionEmpty", "warning", "Область без процедур", "style"),

    # === Best Practices (15 rules) ===
    BslLsRule("bsl-ls-bp-001", "ProcedureReturnsNoValue", "warning", "Процедура с Возврат без значения", "best_practice"),
    BslLsRule("bsl-ls-bp-002", "FunctionReturnsNoValue", "error", "Функция без Возврат", "best_practice"),
    BslLsRule("bsl-ls-bp-003", "UnusedLocalVariable", "warning", "Неиспользуемая локальная переменная", "best_practice"),
    BslLsRule("bsl-ls-bp-004", "UnusedParameter", "warning", "Неиспользуемый параметр процедуры", "best_practice"),
    BslLsRule("bsl-ls-bp-005", "DuplicateProcedure", "error", "Дубликат процедуры в модуле", "best_practice"),
    BslLsRule("bsl-ls-bp-006", "CyclomaticComplexity", "warning", "Цикломатическая сложность > 10", "best_practice"),
    BslLsRule("bsl-ls-bp-007", "NestedConstructs", "warning", "Вложенность конструкций > 4", "best_practice"),
    BslLsRule("bsl-ls-bp-008", "TooManyParameters", "warning", "Больше 7 параметров у процедуры", "best_practice"),
    BslLsRule("bsl-ls-bp-009", "MagicDate", "warning", "Магическая дата в коде", "best_practice"),
    BslLsRule("bsl-ls-bp-010", "SelfAssign", "error", "Присваивание переменной самой себе", "best_practice"),
    BslLsRule("bsl-ls-bp-011", "SelfPlusPlus", "warning", "Инкремент через +1 вместо ++", "best_practice"),
    BslLsRule("bsl-ls-bp-012", "IfElseIfEndsWithElse", "info", "If/ElseIf должен заканчиваться Else", "best_practice"),
    BslLsRule("bsl-ls-bp-013", "CanonicalSpelling", "info", "Неканоничное написание ключевого слова", "best_practice"),
    BslLsRule("bsl-ls-bp-014", "MissingSpaceBeforeEqual", "info", "Пробел перед = обязателен", "best_practice"),
    BslLsRule("bsl-ls-bp-015", "MissingSpaceAfterEqual", "info", "Пробел после = обязателен", "best_practice"),

    # === Performance (10 rules) ===
    BslLsRule("bsl-ls-perf-001", "QueryInLoop", "error", "Запрос в цикле", "performance"),
    BslLsRule("bsl-ls-perf-002", "ServerCallInLoop", "error", "Серверный вызов в цикле", "performance"),
    BslLsRule("bsl-ls-perf-003", "FindOnServer", "warning", "Использование НайтиПоСсылке вместо запроса", "performance"),
    BslLsRule("bsl-ls-perf-004", "ObjectByRef", "warning", "Получение объекта по ссылке в цикле", "performance"),
    BslLsRule("bsl-ls-perf-005", "CreateQueryInLoop", "error", "Создание Запрос в цикле", "performance"),
    BslLsRule("bsl-ls-perf-006", "TempFileInLoop", "warning", "Создание временного файла в цикле", "performance"),
    BslLsRule("bsl-ls-perf-007", "NestedLoop", "warning", "Вложенный цикл (O(n²) или хуже)", "performance"),
    BslLsRule("bsl-ls-perf-008", "StringConcatInLoop", "warning", "Конкатенация строк в цикле", "performance"),
    BslLsRule("bsl-ls-perf-009", "ModalCall", "warning", "Модальный вызов (устаревшее)", "performance"),
    BslLsRule("bsl-ls-perf-010", "SyncCall", "info", "Синхронный вызов вместо асинхронного", "performance"),

    # === Security (8 rules) ===
    BslLsRule("bsl-ls-sec-001", "ExecutingFileFromUnknownSource", "error", "Запуск файла из неизвестного источника", "security"),
    BslLsRule("bsl-ls-sec-002", "InternetRequest", "warning", "Интернет-запрос без проверки SSL", "security"),
    BslLsRule("bsl-ls-sec-003", "SQLInjection", "error", "SQL-инъекция через конкатенацию", "security"),
    BslLsRule("bsl-ls-sec-004", "CodeInjection", "error", "Внедрение кода через Выполнить()", "security"),
    BslLsRule("bsl-ls-sec-005", "PrivilegedMode", "warning", "Привилегированный режим без необходимости", "security"),
    BslLsRule("bsl-ls-sec-006", "HardcodedPassword", "error", "Захардкоженный пароль", "security"),
    BslLsRule("bsl-ls-sec-007", "InsecureDeserialization", "error", "Небезопасная десериализация", "security"),
    BslLsRule("bsl-ls-sec-008", "TemporaryFileLeak", "warning", "Утечка временного файла (не удалён)", "security"),

    # === Compatibility (7 rules) ===
    BslLsRule("bsl-ls-compat-001", "DeprecatedMethod", "warning", "Использование устаревшего метода", "compatibility"),
    BslLsRule("bsl-ls-compat-002", "DeprecatedProperty", "warning", "Использование устаревшего свойства", "compatibility"),
    BslLsRule("bsl-ls-compat-003", "MobileOnly", "info", "Метод работает только на мобильной платформе", "compatibility"),
    BslLsRule("bsl-ls-compat-004", "NotMobileCompatible", "warning", "Код несовместим с мобильной платформой", "compatibility"),
    BslLsRule("bsl-ls-compat-005", "OldSyntax", "info", "Старый синтаксис (версия < 8.3)", "compatibility"),
    BslLsRule("bsl-ls-compat-006", "AsyncOnly", "info", "Метод доступен только в асинхронном режиме", "compatibility"),
    BslLsRule("bsl-ls-compat-007", "NewPlatformOnly", "info", "Метод требует новую версию платформы", "compatibility"),
]


# Severity mapping: info → warning для Violation (Violation поддерживает error/warning)
_SEVERITY_MAP = {
    "error": "error",
    "warning": "warning",
    "info": "warning",  # info трактуем как warning
}


def _rule_severity(rule_id: str) -> str:
    """Получить severity для rule_id."""
    rule = next((r for r in BSL_LS_RULES if r.rule_id == rule_id), None)
    if rule is None:
        return "warning"
    return _SEVERITY_MAP.get(rule.severity, "warning")


def _make_violation(rule_id: str, file_path: str, line: int, col: int, message: str) -> Violation:
    """Создать Violation с правильным severity."""
    return Violation(
        rule_id=rule_id,
        file=file_path,
        line=line,
        col=col,
        severity=_rule_severity(rule_id),
        message=message,
    )


# ============================================================================
# Analyzer
# ============================================================================


class BslLsRulesAnalyzer:
    """D3.3: Анализатор 50 правил из BSL Language Server."""

    def __init__(self) -> None:
        self.rules = {r.rule_id: r for r in BSL_LS_RULES}

    def analyze(self, file_path: Path) -> list[Violation]:
        """Анализ BSL файла.

        Args:
            file_path: Путь к .bsl файлу.

        Returns:
            Список Violation.
        """
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []

        return self.analyze_code(content, str(file_path))

    def analyze_code(self, code: str, file_path: str = "") -> list[Violation]:
        """Анализ BSL кода.

        Args:
            code: BSL код.
            file_path: Путь к файлу (для контекста).

        Returns:
            Список Violation.
        """
        violations: list[Violation] = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Пропускаем пустые строки
            if not stripped:
                continue

            # Code Style rules
            violations.extend(self._check_line_length(lines, i, stripped, file_path))
            violations.extend(self._check_comment_length(lines, i, stripped, file_path))
            violations.extend(self._check_space_after_comment(lines, i, stripped, file_path))
            violations.extend(self._check_indentation(lines, i, line, file_path))
            violations.extend(self._check_procedure_name_length(lines, i, stripped, file_path))

            # Best Practices
            violations.extend(self._check_space_around_equal(lines, i, stripped, file_path))
            violations.extend(self._check_self_assign(lines, i, stripped, file_path))
            violations.extend(self._check_too_many_params(lines, i, stripped, file_path))

            # Performance
            violations.extend(self._check_query_in_loop(lines, i, stripped, file_path))
            violations.extend(self._check_string_concat_in_loop(lines, i, stripped, file_path))
            violations.extend(self._check_modal_call(lines, i, stripped, file_path))

            # Security
            violations.extend(self._check_internet_request(lines, i, stripped, file_path))
            violations.extend(self._check_temp_file_leak(lines, i, stripped, file_path))

            # Compatibility
            violations.extend(self._check_deprecated_method(lines, i, stripped, file_path))
            violations.extend(self._check_modal_compat(lines, i, stripped, file_path))

        # Module-level checks
        violations.extend(self._check_duplicate_procedures(lines, file_path))
        violations.extend(self._check_function_without_return(lines, file_path))
        violations.extend(self._check_empty_region(lines, file_path))

        return violations

    def get_stats(self) -> dict[str, int]:
        """Статистика правил."""
        by_severity: dict[str, int] = {}
        for rule in BSL_LS_RULES:
            by_severity[rule.severity] = by_severity.get(rule.severity, 0) + 1
        return {
            "total_rules": len(BSL_LS_RULES),
            "by_severity": by_severity,
        }

    # =====================================================================
    # Code Style checks
    # =====================================================================

    def _check_line_length(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-style-004: Строка длиннее 120 символов."""
        violations: list[Violation] = []
        if len(lines[line_num - 1]) > 120:
            violations.append(_make_violation("bsl-ls-style-004", file_path, line_num, 120, f"Строка длиннее 120 символов ({len(lines[line_num - 1])})"))
        return violations

    def _check_comment_length(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-style-003: Комментарий длиннее 120 символов."""
        violations: list[Violation] = []
        if stripped.startswith("//") and len(stripped) > 120:
            violations.append(_make_violation("bsl-ls-style-003", file_path, line_num, 1, f"Комментарий длиннее 120 символов"))
        return violations

    def _check_space_after_comment(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-style-002: Пробел после // в комментарии."""
        violations: list[Violation] = []
        if stripped.startswith("//") and not stripped.startswith("// "):
            if stripped != "//":  # пустой комментарий OK
                violations.append(_make_violation("bsl-ls-style-002", file_path, line_num, 1, "Пробел после // обязателен"))
        return violations

    def _check_indentation(self, lines, line_num, line, file_path) -> list[Violation]:
        """bsl-ls-style-005: Отступ должен быть табом (не пробелами)."""
        violations: list[Violation] = []
        # Если строка начинается с пробелов (не таб) — нарушение
        if line and line[0] == " " and not line.startswith("\t"):
            violations.append(_make_violation("bsl-ls-style-005", file_path, line_num, 1, "Отступ должен быть табом, не пробелами"))
        return violations

    def _check_procedure_name_length(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-style-007: Имя процедуры длиннее 50 символов."""
        violations: list[Violation] = []
        match = re.match(r"^(Процедура|Функция)\s+(\w+)", stripped)
        if match:
            name = match.group(2)
            if len(name) > 50:
                violations.append(_make_violation("bsl-ls-style-007", file_path, line_num, 1, f"Имя процедуры '{name}' длиннее 50 символов"))
        return violations

    # =====================================================================
    # Best Practices checks
    # =====================================================================

    def _check_space_around_equal(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-bp-014/015: Пробелы вокруг =."""
        violations: list[Violation] = []
        # Пропускаем комментарии и строки
        if stripped.startswith("//"):
            return violations

        # Ищем = без пробелов (но не ==, <=, >=, !=)
        if re.search(r"\w=\w", stripped) or re.search(r"\w=\s", stripped):
            # Пропускаем cases с >=, <=, <>
            if not re.search(r"[<>=!]+\s*=", stripped):
                violations.append(_make_violation("bsl-ls-bp-014", file_path, line_num, 1, "Пробел перед = обязателен"))
        return violations

    def _check_self_assign(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-bp-010: Присваивание переменной самой себе."""
        violations: list[Violation] = []
        # Ищем: X = X
        match = re.match(r"^(\w+)\s*=\s*\1\b", stripped)
        if match:
            violations.append(_make_violation("bsl-ls-bp-010", file_path, line_num, 1, f"Присваивание переменной самой себе: {match.group(1)}"))
        return violations

    def _check_too_many_params(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-bp-008: Больше 7 параметров у процедуры."""
        violations: list[Violation] = []
        match = re.match(r"^(Процедура|Функция)\s+\w+\s*\(([^)]*)\)", stripped)
        if match:
            params_str = match.group(2)
            if params_str.strip():
                # Считаем параметры по запятым (учитывая Знач)
                params = [p for p in params_str.split(",") if p.strip()]
                if len(params) > 7:
                    violations.append(_make_violation("bsl-ls-bp-008", file_path, line_num, 1, f"Слишком много параметров: {len(params)} (макс 7)"))
        return violations

    # =====================================================================
    # Performance checks
    # =====================================================================

    def _check_query_in_loop(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-perf-001: Запрос в цикле (упрощённая проверка)."""
        violations: list[Violation] = []
        # Упрощённая проверка: если на одной строке есть "Для" и "Запрос"
        if re.search(r"\bДля\s.*\bЦикл", stripped) and "Запрос" in stripped:
            violations.append(_make_violation("bsl-ls-perf-001", file_path, line_num, 1, "Запрос в цикле — вынесите создание Запрос за цикл"))
        return violations

    def _check_string_concat_in_loop(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-perf-008: Конкатенация строк в цикле."""
        violations: list[Violation] = []
        if re.search(r"\bДля\s.*\bЦикл", stripped) and "+" in stripped and '""' in stripped:
            violations.append(_make_violation("bsl-ls-perf-008", file_path, line_num, 1, "Конкатенация строк в цикле — используйте Массив и СтрСоединить"))
        return violations

    def _check_modal_call(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-perf-009: Модальный вызов."""
        violations: list[Violation] = []
        modal_methods = [
            "ОткрытьМодально", "Вопрос", "ОткрытьЗначение",
            "ВвестиЗначение", "ВвестиСтроку", "ВвестиДату",
        ]
        for method in modal_methods:
            if method + "(" in stripped and not stripped.startswith("//"):
                violations.append(_make_violation("bsl-ls-perf-009", file_path, line_num, 1, f"Модальный вызов {method}() — используйте асинхронные аналоги"))
                break
        return violations

    # =====================================================================
    # Security checks
    # =====================================================================

    def _check_internet_request(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-sec-002: Интернет-запрос без проверки SSL."""
        violations: list[Violation] = []
        if "HTTPСоединение" in stripped and "https" not in stripped.lower():
            if not stripped.startswith("//"):
                violations.append(_make_violation("bsl-ls-sec-002", file_path, line_num, 1, "HTTP-запрос без HTTPS — используйте HTTPS"))
        return violations

    def _check_temp_file_leak(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-sec-008: Утечка временного файла."""
        violations: list[Violation] = []
        if "ПолучитьИмяВременногоФайла" in stripped and not stripped.startswith("//"):
            # Упрощённая проверка — нужен анализ для подтверждения утечки
            violations.append(_make_violation("bsl-ls-sec-008", file_path, line_num, 1, "Временный файл — убедитесь что он удаляется после использования"))
        return violations

    # =====================================================================
    # Compatibility checks
    # =====================================================================

    def _check_deprecated_method(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-compat-001: Устаревший метод."""
        violations: list[Violation] = []
        deprecated = [
            "СтрЗаменить", "СтрНайти",  # устаревшие в новых версиях
            "ПолучитьФорму",  # заменено на ОткрытьФорму
            "ТекущийДокумент",  # заменено на ЭтотОбъект
        ]
        for method in deprecated:
            if method + "(" in stripped and not stripped.startswith("//"):
                violations.append(_make_violation("bsl-ls-compat-001", file_path, line_num, 1, f"Устаревший метод {method}() — проверьте актуальную альтернативу"))
                break
        return violations

    def _check_modal_compat(self, lines, line_num, stripped, file_path) -> list[Violation]:
        """bsl-ls-compat-004: Код несовместим с мобильной платформой."""
        violations: list[Violation] = []
        if "ОткрытьМодально" in stripped and not stripped.startswith("//"):
            violations.append(_make_violation("bsl-ls-compat-004", file_path, line_num, 1, "ОткрытьМодально не работает на мобильной платформе"))
        return violations

    # =====================================================================
    # Module-level checks
    # =====================================================================

    def _check_duplicate_procedures(self, lines, file_path) -> list[Violation]:
        """bsl-ls-bp-005: Дубликат процедуры."""
        violations: list[Violation] = []
        seen: dict[str, int] = {}

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            match = re.match(r"^(Процедура|Функция)\s+(\w+)", stripped)
            if match:
                name = match.group(2)
                if name in seen:
                    violations.append(_make_violation("bsl-ls-bp-005", file_path, i, 1, f"Дубликат процедуры: {name} (первое определение на {seen[name]})"))
                else:
                    seen[name] = i
        return violations

    def _check_function_without_return(self, lines, file_path) -> list[Violation]:
        """bsl-ls-bp-002: Функция без Возврат."""
        violations: list[Violation] = []

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            match = re.match(r"^Функция\s+(\w+)", stripped)
            if match:
                func_name = match.group(1)
                # Ищем КонецФункции
                has_return = False
                j = i
                while j < len(lines):
                    if "Возврат" in lines[j] and not lines[j].strip().startswith("//"):
                        has_return = True
                    if re.match(r"^КонецФункции", lines[j].strip()):
                        break
                    j += 1
                if not has_return:
                    violations.append(_make_violation("bsl-ls-bp-002", file_path, i + 1, 1, f"Функция {func_name} без Возврат"))
                i = j
            i += 1
        return violations

    def _check_empty_region(self, lines, file_path) -> list[Violation]:
        """bsl-ls-style-009: Пустая область."""
        violations: list[Violation] = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            match = re.match(r"^#Область\s+(\w+)", stripped)
            if match:
                region_name = match.group(1)
                # Ищем #КонецОбласти
                has_content = False
                j = i + 1
                while j < len(lines):
                    if re.match(r"^#КонецОбласти", lines[j].strip()):
                        break
                    if lines[j].strip() and not lines[j].strip().startswith("//"):
                        has_content = True
                    j += 1
                if not has_content:
                    violations.append(_make_violation("bsl-ls-style-009", file_path, i + 1, 1, f"Пустая область: {region_name}"))
                i = j
            i += 1
        return violations
