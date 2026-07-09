from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class RoleParser:
    """Парсер ролей 1С — извлекает права доступа и RLS."""

    def __init__(self):
        self.utils = XMLUtils()

    def parse_role_metadata(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит метаданные роли (Role/<Имя>.xml)."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        role_elem = None
        for child in root:
            if XMLUtils.strip_ns(child.tag) == "Role":
                role_elem = child
                break

        if role_elem is None:
            return None

        properties = XMLUtils.get_child(role_elem, "Properties")
        return {
            "type": "Role",
            "name": XMLUtils.get_text(properties, "Name") if properties is not None else "",
            "uuid": role_elem.get("uuid", ""),
            "synonym": XMLUtils.get_synonym(properties) if properties is not None else "",
        }

    def parse_rights(self, xml_path: Path) -> dict[str, Any] | None:
        """Парсит Rights.xml — права доступа для роли."""
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        rights = []
        for obj_elem in root:
            if XMLUtils.strip_ns(obj_elem.tag) != "object":
                continue

            obj_name = XMLUtils.get_text(obj_elem, "name")
            obj_rights = []

            for right_elem in obj_elem:
                if XMLUtils.strip_ns(right_elem.tag) != "right":
                    continue

                right_name = XMLUtils.get_text(right_elem, "name")
                right_value = XMLUtils.get_text(right_elem, "value")

                # RLS-правила (Restriction)
                restriction = XMLUtils.get_child(right_elem, "restriction")
                rls_text = ""
                if restriction is not None and restriction.text:
                    rls_text = restriction.text.strip()

                obj_rights.append(
                    {
                        "right": right_name,
                        "value": right_value == "true",
                        "rls": rls_text,
                    }
                )

            rights.append(
                {
                    "object": obj_name,
                    "rights": obj_rights,
                }
            )

        return {
            "total_objects": len(rights),
            "objects": rights,
        }


# ============================================================================
# ПАРСЕР SUBSYSTEMS (иерархия подсистем)
# ============================================================================


