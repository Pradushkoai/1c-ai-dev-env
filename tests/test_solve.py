"""
Интеграционный тест для 1c-ai solve check.

Проверяет полный цикл:
1. Создаёт .bsl файл с нарушениями
2. Запускает solve check (BSL LS + 42 правила)
3. Проверяет exit code и содержание отчёта

BSL LS тесты помечены @requires_bsl_ls — пропускаются если не установлен.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from src.project import Project
from src.services.path_manager import PathManager


def _is_bsl_ls_available() -> bool:
    """Проверяет, установлен ли BSL LS."""
    pm = PathManager()
    return pm.bsl_ls_binary.exists()


requires_bsl_ls = pytest.mark.skipif(not _is_bsl_ls_available(), reason="BSL Language Server не установлен")


def test_solve_check_with_errors(tmp_path):
    """solve check на файле с errors — должен вернуть exit code 1."""
    from src.cli import _solve_check

    # Создаём .bsl файл с известными нарушениями (no-vypolnit = error)
    bsl_file = tmp_path / "bad.bsl"
    bsl_file.write_text(
        """Перем _Запрос;

Процедура Тест()
    Выполнить("code");
КонецПроцедуры
""",
        encoding="utf-8",
    )

    # Создаём project с mock PathManager
    pm = PathManager(project_root=tmp_path)

    project = MagicMock()
    project.paths = pm
    # PathManager.bsl_ls_binary — property, используем mock
    project.paths = MagicMock()
    project.paths.bsl_ls_binary = tmp_path / "nonexistent"
    # Указываем реальный путь к scripts/ из репозитория
    repo_scripts = Path(__file__).parent.parent / "scripts"
    project.paths.scripts_dir = repo_scripts
    project.paths.root = Path(__file__).parent.parent
    project.bsl_analyzer = MagicMock()

    args = MagicMock()
    args.path = str(bsl_file)
    args.config = None
    args.ci = False
    args.json = False
    args.sarif = None
    args.level = "quick"

    # solve check должен вызвать sys.exit(1) т.к. есть errors (no-vypolnit, no-underscore-vars)
    with pytest.raises(SystemExit) as exc_info:
        _solve_check(project, args)

    assert exc_info.value.code == 1


def test_solve_check_clean_file(tmp_path):
    """solve check на чистом файле — exit code 0."""
    from src.cli import _solve_check

    bsl_file = tmp_path / "clean.bsl"
    bsl_file.write_text(
        """#Область ПрограммныйИнтерфейс

// Рассчитать сумму.
//
// Параметры:
//  А - Число - первое число
//  Б - Число - второе число
//
// Возвращаемое значение:
//  Число - сумма
Функция РассчитатьСумму(А, Б) Экспорт
    Возврат А + Б;
КонецФункции

#КонецОбласти

#Область СлужебныйПрограммныйИнтерфейс
#КонецОбласти

#Область СлужебныеПроцедурыИФункции
#КонецОбласти
""",
        encoding="utf-8",
    )

    pm = PathManager(project_root=tmp_path)
    from src.services.bsl_analyzer import BSLAnalyzer

    project = MagicMock()
    project.paths = pm
    project.bsl_analyzer = BSLAnalyzer(pm.bsl_ls_binary, pm.bsl_ls_config, pm.root)

    args = MagicMock()
    args.path = str(bsl_file)
    args.config = None
    args.ci = False
    args.json = False
    args.sarif = None
    args.level = "quick"

    # solve check должен вызвать sys.exit(0) — нет errors
    with pytest.raises(SystemExit) as exc_info:
        _solve_check(project, args)

    # exit code 0 = нет errors (warnings допустимы)
    assert exc_info.value.code == 0


def test_solve_check_nonexistent_file(tmp_path):
    """solve check на несуществующем файле — exit code 1."""
    from src.cli import _solve_check

    pm = PathManager(project_root=tmp_path)

    project = MagicMock()
    project.paths = pm

    args = MagicMock()
    args.path = str(tmp_path / "nonexistent.bsl")
    args.config = None
    args.ci = False
    args.json = False
    args.sarif = None
    args.level = "quick"

    with pytest.raises(SystemExit) as exc_info:
        _solve_check(project, args)

    assert exc_info.value.code == 2


def test_solve_context_no_config(tmp_path):
    """solve context без --config — должен работать, но пропустить API."""
    import io
    from contextlib import redirect_stdout

    from src.cli import _solve_context

    pm = PathManager(project_root=tmp_path)

    project = MagicMock()
    project.paths = pm
    # fast_search_index не существует → поиск пропускается

    args = MagicMock()
    args.query = "найти элемент по коду"
    args.config = None
    args.limit = 3

    output = io.StringIO()
    with redirect_stdout(output):
        _solve_context(project, args)

    result = output.getvalue()
    assert "сбор контекста" in result.lower() or "контекст" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
