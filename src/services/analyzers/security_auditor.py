#!/usr/bin/env python3
"""
security_auditor.py — Аудит безопасности BSL кода 1С.

Проверяет:
1. SQL-инъекции — конкатенация строк в запросах
2. Выполнить()/Вычислить() с пользовательским вводом
3. Хардкод паролей, ключей, токенов
4. Небезопасные COM-объекты
5. Обход RLS через ПривилегированныйРежим
6. Небезопасные файловые операции
7. Использование ВыполнитьПоФайлу без проверки пути
8. Отсутствие проверки прав перед операциями
9. Небезопасное использование ИнтернетСоединение
10. Команды ОС через ЗапуститьПриложение

Использование:
    from security_auditor import SecurityAuditor
    auditor = SecurityAuditor()
    violations = auditor.audit_file(Path('module.bsl'))
"""

from __future__ import annotations
from typing import Any

import re
from dataclasses import dataclass
from pathlib import Path

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================


@dataclass
class SecurityViolation:
    """Нарушение безопасности."""

    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    line: int
    column: int = 0
    message: str = ""
    code_snippet: str = ""
    recommendation: str = ""


@dataclass
class SecurityRule:
    """Правило проверки безопасности."""

    rule_id: str
    name: str
    severity: str
    description: str
    recommendation: str


# ============================================================================
# ПРАВИЛА БЕЗОПАСНОСТИ
# ============================================================================

SECURITY_RULES = [
    SecurityRule(
        rule_id="SEC001",
        name="SQL Injection — конкатенация в запросе",
        severity="CRITICAL",
        description="Обнаружена конкатенация строк при формировании запроса. Это позволяет внедрить произвольный SQL-код.",
        recommendation='Используйте параметры запроса: Запрос.УстановитьПараметр("Имя", Значение)',
    ),
    SecurityRule(
        rule_id="SEC002",
        name="Выполнить() с динамическим кодом",
        severity="CRITICAL",
        description="Использование Выполнить() с динамически сформированным кодом позволяет внедрить произвольный BSL-код.",
        recommendation="Избегайте Выполнить(). Если необходимо — проверяйте входные данные.",
    ),
    SecurityRule(
        rule_id="SEC003",
        name="Вычислить() с динамическим выражением",
        severity="HIGH",
        description="Использование Вычислить() с пользовательским вводом позволяет вычислить произвольное выражение.",
        recommendation="Не используйте Вычислить() с непроверенными данными.",
    ),
    SecurityRule(
        rule_id="SEC004",
        name="Хардкод пароля",
        severity="CRITICAL",
        description="Обнаружен захардкоженный пароль в коде.",
        recommendation="Храните пароли в безопасном хранилище или используйте СредстваКриптографии.",
    ),
    SecurityRule(
        rule_id="SEC005",
        name="Хардкод API ключа/токена",
        severity="CRITICAL",
        description="Обнаружен захардкоженный API ключ или токен.",
        recommendation="Храните ключи в параметрах сеанса или в безопасном хранилище.",
    ),
    SecurityRule(
        rule_id="SEC006",
        name="Небезопасный COM-объект",
        severity="HIGH",
        description="Создание COM-объекта может быть небезопасным — позволяет выполнить произвольный код.",
        recommendation="Проверяйте ProgID COM-объекта перед созданием.",
    ),
    SecurityRule(
        rule_id="SEC007",
        name="Привилегированный режим без проверки",
        severity="HIGH",
        description="УстановкаПривилегированногоРежима(Истина) безусловно — обход RLS и прав доступа.",
        recommendation="Используйте привилегированный режим только при необходимости, с проверкой контекста.",
    ),
    SecurityRule(
        rule_id="SEC008",
        name="ЗапуститьПриложение() с динамическим путём",
        severity="HIGH",
        description="ЗапуститьПриложение() с динамически сформированной строкой — выполнение произвольной команды ОС.",
        recommendation="Проверяйте и санитизируйте путь перед запуском приложения.",
    ),
    SecurityRule(
        rule_id="SEC009",
        name="Небезопасное файловое чтение без проверки пути",
        severity="MEDIUM",
        description="Чтение файла без проверки пути может привести к чтению произвольных файлов (path traversal).",
        recommendation='Проверяйте путь на наличие ".." и ограничивайте директорию.',
    ),
    SecurityRule(
        rule_id="SEC010",
        name="ИнтернетСоединение без проверки SSL",
        severity="MEDIUM",
        description="HTTP-запрос без проверки SSL сертификата — возможность MITM атаки.",
        recommendation="Используйте HTTPS и проверяйте сертификат.",
    ),
    SecurityRule(
        rule_id="SEC011",
        name="Отсутствие проверки прав перед записью",
        severity="MEDIUM",
        description="Запись объекта без проверки ПравоДоступа — возможна несанкционированная модификация.",
        recommendation='Проверяйте ПравоДоступа("Запись", Метаданные.Объект) перед записью.',
    ),
    SecurityRule(
        rule_id="SEC012",
        name="Небезопасная сериализация",
        severity="MEDIUM",
        description="ЗначениеИзСтрокиВнутр() с непроверенными данными — возможность десериализации произвольных объектов.",
        recommendation="Не используйте ЗначениеИзСтрокиВнутр() с пользовательским вводом.",
    ),
    SecurityRule(
        rule_id="SEC013",
        name="Формирование XML без экранирования",
        severity="MEDIUM",
        description="Формирование XML через конкатенацию строк без экранирования — XML injection.",
        recommendation="Используйте ЗаписьXML для формирования XML.",
    ),
    SecurityRule(
        rule_id="SEC014",
        name="Хардкод IP-адреса сервера",
        severity="LOW",
        description="Захардкоженный IP-адрес или URL сервера в коде.",
        recommendation="Используйте параметры или константы для адресов серверов.",
    ),
    SecurityRule(
        rule_id="SEC015",
        name="Использование ШифрованиеДанных без проверки",
        severity="MEDIUM",
        description="Использование устаревшего ШифрованиеДанных — небезопасное шифрование.",
        recommendation="Используйте СредстваКриптографии для надёжного шифрования.",
    ),
    # Усиление по стандартам v8std.ru / ITS — #std748, #std770, #std774, #std775, #std794
    SecurityRule(
        rule_id="SEC016",
        name="HTTPСоединение/WSПрокси/FTPСоединение без таймаута (#std748)",
        severity="HIGH",
        description="Соединение с внешним ресурсом без явного указания таймаута — программа зависает при недоступности.",
        recommendation=(
            "Укажите таймаут (обычно 30-60 сек, не более 3 минут). "
            "См. https://v8std.ru/std/748/ — #std748"
        ),
    ),
    SecurityRule(
        rule_id="SEC017",
        name="Выполнить/Вычислить без УстановитьБезопасныйРежим (#std770)",
        severity="CRITICAL",
        description="Выполнить()/Вычислить() на сервере без включения безопасного режима — выполнение произвольного кода.",
        recommendation=(
            "Перед Выполнить/Вычислить вызывайте УстановитьБезопасныйРежим(Истина). "
            "Или используйте ОбщегоНазначения.ВыполнитьВБезопасномРежиме(). "
            "См. https://v8std.ru/std/770/ — #std770"
        ),
    ),
    SecurityRule(
        rule_id="SEC018",
        name="КомандаСистемы/ЗапуститьПриложение с опасными символами (#std774)",
        severity="CRITICAL",
        description="Запуск внешнего приложения со строкой, содержащей опасные символы ($ ` | || ; & &&) — командная инъекция.",
        recommendation=(
            "Санитизируйте командную строку. Запрещены символы: $ ` | || ; & &&. "
            "См. https://v8std.ru/std/774/ — #std774"
        ),
    ),
    SecurityRule(
        rule_id="SEC019",
        name="COM Word/Excel без DisableAutoMacros (#std775)",
        severity="HIGH",
        description="Открытие Word/Excel через COM без отключения макросов — выполнение произвольного кода в документе.",
        recommendation=(
            "Перед открытием Word: ОбъектWord.WordBasic.DisableAutoMacros(1). "
            "Перед открытием Excel: ОбъектExcel.AutomationSecurity = 3. "
            "См. https://v8std.ru/std/775/ — #std775"
        ),
    ),
    SecurityRule(
        rule_id="SEC020",
        name="Внешняя обработка/расширение без БСП-механизма (#std669)",
        severity="HIGH",
        description="Загрузка внешней обработки/расширения/компоненты напрямую из файла — выполнение непроверенного кода.",
        recommendation=(
            "Используйте подсистемы БСП: 'Дополнительные отчёты и обработки', "
            "'Внешние компоненты'. Запрещено 'Файл – Открыть' в production. "
            "См. https://v8std.ru/std/669/ — #std669"
        ),
    ),
]


# ============================================================================
# АУДИТОР БЕЗОПАСНОСТИ
# ============================================================================


class SecurityAuditor:
    """Аудитор безопасности BSL кода 1С."""

    def __init__(self):
        self.rules = {r.rule_id: r for r in SECURITY_RULES}

    def audit_file(self, file_path: Path) -> list[SecurityViolation]:
        """Аудит одного BSL файла.

        Args:
            file_path: Путь к .bsl файлу

        Returns:
            Список нарушений безопасности
        """
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []

        return self.audit_code(content, str(file_path))

    def audit_code(self, code: str, file_path: str = "") -> list[SecurityViolation]:
        """Аудит BSL кода.

        Args:
            code: BSL код
            file_path: Путь к файлу (для контекста)

        Returns:
            Список нарушений
        """
        violations = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Пропускаем комментарии
            if stripped.startswith("//"):
                continue

            # SEC001: SQL-инъекция — конкатенация в запросе
            violations.extend(self._check_sql_injection(lines, i, stripped, file_path))

            # SEC002: Выполнить() с динамическим кодом
            violations.extend(self._check_execute(lines, i, stripped, file_path))

            # SEC003: Вычислить() с динамическим выражением
            violations.extend(self._check_eval(lines, i, stripped, file_path))

            # SEC004: Хардкод пароля
            violations.extend(self._check_hardcoded_password(lines, i, stripped, file_path))

            # SEC005: Хардкод API ключа/токена
            violations.extend(self._check_hardcoded_token(lines, i, stripped, file_path))

            # SEC006: Небезопасный COM-объект
            violations.extend(self._check_com_object(lines, i, stripped, file_path))

            # SEC007: Привилегированный режим
            violations.extend(self._check_privileged_mode(lines, i, stripped, file_path))

            # SEC008: ЗапуститьПриложение
            violations.extend(self._check_run_app(lines, i, stripped, file_path))

            # SEC009: Небезопасное файловое чтение
            violations.extend(self._check_path_traversal(lines, i, stripped, file_path))

            # SEC010: ИнтернетСоединение без SSL
            violations.extend(self._check_http_no_ssl(lines, i, stripped, file_path))

            # SEC011: Отсутствие проверки прав перед записью
            violations.extend(self._check_no_rights_check(lines, i, stripped, file_path))

            # SEC012: Небезопасная десериализация
            violations.extend(self._check_deserialization(lines, i, stripped, file_path))

            # SEC013: XML injection
            violations.extend(self._check_xml_injection(lines, i, stripped, file_path))

            # SEC014: Хардкод IP/URL
            violations.extend(self._check_hardcoded_url(lines, i, stripped, file_path))

            # SEC015: Устаревшее шифрование
            violations.extend(self._check_weak_crypto(lines, i, stripped, file_path))

            # SEC016: HTTPСоединение/WSПрокси без таймаута (#std748)
            violations.extend(self._check_external_no_timeout(lines, i, stripped, file_path))

            # SEC017: Выполнить/Вычислить без безопасного режима (#std770)
            violations.extend(self._check_exec_no_safe_mode(lines, i, stripped, file_path))

            # SEC018: КомандаСистемы с опасными символами (#std774)
            violations.extend(self._check_cmd_injection(lines, i, stripped, file_path))

            # SEC019: COM Word/Excel без DisableAutoMacros (#std775)
            violations.extend(self._check_com_no_macro_disable(lines, i, stripped, file_path))

            # SEC020: Внешняя обработка без БСП (#std669)
            violations.extend(self._check_external_code_load(lines, i, stripped, file_path))

        return violations

    def audit_path(self, dir_path: Path) -> list[SecurityViolation]:
        """Аудит всех BSL файлов в директории.

        Args:
            dir_path: Директория для аудита

        Returns:
            Список всех нарушений
        """
        violations = []
        for bsl_file in sorted(dir_path.rglob("*.bsl")):
            violations.extend(self.audit_file(bsl_file))
        return violations

    def get_stats(self, violations: list[SecurityViolation]) -> dict[str, Any]:
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
    # ПРАВИЛА ПРОВЕРКИ
    # =====================================================================

    def _check_sql_injection(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC001: SQL-инъекция — конкатенация строк в запросе."""
        violations = []

        # Ищем: Запрос.Текст = "..." + ... или Запрос.Текст = СтрСоединить(...)
        patterns = [
            (r'[Тт]екст\s*=\s*"[^"]*"\s*\+', "Конкатенация в Запрос.Текст"),
            (r'[Тt]ext\s*=\s*"[^"]*"\s*\+', "Конкатенация в Query.Text"),
            (r"СтрСоединить\s*\([^)]*[Тт]екст", "СтрСоединить для формирования запроса"),
            (r'"\s*\+\s*[^;]*\+.*Запрос', "Множественная конкатенация с запросом"),
            (r"СтрШаблон\s*\([^)]*ВЫБРАТЬ", "СтрШаблон для формирования запроса"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, stripped):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC001",
                        severity="CRITICAL",
                        line=line_num,
                        message=f"{desc}: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC001"].recommendation,
                    )
                )
                break

        return violations

    def _check_execute(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC002: Выполнить() с динамическим кодом."""
        violations = []

        # Выполнить(Стр...) или Выполнить("..." + ...)
        if re.search(r"Выполнить\s*\(", stripped):
            # Проверяем что аргумент не статичный строковый литерал
            if not re.search(r'Выполнить\s*\(\s*"[^"]*"\s*\)', stripped):
                # Это не статичная строка — потенциально опасно
                # Проверяем: переменная, конкатенация, СтрШаблон
                if (
                    re.search(r"Выполнить\s*\(\s*[А-Яа-я]", stripped)
                    or re.search(r"Выполнить\s*\(\s*Стр", stripped)
                    or re.search(r'Выполнить\s*\(\s*"[^"]*"\s*\+', stripped)
                    or re.search(r"Выполнить\s*\(\s*СтрШаблон", stripped)
                ):
                    violations.append(
                        SecurityViolation(
                            rule_id="SEC002",
                            severity="CRITICAL",
                            line=line_num,
                            message=f"Выполнить() с динамическим кодом: {stripped[:80]}",
                            code_snippet=stripped[:120],
                            recommendation=self.rules["SEC002"].recommendation,
                        )
                    )

        return violations

    def _check_eval(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC003: Вычислить() с динамическим выражением."""
        violations = []

        if re.search(r"Вычислить\s*\(", stripped):
            # Проверяем что аргумент не строковый литерал
            if not re.search(r'Вычислить\s*\(\s*"[^"]*"\s*\)', stripped):
                if re.search(r"Вычислить\s*\(\s*[А-Яа-я]", stripped):
                    violations.append(
                        SecurityViolation(
                            rule_id="SEC003",
                            severity="HIGH",
                            line=line_num,
                            message=f"Вычислить() с динамическим выражением: {stripped[:80]}",
                            code_snippet=stripped[:120],
                            recommendation=self.rules["SEC003"].recommendation,
                        )
                    )

        return violations

    def _check_hardcoded_password(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC004: Хардкод пароля."""
        violations = []

        patterns = [
            r'[Пп]ароль\s*=\s*"[^"]+"',
            r'[Пp]assword\s*=\s*"[^"]+"',
            r"[Пп]ароль\s*=\s*\'[^\']+\'",
            r'Соединение\s*=\s*"[^"]*:[^"]*@',  # user:pass@host
        ]

        for pattern in patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC004",
                        severity="CRITICAL",
                        line=line_num,
                        message=f"Хардкод пароля: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC004"].recommendation,
                    )
                )
                break

        return violations

    def _check_hardcoded_token(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC005: Хардкод API ключа/токена."""
        violations = []

        patterns = [
            r'[Тт]окен\s*=\s*"[A-Za-z0-9_\-]{20,}"',
            r'[Tt]oken\s*=\s*"[A-Za-z0-9_\-]{20,}"',
            r'[Кк]люч\s*=\s*"[A-Za-z0-9_\-]{20,}"',
            r'[Aa]pi[_-]?[Kk]ey\s*=\s*"[^"]+"',
            r"[Aa]uthorization.*[Bb]earer\s",
            r'secret\s*=\s*"[^"]+"',
            r"[Bb]earer\s+[A-Za-z0-9_\-.]{10,}",
        ]

        for pattern in patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC005",
                        severity="CRITICAL",
                        line=line_num,
                        message=f"Хардкод API ключа/токена: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC005"].recommendation,
                    )
                )
                break

        return violations

    def _check_com_object(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC006: Небезопасный COM-объект."""
        violations = []

        if re.search(r"Новый\s+COMОбъект\s*\(", stripped):
            # Если ProgID формируется динамически
            if re.search(r"Новый\s+COMОбъект\s*\(\s*[А-Яа-я]", stripped) and not re.search(
                r'Новый\s+COMОбъект\s*\(\s*"[^"]+"\s*\)', stripped
            ):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC006",
                        severity="HIGH",
                        line=line_num,
                        message=f"COM-объект с динамическим ProgID: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC006"].recommendation,
                    )
                )
            elif re.search(r'Новый\s+COMОбъект\s*\(\s*"[^"]+"\s*\)', stripped):
                # Статичный ProgID — проверяем на опасные
                dangerous_progs = ["WScript.Shell", "Shell.Application", "Scripting.FileSystemObject"]
                for prog in dangerous_progs:
                    if prog.lower() in stripped.lower():
                        violations.append(
                            SecurityViolation(
                                rule_id="SEC006",
                                severity="HIGH",
                                line=line_num,
                                message=f"Опасный COM-объект {prog}: {stripped[:80]}",
                                code_snippet=stripped[:120],
                                recommendation=self.rules["SEC006"].recommendation,
                            )
                        )
                        break

        return violations

    def _check_privileged_mode(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC007: Привилегированный режим без проверки."""
        violations = []

        if re.search(r"УстановкаПривилегированногоРежима\s*\(\s*Истина\s*\)", stripped) or re.search(
            r"УстановкаПривилегированногоРежима\s*\(\s*True\s*\)", stripped
        ):
            violations.append(
                SecurityViolation(
                    rule_id="SEC007",
                    severity="HIGH",
                    line=line_num,
                    message=f"Привилегированный режим безусловно: {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC007"].recommendation,
                )
            )

        return violations

    def _check_run_app(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC008: ЗапуститьПриложение с динамическим путём."""
        violations = []

        if re.search(r"ЗапуститьПриложение\s*\(", stripped):
            # Если путь формируется динамически
            if not re.search(r'ЗапуститьПриложение\s*\(\s*"[^"]+"\s*\)', stripped):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC008",
                        severity="HIGH",
                        line=line_num,
                        message=f"ЗапуститьПриложение с динамическим путём: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC008"].recommendation,
                    )
                )

        return violations

    def _check_path_traversal(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC009: Path traversal — чтение файла без проверки пути."""
        violations = []

        # Чтение файла с переменной-путём без проверки
        if re.search(r"(Прочитать|ЧтениеТекста|ЗначениеИзФайла|КопироватьФайл|ПереместитьФайл)\s*\(", stripped):
            if re.search(
                r"(Прочитать|ЧтениеТекста|ЗначениеИзФайла|КопироватьФайл|ПереместитьФайл)\s*\(\s*[А-Яа-я]", stripped
            ):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC009",
                        severity="MEDIUM",
                        line=line_num,
                        message=f"Файловая операция без проверки пути: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC009"].recommendation,
                    )
                )

        return violations

    def _check_http_no_ssl(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC010: HTTP без SSL."""
        violations = []

        if re.search(r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)", stripped, re.IGNORECASE):
            violations.append(
                SecurityViolation(
                    rule_id="SEC010",
                    severity="MEDIUM",
                    line=line_num,
                    message=f"HTTP без SSL: {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC010"].recommendation,
                )
            )

        return violations

    def _check_no_rights_check(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC011: Отсутствие проверки прав перед записью."""
        violations = []

        # Если .Записать() без проверки ПравоДоступа в ближайших строках
        if re.search(r"\.Записать\s*\(\s*\)", stripped):
            # Проверяем 5 строк вверх на наличие ПравоДоступа
            start = max(0, line_num - 6)
            context = " ".join(lines[start:line_num])
            if "ПравоДоступа" not in context:
                violations.append(
                    SecurityViolation(
                        rule_id="SEC011",
                        severity="MEDIUM",
                        line=line_num,
                        message=f"Запись без проверки прав: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC011"].recommendation,
                    )
                )

        return violations

    def _check_deserialization(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC012: Небезопасная десериализация."""
        violations = []

        if re.search(r"ЗначениеИзСтрокиВнутр\s*\(", stripped):
            violations.append(
                SecurityViolation(
                    rule_id="SEC012",
                    severity="MEDIUM",
                    line=line_num,
                    message=f"ЗначениеИзСтрокиВнутр() — небезопасная десериализация: {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC012"].recommendation,
                )
            )

        return violations

    def _check_xml_injection(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC013: XML injection — формирование XML через конкатенацию."""
        violations = []

        # Формирование XML через строку
        if re.search(r'"<[A-Za-z][^"]*"\s*\+', stripped) or re.search(r'"\s*\+\s*"<[A-Za-z]', stripped):
            if "xml" in stripped.lower() or "<" in stripped:
                violations.append(
                    SecurityViolation(
                        rule_id="SEC013",
                        severity="MEDIUM",
                        line=line_num,
                        message=f"Формирование XML через конкатенацию: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC013"].recommendation,
                    )
                )

        return violations

    def _check_hardcoded_url(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC014: Хардкод IP/URL сервера."""
        violations = []

        # IP-адрес
        if re.search(r'"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"', stripped):
            # Исключаем 127.0.0.1, 0.0.0.0
            if not re.search(r'"(127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.255)"', stripped):
                violations.append(
                    SecurityViolation(
                        rule_id="SEC014",
                        severity="LOW",
                        line=line_num,
                        message=f"Хардкод IP-адреса: {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC014"].recommendation,
                    )
                )

        return violations

    def _check_weak_crypto(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC015: Устаревшее шифрование."""
        violations = []

        if "ШифрованиеДанных" in stripped and "СредстваКриптографии" not in stripped:
            violations.append(
                SecurityViolation(
                    rule_id="SEC015",
                    severity="MEDIUM",
                    line=line_num,
                    message=f"Устаревшее ШифрованиеДанных: {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC015"].recommendation,
                )
            )

        return violations

    # =====================================================================
    # Усиление по стандартам v8std.ru / ITS
    # =====================================================================

    def _check_external_no_timeout(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC016: HTTPСоединение/WSПрокси/FTPСоединение без таймаута (#std748).

        https://v8std.ru/std/748/
        """
        violations = []

        # Проверяем создание соединения с внешним ресурсом
        external_patterns = [
            r"Новый\s+HTTPСоединение\s*\(",
            r"Новый\s+WSПрокси\s*\(",
            r"Новый\s+WSОпределения\s*\(",
            r"Новый\s+FTPСоединение\s*\(",
            r"Новый\s+ИнтернетПочтовыйПрофиль\s*\(",
        ]
        for pattern in external_patterns:
            if re.search(pattern, stripped):
                # Проверяем, что вызов многострочный (ищем таймаут в следующих строках)
                # или что в текущей строке нет таймаута
                # Таймаут — обычно 6-й параметр (HTTPСоединение) или именованный
                # Ищем 'Таймаут' или числовой параметр >= 5-й позиции
                end_line = min(line_num + 5, len(lines))
                full_call = "\n".join(lines[line_num - 1 : end_line])

                # Эвристика: ищем явный 'Таймаут' или числовой аргумент
                has_timeout = (
                    "Таймаут" in full_call
                    or re.search(r",\s*\d{1,4}\s*[,\)]", full_call)
                )
                # Если соединение закрывается на той же строке — проверяем только её
                if ")" in stripped and "(" in stripped:
                    # Однострочный вызов
                    has_timeout = (
                        "Таймаут" in stripped
                        or re.search(r",\s*\d{1,4}\s*\)", stripped) is not None
                    )

                if not has_timeout:
                    violations.append(
                        SecurityViolation(
                            rule_id="SEC016",
                            severity="HIGH",
                            line=line_num,
                            message=f"Внешнее соединение без таймаута (#std748): {stripped[:80]}",
                            code_snippet=stripped[:120],
                            recommendation=self.rules["SEC016"].recommendation,
                        )
                    )
                break  # одно срабатывание на строку

        return violations

    def _check_exec_no_safe_mode(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC017: Выполнить/Вычислить без УстановитьБезопасныйРежим (#std770).

        https://v8std.ru/std/770/
        """
        violations = []

        # Если есть Выполнить/Вычислить с динамической строкой
        has_exec = (
            re.search(r"Выполнить\s*\(", stripped) is not None
            or re.search(r"Вычислить\s*\(", stripped) is not None
        )
        if not has_exec:
            return violations

        # Проверяем, что это не статичный литерал
        is_static = (
            re.search(r'Выполнить\s*\(\s*"[^"]*"\s*\)', stripped) is not None
            or re.search(r'Вычислить\s*\(\s*"[^"]*"\s*\)', stripped) is not None
        )
        if is_static:
            return violations

        # Проверяем 5 строк до и 1 после — есть ли УстановитьБезопасныйРежим(Истина)
        start = max(0, line_num - 6)
        end = min(len(lines), line_num + 1)
        context = "\n".join(lines[start:end])

        has_safe_mode = (
            "УстановитьБезопасныйРежим(Истина)" in context
            or "УстановитьБезопасныйРежим(True)" in context
            or "ВыполнитьВБезопасномРежиме" in context
            or "ВычислитьВБезопасномРежиме" in context
        )
        if not has_safe_mode:
            violations.append(
                SecurityViolation(
                    rule_id="SEC017",
                    severity="CRITICAL",
                    line=line_num,
                    message=f"Выполнить/Вычислить без УстановитьБезопасныйРежим (#std770): {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC017"].recommendation,
                )
            )

        return violations

    def _check_cmd_injection(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC018: КомандаСистемы/ЗапуститьПриложение с опасными символами (#std774).

        https://v8std.ru/std/774/
        """
        violations = []

        # Ищем вызов запуска приложения и извлекаем аргумент-строку
        cmd_match = re.search(
            r"(КомандаСистемы|ЗапуститьПриложение|НачатьЗапускПриложения)\s*\(\s*(.+?)\s*\)",
            stripped,
        )
        if not cmd_match:
            return violations

        args = cmd_match.group(2)

        # Опасные символы по #std774: $ ` | || ; & &&
        # Проверяем только внутри аргументов, не в конце оператора
        dangerous_chars = ["$", "`", "||", "&&"]
        # Одинарные | и & — отдельно, чтобы не путать с && и ||
        # ; — отдельно, чтобы не путать с концом оператора (если ; внутри строки)
        for char in dangerous_chars:
            if char in args:
                violations.append(
                    SecurityViolation(
                        rule_id="SEC018",
                        severity="CRITICAL",
                        line=line_num,
                        message=f"Командная строка с опасным символом '{char}' (#std774): {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC018"].recommendation,
                    )
                )
                return violations

        # Проверяем ; только если она внутри строкового литерала
        # (это означает, что ; — часть команды, а не конец оператора)
        # Ищем строку вида "...;..." — точка с запятой внутри кавычек
        if re.search(r'"[^"]*;[^"]*"', args):
            violations.append(
                SecurityViolation(
                    rule_id="SEC018",
                    severity="CRITICAL",
                    line=line_num,
                    message=f"Командная строка с опасным символом ';' (#std774): {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC018"].recommendation,
                )
            )

        # Одиночный | и & — внутри строк
        if re.search(r'"[^"]*\|[^|][^"]*"', args) or re.search(r'"[^"]*&[^&][^"]*"', args):
            violations.append(
                SecurityViolation(
                    rule_id="SEC018",
                    severity="CRITICAL",
                    line=line_num,
                    message=f"Командная строка с опасным символом '|' или '&' (#std774): {stripped[:80]}",
                    code_snippet=stripped[:120],
                    recommendation=self.rules["SEC018"].recommendation,
                )
            )

        return violations

    def _check_com_no_macro_disable(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC019: COM Word/Excel без DisableAutoMacros (#std775).

        https://v8std.ru/std/775/
        """
        violations = []

        # Создание COM Word.Application или Excel.Application
        if re.search(r'Новый\s+COMОбъект\s*\(\s*"(Word\.Application|Excel\.Application)"', stripped, re.IGNORECASE):
            # Проверяем 5 строк после — есть ли DisableAutoMacros или AutomationSecurity
            end = min(len(lines), line_num + 5)
            context = "\n".join(lines[line_num - 1 : end])

            is_word = "word.application" in stripped.lower()
            is_excel = "excel.application" in stripped.lower()

            if is_word and "DisableAutoMacros" not in context:
                violations.append(
                    SecurityViolation(
                        rule_id="SEC019",
                        severity="HIGH",
                        line=line_num,
                        message=f"Word через COM без DisableAutoMacros (#std775): {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC019"].recommendation,
                    )
                )
            elif is_excel and "AutomationSecurity" not in context:
                violations.append(
                    SecurityViolation(
                        rule_id="SEC019",
                        severity="HIGH",
                        line=line_num,
                        message=f"Excel через COM без AutomationSecurity (#std775): {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC019"].recommendation,
                    )
                )

        return violations

    def _check_external_code_load(self, lines, line_num, stripped, file_path) -> list[SecurityViolation]:
        """SEC020: Внешняя обработка/расширение без БСП (#std669).

        https://v8std.ru/std/669/
        """
        violations = []

        # Поиск прямой загрузки внешней обработки из файла
        load_patterns = [
            r"ВнешниеОбработки\.Создать\s*\(",
            r"ВнешниеОтчеты\.Создать\s*\(",
            r'\.Подключить\s*\(\s*"[^"]*\.epf',
            r'\.Подключить\s*\(\s*"[^"]*\.erf',
            r"ПодключитьВнешнююОбработку\s*\(",
            r"ПодключитьВнешнийОтчет\s*\(",
        ]
        for pattern in load_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                # Если есть ДополнительныеОтчетыИОбработки — это БСП
                # Проверяем контекст 5 строк до
                start = max(0, line_num - 6)
                context = "\n".join(lines[start:line_num])
                if "ДополнительныеОтчетыИОбработки" in context:
                    continue  # через БСП — нормально

                violations.append(
                    SecurityViolation(
                        rule_id="SEC020",
                        severity="HIGH",
                        line=line_num,
                        message=f"Прямая загрузка внешнего кода без БСП (#std669): {stripped[:80]}",
                        code_snippet=stripped[:120],
                        recommendation=self.rules["SEC020"].recommendation,
                    )
                )
                break

        return violations


# ============================================================================
# CLI
# ============================================================================


# CLI вынесен в scripts/security_auditor.py (Этап 1.2, Группа 1e)
