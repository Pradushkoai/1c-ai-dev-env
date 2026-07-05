"""
Кастомные исключения проекта 1C AI Development Environment.

Иерархия (F1.4 — 2026-07-05: расширена с 4 до 8 базовых классов):
    ProjectError (базовое)
    ├── ConfigError (ошибки конфигураций)
    │   ├── ConfigAlreadyExistsError
    │   ├── ConfigNotFoundError
    │   └── ConfigNotActiveError
    ├── ArchiveError (ошибки архивации)
    │   ├── ArchiveNotFoundError
    │   └── ArchiveCorruptedError
    ├── BSLAnalysisError (ошибки анализа BSL)
    │   ├── BSLBinaryNotFoundError
    │   └── BSLAnalysisTimeoutError
    ├── IndexError (ошибки индексации)
    │   └── IndexBuildError
    ├── SecurityError (ошибки безопасности) — F1.4
    │   ├── PathTraversalError
    │   └── RateLimitExceededError
    ├── ExternalToolError (ошибки внешних инструментов) — F1.4
    │   └── V8UnpackError
    ├── ValidationError (ошибки валидации входных данных) — F1.4
    │   └── InvalidParameterError
    └── ParseError (ошибки парсинга) — F1.4
        ├── XMLParseError
        └── BSLParseError

Каждый класс имеет recovery_hint — рекомендуемое действие для восстановления.
"""

from __future__ import annotations

from src.since import since


@since("6.0.0")
class ProjectError(Exception):
    """Базовое исключение проекта.

    Attributes:
        recovery_hint: Рекомендуемое действие для восстановления (опционально).
    """

    def __init__(self, *args: object, recovery_hint: str = "") -> None:
        super().__init__(*args)
        self.recovery_hint = recovery_hint


# === Конфигурации ===


class ConfigError(ProjectError):
    """Базовая ошибка конфигурации."""


class ConfigAlreadyExistsError(ConfigError):
    """Конфигурация с таким именем уже существует."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Конфигурация '{name}' уже существует",
            recovery_hint=f"Удалите существующую конфигурацию '{name}' или используйте другое имя",
        )


class ConfigNotFoundError(ConfigError):
    """Конфигурация не найдена."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Конфигурация '{name}' не найдена",
            recovery_hint=f"Добавьте конфигурацию: 1c-ai config add --name {name} --zip <path>",
        )


class ConfigNotActiveError(ConfigError):
    """Конфигурация не активна."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Конфигурация '{name}' не активна",
            recovery_hint=f"Активируйте конфигурацию: 1c-ai config activate --name {name}",
        )


# === Архивация ===


class ArchiveError(ProjectError):
    """Базовая ошибка архивации."""


class ArchiveNotFoundError(ArchiveError):
    """Архив не найден."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Архив для '{name}' не найден",
            recovery_hint=f"Создайте архив: 1c-ai config archive --name {name}",
        )


class ArchiveCorruptedError(ArchiveError):
    """Архив повреждён."""

    def __init__(self, path: str, detail: str = "") -> None:
        self.path = path
        msg = f"Архив повреждён: {path} ({detail})" if detail else f"Архив повреждён: {path}"
        super().__init__(
            msg,
            recovery_hint=f"Пересоздайте архив из исходной конфигурации: {path}",
        )


# === BSL анализ ===


class BSLAnalysisError(ProjectError):
    """Базовая ошибка анализа BSL."""


class BSLBinaryNotFoundError(BSLAnalysisError):
    """BSL LS binary не найден."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"BSL Language Server не найден: {path}. Запустите: bash install.sh",
            recovery_hint="Установите BSL LS: bash install.sh",
        )


class BSLAnalysisTimeoutError(BSLAnalysisError):
    """Превышен таймаут анализа BSL."""

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        super().__init__(
            f"Превышен таймаут BSL LS: {timeout} сек",
            recovery_hint="Используйте --skip-bsl-validation или увеличьте таймаут",
        )


# === Индексация ===


class IndexBuildError(ProjectError):
    """Ошибка построения индекса."""

    def __init__(self, config_name: str, detail: str = "") -> None:
        self.config_name = config_name
        msg = f"Ошибка построения индекса для '{config_name}'" + (f": {detail}" if detail else "")
        super().__init__(
            msg,
            recovery_hint=f"Проверьте исходники: 1c-ai config build --name {config_name} --validate",
        )


# === Безопасность (F1.4 — 2026-07-05) ===


@since("6.0.0")
class SecurityError(ProjectError):
    """Базовая ошибка безопасности.

    Используется для ошибок, связанных с нарушением безопасности:
    path traversal, rate limit, injection attempts, и т.д.
    """


class PathTraversalError(SecurityError):
    """Попытка path traversal — доступ к файлу за пределами проекта.

    Срабатывает когда MCP handler получает file_path с '../'
    или абсолютный путь вне project root.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"Path traversal заблокирован: '{path}' — путь вне project root",
            recovery_hint="Используйте путь относительно корня проекта",
        )


class RateLimitExceededError(SecurityError):
    """Превышен rate limit для MCP tool."""

    def __init__(self, tool_name: str, max_calls: int, window: float) -> None:
        self.tool_name = tool_name
        self.max_calls = max_calls
        self.window = window
        super().__init__(
            f"Rate limit превышен для '{tool_name}': {max_calls} вызовов за {window} сек",
            recovery_hint=f"Подождите {window} сек или увеличьте лимит через MCP_RATE_LIMIT env var",
        )


# === Внешние инструменты (F1.4 — 2026-07-05) ===


@since("6.0.0")
class ExternalToolError(ProjectError):
    """Базовая ошибка внешнего инструмента.

    Используется для ошибок внешних инструментов: v8unpack, BSL LS, git, curl.
    """

    def __init__(self, *args: object, tool_name: str = "", recovery_hint: str = "") -> None:
        self.tool_name = tool_name
        super().__init__(*args, recovery_hint=recovery_hint)


class V8UnpackError(ExternalToolError):
    """Ошибка v8unpack при сборке/распаковке .epf/.cf."""

    def __init__(self, operation: str, detail: str = "") -> None:
        self.operation = operation
        msg = f"v8unpack ошибка при {operation}"
        if detail:
            msg += f": {detail}"
        super().__init__(
            msg,
            tool_name="v8unpack",
            recovery_hint="Проверьте, что v8unpack установлен: pip install v8unpack",
        )


# === Валидация (F1.4 — 2026-07-05) ===


@since("6.0.0")
class ValidationError(ProjectError):
    """Базовая ошибка валидации входных данных.

    Используется для ошибок валидации параметров MCP tools и CLI команд.
    """


class InvalidParameterError(ValidationError):
    """Неверный параметр — отсутствует, неверный тип, пустое значение."""

    def __init__(self, param_name: str, reason: str = "") -> None:
        self.param_name = param_name
        msg = f"Неверный параметр '{param_name}'"
        if reason:
            msg += f": {reason}"
        super().__init__(
            msg,
            recovery_hint=f"Проверьте документацию для параметра '{param_name}'",
        )


# === Парсинг (F1.4 — 2026-07-05) ===


@since("6.0.0")
class ParseError(ProjectError):
    """Базовая ошибка парсинга.

    Используется для ошибок парсинга XML, BSL, JSON DSL, метаданных.
    """


class XMLParseError(ParseError):
    """Ошибка парсинга XML файла 1С."""

    def __init__(self, file_path: str, detail: str = "") -> None:
        self.file_path = file_path
        msg = f"XML parse error в '{file_path}'"
        if detail:
            msg += f": {detail}"
        super().__init__(
            msg,
            recovery_hint=f"Проверьте, что файл '{file_path}' — валидный XML",
        )


class BSLParseError(ParseError):
    """Ошибка парсинга BSL файла."""

    def __init__(self, file_path: str, line: int = 0, detail: str = "") -> None:
        self.file_path = file_path
        self.line = line
        msg = f"BSL parse error в '{file_path}'"
        if line > 0:
            msg += f" (строка {line})"
        if detail:
            msg += f": {detail}"
        super().__init__(
            msg,
            recovery_hint=f"Проверьте синтаксис BSL в файле '{file_path}'",
        )
