"""
bsl_tree_sitter.py — Python-обёртка над tree-sitter-bsl для AST-парсинга BSL.

P1-A: заменяет regex-based bsl_ast.py на настоящий инкрементальный AST-парсер.

Преимущества:
- Точное извлечение процедур/функций (без ложных срабатываний в строках/комментариях)
- Точное определение флага Экспорт
- Точное извлечение вызовов методов внутри тела (включая вложенные)
- Поддержка сложных конструкций: аннотации &НаСервере, region-блоки, многострочные параметры

Использует:
- py-tree-sitter (Python bindings для tree-sitter)
- tree-sitter-bsl (alkoleft/tree-sitter-bsl, Apache 2.0)

Лицензия: MIT (использует open-source компоненты).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Lazy import — tree-sitter не является обязательной зависимостью для проекта,
# bsl_ast.py используется как fallback если tree-sitter не установлен.
_TS_AVAILABLE = False
_TS_LANGUAGE = None

try:
    import tree_sitter
    import tree_sitter_bsl

    _TS_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# DATA CLASSES (совместимы с bsl_ast.py)
# ============================================================================


@dataclass
class BslSymbol:
    """Процедура или функция BSL — символ AST."""

    name: str
    kind: str  # "procedure" | "function"
    start_line: int  # 1-based
    end_line: int  # 1-based
    is_export: bool
    calls: list[str] = field(default_factory=list)  # имена вызываемых методов


# ============================================================================
# BSL KEYWORDS (для фильтрации вызовов — не считаем ключевые слова методами)
# ============================================================================

# Эти ключевые слова могут выглядеть как вызовы методов, но ими не являются
BSL_KEYWORDS_LOWER: frozenset[str] = frozenset(
    {
        # Русские
        "если", "иначеесли", "иначе", "конецесли",
        "пока", "конецпока", "для", "каждого", "из", "по", "конеццикла", "конецдля",
        "попытка", "исключение", "вызватьисключение", "конецпопытки",
        "возврат", "прервать", "продолжить",
        "перейти",
        "новый",
        "истина", "ложь", "неопределено", "null",
        "и", "или", "не",
        "экспорт",
        "перем",
        "процедура", "конецпроцедуры",
        "функция", "конецфункции",
        "знач",
        "неопределено",
        # Английские эквиваленты
        "if", "elseif", "else", "endif",
        "while", "endwhile", "for", "each", "in", "to", "endfor",
        "try", "except", "raise", "endtry",
        "return", "break", "continue",
        "goto",
        "new",
        "true", "false", "undefined",
        "and", "or", "not",
        "export",
        "var",
        "procedure", "endprocedure",
        "function", "endfunction",
        "val",
    }
)


# ============================================================================
# PARSER
# ============================================================================


class BslTreeSitterParser:
    """Парсер BSL кода через tree-sitter-bsl.

    Требует установленных пакетов `tree-sitter` и `tree-sitter-bsl`.
    Если они не установлены — используйте bsl_ast.py (regex-based) как fallback.
    """

    def __init__(self) -> None:
        if not _TS_AVAILABLE:
            raise ImportError(
                "tree-sitter и tree-sitter-bsl не установлены. "
                "Установите: pip install tree-sitter tree-sitter-bsl"
            )
        self._language = tree_sitter.Language(tree_sitter_bsl.language())
        self._parser = tree_sitter.Parser(self._language)

    def parse(self, source: str) -> list[BslSymbol]:
        """Парсит BSL код и возвращает список процедур/функций.

        Args:
            source: Исходный BSL код

        Returns:
            Список BslSymbol с именами, границами, флагом Экспорт и вызовами.
        """
        if not source:
            return []

        source_bytes = source.encode("utf-8", errors="replace")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        symbols: list[BslSymbol] = []
        self._traverse_for_symbols(root, source_bytes, symbols)
        return symbols

    def parse_file(self, file_path) -> list[BslSymbol]:
        """Парсит BSL файл.

        Args:
            file_path: Путь к .bsl файлу

        Returns:
            Список BslSymbol.
        """
        from pathlib import Path

        path = Path(file_path)
        # Поддержка UTF-8 с BOM и без
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        return self.parse(content)

    # ========================================================================
    # ВНУТРЕННИЕ МЕТОДЫ
    # ========================================================================

    def _traverse_for_symbols(
        self,
        node,
        source: bytes,
        symbols: list[BslSymbol],
    ) -> None:
        """Обходит AST и собирает procedure_definition / function_definition."""
        kind = node.type

        if kind in ("procedure_definition", "function_definition"):
            symbol = self._parse_symbol_definition(node, source)
            if symbol:
                symbols.append(symbol)
            # Не спускаемся внутрь — вложенные определения не поддерживаются BSL
            return

        # Рекурсивно обходим дочерние узлы
        for child in node.children:
            self._traverse_for_symbols(child, source, symbols)

    def _parse_symbol_definition(self, node, source: bytes) -> BslSymbol | None:
        """Парсит определение процедуры/функции в BslSymbol."""
        # Имя — это identifier-ребёнок (не keyword)
        name = ""
        is_export = False
        kind = "procedure" if node.type == "procedure_definition" else "function"
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Проходим по прямым детям для имени и флага Экспорт
        for child in node.children:
            child_type = child.type
            if child_type == "identifier" and not name:
                name = child.text.decode("utf-8", errors="replace").strip()
            elif child_type == "EXPORT_KEYWORD":
                is_export = True
            elif child_type in ("PROCEDURE_KEYWORD", "FUNCTION_KEYWORD"):
                # Пропускаем ключевое слово Процедура/Функция
                continue
            elif child_type == "parameters":
                # Параметры — пропускаем
                continue

        if not name:
            return None

        # Извлекаем вызовы методов из тела функции/процедуры
        # Тело — это всё между parameters и END*_KEYWORD
        calls = self._extract_calls_from_node(node, source)

        return BslSymbol(
            name=name,
            kind=kind,
            start_line=start_line,
            end_line=end_line,
            is_export=is_export,
            calls=calls,
        )

    def _extract_calls_from_node(self, node, source: bytes) -> list[str]:
        """Извлекает все вызовы методов из поддерева.

        Возвращает список уникальных имён вызываемых методов.
        Исключает ключевые слова BSL (если, пока, и т.д.).

        Замечание: BSL не поддерживает вложенные определения процедур/функций,
        поэтому мы можем безопасно обходить всё поддерево procedure_definition.
        """
        seen: set[str] = set()
        result: list[str] = []

        # Пропускаем сигнатуру (имя, параметры, EXPORT_KEYWORD) — берём только тело.
        # Дети procedure_definition: PROCEDURE_KEYWORD, identifier, parameters, ...body..., ENDPROCEDURE_KEYWORD
        # Обходим всех детей кроме первых трёх и последнего.
        children = list(node.children)
        # Фильтруем ключевые слова и сигнатуру
        body_children = []
        skip_signature = True
        for child in children:
            t = child.type
            if skip_signature:
                # Пропускаем PROCEDURE_KEYWORD/FUNCTION_KEYWORD, identifier, parameters, EXPORT_KEYWORD
                if t in ("PROCEDURE_KEYWORD", "FUNCTION_KEYWORD", "identifier", "parameters", "EXPORT_KEYWORD"):
                    continue
                # Первый не-сигнатурный узел — начало тела
                skip_signature = False
            # Пропускаем ENDPROCEDURE_KEYWORD/ENDFUNCTION_KEYWORD в конце
            if t in ("ENDPROCEDURE_KEYWORD", "ENDFUNCTION_KEYWORD"):
                continue
            body_children.append(child)

        for child in body_children:
            self._collect_calls_recursive(child, source, seen, result)
        return result

    def _collect_calls_recursive(
        self,
        node,
        source: bytes,
        seen: set[str],
        result: list[str],
    ) -> None:
        """Рекурсивно собирает method_call → identifier.

        BSL не поддерживает вложенные определения процедур/функций, поэтому
        можем безопасно обходить всё поддерево без проверки на вложенные def.
        """
        kind = node.type

        # method_call содержит identifier с именем вызываемого метода
        if kind == "method_call":
            name_node = None
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break

            if name_node and name_node.text:
                name = name_node.text.decode("utf-8", errors="replace").strip()
                if name:
                    name_lower = name.lower()
                    # Исключаем ключевые слова BSL
                    if name_lower not in BSL_KEYWORDS_LOWER and name_lower not in seen:
                        seen.add(name_lower)
                        result.append(name)

        # Рекурсивно обходим детей
        for child in node.children:
            self._collect_calls_recursive(child, source, seen, result)


# ============================================================================
# ОДНОТОННЫЙ ПАРСЕР (для переиспользования)
# ============================================================================


_PARSER_SINGLETON: BslTreeSitterParser | None = None


def get_parser() -> BslTreeSitterParser:
    """Возвращает singleton-экземпляр парсера (создаёт при первом вызове)."""
    global _PARSER_SINGLETON
    if _PARSER_SINGLETON is None:
        _PARSER_SINGLETON = BslTreeSitterParser()
    return _PARSER_SINGLETON


def is_available() -> bool:
    """Проверяет, доступны ли tree-sitter и tree-sitter-bsl."""
    return _TS_AVAILABLE


# ============================================================================
# PUBLIC API — функции, совместимые с bsl_ast.py
# ============================================================================


def extract_symbols(source: str) -> list[BslSymbol]:
    """Извлекает все процедуры и функции из BSL кода.

    Совместимо с bsl_ast.extract_symbols по возвращаемому типу.

    Args:
        source: BSL код как строка

    Returns:
        Список BslSymbol.
    """
    if not _TS_AVAILABLE:
        raise ImportError(
            "tree-sitter не установлен. Используйте bsl_ast.py (regex-based) как fallback."
        )
    return get_parser().parse(source)


def extract_symbols_from_file(file_path) -> list[BslSymbol]:
    """Извлекает символы из BSL файла."""
    if not _TS_AVAILABLE:
        raise ImportError("tree-sitter не установлен.")
    return get_parser().parse_file(file_path)
