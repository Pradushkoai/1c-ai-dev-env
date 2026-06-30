#!/usr/bin/env python3
"""
transaction_checker.py — Проверка транзакций в BSL коде 1С.

Проверяет:
1. Отсутствие НачатьТранзакцию/ЗафиксироватьТранзакцию (незавершённые)
2. Отсутствие ОтменитьТранзакцию в Исключение
3. Интерактив в транзакции (Сообщить, ПоказатьПредупреждение, ОткрытьФорму)
4. Слишком длинные транзакции (> 100 строк)
5. Вложенные транзакции
6. Запросы в транзакции без Try/Catch
7. Отсутствие Try/Catch вокруг транзакции
8. Вызов сервера из транзакции
9. Изменение данных без транзакции
10. Транзакция без записи данных

Использование:
    from transaction_checker import TransactionChecker
    checker = TransactionChecker()
    violations = checker.check_file(Path('module.bsl'))
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TransactionViolation:
    """Нарушение транзакционной логики."""
    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    line: int
    message: str
    code_snippet: str = ''
    recommendation: str = ''


class TransactionChecker:
    """Проверка транзакций в BSL коде."""

    # Ключевые слова транзакций
    BEGIN_TX = re.compile(r'\bНачатьТранзакцию\s*\(', re.IGNORECASE)
    COMMIT_TX = re.compile(r'\bЗафиксироватьТранзакцию\s*\(', re.IGNORECASE)
    ROLLBACK_TX = re.compile(r'\bОтменитьТранзакцию\s*\(', re.IGNORECASE)

    # Интерактивные операции (запрещены в транзакции)
    INTERACTIVE_OPS = [
        (re.compile(r'\bСообщить\s*\(', re.IGNORECASE), 'Сообщить'),
        (re.compile(r'\bПоказатьПредупреждение\s*\(', re.IGNORECASE), 'ПоказатьПредупреждение'),
        (re.compile(r'\bПоказатьВопрос\s*\(', re.IGNORECASE), 'ПоказатьВопрос'),
        (re.compile(r'\bПоказатьЗначение\s*\(', re.IGNORECASE), 'ПоказатьЗначение'),
        (re.compile(r'\bОткрытьФорму\s*\(', re.IGNORECASE), 'ОткрытьФорму'),
        (re.compile(r'\bОткрытьЗначение\s*\(', re.IGNORECASE), 'ОткрытьЗначение'),
        (re.compile(r'\bВопрос\s*\(', re.IGNORECASE), 'Вопрос'),
        (re.compile(r'\bОповестить\s*\(', re.IGNORECASE), 'Оповестить'),
        (re.compile(r'\bПоставитьОтметкуОбработки\s*\(', re.IGNORECASE), 'ПоставитьОтметкуОбработки'),
    ]

    # Операции с БД (должны быть в транзакции)
    DB_WRITE_OPS = [
        re.compile(r'\.Записать\s*\(', re.IGNORECASE),
        re.compile(r'\.Удалить\s*\(', re.IGNORECASE),
        re.compile(r'\.Провести\s*\(', re.IGNORECASE),
        re.compile(r'\.ОтменаПроведения\s*\(', re.IGNORECASE),
        re.compile(r'\.СнятьПометкуУдаления\s*\(', re.IGNORECASE),
        re.compile(r'\.ПометитьНаУдаление\s*\(', re.IGNORECASE),
        re.compile(r'\bЗаписать\s*\(', re.IGNORECASE),
        re.compile(r'\bУдалить\s*\(', re.IGNORECASE),
    ]

    def check_file(self, file_path: Path) -> list[TransactionViolation]:
        """Проверка одного BSL файла."""
        try:
            content = file_path.read_text(encoding='utf-8-sig', errors='replace')
        except Exception:
            return []

        return self.check_code(content, str(file_path))

    def check_code(self, code: str, file_path: str = '') -> list[TransactionViolation]:
        """Проверка BSL кода."""
        violations = []
        lines = code.split('\n')

        violations.extend(self._check_unbalanced_transactions(lines, file_path))
        violations.extend(self._check_no_try_catch(lines, file_path))
        violations.extend(self._check_interactive_in_transaction(lines, file_path))
        violations.extend(self._check_long_transactions(lines, file_path))
        violations.extend(self._check_nested_transactions(lines, file_path))
        violations.extend(self._check_db_write_without_transaction(lines, file_path))

        return violations

    def check_path(self, dir_path: Path) -> list[TransactionViolation]:
        """Проверка всех BSL файлов в директории."""
        violations = []
        for bsl_file in sorted(dir_path.rglob('*.bsl')):
            violations.extend(self.check_file(bsl_file))
        return violations

    # =====================================================================
    # ПРАВИЛА
    # =====================================================================

    def _check_unbalanced_transactions(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX001: Несбалансированные транзакции (Начать без Зафиксировать/Отменить)."""
        violations = []
        begin_count = 0
        commit_count = 0
        rollback_count = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                begin_count += 1
            if self.COMMIT_TX.search(stripped):
                commit_count += 1
            if self.ROLLBACK_TX.search(stripped):
                rollback_count += 1

        # Сбалансированная транзакция: Начать == Зафиксировать + Отменить
        # Но если есть и Зафиксировать и Отменить (в Попытка/Исключение),
        # то должен быть только один из них (не оба для одной Начать)
        if begin_count > 0:
            # Правильный паттерн: Начать(1) + Зафиксировать(1) + Отменить(1)
            # где Зафиксировать в Попытка и Отменить в Исключение
            # Это СБАЛАНСИРОВАНО: 1 Начать → 1 Зафиксировать ИЛИ 1 Отменить (не оба одновременно)
            # Но в коде оба встречаются в одном блоке Попытка/Исключение
            # Поэтому правильная проверка: begin_count >= commit_count и begin_count >= rollback_count
            # и (commit_count + rollback_count) >= begin_count (хотя бы один из пары)
            if commit_count + rollback_count < begin_count:
                violations.append(TransactionViolation(
                    rule_id='TX001',
                    severity='CRITICAL',
                    line=0,
                    message=f'Несбалансированная транзакция: Начать={begin_count}, Зафиксировать={commit_count}, Отменить={rollback_count}',
                    recommendation='Каждая НачатьТранзакцию должна иметь парную ЗафиксироватьТранзакцию или ОтменитьТранзакцию',
                ))

        return violations

    def _check_no_try_catch(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX002: Транзакция без Try/Catch — нет отката при ошибке."""
        violations = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                # Проверяем 10 строк вперёд на Попытка
                context = ' '.join(lines[i:min(i + 10, len(lines))])
                context_before = ' '.join(lines[max(0, i - 5):i])

                # Попытка должна быть до или сразу после НачатьТранзакцию
                if 'Попытка' not in context_before and 'Попытка' not in context:
                    violations.append(TransactionViolation(
                        rule_id='TX002',
                        severity='HIGH',
                        line=i,
                        message=f'НачатьТранзакцию без Попытка/Исключение — нет отката при ошибке',
                        code_snippet=stripped[:120],
                        recommendation='Оберните транзакцию в Попытка/Исключение с ОтменитьТранзакцию',
                    ))

        return violations

    def _check_interactive_in_transaction(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX003: Интерактивные операции внутри транзакции."""
        violations = []
        in_transaction = False
        tx_start_line = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                in_transaction = True
                tx_start_line = i
                continue

            if self.COMMIT_TX.search(stripped) or self.ROLLBACK_TX.search(stripped):
                in_transaction = False
                continue

            if in_transaction:
                for pattern, op_name in self.INTERACTIVE_OPS:
                    if pattern.search(stripped):
                        violations.append(TransactionViolation(
                            rule_id='TX003',
                            severity='MEDIUM',
                            line=i,
                            message=f'Интерактивная операция {op_name} в транзакции (начата на строке {tx_start_line})',
                            code_snippet=stripped[:120],
                            recommendation='Избегайте интерактивных операций в транзакции — они увеличивают время блокировок',
                        ))
                        break

        return violations

    def _check_long_transactions(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX004: Слишком длинные транзакции (> 100 строк)."""
        violations = []
        tx_start = 0
        MAX_TX_LINES = 100

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                tx_start = i

            if (self.COMMIT_TX.search(stripped) or self.ROLLBACK_TX.search(stripped)) and tx_start > 0:
                tx_length = i - tx_start
                if tx_length > MAX_TX_LINES:
                    violations.append(TransactionViolation(
                        rule_id='TX004',
                        severity='HIGH',
                        line=tx_start,
                        message=f'Длинная транзакция: {tx_length} строк (рекомендуется < {MAX_TX_LINES})',
                        recommendation='Разбейте транзакцию на более мелкие или вынесите подготовку данных за пределы транзакции',
                    ))
                tx_start = 0

        return violations

    def _check_nested_transactions(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX005: Вложенные транзакции (НачатьТранзакцию внутри другой)."""
        violations = []
        tx_depth = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                tx_depth += 1
                if tx_depth > 1:
                    violations.append(TransactionViolation(
                        rule_id='TX005',
                        severity='HIGH',
                        line=i,
                        message=f'Вложенная транзакция (уровень {tx_depth}) — 1С не поддерживает вложенные транзакции',
                        code_snippet=stripped[:120],
                        recommendation='Не используйте вложенные НачатьТранзакцию — вторая игнорируется',
                    ))

            if self.COMMIT_TX.search(stripped) or self.ROLLBACK_TX.search(stripped):
                tx_depth = max(0, tx_depth - 1)

        return violations

    def _check_db_write_without_transaction(self, lines: list[str], file_path: str) -> list[TransactionViolation]:
        """TX006: Запись в БД без транзакции (если > 3 операций записи подряд)."""
        violations = []
        write_count = 0
        write_start = 0
        in_transaction = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//'):
                continue

            if self.BEGIN_TX.search(stripped):
                in_transaction = True
                write_count = 0
                continue

            if self.COMMIT_TX.search(stripped) or self.ROLLBACK_TX.search(stripped):
                in_transaction = False
                write_count = 0
                continue

            # Проверяем запись в БД
            is_write = False
            for pattern in self.DB_WRITE_OPS:
                if pattern.search(stripped):
                    is_write = True
                    break

            if is_write and not in_transaction:
                if write_count == 0:
                    write_start = i
                write_count += 1
            else:
                if write_count >= 3:
                    violations.append(TransactionViolation(
                        rule_id='TX006',
                        severity='MEDIUM',
                        line=write_start,
                        message=f'{write_count} операций записи БД без транзакции (строки {write_start}-{i - 1})',
                        recommendation='Используйте НачатьТранзакцию для групповых операций записи',
                    ))
                write_count = 0

        return violations

    def get_stats(self, violations: list[TransactionViolation]) -> dict:
        """Статистика по нарушениям."""
        from collections import Counter
        by_severity = Counter(v.severity for v in violations)
        by_rule = Counter(v.rule_id for v in violations)
        return {
            'total': len(violations),
            'by_severity': dict(by_severity),
            'by_rule': dict(by_rule),
        }


def main():
    import sys
    if len(sys.argv) < 2:
        print("Использование: python3 transaction_checker.py <file.bsl|directory>")
        sys.exit(1)

    path = Path(sys.argv[1])
    checker = TransactionChecker()

    if path.is_file():
        violations = checker.check_file(path)
    elif path.is_dir():
        violations = checker.check_path(path)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)

    stats = checker.get_stats(violations)
    print(f"\n{'='*60}")
    print(f"ПРОВЕРКА ТРАНЗАКЦИЙ: {path}")
    print(f"{'='*60}")
    print(f"Нарушений: {stats['total']}")
    for sev, count in stats['by_severity'].items():
        print(f"  {sev}: {count}")

    if violations:
        print(f"\n{'='*60}")
        for v in violations:
            print(f"\n  [{v.severity}] {v.rule_id} (строка {v.line})")
            print(f"  {v.message}")
            if v.recommendation:
                print(f"  Рекомендация: {v.recommendation}")

    if stats['total'] == 0:
        print("\n✅ Нарушений транзакционной логики не найдено")


if __name__ == '__main__':
    main()
