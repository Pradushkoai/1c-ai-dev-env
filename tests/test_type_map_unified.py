"""
Тесты для P3.17: унификация TYPE_MAP (DRY).

До фикса: TYPE_MAP дублировался в двух местах:
  - src/dsl/_common.py (24 типа)
  - src/services/cfe_manager.py (41 тип)
Легко было допустить опечатку (как 'WebServce' в P0.2) или забыть
обновить один из файлов при добавлении нового типа.

После фикса: единый TYPE_MAP в src/services/object_types.py,
оба модуля импортируют его. DSL использует подмножество DSL_SUPPORTED_TYPES.
"""

from __future__ import annotations

import pytest

from src.dsl._common import TYPE_MAP as DSL_TYPE_MAP
from src.services.cfe_manager import TYPE_MAP as CFE_TYPE_MAP
from src.services.object_types import (
    DSL_SUPPORTED_TYPES,
    TYPE_MAP as UNIFIED_TYPE_MAP,
    get_type_info,
    is_dsl_supported,
    is_supported_type,
)


# ============================================================================
# Тесты — единый источник TYPE_MAP
# ============================================================================


class TestUnifiedTypeMap:
    """src/services/object_types.py — единый источник TYPE_MAP."""

    def test_unified_type_map_has_all_41_types(self) -> None:
        """Unified TYPE_MAP должен содержать все 41 типа 1С."""
        assert len(UNIFIED_TYPE_MAP) >= 41, (
            f"Unified TYPE_MAP must have >=41 types, got {len(UNIFIED_TYPE_MAP)}"
        )

    def test_each_entry_has_xml_tag_and_dir(self) -> None:
        """Каждая запись должна иметь xml_tag и dir."""
        for type_name, info in UNIFIED_TYPE_MAP.items():
            assert "xml_tag" in info, f"{type_name} missing xml_tag"
            assert "dir" in info, f"{type_name} missing dir"
            assert info["xml_tag"], f"{type_name} has empty xml_tag"
            assert info["dir"], f"{type_name} has empty dir"

    def test_no_typos_in_keys(self) -> None:
        """Все ключи должны быть корректными именами типов (без опечаток).

        Regression для P0.2: 'WebServce' → 'WebService'.
        """
        # Проверяем что нет типичных опечаток
        for typo in ("WebServce", "Catalogg", "Documentt", "Rol"):
            assert typo not in UNIFIED_TYPE_MAP, (
                f"Typo '{typo}' found in TYPE_MAP (regression)"
            )

    def test_webservice_present(self) -> None:
        """WebService должен быть в TYPE_MAP (P0.2 regression)."""
        assert "WebService" in UNIFIED_TYPE_MAP
        info = UNIFIED_TYPE_MAP["WebService"]
        assert info["xml_tag"] == "WebService"
        assert info["dir"] == "WebServices"

    def test_no_duplicate_entries(self) -> None:
        """Не должно быть дубликатов (один ключ, разные значения)."""
        # dict в Python автоматически не имеет дубликатов ключей,
        # но проверяем что значения уникальны
        xml_tags = [v["xml_tag"] for v in UNIFIED_TYPE_MAP.values()]
        dirs = [v["dir"] for v in UNIFIED_TYPE_MAP.values()]
        assert len(set(xml_tags)) == len(xml_tags), "Duplicate xml_tag found"
        assert len(set(dirs)) == len(dirs), "Duplicate dir found"


# ============================================================================
# Тесты — DRY (единственный источник)
# ============================================================================


class TestDrySingleSource:
    """TYPE_MAP должен быть определён в одном месте, остальные импортируют."""

    def test_cfe_uses_unified(self) -> None:
        """CFE TYPE_MAP должен быть identity-equal unified TYPE_MAP."""
        # Поскольку cfe_manager делает `from .object_types import TYPE_MAP`,
        # они должны быть одним и тем же объектом.
        assert CFE_TYPE_MAP is UNIFIED_TYPE_MAP, (
            "CFE TYPE_MAP must be the SAME object as unified (not a copy)"
        )

    def test_dsl_is_subset_of_unified(self) -> None:
        """DSL TYPE_MAP должен быть подмножеством unified (по ключам)."""
        dsl_keys = set(DSL_TYPE_MAP.keys())
        unified_keys = set(UNIFIED_TYPE_MAP.keys())
        assert dsl_keys.issubset(unified_keys), (
            f"DSL types not in unified: {dsl_keys - unified_keys}"
        )

    def test_dsl_entries_match_unified(self) -> None:
        """Для каждого типа в DSL, запись должна совпадать с unified."""
        for type_name, dsl_info in DSL_TYPE_MAP.items():
            unified_info = UNIFIED_TYPE_MAP[type_name]
            assert dsl_info == unified_info, (
                f"DSL entry for {type_name} ({dsl_info}) differs from "
                f"unified ({unified_info})"
            )

    def test_dsl_does_not_include_unsupported_types(self) -> None:
        """DSL не должен включать типы, не входящие в DSL_SUPPORTED_TYPES."""
        for type_name in DSL_TYPE_MAP:
            assert type_name in DSL_SUPPORTED_TYPES, (
                f"{type_name} in DSL TYPE_MAP but not in DSL_SUPPORTED_TYPES"
            )


# ============================================================================
# Тесты — helper functions
# ============================================================================


class TestHelpers:
    """Helper functions в object_types.py."""

    def test_get_type_info_existing(self) -> None:
        """get_type_info возвращает dict для существующего типа."""
        info = get_type_info("Catalog")
        assert info == {"xml_tag": "Catalog", "dir": "Catalogs"}

    def test_get_type_info_unknown(self) -> None:
        """get_type_info возвращает None для неизвестного типа."""
        assert get_type_info("UnknownType") is None

    def test_is_supported_type(self) -> None:
        """is_supported_type проверяет наличие в TYPE_MAP."""
        assert is_supported_type("Catalog") is True
        assert is_supported_type("WebService") is True
        assert is_supported_type("Unknown") is False

    def test_is_dsl_supported(self) -> None:
        """is_dsl_supported проверяет, что тип входит в DSL_SUPPORTED_TYPES."""
        # Типы, поддерживаемые DSL
        assert is_dsl_supported("Catalog") is True
        assert is_dsl_supported("WebService") is True
        # Типы, НЕ поддерживаемые DSL (только в CFE)
        assert is_dsl_supported("WSReference") is False
        assert is_dsl_supported("XDTOPackage") is False
        assert is_dsl_supported("Subsystem") is False


# ============================================================================
# Тесты — backward compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Существующий API должен продолжать работать."""

    def test_dsl_type_map_importable(self) -> None:
        """`from src.dsl._common import TYPE_MAP` должен работать."""
        from src.dsl._common import TYPE_MAP

        assert isinstance(TYPE_MAP, dict)
        assert len(TYPE_MAP) > 0

    def test_cfe_type_map_importable(self) -> None:
        """`from src.services.cfe_manager import TYPE_MAP` должен работать."""
        from src.services.cfe_manager import TYPE_MAP

        assert isinstance(TYPE_MAP, dict)
        assert len(TYPE_MAP) > 0

    def test_dsl_has_same_keys_as_before(self) -> None:
        """DSL TYPE_MAP должен содержать все типы, что и до рефакторинга."""
        # Типы, которые были в dsl/_common.py до P3.17
        expected_dsl_types = {
            "Catalog", "Document", "Enum", "Constant",
            "InformationRegister", "AccumulationRegister",
            "AccountingRegister", "CalculationRegister",
            "ChartOfAccounts", "ChartOfCharacteristicTypes",
            "ChartOfCalculationTypes", "BusinessProcess", "Task",
            "ExchangePlan", "DocumentJournal", "Report", "DataProcessor",
            "CommonModule", "ScheduledJob", "EventSubscription",
            "DefinedType", "HTTPService", "WebService",
        }
        assert set(DSL_TYPE_MAP.keys()) == expected_dsl_types, (
            f"DSL TYPE_MAP keys changed: expected {expected_dsl_types}, "
            f"got {set(DSL_TYPE_MAP.keys())}"
        )

    def test_cfe_has_same_keys_as_before(self) -> None:
        """CFE TYPE_MAP должен содержать все типы, что и до рефакторинга."""
        # Типы, которые были в cfe_manager.py до P3.17
        # (41 тип, включая добавленные в CFE только)
        cfe_only_types = {
            "CommonForm", "CommonCommand", "CommonTemplate", "CommonPicture",
            "CommonAttribute", "CommandGroup", "DocumentNumerator",
            "FilterCriterion", "FunctionalOption", "FunctionalOptionParameter",
            "Sequence", "SessionParameter", "SettingsStorage",
            "Style", "Subsystem", "Role", "WSReference", "XDTOPackage",
        }
        # Все CFE-only типы должны быть в CFE_TYPE_MAP
        for t in cfe_only_types:
            assert t in CFE_TYPE_MAP, (
                f"CFE-only type {t} missing from CFE TYPE_MAP"
            )
        # И НЕ должны быть в DSL_TYPE_MAP
        for t in cfe_only_types:
            assert t not in DSL_TYPE_MAP, (
                f"CFE-only type {t} should NOT be in DSL TYPE_MAP"
            )
