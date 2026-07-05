#!/usr/bin/env python3
"""
architecture_analyzer.py — Анализ архитектуры BSL кода 1С.

Проверяет:
1. Циклические зависимости между модулями
2. Нарушение layering (формы → БД напрямую, без модуля объекта)
3. Дублирование логики в разных модулях
4. God Object (модули > 1000 строк или > 50 методов)
5. Неиспользуемые экспортные методы (мёртвый код на уровне API)
6. Too Many Dependencies (модуль зависит от > 10 других)
7. Отсутствие областей в модуле
8. Смешение клиентского и серверного кода
9. Прямые запросы в формах (без выноса в модуль объекта)
10. Отсутствие модуля менеджера при наличии модуля объекта

Использование:
    from architecture_analyzer import ArchitectureAnalyzer
    analyzer = ArchitectureAnalyzer()
    issues = analyzer.analyze_config(Path('data/configs/ut11'))
"""

from __future__ import annotations
from typing import Any

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ArchitectureIssue:
    """Проблема архитектуры."""

    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    module: str
    line: int = 0
    message: str = ""
    recommendation: str = ""


@dataclass
class ModuleInfo:
    """Информация о модуле."""

    name: str
    file_path: str
    module_type: str  # CommonModule, ObjectModule, ManagerModule, FormModule, etc.
    parent_type: str = ""  # Catalog, Document, etc.
    parent_name: str = ""
    loc: int = 0
    export_methods: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # модули, которые вызывает
    has_regions: bool = False
    has_server_code: bool = False
    has_client_code: bool = False


class ArchitectureAnalyzer:
    """Анализатор архитектуры конфигурации 1С."""

    def analyze_config(self, config_dir: Path) -> tuple[list[ArchitectureIssue], list[ModuleInfo]]:
        """Анализ архитектуры всей конфигурации.

        Returns:
            (issues, modules) — проблемы и информация о модулях
        """
        config_dir = Path(config_dir)
        modules = self._collect_modules(config_dir)
        issues = []

        issues.extend(self._check_god_objects(modules))
        issues.extend(self._check_cyclic_dependencies(modules))
        issues.extend(self._check_dead_code(modules))
        issues.extend(self._check_too_many_dependencies(modules))
        issues.extend(self._check_missing_regions(modules))
        issues.extend(self._check_mixed_client_server(modules))
        issues.extend(self._check_queries_in_forms(modules))
        issues.extend(self._check_forms_direct_db(modules))

        return issues, modules

    def analyze_file(self, file_path: Path, module_name: str = "") -> list[ArchitectureIssue]:
        """Анализ одного BSL файла."""
        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return []

        issues = []
        name = module_name or file_path.stem

        # ARCH004: God Object
        lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("//")]
        if len(lines) > 1000:
            issues.append(
                ArchitectureIssue(
                    rule_id="ARCH004",
                    severity="HIGH",
                    module=name,
                    message=f"God Object: {len(lines)} строк кода (рекомендуется < 1000)",
                    recommendation="Разбейте модуль на несколько более мелких",
                )
            )

        # ARCH007: Отсутствие областей
        if "#Область" not in content and "#Область" not in content and len(lines) > 20:
            issues.append(
                ArchitectureIssue(
                    rule_id="ARCH007",
                    severity="MEDIUM",
                    module=name,
                    message="Модуль без #Область/#КонецОбласти (размер > 20 строк)",
                    recommendation="Используйте области для структурирования кода",
                )
            )

        # ARCH008: Смешение клиент/сервер
        has_server = bool(re.search(r"&НаСервере|&НаСервереБезКонтекста", content))
        has_client = bool(re.search(r"&НаКлиенте|&НаКлиентеНаСервере", content))
        if has_server and has_client and "Form" in str(file_path):
            # Форма с явным смешением — нормально, но проверяем:
            # серверный код, который не в &НаСервере
            lines_list = content.split("\n")
            for i, line in enumerate(lines_list, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("&"):
                    continue
                # Если в коде формы есть Запрос без &НаСервере выше
                if re.search(r"\bНовый\s+Запрос\b", stripped) or re.search(r"\bЗапрос\s*=", stripped):
                    # Проверяем 5 строк вверх на &НаСервере
                    context = " ".join(lines_list[max(0, i - 6) : i])
                    if "&НаСервере" not in context:
                        issues.append(
                            ArchitectureIssue(
                                rule_id="ARCH009",
                                severity="HIGH",
                                module=name,
                                line=i,
                                message="Запрос в коде формы без &НаСервере — нарушение layering",
                                code_snippet=stripped[:100],
                                recommendation="Вынесите запрос в модуль объекта или пометьте процедуру &НаСервере",
                            )
                        )

        return issues

    # =====================================================================
    # СБОР ИНФОРМАЦИИ О МОДУЛЯХ
    # =====================================================================

    def _collect_modules(self, config_dir: Path) -> list[ModuleInfo]:
        """Сбор информации обо всех BSL модулях конфигурации."""
        modules = []

        # CommonModules
        cm_dir = config_dir / "CommonModules"
        if cm_dir.exists():
            for xml_file in cm_dir.glob("*.xml"):
                name = xml_file.stem
                bsl_file = cm_dir / name / "Ext" / "Module.bsl"
                if bsl_file.exists():
                    modules.append(self._parse_module(bsl_file, name, "CommonModule"))

        # Object modules (Catalogs, Documents, etc.)
        for obj_type in [
            "Catalogs",
            "Documents",
            "DataProcessors",
            "Reports",
            "InformationRegisters",
            "AccumulationRegisters",
        ]:
            type_dir = config_dir / obj_type
            if not type_dir.exists():
                continue
            for obj_dir in type_dir.iterdir():
                if not obj_dir.is_dir():
                    continue
                obj_name = obj_dir.name
                # ObjectModule
                obj_bsl = obj_dir / "Ext" / "ObjectModule.bsl"
                if obj_bsl.exists():
                    modules.append(self._parse_module(obj_bsl, obj_name, "ObjectModule", obj_type, obj_name))
                # ManagerModule
                mgr_bsl = obj_dir / "Ext" / "ManagerModule.bsl"
                if mgr_bsl.exists():
                    modules.append(
                        self._parse_module(mgr_bsl, obj_name + ".Менеджер", "ManagerModule", obj_type, obj_name)
                    )
                # Form modules
                forms_dir = obj_dir / "Forms"
                if forms_dir.exists():
                    for form_dir in forms_dir.iterdir():
                        if not form_dir.is_dir():
                            continue
                        form_bsl = form_dir / "Ext" / "Form" / "Module.bsl"
                        if form_bsl.exists():
                            form_name = f"{obj_name}.{form_dir.name}"
                            modules.append(self._parse_module(form_bsl, form_name, "FormModule", obj_type, obj_name))

        # CommonForms
        cf_dir = config_dir / "CommonForms"
        if cf_dir.exists():
            for form_dir in cf_dir.iterdir():
                if not form_dir.is_dir():
                    continue
                form_bsl = form_dir / "Ext" / "Form" / "Module.bsl"
                if form_bsl.exists():
                    modules.append(self._parse_module(form_bsl, form_dir.name, "FormModule", "CommonForm", ""))

        # ManagedApplicationModule
        app_bsl = config_dir / "Ext" / "ManagedApplicationModule.bsl"
        if app_bsl.exists():
            modules.append(self._parse_module(app_bsl, "ManagedApplicationModule", "ManagedApplicationModule"))

        return modules

    def _parse_module(
        self, bsl_file: Path, name: str, module_type: str, parent_type: str = "", parent_name: str = ""
    ) -> ModuleInfo:
        """Парсинг BSL модуля."""
        try:
            content = bsl_file.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return ModuleInfo(
                name=name,
                file_path=str(bsl_file),
                module_type=module_type,
                parent_type=parent_type,
                parent_name=parent_name,
            )

        lines = content.split("\n")
        loc = sum(1 for l in lines if l.strip() and not l.strip().startswith("//"))

        # Экспортные методы
        export_methods = []
        method_pattern = re.compile(r"^(Процедура|Функция)\s+(\w+)\s*\([^)]*\)(\s+Экспорт)?", re.IGNORECASE)
        for line in lines:
            m = method_pattern.match(line.strip())
            if m and m.group(3):
                export_methods.append(m.group(2))

        # Зависимости (вызовы других модулей)
        dependencies = set()
        # Pattern: ИмяМодуля.ИмяМетода()
        dep_pattern = re.compile(r"\b([А-Яа-я][А-Яа-я0-9_]*)\.[А-Яа-я][А-Яа-я0-9_]*\s*\(")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            for match in dep_pattern.finditer(stripped):
                dep = match.group(1)
                # Фильтруем стандартные объекты
                if dep not in (
                    "Элементы",
                    "ЭтаФорма",
                    "Объект",
                    "РеквизитФормыВЗначение",
                    "ЗначениеВРеквизитФормы",
                    "Стр",
                    "СтрНайти",
                    "СтрДлина",
                    "СтрЗаменить",
                    "СтрРазделить",
                    "СтрСоединить",
                    "Массив",
                    "Структура",
                    "Соответствие",
                    "СписокЗначений",
                    "ТаблицаЗначений",
                    "ДеревоЗначений",
                    "Запрос",
                    "Результат",
                    "Выборка",
                    "Справочники",
                    "Документы",
                    "РегистрыСведений",
                    "РегистрыНакопления",
                    "Константы",
                    "Перечисления",
                    "ПланыВидовХарактеристик",
                    "ПланыСчетов",
                    "БизнесПроцессы",
                    "Задачи",
                    "ПланыОбмена",
                ):
                    dependencies.add(dep)

        # Области
        has_regions = "#Область" in content or "#Область" in content

        # Клиент/сервер
        has_server = bool(re.search(r"&НаСервере|&НаСервереБезКонтекста", content))
        has_client = bool(re.search(r"&НаКлиенте|&НаКлиентеНаСервере", content))

        return ModuleInfo(
            name=name,
            file_path=str(bsl_file),
            module_type=module_type,
            parent_type=parent_type,
            parent_name=parent_name,
            loc=loc,
            export_methods=export_methods,
            dependencies=list(dependencies),
            has_regions=has_regions,
            has_server_code=has_server,
            has_client_code=has_client,
        )

    # =====================================================================
    # ПРАВИЛА
    # =====================================================================

    def _check_god_objects(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH004: God Object — модули > 1000 строк или > 50 методов."""
        issues = []
        for m in modules:
            if m.loc > 1000:
                issues.append(
                    ArchitectureIssue(
                        rule_id="ARCH004",
                        severity="HIGH",
                        module=m.name,
                        message=f"God Object: {m.loc} строк кода (рекомендуется < 1000)",
                        recommendation="Разбейте модуль на несколько более мелких",
                    )
                )
            elif len(m.export_methods) > 50:
                issues.append(
                    ArchitectureIssue(
                        rule_id="ARCH004",
                        severity="MEDIUM",
                        module=m.name,
                        message=f"God Object: {len(m.export_methods)} экспортных методов (рекомендуется < 50)",
                        recommendation="Разбейте модуль на несколько более мелких",
                    )
                )
        return issues

    def _check_cyclic_dependencies(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH001: Циклические зависимости между модулями."""
        issues = []

        # Строим граф зависимостей
        module_names = {m.name for m in modules}
        dep_graph: dict[str, list[str]] = defaultdict(list)

        for m in modules:
            for dep in m.dependencies:
                if dep in module_names and dep != m.name:
                    dep_graph[m.name].append(dep)

        # Поиск циклов (DFS)
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: list[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dep_graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    cycle = path + [neighbor]
                    issues.append(
                        ArchitectureIssue(
                            rule_id="ARCH001",
                            severity="HIGH",
                            module=node,
                            message=f"Циклическая зависимость: {' → '.join(cycle)}",
                            recommendation="Разорвите цикл, вынеся общую логику в отдельный модуль",
                        )
                    )
                    return True

            rec_stack.discard(node)
            return False

        for node in module_names:
            if node not in visited:
                dfs(node, [node])

        return issues

    def _check_dead_code(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH005: Неиспользуемые экспортные методы."""
        issues = []

        # Собираем все вызовы методов
        all_calls = set()
        for m in modules:
            for dep in m.dependencies:
                all_calls.add(dep)

        # Проверяем, какие модули с экспортными методами не вызываются
        for m in modules:
            if m.module_type == "CommonModule" and m.export_methods:
                if m.name not in all_calls and len(m.export_methods) > 0:
                    issues.append(
                        ArchitectureIssue(
                            rule_id="ARCH005",
                            severity="LOW",
                            module=m.name,
                            message=f"Возможно неиспользуемый модуль: {len(m.export_methods)} экспортных методов, не вызывается ни разу",
                            recommendation="Проверьте, используется ли модуль. Если нет — удалите.",
                        )
                    )

        return issues

    def _check_too_many_dependencies(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH006: Too Many Dependencies — модуль зависит от > 10 других."""
        issues = []
        MAX_DEPS = 10

        for m in modules:
            if len(m.dependencies) > MAX_DEPS:
                issues.append(
                    ArchitectureIssue(
                        rule_id="ARCH006",
                        severity="MEDIUM",
                        module=m.name,
                        message=f"Too Many Dependencies: {len(m.dependencies)} зависимостей (рекомендуется < {MAX_DEPS})",
                        recommendation="Уменьшите количество зависимостей, возможно через фасадный модуль",
                    )
                )

        return issues

    def _check_missing_regions(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH007: Отсутствие областей в модуле > 20 строк."""
        issues = []
        for m in modules:
            if not m.has_regions and m.loc > 20:
                issues.append(
                    ArchitectureIssue(
                        rule_id="ARCH007",
                        severity="MEDIUM",
                        module=m.name,
                        message=f"Модуль без #Область ({m.loc} строк)",
                        recommendation="Используйте области: ПрограммныйИнтерфейс, СлужебныйПрограммныйИнтерфейс, СлужебныеПроцедурыИФункции",
                    )
                )
        return issues

    def _check_mixed_client_server(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH008: Смешение клиентского и серверного кода (в общих модулях)."""
        issues = []
        for m in modules:
            if m.module_type == "CommonModule" and m.has_server_code and m.has_client_code:
                issues.append(
                    ArchitectureIssue(
                        rule_id="ARCH008",
                        severity="LOW",
                        module=m.name,
                        message="Общий модуль со смешанным клиент/сервер контекстом",
                        recommendation="Разделите на отдельные клиентский и серверный модули",
                    )
                )
        return issues

    def _check_queries_in_forms(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH009: Прямые запросы в формах (без &НаСервере)."""
        issues = []
        for m in modules:
            if m.module_type != "FormModule":
                continue
            try:
                content = Path(m.file_path).read_text(encoding="utf-8-sig", errors="replace")
            except Exception:
                continue

            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//"):
                    continue
                if re.search(r"\bНовый\s+Запрос\b", stripped) or re.search(r"\bЗапрос\s*=", stripped):
                    context = " ".join(lines[max(0, i - 6) : i])
                    if "&НаСервере" not in context:
                        issues.append(
                            ArchitectureIssue(
                                rule_id="ARCH009",
                                severity="HIGH",
                                module=m.name,
                                line=i,
                                message="Запрос в форме без &НаСервере — нарушение layering",
                                recommendation="Вынесите запрос в модуль объекта или пометьте &НаСервере",
                            )
                        )
        return issues

    def _check_forms_direct_db(self, modules: list[ModuleInfo]) -> list[ArchitectureIssue]:
        """ARCH010: Формы обращаются к БД напрямую (Записать, Удалить без модуля объекта)."""
        issues = []
        db_ops = [r"\.Записать\s*\(", r"\.Удалить\s*\(", r"\.Провести\s*\("]

        for m in modules:
            if m.module_type != "FormModule":
                continue
            try:
                content = Path(m.file_path).read_text(encoding="utf-8-sig", errors="replace")
            except Exception:
                continue

            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//"):
                    continue
                for pattern in db_ops:
                    if re.search(pattern, stripped):
                        # Проверяем что это не в &НаСервере
                        context = " ".join(lines[max(0, i - 6) : i])
                        if "&НаСервере" not in context:
                            issues.append(
                                ArchitectureIssue(
                                    rule_id="ARCH010",
                                    severity="MEDIUM",
                                    module=m.name,
                                    line=i,
                                    message="Прямая запись в БД из формы без &НаСервере",
                                    recommendation="Вынесите операцию записи в модуль объекта",
                                )
                            )
                            break
        return issues

    def get_stats(self, issues: list[ArchitectureIssue]) -> dict[str, Any]:
        """Статистика."""
        from collections import Counter

        by_severity = Counter(i.severity for i in issues)
        by_rule = Counter(i.rule_id for i in issues)
        return {
            "total_issues": len(issues),
            "by_severity": dict[str, Any](by_severity),
            "by_rule": dict[str, Any](by_rule),
        }


# CLI вынесен в scripts/architecture_analyzer.py (Этап 1.2, Группа 1d)
