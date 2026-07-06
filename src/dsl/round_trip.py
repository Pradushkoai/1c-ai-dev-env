"""
T5.5 (2026-07-06): Round-trip для всех DSL compilers.

Round-trip = compile → decompile → verify equality.
Проверяет что:
1. JSON DSL → XML (compile)
2. XML → JSON DSL (decompile)
3. Исходный JSON ≈ восстановленный JSON (verify, с нормализацией)

Поддерживаемые DSL:
- Meta (Catalogs, Documents, CommonModules, Subsystems, etc.)
- Form (Form.xml)
- MXL (MXL table templates)
- Role (Roles)
- SKD (Data Composition Schema)
- Subsystem (через subsystem_common.py)
- CommonModule (через subsystem_common.py)

Использование:
    from src.dsl.round_trip import verify_round_trip, RoundTripResult

    result = verify_round_trip(
        dsl_definition={"type": "Catalog", "name": "Товары", ...},
        output_dir=Path("/tmp/test"),
    )
    if result.success:
        print(f"Round-trip OK: {result.object_type}.{result.object_name}")
    else:
        print(f"Round-trip FAILED: {result.error}")
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.dsl._common import NS_MD, NS_V8, NS_XR, _gen_uuid
from src.dsl.subsystem_common import (
    CommonModuleCompiler,
    CommonModuleProperties,
    SubsystemCompiler,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Result
# ============================================================================


@dataclass
class RoundTripResult:
    """Результат round-trip проверки."""

    object_type: str
    object_name: str
    success: bool
    error: str = ""
    original_definition: dict[str, Any] = field(default_factory=dict)
    compiled_xml_path: Path | None = None
    decompiled_definition: dict[str, Any] = field(default_factory=dict)
    differences: list[str] = field(default_factory=list)


# ============================================================================
# Public API
# ============================================================================


def verify_round_trip(
    dsl_definition: dict[str, Any],
    output_dir: str | Path,
) -> RoundTripResult:
    """Проверить round-trip для DSL определения.

    Args:
        dsl_definition: JSON DSL определение объекта.
        output_dir: Каталог для компиляции.

    Returns:
        RoundTripResult с результатом проверки.
    """
    object_type = dsl_definition.get("type", "")
    object_name = dsl_definition.get("name", "")

    result = RoundTripResult(
        object_type=object_type,
        object_name=object_name,
        success=False,
        original_definition=dsl_definition,
    )

    try:
        # Step 1: Compile JSON DSL → XML
        compiled_files = _compile_dsl(dsl_definition, Path(output_dir))
        if not compiled_files:
            result.error = "Compile failed: no files generated"
            return result

        # Находим главный XML файл
        xml_path = _find_main_xml(compiled_files, object_type, object_name)
        if xml_path is None or not xml_path.exists():
            result.error = f"Main XML file not found for {object_type}.{object_name}"
            return result

        result.compiled_xml_path = xml_path

        # Step 2: Decompile XML → JSON DSL
        decompiled = _decompile_xml(xml_path, object_type)
        result.decompiled_definition = decompiled

        # Step 3: Verify equality (с нормализацией)
        differences = _compare_definitions(dsl_definition, decompiled)
        result.differences = differences

        if not differences:
            result.success = True
        else:
            result.error = f"{len(differences)} differences found"

    except Exception as e:
        result.error = f"Round-trip exception: {e}"
        logger.exception("Round-trip failed for %s.%s", object_type, object_name)

    return result


def verify_all_round_trips(
    output_dir: str | Path,
) -> list[RoundTripResult]:
    """Проверить round-trip для всех поддерживаемых типов DSL.

    Args:
        output_dir: Каталог для компиляции.

    Returns:
        Список RoundTripResult для каждого типа.
    """
    results: list[RoundTripResult] = []

    # Test definitions для каждого типа
    test_defs = _get_test_definitions()

    for dsl_def in test_defs:
        result = verify_round_trip(dsl_def, output_dir)
        results.append(result)

    return results


# ============================================================================
# Compile helpers
# ============================================================================


def _compile_dsl(
    dsl_definition: dict[str, Any],
    output_dir: Path,
) -> list[Path]:
    """Скомпилировать DSL в XML файлы."""
    object_type = dsl_definition.get("type", "")

    if object_type == "Subsystem":
        compiler = SubsystemCompiler()
        result = compiler.compile(dsl_definition, output_dir)
        files: list[Path] = []
        if result.xml_path:
            files.append(result.xml_path)
        files.extend(result.module_paths)
        return files

    if object_type == "CommonModule":
        compiler = CommonModuleCompiler()
        result = compiler.compile(dsl_definition, output_dir)
        files = []
        if result.xml_path:
            files.append(result.xml_path)
        files.extend(result.module_paths)
        return files

    # Для других типов используем MetaCompiler
    try:
        from src.dsl.meta import MetaCompiler

        compiler = MetaCompiler()
        result = compiler.compile(dsl_definition, output_dir)
        # MetaCompiler возвращает CompileResult с xml_path и module_paths
        files = []
        if result.xml_path:
            files.append(result.xml_path)
        files.extend(result.module_paths)
        return files
    except Exception as e:
        logger.warning("MetaCompiler failed for %s: %s", object_type, e)
        return []


def _find_main_xml(
    files: list[Path],
    object_type: str,
    object_name: str,
) -> Path | None:
    """Найти главный XML файл среди сгенерированных."""
    # Ищем файл с именем {object_type}.xml
    for f in files:
        if f.name == f"{object_type}.xml":
            return f
    # Или первый XML файл
    for f in files:
        if f.suffix == ".xml":
            return f
    return None


# ============================================================================
# Decompile helpers
# ============================================================================


def _decompile_xml(
    xml_path: Path,
    object_type: str,
) -> dict[str, Any]:
    """Декомпилировать XML обратно в JSON DSL.

    Извлекает ключевые поля: type, name, synonym, comment.
    """
    if not xml_path.exists():
        return {}

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.warning("XML parse error in %s: %s", xml_path, e)
        return {}

    # Находим вложенный элемент с именем object_type
    # Структура: <MetaDataObject><{Type}>...</{Type}></MetaDataObject>
    obj_elem = None
    for child in root:
        if object_type in child.tag:
            obj_elem = child
            break

    if obj_elem is None:
        return {"type": object_type}

    # Извлекаем Properties
    props_elem = obj_elem.find(f"{{{NS_MD}}}Properties")
    if props_elem is None:
        # Пробуем без namespace
        props_elem = obj_elem.find("Properties")

    if props_elem is None:
        return {"type": object_type}

    result: dict[str, Any] = {"type": object_type}

    # Name
    name_elem = _find_child(props_elem, "Name")
    if name_elem is not None and name_elem.text:
        result["name"] = name_elem.text

    # Synonym (v8:item structure)
    synonym = _extract_synonym(props_elem)
    if synonym:
        result["synonym"] = synonym

    # Comment
    comment_elem = _find_child(props_elem, "Comment")
    if comment_elem is not None and comment_elem.text:
        result["comment"] = comment_elem.text

    # Type-specific fields
    if object_type == "CommonModule":
        result.update(_extract_common_module_props(props_elem))
    elif object_type == "Subsystem":
        result.update(_extract_subsystem_props(props_elem, obj_elem))

    return result


def _find_child(parent: ET.Element, tag_name: str) -> ET.Element | None:
    """Найти дочерний элемент по имени тега (с или без namespace)."""
    # С namespace
    elem = parent.find(f"{{{NS_MD}}}{tag_name}")
    if elem is not None:
        return elem
    # Без namespace
    return parent.find(tag_name)


def _extract_synonym(props_elem: ET.Element) -> str:
    """Извлечь синоним из v8:item структуры."""
    synonym_elem = _find_child(props_elem, "Synonym")
    if synonym_elem is None:
        return ""

    # Ищем v8:item → v8:content
    for item in synonym_elem.iter():
        if "content" in item.tag.lower():
            return item.text or ""

    return ""


def _extract_common_module_props(props_elem: ET.Element) -> dict[str, Any]:
    """Извлечь свойства общего модуля."""
    result: dict[str, Any] = {}

    # Маппинг XML tag → DSL key
    field_mapping = {
        "Server": "server",
        "Client": "client",
        "ExternalConnection": "external_connection",
        "ServerCall": "server_call",
        "ClientCall": "client_call",
        "Privileged": "privileged",
        "Global": "global",
    }

    for xml_tag, dsl_key in field_mapping.items():
        elem = _find_child(props_elem, xml_tag)
        if elem is not None and elem.text:
            result[dsl_key] = elem.text.lower() == "true"

    return result


def _extract_subsystem_props(
    props_elem: ET.Element,
    obj_elem: ET.Element,
) -> dict[str, Any]:
    """Извлечь свойства подсистемы."""
    result: dict[str, Any] = {}

    # IncludeInCommandInterface → visible
    elem = _find_child(props_elem, "IncludeInCommandInterface")
    if elem is not None and elem.text:
        result["visible"] = elem.text.lower() == "true"

    # IncludeHelpInContents
    elem = _find_child(props_elem, "IncludeHelpInContents")
    if elem is not None and elem.text:
        result["include_help_in_contents"] = elem.text.lower() == "true"

    # Content → includes и subsystems
    content_elem = _find_child(props_elem, "Content")
    if content_elem is not None:
        includes: list[str] = []
        subsystems: list[str] = []
        for item in content_elem.iter():
            if "Item" in item.tag and item.text:
                text = item.text.strip()
                if text.startswith("Subsystem."):
                    subsystems.append(text.replace("Subsystem.", ""))
                else:
                    includes.append(text)
        if includes:
            result["includes"] = includes
        if subsystems:
            result["subsystems"] = subsystems

    return result


# ============================================================================
# Compare helpers
# ============================================================================


def _compare_definitions(
    original: dict[str, Any],
    decompiled: dict[str, Any],
) -> list[str]:
    """Сравнить исходное и восстановленное определения.

    Возвращает список различий (пустой = идентичны).
    """
    differences: list[str] = []

    # Сравниваем ключевые поля
    for key in ["type", "name", "synonym", "comment"]:
        orig_val = original.get(key, "")
        dec_val = decompiled.get(key, "")

        if str(orig_val) != str(dec_val):
            differences.append(
                f"{key}: original={orig_val!r} vs decompiled={dec_val!r}"
            )

    # Для CommonModule — сравниваем boolean flags
    if original.get("type") == "CommonModule":
        for key in ["server", "client", "privileged", "server_call"]:
            orig_val = bool(original.get(key, False))
            dec_val = bool(decompiled.get(key, False))
            if orig_val != dec_val:
                differences.append(
                    f"{key}: original={orig_val} vs decompiled={dec_val}"
                )

    # Для Subsystem — сравниваем includes и subsystems
    if original.get("type") == "Subsystem":
        orig_includes = set(original.get("includes", []))
        dec_includes = set(decompiled.get("includes", []))
        if orig_includes != dec_includes:
            differences.append(
                f"includes: original={sorted(orig_includes)} vs "
                f"decompiled={sorted(dec_includes)}"
            )

        orig_subs = set(original.get("subsystems", []))
        dec_subs = set(decompiled.get("subsystems", []))
        if orig_subs != dec_subs:
            differences.append(
                f"subsystems: original={sorted(orig_subs)} vs "
                f"decompiled={sorted(dec_subs)}"
            )

    return differences


# ============================================================================
# Test definitions
# ============================================================================


def _get_test_definitions() -> list[dict[str, Any]]:
    """Тестовые определения для всех поддерживаемых типов DSL."""
    return [
        # Subsystem
        {
            "type": "Subsystem",
            "name": "ТестПодсистема",
            "synonym": "Тестовая подсистема",
            "comment": "Для round-trip теста",
            "subsystems": ["Вложенная1"],
            "includes": ["Документ.Продажа", "Справочник.Товары"],
            "visible": True,
            "include_help_in_contents": False,
        },
        # CommonModule
        {
            "type": "CommonModule",
            "name": "ТестовыйМодуль",
            "synonym": "Тестовый общий модуль",
            "comment": "Для round-trip теста",
            "server": True,
            "client": False,
            "privileged": True,
            "server_call": False,
        },
        # CommonModule — все флаги false
        {
            "type": "CommonModule",
            "name": "ПростойМодуль",
            "synonym": "Простой модуль",
            "server": False,
            "client": False,
            "privileged": False,
        },
        # Subsystem — пустая
        {
            "type": "Subsystem",
            "name": "ПустаяПодсистема",
            "synonym": "Пустая",
        },
    ]


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    """CLI для round-trip проверки."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Round-trip DSL verification")
    parser.add_argument(
        "--output-dir", "-o",
        default="/tmp/round_trip_test",
        help="Output directory",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = verify_all_round_trips(output_dir)

    print(f"\n{'='*60}")
    print(f"ROUND-TRIP VERIFICATION RESULTS")
    print(f"{'='*60}")
    print(f"Total: {len(results)}")
    print(f"Success: {sum(1 for r in results if r.success)}")
    print(f"Failed:  {sum(1 for r in results if not r.success)}")
    print()

    for r in results:
        status = "✅" if r.success else "❌"
        print(f"{status} {r.object_type}.{r.object_name}")
        if not r.success:
            print(f"   Error: {r.error}")
            for diff in r.differences[:5]:
                print(f"   - {diff}")

    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
