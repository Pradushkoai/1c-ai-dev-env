"""
CFE Manager — работа с расширениями конфигураций 1С (CFE).

3 операции:
1. borrow_object(extension_path, config_path, object_ref) — заимствовать объект
   из основной конфигурации в расширение (создаёт XML с ObjectBelonging=Adopted)
2. patch_method(extension_path, module_path, method_name, interceptor_type,
   context, is_function) — генерация BSL с декораторами &Перед/&После/
   &ИзменениеИКонтроль
3. diff(extension_path, config_path) — анализ что перенесено в основную конфигурацию

Позаимствовано из 1c-ai-development-kit (skills cfe-borrow, cfe-patch-method, cfe-diff).
"""

from __future__ import annotations
from typing import Any

import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .cfe import BorrowResult, CfeDiffResult, PatchMethodResult  # noqa: F401 — re-export
from .cfe.cli import borrow_object_cli, diff_cli, patch_method_cli  # noqa: F401 — re-export
from .object_types import TYPE_MAP  # noqa: F401 — re-export
from .path_manager import PathManager

# XML namespace 1C
NS_MD = "http://v8.1c.ru/8.3/MDClasses"
NS_XR = "http://v8.1c.ru/8.3/xcf/extprops"

# ============================================================================
# ГЛАВНЫЙ КЛАСС
# ============================================================================


# ============================================================================
# МЕНЕДЖЕР
# ============================================================================


class CfeManager:
    """Управление расширениями конфигураций 1С."""

    def __init__(self, paths: PathManager | None = None):
        self._paths = paths

    # ─────────────────────────────────────────────
    # BORROW — заимствование объекта из конфигурации в расширение
    # ─────────────────────────────────────────────

    def borrow_object(
        self,
        extension_path: Path,
        config_path: Path,
        object_ref: str,
    ) -> BorrowResult:
        """Заимствовать объект из конфигурации в расширение.

        Args:
            extension_path: путь к каталогу расширения (с Configuration.xml)
            config_path: путь к каталогу основной конфигурации
            object_ref: ссылка на объект в формате Type.Name
                       (например, "Catalog.Контрагенты")
                       Поддерживается batch через ";;":
                       "Catalog.Контрагенты;; CommonModule.РаботаСФайлами"

        Returns:
            BorrowResult с путями созданных XML-файлов
        """
        extension_path = Path(extension_path)
        config_path = Path(config_path)

        if not extension_path.exists():
            raise FileNotFoundError(f"Расширение не найдено: {extension_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Конфигурация не найдена: {config_path}")

        # Batch обработка
        refs = [r.strip() for r in object_ref.split(";;") if r.strip()]
        results = []
        for ref in refs:
            result = self._borrow_single(extension_path, config_path, ref)
            results.append(result)

        # Возвращаем объединённый результат (для удобства)
        if len(results) == 1:
            return results[0]
        return BorrowResult(
            object_ref=object_ref,
            object_type="Multiple",
            object_name="Multiple",
            xml_created=[p for r in results for p in r.xml_created],
            registered_in_config=all(r.registered_in_config for r in results),
            warnings=[w for r in results for w in r.warnings],
        )

    def _borrow_single(
        self,
        extension_path: Path,
        config_path: Path,
        object_ref: str,
    ) -> BorrowResult:
        """Заимствовать один объект."""
        # Парсим Type.Name
        if "." not in object_ref:
            raise ValueError(f"Неверный формат object_ref: {object_ref}. Ожидается Type.Name")

        parts = object_ref.split(".", 1)
        object_type, object_name = parts[0], parts[1]

        if object_type not in TYPE_MAP:
            raise ValueError(f"Неподдерживаемый тип объекта: {object_type}. Поддерживается {len(TYPE_MAP)} типов.")

        type_info = TYPE_MAP[object_type]
        result = BorrowResult(
            object_ref=object_ref,
            object_type=object_type,
            object_name=object_name,
        )

        # 1. Проверяем что объект есть в основной конфигурации
        source_dir = config_path / type_info["dir"] / object_name
        source_xml = config_path / type_info["dir"] / f"{object_name}.xml"
        if not source_dir.exists() and not source_xml.exists():
            result.warnings.append(f"Объект {object_ref} не найден в конфигурации {config_path}")
            # Продолжаем — всё равно создаём заглушку в расширении

        # 2. Читаем UUID объекта из источника (если есть)
        source_uuid = self._read_object_uuid(source_xml) if source_xml.exists() else str(uuid.uuid4())

        # 3. Читаем NamePrefix из Configuration.xml расширения
        ext_config_xml = extension_path / "Configuration.xml"
        if not ext_config_xml.exists():
            raise FileNotFoundError(f"Configuration.xml расширения не найден: {ext_config_xml}")

        name_prefix = self._read_name_prefix(ext_config_xml)

        # 4. Создаём каталог объекта в расширении
        ext_obj_dir = extension_path / type_info["dir"] / object_name
        ext_obj_dir.mkdir(parents=True, exist_ok=True)

        # 5. Создаём XML объекта с ObjectBelonging=Adopted
        obj_xml_path = extension_path / type_info["dir"] / f"{object_name}.xml"
        self._write_borrowed_xml(
            obj_xml_path,
            object_type=type_info["xml_tag"],
            object_name=object_name,
            source_uuid=source_uuid,
            name_prefix=name_prefix,
        )
        result.xml_created.append(obj_xml_path)

        # 6. Регистрируем в Configuration.xml расширения (в ChildObjects)
        registered = self._register_in_config(ext_config_xml, object_type, object_name)
        result.registered_in_config = registered

        return result

    @staticmethod
    def _read_object_uuid(xml_path: Path) -> str:
        """Прочитать UUID объекта из его XML."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            # <xr:TypeId>...</xr:TypeId> или атрибут uuid
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag in ("TypeId", "uuid", "id"):
                    return elem.text or str(uuid.uuid4())
        except ET.ParseError:
            pass
        return str(uuid.uuid4())

    @staticmethod
    def _read_name_prefix(config_xml: Path) -> str:
        """Прочитать NamePrefix из Configuration.xml расширения."""
        try:
            tree = ET.parse(config_xml)
            root = tree.getroot()
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "NamePrefix":
                    return elem.text or ""
        except ET.ParseError:
            pass
        return ""

    @staticmethod
    def _write_borrowed_xml(
        out_path: Path,
        object_type: str,
        object_name: str,
        source_uuid: str,
        name_prefix: str,
    ) -> None:
        """Записать XML заимствованного объекта с ObjectBelonging=Adopted."""
        # Регистрируем namespace
        for prefix, uri in [("xr", NS_XR), ("md", NS_MD)]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_MD}}}{object_type}")
        root.set("uuid", source_uuid)
        root.set("name", object_name)

        # <Properties>
        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")
        name = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name.text = object_name

        syn = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn, "{http://v8.1c.ru/8.1/data/core}item")
        content = ET.SubElement(item, "{http://v8.1c.ru/8.1/data/core}content")
        content.text = object_name

        # ObjectBelonging = Adopted (ключевой атрибут расширения)
        belonging = ET.SubElement(props, f"{{{NS_XR}}}ObjectBelonging")
        belonging.text = "Adopted"

        if name_prefix:
            prefix_elem = ET.SubElement(props, f"{{{NS_XR}}}NamePrefix")
            prefix_elem.text = name_prefix

        # <ChildObjects> — пустой (заимствуем без изменений)
        ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")

        tree = ET.ElementTree(root)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _register_in_config(config_xml: Path, object_type: str, object_name: str) -> bool:
        """Добавить запись в <ChildObjects> Configuration.xml расширения."""
        try:
            tree = ET.parse(config_xml)
            root = tree.getroot()
            type_info = TYPE_MAP.get(object_type)
            if not type_info:
                return False

            # Ищем <ChildObjects>
            child_objects = None
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "ChildObjects":
                    child_objects = elem
                    break

            if child_objects is None:
                child_objects = ET.SubElement(root, f"{{{NS_MD}}}ChildObjects")

            # Проверяем — не зарегистрирован ли уже
            xml_tag = type_info["xml_tag"]
            for child in child_objects:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == xml_tag and child.text == object_name:
                    return True  # уже зарегистрирован

            # Добавляем <Type>Name</Type>
            new_elem = ET.SubElement(child_objects, f"{{{NS_MD}}}{xml_tag}")
            new_elem.text = object_name

            tree.write(config_xml, encoding="utf-8", xml_declaration=True)
            return True
        except (ET.ParseError, OSError):
            return False

    # ─────────────────────────────────────────────
    # PATCH_METHOD — генерация BSL с декораторами перехвата
    # ─────────────────────────────────────────────

    def patch_method(
        self,
        extension_path: Path,
        module_path: str,
        method_name: str,
        interceptor_type: str,
        context: str = "НаСервере",
        is_function: bool = False,
    ) -> PatchMethodResult:
        """Сгенерировать BSL-файл с декоратором перехвата метода.

        Args:
            extension_path: путь к расширению
            module_path: путь к модулю в формате Catalog.X.ObjectModule
            method_name: имя перехватываемого метода (например, "ПриЗаписи")
            interceptor_type: Before | After | ModificationAndControl
            context: директива контекста (НаСервере, НаКлиенте, etc.)
            is_function: True если метод — функция (добавит Возврат)

        Returns:
            PatchMethodResult с путём к созданному .bsl файлу
        """
        # Нормализуем регистр, сохраняя CamelCase для ModificationAndControl
        type_map_norm = {
            "before": "Before",
            "after": "After",
            "modificationandcontrol": "ModificationAndControl",
            "modification_and_control": "ModificationAndControl",
        }
        normalized = type_map_norm.get(interceptor_type.lower().replace("_", ""), interceptor_type)
        interceptor_type = normalized
        if interceptor_type not in ("Before", "After", "ModificationAndControl"):
            raise ValueError(
                f"Неверный interceptor_type: {interceptor_type}. Ожидается: Before, After, ModificationAndControl"
            )

        # Разбор module_path → относительный путь к .bsl файлу
        bsl_rel_path = self._resolve_module_path(module_path)
        extension_path = Path(extension_path)

        # Читаем NamePrefix для формирования имени процедуры
        ext_config_xml = extension_path / "Configuration.xml"
        name_prefix = ""
        if ext_config_xml.exists():
            name_prefix = self._read_name_prefix(ext_config_xml)

        # Формируем имя процедуры с префиксом расширения
        procedure_name = f"{name_prefix}{method_name}" if name_prefix else method_name

        # Генерируем BSL
        bsl_content = self._generate_patch_bsl(
            procedure_name=procedure_name,
            method_name=method_name,
            interceptor_type=interceptor_type,
            context=context,
            is_function=is_function,
        )

        # Полный путь к файлу
        bsl_file = extension_path / bsl_rel_path
        bsl_file.parent.mkdir(parents=True, exist_ok=True)
        bsl_file.write_text(bsl_content, encoding="utf-8")

        return PatchMethodResult(
            module_path=module_path,
            method_name=method_name,
            interceptor_type=interceptor_type,
            bsl_file=bsl_file,
            bsl_content=bsl_content,
        )

    @staticmethod
    def _resolve_module_path(module_path: str) -> str:
        """Преобразовать Catalog.X.ObjectModule → Catalogs/X/Ext/ObjectModule.bsl."""
        parts = module_path.split(".")
        if len(parts) < 2:
            raise ValueError(f"Неверный module_path: {module_path}")

        object_type = parts[0]
        object_name = parts[1]

        if object_type not in TYPE_MAP:
            raise ValueError(f"Неподдерживаемый тип: {object_type}")

        type_info = TYPE_MAP[object_type]
        dir_name = type_info["dir"]

        # Catalog.X.ObjectModule → Catalogs/X/Ext/ObjectModule.bsl
        # Catalog.X.ManagerModule → Catalogs/X/Ext/ManagerModule.bsl
        # Catalog.X.Form.Y → Catalogs/X/Forms/Y/Ext/Form/Module.bsl
        # CommonModule.X → CommonModules/X/Ext/Module.bsl

        if len(parts) == 2:
            # CommonModule.X → CommonModules/X/Ext/Module.bsl
            return f"{dir_name}/{object_name}/Ext/Module.bsl"

        module_type = parts[2]  # ObjectModule, ManagerModule, Form, etc.

        if module_type == "Form":
            if len(parts) < 4:
                raise ValueError(f"Form module_path требует имя формы: {module_path}")
            form_name = parts[3]
            return f"{dir_name}/{object_name}/Forms/{form_name}/Ext/Form/Module.bsl"
        else:
            # ObjectModule, ManagerModule, RecordSetModule, etc.
            return f"{dir_name}/{object_name}/Ext/{module_type}.bsl"

    @staticmethod
    def _generate_patch_bsl(
        procedure_name: str,
        method_name: str,
        interceptor_type: str,
        context: str,
        is_function: bool,
    ) -> str:
        """Сгенерировать BSL-код перехватчика."""
        decorator_map = {
            "Before": "&Перед",
            "After": "&После",
            "ModificationAndControl": "&ИзменениеИКонтроль",
        }
        decorator = decorator_map[interceptor_type]

        keyword = "Функция" if is_function else "Процедура"
        end_keyword = "Возврат" if is_function else ""
        end_block = "КонецФункции" if is_function else "КонецПроцедуры"

        lines = [
            f"// Перехватчик: {method_name} ({interceptor_type})",
            "// Сгенерировано CfeManager",
            "",
            f"{decorator}",
            f"{keyword} {procedure_name}()",
            "",
        ]

        if interceptor_type == "Before":
            lines.append("\t// TODO: Код ДО вызова оригинального метода")
            lines.append("\t")
            lines.append("\t// Вызов оригинального метода (вызывается автоматически)")
        elif interceptor_type == "After":
            lines.append("\t// Оригинальный метод уже выполнен")
            lines.append("\t")
            lines.append("\t// TODO: Код ПОСЛЕ вызова оригинального метода")
        elif interceptor_type == "ModificationAndControl":
            lines.append("\t// Копия тела оригинального метода с маркерами изменений")
            lines.append("\t")
            lines.append("\t// TODO: Раскомментируй и вставь свой код внутри маркеров")
            lines.append("\t// #Вставка")
            lines.append("\t//     <твой код>")
            lines.append("\t// #КонецВставки")
            lines.append("\t")
            lines.append("\t// TODO: Раскомментируй для удаления строк оригинала")
            lines.append("\t// #Удаление")
            lines.append("\t//     <строки для удаления>")
            lines.append("\t// #КонецУдаления")

        lines.append("")

        if end_keyword:
            lines.append(f"\t{end_keyword} Неопределено;")

        lines.append(end_block)
        lines.append("")

        # Добавляем директиву контекста комментарием
        if context:
            lines.insert(0, f"// Контекст: {context}")
            lines.insert(1, "")

        return "\n".join(lines)

    # ─────────────────────────────────────────────
    # DIFF — анализ что перенесено в основную конфигурацию
    # ─────────────────────────────────────────────

    def diff(
        self,
        extension_path: Path,
        config_path: Path,
    ) -> CfeDiffResult:
        """Анализ расширения: что заимствовано, какие методы перехвачены.

        Args:
            extension_path: путь к расширению
            config_path: путь к основной конфигурации

        Returns:
            CfeDiffResult со списками borrowed_objects, patch_methods, not_in_config
        """
        extension_path = Path(extension_path)
        config_path = Path(config_path)

        result = CfeDiffResult(
            extension_path=extension_path,
            config_path=config_path,
        )

        if not extension_path.exists():
            result.warnings.append(f"Расширение не найдено: {extension_path}")
            return result

        # 1. Сканируем объекты в расширении (по директориям)
        for object_type, type_info in TYPE_MAP.items():
            type_dir = extension_path / type_info["dir"]
            if not type_dir.exists():
                continue

            # Ищем .xml файлы объектов
            for xml_file in type_dir.glob("*.xml"):
                if xml_file.name == "Configuration.xml":
                    continue
                obj_name = xml_file.stem
                borrowed = self._analyze_borrowed_object(xml_file, object_type, obj_name, config_path)
                if borrowed:
                    result.borrowed_objects.append(borrowed)
                    if not borrowed.get("found_in_config"):
                        result.not_in_config.append(f"{object_type}.{obj_name}")

        # 2. Сканируем .bsl файлы на наличие декораторов перехвата
        for bsl_file in extension_path.rglob("*.bsl"):
            patches = self._find_patch_methods_in_bsl(bsl_file, extension_path)
            result.patch_methods.extend(patches)

        return result

    def _analyze_borrowed_object(
        self,
        xml_file: Path,
        object_type: str,
        object_name: str,
        config_path: Path,
    ) -> dict[str, Any] | None:
        """Проанализировать XML заимствованного объекта."""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            info = {
                "object_ref": f"{object_type}.{object_name}",
                "object_type": object_type,
                "object_name": object_name,
                "object_belonging": "Adopted",  # по умолчанию
                "has_modifications": False,
                "found_in_config": False,
                "xml_path": str(xml_file),
            }

            # Читаем ObjectBelonging
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "ObjectBelonging":
                    info["object_belonging"] = elem.text or "Adopted"

            # Проверяем есть ли в ChildObjects что-то кроме пустых тегов
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "ChildObjects":
                    children = list(elem)
                    if children:
                        info["has_modifications"] = True
                    break

            # Проверяем что объект есть в основной конфигурации
            type_info = TYPE_MAP.get(object_type, {})
            config_dir_name = type_info.get("dir", "")
            if config_dir_name:
                config_obj_dir = config_path / config_dir_name / object_name
                config_obj_xml = config_path / config_dir_name / f"{object_name}.xml"
                info["found_in_config"] = config_obj_dir.exists() or config_obj_xml.exists()

            return info
        except ET.ParseError:
            return None

    def _find_patch_methods_in_bsl(
        self,
        bsl_file: Path,
        extension_path: Path,
    ) -> list[dict]:
        """Найти декораторы перехвата (&Перед, &После, &ИзменениеИКонтроль) в BSL."""
        patches: list[dict] = []
        try:
            content = bsl_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return patches

        # Разбор module_path из пути файла
        try:
            rel_path = bsl_file.relative_to(extension_path)
            module_path = self._path_to_module_path(rel_path)
        except ValueError:
            module_path = str(bsl_file)

        # Регэксп для декораторов
        re.compile(r"^(&Перед|&После|&ИзменениеИКонтроль)\s*$", re.MULTILINE)

        # Процедура/Функция
        proc_re = re.compile(r"^(Процедура|Функция)\s+(\w+)\s*\(", re.MULTILINE)

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line in ("&Перед", "&После", "&ИзменениеИКонтроль"):
                # Ищем следующую Процедура/Функция
                for j in range(i + 1, min(i + 5, len(lines))):
                    proc_match = proc_re.match(lines[j].strip())
                    if proc_match:
                        method_kind = proc_match.group(1)
                        method_name = proc_match.group(2)
                        interceptor_map = {
                            "&Перед": "Before",
                            "&После": "After",
                            "&ИзменениеИКонтроль": "ModificationAndControl",
                        }
                        patches.append(
                            {
                                "module_path": module_path,
                                "method_name": method_name,
                                "interceptor_type": interceptor_map[line],
                                "is_function": method_kind == "Функция",
                                "bsl_file": str(bsl_file),
                                "line": i + 1,
                            }
                        )
                        break
            i += 1

        return patches

    @staticmethod
    def _path_to_module_path(rel_path: Path) -> str:
        """Преобразовать относительный путь BSL обратно в module_path.

        Catalogs/X/Ext/ObjectModule.bsl → Catalog.X.ObjectModule
        CommonModules/X/Ext/Module.bsl → CommonModule.X
        Catalogs/X/Forms/Y/Ext/Form/Module.bsl → Catalog.X.Form.Y
        """
        parts = rel_path.parts
        if len(parts) < 2:
            return str(rel_path)

        # Находим тип объекта по директории
        dir_name = parts[0]
        object_type = None
        for t, info in TYPE_MAP.items():
            if info["dir"] == dir_name:
                object_type = t
                break

        if not object_type:
            return str(rel_path)

        object_name = parts[1]

        # Catalogs/X/Ext/ObjectModule.bsl
        if len(parts) == 4 and parts[2] == "Ext":
            module_type = parts[3].replace(".bsl", "")
            if module_type == "Module" and object_type == "CommonModule":
                return f"{object_type}.{object_name}"
            return f"{object_type}.{object_name}.{module_type}"

        # Catalogs/X/Forms/Y/Ext/Form/Module.bsl
        if len(parts) == 7 and parts[2] == "Forms" and parts[4] == "Ext" and parts[5] == "Form":
            form_name = parts[3]
            return f"{object_type}.{object_name}.Form.{form_name}"

        return str(rel_path)


# CLI helpers вынесены в src/services/cfe/cli.py (Этап 2.5)
# Re-export: from .cfe.cli import borrow_object_cli, patch_method_cli, diff_cli
# (см. импорт в начале файла)
