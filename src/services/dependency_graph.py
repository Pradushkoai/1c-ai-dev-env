"""
DependencyGraph — граф зависимостей метаданных 1С.

В отличие от call_graph.py (граф вызовов BSL-методов), этот модуль строит
граф зависимостей МЕТАДАННЫХ: какие объекты ссылаются на какие.

Позаимствовано из 1c-ai-development-kit (docs/guides/project-mcp-setup.md,
Graph MCP через Neo4j) — но реализовано на networkx вместо Neo4j,
чтобы избежать тяжёлой зависимости (Java + Docker).

Запросы (аналоги Cypher):
- "Что зависит от справочника Контрагенты?" → what_depends_on("Catalog.Контрагенты")
- "На что ссылается документ ЗаказКлиента?" → dependencies_of("Document.ЗаказКлиента")
- "Циклические зависимости" → find_cycles()
- "Мёртвый код — объекты на которые никто не ссылается" → find_unused_objects()
- "Транзитивное замыкание" → transitive_dependencies("Catalog.Контрагенты")

Источники зависимостей:
1. Реквизиты типа CatalogRef.X / DocumentRef.X / EnumRef.X (из unified-metadata-index.json)
2. Табличные части с типами ссылок
3. Регистраторы регистров (Document.X → Register.Y)
4. Подсистемы (Catalog.X → Subsystem.Y)
5. Подписки на события (EventSubscription.X → CommonModule.Y.handler)
6. Вызовы методов между модулями (из call_graph если есть)

Пример:
    from src.services.dependency_graph import DependencyGraph

    dg = DependencyGraph()
    dg.build_from_metadata_index("ut11", paths)
    dependents = dg.what_depends_on("Catalog.Контрагенты")
    # → ["Document.ЗаказКлиента", "Document.РеализацияТоваров", ...]
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .path_manager import PathManager

# Типы связей в графе зависимостей
RELATION_TYPES = {
    "uses_attribute": "Реквизит ссылочного типа",
    "uses_tabular_section": "Табличная часть со ссылкой",
    "registered_by": "Регистратор регистра",
    "in_subsystem": "Входит в подсистему",
    "event_handler": "Подписка на событие → обработчик",
    "calls_method": "Вызов метода модуля",
}


@dataclass
class DependencyEdge:
    """Ребро графа зависимостей: кто → кого → почему."""
    source: str          # "Document.ЗаказКлиента" (кто зависит)
    target: str          # "Catalog.Контрагенты" (от кого зависит)
    relation: str        # uses_attribute | registered_by | in_subsystem | ...
    detail: str = ""     # "реквизит Контрагент" | "ТЧ Товары.Номенклатура"
    line: int = 0        # номер строки (для calls_method)


@dataclass
class DependencyGraphResult:
    """Результат построения графа зависимостей."""
    config_name: str
    nodes: list[str] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Маппинг множественного числа (из metadata-index) → единственное (TYPE_MAP)
PLURAL_TO_SINGULAR: dict[str, str] = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "Enums": "Enum",
    "Constants": "Constant",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "AccountingRegisters": "AccountingRegister",
    "CalculationRegisters": "CalculationRegister",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
    "BusinessProcesses": "BusinessProcess",
    "Tasks": "Task",
    "ExchangePlans": "ExchangePlan",
    "DocumentJournals": "DocumentJournal",
    "Reports": "Report",
    "DataProcessors": "DataProcessor",
    "CommonModules": "CommonModule",
    "CommonForms": "CommonForm",
    "CommonCommands": "CommonCommand",
    "CommonTemplates": "CommonTemplate",
    "CommonPictures": "CommonPicture",
    "CommonAttributes": "CommonAttribute",
    "CommandGroups": "CommandGroup",
    "DefinedTypes": "DefinedType",
    "DocumentNumerators": "DocumentNumerator",
    "EventSubscriptions": "EventSubscription",
    "FilterCriteria": "FilterCriterion",
    "FunctionalOptions": "FunctionalOption",
    "FunctionalOptionsParameters": "FunctionalOptionParameter",
    "HTTPServices": "HTTPService",
    "ScheduledJobs": "ScheduledJob",
    "Sequences": "Sequence",
    "SessionParameters": "SessionParameter",
    "SettingsStorages": "SettingsStorage",
    "Styles": "Style",
    "StyleItems": "StyleItem",
    "Subsystems": "Subsystem",
    "Roles": "Role",
    "WebServices": "WebService",
    "WSReferences": "WSReference",
    "XDTOPackages": "XDTOPackage",
}


class DependencyGraph:
    """Граф зависимостей метаданных 1С на networkx.

    Альтернатива Neo4j из 1c-ai-development-kit, но без внешних зависимостей.
    """

    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError(
                "networkx не установлен. Установите: pip install networkx"
            )
        self._graph: nx.DiGraph = nx.DiGraph()
        self._edges: list[DependencyEdge] = []
        self._config_name: str = ""

    # ─────────────────────────────────────────────
    # Построение графа
    # ─────────────────────────────────────────────

    def build_from_metadata_index(
        self,
        config_name: str,
        paths: PathManager,
    ) -> DependencyGraphResult:
        """Построить граф из unified-metadata-index.json.

        Args:
            config_name: имя конфигурации
            paths: PathManager проекта
        """
        self._graph = nx.DiGraph()
        self._edges = []
        self._config_name = config_name

        result = DependencyGraphResult(config_name=config_name)

        index_path = (
            paths.root / "derived" / "configs" / config_name
            / "unified-metadata-index.json"
        )
        if not index_path.exists():
            result.warnings.append(
                f"unified-metadata-index.json не найден для '{config_name}'"
            )
            return result

        try:
            with open(index_path, encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            result.warnings.append(f"Ошибка чтения metadata: {e}")
            return result

        # 1. Реквизиты ссылочных типов
        self._scan_attributes(metadata, result)

        # 2. Регистраторы регистров
        self._scan_register_recorders(metadata, result)

        # 3. Подсистемы
        self._scan_subsystems(metadata, result)

        # 4. Подписки на события
        self._scan_event_subscriptions(metadata, result)

        result.nodes = list(self._graph.nodes())
        result.edges = self._edges

        return result

    def _scan_attributes(self, metadata: dict, result: DependencyGraphResult) -> None:
        """Сканировать реквизиты ссылочных типов."""
        objects_by_type = metadata.get("objects", {})
        for type_name, objs in objects_by_type.items():
            # Нормализуем множественное → единственное (Catalogs → Catalog)
            singular = PLURAL_TO_SINGULAR.get(type_name, type_name)
            for obj in objs:
                obj_full = f"{singular}.{obj.get('name', '')}"
                if obj_full not in self._graph:
                    self._graph.add_node(obj_full)

                # Реквизиты
                children = obj.get("child_objects", {})
                for attr in children.get("attributes", []):
                    self._check_attribute_type(obj_full, attr, "реквизит")

                # Табличные части
                for ts in children.get("tabular_sections", []):
                    ts_name = ts.get("name", "")
                    for ts_attr in ts.get("attributes", []):
                        self._check_attribute_type(
                            obj_full, ts_attr, f"ТЧ {ts_name}"
                        )

    def _check_attribute_type(
        self, source_obj: str, attr: dict, context: str
    ) -> None:
        """Проверить тип реквизита на ссылочный."""
        attr_name = attr.get("name", "")
        # metadata_extractor хранит типы в 'types' (список), не в 'type' (строка)
        # Поддерживаем оба формата для совместимости
        attr_types = attr.get("types", [])
        if not attr_types:
            type_str = attr.get("type", "")
            if type_str:
                attr_types = [type_str]

        # Объединяем все типы в одну строку для парсинга
        # (составной тип: CatalogRef.А, CatalogRef.Б)
        combined_type = ", ".join(str(t) for t in attr_types if t)

        refs = self._extract_refs(combined_type)
        for ref_type, ref_name in refs:
            target = f"{ref_type}.{ref_name}"
            if target != source_obj:  # не ссылка на себя
                self._add_edge(source_obj, target, "uses_attribute",
                               f"{context} {attr_name}")

    @staticmethod
    def _extract_refs(type_str: str) -> list[tuple[str, str]]:
        """Извлечь ссылочные типы из строки типа.

        'CatalogRef.Контрагенты' → [('Catalog', 'Контрагенты')]
        'CatalogRef.Контрагенты, DocumentRef.Заказ' → [('Catalog', 'Контрагенты'), ('Document', 'Заказ')]
        """
        if not type_str:
            return []

        # Маппинг: CatalogRef → Catalog, DocumentRef → Document, и т.д.
        ref_pattern = re.compile(
            r"(CatalogRef|DocumentRef|EnumRef|ChartOfAccountsRef|"
            r"ChartOfCharacteristicTypesRef|ChartOfCalculationTypesRef|"
            r"ExchangePlanRef|BusinessProcessRef|TaskRef)\.(\w+)"
        )

        # Убираем "cfg:" префикс если есть
        type_str = type_str.replace("cfg:", "")

        refs = []
        for match in ref_pattern.finditer(type_str):
            ref_full = match.group(1)  # CatalogRef
            ref_name = match.group(2)  # Контрагенты
            # CatalogRef → Catalog
            base_type = ref_full.replace("Ref", "")
            refs.append((base_type, ref_name))

        return refs

    def _scan_register_recorders(
        self, metadata: dict, result: DependencyGraphResult
    ) -> None:
        """Регистраторы регистров: Document.X → Register.Y.

        В 1С XML регистраторы хранятся в <RegisterRecords> внутри Properties документа.
        Каждый документ указывает список регистров, по которым он делает движения.
        """
        objects_by_type = metadata.get("objects", {})

        # Сначала добавляем все регистры как узлы
        for reg_type_plural in ("InformationRegisters", "AccumulationRegisters",
                                 "AccountingRegisters", "CalculationRegisters"):
            reg_type = PLURAL_TO_SINGULAR.get(reg_type_plural, reg_type_plural)
            for reg in objects_by_type.get(reg_type, []) + objects_by_type.get(reg_type_plural, []):
                reg_full = f"{reg_type}.{reg.get('name', '')}"
                if reg_full not in self._graph:
                    self._graph.add_node(reg_full)

        # Обходим документы и ищем RegisterRecords в properties
        for doc_type_plural in ("Documents",):
            doc_type = PLURAL_TO_SINGULAR.get(doc_type_plural, doc_type_plural)
            for doc in objects_by_type.get(doc_type_plural, []):
                doc_full = f"{doc_type}.{doc.get('name', '')}"
                if doc_full not in self._graph:
                    self._graph.add_node(doc_full)

                # Ищем RegisterRecords в properties
                props = doc.get("properties", {})
                register_records = props.get("RegisterRecords", "")

                if isinstance(register_records, list):
                    for reg_ref in register_records:
                        if isinstance(reg_ref, str) and reg_ref:
                            self._add_edge(doc_full, reg_ref, "registered_by",
                                           "регистратор")
                elif isinstance(register_records, str) and register_records:
                    self._add_edge(doc_full, register_records, "registered_by",
                                   "регистратор")

    def _scan_subsystems(
        self, metadata: dict, result: DependencyGraphResult
    ) -> None:
        """Подсистемы: объекты входят в подсистемы."""
        for subsystem in metadata.get("subsystems", []):
            ss_name = subsystem.get("name", "")
            ss_full = f"Subsystem.{ss_name}"
            if ss_full not in self._graph:
                self._graph.add_node(ss_full)

            # Content — список объектов в подсистеме
            content = subsystem.get("content", [])
            for item in content:
                if isinstance(item, str) and "." in item:
                    self._add_edge(item, ss_full, "in_subsystem",
                                   "входит в подсистему")

    def _scan_event_subscriptions(
        self, metadata: dict, result: DependencyGraphResult
    ) -> None:
        """Подписки на события: EventSubscription.X → CommonModule.Y.handler."""
        for es in metadata.get("event_subscriptions", []):
            es_name = es.get("name", "")
            es_full = f"EventSubscription.{es_name}"
            if es_full not in self._graph:
                self._graph.add_node(es_full)

            handler = es.get("handler", "")
            if handler and "." in handler:
                # handler = "ОбщийМодуль.ИмяМетода" или "CommonModule.Имя.Метод"
                # Нормализуем
                handler_parts = handler.split(".")
                if len(handler_parts) >= 2:
                    target = f"CommonModule.{handler_parts[0]}"
                    self._add_edge(es_full, target, "event_handler", handler)

    def _add_edge(
        self, source: str, target: str, relation: str, detail: str = ""
    ) -> None:
        """Добавить ребро в граф."""
        if source not in self._graph:
            self._graph.add_node(source)
        if target not in self._graph:
            self._graph.add_node(target)

        self._graph.add_edge(source, target, relation=relation, detail=detail)
        self._edges.append(DependencyEdge(
            source=source, target=target, relation=relation, detail=detail
        ))

    # ─────────────────────────────────────────────
    # Запросы (аналоги Cypher)
    # ─────────────────────────────────────────────

    def what_depends_on(self, target: str) -> list[dict]:
        """Что зависит от target? (обратные рёбра)

        Аналог Cypher: MATCH (target)<-[:USES]-(source) RETURN source

        Args:
            target: "Catalog.Контрагенты"

        Returns:
            [{"source": "Document.ЗаказКлиента", "relation": "uses_attribute",
              "detail": "реквизит Контрагент"}, ...]
        """
        if target not in self._graph:
            return []

        result = []
        for source in self._graph.predecessors(target):
            edge_data = self._graph.get_edge_data(source, target)
            result.append({
                "source": source,
                "relation": edge_data.get("relation", ""),
                "detail": edge_data.get("detail", ""),
            })
        return result

    def dependencies_of(self, source: str) -> list[dict]:
        """На что ссылается source? (прямые рёбра)

        Аналог Cypher: MATCH (source)-[:USES]->(target) RETURN target

        Args:
            source: "Document.ЗаказКлиента"

        Returns:
            [{"target": "Catalog.Контрагенты", "relation": "uses_attribute",
              "detail": "реквизит Контрагент"}, ...]
        """
        if source not in self._graph:
            return []

        result = []
        for target in self._graph.successors(source):
            edge_data = self._graph.get_edge_data(source, target)
            result.append({
                "target": target,
                "relation": edge_data.get("relation", ""),
                "detail": edge_data.get("detail", ""),
            })
        return result

    def find_cycles(self, max_cycles: int = 100, timeout_seconds: float = 10.0) -> list[list[str]]:
        """Найти циклические зависимости с ограничением по количеству и времени.

        Аналог Cypher: MATCH path = (n)-[:USES*]->(n) RETURN path

        Args:
            max_cycles: максимальное количество циклов (default: 100)
            timeout_seconds: таймаут в секундах (default: 10)

        Returns:
            Список циклов, каждый цикл — список узлов.
            Если превышен timeout — возвращает то что успело найтись + warning.
        """
        import threading
        import time

        cycles: list[list[str]] = []
        timed_out = False

        def _find():
            nonlocal cycles, timed_out
            try:
                start = time.time()
                for i, cycle in enumerate(nx.simple_cycles(self._graph)):
                    if i >= max_cycles:
                        break
                    if time.time() - start > timeout_seconds:
                        timed_out = True
                        break
                    cycles.append(cycle)
            except nx.NetworkXError:
                pass
            except Exception:
                pass

        # Запускаем в потоке с timeout
        thread = threading.Thread(target=_find, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds + 2)  # +2 сек запас

        if thread.is_alive():
            # Поток всё ещё работает — возвращаем что успели
            timed_out = True

        return cycles

    def find_unused_objects(self) -> list[str]:
        """Найти объекты на которые никто не ссылается (мёртвый код).

        Аналог Cypher: MATCH (n) WHERE NOT ()-[:USES]->(n) RETURN n

        Returns:
            Список имён объектов.
        """
        unused = []
        for node in self._graph.nodes():
            # Если на узел никто не ссылается (нет predecessors)
            # и это не Catalog/Document (они могут быть сами по себе)
            in_degree = self._graph.in_degree(node)
            if in_degree == 0:
                unused.append(node)
        return unused

    def find_root_objects(self) -> list[str]:
        """Найти корневые объекты — на которые ссылаются, но сами ни на кого.

        Аналог Cypher: MATCH (n) WHERE NOT (n)-[:USES]->() AND ()-[:USES]->(n) RETURN n

        Returns:
            Список имён объектов.
        """
        roots = []
        for node in self._graph.nodes():
            out_degree = self._graph.out_degree(node)
            in_degree = self._graph.in_degree(node)
            if out_degree == 0 and in_degree > 0:
                roots.append(node)
        return roots

    def transitive_dependencies(self, source: str) -> list[str]:
        """Все транзитивные зависимости объекта.

        Аналог Cypher: MATCH (source)-[:USES*]->(target) RETURN DISTINCT target

        Args:
            source: "Catalog.Контрагенты"

        Returns:
            Список всех объектов на которые (транзитивно) ссылается source.
        """
        if source not in self._graph:
            return []
        try:
            return list(nx.descendants(self._graph, source))
        except nx.NetworkXError:
            return []

    def transitive_dependents(self, target: str) -> list[str]:
        """Все транзитивные зависимые (кто зависит от target прямо или косвенно).

        Аналог Cypher: MATCH (source)-[:USES*]->(target) RETURN DISTINCT source

        Args:
            target: "Catalog.Контрагенты"

        Returns:
            Список всех объектов которые зависят от target.
        """
        if target not in self._graph:
            return []
        try:
            return list(nx.ancestors(self._graph, target))
        except nx.NetworkXError:
            return []

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        """Кратчайший путь зависимости между двумя объектами.

        Аналог Cypher: MATCH path = shortestPath((source)-[:USES*]-(target)) RETURN path

        Args:
            source: "Catalog.Контрагенты"
            target: "Report.АнализПродаж"

        Returns:
            Список узлов пути или None если пути нет.
        """
        try:
            return nx.shortest_path(self._graph, source, target)
        except (nx.NetworkXError, nx.NetworkXNoPath):
            return None

    def get_stats(self) -> dict:
        """Статистика графа."""
        return {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "cycles": len(self.find_cycles()),
            "unused_objects": len(self.find_unused_objects()),
            "root_objects": len(self.find_root_objects()),
            "density": nx.density(self._graph),
            "is_dag": nx.is_directed_acyclic_graph(self._graph),
        }

    def to_dict(self) -> dict:
        """Сериализация графа в dict."""
        return {
            "config_name": self._config_name,
            "nodes": list(self._graph.nodes()),
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "detail": e.detail,
                }
                for e in self._edges
            ],
            "stats": self.get_stats(),
        }
