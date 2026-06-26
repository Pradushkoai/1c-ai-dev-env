"""
Тесты для PathManager.
Проверяем корректность определения путей в 4-слойной архитектуре.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from src.services.path_manager import PathManager


def test_path_manager_root_detection(tmp_path):
    """PathManager корректно принимает project_root."""
    pm = PathManager(project_root=tmp_path)
    assert pm.root == tmp_path


def test_path_manager_4_layers(tmp_path):
    """Все 4 слоя архитектуры возвращают правильные пути."""
    pm = PathManager(project_root=tmp_path)
    assert pm.data_dir == tmp_path / "data"
    assert pm.derived_dir == tmp_path / "derived"
    assert pm.tools_dir == tmp_path / "tools"
    assert pm.runtime_dir == tmp_path / "runtime"


def test_path_manager_config_paths(tmp_path):
    """Пути конфигураций строятся корректно."""
    pm = PathManager(project_root=tmp_path)
    assert pm.config_path("ut11") == tmp_path / "data" / "configs" / "ut11"
    assert pm.config_derived_dir("ut11") == tmp_path / "derived" / "configs" / "ut11"
    assert pm.config_index_path("ut11").name == "index.md"
    assert pm.config_api_reference_md("ut11").name == "api-reference.md"
    assert pm.config_api_reference_json("ut11").name == "api-reference.json"


def test_path_manager_platform_paths(tmp_path):
    """Пути платформенных индексов корректны."""
    pm = PathManager(project_root=tmp_path)
    assert pm.syntax_helper_dir == tmp_path / "derived" / "platform" / "syntax-helper"
    assert pm.syntax_helper_index_json.name == "syntax-helper-index.json"
    assert pm.fast_search_index.name == "fast-search-index.json"


def test_path_manager_validate(tmp_path):
    """validate() возвращает dict с правильными ключами."""
    # Создаём нужные директории
    for d in ["data/configs", "data/archives", "derived", "tools", "runtime"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "runtime" / "config-registry.json").touch()

    pm = PathManager(project_root=tmp_path)
    result = pm.validate()

    assert "root" in result
    assert "data" in result
    assert "configs" in result
    assert "derived" in result
    assert "tools" in result
    assert "runtime" in result
    assert "registry" in result
    assert result["root"] is True
    assert result["data"] is True
    assert result["configs"] is True


def test_path_manager_env_substitution(tmp_path, monkeypatch):
    """PathManager поддерживает подстановку ${VAR} из окружения."""
    # Создаём paths.env с подстановкой
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    env_file = runtime_dir / "paths.env"
    env_file.write_text('BSL_LS_BINARY=${HOME}/.local/bin/bsl-language-server\n', encoding='utf-8')

    monkeypatch.setenv("HOME", "/tmp/testhome")
    pm = PathManager(project_root=tmp_path)
    assert str(pm.bsl_ls_binary) == "/tmp/testhome/.local/bin/bsl-language-server"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
