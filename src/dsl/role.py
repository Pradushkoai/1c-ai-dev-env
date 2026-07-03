"""role — компилятор JSON DSL → XML для ролей 1С (Rights.xml)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    NS_MD,
    NS_V8,
    NS_XR,
    CompileResult,
    _gen_uuid,
)

# Русские синонимы типов объектов для ролей
RU_OBJECT_TYPE_SYNONYMS: dict[str, str] = {
    "Справочник": "Catalog",
    "Документ": "Document",
    "Перечисление": "Enum",
    "Константа": "Constant",
    "РегистрСведений": "InformationRegister",
    "РегистрНакопления": "AccumulationRegister",
    "РегистрБухгалтерии": "AccountingRegister",
    "РегистрРасчёта": "CalculationRegister",
    "РегистрРасчета": "CalculationRegister",
    "ПланСчетов": "ChartOfAccounts",
    "ПланВидовХарактеристик": "ChartOfCharacteristicTypes",
    "ПланВидовРасчёта": "ChartOfCalculationTypes",
    "ПланВидовРасчета": "ChartOfCalculationTypes",
    "Обработка": "DataProcessor",
    "Отчёт": "Report",
    "Отчет": "Report",
    "ОбщийМодуль": "CommonModule",
}

# Русские синонимы прав
RU_RIGHT_SYNONYMS: dict[str, str] = {
    "Чтение": "Read",
    "Просмотр": "View",
    "Добавление": "Insert",
    "Изменение": "Update",
    "Удаление": "Delete",
    "Проведение": "Posting",
    "ОтменаПроведения": "Unposting",
    "ВводПоСтроке": "InputByString",
    "Использование": "Use",
    "ИнтерактивноеДобавление": "InteractiveInsert",
    "ИнтерактивноеИзменение": "InteractiveUpdate",
    "ИнтерактивноеУдаление": "InteractiveDelete",
    "ИнтерактивноеПроведение": "InteractivePosting",
    "ИнтерактивнаяОтменаПроведения": "InteractiveUnposting",
    "ИнтерактивныйВводПоСтроке": "InteractiveInputByString",
    "ЧтениеВОП": "ReadMain",
    "ИзменениеВОП": "UpdateMain",
}

# Пресеты прав (базовые наборы)
RIGHTS_PRESETS: dict[str, dict[str, list[str]]] = {
    "view": {
        "Catalog": ["Read", "View", "InputByString"],
        "Document": ["Read", "View", "InputByString"],
        "InformationRegister": ["Read", "View"],
        "AccumulationRegister": ["Read", "View"],
        "Constant": ["Read"],
        "Enum": ["Read", "View"],
        "DataProcessor": ["Use", "View"],
        "Report": ["Use", "View"],
        "CommonModule": ["Use"],
        "_default": ["Read", "View"],
    },
    "edit": {
        "Catalog": [
            "Read",
            "View",
            "Insert",
            "Update",
            "Delete",
            "InputByString",
            "InteractiveInsert",
            "InteractiveUpdate",
            "InteractiveDelete",
            "InteractiveInputByString",
        ],
        "Document": [
            "Read",
            "View",
            "Insert",
            "Update",
            "Delete",
            "Posting",
            "Unposting",
            "InputByString",
            "InteractiveInsert",
            "InteractiveUpdate",
            "InteractiveDelete",
            "InteractivePosting",
            "InteractiveUnposting",
            "InteractiveInputByString",
        ],
        "InformationRegister": [
            "Read",
            "View",
            "Insert",
            "Update",
            "Delete",
            "InteractiveInsert",
            "InteractiveUpdate",
            "InteractiveDelete",
        ],
        "AccumulationRegister": ["Read", "View"],
        "Constant": ["Read", "Update"],
        "Enum": ["Read", "View"],
        "DataProcessor": ["Use", "View"],
        "Report": ["Use", "View"],
        "CommonModule": ["Use"],
        "_default": ["Read", "View", "Insert", "Update", "Delete"],
    },
}


class RoleCompiler:
    """Компилятор JSON DSL → Rights.xml для ролей 1С.

    Поддерживает: objects с правами, пресеты (view/edit), RLS шаблоны,
    русские синонимы типов и прав.
    """

    def compile(
        self,
        definition: str | dict | Path,
        output_dir: str | Path,
    ) -> CompileResult:
        """Скомпилировать JSON DSL → Rights.xml + метаданные роли.

        Args:
            definition: JSON-определение роли
            output_dir: каталог Roles/ в исходниках конфигурации
        """
        if isinstance(definition, (str, Path)):
            def_path = Path(definition)
            if def_path.exists():
                import json as _json

                with open(def_path, encoding="utf-8") as f:
                    def_dict = _json.load(f)
            else:
                import json as _json

                def_dict = _json.loads(str(definition))
        elif isinstance(definition, dict):
            def_dict = definition
        else:
            raise ValueError(f"Неверный тип definition: {type(definition)}")

        role_name = def_dict.get("name", "")
        if not role_name:
            raise ValueError("Имя роли не указано (поле 'name')")

        result = CompileResult(
            object_type="Role",
            object_name=role_name,
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Создаём метаданные роли: Roles/<Name>.xml
        meta_path = output_dir / f"{role_name}.xml"
        self._write_role_metadata(meta_path, role_name, def_dict)
        result.xml_path = meta_path

        # 2. Создаём Rights.xml: Roles/<Name>/Ext/Rights.xml
        rights_dir = output_dir / role_name / "Ext"
        rights_dir.mkdir(parents=True, exist_ok=True)
        rights_path = rights_dir / "Rights.xml"
        self._write_rights_xml(rights_path, def_dict)
        result.module_paths = [rights_path]

        return result

    def _write_role_metadata(self, meta_path: Path, role_name: str, def_dict: dict) -> None:
        """Записать метаданные роли (Roles/<Name>.xml)."""
        for prefix, uri in [("md", NS_MD), ("xr", NS_XR), ("v8", NS_V8)]:
            ET.register_namespace(prefix, uri)

        root = ET.Element(f"{{{NS_MD}}}Role")
        root.set("uuid", _gen_uuid())
        root.set("name", role_name)

        props = ET.SubElement(root, f"{{{NS_MD}}}Properties")
        name_elem = ET.SubElement(props, f"{{{NS_XR}}}Name")
        name_elem.text = role_name

        synonym = def_dict.get("synonym", role_name)
        syn_elem = ET.SubElement(props, f"{{{NS_XR}}}Synonym")
        item = ET.SubElement(syn_elem, f"{{{NS_V8}}}item")
        content = ET.SubElement(item, f"{{{NS_V8}}}content")
        content.text = synonym

        if def_dict.get("comment"):
            c = ET.SubElement(props, f"{{{NS_XR}}}Comment")
            c.text = def_dict["comment"]

        # SetForNewObjects
        if "setForNewObjects" in def_dict:
            sfno = ET.SubElement(props, f"{{{NS_XR}}}SetForNewObjects")
            sfno.text = "true" if def_dict["setForNewObjects"] else "false"

        # SetForAttributesByDefault
        sfabd = ET.SubElement(props, f"{{{NS_XR}}}SetForAttributesByDefault")
        sfabd.text = "true" if def_dict.get("setForAttributesByDefault", True) else "false"

        tree = ET.ElementTree(root)
        tree.write(meta_path, encoding="utf-8", xml_declaration=True)

    def _write_rights_xml(self, rights_path: Path, def_dict: dict) -> None:
        """Записать Rights.xml с правами на объекты.

        Формат: реальный 1C Rights.xml (version 2.18):
        <Rights xmlns="http://v8.1c.ru/8.2/roles">
          <setForNewObjects>false</setForNewObjects>
          <object>
            <name>Catalog.Номенклатура</name>
            <right>
              <name>Read</name>
              <value>true</value>
            </right>
          </object>
        </Rights>
        """
        NS_RIGHTS_REAL = "http://v8.1c.ru/8.2/roles"
        ET.register_namespace("", NS_RIGHTS_REAL)

        root = ET.Element(f"{{{NS_RIGHTS_REAL}}}Rights")
        root.set("{http://www.w3.org/2001/XMLSchema-instance}type", "Rights")

        # SetForNewObjects, SetForAttributesByDefault
        sfno = ET.SubElement(root, f"{{{NS_RIGHTS_REAL}}}setForNewObjects")
        sfno.text = "true" if def_dict.get("setForNewObjects") else "false"
        sfabd = ET.SubElement(root, f"{{{NS_RIGHTS_REAL}}}setForAttributesByDefault")
        sfabd.text = "true" if def_dict.get("setForAttributesByDefault", True) else "false"
        iroco = ET.SubElement(root, f"{{{NS_RIGHTS_REAL}}}independentRightsOfChildObjects")
        iroco.text = "true" if def_dict.get("independentRightsOfChildObjects") else "false"

        # Objects
        for obj_def in def_dict.get("objects", []):
            self._write_object_rights(root, obj_def, NS_RIGHTS_REAL)

        # Templates (RLS)
        for tmpl_def in def_dict.get("templates", []):
            tmpl_elem = ET.SubElement(root, f"{{{NS_RIGHTS_REAL}}}template")
            tmpl_name = ET.SubElement(tmpl_elem, f"{{{NS_RIGHTS_REAL}}}name")
            tmpl_name.text = tmpl_def.get("name", "")
            condition = tmpl_def.get("condition", "")
            cond_elem = ET.SubElement(tmpl_elem, f"{{{NS_RIGHTS_REAL}}}condition")
            # Экранируем & → &amp; только один раз (ET делает это сам)
            cond_elem.text = condition

        tree = ET.ElementTree(root)
        tree.write(rights_path, encoding="utf-8", xml_declaration=True)

    def _write_object_rights(self, parent: ET.Element, obj_def: dict | str, ns: str) -> None:
        """Записать права на один объект в реальном формате 1C."""
        if isinstance(obj_def, str):
            parsed = self._parse_object_shorthand(obj_def)
        elif isinstance(obj_def, dict):
            parsed = obj_def
        else:
            return

        object_name = parsed.get("name", "")
        if not object_name or "." not in object_name:
            return

        # Разделяем Type.Name
        type_str, name = object_name.split(".", 1)
        type_en = RU_OBJECT_TYPE_SYNONYMS.get(type_str, type_str)

        obj_elem = ET.SubElement(parent, f"{{{ns}}}object")

        # name как child element (не атрибут!)
        name_elem = ET.SubElement(obj_elem, f"{{{ns}}}name")
        name_elem.text = f"{type_en}.{name}"

        # Определяем набор прав
        rights_set: set[str] = set()

        preset = parsed.get("preset")
        if preset and preset in RIGHTS_PRESETS:
            preset_rights = RIGHTS_PRESETS[preset].get(type_en) or RIGHTS_PRESETS[preset].get("_default", [])
            rights_set.update(preset_rights)

        explicit_rights = parsed.get("rights", [])
        if isinstance(explicit_rights, dict):
            for right, val in explicit_rights.items():
                right_en = RU_RIGHT_SYNONYMS.get(right, right)
                if val:
                    rights_set.add(right_en)
                else:
                    rights_set.discard(right_en)
        elif isinstance(explicit_rights, list):
            for right in explicit_rights:
                right_en = RU_RIGHT_SYNONYMS.get(right, right)
                rights_set.add(right_en)

        # Записываем права в реальном формате: <right><name>Read</name><value>true</value></right>
        for right in sorted(rights_set):
            right_elem = ET.SubElement(obj_elem, f"{{{ns}}}right")
            r_name = ET.SubElement(right_elem, f"{{{ns}}}name")
            r_name.text = right
            r_value = ET.SubElement(right_elem, f"{{{ns}}}value")
            r_value.text = "true"

        # RLS
        rls = parsed.get("rls", {})
        if rls:
            for right_name, condition in rls.items():
                right_en = RU_RIGHT_SYNONYMS.get(right_name, right_name)
                right_elem = ET.SubElement(obj_elem, f"{{{ns}}}right")
                r_name = ET.SubElement(right_elem, f"{{{ns}}}name")
                r_name.text = right_en
                r_value = ET.SubElement(right_elem, f"{{{ns}}}value")
                r_value.text = "true"
                rls_elem = ET.SubElement(right_elem, f"{{{ns}}}restriction")
                rls_elem.text = condition  # ET сам экранирует &

    def _parse_object_shorthand(self, shorthand: str) -> dict:
        """Парсит 'Тип.Имя: @пресет' или 'Тип.Имя: Право1, Право2'."""
        if ":" in shorthand:
            obj_part, rights_part = shorthand.split(":", 1)
            obj_part = obj_part.strip()
            rights_part = rights_part.strip()
        else:
            return {"name": shorthand.strip()}

        if rights_part.startswith("@"):
            return {"name": obj_part, "preset": rights_part[1:]}
        elif rights_part:
            rights = [r.strip() for r in rights_part.split(",")]
            return {"name": obj_part, "rights": rights}
        return {"name": obj_part}


# _write_rls_template удалён — интегрирован в _write_rights_xml


# ============================================================================
# Расширяем DslCompiler фасад
# ============================================================================


# Переписываем DslCompiler чтобы включить все 5 компиляторов
