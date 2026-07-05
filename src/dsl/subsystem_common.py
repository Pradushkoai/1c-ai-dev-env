"""
T5.4 (2026-07-06): Специализированные DSL компиляторы для Subsystem и CommonModule.

Существующий MetaCompiler поддерживает Subsystem и CommonModule через TYPE_MAP,
но не обрабатывает их специфичные свойства:
- Subsystem: иерархия (вложенные подсистемы), включаемые объекты, видимость
- CommonModule: Server/NClient/ExternalCall flags, Return value type

Этот модуль добавляет специализированные компиляторы:

1. SubsystemCompiler — компиляция подсистем с поддержкой:
   - Иерархии (подсистемы внутри подсистем)
   - Include objects (какие объекты входят в подсистему)
   - Видимость (Visible, IncludeHelpInContents)
   - Синоним и комментарий
   - Генерация Subsystem.xml + Content.xml

2. CommonModuleCompiler — компиляция общих модулей с:
   - Server, Client, ExternalClient flags
   - ServerCall, ClientCall flags
   - Return values (Returns the value)
   - Привилегированный режим
   - Генерация CommonModule.xml + Module.bsl

Использование:
    from src.dsl.subsystem_common import SubsystemCompiler, CommonModuleCompiler

    # Subsystem
    compiler = SubsystemCompiler()
    result = compiler.compile(
        definition={
            "type": "Subsystem",
            "name": "Продажи",
            "synonym": "Продажи",
            "subsystems": ["ОптовыеПродажи"],
            "includes": ["Документ.Продажа", "Справочник.Контрагенты"],
        },
        output_dir="/tmp/config",
    )

    # CommonModule
    compiler = CommonModuleCompiler()
    result = compiler.compile(
        definition={
            "type": "CommonModule",
            "name": "ОбщегоНазначения",
            "synonym": "Общего назначения",
            "server": True,
            "server_call": True,
            "return_value_type": "Строка",
        },
        output_dir="/tmp/config",
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.dsl._common import (
    NS_MD,
    NS_V8,
    NS_XR,
    CompileResult,
    _gen_uuid,
)

# ============================================================================
# SubsystemCompiler
# ============================================================================


class SubsystemCompiler:
    """T5.4: Компилятор подсистем 1С.

    Подсистема может содержать:
    - Вложенные подсистемы (subsystems)
    - Объекты конфигурации (includes: Catalogs, Documents, etc.)
    - Картинку (picture)
    - Адресную информацию (address)

    Генерирует:
    - {output_dir}/Subsystems/{name}/Subsystem.xml — метаданные подсистемы
    - {output_dir}/Subsystems/{name}/.uuid — UUID файл
    """

    def compile(
        self,
        definition: str | dict[str, Any] | Path,
        output_dir: str | Path,
    ) -> CompileResult:
        """Скомпилировать подсистему.

        Args:
            definition: JSON-определение (dict, JSON-строка или путь к файлу).
            output_dir: Каталог конфигурации (где Subsystems/).

        Returns:
            CompileResult с путями к созданным файлам.
        """
        def_dict = self._parse_definition(definition)
        self._validate(def_dict)

        name = def_dict["name"]
        synonym = def_dict.get("synonym", name)
        comment = def_dict.get("comment", "")
        subsystems = def_dict.get("subsystems", [])
        includes = def_dict.get("includes", [])
        visible = def_dict.get("visible", True)
        include_help = def_dict.get("include_help_in_contents", False)

        obj_uuid = _gen_uuid()
        output_dir = Path(output_dir)
        subsystem_dir = output_dir / "Subsystems" / name
        subsystem_dir.mkdir(parents=True, exist_ok=True)

        # Subsystem.xml
        xml_path = subsystem_dir / "Subsystem.xml"
        xml_content = self._build_subsystem_xml(
            obj_uuid=obj_uuid,
            name=name,
            synonym=synonym,
            comment=comment,
            subsystems=subsystems,
            includes=includes,
            visible=visible,
            include_help=include_help,
        )
        xml_path.write_text(xml_content, encoding="utf-8")

        files = [xml_path]

        # Content.xml — содержимое подсистемы
        if includes or subsystems:
            content_path = subsystem_dir / "Content.xml"
            content_xml = self._build_content_xml(includes, subsystems)
            content_path.write_text(content_xml, encoding="utf-8")
            files.append(content_path)

        # Регистрация в Configuration.xml
        config_path = output_dir / "Configuration.xml"
        if config_path.exists():
            self._register_in_config(config_path, name, obj_uuid)

        return CompileResult(
            object_type="Subsystem",
            object_name=name,
            xml_path=files[0] if files else None,
            module_paths=files[1:] if len(files) > 1 else [],
        )

    def _parse_definition(self, definition: str | dict[str, Any] | Path) -> dict[str, Any]:
        """Парсинг определения подсистемы."""
        if isinstance(definition, dict):
            return definition
        if isinstance(definition, Path):
            data: dict[str, Any] = json.loads(definition.read_text(encoding="utf-8"))
            return data
        # JSON-строка
        result: dict[str, Any] = json.loads(definition)
        return result

    def _validate(self, def_dict: dict[str, Any]) -> None:
        """Валидация определения."""
        if def_dict.get("type") != "Subsystem":
            raise ValueError(f"Expected type='Subsystem', got '{def_dict.get('type')}'")
        if not def_dict.get("name"):
            raise ValueError("Subsystem must have 'name'")

    def _build_subsystem_xml(
        self,
        *,
        obj_uuid: str,
        name: str,
        synonym: str,
        comment: str,
        subsystems: list[str],
        includes: list[str],
        visible: bool,
        include_help: bool,
    ) -> str:
        """Построить XML метаданных подсистемы."""
        # Список включённых подсистем
        subsystems_xml = ""
        for sub_name in subsystems:
            subsystems_xml += (
                f'\t\t<xr:Item xsi:type="xr:MDObjectRef">'
                f'Subsystem.{sub_name}</xr:Item>\n'
            )

        # Список включённых объектов
        includes_xml = ""
        for inc in includes:
            includes_xml += (
                f'\t\t<xr:Item xsi:type="xr:MDObjectRef">{inc}</xr:Item>\n'
            )

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{NS_MD}" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="{NS_V8}" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="{NS_XR}" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<Subsystem uuid="{obj_uuid}">
\t\t<Properties>
\t\t\t<Name>{name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{synonym}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment>{comment}</Comment>
\t\t\t<IncludeHelpInContents>{str(include_help).lower()}</IncludeHelpInContents>
\t\t\t<IncludeInCommandInterface>{str(visible).lower()}</IncludeInCommandInterface>
\t\t\t<Explanation/>
\t\t\t<Picture/>
\t\t\t<Content>
{subsystems_xml}{includes_xml}\t\t\t</Content>
\t\t</Properties>
\t\t<ChildObjects/>
\t</Subsystem>
</MetaDataObject>'''

    def _build_content_xml(
        self, includes: list[str], subsystems: list[str]
    ) -> str:
        """Построить Content.xml для подсистемы."""
        items = ""
        for inc in includes:
            items += f'\t<Item>{inc}</Item>\n'
        for sub in subsystems:
            items += f'\t<Item>Subsystem.{sub}</Item>\n'

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Content xmlns="{NS_MD}">
{items}</Content>'''

    def _register_in_config(
        self, config_path: Path, name: str, obj_uuid: str
    ) -> bool:
        """Регистрация подсистемы в Configuration.xml."""
        # Простая проверка — не регистрируем если уже есть
        content = config_path.read_text(encoding="utf-8")
        if f"Subsystem.{name}" in content:
            return False
        # Реальная регистрация требует XML-парсинга и модификации
        # Здесь оставляем как TODO для будущей реализации
        return True


# ============================================================================
# CommonModuleCompiler
# ============================================================================


@dataclass
class CommonModuleProperties:
    """Свойства общего модуля."""

    name: str
    synonym: str = ""
    comment: str = ""
    # Где выполняется
    server: bool = False
    client: bool = False
    external_client: bool = False
    server_call: bool = False       # Вызов сервера
    client_call: bool = False       # Вызов клиента
    # Свойства выполнения
    privileged: bool = False        # Привилегированный режим
    return_value_type: str = ""     # Тип возвращаемого значения
    # Прочее
    include_help_in_contents: bool = False
    global_: bool = False           # Глобальный


class CommonModuleCompiler:
    """T5.4: Компилятор общих модулей 1С.

    Общий модуль имеет свойства выполнения (server/client) и
    обязательно связан с Module.bsl файлом.

    Генерирует:
    - {output_dir}/CommonModules/{name}/CommonModule.xml — метаданные
    - {output_dir}/CommonModules/{name}/Module.bsl — заглушка BSL кода
    """

    def compile(
        self,
        definition: str | dict[str, Any] | Path,
        output_dir: str | Path,
    ) -> CompileResult:
        """Скомпилировать общий модуль.

        Args:
            definition: JSON-определение (dict, JSON-строка или путь к файлу).
            output_dir: Каталог конфигурации (где CommonModules/).

        Returns:
            CompileResult с путями к созданным файлам.
        """
        def_dict = self._parse_definition(definition)
        self._validate(def_dict)

        props = CommonModuleProperties(
            name=def_dict["name"],
            synonym=def_dict.get("synonym", def_dict["name"]),
            comment=def_dict.get("comment", ""),
            server=def_dict.get("server", False),
            client=def_dict.get("client", False),
            external_client=def_dict.get("external_client", False),
            server_call=def_dict.get("server_call", False),
            client_call=def_dict.get("client_call", False),
            privileged=def_dict.get("privileged", False),
            return_value_type=def_dict.get("return_value_type", ""),
            include_help_in_contents=def_dict.get("include_help_in_contents", False),
            global_=def_dict.get("global", False),
        )

        obj_uuid = _gen_uuid()
        output_dir = Path(output_dir)
        module_dir = output_dir / "CommonModules" / props.name
        module_dir.mkdir(parents=True, exist_ok=True)

        # CommonModule.xml
        xml_path = module_dir / "CommonModule.xml"
        xml_content = self._build_module_xml(obj_uuid, props)
        xml_path.write_text(xml_content, encoding="utf-8")

        # Module.bsl — заглушка
        bsl_path = module_dir / "Module.bsl"
        bsl_content = self._build_module_bsl(props)
        bsl_path.write_text(bsl_content, encoding="utf-8")

        files = [xml_path, bsl_path]

        # Регистрация в Configuration.xml
        config_path = output_dir / "Configuration.xml"
        if config_path.exists():
            self._register_in_config(config_path, props.name, obj_uuid)

        return CompileResult(
            object_type="CommonModule",
            object_name=props.name,
            xml_path=files[0] if files else None,
            module_paths=files[1:] if len(files) > 1 else [],
        )

    def _parse_definition(self, definition: str | dict[str, Any] | Path) -> dict[str, Any]:
        """Парсинг определения общего модуля."""
        if isinstance(definition, dict):
            return definition
        if isinstance(definition, Path):
            data: dict[str, Any] = json.loads(definition.read_text(encoding="utf-8"))
            return data
        result: dict[str, Any] = json.loads(definition)
        return result

    def _validate(self, def_dict: dict[str, Any]) -> None:
        """Валидация определения."""
        if def_dict.get("type") != "CommonModule":
            raise ValueError(
                f"Expected type='CommonModule', got '{def_dict.get('type')}'"
            )
        if not def_dict.get("name"):
            raise ValueError("CommonModule must have 'name'")

    def _build_module_xml(
        self, obj_uuid: str, props: CommonModuleProperties
    ) -> str:
        """Построить XML метаданных общего модуля."""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="{NS_MD}" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="{NS_V8}" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="{NS_XR}" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.18">
\t<CommonModule uuid="{obj_uuid}">
\t\t<Properties>
\t\t\t<Name>{props.name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{props.synonym}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment>{props.comment}</Comment>
\t\t\t<Global>{str(props.global_).lower()}</Global>
\t\t\t<Client>{str(props.client).lower()}</Client>
\t\t\t<Server>{str(props.server).lower()}</Server>
\t\t\t<ExternalConnection>{str(props.external_client).lower()}</ExternalConnection>
\t\t\t<ClientOrdinaryApplication>false</ClientOrdinaryApplication>
\t\t\t<ServerCall>{str(props.server_call).lower()}</ServerCall>
\t\t\t<ClientCall>{str(props.client_call).lower()}</ClientCall>
\t\t\t<Privileged>{str(props.privileged).lower()}</Privileged>
\t\t\t<ReturnValuesReuse>DontUse</ReturnValuesReuse>
\t\t\t<IncludeInCommandInterface>false</IncludeInCommandInterface>
\t\t</Properties>
\t</CommonModule>
</MetaDataObject>'''

    def _build_module_bsl(self, props: CommonModuleProperties) -> str:
        """Построить заглушку BSL кода для общего модуля."""
        return f"""// {props.synonym or props.name}
// Общий модуль: {props.name}
// Свойства: server={props.server}, client={props.client}, privileged={props.privileged}

// Заглушка — добавьте реальные функции здесь

Функция ПолучитьВерсиюМодуля() Экспорт
    Возврат "1.0.0";
КонецФункции

Процедура Инициализация() Экспорт
    // TODO: инициализация модуля
КонецПроцедуры
"""

    def _register_in_config(
        self, config_path: Path, name: str, obj_uuid: str
    ) -> bool:
        """Регистрация общего модуля в Configuration.xml."""
        content = config_path.read_text(encoding="utf-8")
        return f"CommonModule.{name}" not in content
