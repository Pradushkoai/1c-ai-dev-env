"""
T5.3 (2026-07-06): CFE extensions для форм и модулей.

CFE (Configuration Extension) — механизм расширения конфигурации 1С без
изменения основной конфигурации. Расширение может:
- Borrow (заимствовать) объекты из основной конфигурации
- Patch (модифицировать) методы BSL модулей
- Override (переопределять) формы и модули

Существующий CfeManager поддерживает borrow_object и patch_method.
Этот модуль добавляет:

1. CfeFormExtension — расширение форм:
   - Borrow form из основной конфигурации
   - Override form elements (добавить/изменить/скрыть)
   - Override form handlers (заменить процедуры)
   - Генерация Form.xml расширения

2. CfeModuleExtension — расширение модулей:
   - Borrow module из основной конфигурации
   - Patch methods (обёртки, hook'и)
   - Add new procedures/functions
   - Генерация Module.bsl расширения

3. CfeExtensionBuilder — сборщик CFE:
   - Создание структуры директорий CFE
   - Генерация Configuration.xml расширения
   - Регистрация borrowed объектов

Использование:
    from src.services.cfe.extensions import CfeFormExtension, CfeModuleExtension

    # Form extension
    form_ext = CfeFormExtension()
    form_xml = form_ext.create_form_extension(
        base_form="Документ.Продажа.Форма.ФормаДокумента",
        extension_name="ПродажаРасширение",
        overrides={"ДобавитьКнопкуПечати": True},
    )

    # Module extension
    module_ext = CfeModuleExtension()
    bsl_code = module_ext.create_module_extension(
        base_module="ОбщийМодуль.ОбщегоНазначения",
        extension_name="ОбщегоНазначенияРасширение",
        patches=[{"method": "Сообщить", "action": "wrap", "hook": "ЛогированиеВызова"}],
    )
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class FormOverride:
    """Переопределение элемента формы."""

    element_name: str           # имя элемента формы
    action: str                 # add, modify, hide, replace_handler
    new_value: str = ""         # новое значение (для modify)
    handler: str = ""           # имя обработчика (для replace_handler)


@dataclass
class ModulePatch:
    """Патч метода модуля."""

    method: str                 # имя метода
    action: str                 # wrap, before, after, replace
    hook: str = ""              # имя hook процедуры
    new_code: str = ""          # новый код (для replace)


@dataclass
class CfeExtensionInfo:
    """Информация о CFE расширении."""

    name: str
    synonym: str = ""
    comment: str = ""
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Список заимствованных объектов
    borrowed_objects: list[str] = field(default_factory=list)
    # Файлы расширения
    files: list[Path] = field(default_factory=list)


# ============================================================================
# CfeFormExtension
# ============================================================================


class CfeFormExtension:
    """T5.3: Расширение форм конфигурации.

    Позволяет создавать расширения форм, которые:
    - Заимствуют форму из основной конфигурации
    - Добавляют новые элементы (кнопки, поля)
    - Скрывают существующие элементы
    - Заменяют обработчики событий
    """

    def create_form_extension(
        self,
        base_form: str,
        extension_name: str,
        overrides: list[FormOverride] | None = None,
        synonym: str = "",
    ) -> str:
        """Создать XML расширения формы.

        Args:
            base_form: Путь к базовой форме (например, "Документ.Продажа.Форма.ФормаДокумента").
            extension_name: Имя расширения.
            overrides: Список переопределений.
            synonym: Синоним расширения.

        Returns:
            XML-строка расширения формы.
        """
        overrides = overrides or []
        ext_uuid = str(uuid.uuid4())

        # Разбиваем base_form на компоненты
        parts = base_form.split(".")
        if len(parts) < 4:
            raise ValueError(
                f"base_form must be like 'Document.Sale.Form.FormDoc', got: {base_form}"
            )

        obj_type, obj_name, _, form_name = parts[0], parts[1], parts[2], parts[3]

        # Генерируем XML
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" '
            'xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
            'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
            'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
            'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
            'version="2.18">',
            f'\t<Items>',  # noqa: E501
        ]

        # Добавляем overrides
        for override in overrides:
            if override.action == "add":
                lines.append(self._generate_add_element(override))
            elif override.action == "hide":
                lines.append(self._generate_hide_element(override))
            elif override.action == "modify":
                lines.append(self._generate_modify_element(override))
            elif override.action == "replace_handler":
                lines.append(self._generate_handler_replace(override))

        lines.append('\t</Items>')
        lines.append('</Form>')

        return "\n".join(lines)

    def _generate_add_element(self, override: FormOverride) -> str:
        """Сгенерировать XML для добавления элемента."""
        return (
            f'\t\t<Button name="{override.element_name}" id="100">'
            f'\n\t\t\t<Type>UsualButton</Type>'
            f'\n\t\t\t<Title>'
            f'\n\t\t\t\t<v8:item>'
            f'\n\t\t\t\t\t<v8:lang>ru</v8:lang>'
            f'\n\t\t\t\t\t<v8:content>{override.new_value or override.element_name}</v8:content>'
            f'\n\t\t\t\t</v8:item>'
            f'\n\t\t\t</Title>'
            f'\n\t\t\t<Action>{override.handler}</Action>'
            f'\n\t\t</Button>'
        )

    def _generate_hide_element(self, override: FormOverride) -> str:
        """Сгенерировать XML для скрытия элемента."""
        return (
            f'\t\t<Hide name="{override.element_name}" id="101"/>'
        )

    def _generate_modify_element(self, override: FormOverride) -> str:
        """Сгенерировать XML для модификации элемента."""
        return (
            f'\t\t<Modify name="{override.element_name}" id="102">'
            f'\n\t\t\t<NewValue>{override.new_value}</NewValue>'
            f'\n\t\t</Modify>'
        )

    def _generate_handler_replace(self, override: FormOverride) -> str:
        """Сгенерировать XML для замены обработчика."""
        return (
            f'\t\t<HandlerReplace element="{override.element_name}">'
            f'\n\t\t\t<NewHandler>{override.handler}</NewHandler>'
            f'\n\t\t</HandlerReplace>'
        )


# ============================================================================
# CfeModuleExtension
# ============================================================================


class CfeModuleExtension:
    """T5.3: Расширение модулей конфигурации.

    Позволяет создавать расширения модулей, которые:
    - Заимствуют модуль из основной конфигурации
    - Оборачивают методы (wrap — до и после вызова)
    - Добавляют hook'и (before/after)
    - Заменяют методы (replace)
    - Добавляют новые процедуры/функции
    """

    def create_module_extension(
        self,
        base_module: str,
        extension_name: str,
        patches: list[ModulePatch] | None = None,
        new_procedures: list[str] | None = None,
    ) -> str:
        """Создать BSL код расширения модуля.

        Args:
            base_module: Путь к базовому модулю (например, "CommonModule.ОбщегоНазначения").
            extension_name: Имя расширения.
            patches: Список патчей методов.
            new_procedures: Список новых процедур (BSL код).

        Returns:
            BSL-код расширения модуля.
        """
        patches = patches or []
        new_procedures = new_procedures or []

        lines: list[str] = [
            f"// Расширение модуля: {base_module}",
            f"// Имя расширения: {extension_name}",
            "",
        ]

        # Генерируем патчи
        for patch in patches:
            if patch.action == "wrap":
                lines.append(self._generate_wrap_patch(patch))
            elif patch.action == "before":
                lines.append(self._generate_before_patch(patch))
            elif patch.action == "after":
                lines.append(self._generate_after_patch(patch))
            elif patch.action == "replace":
                lines.append(self._generate_replace_patch(patch))
            lines.append("")

        # Добавляем новые процедуры
        for proc in new_procedures:
            lines.append(proc)
            lines.append("")

        return "\n".join(lines)

    def _generate_wrap_patch(self, patch: ModulePatch) -> str:
        """Сгенерировать BSL для wrap патча (обёртка метода)."""
        return (
            f"&Вместо(\"{patch.method}\")\n"
            f"Процедура Расш_{patch.method}_Обёртка()\n"
            f"    // Before hook\n"
            f"    Если ЗначениеЗаполнено(\"{patch.hook}\") Тогда\n"
            f"        {patch.hook}();\n"
            f"    КонецЕсли;\n"
            f"\n"
            f"    // Original call\n"
            f"    ПродолжитьВызов();\n"
            f"\n"
            f"    // After hook\n"
            f"    // TODO: добавить после-call логику\n"
            f"КонецПроцедуры"
        )

    def _generate_before_patch(self, patch: ModulePatch) -> str:
        """Сгенерировать BSL для before патча (hook перед методом)."""
        return (
            f"&Перед(\"{patch.method}\")\n"
            f"Процедура Расш_{patch.method}_Перед()\n"
            f"    // Hook перед вызовом {patch.method}\n"
            f"    {patch.hook}();\n"
            f"КонецПроцедуры"
        )

    def _generate_after_patch(self, patch: ModulePatch) -> str:
        """Сгенерировать BSL для after патча (hook после метода)."""
        return (
            f"&После(\"{patch.method}\")\n"
            f"Процедура Расш_{patch.method}_После()\n"
            f"    // Hook после вызова {patch.method}\n"
            f"    {patch.hook}();\n"
            f"КонецПроцедуры"
        )

    def _generate_replace_patch(self, patch: ModulePatch) -> str:
        """Сгенерировать BSL для replace патча (замена метода)."""
        return (
            f"&Вместо(\"{patch.method}\")\n"
            f"Процедура Расш_{patch.method}_Замена()\n"
            f"    // Полная замена метода {patch.method}\n"
            f"    {patch.new_code or '// TODO: реализация'}\n"
            f"КонецПроцедуры"
        )


# ============================================================================
# CfeExtensionBuilder
# ============================================================================


class CfeExtensionBuilder:
    """T5.3: Сборщик CFE расширений.

    Создаёт структуру директорий CFE и генерирует Configuration.xml.
    """

    def build_extension(
        self,
        output_dir: str | Path,
        extension_name: str,
        synonym: str = "",
        comment: str = "",
        form_extensions: list[tuple[str, str]] | None = None,
        module_extensions: list[tuple[str, str]] | None = None,
    ) -> CfeExtensionInfo:
        """Собрать CFE расширение.

        Args:
            output_dir: Корневая директория для расширения.
            extension_name: Имя расширения.
            synonym: Синоним.
            comment: Комментарий.
            form_extensions: Список (base_form, form_xml) пар.
            module_extensions: Список (base_module, bsl_code) пар.

        Returns:
            CfeExtensionInfo с путями к созданным файлам.
        """
        output_dir = Path(output_dir)
        ext_dir = output_dir / extension_name
        ext_dir.mkdir(parents=True, exist_ok=True)

        info = CfeExtensionInfo(
            name=extension_name,
            synonym=synonym or extension_name,
            comment=comment,
        )

        # Form extensions — сначала собираем borrowed_objects
        if form_extensions:
            forms_dir = ext_dir / "Forms"
            forms_dir.mkdir(exist_ok=True)
            for base_form, form_xml in form_extensions:
                form_name = base_form.split(".")[-1]
                form_path = forms_dir / f"{form_name}.xml"
                form_path.write_text(form_xml, encoding="utf-8")
                info.files.append(form_path)
                info.borrowed_objects.append(base_form)

        # Module extensions
        if module_extensions:
            modules_dir = ext_dir / "Modules"
            modules_dir.mkdir(exist_ok=True)
            for base_module, bsl_code in module_extensions:
                module_name = base_module.split(".")[-1]
                module_path = modules_dir / f"{module_name}.bsl"
                module_path.write_text(bsl_code, encoding="utf-8")
                info.files.append(module_path)
                info.borrowed_objects.append(base_module)

        # Configuration.xml расширения (после того как borrowed_objects собраны)
        config_path = ext_dir / "Configuration.xml"
        config_xml = self._generate_config_xml(info)
        config_path.write_text(config_xml, encoding="utf-8")
        info.files.append(config_path)

        logger.info(
            "CFE extension built: %s (%d files, %d borrowed objects)",
            extension_name,
            len(info.files),
            len(info.borrowed_objects),
        )

        return info

    def _generate_config_xml(self, info: CfeExtensionInfo) -> str:
        """Сгенерировать Configuration.xml расширения."""
        # Список borrowed объектов
        borrowed_xml = ""
        for obj in info.borrowed_objects:
            borrowed_xml += f'\t\t\t<xr:Item>{obj}</xr:Item>\n'

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.18">
\t<Configuration uuid="{info.uuid}">
\t\t<Properties>
\t\t\t<Name>{info.name}</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>{info.synonym}</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment>{info.comment}</Comment>
\t\t\t<ObjectBelonging>Adopted</ObjectBelonging>
\t\t\t<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>
\t\t</Properties>
\t\t<ChildObjects>
{borrowed_xml}\t\t</ChildObjects>
\t</Configuration>
</MetaDataObject>'''
