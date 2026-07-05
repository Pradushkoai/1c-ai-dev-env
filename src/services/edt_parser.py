"""
edt_parser.py — Парсер EDT (Enterprise Development Tools) формата 1С.

P2.1: MVP парсер EDT XML выгрузки в унифицированный формат metadata-index.

EDT формат отличается от Конфигуратора:
- Структура каталогов: EDT использует src/<Configuration>/ вместо корня
- Имена файлов: Configuration.mdo вместо Configuration.xml
- Namespace: http://g5.1c.ru/v8/dt/metadata/mdclasses вместо v8.1c.ru/8.3/MDClasses
- Дополнительные файлы: .mdo, .en.md (документация), .settings

Этот парсер конвертирует EDT выгрузку в тот же формат, что и
metadata_extractor (unified-metadata-index.json), чтобы все MCP tools
работали с обоими форматами без изменений.

Использование:
    from src.services.edt_parser import EdtParser

    parser = EdtParser()
    objects = parser.parse(edt_project_path)
    # objects — список в формате unified-metadata-index

Статус: MVP — поддерживает Catalog, Document, Enum, InformationRegister.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# EDT namespace
NS_EDT = "http://g5.1c.ru/v8/dt/metadata/mdclasses"

# Маппинг типов объектов EDT → unified format
EDT_TYPE_MAP: dict[str, str] = {
    "Catalog": "Catalog",
    "Document": "Document",
    "Enum": "Enum",
    "InformationRegister": "InformationRegister",
    "AccumulationRegister": "AccumulationRegister",
    "Constant": "Constant",
    "CommonModule": "CommonModule",
    "Report": "Report",
    "DataProcessor": "DataProcessor",
}

# Папки EDT по типам объектов
EDT_DIRS: dict[str, str] = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "Enum": "Enums",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "Constant": "Constants",
    "CommonModule": "CommonModules",
    "Report": "Reports",
    "DataProcessor": "DataProcessors",
}


class EdtParser:
    """Парсер EDT (Enterprise Development Tools) формата 1С.

    MVP (P2.1): поддерживает Catalog, Document, Enum, InformationRegister.
    Конвертирует EDT XML в unified-metadata-index формат.
    """

    def __init__(self) -> None:
        self._objects: list[dict[str, Any]] = []
        self._config_name: str = ""

    def parse(self, edt_project_path: Path | str) -> list[dict[str, Any]]:
        """Парсить EDT проект в unified metadata format.

        Args:
            edt_project_path: Путь к корню EDT проекта (содержит src/).

        Returns:
            Список объектов в unified-metadata-index формате.
        """
        project_path = Path(edt_project_path)
        self._objects = []
        self._config_name = self._detect_config_name(project_path)

        # EDT структура: src/<Configuration>/Configuration.mdo
        # и src/<Configuration>/Catalogs/, Documents/, и т.д.
        src_dir = project_path / "src"
        if not src_dir.exists():
            # Fallback: корень проекта может быть напрямую конфигурацией
            src_dir = project_path

        # Ищем поддиректории с типами объектов
        for obj_type, dir_name in EDT_DIRS.items():
            type_dir = src_dir / dir_name
            if type_dir.is_dir():
                for mdo_file in type_dir.glob("*.mdo"):
                    try:
                        obj = self._parse_mdo_file(mdo_file, obj_type)
                        if obj:
                            self._objects.append(obj)
                    except Exception as e:
                        logger.warning("Failed to parse %s: %s", mdo_file, e)

        logger.info("EDT parse complete: %d objects found", len(self._objects))
        return self._objects

    def _detect_config_name(self, project_path: Path) -> str:
        """Определить имя конфигурации из EDT проекта."""
        # Ищем Configuration.mdo
        src_dir = project_path / "src"
        if not src_dir.exists():
            src_dir = project_path

        for config_mdo in src_dir.rglob("Configuration.mdo"):
            try:
                tree = ET.parse(config_mdo)
                root = tree.getroot()
                # Имя конфигурации (пробуем с EDT namespace и без)
                name = self._get_text(root, "name")
                if name:
                    return name
            except ET.ParseError:
                continue

        return project_path.name

    def _parse_mdo_file(self, mdo_path: Path, obj_type: str) -> dict[str, Any] | None:
        """Парсить один .mdo файл EDT.

        Args:
            mdo_path: Путь к .mdo файлу.
            obj_type: Тип объекта (Catalog, Document, и т.д.).

        Returns:
            Объект в unified format, или None если парсинг не удался.
        """
        try:
            tree = ET.parse(mdo_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.warning("XML parse error in %s: %s", mdo_path, e)
            return None

        # Извлекаем имя объекта
        name = self._get_text(root, "name")
        if not name:
            # Fallback: имя из имени файла
            name = mdo_path.stem

        # Создаём объект в unified format
        obj: dict[str, Any] = {
            "type": EDT_TYPE_MAP.get(obj_type, obj_type),
            "name": name,
            "synonym": self._get_text(root, "synonym") or name,
            "comment": self._get_text(root, "comment") or "",
            "source": "edt",
            "mdo_path": str(mdo_path),
        }

        # Парсим специфичные для типа поля
        if obj_type == "Catalog":
            self._parse_catalog_fields(root, obj)
        elif obj_type == "Document":
            self._parse_document_fields(root, obj)
        elif obj_type == "InformationRegister":
            self._parse_register_fields(root, obj)

        return obj

    def _parse_catalog_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля справочника."""
        obj["hierarchical"] = self._get_text(root, "hierarchical") == "true"
        obj["owners"] = []  # TODO: парсить владельцев
        # Реквизиты
        obj["attributes"] = self._parse_attributes(root)

    def _parse_document_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля документа."""
        obj["number_type"] = self._get_text(root, "numberType") or "String"
        obj["register_records"] = []  # TODO: парсить регистры
        obj["attributes"] = self._parse_attributes(root)

    def _parse_register_fields(self, root: ET.Element, obj: dict[str, Any]) -> None:
        """Парсить поля регистра сведений."""
        obj["periodicity"] = self._get_text(root, "periodicity") or "Nonperiodical"
        obj["resources"] = self._parse_attributes(root, tag="resources")
        obj["dimensions"] = self._parse_attributes(root, tag="dimensions")

    def _parse_attributes(self, root: ET.Element, tag: str = "attributes") -> list[dict[str, str]]:
        """Парсить реквизиты/ресурсы/измерения объекта.

        Args:
            root: XML корень элемента.
            tag: Имя тега для поиска (attributes, resources, dimensions).

        Returns:
            Список атрибутов [{name, type, synonym}].
        """
        attrs: list[dict[str, str]] = []
        # Пробуем с EDT namespace и без
        attr_elems = root.findall(f".//{{{NS_EDT}}}{tag}")
        if not attr_elems:
            attr_elems = root.findall(f".//{tag}")

        for attr_elem in attr_elems:
            name = self._get_text(attr_elem, "name")
            if name:
                attrs.append(
                    {
                        "name": name,
                        "type": self._get_text(attr_elem, "type") or "String",
                        "synonym": self._get_text(attr_elem, "synonym") or name,
                    }
                )
        return attrs

    def _get_text(self, root: ET.Element, tag: str) -> str | None:
        """Получить текст элемента по имени тега (с EDT namespace).

        Args:
            root: XML элемент для поиска.
            tag: Имя тега без namespace.

        Returns:
            Текст элемента, или None если не найден.
        """
        # Пробуем с EDT namespace
        elem = root.find(f".//{{{NS_EDT}}}{tag}")
        if elem is not None and elem.text:
            return elem.text.strip()

        # Fallback: без namespace
        elem = root.find(f".//{tag}")
        if elem is not None and elem.text:
            return elem.text.strip()

        return None

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику парсинга.

        Returns:
            {config_name, total_objects, by_type}
        """
        by_type: dict[str, int] = {}
        for obj in self._objects:
            t = obj.get("type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "config_name": self._config_name,
            "total_objects": len(self._objects),
            "by_type": by_type,
            "source": "edt",
        }
