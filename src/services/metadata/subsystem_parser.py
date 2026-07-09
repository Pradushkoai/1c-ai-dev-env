from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class SubsystemParser:
    """Парсер подсистем 1С — извлекает иерархию и содержимое."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит Subsystem/<Имя>.xml."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        subsys_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == "Subsystem":
                subsys_elem = child
                break

        if subsys_elem is None:
            return None

        properties = XMLUtils.get_child(subsys_elem, "Properties")
        child_objects = XMLUtils.get_child(subsys_elem, "ChildObjects")

        result = {
            "type": "Subsystem",
            "name": XMLUtils.get_text(properties, "Name") if properties is not None else "",
            "uuid": subsys_elem.get("uuid", ""),
            "synonym": XMLUtils.get_synonym(properties) if properties is not None else "",
            "comment": XMLUtils.get_text(properties, "Comment") if properties is not None else "",
            "content": [],
            "child_subsystems": [],
        }

        # Content — список объектов в подсистеме
        content_elem = XMLUtils.get_child(properties, "Content") if properties is not None else None
        if content_elem is not None:
            for item in content_elem:
                result["content"].append(item.text or "")

        # Child subsystems
        if child_objects is not None:
            for child in child_objects:
                if XMLUtils.strip_ns(child.tag) == "Subsystem":
                    result["child_subsystems"].append(
                        {
                            "name": child.text or "",
                            "uuid": child.get("uuid", ""),
                        }
                    )

        return result


# ============================================================================
# ПАРСЕР EVENT SUBSCRIPTIONS
# ============================================================================


