"""
Pytest конфигурация.
После `pip install -e .` пакет `src` доступен для импорта без sys.path хаков.
"""

import sys


def pytest_runtest_teardown(item, nextitem):
    """Cleanup: удаляем динамически загруженные модули из sys.modules после каждого теста.

    Фиксура scope='module' в test_check_standards.py загружает check_1c_standards
    в sys.modules, что загрязняет последующие тесты (test_solve и др.).
    Этот cleanup удаляет такие модули после каждого теста.
    """
    # Модули, которые могут быть загружены динамически и загрязнять sys.modules
    _dynamic_modules = [
        "check_1c_standards",
        "check_metadata_standards",
        "security_auditor",
        "code_metrics",
        "transaction_checker",
        "query_analyzer",
        "architecture_analyzer",
        "form_quality_checker",
        "skd_quality_checker",
        "diff_analyzer",  # Этап 1.2: оставлен временно, удалю после всех переносов
        "code_generator",
        "code_validator",
        "epf_builder",
        "cf_extractor",
        "metadata_extractor",
        "skd_parser",
        "form_analyzer",
        "build_api_reference",
        "build_config_index_generic",
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
