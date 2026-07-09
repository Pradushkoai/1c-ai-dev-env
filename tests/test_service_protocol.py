"""
F1.2 + F1.8 (2026-07-05): Тесты для ServiceProtocol и PathManager cleanup.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.service_protocol import ServiceProtocol


class TestServiceProtocol:
    """F1.2: ServiceProtocol — строгий интерфейс для сервисов."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """ServiceProtocol — runtime_checkable (можно isinstance)."""

        class FakeService:
            @property
            def name(self) -> str:
                return "fake"

            def initialize(self) -> None:
                pass

            def is_available(self) -> bool:
                return True

        svc = FakeService()
        assert isinstance(svc, ServiceProtocol)

    def test_protocol_requires_name(self) -> None:
        """ServiceProtocol требует свойство name."""

        class NoName:
            def initialize(self) -> None:
                pass

            def is_available(self) -> bool:
                return True

        assert not isinstance(NoName(), ServiceProtocol)

    def test_protocol_requires_initialize(self) -> None:
        """ServiceProtocol требует метод initialize()."""

        class NoInit:
            @property
            def name(self) -> str:
                return "test"

            def is_available(self) -> bool:
                return True

        assert not isinstance(NoInit(), ServiceProtocol)

    def test_protocol_requires_is_available(self) -> None:
        """ServiceProtocol требует метод is_available()."""

        class NoAvailable:
            @property
            def name(self) -> str:
                return "test"

            def initialize(self) -> None:
                pass

        assert not isinstance(NoAvailable(), ServiceProtocol)


class TestPathManagerDeprecated:
    """F1.8: PathManager помечен как deprecated в пользу Config."""

    def test_path_manager_has_deprecation_note(self) -> None:
        """PathManager docstring содержит F1.8 deprecation note."""
        from src.services.path_manager import PathManager

        assert "F1.8" in PathManager.__doc__ or "Config" in PathManager.__doc__

    def test_paths_env_has_deprecation_note(self) -> None:
        """paths.env содержит DEPRECATED note."""
        paths_env = Path(__file__).parent.parent / "paths.env"
        content = paths_env.read_text(encoding="utf-8")
        assert "DEPRECATED" in content or "deprecated" in content
        assert "config.py" in content

    def test_config_has_same_paths_as_path_manager(self, tmp_path: Path) -> None:
        """Config и PathManager возвращают одинаковые пути."""
        from src.services.path_manager import PathManager

        (tmp_path / "paths.env").write_text("# fake", encoding="utf-8")

        config = Config(project_root=tmp_path)
        pm = PathManager(project_root=tmp_path)

        assert config.data_dir == pm.data_dir
        assert config.configs_dir == pm.configs_dir
        assert config.derived_dir == pm.derived_dir
        assert config.runtime_dir == pm.runtime_dir
