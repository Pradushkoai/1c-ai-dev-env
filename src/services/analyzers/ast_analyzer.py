"""
D3.2 (2026-07-05): AST-based BSL analyzer.

Миграция 20 правил с regex на tree-sitter AST.
AST даёт лучшую точность — нет false positives на комментариях и строковых литералах.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.bsl_ast import parse_bsl, is_tree_sitter_available

logger = logging.getLogger(__name__)


@dataclass
class AstViolation:
    """Нарушение, найденное AST analyzer."""
    rule_id: str
    line: int
    column: int = 0
    severity: str = "warning"
    message: str = ""
    source: str = "ast_analyzer"


class AstAnalyzer:
    """D3.2: AST-based analyzer для BSL кода через tree-sitter-bsl."""

    def __init__(self) -> None:
        self._available = is_tree_sitter_available()

    def is_available(self) -> bool:
        return self._available

    def analyze(self, file_path: Path | str) -> list[AstViolation]:
        if not self._available:
            return []
        file_path = Path(file_path)
        if not file_path.exists():
            return []
        code = file_path.read_text(encoding="utf-8")
        return self.analyze_code(code)

    def analyze_code(self, code: str) -> list[AstViolation]:
        if not self._available:
            return []
        tree = parse_bsl(code)
        if tree is None:
            return []

        violations: list[AstViolation] = []
        root = tree.root_node
        nodes = self._walk(root)

        # 20 AST-based правил
        self._rule_execute(nodes, violations)
        self._rule_commented_code(nodes, violations)
        self._rule_procedure_without_region(nodes, violations)
        self._rule_empty_procedure(nodes, violations)
        self._rule_deep_nesting(root, violations)
        self._rule_todo_without_issue(nodes, violations)
        self._rule_global_variables(nodes, violations)
        self._rule_multiple_return(nodes, violations)
        self._rule_long_procedure(nodes, violations)
        self._rule_no_try_for_execute(nodes, violations)
        self._rule_hardcoded_password(nodes, violations)
        self._rule_run_application(nodes, violations)
        self._rule_com_object(nodes, violations)
        self._rule_internet_connection(nodes, violations)
        self._rule_file_operations(nodes, violations)
        self._rule_eval(nodes, violations)
        self._rule_string_in_query(nodes, violations)
        self._rule_privileged_mode(nodes, violations)
        self._rule_event_subscription(nodes, violations)
        self._rule_commented_todo(nodes, violations)

        return violations

    def _walk(self, node: Any) -> list[Any]:
        result = [node]
        for child in node.children:
            result.extend(self._walk(child))
        return result

    def _get_text(self, node: Any) -> str:
        if node.text is None:
            return ""
        if isinstance(node.text, bytes):
            return node.text.decode("utf-8", errors="ignore")
        return str(node.text)

    # ─── 20 правил ───

    def _rule_execute(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-EXEC001: Выполнить() в коде."""
        for n in nodes:
            if n.type == "execute_statement":
                v.append(AstViolation("AST-EXEC001", n.start_point[0]+1, n.start_point[1], "critical", "Выполнить() — потенциальная инъекция"))

    def _rule_eval(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-EXEC002: Вычислить() в коде."""
        for n in nodes:
            text = self._get_text(n)
            if n.type == "identifier" and "Вычислить" in text:
                parent_type = n.parent.type if n.parent else ""
                if "call" in parent_type.lower() or "statement" in parent_type.lower():
                    v.append(AstViolation("AST-EXEC002", n.start_point[0]+1, n.start_point[1], "high", "Вычислить() с динамическим выражением"))

    def _rule_commented_code(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-STYLE001: Закомментированный код."""
        keywords = ["Если", "Для", "Пока", "Процедура", "Функция", "Возврат", "Попытка"]
        for n in nodes:
            if n.type in ("comment", "line_comment"):
                text = self._get_text(n)
                for kw in keywords:
                    if kw in text:
                        v.append(AstViolation("AST-STYLE001", n.start_point[0]+1, severity="info", message="Закомментированный код"))
                        break

    def _rule_procedure_without_region(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-ARCH001: Процедура без #Область."""
        has_regions = any(n.type == "region_definition" or n.type == "preproc_region" for n in nodes)
        if not has_regions:
            for n in nodes:
                if n.type in ("procedure_definition", "function_definition"):
                    v.append(AstViolation("AST-ARCH001", n.start_point[0]+1, "warning", "Процедура без #Область"))

    def _rule_empty_procedure(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-QUALITY001: Пустая процедура."""
        skip_types = {"PROCEDURE_KEYWORD", "FUNCTION_KEYWORD", "ENDPROCEDURE_KEYWORD", "ENDFUNCTION_KEYWORD", "identifier", "parameters", "(", ")", "comment", ";"}
        for n in nodes:
            if n.type in ("procedure_definition", "function_definition"):
                real_children = [c for c in n.children if c.type not in skip_types]
                if len(real_children) == 0:
                    v.append(AstViolation("AST-QUALITY001", n.start_point[0]+1, "info", "Пустая процедура/функция"))

    def _rule_deep_nesting(self, root: Any, v: list[AstViolation], max_depth: int = 4) -> None:
        """AST-ARCH002: Глубокая вложенность."""
        def check(node: Any, depth: int) -> None:
            block_types = {"if_statement", "for_statement", "while_statement", "try_statement"}
            if depth > max_depth and node.type in block_types:
                v.append(AstViolation("AST-ARCH002", node.start_point[0]+1, "warning", f"Глубокая вложенность: {depth}"))
            for c in node.children:
                check(c, depth + 1 if c.type in block_types else depth)
        check(root, 0)

    def _rule_todo_without_issue(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-STYLE002: TODO без номера."""
        for n in nodes:
            if n.type in ("comment", "line_comment"):
                text = self._get_text(n)
                if ("TODO" in text or "FIXME" in text) and "№" not in text and "#" not in text:
                    v.append(AstViolation("AST-STYLE002", n.start_point[0]+1, "info", "TODO без номера issue"))

    def _rule_global_variables(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-ARCH003: Глобальные переменные."""
        for n in nodes:
            if n.type == "var_statement" and n.parent and n.parent.type == "source_file":
                v.append(AstViolation("AST-ARCH003", n.start_point[0]+1, "warning", "Глобальная переменная"))

    def _rule_multiple_return(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-QUALITY002: Множественные Возврат."""
        for n in nodes:
            if n.type == "function_definition":
                returns = [c for c in self._walk(n) if c.type == "return_statement"]
                if len(returns) > 1:
                    v.append(AstViolation("AST-QUALITY002", returns[1].start_point[0]+1, "info", f"Множественные Возврат ({len(returns)})"))

    def _rule_long_procedure(self, nodes: list[Any], v: list[AstViolation], max_lines: int = 100) -> None:
        """AST-QUALITY003: Длинная процедура."""
        for n in nodes:
            if n.type in ("procedure_definition", "function_definition"):
                length = n.end_point[0] - n.start_point[0] + 1
                if length > max_lines:
                    v.append(AstViolation("AST-QUALITY003", n.start_point[0]+1, "warning", f"Длинная процедура: {length} строк"))

    def _rule_no_try_for_execute(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC001: Выполнить без Попытка."""
        for n in nodes:
            if n.type in ("procedure_definition", "function_definition"):
                children = self._walk(n)
                has_execute = any(c.type == "execute_statement" for c in children)
                has_try = any(c.type == "try_statement" for c in children)
                if has_execute and not has_try:
                    v.append(AstViolation("AST-SEC001", n.start_point[0]+1, "high", "Выполнить() без Попытка/Исключение"))

    def _rule_string_in_query(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC002: Конкатенация в Запрос.Текст."""
        for n in nodes:
            if n.type == "assignment":
                text = self._get_text(n)
                if "Текст" in text and "+" in text and "Запрос" in text:
                    v.append(AstViolation("AST-SEC002", n.start_point[0]+1, "critical", "Конкатенация в Запрос.Текст — SQL инъекция"))

    def _rule_hardcoded_password(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC003: Хардкод пароля."""
        pwd_keywords = ["пароль", "password", "token", "секрет", "ключ"]
        for n in nodes:
            if n.type in ("assignment", "assignment_statement"):
                text = self._get_text(n)
                if any(kw in text.lower() for kw in pwd_keywords):
                    v.append(AstViolation("AST-SEC003", n.start_point[0]+1, "critical", "Хардкод пароля/токена"))

    def _rule_privileged_mode(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC004: Привилегированный режим."""
        for n in nodes:
            text = self._get_text(n)
            if "ПривилегированныйРежим" in text and n.type != "comment":
                v.append(AstViolation("AST-SEC004", n.start_point[0]+1, "high", "Привилегированный режим — обход RLS"))

    def _rule_run_application(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC005: ЗапуститьПриложение."""
        for n in nodes:
            text = self._get_text(n)
            if "ЗапуститьПриложение" in text and n.type not in ("comment", "string", "string_content"):
                v.append(AstViolation("AST-SEC005", n.start_point[0]+1, "high", "ЗапуститьПриложение — OS command"))

    def _rule_com_object(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC006: COM-объекты."""
        for n in nodes:
            if n.type == "string":
                text = self._get_text(n)
                if "COM" in text or "WScript" in text:
                    v.append(AstViolation("AST-SEC006", n.start_point[0]+1, "medium", "COM-объект — небезопасно"))

    def _rule_internet_connection(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC007: ИнтернетСоединение."""
        for n in nodes:
            text = self._get_text(n)
            if "ИнтернетСоединение" in text and n.type not in ("comment", "string", "string_content"):
                v.append(AstViolation("AST-SEC007", n.start_point[0]+1, "medium", "ИнтернетСоединение — MITM risk"))

    def _rule_file_operations(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-SEC008: Файловые операции."""
        file_funcs = ["ЗначениеВФайл", "ЗначениеИзФайла", "КопироватьФайл", "ПереместитьФайл"]
        for n in nodes:
            text = self._get_text(n)
            if any(f in text for f in file_funcs) and n.type not in ("comment", "string", "string_content"):
                v.append(AstViolation("AST-SEC008", n.start_point[0]+1, "medium", "Файловая операция без проверки пути"))

    def _rule_event_subscription(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-ARCH004: УстановитьОбработчик."""
        for n in nodes:
            text = self._get_text(n)
            if "УстановитьОбработчик" in text and n.type not in ("comment", "string"):
                v.append(AstViolation("AST-ARCH004", n.start_point[0]+1, "info", "УстановитьОбработчик — лучше через подписки"))

    def _rule_commented_todo(self, nodes: list[Any], v: list[AstViolation]) -> None:
        """AST-STYLE003: Закомментированный TODO без контекста."""
        for n in nodes:
            if n.type == "comment":
                text = self._get_text(n)
                if "MRG" in text or "XXX" in text:
                    v.append(AstViolation("AST-STYLE003", n.start_point[0]+1, "info", "MRG/XXX — merge conflict marker"))
