#!/usr/bin/env python3
"""
backup_manager.py — Управление backup/restore данных проекта.

Решает проблему потери данных между сессиями (диск пересоздаётся).
Создаёт ZIP архив с содержимым data/ и runtime/, который пользователь
может скачать и хранить у себя. В новой сессии — restore из ZIP.

Использование:
    from src.services.backup_manager import BackupManager
    bm = BackupManager(paths)
    bm.create_backup('/tmp/backup.zip')
    bm.restore_backup('/tmp/backup.zip')
"""
from __future__ import annotations

import logging
import zipfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    """Управление backup/restore данных проекта."""

    def __init__(self, paths):
        """paths — объект PathManager."""
        self.paths = paths

    def create_backup(self, output_path: Path, include_derived: bool = False) -> Path:
        """
        Создать backup в ZIP архиве.

        Args:
            output_path: Куда сохранить ZIP
            include_derived: Включить derived/ (индексы, можно перестроить)

        Returns:
            Путь к созданному ZIP файлу
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Что включаем в backup
        dirs_to_backup = [
            ('data', self.paths.data_dir),
            ('runtime', self.paths.runtime_dir),
        ]
        if include_derived:
            dirs_to_backup.append(('derived', self.paths.derived_dir))

        # Файлы runtime которые включаем (исключаем временные)
        runtime_exclude = {'__pycache__', '.pytest_cache'}

        total_files = 0
        total_size = 0

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # Метаданные backup
            metadata = {
                'created_at': datetime.now().isoformat(),
                'project_root': str(self.paths.root),
                'include_derived': include_derived,
                'dirs': [d[0] for d in dirs_to_backup],
            }
            zf.writestr('_backup_meta.json', str(metadata))

            for dir_name, dir_path in dirs_to_backup:
                if not dir_path.exists():
                    logger.warning(f"Директория не существует: {dir_path}")
                    continue

                for file_path in dir_path.rglob('*'):
                    if file_path.is_file():
                        # Пропускаем исключения
                        rel = file_path.relative_to(dir_path)
                        if any(part in runtime_exclude for part in rel.parts):
                            continue

                        # Архивируем
                        arcname = f'{dir_name}/{rel}'
                        zf.write(file_path, arcname)
                        total_files += 1
                        total_size += file_path.stat().st_size

        logger.info(f"Backup создан: {output_path} ({total_files} файлов, "
                    f"{total_size / 1024 / 1024:.1f} МБ)")
        return output_path

    def restore_backup(self, backup_path: Path) -> dict:
        """
        Восстановить данные из ZIP архива.

        Args:
            backup_path: Путь к ZIP файлу

        Returns:
            dict со статистикой восстановления
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup файл не найден: {backup_path}")

        stats = {
            'files_restored': 0,
            'dirs_restored': set(),
            'size_bytes': 0,
        }

        with zipfile.ZipFile(backup_path, 'r') as zf:
            # Читаем метаданные
            try:
                meta = zf.read('_backup_meta.json').decode('utf-8')
                logger.info(f"Backup метаданные: {meta}")
            except KeyError:
                pass  # старый формат без метаданных

            for info in zf.infolist():
                if info.filename.startswith('_'):
                    continue  # служебные файлы

                # Разбираем путь: dir_name/relative_path
                parts = info.filename.split('/', 1)
                if len(parts) < 2:
                    continue

                dir_name, rel_path = parts
                target_dir = self._get_target_dir(dir_name)
                if target_dir is None:
                    continue

                target_path = target_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Извлекаем файл
                with zf.open(info) as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())

                stats['files_restored'] += 1
                stats['dirs_restored'].add(dir_name)
                stats['size_bytes'] += info.file_size

        stats['dirs_restored'] = list(stats['dirs_restored'])
        logger.info(f"Restore завершён: {stats['files_restored']} файлов")
        return stats

    def _get_target_dir(self, dir_name: str) -> Path | None:
        """Возвращает целевую директорию по имени."""
        dirs = {
            'data': self.paths.data_dir,
            'runtime': self.paths.runtime_dir,
            'derived': self.paths.derived_dir,
        }
        return dirs.get(dir_name)

    def list_backups(self, backup_dir: Path) -> list[dict]:
        """
        Список доступных backup'ов в директории.

        Args:
            backup_dir: Папка с ZIP архивами

        Returns:
            list of dict с информацией о каждом backup
        """
        backup_dir = Path(backup_dir)
        if not backup_dir.exists():
            return []

        backups = []
        for zf_path in sorted(backup_dir.glob('*.zip')):
            try:
                with zipfile.ZipFile(zf_path, 'r') as zf:
                    # Читаем метаданные
                    try:
                        meta = zf.read('_backup_meta.json').decode('utf-8')
                        import ast
                        meta_dict = ast.literal_eval(meta)
                        created_at = meta_dict.get('created_at', '?')
                    except (KeyError, Exception):
                        created_at = '?'

                    file_count = sum(1 for i in zf.infolist() if not i.filename.startswith('_'))

                backups.append({
                    'path': str(zf_path),
                    'name': zf_path.name,
                    'size_mb': zf_path.stat().st_size / 1024 / 1024,
                    'files': file_count,
                    'created_at': created_at,
                })
            except Exception as e:
                logger.warning(f"Не удалось прочитать backup {zf_path}: {e}")

        return backups
