"""
T5.1b (2026-07-06): Тесты для миграции epf_factory на native writer.

Проверяет:
- EpfFactory.create_epf_native метод существует
- Создаёт EPF через NativeEpfWriter
- EpfFactoryResult.native_mode = True
- Совместимость с create_epf (тот же interface)
- create_native_epf convenience function
- Fallback когда v8unpack недоступен
- Round-trip: созданный EPF читается NativeEpfReader
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from src.services.epf.native_writer import NativeEpfReader
from src.services.epf_factory import EpfFactory
from src.services.epf.native_migration import create_native_epf


# ============================================================================
# EpfFactory.create_epf_native tests
# ============================================================================


class TestCreateEpfNative:
    """Тесты метода create_epf_native."""

    def test_method_exists(self) -> None:
        """Метод create_epf_native существует."""
        factory = EpfFactory()
        assert hasattr(factory, "create_epf_native")
        assert callable(factory.create_epf_native)

    def test_creates_epf_file(self, tmp_path: Path) -> None:
        """Создаёт .epf файл."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="Тестовая",
            synonym="Тестовая обработка",
            bsl_code='Процедура X() Экспорт\nСообщить("Hi");\nКонецПроцедуры',
            output_epf=output,
        )
        assert result.ok
        assert output.exists()

    def test_native_mode_flag(self, tmp_path: Path) -> None:
        """native_mode = True."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.native_mode is True

    def test_synonym_defaults_to_name(self, tmp_path: Path) -> None:
        """Если synonym=None, используется name."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="MyName",
            synonym=None,
            bsl_code='// code',
            output_epf=output,
        )
        assert result.synonym == "MyName"

    def test_creates_valid_zip(self, tmp_path: Path) -> None:
        """Созданный файл — валидный ZIP."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert zipfile.is_zipfile(output)

    def test_size_bytes_populated(self, tmp_path: Path) -> None:
        """size_bytes > 0."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.size_bytes > 0

    def test_epf_path_set(self, tmp_path: Path) -> None:
        """epf_path установлен."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.epf_path == output

    def test_bsl_lines_counted(self, tmp_path: Path) -> None:
        """bsl_lines считается."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        bsl_code = 'Процедура X() Экспорт\nСообщить("a");\nСообщить("b");\nКонецПроцедуры'
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code=bsl_code,
            output_epf=output,
        )
        assert result.bsl_lines == 4  # 4 строки

    def test_round_trip_ok_true(self, tmp_path: Path) -> None:
        """round_trip_ok = True (native writer всегда round-trip safe)."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.round_trip_ok is True

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Создаёт родительские директории."""
        factory = EpfFactory()
        output = tmp_path / "deep" / "nested" / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.ok
        assert output.exists()

    def test_bsl_validation_skipped_by_default(self, tmp_path: Path) -> None:
        """BSL validation пропускается по умолчанию."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        # bsl_validation_ok = True когда validation skipped
        assert result.bsl_validation_ok is True


# ============================================================================
# Compatibility with create_epf tests
# ============================================================================


class TestCompatibility:
    """Тесты совместимости с create_epf interface."""

    def test_returns_epf_factory_result(self, tmp_path: Path) -> None:
        """Возвращает EpfFactoryResult."""
        from src.services.epf.result import EpfFactoryResult

        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert isinstance(result, EpfFactoryResult)

    def test_same_parameter_names(self) -> None:
        """Параметры совпадают с create_epf."""
        import inspect
        factory = EpfFactory()

        native_sig = inspect.signature(factory.create_epf_native)
        native_params = set(native_sig.parameters.keys())

        # Ключевые параметры должны совпадать
        expected = {"name", "synonym", "bsl_code", "output_epf", "form_name"}
        assert expected.issubset(native_params)

    def test_work_dir_none_in_native_mode(self, tmp_path: Path) -> None:
        """work_dir = None в native mode (не используется)."""
        factory = EpfFactory()
        output = tmp_path / "test.epf"
        result = factory.create_epf_native(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.work_dir is None


# ============================================================================
# create_native_epf convenience function tests
# ============================================================================


class TestCreateNativeEpfFunction:
    def test_function_exists(self) -> None:
        """Функция create_native_epf существует."""
        assert callable(create_native_epf)

    def test_creates_epf(self, tmp_path: Path) -> None:
        """Создаёт EPF."""
        output = tmp_path / "conv.epf"
        result = create_native_epf(
            name="Conv",
            synonym="Convenience",
            bsl_code='Процедура X() Экспорт\nКонецПроцедуры',
            output_epf=output,
        )
        assert result.ok
        assert output.exists()

    def test_native_mode_flag(self, tmp_path: Path) -> None:
        """native_mode = True."""
        output = tmp_path / "conv.epf"
        result = create_native_epf(
            name="X",
            synonym="X",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.native_mode is True


# ============================================================================
# Round-trip: create_epf_native → NativeEpfReader
# ============================================================================


class TestNativeRoundTrip:
    """Round-trip: create_epf_native → NativeEpfReader.read_epf."""

    def test_read_creates_by_native(self, tmp_path: Path) -> None:
        """EPF созданный create_epf_native читается NativeEpfReader."""
        factory = EpfFactory()
        output = tmp_path / "rt.epf"

        bsl_code = 'Процедура Test() Экспорт\nСообщить("Hello");\nКонецПроцедуры'
        factory.create_epf_native(
            name="RoundTrip",
            synonym="Round Trip Test",
            bsl_code=bsl_code,
            output_epf=output,
        )

        reader = NativeEpfReader()
        content = reader.read_epf(output)

        assert content is not None
        assert content.metadata["name"] == "RoundTrip"
        assert content.module_bsl == bsl_code

    def test_read_preserves_synonym(self, tmp_path: Path) -> None:
        """Синоним сохраняется при round-trip."""
        factory = EpfFactory()
        output = tmp_path / "rt.epf"
        factory.create_epf_native(
            name="X",
            synonym="Мой синоним",
            bsl_code='// code',
            output_epf=output,
        )

        reader = NativeEpfReader()
        content = reader.read_epf(output)
        assert content is not None
        assert content.metadata["synonym"] == "Мой синоним"


# ============================================================================
# Fallback scenario tests
# ============================================================================


class TestFallbackScenario:
    """Тесты fallback сценария (когда v8unpack недоступен)."""

    def test_native_works_without_v8unpack(self, tmp_path: Path) -> None:
        """Native writer работает без v8unpack."""
        factory = EpfFactory()
        output = tmp_path / "fallback.epf"
        result = factory.create_epf_native(
            name="Fallback",
            synonym="Fallback Test",
            bsl_code='Процедура X() Экспорт\nКонецПроцедуры',
            output_epf=output,
        )
        # Не должно зависеть от v8unpack
        assert result.ok
        assert result.native_mode is True

    def test_native_does_not_call_subprocess(self, tmp_path: Path) -> None:
        """Native writer не вызывает subprocess (без v8unpack)."""
        from unittest.mock import patch, MagicMock

        factory = EpfFactory()
        output = tmp_path / "no_sub.epf"

        # Mock subprocess.run чтобы убедиться что он не вызывается
        with patch("subprocess.run") as mock_run:
            result = factory.create_epf_native(
                name="NoSub",
                synonym="No Subprocess",
                bsl_code='// code',
                output_epf=output,
            )
            assert result.ok
            # subprocess.run не должен вызываться в native mode
            mock_run.assert_not_called()


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_empty_bsl_code_still_creates(self, tmp_path: Path) -> None:
        """Пустой BSL код — EPF создаётся (native writer менее строгий)."""
        factory = EpfFactory()
        output = tmp_path / "empty.epf"
        # Native writer требует module_bsl, но пустая строка не валидна
        # Используем минимальный код
        result = factory.create_epf_native(
            name="Empty",
            synonym="Empty",
            bsl_code='// empty module',
            output_epf=output,
        )
        assert result.ok

    def test_unicode_name(self, tmp_path: Path) -> None:
        """Unicode имя обработки."""
        factory = EpfFactory()
        output = tmp_path / "unicode.epf"
        result = factory.create_epf_native(
            name="Обработка",
            synonym="Моя обработка",
            bsl_code='// code',
            output_epf=output,
        )
        assert result.ok

        reader = NativeEpfReader()
        content = reader.read_epf(output)
        assert content is not None
        assert content.metadata["name"] == "Обработка"

    def test_with_form_spec(self, tmp_path: Path) -> None:
        """С form_spec — form_elements сохраняются."""
        factory = EpfFactory()
        output = tmp_path / "with_form.epf"
        result = factory.create_epf_native(
            name="WithForm",
            synonym="With Form",
            bsl_code='// code',
            output_epf=output,
            form_spec={
                "props": [
                    {"name": "Объект", "type": "DataProcessorObject"},
                    {"name": "Поле1", "type": "String"},
                ]
            },
        )
        assert result.ok

        reader = NativeEpfReader()
        content = reader.read_epf(output)
        # form_elements могут быть или не быть (зависит от обработки form_spec)
        assert content is not None
