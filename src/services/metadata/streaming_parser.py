"""
D2.5 (2026-07-05): Streaming-парсинг XML через lxml.iterparse.

Опциональная оптимизация для больших конфигураций (УТ11, ERP).
xml.etree.ElementTree загружает весь XML в память → OOM на 8000+ объектов.
lxml.iterparse обрабатывает элементы по одному → стабильный memory footprint.

Использование:
    from src.services.metadata.streaming_parser import stream_parse_config

    # Опционально: если lxml установлен
    try:
        stats = stream_parse_config(config_dir, output_path)
    except ImportError:
        # Fallback на обычный extractor
        from src.services.metadata import extract_and_save
        extract_and_save(config_dir, output_path)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import lxml — опциональная зависимость
_LXML_AVAILABLE: bool | None = None


def _check_lxml() -> bool:
    """Проверить доступность lxml (с кэшированием)."""
    global _LXML_AVAILABLE
    if _LXML_AVAILABLE is None:
        try:
            import lxml.etree  # noqa: F401

            _LXML_AVAILABLE = True
        except ImportError:
            _LXML_AVAILABLE = False
            logger.debug("lxml не установлен. pip install lxml для streaming-парсинга.")
    return _LXML_AVAILABLE


def stream_parse_config(config_dir: Path | str, output_path: Path | str) -> dict[str, Any]:
    """
    D2.5: Streaming-парсинг Configuration.xml через lxml.iterparse.

    Обрабатывает XML по элементам, не загружая весь файл в память.
    Подходит для больших конфигураций (8000+ объектов).

    Args:
        config_dir: Путь к директории конфигурации.
        output_path: Куда сохранить результат.

    Returns:
        Статистика парсинга.

    Raises:
        ImportError: если lxml не установлен.
    """
    if not _check_lxml():
        raise ImportError(
            "lxml не установлен. pip install lxml для streaming-парсинга. "
            "Или используйте src.services.metadata.extract_and_save (fallback)."
        )

    from lxml.etree import iterparse

    config_dir = Path(config_dir)
    output_path = Path(output_path)

    config_xml = config_dir / "Configuration.xml"
    if not config_xml.exists():
        raise FileNotFoundError(f"Configuration.xml не найден: {config_xml}")

    result: dict[str, Any] = {
        "version": "1.0",
        "config_name": "",
        "objects": [],
        "stats": {"total_objects": 0, "by_type": {}},
    }

    # Streaming-парсинг Configuration.xml
    stats = {"total": 0, "by_type": {}}

    for _event, elem in iterparse(str(config_xml), events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in ("Catalog", "Document", "Enum", "Constant", "InformationRegister",
                    "AccumulationRegister", "CommonModule", "Report", "DataProcessor"):
            name_elem = elem.find(".//{*}Name") or elem.find("Name")
            name = name_elem.text if name_elem is not None and name_elem.text else ""

            uuid = elem.get("uuid", "")

            result["objects"].append({
                "type": tag,
                "name": name,
                "uuid": uuid,
            })

            stats["total"] += 1
            stats["by_type"][tag] = stats["by_type"].get(tag, 0) + 1

            # Очищаем элемент для освобождения памяти
            elem.clear()

    result["stats"]["total_objects"] = stats["total"]
    result["stats"]["by_type"] = stats["by_type"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "stream_parse_complete",
        total_objects=stats["total"],
        by_type=stats["by_type"],
        output=str(output_path),
    )

    return result["stats"]


def is_streaming_available() -> bool:
    """Проверить, доступен ли streaming-парсинг (lxml установлен)."""
    return _check_lxml()
