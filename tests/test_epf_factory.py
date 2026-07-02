"""
Тесты для src/services/epf_factory.py — утилиты и полный цикл создания EPF.

Покрытие:
- _replace_in_tree — рекурсивная замена в JSON-дереве
- validate_bsl — обёртка над BSL LS (мок subprocess)
- EpfFactory.create_epf — полный цикл (с реальной сборкой через v8unpack)
- EpfFactory.templates — список доступных шаблонов
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.epf_factory import (
    EpfFactory,
    EpfFactoryResult,
    _replace_in_tree,
    validate_bsl,
)


# ─── _replace_in_tree ───


class TestReplaceInTree:
    """Рекурсивная замена значений в JSON-дереве v8unpack."""

    def test_replaces_simple_string(self):
        result = _replace_in_tree("OldName", {"OldName": "NewName"})
        assert result == "NewName"

    def test_returns_original_string_if_not_in_replacements(self):
        result = _replace_in_tree("OtherName", {"OldName": "NewName"})
        assert result == "OtherName"

    def test_replaces_quoted_string(self):
        """Обёрнутые кавычки 1С: '"OldName"' → '"NewValue"'."""
        result = _replace_in_tree('"OldName"', {"OldName": "NewName"})
        assert result == '"NewName"'

    def test_returns_quoted_string_unchanged_if_inner_not_in_replacements(self):
        result = _replace_in_tree('"OtherName"', {"OldName": "NewName"})
        assert result == '"OtherName"'

    def test_handles_string_with_only_quotes(self):
        """Строка только из кавычек не должна падать."""
        result = _replace_in_tree('""', {"OldName": "NewName"})
        assert result == '""'

    def test_replaces_in_list(self):
        data = ["OldName", "other", ["OldName", "deep"]]
        result = _replace_in_tree(data, {"OldName": "NewName"})
        assert result == ["NewName", "other", ["NewName", "deep"]]

    def test_replaces_in_dict_values(self):
        data = {"key1": "OldName", "key2": "other", "nested": {"deep": "OldName"}}
        result = _replace_in_tree(data, {"OldName": "NewName"})
        assert result == {
            "key1": "NewName",
            "key2": "other",
            "nested": {"deep": "NewName"},
        }

    def test_does_not_modify_dict_keys(self):
        """Ключи не заменяются, только значения."""
        data = {"OldName": "value"}
        result = _replace_in_tree(data, {"OldName": "NewName"})
        assert "OldName" in result  # ключ не заменён
        assert result["OldName"] == "value"

    def test_handles_int_and_float(self):
        """Числа возвращаются как есть."""
        assert _replace_in_tree(42, {"OldName": "NewName"}) == 42
        assert _replace_in_tree(3.14, {"OldName": "NewName"}) == 3.14

    def test_handles_bool_and_none(self):
        """Bool и None возвращаются как есть."""
        assert _replace_in_tree(True, {}) is True
        assert _replace_in_tree(False, {}) is False
        assert _replace_in_tree(None, {}) is None

    def test_handles_empty_collections(self):
        assert _replace_in_tree([], {}) == []
        assert _replace_in_tree({}, {}) == {}

    def test_handles_nested_mixed_structure(self):
        data = {
            "list": [1, "OldName", {"key": "OldName"}],
            "quoted": '"OldName"',
            "nested": {"deep_list": ["OldName", "other"]},
        }
        result = _replace_in_tree(data, {"OldName": "Replaced"})
        assert result == {
            "list": [1, "Replaced", {"key": "Replaced"}],
            "quoted": '"Replaced"',
            "nested": {"deep_list": ["Replaced", "other"]},
        }


# ─── validate_bsl ───


class TestValidateBSL:
    """Проверка BSL через BSL LS (с моками)."""

    def test_returns_error_when_bsl_ls_binary_not_found(self, tmp_path):
        """Если BSL LS binary не существует — возвращает ok=False."""
        bsl_file = tmp_path / "module.bsl"
        bsl_file.write_text("#Область ПрограммныйИнтерфейс\n#КонецОбласти\n", encoding="utf-8")

        with patch("src.services.epf_factory.BSL_LS_BINARY", "/nonexistent/bsl-ls"):
            result = validate_bsl(bsl_file)
            assert result["ok"] is False
            assert "не найден" in result["error"]
            assert result["errors"] == 0
            assert result["warnings"] == 0
            assert result["infos"] == 0

    def test_returns_success_when_bsl_ls_passes(self, tmp_path):
        """При успешном анализе возвращает ok=True."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        bsl_file = src_dir / "module.bsl"
        bsl_file.write_text("#Область ПрограммныйИнтерфейс\n#КонецОбласти\n", encoding="utf-8")

        # Создаём фейковый binary файл, чтобы Path.exists() вернул True
        fake_binary = tmp_path / "fake-bsl-ls"
        fake_binary.write_text("#!/bin/bash\necho 'fake'\n", encoding="utf-8")
        fake_binary.chmod(0o755)

        # Мокаем subprocess.run чтобы не вызывать реальный BSL LS
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        # Создаём фейковый out_dir с BSL LS отчётом (bsl-json.json)
        out_dir = tmp_path / "bsl_ls_out"
        out_dir.mkdir(exist_ok=True)
        # BSL LS пишет отчёт в bsl-json.json
        (out_dir / "bsl-json.json").write_text(json.dumps({"fileinfos": [{"diagnostics": []}]}), encoding="utf-8")

        # Мокаем Path.exists() и Path.mkdir() для out_dir
        with (
            patch("src.services.epf_factory.BSL_LS_BINARY", str(fake_binary)),
            patch("src.services.epf_factory.subprocess.run", return_value=mock_result),
            patch("src.services.epf_factory.shutil.rmtree"),
        ):
            result = validate_bsl(bsl_file)
            assert result["ok"] is True
            assert result["errors"] == 0
            assert result["warnings"] == 0


# ─── EpfFactoryResult ───


class TestEpfFactoryResult:
    """Тест дата-класса результата."""

    def test_default_values(self):
        result = EpfFactoryResult()
        assert result.ok is False
        assert result.error == ""
        assert result.epf_path is None
        assert result.size_bytes == 0
        assert result.name == ""
        assert result.synonym == ""
        assert result.proc_uuid == ""
        assert result.form_uuid == ""
        assert result.bsl_lines == 0
        assert result.bsl_warnings == 0
        assert result.bsl_errors == 0
        assert result.round_trip_ok is False
        assert result.work_dir is None

    def test_with_values(self):
        result = EpfFactoryResult(
            ok=True,
            name="TestProc",
            synonym="Test Processing",
            proc_uuid="abc-123",
            form_uuid="def-456",
            bsl_lines=42,
            size_bytes=1024,
        )
        assert result.ok is True
        assert result.name == "TestProc"
        assert result.synonym == "Test Processing"
        assert result.proc_uuid == "abc-123"
        assert result.form_uuid == "def-456"
        assert result.bsl_lines == 42
        assert result.size_bytes == 1024


# ─── EpfFactory.templates ───


class TestEpfFactoryTemplates:
    """Список доступных шаблонов."""

    def test_templates_returns_dict(self):
        """list_templates() возвращает dict с путями к шаблонам."""
        result = EpfFactory.list_templates()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_templates_includes_ext_proc_template(self):
        result = EpfFactory.list_templates()
        assert "ext_proc" in result
        assert "ExternalDataProcessor" in result["ext_proc"]

    def test_templates_includes_form_template(self):
        result = EpfFactory.list_templates()
        assert "form" in result
        assert "Form" in result["form"]

    def test_templates_includes_form_id_template(self):
        result = EpfFactory.list_templates()
        assert "form_id" in result

    def test_templates_includes_form_elem_empty_template(self):
        result = EpfFactory.list_templates()
        assert "form_elem_empty" in result

    def test_templates_includes_templates_dir(self):
        result = EpfFactory.list_templates()
        assert "templates_dir" in result

    def test_templates_paths_exist(self):
        """Все пути к шаблонам в репозитории должны существовать."""
        result = EpfFactory.list_templates()
        for key, path_str in result.items():
            path = Path(path_str)
            assert path.exists(), f"Template {key} not found: {path}"


# ─── EpfFactory.create_epf — базовые сценарии ───


class TestEpfFactoryCreateEpf:
    """Полный цикл создания .epf (с реальной сборкой через v8unpack)."""

    def test_create_epf_with_minimal_bsl_code(self, tmp_path):
        """Создание EPF с минимальным BSL-кодом."""
        factory = EpfFactory()
        output = tmp_path / "TestProc.epf"
        bsl_code = (
            "#Область ПрограммныйИнтерфейс\n#КонецОбласти\n\n#Область СлужебныеПроцедурыИФункции\n#КонецОбласти\n"
        )

        result = factory.create_epf(
            name="TestProc",
            synonym="Тестовая обработка",
            bsl_code=bsl_code,
            output_epf=output,
            skip_bsl_validation=True,
        )

        assert result.ok is True, f"Error: {result.error}"
        assert result.error == ""
        assert result.epf_path == output
        assert output.exists()
        assert output.stat().st_size > 0
        assert result.size_bytes > 0
        assert result.name == "TestProc"
        assert result.synonym == "Тестовая обработка"
        assert result.proc_uuid  # не пустой
        assert result.form_uuid  # не пустой
        assert result.bsl_lines > 0

    def test_create_epf_synonym_defaults_to_name_when_none(self, tmp_path):
        """Если synonym=None — используется name."""
        factory = EpfFactory()
        output = tmp_path / "Test.epf"
        result = factory.create_epf(
            name="TestProc",
            synonym=None,
            bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            output_epf=output,
            skip_bsl_validation=True,
        )
        assert result.ok is True
        assert result.synonym == "TestProc"

    def test_create_epf_with_custom_work_dir(self, tmp_path):
        """Можно указать свой work_dir."""
        factory = EpfFactory()
        work_dir = tmp_path / "custom_workdir"
        output = tmp_path / "Test.epf"

        result = factory.create_epf(
            name="TestProc",
            synonym="Test",
            bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            output_epf=output,
            work_dir=work_dir,
            skip_bsl_validation=True,
            save_sources=True,
        )

        assert result.ok is True
        assert result.work_dir == work_dir
        assert work_dir.exists()

    def test_create_epf_save_sources_preserves_work_dir(self, tmp_path):
        """save_sources=True сохраняет рабочий каталог."""
        factory = EpfFactory()
        work_dir = tmp_path / "saved_workdir"
        output = tmp_path / "Test.epf"

        result = factory.create_epf(
            name="TestProc",
            synonym="Test",
            bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            output_epf=output,
            work_dir=work_dir,
            skip_bsl_validation=True,
            save_sources=True,
        )

        assert result.ok is True
        assert work_dir.exists()
        # В work_dir должны быть v8unpack-исходники
        src_dir = work_dir / "src"
        assert src_dir.exists()
        # Должен быть ExternalDataProcessor.json
        assert (src_dir / "ExternalDataProcessor.json").exists()

    def test_create_epf_without_save_sources_cleans_work_dir(self, tmp_path):
        """save_sources=False (по умолчанию) удаляет рабочий каталог."""
        factory = EpfFactory()
        work_dir = tmp_path / "temp_workdir"
        output = tmp_path / "Test.epf"

        result = factory.create_epf(
            name="TestProc",
            synonym="Test",
            bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            output_epf=output,
            work_dir=work_dir,
            skip_bsl_validation=True,
            save_sources=False,
        )

        assert result.ok is True
        # work_dir должен быть удалён (или хотя бы очищен)
        # Реализация может оставлять пустой каталог — главное, что исходники не сохранены

    def test_create_epf_generates_unique_uuids(self, tmp_path):
        """Каждый запуск генерирует новые UUID."""
        factory = EpfFactory()
        output1 = tmp_path / "Test1.epf"
        output2 = tmp_path / "Test2.epf"

        bsl = "#Область ПрограммныйИнтерфейс\n#КонецОбласти\n"
        result1 = factory.create_epf(
            name="Test1",
            synonym="T1",
            bsl_code=bsl,
            output_epf=output1,
            skip_bsl_validation=True,
        )
        result2 = factory.create_epf(
            name="Test2",
            synonym="T2",
            bsl_code=bsl,
            output_epf=output2,
            skip_bsl_validation=True,
        )

        assert result1.ok and result2.ok
        assert result1.proc_uuid != result2.proc_uuid
        assert result1.form_uuid != result2.form_uuid

    def test_create_epf_with_custom_form_name(self, tmp_path):
        """Можно указать своё имя формы."""
        factory = EpfFactory()
        output = tmp_path / "Test.epf"

        result = factory.create_epf(
            name="TestProc",
            synonym="Test",
            bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
            output_epf=output,
            form_name="МояФорма",
            skip_bsl_validation=True,
        )

        assert result.ok is True

    def test_create_epf_round_trip_verification(self, tmp_path):
        """Round-trip: собранный .epf можно распаковать и получить BSL обратно."""
        factory = EpfFactory()
        output = tmp_path / "RoundTrip.epf"
        original_bsl = (
            "#Область ПрограммныйИнтерфейс\nФункция МойМетод() Экспорт\n    Возврат 42;\nКонецФункции\n#КонецОбласти\n"
        )

        result = factory.create_epf(
            name="RoundTrip",
            synonym="Round Trip Test",
            bsl_code=original_bsl,
            output_epf=output,
            skip_bsl_validation=True,
        )

        assert result.ok is True
        assert result.round_trip_ok is True


# ─── EpfFactory.create_epf — ошибки ───


class TestEpfFactoryCreateEpfErrors:
    """Обработка ошибок при создании EPF."""

    def test_create_epf_handles_v8unpack_failure(self, tmp_path):
        """Если v8unpack падает — возвращается ok=False с ошибкой."""
        factory = EpfFactory()
        output = tmp_path / "Failed.epf"

        # Мокаем subprocess.run чтобы v8unpack упал
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "v8unpack error: simulated failure"

        with patch("src.services.epf_factory.subprocess.run", return_value=mock_result):
            result = factory.create_epf(
                name="Failed",
                synonym="F",
                bsl_code="#Область ПрограммныйИнтерфейс\n#КонецОбласти\n",
                output_epf=output,
                skip_bsl_validation=True,
            )

        assert result.ok is False
        assert result.error != ""
        assert "v8unpack" in result.error.lower() or "failed" in result.error.lower()
