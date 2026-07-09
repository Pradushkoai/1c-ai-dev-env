"""
F1.3 (2026-07-05): Тесты для единого Config dataclass.

Гарантирует:
1. Config создаётся с defaults
2. Config.from_env() читает env vars
3. Валидация работает (log_format, log_level, mcp_rate_limit, ollama_url)
4. Свойства путей корректны
5. to_dict() работает
6. Backward compat с PathManager
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import Config


class TestConfigDefaults:
    """F1.3: Config с default значениями."""

    def test_config_creates_with_defaults(self, tmp_path: Path) -> None:
        """Config создаётся с default значениями."""
        config = Config(project_root=tmp_path)
        assert config.project_root == tmp_path
        assert config.language == "ru"
        assert config.mcp_rate_limit == 100
        assert config.log_format == "console"
        assert config.log_level == "INFO"
        assert config.ollama_url == "http://localhost:11434"

    def test_config_log_level_uppercased(self, tmp_path: Path) -> None:
        """log_level автоматически переводится в uppercase."""
        config = Config(project_root=tmp_path, log_level="debug")
        assert config.log_level == "DEBUG"


class TestConfigValidation:
    """F1.3: Валидация конфигурации."""

    def test_invalid_log_format_raises(self, tmp_path: Path) -> None:
        """Неверный log_format вызывает ValueError."""
        with pytest.raises(ValueError, match="log_format"):
            Config(project_root=tmp_path, log_format="xml")

    def test_invalid_log_level_raises(self, tmp_path: Path) -> None:
        """Неверный log_level вызывает ValueError."""
        with pytest.raises(ValueError, match="log_level"):
            Config(project_root=tmp_path, log_level="TRACE")

    def test_negative_rate_limit_raises(self, tmp_path: Path) -> None:
        """Отрицательный mcp_rate_limit вызывает ValueError."""
        with pytest.raises(ValueError, match="mcp_rate_limit"):
            Config(project_root=tmp_path, mcp_rate_limit=-1)

    def test_invalid_ollama_url_raises(self, tmp_path: Path) -> None:
        """Неверный ollama_url вызывает ValueError."""
        with pytest.raises(ValueError, match="ollama_url"):
            Config(project_root=tmp_path, ollama_url="ftp://wrong")

    def test_zero_rate_limit_ok(self, tmp_path: Path) -> None:
        """mcp_rate_limit=0 (отключено) — допустимо."""
        config = Config(project_root=tmp_path, mcp_rate_limit=0)
        assert config.mcp_rate_limit == 0


class TestConfigFromEnv:
    """F1.3: Config.from_env() — создание из env vars."""

    def test_from_env_reads_onec_ai_dev_env_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_env читает ONEC_AI_DEV_ENV_ROOT."""
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(tmp_path))
        config = Config.from_env()
        assert config.project_root == tmp_path

    def test_from_env_reads_mcp_rate_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_env читает MCP_RATE_LIMIT."""
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(tmp_path))
        monkeypatch.setenv("MCP_RATE_LIMIT", "50")
        config = Config.from_env()
        assert config.mcp_rate_limit == 50

    def test_from_env_reads_log_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_env читает LOG_FORMAT."""
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(tmp_path))
        monkeypatch.setenv("LOG_FORMAT", "json")
        config = Config.from_env()
        assert config.log_format == "json"

    def test_from_env_reads_ollama_model(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_env читает OLLAMA_MODEL."""
        monkeypatch.setenv("ONEC_AI_DEV_ENV_ROOT", str(tmp_path))
        monkeypatch.setenv("OLLAMA_MODEL", "codellama:13b")
        config = Config.from_env()
        assert config.ollama_model == "codellama:13b"


class TestConfigPaths:
    """F1.3: Свойства путей."""

    def test_data_dir(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.data_dir == tmp_path / "data"

    def test_configs_dir(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.configs_dir == tmp_path / "data" / "configs"

    def test_derived_dir(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.derived_dir == tmp_path / "derived"

    def test_runtime_dir(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.runtime_dir == tmp_path / "runtime"

    def test_config_derived_dir(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.config_derived_dir("ut11") == tmp_path / "derived" / "configs" / "ut11"

    def test_config_path(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.config_path("ut11") == tmp_path / "data" / "configs" / "ut11"

    def test_config_registry_path(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.config_registry_path == tmp_path / "runtime" / "config-registry.json"

    def test_fast_search_index(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.fast_search_index == tmp_path / "derived" / "platform" / "fast-search-index.json"


class TestConfigUtility:
    """F1.3: Utility методы."""

    def test_to_dict(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path, log_format="json")
        d = config.to_dict()
        assert d["project_root"] == str(tmp_path)
        assert d["log_format"] == "json"
        assert "mcp_rate_limit" in d

    def test_validate(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        result = config.validate()
        assert "root" in result
        assert "data" in result
        assert result["root"] is True  # tmp_path exists

    def test_repr(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        r = repr(config)
        assert "Config" in r
        assert "project_root" in r


class TestConfigBackwardCompat:
    """F1.3: Backward compatibility с PathManager."""

    def test_config_has_same_paths_as_path_manager(self, tmp_path: Path) -> None:
        """Config и PathManager возвращают одинаковые пути."""
        from src.services.path_manager import PathManager

        # Создать paths.env чтобы PathManager обнаружил корень
        (tmp_path / "paths.env").write_text("# fake", encoding="utf-8")

        config = Config(project_root=tmp_path)
        pm = PathManager(project_root=tmp_path)

        assert config.data_dir == pm.data_dir
        assert config.configs_dir == pm.configs_dir
        assert config.derived_dir == pm.derived_dir
        assert config.runtime_dir == pm.runtime_dir
        assert config.tools_dir == pm.tools_dir
        assert config.config_registry_path == pm.config_registry_path
        assert config.fast_search_index == pm.fast_search_index
