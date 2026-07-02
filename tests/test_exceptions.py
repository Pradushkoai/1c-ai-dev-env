"""
Тесты для src/exceptions.py — кастомные исключения проекта.

Покрытие:
- Иерархия наследования (ProjectError → ConfigError → ConfigAlreadyExistsError, и т.д.)
- Сообщения об ошибках
- Атрибуты (.name, .path, .timeout, .config_name)
- Передача detail опционально
"""

from __future__ import annotations

import pytest

from src.exceptions import (
    ArchiveCorruptedError,
    ArchiveError,
    ArchiveNotFoundError,
    BSLAnalysisError,
    BSLAnalysisTimeoutError,
    BSLBinaryNotFoundError,
    ConfigAlreadyExistsError,
    ConfigError,
    ConfigNotFoundError,
    ConfigNotActiveError,
    IndexBuildError,
    ProjectError,
)


# ─── Иерархия наследования ───


class TestExceptionHierarchy:
    """Все кастомные исключения наследуются от ProjectError."""

    def test_config_errors_are_project_errors(self):
        assert issubclass(ConfigError, ProjectError)
        assert issubclass(ConfigAlreadyExistsError, ProjectError)
        assert issubclass(ConfigNotFoundError, ProjectError)
        assert issubclass(ConfigNotActiveError, ProjectError)

    def test_config_already_exists_is_config_error(self):
        assert issubclass(ConfigAlreadyExistsError, ConfigError)

    def test_config_not_found_is_config_error(self):
        assert issubclass(ConfigNotFoundError, ConfigError)

    def test_config_not_active_is_config_error(self):
        assert issubclass(ConfigNotActiveError, ConfigError)

    def test_archive_errors_are_project_errors(self):
        assert issubclass(ArchiveError, ProjectError)
        assert issubclass(ArchiveNotFoundError, ProjectError)
        assert issubclass(ArchiveCorruptedError, ProjectError)

    def test_archive_not_found_is_archive_error(self):
        assert issubclass(ArchiveNotFoundError, ArchiveError)

    def test_archive_corrupted_is_archive_error(self):
        assert issubclass(ArchiveCorruptedError, ArchiveError)

    def test_bsl_errors_are_project_errors(self):
        assert issubclass(BSLAnalysisError, ProjectError)
        assert issubclass(BSLBinaryNotFoundError, ProjectError)
        assert issubclass(BSLAnalysisTimeoutError, ProjectError)

    def test_bsl_binary_not_found_is_bsl_analysis_error(self):
        assert issubclass(BSLBinaryNotFoundError, BSLAnalysisError)

    def test_bsl_timeout_is_bsl_analysis_error(self):
        assert issubclass(BSLAnalysisTimeoutError, BSLAnalysisError)

    def test_index_build_error_is_project_error(self):
        assert issubclass(IndexBuildError, ProjectError)

    def test_project_error_is_exception(self):
        assert issubclass(ProjectError, Exception)


# ─── ConfigAlreadyExistsError ───


class TestConfigAlreadyExistsError:
    def test_message_contains_name(self):
        err = ConfigAlreadyExistsError("ut11")
        assert "ut11" in str(err)
        assert "уже существует" in str(err)

    def test_name_attribute(self):
        err = ConfigAlreadyExistsError("ut11")
        assert err.name == "ut11"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigAlreadyExistsError) as exc_info:
            raise ConfigAlreadyExistsError("edo2")
        assert exc_info.value.name == "edo2"

    def test_caught_as_project_error(self):
        with pytest.raises(ProjectError):
            raise ConfigAlreadyExistsError("unp")


# ─── ConfigNotFoundError ───


class TestConfigNotFoundError:
    def test_message_contains_name(self):
        err = ConfigNotFoundError("ut11")
        assert "ut11" in str(err)
        assert "не найдена" in str(err)

    def test_name_attribute(self):
        err = ConfigNotFoundError("ut11")
        assert err.name == "ut11"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigNotFoundError) as exc_info:
            raise ConfigNotFoundError("edo2")
        assert exc_info.value.name == "edo2"

    def test_caught_as_config_error(self):
        with pytest.raises(ConfigError):
            raise ConfigNotFoundError("test")


# ─── ConfigNotActiveError ───


class TestConfigNotActiveError:
    def test_message_contains_name(self):
        err = ConfigNotActiveError("ut11")
        assert "ut11" in str(err)
        assert "не активна" in str(err)

    def test_name_attribute(self):
        err = ConfigNotActiveError("ut11")
        assert err.name == "ut11"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigNotActiveError) as exc_info:
            raise ConfigNotActiveError("edo2")
        assert exc_info.value.name == "edo2"


# ─── ArchiveNotFoundError ───


class TestArchiveNotFoundError:
    def test_message_contains_name(self):
        err = ArchiveNotFoundError("ut11")
        assert "ut11" in str(err)
        assert "не найден" in str(err)

    def test_name_attribute(self):
        err = ArchiveNotFoundError("ut11")
        assert err.name == "ut11"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ArchiveNotFoundError):
            raise ArchiveNotFoundError("test")

    def test_caught_as_archive_error(self):
        with pytest.raises(ArchiveError):
            raise ArchiveNotFoundError("test")


# ─── ArchiveCorruptedError ───


class TestArchiveCorruptedError:
    def test_message_contains_path_without_detail(self):
        err = ArchiveCorruptedError("/tmp/test.zip")
        assert "/tmp/test.zip" in str(err)
        assert "повреждён" in str(err)
        # Без detail — нет скобок
        assert "(" not in str(err)

    def test_message_contains_path_with_detail(self):
        err = ArchiveCorruptedError("/tmp/test.zip", "EOFError")
        assert "/tmp/test.zip" in str(err)
        assert "EOFError" in str(err)
        assert "(" in str(err)

    def test_path_attribute(self):
        err = ArchiveCorruptedError("/tmp/test.zip", "CRC failed")
        assert err.path == "/tmp/test.zip"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ArchiveCorruptedError) as exc_info:
            raise ArchiveCorruptedError("/path/to/file.zip", "bad zip")
        assert exc_info.value.path == "/path/to/file.zip"


# ─── BSLBinaryNotFoundError ───


class TestBSLBinaryNotFoundError:
    def test_message_contains_path(self):
        err = BSLBinaryNotFoundError("/usr/local/bin/bsl-ls")
        assert "/usr/local/bin/bsl-ls" in str(err)
        assert "BSL Language Server" in str(err)
        assert "install.sh" in str(err)

    def test_path_attribute(self):
        err = BSLBinaryNotFoundError("/usr/local/bin/bsl-ls")
        assert err.path == "/usr/local/bin/bsl-ls"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(BSLBinaryNotFoundError):
            raise BSLBinaryNotFoundError("/some/path")

    def test_caught_as_bsl_analysis_error(self):
        with pytest.raises(BSLAnalysisError):
            raise BSLBinaryNotFoundError("/some/path")


# ─── BSLAnalysisTimeoutError ───


class TestBSLAnalysisTimeoutError:
    def test_message_contains_timeout(self):
        err = BSLAnalysisTimeoutError(60)
        assert "60" in str(err)
        assert "таймаут" in str(err).lower() or "timeout" in str(err).lower()

    def test_timeout_attribute(self):
        err = BSLAnalysisTimeoutError(120)
        assert err.timeout == 120

    def test_can_be_raised_and_caught(self):
        with pytest.raises(BSLAnalysisTimeoutError) as exc_info:
            raise BSLAnalysisTimeoutError(30)
        assert exc_info.value.timeout == 30

    def test_caught_as_bsl_analysis_error(self):
        with pytest.raises(BSLAnalysisError):
            raise BSLAnalysisTimeoutError(60)


# ─── IndexBuildError ───


class TestIndexBuildError:
    def test_message_contains_config_name_without_detail(self):
        err = IndexBuildError("ut11")
        assert "ut11" in str(err)
        # Без detail — нет двоеточия с дополнительной информацией
        assert ":" not in str(err).replace("https://", "").replace("http://", "")

    def test_message_contains_config_name_with_detail(self):
        err = IndexBuildError("ut11", "metadata_extractor failed")
        assert "ut11" in str(err)
        assert "metadata_extractor failed" in str(err)
        assert ":" in str(err)

    def test_config_name_attribute(self):
        err = IndexBuildError("ut11", "detail")
        assert err.config_name == "ut11"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(IndexBuildError) as exc_info:
            raise IndexBuildError("edo2", "some error")
        assert exc_info.value.config_name == "edo2"

    def test_caught_as_project_error(self):
        with pytest.raises(ProjectError):
            raise IndexBuildError("test")


# ─── ProjectError (базовый) ───


class TestProjectError:
    def test_can_be_raised_with_message(self):
        with pytest.raises(ProjectError) as exc_info:
            raise ProjectError("custom message")
        assert "custom message" in str(exc_info.value)

    def test_can_be_caught_as_exception(self):
        # ProjectError наследуется от Exception
        assert issubclass(ProjectError, Exception)
        try:
            raise ProjectError("test")
        except ProjectError as exc:
            assert isinstance(exc, Exception)

    def test_default_no_args(self):
        err = ProjectError()
        assert str(err) == ""
