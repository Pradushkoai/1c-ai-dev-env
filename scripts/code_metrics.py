#!/usr/bin/env python3
"""
code_metrics.py — Метрики кода BSL 1С.

Вычисляет:
1. LOC (Lines of Code) — физические и логические строки
2. Cyclomatic Complexity — цикломатическая сложность
3. Cognitive Complexity — когнитивная сложность
4. Maximum Nesting Depth — максимальная вложенность
5. Number of Parameters — количество параметров процедур/функций
6. Дублирование кода — поиск одинаковых блоков
7. God Object — модули > 1000 строк или > 50 методов
8. Long Method — процедуры/функции > 50 строк
9. Too Many Parameters — > 5 параметров
10. Технический долг — оценка

Использование:
    from code_metrics import CodeMetricsAnalyzer
    analyzer = CodeMetricsAnalyzer()
    metrics = analyzer.analyze_file(Path('module.bsl'))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================


@dataclass
class MethodMetrics:
    """Метрики метода (процедуры/функции)."""

    name: str
    method_type: str  # Процедура или Функция
    line_start: int
    line_end: int
    loc: int  # физические строки
    lloc: int  # логические строки (без пустых и комментариев)
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    max_nesting_depth: int = 0
    param_count: int = 0
    is_export: bool = False
    has_region: bool = False


@dataclass
class CodeMetrics:
    """Метрики всего модуля."""

    file_path: str = ""
    # LOC
    total_lines: int = 0
    code_lines: int = 0  # lloc
    comment_lines: int = 0
    blank_lines: int = 0
    # Методы
    methods: list[MethodMetrics] = field(default_factory=list)
    procedures_count: int = 0
    functions_count: int = 0
    export_count: int = 0
    # Сложность
    total_cyclomatic: int = 0
    avg_cyclomatic: float = 0.0
    max_cyclomatic: int = 0
    total_cognitive: int = 0
    max_cognitive: int = 0
    # Вложенность
    max_nesting: int = 0
    # Проблемы
    long_methods: list[MethodMetrics] = field(default_factory=list)
    too_many_params: list[MethodMetrics] = field(default_factory=list)
    is_god_object: bool = False
    # Дублирование
    duplicate_blocks: int = 0
    duplicate_lines: int = 0
    # Техдолг
    technical_debt_minutes: int = 0
    # Вердикт
    health_score: float = 0.0  # 0-100, где 100 — идеальный код
    issues: list[dict] = field(default_factory=list)


# ============================================================================
# АНАЛИЗАТОР МЕТРИК
# ============================================================================


class CodeMetricsAnalyzer:
    """Анализатор метрик BSL кода."""

    # Ключевые слова для цикломатической сложности
    COMPLEXITY_KEYWORDS = [
        r"\bЕсли\b",
        r"\bИначе\b",
        r"\bИначеЕсли\b",
        r"\bПока\b",
        r"\bДля\b",
        r"\bДля\s+Каждого\b",
        r"\bПопытка\b",
        r"\bИсключение\b",
        r"\bИ\b",
        r"\bИЛИ\b",
        r"\bНЕ\b",
    ]

    # Ключевые слова для вложенности
    NESTING_OPEN = [
        r"\bЕсли\b.*\bТогда\b",
        r"\bПока\b.*\bЦикл\b",
        r"\bДля\b.*\bЦикл\b",
        r"\bПопытка\b",
        r"\bФункция\b",
        r"\bПроцедура\b",
    ]
    NESTING_CLOSE = [
        r"\bКонецЕсли\b",
        r"\bКонецЦикла\b",
        r"\bКонецПопытки\b",
        r"\bКонецФункции\b",
        r"\bКонецПроцедуры\b",
    ]

    def analyze_file(self, file_path: Path) -> CodeMetrics:
        """Анализ одного BSL файла."""
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return CodeMetrics(file_path=str(file_path))

        return self.analyze_code(content, str(file_path))

    def analyze_code(self, code: str, file_path: str = "") -> CodeMetrics:
        """Анализ BSL кода."""
        lines = code.split("\n")
        metrics = CodeMetrics(file_path=file_path)

        # 1. LOC метрики
        self._count_loc(lines, metrics)

        # 2. Методы (процедуры/функции)
        self._parse_methods(lines, metrics)

        # 3. Сложность и вложенность
        self._calculate_complexity(lines, metrics)

        # 4. Проблемы
        self._find_issues(metrics)

        # 5. Дублирование
        self._find_duplicates(lines, metrics)

        # 6. Техдолг
        self._estimate_debt(metrics)

        # 7. Health score
        self._calculate_health(metrics)

        return metrics

    def analyze_path(self, dir_path: Path) -> list[CodeMetrics]:
        """Анализ всех BSL файлов в директории."""
        results = []
        for bsl_file in sorted(dir_path.rglob("*.bsl")):
            results.append(self.analyze_file(bsl_file))
        return results

    def get_summary(self, metrics_list: list[CodeMetrics]) -> dict:
        """Сводка по нескольким файлам."""
        total_files = len(metrics_list)
        total_lines = sum(m.code_lines for m in metrics_list)
        total_methods = sum(len(m.methods) for m in metrics_list)
        god_objects = sum(1 for m in metrics_list if m.is_god_object)
        long_methods = sum(len(m.long_methods) for m in metrics_list)
        total_debt = sum(m.technical_debt_minutes for m in metrics_list)

        return {
            "total_files": total_files,
            "total_code_lines": total_lines,
            "total_methods": total_methods,
            "god_objects": god_objects,
            "long_methods": long_methods,
            "avg_complexity": sum(m.avg_cyclomatic for m in metrics_list) / total_files if total_files else 0,
            "avg_health": sum(m.health_score for m in metrics_list) / total_files if total_files else 0,
            "total_debt_hours": total_debt / 60,
            "total_debt_minutes": total_debt,
        }

    # =====================================================================
    # LOC
    # =====================================================================

    def _count_loc(self, lines: list[str], metrics: CodeMetrics):
        """Подсчёт строк кода."""
        metrics.total_lines = len(lines)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                metrics.blank_lines += 1
            elif stripped.startswith("//"):
                metrics.comment_lines += 1
            else:
                metrics.code_lines += 1

    # =====================================================================
    # МЕТОДЫ
    # =====================================================================

    def _parse_methods(self, lines: list[str], metrics: CodeMetrics):
        """Парсинг процедур и функций."""
        method_pattern = re.compile(r"^(Процедура|Функция)\s+(\w+)\s*\(([^)]*)\)(\s+Экспорт)?", re.IGNORECASE)
        end_pattern = re.compile(r"^(КонецПроцедуры|КонецФункции)", re.IGNORECASE)

        current_method = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Начало метода
            m = method_pattern.match(stripped)
            if m:
                method_type = m.group(1)
                name = m.group(2)
                params = m.group(3).strip()
                is_export = m.group(4) is not None

                param_count = len([p for p in params.split(",") if p.strip()]) if params else 0

                current_method = MethodMetrics(
                    name=name,
                    method_type=method_type,
                    line_start=i,
                    line_end=0,
                    loc=0,
                    lloc=0,
                    param_count=param_count,
                    is_export=is_export,
                )

            # Конец метода
            if current_method and end_pattern.match(stripped):
                current_method.line_end = i
                current_method.loc = i - current_method.line_start + 1

                # LLOC — логические строки
                method_lines = lines[current_method.line_start - 1 : i]
                current_method.lloc = sum(1 for l in method_lines if l.strip() and not l.strip().startswith("//"))

                metrics.methods.append(current_method)
                if current_method.method_type.lower() == "процедура":
                    metrics.procedures_count += 1
                else:
                    metrics.functions_count += 1
                if current_method.is_export:
                    metrics.export_count += 1

                current_method = None

    # =====================================================================
    # СЛОЖНОСТЬ
    # =====================================================================

    def _calculate_complexity(self, lines: list[str], metrics: CodeMetrics):
        """Расчёт цикломатической и когнитивной сложности."""
        # Глобальная сложность
        total_cc = 1  # базовая сложность
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            for pattern in self.COMPLEXITY_KEYWORDS:
                total_cc += len(re.findall(pattern, stripped, re.IGNORECASE))

        metrics.total_cyclomatic = total_cc

        # Сложность по методам
        for method in metrics.methods:
            cc = 1
            cognitive = 0
            nesting = 0
            max_nesting = 0

            method_lines = lines[method.line_start - 1 : method.line_end]

            for line in method_lines:
                stripped = line.strip()
                if stripped.startswith("//"):
                    continue

                # Цикломатическая
                for pattern in self.COMPLEXITY_KEYWORDS:
                    cc += len(re.findall(pattern, stripped, re.IGNORECASE))

                # Вложенность
                for pattern in self.NESTING_OPEN:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        nesting += 1
                        max_nesting = max(max_nesting, nesting)

                for pattern in self.NESTING_CLOSE:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        nesting = max(0, nesting - 1)

                # Когнитивная: +1 за каждый управляющий оператор, +nesting за вложенность
                for pattern in self.COMPLEXITY_KEYWORDS:
                    matches = re.findall(pattern, stripped, re.IGNORECASE)
                    if matches:
                        cognitive += len(matches) * (1 + nesting)

            method.cyclomatic_complexity = cc
            method.cognitive_complexity = cognitive
            method.max_nesting_depth = max_nesting

            metrics.total_cyclomatic += cc - 1  # не считаем базовую сложность дважды
            metrics.total_cognitive += cognitive
            metrics.max_cyclomatic = max(metrics.max_cyclomatic, cc)
            metrics.max_cognitive = max(metrics.max_cognitive, cognitive)
            metrics.max_nesting = max(metrics.max_nesting, max_nesting)

        # Средняя сложность
        if metrics.methods:
            metrics.avg_cyclomatic = metrics.total_cyclomatic / len(metrics.methods)

    # =====================================================================
    # ПРОБЛЕМЫ
    # =====================================================================

    def _find_issues(self, metrics: CodeMetrics):
        """Поиск проблем в коде."""
        # Long Method — > 50 строк
        for method in metrics.methods:
            if method.lloc > 50:
                metrics.long_methods.append(method)
                metrics.issues.append(
                    {
                        "type": "long_method",
                        "severity": "warning",
                        "method": method.name,
                        "line": method.line_start,
                        "message": f"Метод {method.name} слишком длинный: {method.lloc} строк (рекомендуется < 50)",
                    }
                )

        # Too Many Parameters — > 5
        for method in metrics.methods:
            if method.param_count > 5:
                metrics.too_many_params.append(method)
                metrics.issues.append(
                    {
                        "type": "too_many_params",
                        "severity": "warning",
                        "method": method.name,
                        "line": method.line_start,
                        "message": f"Метод {method.name} имеет {method.param_count} параметров (рекомендуется < 5)",
                    }
                )

        # God Object — > 1000 строк кода или > 50 методов
        if metrics.code_lines > 1000 or len(metrics.methods) > 50:
            metrics.is_god_object = True
            metrics.issues.append(
                {
                    "type": "god_object",
                    "severity": "error",
                    "line": 0,
                    "message": f"God Object: {metrics.code_lines} строк, {len(metrics.methods)} методов (рекомендуется < 1000 строк, < 50 методов)",
                }
            )

        # Высокая сложность
        if metrics.max_cyclomatic > 15:
            metrics.issues.append(
                {
                    "type": "high_complexity",
                    "severity": "warning",
                    "line": 0,
                    "message": f"Высокая цикломатическая сложность: max={metrics.max_cyclomatic} (рекомендуется < 15)",
                }
            )

        # Глубокая вложенность
        if metrics.max_nesting > 4:
            metrics.issues.append(
                {
                    "type": "deep_nesting",
                    "severity": "warning",
                    "line": 0,
                    "message": f"Глубокая вложенность: max={metrics.max_nesting} (рекомендуется < 4)",
                }
            )

    # =====================================================================
    # ДУБЛИРОВАНИЕ
    # =====================================================================

    def _find_duplicates(self, lines: list[str], metrics: CodeMetrics):
        """Поиск дублирующихся блоков кода (минимум 6 строк)."""
        min_block_size = 6
        seen_blocks: dict[str, int] = {}
        duplicates = 0
        dup_lines = 0

        for i in range(len(lines) - min_block_size):
            block = tuple(
                l.strip() for l in lines[i : i + min_block_size] if l.strip() and not l.strip().startswith("//")
            )
            if len(block) < min_block_size:
                continue

            block_key = "\n".join(block)
            if block_key in seen_blocks:
                duplicates += 1
                dup_lines += min_block_size
            else:
                seen_blocks[block_key] = i

        metrics.duplicate_blocks = duplicates
        metrics.duplicate_lines = dup_lines

        if duplicates > 0:
            metrics.issues.append(
                {
                    "type": "code_duplication",
                    "severity": "warning",
                    "line": 0,
                    "message": f"Найдено {duplicates} дублирующихся блоков ({dup_lines} строк)",
                }
            )

    # =====================================================================
    # ТЕХДОЛГ
    # =====================================================================

    def _estimate_debt(self, metrics: CodeMetrics):
        """Оценка технического долга в минутах."""
        debt = 0

        # Long Method — 10 мин за каждый
        debt += len(metrics.long_methods) * 10

        # Too Many Params — 5 мин за каждый
        debt += len(metrics.too_many_params) * 5

        # God Object — 60 мин
        if metrics.is_god_object:
            debt += 60

        # Высокая сложность — 15 мин
        if metrics.max_cyclomatic > 15:
            debt += 15

        # Дублирование — 5 мин за каждый блок
        debt += metrics.duplicate_blocks * 5

        # Глубокая вложенность — 10 мин
        if metrics.max_nesting > 4:
            debt += 10

        metrics.technical_debt_minutes = debt

    # =====================================================================
    # HEALTH SCORE
    # =====================================================================

    def _calculate_health(self, metrics: CodeMetrics):
        """Расчёт health score (0-100)."""
        score = 100

        # Штрафы
        score -= min(30, len(metrics.long_methods) * 5)  # Long Method
        score -= min(20, len(metrics.too_many_params) * 3)  # Too Many Params
        score -= 30 if metrics.is_god_object else 0  # God Object
        score -= min(10, max(0, metrics.max_cyclomatic - 10))  # Сложность
        score -= min(15, metrics.duplicate_blocks * 3)  # Дублирование
        score -= min(10, max(0, metrics.max_nesting - 3) * 3)  # Вложенность

        metrics.health_score = max(0, score)


# ============================================================================
# CLI
# ============================================================================


def main():
    import sys

    if len(sys.argv) < 2:
        print("Использование: python3 code_metrics.py <file.bsl|directory>")
        sys.exit(1)

    path = Path(sys.argv[1])
    analyzer = CodeMetricsAnalyzer()

    if path.is_file():
        metrics = analyzer.analyze_file(path)
        _print_metrics(metrics)
    elif path.is_dir():
        results = analyzer.analyze_path(path)
        summary = analyzer.get_summary(results)
        _print_summary(summary, results)
    else:
        print(f"❌ Путь не найден: {path}")
        sys.exit(1)


def _print_metrics(m: CodeMetrics):
    print(f"\n{'=' * 60}")
    print(f"МЕТРИКИ КОДА: {m.file_path}")
    print(f"{'=' * 60}")
    print(f"\nLOC: {m.total_lines} всего, {m.code_lines} кода, {m.comment_lines} комментариев, {m.blank_lines} пустых")
    print(f"Методы: {m.procedures_count} процедур, {m.functions_count} функций, {m.export_count} экспортных")
    print(
        f"Сложность: cyclomatic={m.total_cyclomatic} (avg={m.avg_cyclomatic:.1f}, max={m.max_cyclomatic}), cognitive={m.total_cognitive} (max={m.max_cognitive})"
    )
    print(f"Вложенность: max={m.max_nesting}")
    print(f"Дублирование: {m.duplicate_blocks} блоков ({m.duplicate_lines} строк)")
    print(f"Техдолг: {m.technical_debt_minutes} мин ({m.technical_debt_minutes / 60:.1f} ч)")
    print(f"Health Score: {m.health_score:.0f}/100")

    if m.long_methods:
        print(f"\n⚠️ Длинные методы ({len(m.long_methods)}):")
        for method in m.long_methods[:5]:
            print(f"  {method.name}: {method.lloc} строк (строка {method.line_start})")

    if m.too_many_params:
        print(f"\n⚠️ Слишком много параметров ({len(m.too_many_params)}):")
        for method in m.too_many_params[:5]:
            print(f"  {method.name}: {method.param_count} параметров")

    if m.is_god_object:
        print(f"\n❌ GOD OBJECT: {m.code_lines} строк, {len(m.methods)} методов")

    if m.issues:
        print(f"\nПроблемы ({len(m.issues)}):")
        for issue in m.issues:
            print(f"  [{issue['severity']}] {issue['message']}")


def _print_summary(summary: dict, results: list[CodeMetrics]):
    print(f"\n{'=' * 60}")
    print(f"СВОДКА ПО {summary['total_files']} ФАЙЛАМ")
    print(f"{'=' * 60}")
    print(f"Всего строк кода: {summary['total_code_lines']}")
    print(f"Всего методов: {summary['total_methods']}")
    print(f"God Objects: {summary['god_objects']}")
    print(f"Длинных методов: {summary['long_methods']}")
    print(f"Средняя сложность: {summary['avg_complexity']:.1f}")
    print(f"Средний Health: {summary['avg_health']:.0f}/100")
    print(f"Техдолг: {summary['total_debt_hours']:.1f} ч ({summary['total_debt_minutes']} мин)")


if __name__ == "__main__":
    main()
