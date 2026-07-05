"""
_security.py — общие security-утилиты для MCP handlers.

Главная задача: защита от path traversal (CWE-22) при работе с file_path,
которые приходят от MCP-клиента (IDE/LLM). Без валидации атакующий может
передать file_path='../../../../etc/passwd' и получить содержимое любого
файла, доступного процессу MCP-сервера.

См. audit P1.8: src/mcpserver/handlers/quality.py:83-91 — path traversal.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.project import Project


def resolve_path_within_project(
    raw_path: str,
    project: Project,
    *,
    must_exist: bool = False,
) -> Path | None:
    """
    Резолвит путь, проверяя что он находится внутри project.paths.root.

    Алгоритм:
    1. Если путь относительный — он считается относительным к project.paths.root
       (это поведение сохранено из оригинальных handlers для обратной совместимости).
    2. Резолвим через os.path.realpath() чтобы раскрыть '..' и симлинки.
    3. Проверяем, что полученный абсолютный путь начинается с project.paths.root.
    4. Если must_exist=True — дополнительно проверяем существование.

    Args:
        raw_path: Путь от MCP-клиента (может быть относительным, абсолютным,
            содержать '..' или симлинки).
        project: Project для получения корня.
        must_exist: Если True, вернуть None если путь не существует.

    Returns:
        Path если путь валиден и находится внутри проекта, иначе None.

    Examples:
        >>> resolve_path_within_project("data/file.bsl", project)
        PosixPath('/repo/data/file.bsl')

        >>> resolve_path_within_project("../../etc/passwd", project)
        None  # path traversal blocked

        >>> resolve_path_within_project("/etc/passwd", project)
        None  # absolute path outside project
    """
    if not raw_path:
        return None

    project_root = project.paths.root.resolve()

    # Шаг 1: делаем путь абсолютным (relative → relative to project root).
    if os.path.isabs(raw_path):  # noqa: SIM108 - явный if-else для читаемости security-кода
        candidate = Path(raw_path)
    else:
        candidate = project_root / raw_path

    # Шаг 2: резолвим через realpath — раскрывает '..' и симлинки.
    # Это критически важно: Path.resolve() тоже работает, но os.path.realpath
    # корректно обрабатывает симлинки, которые указывают ЗА пределы проекта.
    try:
        resolved = Path(os.path.realpath(str(candidate)))
    except (OSError, RuntimeError):
        return None

    # Шаг 3: path traversal check.
    # Используем os.path.commonpath для надёжного сравнения
    # (startswith на строках может дать false positive при совпадении префиксов).
    try:
        common = os.path.commonpath([str(resolved), str(project_root)])
    except ValueError:
        # ValueError если пути на разных дисках (Windows) — точно не внутри.
        return None
    if common != str(project_root):
        return None

    # Шаг 4: опциональная проверка существования.
    if must_exist and not resolved.exists():
        return None

    return resolved


def is_path_within_project(path: Path, project: Project) -> bool:
    """
    Быстрая проверка: находится ли path внутри project.paths.root.

    Не резолвит симлинки — для использования с уже валидными путями.
    Для user-supplied input используйте resolve_path_within_project().
    """
    try:
        path.resolve().relative_to(project.paths.root.resolve())
        return True
    except (ValueError, OSError):
        return False
