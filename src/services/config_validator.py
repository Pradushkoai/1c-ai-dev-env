"""
config_validator.py — валидация исходников и индексов конфигураций 1С.

P2.11: выделен из ConfigManager (746 строк, God Object) для соблюдения SRP.
ConfigValidator отвечает только за:
  - validate_sources(name) — проверка исходников конфигурации
  - check_freshness(name) — проверка актуальности индексов

Не зависит от ConfigManager — работает напрямую с registry и paths.
Может использоваться независимо для pre-flight проверок.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.config_registry import ConfigurationRegistry
    from .path_manager import PathManager


# --- Директории 1С, которые считаются валидными метаданными ---

REQUIRED_TYPE_DIRS: tuple[str, ...] = (
    "Catalogs",
    "Documents",
    "Enums",
    "Constants",
    "CommonModules",
    "InformationRegisters",
    "AccumulationRegisters",
    "Reports",
    "DataProcessors",
    "CommonForms",
    "CommonTemplates",
    "CommonCommands",
    "CommonPictures",
    "Roles",
    "Subsystems",
    "EventSubscriptions",
    "ScheduledJobs",
    "DefinedTypes",
    "FunctionalOptions",
    "ExchangePlans",
    "ChartsOfCharacteristicTypes",
    "HTTPServices",
    "WebServices",
    "XDTOPackages",
    "FilterCriteria",
    "SessionParameters",
    "CommandGroups",
    "SettingsStorages",
    "BusinessProcesses",
    "Tasks",
    "DocumentJournals",
    "DocumentNumerators",
    "Sequences",
    "FunctionalOptionsParameters",
    "CommonAttributes",
    "WSReferences",
)

# Минимум одна из этих директорий должна быть, чтобы считать выгрузку валидной
MIN_REQUIRED_DIRS: tuple[str, ...] = ("CommonModules", "Catalogs", "Documents", "Subsystems")


# ============================================================================
# Dataclasses для результатов валидации
# ============================================================================


@dataclass
class SourceValidation:
    """Результат валидации исходников конфигурации."""

    is_valid: bool
    has_configuration_xml: bool = False
    has_metadata_dirs: bool = False
    has_bsl_files: bool = False
    found_type_dirs: list[str] = field(default_factory=list)
    missing_critical: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IndexStatus:
    """Статус одного индекса конфигурации."""

    name: str
    path: Path | None
    exists: bool = False
    mtime: float | None = None
    size_bytes: int = 0
    is_stale: bool = False
    stale_reason: str = ""
    source_hash_match: bool = True  # D2.4: True если hash исходников совпадает с сохранённым


@dataclass
class IndexFreshnessReport:
    """Отчёт о свежести всех индексов конфигурации."""

    config_name: str
    source_mtime: float | None = None
    source_hash: str = ""  # D2.4: content hash исходников
    all_fresh: bool = True
    indexes: list[IndexStatus] = field(default_factory=list)
    stale_indexes: list[str] = field(default_factory=list)
    missing_indexes: list[str] = field(default_factory=list)


# ============================================================================
# ConfigValidator
# ============================================================================


class ConfigValidator:
    """
    Валидация исходников и индексов конфигураций 1С.

    Ответственность (SRP):
    - validate_sources(name): проверка, что исходники готовы к индексации
    - check_freshness(name): проверка, что индексы не устарели

    Не делает: CRUD операций (это ConfigManager), построения индексов
    (это ConfigBuilder).

    Usage:
        validator = ConfigValidator(registry, paths)
        result = validator.validate_sources("ut11")
        if not result.is_valid:
            print(f"Ошибки: {result.errors}")
    """

    def __init__(
        self,
        registry: ConfigurationRegistry,
        paths: PathManager,
    ) -> None:
        self._registry = registry
        self._paths = paths

    def validate_sources(self, name: str) -> SourceValidation:
        """
        Проверить что исходники конфигурации валидны для индексации.

        Проверки:
        1. Configuration.xml существует (обязателен для полной XML выгрузки)
        2. Хотя бы одна из MIN_REQUIRED_DIRS директорий существует
        3. Наличие .bsl файлов (предупреждение если нет)

        Args:
            name: Имя конфигурации в реестре.

        Returns:
            SourceValidation с флагом is_valid и списками errors/warnings.
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            return SourceValidation(
                is_valid=False,
                errors=[f"Конфигурация '{name}' не активна"],
            )

        result = SourceValidation(is_valid=True)
        config_dir = config.path

        # 1. Configuration.xml
        cfg_xml = config_dir / "Configuration.xml"
        result.has_configuration_xml = cfg_xml.exists()
        if not result.has_configuration_xml:
            result.errors.append("Configuration.xml не найден — это не полная XML выгрузка")
            result.is_valid = False

        # 2. Метаданные-директории
        for type_dir in REQUIRED_TYPE_DIRS:
            d = config_dir / type_dir
            if d.is_dir() and any(d.iterdir()):
                result.found_type_dirs.append(type_dir)

        has_critical = any(d in result.found_type_dirs for d in MIN_REQUIRED_DIRS)
        result.has_metadata_dirs = has_critical
        if not has_critical:
            result.missing_critical = list(MIN_REQUIRED_DIRS)
            result.errors.append("Ни одна из критических директорий не найдена: " + ", ".join(MIN_REQUIRED_DIRS))
            result.is_valid = False

        # 3. .bsl файлы (предупреждение)
        try:
            bsl_count = sum(1 for _ in config_dir.rglob("*.bsl"))
            result.has_bsl_files = bsl_count > 0
            if not result.has_bsl_files:
                result.warnings.append(
                    ".bsl файлы не найдены — api-reference будет пустым. Возможно это .cf распаковка без адаптации."
                )
        except (OSError, PermissionError) as e:
            result.warnings.append(f"Не удалось проверить .bsl файлы: {e}")

        return result

    def check_freshness(self, name: str) -> IndexFreshnessReport:
        """
        Проверить актуальность индексов конфигурации.

        D2.4 (2026-07-05): добавлена content hash проверка.
        Для каждого из 4 индексов (metadata/api/skd/forms):
        - существует ли файл?
        - совпадает ли hash исходников с сохранённым? (content-based, primary)
        - новее ли source чем index? (mtime-based, fallback если нет hash файла)

        Args:
            name: Имя конфигурации.

        Returns:
            IndexFreshnessReport со списками stale_indexes и missing_indexes.
        """
        import hashlib

        config = self._registry.get(name)
        if not config or not config.is_active():
            return IndexFreshnessReport(
                config_name=name,
                source_mtime=None,
                all_fresh=False,
                missing_indexes=["metadata", "api", "skd", "forms"],
            )

        source_mtime = self._latest_source_mtime(config.path)

        # D2.4: вычисляем content hash исходников
        source_hash = self._compute_source_hash(config.path)

        derived_dir = self._paths.config_derived_dir(name)
        index_files = {
            "metadata": derived_dir / "unified-metadata-index.json",
            "api": self._paths.config_api_reference_json(name),
            "skd": derived_dir / "skd-index.json",
            "forms": derived_dir / "form-index.json",
        }

        # D2.4: путь к файлу с сохранённым hash
        hash_file = derived_dir / ".source-hash"

        report = IndexFreshnessReport(
            config_name=name,
            source_mtime=source_mtime,
            source_hash=source_hash,
        )

        # D2.4: читаем сохранённый hash
        stored_hash = ""
        if hash_file.exists():
            try:
                stored_hash = hash_file.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                pass

        for idx_name, idx_path in index_files.items():
            status = IndexStatus(name=idx_name, path=idx_path, exists=False, mtime=None)

            if idx_path and idx_path.exists():
                status.exists = True
                status.mtime = idx_path.stat().st_mtime
                status.size_bytes = idx_path.stat().st_size

                # D2.4: если есть сохранённый hash — используем content-based проверку
                if stored_hash:
                    if source_hash == stored_hash:
                        # Hash совпадает — индекс свежий, даже если mtime изменился
                        status.source_hash_match = True
                        # Не stale, даже если mtime source > mtime index
                    else:
                        # Hash differs — содержимое изменилось, индекс устарел
                        status.source_hash_match = False
                        status.is_stale = True
                        status.stale_reason = (
                            f"content hash изменился "
                            f"(stored={stored_hash[:12]}..., current={source_hash[:12]}...)"
                        )
                        report.stale_indexes.append(idx_name)
                        report.all_fresh = False
                else:
                    # Нет сохранённого hash — fallback на mtime проверку
                    status.source_hash_match = False
                    if source_mtime is not None and source_mtime > status.mtime:
                        status.is_stale = True
                        delta = int(source_mtime - status.mtime)
                        status.stale_reason = (
                            f"исходники новее на {delta} сек (mtime fallback, нет .source-hash) "
                            f"(source={time.ctime(source_mtime)}, "
                            f"index={time.ctime(status.mtime)})"
                        )
                        report.stale_indexes.append(idx_name)
                        report.all_fresh = False
            else:
                status.is_stale = True
                status.stale_reason = "индекс отсутствует"
                report.missing_indexes.append(idx_name)
                report.all_fresh = False

            report.indexes.append(status)

        return report

    @staticmethod
    def _latest_source_mtime(config_dir: Path) -> float | None:
        """Найти самый свежий mtime среди .xml и .bsl файлов исходников."""
        latest: float | None = None
        try:
            for pattern in ("*.xml", "*.bsl"):
                for f in config_dir.rglob(pattern):
                    if f.is_file():
                        try:
                            m = f.stat().st_mtime
                            if latest is None or m > latest:
                                latest = m
                        except (OSError, PermissionError):
                            continue
        except (OSError, PermissionError):
            pass
        return latest

    @staticmethod
    def _compute_source_hash(config_dir: Path) -> str:
        """
        D2.4 (2026-07-05): Вычислить content hash исходников конфигурации.

        Hash строится из содержимого всех .xml и .bsl файлов в config_dir.
        Если содержимое не изменилось — hash совпадает, даже если mtime изменился
        (например, после `touch`).

        Args:
            config_dir: Путь к директории конфигурации.

        Returns:
            SHA-256 hex строка (первые 64 символа).
        """
        import hashlib

        hasher = hashlib.sha256()
        try:
            files_sorted: list[Path] = []
            for pattern in ("*.xml", "*.bsl"):
                files_sorted.extend(f for f in config_dir.rglob(pattern) if f.is_file())
            files_sorted.sort()  # Детерминированный порядок

            for f in files_sorted:
                try:
                    # Включаем относительный путь + содержимое в hash
                    rel = str(f.relative_to(config_dir))
                    hasher.update(rel.encode("utf-8"))
                    hasher.update(b"\0")
                    content = f.read_bytes()
                    hasher.update(content)
                    hasher.update(b"\0")
                except (OSError, PermissionError, ValueError):
                    continue
        except (OSError, PermissionError):
            pass

        return hasher.hexdigest()

    def save_source_hash(self, name: str) -> str:
        """
        D2.4 (2026-07-05): Сохранить текущий content hash исходников.

        Вызывается после построения индексов (ConfigManager.build()),
        чтобы при следующей проверке freshness сравнивать hash, а не mtime.

        Args:
            name: Имя конфигурации.

        Returns:
            Сохранённый hash (SHA-256 hex).
        """
        config = self._registry.get(name)
        if not config or not config.is_active():
            return ""

        source_hash = self._compute_source_hash(config.path)
        derived_dir = self._paths.config_derived_dir(name)
        hash_file = derived_dir / ".source-hash"

        derived_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(source_hash, encoding="utf-8")

        return source_hash
