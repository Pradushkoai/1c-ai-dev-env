"""
Pytest конфигурация.
После `pip install -e .` пакет `src` доступен для импорта без sys.path хаков.
"""

import sys


def pytest_runtest_teardown(item, nextitem):
    """Cleanup: удаляем динамически загруженные модули из sys.modules после каждого теста.

    Этап 1.2 завершён: все генераторы и анализаторы перенесены в src.services.
    Больше не нужно чистить эти имена из sys.modules — они загружаются как
    нормальные Python-пакеты через importlib.import_module().

    Список оставлен для документации истории — что было перенесено в рамках
    этапа 1.2 (Группы 1-3):
      - check_1c_standards, security_auditor, transaction_checker, query_analyzer,
        code_metrics, check_metadata_standards, architecture_analyzer,
        form_quality_checker, skd_quality_checker
      - code_generator, code_validator, epf_builder
      - diff_analyzer

    Оставшиеся (ещё не перенесённые — отложено до этапов 2.x):
      - cf_extractor, metadata_extractor, skd_parser, form_analyzer (этап 2.3)
      - build_api_reference, build_config_index_generic, form_indexer (этап 2.4)
      - cf_to_xml_adapter, improved_cf_adapter, v8_metadata_parser (этап 1.2-g7)
      - xml_parser, img_grid, hbk_extractor, fast_search_1c (остаются в scripts/)
    """
    _dynamic_modules = [
        # Перенесённые в src.services.analyzers (Этап 1.2), но всё ещё могут
        # загружаться через dynamic import в некоторых тестах — чистим для
        # обеспечения консистентности между тестами.
        "check_1c_standards",
        "check_metadata_standards",
        "security_auditor",
        "code_metrics",
        "transaction_checker",
        "query_analyzer",
        "architecture_analyzer",
        "form_quality_checker",
        "skd_quality_checker",
        "diff_analyzer",
        "code_generator",
        "code_validator",
        "epf_builder",
        # Этап 2.3: metadata_extractor перенесён в src.services.metadata.extractor
        # Ещё не перенесённые — отложено до этапов 2.x
        "cf_extractor",  # Этап 1.2-g7: перенесён в src.services.cf.extractor
        "skd_parser",
        "form_analyzer",
        "build_api_reference",
        "build_config_index_generic",  # Этап 2.4: перенесён в src.services.builders.config_index
        "cf_to_xml_adapter",
        "improved_cf_adapter",
        "v8_metadata_parser",
        "xml_parser",
        "img_grid",
        "hbk_extractor",
        "fast_search_1c",
        "form_indexer",
    ]
    for mod_name in _dynamic_modules:
        sys.modules.pop(mod_name, None)
