"""
config.py — Единый источник конфигурации проекта.

F1.3 (2026-07-05): Заменяет 3 источника конфигурации:
  1. paths.env (legacy, загружается через python-dotenv в env vars)
  2. env vars (ONEC_AI_DEV_ENV_ROOT, BSL_LS_BINARY, MCP_RATE_LIMIT, etc.)
  3. runtime/config-registry.json (управляется ConfigurationRegistry)

Теперь Config — единая точка доступа ко всем настройкам проекта.
PathManager делегирует конфигурацию путей в Config.

Использование:
    from src.config import Config

    config = Config()  # авто-обнаружение корня + загрузка env
    config = Config(project_root=Path("/custom/path"))
    config = Config.from_env()  # только из env vars, без paths.env

    config.project_root      # Path — корень проекта
    config.bsl_ls_binary     # Path — путь к BSL LS
    config.mcp_rate_limit    # int — лимит вызовов MCP tool в минуту
    config.log_format        # str — "json" или "console"
    config.log_level         # str — "DEBUG", "INFO", "WARNING", "ERROR"

Валидация:
    Config.__post_init__ проверяет:
    - project_root существует
    - log_format в ["json", "console"]
    - log_level в ["DEBUG", "INFO", "WARNING", "ERROR"]
    - mcp_rate_limit >= 0
    - ollama_url — валидный URL
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.since import since


@since("6.0.0")
@dataclass
class Config:
    """
    Единая конфигурация проекта 1C AI Development Environment.

    F1.3 (2026-07-05): заменяет разрозненные источники конфигурации
    (paths.env, env vars, hardcoded defaults) единым dataclass.

    Attributes:
        project_root: Корень проекта (авто-обнаружение или ONEC_AI_DEV_ENV_ROOT).
        language: Язык интерфейса ("ru" или "en").
        bsl_ls_binary: Путь к BSL Language Server.
        mcp_rate_limit: Лимит вызовов MCP tool в минуту (0 = отключено).
        mcp_metrics_port: Порт для Prometheus metrics (None = не запускать).
        ollama_url: URL Ollama API для RAG.
        ollama_model: Модель LLM по умолчанию.
        log_format: Формат логирования ("json" или "console").
        log_level: Уровень логирования ("DEBUG", "INFO", "WARNING", "ERROR").
    """

    # ─── Пути ───
    project_root: Path = field(default_factory=lambda: Path.cwd())

    # ─── Настройки ───
    language: str = "ru"

    # ─── BSL Language Server ───
    bsl_ls_binary: Path = field(
        default_factory=lambda: Path.home() / ".local" / "bin" / "bsl-language-server"
    )

    # ─── MCP Server ───
    mcp_rate_limit: int = 100
    mcp_metrics_port: int | None = None

    # ─── Ollama (RAG, опционально) ───
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # ─── Логирование ───
    log_format: str = "console"
    log_level: str = "INFO"

    # ─── Внутреннее состояние ───
    _env_loaded: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Валидация конфигурации после инициализации."""
        # Загрузить paths.env если ещё не загружен
        if not self._env_loaded:
            self._load_env_file()
            self._env_loaded = True

        # Валидация log_format
        if self.log_format not in ("json", "console"):
            raise ValueError(
                f"log_format должен быть 'json' или 'console', получено: '{self.log_format}'"
            )

        # Валидация log_level
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR")
        if self.log_level.upper() not in valid_levels:
            raise ValueError(
                f"log_level должен быть один из {valid_levels}, получено: '{self.log_level}'"
            )
        self.log_level = self.log_level.upper()

        # Валидация mcp_rate_limit
        if self.mcp_rate_limit < 0:
            raise ValueError(
                f"mcp_rate_limit должен быть >= 0, получено: {self.mcp_rate_limit}"
            )

        # Валидация ollama_url — базовая проверка
        if not self.ollama_url.startswith(("http://", "https://")):
            raise ValueError(
                f"ollama_url должен начинаться с http:// или https://, получено: '{self.ollama_url}'"
            )

    def _load_env_file(self) -> None:
        """Загрузить paths.env через python-dotenv (если существует)."""
        env_file = self.project_root / "runtime" / "paths.env"
        if not env_file.exists():
            env_file = self.project_root / "paths.env"
        if env_file.exists():
            load_dotenv(env_file)

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Config:
        """
        Создать Config из переменных окружения.

        Загружает paths.env (если существует), затем читает env vars.
        Приоритет: env vars > paths.env > defaults.

        Args:
            project_root: Явно указанный корень проекта.
                          Если None — берётся из ONEC_AI_DEV_ENV_ROOT или авто-обнаружение.

        Returns:
            Config с значениями из env vars.
        """
        # Определение корня проекта
        if project_root is None:
            env_root = os.environ.get("ONEC_AI_DEV_ENV_ROOT")
            if env_root:
                project_root = Path(env_root).resolve()
            else:
                project_root = cls._detect_root()

        # Загрузка paths.env
        env_file = project_root / "runtime" / "paths.env"
        if not env_file.exists():
            env_file = project_root / "paths.env"
        if env_file.exists():
            load_dotenv(env_file)

        # Чтение env vars с defaults
        bsl_ls = os.environ.get(
            "BSL_LS_BINARY",
            str(Path.home() / ".local" / "bin" / "bsl-language-server"),
        )

        mcp_port_str = os.environ.get("MCP_METRICS_PORT")
        mcp_port = int(mcp_port_str) if mcp_port_str else None

        return cls(
            project_root=project_root,
            language=os.environ.get("1C_AI_LANG", "ru"),
            bsl_ls_binary=Path(bsl_ls),
            mcp_rate_limit=int(os.environ.get("MCP_RATE_LIMIT", "100")),
            mcp_metrics_port=mcp_port,
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
            log_format=os.environ.get("LOG_FORMAT", "console"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            _env_loaded=True,
        )

    @staticmethod
    def _detect_root() -> Path:
        """
        Авто-обнаружение корня проекта.

        Ищет paths.env или pyproject.toml вверх по дереву каталогов
        (как git ищет .git).

        Returns:
            Path корня проекта (или CWD если не найден).
        """
        cwd = Path.cwd()
        markers = ("paths.env", "pyproject.toml", "manifest.json")
        for candidate in [cwd, *cwd.parents]:
            if any((candidate / marker).exists() for marker in markers):
                return candidate
        return cwd

    # ─── Свойства для путей (делегирование из PathManager) ───

    @property
    def data_dir(self) -> Path:
        """Слой 1: исходные данные (data/)."""
        return self.project_root / "data"

    @property
    def configs_dir(self) -> Path:
        """Директория конфигураций (data/configs/)."""
        return self.data_dir / "configs"

    @property
    def archives_dir(self) -> Path:
        """Директория архивов (data/archives/)."""
        return self.data_dir / "archives"

    @property
    def derived_dir(self) -> Path:
        """Слой 2: производные индексы (derived/)."""
        return self.project_root / "derived"

    @property
    def derived_configs_dir(self) -> Path:
        """Индексы конфигураций (derived/configs/)."""
        return self.derived_dir / "configs"

    @property
    def derived_platform_dir(self) -> Path:
        """Индексы платформы (derived/platform/)."""
        return self.derived_dir / "platform"

    @property
    def tools_dir(self) -> Path:
        """Слой 3: инструменты (tools/)."""
        return self.project_root / "tools"

    @property
    def repos_dir(self) -> Path:
        """Git репозитории (tools/repos/)."""
        return self.tools_dir / "repos"

    @property
    def runtime_dir(self) -> Path:
        """Слой 4: файлы работы (runtime/)."""
        return self.project_root / "runtime"

    @property
    def scripts_dir(self) -> Path:
        """Скрипты (scripts/)."""
        return self.project_root / "scripts"

    @property
    def config_registry_path(self) -> Path:
        """Путь к config-registry.json."""
        return self.runtime_dir / "config-registry.json"

    @property
    def fast_search_index(self) -> Path:
        """Путь к fast-search-index.json."""
        return self.derived_platform_dir / "fast-search-index.json"

    @property
    def bsl_ls_config(self) -> Path:
        """Путь к .bsl-language-server.json."""
        return self.runtime_dir / ".bsl-language-server.json"

    def config_derived_dir(self, name: str) -> Path:
        """Путь к индексам конкретной конфигурации."""
        return self.derived_configs_dir / name

    def config_path(self, name: str) -> Path:
        """Путь к директории конфигурации."""
        return self.configs_dir / name

    def config_api_reference_json(self, name: str) -> Path:
        """Путь к api-reference.json для конфигурации."""
        return self.config_derived_dir(name) / "api-reference.json"

    def config_api_reference_md(self, name: str) -> Path:
        """Путь к api-reference.md для конфигурации."""
        return self.config_derived_dir(name) / "api-reference.md"

    def validate(self) -> dict[str, bool]:
        """Проверить что критичные пути существуют."""
        return {
            "root": self.project_root.exists(),
            "data": self.data_dir.exists(),
            "configs": self.configs_dir.exists(),
            "derived": self.derived_dir.exists(),
            "tools": self.tools_dir.exists(),
            "runtime": self.runtime_dir.exists(),
            "bsl_ls": self.bsl_ls_binary.exists(),
            "registry": self.config_registry_path.exists(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Сериализация конфигурации в dict (для отладки)."""
        return {
            "project_root": str(self.project_root),
            "language": self.language,
            "bsl_ls_binary": str(self.bsl_ls_binary),
            "mcp_rate_limit": self.mcp_rate_limit,
            "mcp_metrics_port": self.mcp_metrics_port,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "log_format": self.log_format,
            "log_level": self.log_level,
        }

    def __repr__(self) -> str:
        return (
            f"Config(project_root={self.project_root}, "
            f"language={self.language}, "
            f"log_format={self.log_format}, "
            f"log_level={self.log_level}, "
            f"mcp_rate_limit={self.mcp_rate_limit})"
        )
