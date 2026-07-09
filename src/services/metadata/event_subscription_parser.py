from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .utils import XMLUtils

class EventSubscriptionParser:
    """Парсер подписок на события."""

    def parse(self, xml_path: Path) -> dict[str, Any] | None:
        root, error = XMLUtils.safe_parse(xml_path)
        if root is None:
            return None

        for child in root:
            if XMLUtils.strip_ns(child.tag) == "EventSubscription":
                properties = XMLUtils.get_child(child, "Properties")
                if properties is None:
                    return None

                # Source — типы объектов, на которые подписка
                source_elem = XMLUtils.get_child(properties, "Source")
                sources = []
                if source_elem is not None:
                    for t in source_elem:
                        if XMLUtils.strip_ns(t.tag) in ("Type", "TypeSet"):
                            if t.text:
                                sources.append(t.text)

                return {
                    "type": "EventSubscription",
                    "name": XMLUtils.get_text(properties, "Name"),
                    "uuid": child.get("uuid", ""),
                    "synonym": XMLUtils.get_synonym(properties),
                    "event": XMLUtils.get_text(properties, "Event"),
                    "handler": XMLUtils.get_text(properties, "Handler"),
                    "sources": sources,
                }
        return None


# ============================================================================
# ПАРСЕР SCHEDULED JOBS
# ============================================================================


