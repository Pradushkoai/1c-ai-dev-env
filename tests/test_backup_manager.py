"""
Тесты для backup_manager.py.
Проверяем создание и восстановление backup'ов.
"""

import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from src.services.backup_manager import BackupManager


@pytest.fixture
def mock_paths(tmp_path):
    """Создаёт mock PathManager с тестовой структурой."""
    paths = MagicMock()
    paths.root = tmp_path
    paths.data_dir = tmp_path / "data"
    paths.runtime_dir = tmp_path / "runtime"
    paths.derived_dir = tmp_path / "derived"

    # Создаём тестовые данные
    paths.data_dir.mkdir(parents=True)
    (paths.data_dir / "configs").mkdir()
    (paths.data_dir / "configs" / "test.txt").write_text("test data", encoding="utf-8")

    paths.runtime_dir.mkdir(parents=True)
    (paths.runtime_dir / "config-registry.json").write_text('{"version": "2.0", "configs": {}}', encoding="utf-8")
    (paths.runtime_dir / "session-resume.md").write_text("# Session", encoding="utf-8")

    paths.derived_dir.mkdir(parents=True)
    (paths.derived_dir / "index.json").write_text('{"methods": []}', encoding="utf-8")

    return paths


def test_backup_create_basic(mock_paths, tmp_path):
    """Создание backup включает data/ и runtime/."""
    bm = BackupManager(mock_paths)
    output = tmp_path / "backup.zip"

    result = bm.create_backup(output)

    assert output.exists()
    assert result == output

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()
        # Должны быть файлы из data/ и runtime/
        assert any(n.startswith("data/") for n in names)
        assert any(n.startswith("runtime/") for n in names)
        # Метаданные
        assert "_backup_meta.json" in names


def test_backup_create_without_derived(mock_paths, tmp_path):
    """По умолчанию derived/ не включается в backup."""
    bm = BackupManager(mock_paths)
    output = tmp_path / "backup.zip"

    bm.create_backup(output, include_derived=False)

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()
        assert not any(n.startswith("derived/") for n in names)


def test_backup_create_with_derived(mock_paths, tmp_path):
    """При include_derived=True индексы включаются."""
    bm = BackupManager(mock_paths)
    output = tmp_path / "backup.zip"

    bm.create_backup(output, include_derived=True)

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()
        assert any(n.startswith("derived/") for n in names)


def test_backup_restore(mock_paths, tmp_path):
    """Восстановление из backup."""
    bm = BackupManager(mock_paths)

    # Создаём backup
    backup_path = tmp_path / "backup.zip"
    bm.create_backup(backup_path)

    # Удаляем исходные данные
    import shutil

    shutil.rmtree(mock_paths.data_dir)
    shutil.rmtree(mock_paths.runtime_dir)
    assert not mock_paths.data_dir.exists()

    # Восстанавливаем
    stats = bm.restore_backup(backup_path)

    assert stats["files_restored"] > 0
    assert "data" in stats["dirs_restored"]
    assert "runtime" in stats["dirs_restored"]

    # Проверим что файлы восстановлены
    assert (mock_paths.data_dir / "configs" / "test.txt").exists()
    assert (mock_paths.runtime_dir / "config-registry.json").exists()
    assert (mock_paths.data_dir / "configs" / "test.txt").read_text() == "test data"


def test_backup_restore_nonexistent(tmp_path, mock_paths):
    """Восстановление из несуществующего файла падает."""
    bm = BackupManager(mock_paths)
    with pytest.raises(FileNotFoundError):
        bm.restore_backup(tmp_path / "nonexistent.zip")


def test_backup_preserves_content(mock_paths, tmp_path):
    """Содержимое файлов сохраняется без искажений."""
    bm = BackupManager(mock_paths)

    # Запишем специальные данные
    special_content = "Привет, 1С! Спецсимволы: ё, «», —, ✓"
    (mock_paths.runtime_dir / "special.txt").write_text(special_content, encoding="utf-8")

    # Backup
    backup_path = tmp_path / "backup.zip"
    bm.create_backup(backup_path)

    # Удаляем и восстанавливаем
    (mock_paths.runtime_dir / "special.txt").unlink()
    bm.restore_backup(backup_path)

    # Проверяем
    restored = (mock_paths.runtime_dir / "special.txt").read_text(encoding="utf-8")
    assert restored == special_content


def test_backup_excludes_pycache(mock_paths, tmp_path):
    """__pycache__ исключается из backup."""
    bm = BackupManager(mock_paths)

    # Создаём __pycache__
    pycache_dir = mock_paths.runtime_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "module.cpython-312.pyc").write_text("compiled", encoding="utf-8")

    # Backup
    backup_path = tmp_path / "backup.zip"
    bm.create_backup(backup_path)

    with zipfile.ZipFile(backup_path, "r") as zf:
        names = zf.namelist()
        # __pycache__ не должен попасть в backup
        assert not any("__pycache__" in n for n in names)


def test_backup_list(mock_paths, tmp_path):
    """list_backups возвращает информацию о backup'ах."""
    bm = BackupManager(mock_paths)

    # Создаём несколько backup'ов
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    bm.create_backup(backup_dir / "backup1.zip")
    bm.create_backup(backup_dir / "backup2.zip")

    backups = bm.list_backups(backup_dir)

    assert len(backups) == 2
    assert backups[0]["name"] == "backup1.zip"
    assert backups[1]["name"] == "backup2.zip"
    assert backups[0]["size_mb"] > 0
    assert backups[0]["files"] > 0


def test_backup_list_empty_dir(mock_paths, tmp_path):
    """list_backups с пустой директорией возвращает пустой список."""
    bm = BackupManager(mock_paths)
    backups = bm.list_backups(tmp_path / "empty")
    assert backups == []


def test_backup_list_nonexistent_dir(mock_paths, tmp_path):
    """list_backups с несуществующей директорией возвращает пустой список."""
    bm = BackupManager(mock_paths)
    backups = bm.list_backups(tmp_path / "nonexistent")
    assert backups == []


def test_backup_create_creates_output_dir(mock_paths, tmp_path):
    """create_backup создаёт родительские директории."""
    bm = BackupManager(mock_paths)
    output = tmp_path / "new" / "deep" / "backup.zip"

    bm.create_backup(output)

    assert output.exists()
    assert output.parent.exists()


def test_backup_restore_creates_dirs(mock_paths, tmp_path):
    """restore_backup создаёт директории если их нет."""
    bm = BackupManager(mock_paths)

    # Создаём backup
    backup_path = tmp_path / "backup.zip"
    bm.create_backup(backup_path)

    # Полностью удаляем data/ и runtime/
    import shutil

    shutil.rmtree(mock_paths.data_dir)
    shutil.rmtree(mock_paths.runtime_dir)

    # Восстанавливаем
    bm.restore_backup(backup_path)

    assert mock_paths.data_dir.exists()
    assert mock_paths.runtime_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
