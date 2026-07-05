"""
i18n.py — Локализация сообщений об ошибках и UI (en/ru).

P3.8: Поддержка двух языков для MCP tools и CLI.
AI-агенты на английском могут не понимать русские сообщения.

Использование:
    from src.i18n import t, set_language, get_language

    set_language('en')  # или 'ru' (по умолчанию)
    msg = t('errors.config_not_found', name='ut11')
"""

from __future__ import annotations

import os
from typing import Any

# Текущий язык (ru по умолчанию, можно переопределить через env LANG=en)
_current_language: str = os.environ.get("1C_AI_LANG", "ru")

# Словарь переводов
# Структура: {key: {lang: message}}
# {var} — плейсхолдеры для подстановки
_MESSAGES: dict[str, dict[str, str]] = {
    # === Ошибки конфигурации ===
    "errors.config_not_found": {
        "ru": "Конфигурация '{name}' не найдена",
        "en": "Configuration '{name}' not found",
    },
    "errors.config_already_exists": {
        "ru": "Конфигурация '{name}' уже существует",
        "en": "Configuration '{name}' already exists",
    },
    "errors.config_not_active": {
        "ru": "Конфигурация '{name}' не активна",
        "en": "Configuration '{name}' is not active",
    },
    "errors.config_name_required": {
        "ru": "config_name required",
        "en": "config_name is required",
    },
    # === Ошибки анализа ===
    "errors.file_not_found": {
        "ru": "Файл не найден: {path}",
        "en": "File not found: {path}",
    },
    "errors.file_path_required": {
        "ru": "file_path is required",
        "en": "file_path is required",
    },
    "errors.bsl_ls_not_found": {
        "ru": "BSL Language Server не найден: {path}. Запустите: bash install.sh",
        "en": "BSL Language Server not found: {path}. Run: bash install.sh",
    },
    "errors.bsl_ls_timeout": {
        "ru": "Превышен таймаут BSL LS: {timeout} сек",
        "en": "BSL LS timeout exceeded: {timeout}s",
    },
    # === Ошибки DSL ===
    "errors.output_dir_required": {
        "ru": "output_dir required",
        "en": "output_dir is required",
    },
    "errors.output_path_required": {
        "ru": "output_path required",
        "en": "output_path is required",
    },
    "errors.unknown_tool": {
        "ru": "Unknown tool: {name}",
        "en": "Unknown tool: {name}",
    },
    "errors.unknown_query_type": {
        "ru": "Unknown query_type: {query_type}",
        "en": "Unknown query_type: {query_type}",
    },
    # === Ошибки EPF ===
    "errors.name_required": {
        "ru": "name required",
        "en": "name is required",
    },
    "errors.epf_build_failed": {
        "ru": "v8unpack -B failed: {error}",
        "en": "v8unpack -B failed: {error}",
    },
    "errors.epf_timeout": {
        "ru": "v8unpack timeout при сборке",
        "en": "v8unpack timeout during build",
    },
    "errors.epf_bad_signature": {
        "ru": "Неверная сигнатура .epf: {sig}",
        "en": "Invalid .epf signature: {sig}",
    },
    # === Ошибки CFE ===
    "errors.extension_path_required": {
        "ru": "extension_path, config_path required",
        "en": "extension_path and config_path are required",
    },
    "errors.object_ref_required": {
        "ru": "extension_path, config_path, object_ref required",
        "en": "extension_path, config_path, object_ref are required",
    },
    "errors.module_path_required": {
        "ru": "extension_path, module_path, method_name required",
        "en": "extension_path, module_path, method_name are required",
    },
    # === Ошибки OpenSpec ===
    "errors.change_id_required": {
        "ru": "change_id required",
        "en": "change_id is required",
    },
    "errors.change_id_title_required": {
        "ru": "change_id, title required",
        "en": "change_id and title are required",
    },
    "errors.item_not_found": {
        "ru": "Item not found: {item_id}",
        "en": "Item not found: {item_id}",
    },
    # === Ошибки данных ===
    "errors.github_token_not_set": {
        "ru": "Не настроен GITHUB_TOKEN или repo. Установите GITHUB_TOKEN в окружении.",
        "en": "GITHUB_TOKEN or repo not configured. Set GITHUB_TOKEN in environment.",
    },
    "errors.index_not_found": {
        "ru": "{index} not found for config '{config_name}'",
        "en": "{index} not found for config '{config_name}'",
    },
    # === Общие ===
    "errors.object_not_found": {
        "ru": "Object '{name}' not found in config '{config_name}'",
        "en": "Object '{name}' not found in config '{config_name}'",
    },
    "errors.form_not_found": {
        "ru": "Form '{name}' not found in config '{config_name}'",
        "en": "Form '{name}' not found in config '{config_name}'",
    },
    "errors.skd_not_found": {
        "ru": "SKD schema for '{name}' not found in config '{config_name}'",
        "en": "SKD schema for '{name}' not found in config '{config_name}'",
    },
    "errors.target_not_implemented": {
        "ru": "target '{target}' with mode '{mode}' not yet implemented",
        "en": "target '{target}' with mode '{mode}' not yet implemented",
    },
    # === Успех ===
    "success.config_added": {
        "ru": "Добавлена: {name} v{version} ({objects} объектов)",
        "en": "Added: {name} v{version} ({objects} objects)",
    },
    "success.config_built": {
        "ru": "Индексы построены для {name}",
        "en": "Indexes built for {name}",
    },
}


def set_language(lang: str) -> None:
    """Установить язык локализации.

    Args:
        lang: 'ru' или 'en'
    """
    global _current_language
    if lang in ("ru", "en"):
        _current_language = lang


def get_language() -> str:
    """Получить текущий язык."""
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """Получить переведённое сообщение.

    Args:
        key: Ключ сообщения (например, 'errors.config_not_found')
        **kwargs: Параметры для подстановки (например, name='ut11')

    Returns:
        Переведённое сообщение на текущем языке

    Example:
        >>> set_language('en')
        >>> t('errors.config_not_found', name='ut11')
        "Configuration 'ut11' not found"
    """
    msg_dict = _MESSAGES.get(key)
    if msg_dict is None:
        return key  # fallback — возвращаем ключ

    msg = msg_dict.get(_current_language) or msg_dict.get("ru") or key

    # Подстановка параметров
    if kwargs:
        import contextlib

        with contextlib.suppress(KeyError, IndexError):
            msg = msg.format(**kwargs)

    return msg
