"""
SARIF reporter — конвертация CheckResult в SARIF 2.1.0.

SARIF (Static Analysis Results Interchange Format) — JSON-стандарт для
GitHub Code Scanning. При загрузке SARIF в GitHub Actions в PR появляются
аннотации прямо на строках кода.

Спецификация: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html

Пример использования:
    from src.services.sarif_reporter import SarifReporter
    from src.services.task_processor import TaskProcessor

    processor = TaskProcessor(paths)
    result = processor.check(file_path, level='full')
    sarif = SarifReporter().convert(result)
    SarifReporter().write(result, Path('results.sarif'))
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.task import CheckResult, Violation

# Маппинг severity → SARIF level
# SARIF уровни: error | warning | note | none
SEVERITY_TO_LEVEL: dict[str, str] = {
    "error": "error",
    "critical": "error",
    "high": "error",
    "warning": "warning",
    "medium": "warning",
    "low": "note",
    "info": "note",
    "information": "note",
    "hint": "note",
}

# Информация об источниках (анализаторах) — для метаданных правил
TOOL_INFO: dict[str, dict[str, str]] = {
    "bsl_ls": {
        "name": "BSL Language Server",
        "version": "1.0.1",
        "information_uri": "https://1c-syntax.github.io/bsl-language-server/",
        "rules_docs": "https://1c-syntax.github.io/bsl-language-server/diagnostics/",
    },
    "check_1c_standards": {
        "name": "1C Standards Checker",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
        "rules_docs": "https://its.1c.ru/db/v8std",
    },
    "security_auditor": {
        "name": "1C Security Auditor",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
    },
    "transaction_checker": {
        "name": "1C Transaction Checker",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
    },
    "query_analyzer": {
        "name": "1C Query Analyzer",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
    },
    "code_metrics": {
        "name": "1C Code Metrics",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
    },
    "check_metadata_standards": {
        "name": "1C Metadata Standards Checker",
        "version": "4.11.0",
        "information_uri": "https://github.com/Pradushkoai/1c-ai-dev-env",
    },
}


class SarifReporter:
    """Конвертер CheckResult → SARIF 2.1.0."""

    SARIF_VERSION = "2.1.0"
    SARIF_SCHEMA = (
        "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
        "main/Schemata/sarif-schema-2.1.0.json"
    )

    def convert(self, result: CheckResult) -> dict[str, Any]:
        """Конвертировать CheckResult в SARIF dict."""
        # Группируем violations по source (tool)
        by_tool: dict[str, list[Violation]] = {}
        for v in result.violations:
            by_tool.setdefault(v.source, []).append(v)

        # Уникальные правила по каждому tool
        tools: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []

        for source, violations in by_tool.items():
            tool_info = TOOL_INFO.get(source, {
                "name": source,
                "version": "unknown",
                "information_uri": "",
            })

            # Уникальные правила
            rules: list[dict[str, Any]] = []
            seen_rule_ids: set[str] = set()
            for v in violations:
                if v.rule_id in seen_rule_ids:
                    continue
                seen_rule_ids.add(v.rule_id)
                rules.append(self._make_rule(v))

            tool: dict[str, Any] = {
                "driver": {
                    "name": tool_info["name"],
                    "version": tool_info["version"],
                    "informationUri": tool_info["information_uri"],
                    "rules": rules,
                }
            }
            tools.append(tool)

            # Results для этого tool
            for v in violations:
                results.append(self._make_result(v, source))

        # Метрики как note-level results (если есть)
        if result.metrics:
            metric_results = self._metrics_to_results(result)
            results.extend(metric_results)
            # Если метрики добавлены — добавляем tool "code_metrics" если ещё нет
            if "code_metrics" not in by_tool:
                tools.append({
                    "driver": {
                        "name": TOOL_INFO["code_metrics"]["name"],
                        "version": TOOL_INFO["code_metrics"]["version"],
                        "informationUri": TOOL_INFO["code_metrics"]["information_uri"],
                        "rules": [],
                    }
                })

        return {
            "$schema": self.SARIF_SCHEMA,
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {"tools": tools} if len(tools) > 1 else {"tool": tools[0]} if tools else {},
                    "results": results,
                    "invocations": [
                        {
                            "executionSuccessful": result.verdict != "errors",
                            "workingDirectory": str(Path(result.file).parent) if result.file else "",
                        }
                    ],
                }
            ],
        }

    def convert_multiple(self, results: list[CheckResult]) -> dict[str, Any]:
        """Конвертировать несколько CheckResult (например, для всех файлов в PR).

        Все результаты объединяются в один SARIF run — GitHub это понимает.
        """
        # Объединяем violations из всех результатов
        all_violations: list[Violation] = []
        for r in results:
            all_violations.extend(r.violations)
            if r.metrics:
                all_violations.extend(self._metrics_to_violations(r))

        # Создаём виртуальный объединённый результат
        merged = CheckResult(file="(multiple)", level="full", violations=all_violations)
        return self.convert(merged)

    def write(
        self,
        result: CheckResult,
        output_path: Path,
        indent: int = 2,
    ) -> Path:
        """Записать SARIF в файл. Возвращает путь."""
        sarif = self.convert(result)
        output_path.write_text(
            json.dumps(sarif, ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        return output_path

    def write_multiple(
        self,
        results: list[CheckResult],
        output_path: Path,
        indent: int = 2,
    ) -> Path:
        """Записать SARIF для нескольких CheckResult."""
        sarif = self.convert_multiple(results)
        output_path.write_text(
            json.dumps(sarif, ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        return output_path

    # ─────────────────────────────────────────────
    # Внутренние методы
    # ─────────────────────────────────────────────

    @staticmethod
    def _make_rule(v: Violation) -> dict[str, Any]:
        """Создать описание правила (для metadata)."""
        return {
            "id": v.rule_id,
            "name": v.rule_id.upper().replace("-", "_"),
            "shortDescription": {
                "text": v.message[:200] if v.message else v.rule_id,
            },
            "fullDescription": {
                "text": f"Rule {v.rule_id} from {v.source}",
            },
            "defaultConfiguration": {
                "level": SEVERITY_TO_LEVEL.get(v.severity.lower(), "warning"),
            },
            "properties": {
                "source": v.source,
                "severity": v.severity,
            },
        }

    @staticmethod
    def _make_result(v: Violation, source: str) -> dict[str, Any]:
        """Создать один result (нарушение)."""
        level = SEVERITY_TO_LEVEL.get(v.severity.lower(), "warning")
        # SARIF требует startLine >= 1; line=0 означает "на файле, не на строке"
        start_line = max(1, v.line)
        return {
            "ruleId": v.rule_id,
            "level": level,
            "message": {
                "text": v.message,
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": v.file or "unknown",
                        },
                        "region": {
                            "startLine": start_line,
                        },
                    }
                }
            ],
            "properties": {
                "source": source,
                "severity": v.severity,
            },
        }

    @staticmethod
    def _metrics_to_violations(result: CheckResult) -> list[Violation]:
        """Сконвертировать метрики в note-level violations (для SARIF)."""
        if not result.metrics:
            return []
        m = result.metrics
        out: list[Violation] = []
        # God Object уже добавлен как violation в TaskProcessor
        # Добавляем общий note с метриками
        out.append(Violation(
            source="code_metrics",
            rule_id="METRICS_SUMMARY",
            severity="info",
            line=1,
            message=(
                f"LOC={m.loc}, LLOC={m.lloc}, "
                f"CC={m.cyclomatic_complexity:.1f}, "
                f"CogC={m.cognitive_complexity:.1f}, "
                f"Nesting={m.max_nesting}, "
                f"Methods={m.methods_count}, "
                f"Health={m.health_score:.1f}/100"
            ),
            file=result.file,
        ))
        return out

    def _metrics_to_results(self, result: CheckResult) -> list[dict[str, Any]]:
        """Сконвертировать метрики в SARIF results (note level)."""
        return [
            self._make_result(v, "code_metrics")
            for v in self._metrics_to_violations(result)
        ]
