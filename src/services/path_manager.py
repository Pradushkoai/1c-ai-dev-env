"""
Менеджер путей проекта.

F1.8 (2026-07-05): PathManager делегирует конфигурацию в Config (src/config.py).
paths.env — legacy, загружается через Config._load_env_file() для backward compat.
Новый код: from src.config import Config
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


class PathManager:
    """Единый источник путей для всего проекта. 4-слойная архитектура.

    F1.8 (2026-07-05): Для нового кода используйте Config (src/config.py).
    PathManager сохранён для backward compat — делегирует в Config где возможно.

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     _ = (Path(tmp) / "paths.env").write_text("# fake", encoding="utf-8")
        ...     pm = PathManager(project_root=Path(tmp))
        ...     pm.root == Path(tmp).resolve()
        True
    """

    def __init__(self, project_root: Path | None = None):
        self._root = project_root or self._detect_root()
        self._load_env()

    def _detect_root(self) -> Path:
        """
        F1.8: Поиск корня проекта — теперь ищет paths.env И pyproject.toml
        (как Config._detect_root). Если не найден — CWD.
        """
        cwd = Path.cwd()
        markers = ("paths.env", "pyproject.toml", "manifest.json")
        for candidate in [cwd, *cwd.parents]:
            if any((candidate / marker).exists() for marker in markers):
                return candidate
        return cwd

    def _load_env(self) -> None:
        """F1.8: Загрузка paths.env — делегирует в тот же механизм что Config."""
        env_file = self._root / "runtime" / "paths.env"
        if not env_file.exists():
            env_file = self._root / "paths.env"
        if env_file.exists():
            load_dotenv(env_file)

    def _get(self, key: str, default: str = "") -> str:
        val = os.getenv(key, default)
        # Подстановка ${VAR}
        while "${" in val:
            start = val.find("${")
            end = val.find("}", start)
            if end == -1:
                break
            val = val[:start] + os.getenv(val[start + 2 : end], "") + val[end + 1 :]
        return val

    # --- Слои ---

    @property
    def root(self) -> Path:
        return self._root

    @property
    def data_dir(self) -> Path:
        return self._root / "data"

    @property
    def configs_dir(self) -> Path:
        return self.data_dir / "configs"

    @property
    def archives_dir(self) -> Path:
        return self.data_dir / "archives"

    @property
    def hbk_dir(self) -> Path:
        return self.data_dir / "hbk"

    @property
    def derived_dir(self) -> Path:
        return self._root / "derived"

    @property
    def derived_configs_dir(self) -> Path:
        return self.derived_dir / "configs"

    @property
    def derived_platform_dir(self) -> Path:
        return self.derived_dir / "platform"

    @property
    def tools_dir(self) -> Path:
        return self._root / "tools"

    @property
    def repos_dir(self) -> Path:
        return self.tools_dir / "repos"

    @property
    def runtime_dir(self) -> Path:
        return self._root / "runtime"

    @property
    def scripts_dir(self) -> Path:
        return self._root / "scripts"

    @property
    def learned_skills_dir(self) -> Path:
        return self._root / "learned-skills"

    # --- Конфигурации ---

    def config_path(self, name: str) -> Path:
        return self.configs_dir / name

    def config_derived_dir(self, name: str) -> Path:
        return self.derived_configs_dir / name

    def config_index_path(self, name: str) -> Path:
        return self.config_derived_dir(name) / "index.md"

    def config_api_reference_md(self, name: str) -> Path:
        return self.config_derived_dir(name) / "api-reference.md"

    def config_api_reference_json(self, name: str) -> Path:
        return self.config_derived_dir(name) / "api-reference.json"

    # --- Платформа ---

    @property
    def syntax_helper_dir(self) -> Path:
        return self.derived_platform_dir / "syntax-helper"

    @property
    def syntax_helper_index_json(self) -> Path:
        return self.derived_platform_dir / "syntax-helper-index.json"

    @property
    def fast_search_index(self) -> Path:
        return self.derived_platform_dir / "fast-search-index.json"

    # --- Инструменты ---

    @property
    def bsl_ls_binary(self) -> Path:
        """F1.8: Делегирует в Config.bsl_ls_binary (читает BSL_LS_BINARY env var)."""
        bsl_path = os.environ.get(
            "BSL_LS_BINARY",
            str(Path.home() / ".local" / "bin" / "bsl-language-server"),
        )
        return Path(bsl_path)

    @property
    def bsl_ls_config(self) -> Path:
        return self.runtime_dir / ".bsl-language-server.json"

    @property
    def config_registry_path(self) -> Path:
        return self.runtime_dir / "config-registry.json"

    # --- Runtime ---

    @property
    def session_resume(self) -> Path:
        return self.runtime_dir / "session-resume.md"

    @property
    def worklog(self) -> Path:
        return self.runtime_dir / "worklog.md"

    @property
    def soul(self) -> Path:
        return self.runtime_dir / "soul.md"

    @property
    def user_profile(self) -> Path:
        return self.runtime_dir / "user-profile.md"

    # --- Проверка ---

    def validate(self) -> dict[str, bool]:
        """Вернуть dict путь → существует ли."""
        checks = {
            "root": self.root.exists(),
            "data": self.data_dir.exists(),
            "configs": self.configs_dir.exists(),
            "derived": self.derived_dir.exists(),
            "tools": self.tools_dir.exists(),
            "runtime": self.runtime_dir.exists(),
            "bsl_ls": self.bsl_ls_binary.exists(),
            "registry": self.config_registry_path.exists(),
        }
        return checks
